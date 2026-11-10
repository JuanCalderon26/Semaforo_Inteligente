"""
=============================================================================
SEMÁFORO INTELIGENTE ADAPTATIVO - AGENTE DUAL PARA RASPBERRY PI
=============================================================================
Configuración:
- Control de dos carriles de maqueta vehicular:
  * Carril 1: CSI Camera v1.3 (Picamera2) O Webcam USB #1.
  * Carril 2: Webcam USB #2.
  * Soporte completo para 2 Webcams USB simultáneas con auto-detección y reconexión en caliente.
- Control de 6 LEDs (2 semáforos completos) mediante GPIO BCM:
  * Carril 1: Rojo 17, Amarillo 27, Verde 22
  * Carril 2: Rojo 23, Amarillo 24, Verde 25
  * GNDs: Pines 6, 9, 14, 20, 30, 34, 39.

Endpoints expuestos:
- /lane1/stream  ó  /stream/lane1  : Video MJPEG Carril 1
- /lane2/stream  ó  /stream/lane2  : Video MJPEG Carril 2
- /lane1/leds?r=1&y=0&g=0         : Control semáforo Carril 1
- /lane2/leds?r=1&y=0&g=0         : Control semáforo Carril 2
- /leds?lane=1&r=1&y=0&g=0        : Endpoint unificado de control
- /status                         : Diagnóstico completo del hardware y cámaras
- /                               : Panel web de prueba en vivo (2 cámaras + 6 LEDs)
=============================================================================
"""

import argparse
import glob
import os
import socket
import sys
import threading
import time
from typing import Optional, Tuple, List, Dict, Any

import cv2
import numpy as np
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
import uvicorn

# Detección de hardware Raspberry Pi
HAS_PICAMERA = False
HAS_GPIO = False

try:
    from picamera2 import Picamera2
    HAS_PICAMERA = True
except ImportError:
    pass

try:
    from gpiozero import LED
    HAS_GPIO = True
except ImportError:
    pass

parser = argparse.ArgumentParser(description="Agente Dual de Cámaras y LEDs para Raspberry Pi")
parser.add_argument("--port", type=int, default=8080, help="Puerto HTTP para el servicio")
parser.add_argument("--lane1-dev", type=str, default=None, help="Índice o ruta V4L2 para Carril 1 (auto si no se especifica)")
parser.add_argument("--lane2-dev", type=str, default=None, help="Índice o ruta V4L2 para Carril 2 (auto si no se especifica)")
parser.add_argument("--usb-index", type=int, default=None, help="Compatibilidad con versión previa")
parser.add_argument("--width", type=int, default=320, help="Ancho de frame")
parser.add_argument("--height", type=int, default=240, help="Alto de frame")
parser.add_argument("--fps", type=int, default=25, help="FPS objetivo")

# Pines Carril 1
parser.add_argument("--pin-l1-red", type=int, default=17, help="GPIO BCM Rojo Carril 1")
parser.add_argument("--pin-l1-yellow", type=int, default=27, help="GPIO BCM Amarillo Carril 1")
parser.add_argument("--pin-l1-green", type=int, default=22, help="GPIO BCM Verde Carril 1")

# Pines Carril 2
parser.add_argument("--pin-l2-red", type=int, default=23, help="GPIO BCM Rojo Carril 2")
parser.add_argument("--pin-l2-yellow", type=int, default=24, help="GPIO BCM Amarillo Carril 2")
parser.add_argument("--pin-l2-green", type=int, default=25, help="GPIO BCM Verde Carril 2")

args, _ = parser.parse_known_args()

app = FastAPI(title="Agente Dual - Raspberry Pi (CSI/USB + LEDs)")

# ==========================================
# GESTIÓN DE HARDWARE LEDS (GPIO)
# ==========================================
lights_state = {
    "lane1": {"red": 1, "yellow": 0, "green": 0},
    "lane2": {"red": 1, "yellow": 0, "green": 0}
}

gpio_leds = {
    "lane1": {"red": None, "yellow": None, "green": None},
    "lane2": {"red": None, "yellow": None, "green": None}
}

if HAS_GPIO:
    try:
        gpio_leds["lane1"]["red"] = LED(args.pin_l1_red)
        gpio_leds["lane1"]["yellow"] = LED(args.pin_l1_yellow)
        gpio_leds["lane1"]["green"] = LED(args.pin_l1_green)

        gpio_leds["lane2"]["red"] = LED(args.pin_l2_red)
        gpio_leds["lane2"]["yellow"] = LED(args.pin_l2_yellow)
        gpio_leds["lane2"]["green"] = LED(args.pin_l2_green)
        print("[GPIO] Inicializados 6 pines BCM para Carril 1 y Carril 2.")
    except Exception as e:
        print(f"[GPIO] Advertencia al configurar pines: {e}")
else:
    print("[GPIO] Modo simulación activo (gpiozero no detectado).")

def apply_leds(lane_key: str, r: int, y: int, g: int):
    """Actualiza el estado físico de los LEDs para el carril indicado."""
    lights_state[lane_key]["red"] = 1 if r > 0 else 0
    lights_state[lane_key]["yellow"] = 1 if y > 0 else 0
    lights_state[lane_key]["green"] = 1 if g > 0 else 0

    if HAS_GPIO:
        leds = gpio_leds.get(lane_key, {})
        for color, val in lights_state[lane_key].items():
            led_obj = leds.get(color)
            if led_obj:
                try:
                    if val:
                        led_obj.on()
                    else:
                        led_obj.off()
                except Exception:
                    pass

# Iniciar ambos semáforos en Rojo por seguridad
apply_leds("lane1", 1, 0, 0)
apply_leds("lane2", 1, 0, 0)

# ==========================================
# UTILIDADES DE SISTEMA
# ==========================================
def get_cpu_temp() -> str:
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            t = float(f.read().strip()) / 1000.0
            return f"{t:.1f} °C"
    except Exception:
        return "N/A"

def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# ==========================================
# DETECCIÓN Y GESTIÓN DE CÁMARAS
# ==========================================
picam2_obj = None

def get_available_v4l2_devices() -> List[int]:
    """Escanea y valida dispositivos V4L2 disponibles para captura de video."""
    candidates = []
    # 1. Enlaces por ID (prioritarios)
    for link in sorted(glob.glob("/dev/v4l/by-id/*index0")):
        try:
            real_path = os.path.realpath(link)
            idx = int(real_path.replace("/dev/video", ""))
            if idx not in candidates:
                candidates.append(idx)
        except Exception:
            pass

    # 2. Índices estándar comunes
    for idx in [0, 2, 4, 1, 3]:
        if idx not in candidates and os.path.exists(f"/dev/video{idx}"):
            candidates.append(idx)

    # 3. Probar si pueden abrirse y capturar
    working = []
    for idx in candidates:
        try:
            cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
            if cap.isOpened():
                # Intentar configurar MJPG para reducir ancho de banda USB
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None and frame.size > 0:
                    working.append(idx)
        except Exception:
            pass
    return working

# Frames actuales y locks
latest_jpeg_l1: Optional[bytes] = None
latest_jpeg_l2: Optional[bytes] = None
lock_l1 = threading.Lock()
lock_l2 = threading.Lock()

camera_info = {
    "lane1": {"name": "Iniciando...", "device": "Desconocido", "status": "Iniciando"},
    "lane2": {"name": "Iniciando...", "device": "Desconocido", "status": "Iniciando"}
}

def make_fallback_frame(lane_id: int, label: str, sublabel: str = "") -> bytes:
    """Genera un cuadro sintético informativo cuando la cámara física está desconectada."""
    img = np.full((args.height, args.width, 3), (28, 30, 36), dtype=np.uint8)
    
    cv2.putText(img, f"CARRIL {lane_id}: {label}", (12, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 200), 1)
    if sublabel:
        cv2.putText(img, sublabel, (12, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (160, 180, 200), 1)
        
    cv2.putText(img, f"Temp CPU: {get_cpu_temp()}", (12, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 200, 200), 1)
    cv2.putText(img, f"IP: {get_local_ip()}:{args.port}", (12, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 200, 200), 1)
    
    # Dibujar estado del semáforo en el fallback
    lane_key = f"lane{lane_id}"
    cur_state = lights_state[lane_key]
    color = (0, 0, 255) if cur_state["red"] else ((0, 220, 255) if cur_state["yellow"] else (0, 255, 0))
    cv2.circle(img, (args.width - 30, 35), 12, color, -1)
    cv2.circle(img, (args.width - 30, 35), 12, (255, 255, 255), 1)

    # Animación sutil de timestamp
    ts = time.strftime("%H:%M:%S")
    cv2.putText(img, f"Hora: {ts}", (12, args.height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (120, 140, 160), 1)

    _, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return enc.tobytes()

# ==========================================
# HILOS DE CAPTURA INDEPENDIENTES
# ==========================================

def get_assigned_devices() -> Tuple[Optional[Any], Optional[Any]]:
    """Determina los dispositivos asignados a Carril 1 y Carril 2."""
    global picam2_obj
    
    # 1. Probar cámara CSI v1.3 si existe
    if HAS_PICAMERA and picam2_obj is None:
        try:
            p2 = Picamera2()
            cfg = p2.create_video_configuration(
                main={"size": (args.width, args.height), "format": "RGB888"},
                controls={"FrameRate": args.fps}
            )
            p2.configure(cfg)
            p2.start()
            picam2_obj = p2
            print("[CSI] Pi Camera v1.3 lista para Carril 1.")
        except Exception:
            picam2_obj = None

    # Si se especificaron overrides manuales
    l1_target = args.lane1_dev
    l2_target = args.lane2_dev or args.usb_index

    # Escaneo dinámico si no hay override
    available = get_available_v4l2_devices()
    print(f"[CÁMARAS] Dispositivos V4L2 funcionales detectados: {available}")

    if picam2_obj is not None:
        # CSI en Carril 1, USB en Carril 2
        l1_dev = "CSI"
        l2_dev = l2_target if l2_target is not None else (available[0] if available else None)
    else:
        # Modo Dual USB: Carril 1 = USB1, Carril 2 = USB2
        if l1_target is not None:
            l1_dev = int(l1_target) if str(l1_target).isdigit() else l1_target
        else:
            l1_dev = available[0] if len(available) > 0 else None

        if l2_target is not None:
            l2_dev = int(l2_target) if str(l2_target).isdigit() else l2_target
        else:
            # Segundo dispositivo distinto del primero
            remaining = [d for d in available if d != l1_dev]
            l2_dev = remaining[0] if remaining else None

    return l1_dev, l2_dev

def worker_lane(lane_id: int):
    """Hilo de captura robusto para un carril (con auto-reconexión independiente)."""
    global latest_jpeg_l1, latest_jpeg_l2, picam2_obj
    
    lane_key = f"lane{lane_id}"
    lock = lock_l1 if lane_id == 1 else lock_l2
    cap_obj = None
    current_dev = None

    while True:
        try:
            # Si es Carril 1 y hay cámara CSI activa
            if lane_id == 1 and picam2_obj is not None:
                camera_info["lane1"] = {
                    "name": "Raspberry Pi Camera (CSI)",
                    "device": "CSI Port",
                    "status": "Transfiriendo video en vivo"
                }
                while picam2_obj is not None:
                    try:
                        frame = picam2_obj.capture_array()
                        if frame is not None:
                            ret, enc = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                            if ret:
                                with lock:
                                    latest_jpeg_l1 = enc.tobytes()
                    except Exception as e:
                        print(f"[CSI] Error en captura: {e}")
                        break
                    time.sleep(1.0 / args.fps)

            # Para cámaras USB
            if cap_obj is None or not cap_obj.isOpened():
                l1_dev, l2_dev = get_assigned_devices()
                target_dev = l1_dev if lane_id == 1 else l2_dev

                if target_dev is None or target_dev == "CSI":
                    # No hay dispositivo conectado para este carril
                    camera_info[lane_key] = {
                        "name": f"Webcam USB Carril {lane_id}",
                        "device": "No detectada",
                        "status": "Esperando conexión de cámara..."
                    }
                    fallback = make_fallback_frame(lane_id, "CAMARA NO DETECTADA", "Conecte la webcam USB al puerto USB")
                    with lock:
                        if lane_id == 1:
                            latest_jpeg_l1 = fallback
                        else:
                            latest_jpeg_l2 = fallback
                    time.sleep(1.5)
                    continue

                # Intentar abrir cámara USB
                idx = int(target_dev) if str(target_dev).isdigit() else target_dev
                print(f"[CARRIL {lane_id}] Abriendo cámara USB en /dev/video{idx}...")
                cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
                    cap.set(cv2.CAP_PROP_FPS, args.fps)
                    for _ in range(2):
                        cap.read()
                    cap_obj = cap
                    current_dev = idx
                    camera_info[lane_key] = {
                        "name": f"Webcam USB (Carril {lane_id})",
                        "device": f"/dev/video{idx}",
                        "status": f"En vivo ({args.width}x{args.height} @ {args.fps}fps)"
                    }
                    print(f"[CARRIL {lane_id}] Webcam USB lista en /dev/video{idx}.")
                else:
                    camera_info[lane_key] = {
                        "name": f"Webcam USB Carril {lane_id}",
                        "device": f"/dev/video{idx}",
                        "status": "Error al abrir dispositivo"
                    }
                    fallback = make_fallback_frame(lane_id, f"ERROR EN /dev/video{idx}", "Reintentando apertura...")
                    with lock:
                        if lane_id == 1:
                            latest_jpeg_l1 = fallback
                        else:
                            latest_jpeg_l2 = fallback
                    time.sleep(2.0)
                    continue

            # Capturar fotograma
            ret, frame = cap_obj.read()
            if ret and frame is not None and frame.size > 0:
                if frame.shape[1] != args.width or frame.shape[0] != args.height:
                    frame = cv2.resize(frame, (args.width, args.height))
                ret_enc, enc = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                if ret_enc:
                    frame_bytes = enc.tobytes()
                    with lock:
                        if lane_id == 1:
                            latest_jpeg_l1 = frame_bytes
                        else:
                            latest_jpeg_l2 = frame_bytes
            else:
                print(f"[CARRIL {lane_id}] Fallo de lectura en /dev/video{current_dev}, reconectando...")
                try:
                    cap_obj.release()
                except Exception:
                    pass
                cap_obj = None
                time.sleep(1.0)

        except Exception as e:
            print(f"[CARRIL {lane_id}] Excepción en hilo de captura: {e}")
            if cap_obj:
                try:
                    cap_obj.release()
                except Exception:
                    pass
                cap_obj = None
            time.sleep(1.5)

        time.sleep(1.0 / args.fps)

# Iniciar hilos dedicados para Carril 1 y Carril 2
thread_l1 = threading.Thread(target=worker_lane, args=(1,), daemon=True)
thread_l2 = threading.Thread(target=worker_lane, args=(2,), daemon=True)
thread_l1.start()
thread_l2.start()

def mjpeg_generator(lane: int):
    """Generador HTTP para streaming MJPEG continuo."""
    lock = lock_l1 if lane == 1 else lock_l2
    while True:
        with lock:
            frame_bytes = latest_jpeg_l1 if lane == 1 else latest_jpeg_l2

        if frame_bytes:
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")

        time.sleep(1.0 / args.fps)

# ==========================================
# ENDPOINTS REST & STREAMING
# ==========================================

@app.get("/lane1/stream")
@app.get("/stream/lane1")
def stream_lane1():
    """Stream de video para Carril 1."""
    return StreamingResponse(mjpeg_generator(1), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/lane2/stream")
@app.get("/stream/lane2")
def stream_lane2():
    """Stream de video para Carril 2."""
    return StreamingResponse(mjpeg_generator(2), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/lane1/leds")
def leds_lane1(r: Optional[int] = None, y: Optional[int] = None, g: Optional[int] = None):
    nr = lights_state["lane1"]["red"] if r is None else r
    ny = lights_state["lane1"]["yellow"] if y is None else y
    ng = lights_state["lane1"]["green"] if g is None else g
    apply_leds("lane1", nr, ny, ng)
    return {"lane": 1, "red": nr, "yellow": ny, "green": ng, "status": "ok"}

@app.get("/lane2/leds")
def leds_lane2(r: Optional[int] = None, y: Optional[int] = None, g: Optional[int] = None):
    nr = lights_state["lane2"]["red"] if r is None else r
    ny = lights_state["lane2"]["yellow"] if y is None else y
    ng = lights_state["lane2"]["green"] if g is None else g
    apply_leds("lane2", nr, ny, ng)
    return {"lane": 2, "red": nr, "yellow": ny, "green": ng, "status": "ok"}

@app.get("/leds")
def leds_unified(lane: int = 1, r: Optional[int] = None, y: Optional[int] = None, g: Optional[int] = None):
    lane_key = f"lane{lane}"
    if lane_key not in lights_state:
        return JSONResponse({"error": "Carril no válido (use 1 o 2)"}, status_code=400)

    nr = lights_state[lane_key]["red"] if r is None else r
    ny = lights_state[lane_key]["yellow"] if y is None else y
    ng = lights_state[lane_key]["green"] if g is None else g
    apply_leds(lane_key, nr, ny, ng)
    return {"lane": lane, "red": nr, "yellow": ny, "green": ng, "status": "ok"}

@app.get("/status")
def status():
    return {
        "device": "Raspberry Pi (Nodo Centralizado Dual)",
        "ip": get_local_ip(),
        "port": args.port,
        "cpu_temp": get_cpu_temp(),
        "lanes": {
            "lane1": {
                "camera": camera_info["lane1"]["name"],
                "device": camera_info["lane1"]["device"],
                "status": camera_info["lane1"]["status"],
                "stream_url": f"http://{get_local_ip()}:{args.port}/lane1/stream",
                "leds_url": f"http://{get_local_ip()}:{args.port}/lane1/leds",
                "state": lights_state["lane1"],
                "gpios": {"red": args.pin_l1_red, "yellow": args.pin_l1_yellow, "green": args.pin_l1_green}
            },
            "lane2": {
                "camera": camera_info["lane2"]["name"],
                "device": camera_info["lane2"]["device"],
                "status": camera_info["lane2"]["status"],
                "stream_url": f"http://{get_local_ip()}:{args.port}/lane2/stream",
                "leds_url": f"http://{get_local_ip()}:{args.port}/lane2/leds",
                "state": lights_state["lane2"],
                "gpios": {"red": args.pin_l2_red, "yellow": args.pin_l2_yellow, "green": args.pin_l2_green}
            }
        }
    }

@app.get("/", response_class=HTMLResponse)
def index_page():
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Semáforo Inteligente - Agente Dual</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }}
            .container {{ max-width: 1100px; margin: 0 auto; }}
            h1 {{ font-size: 22px; text-align: center; margin-bottom: 24px; color: #38bdf8; }}
            .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
            .card {{ background: #1e293b; border-radius: 12px; padding: 16px; border: 1px solid #334155; }}
            .stream-box {{ background: #000; border-radius: 8px; overflow: hidden; aspect-ratio: 4/3; display: flex; align-items: center; justify-content: center; }}
            .stream-box img {{ width: 100%; height: 100%; object-fit: contain; }}
            .btn-row {{ display: flex; gap: 8px; margin-top: 12px; }}
            .btn {{ flex: 1; padding: 10px; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; }}
            .btn-r {{ background: #ef4444; color: white; }}
            .btn-y {{ background: #eab308; color: black; }}
            .btn-g {{ background: #22c55e; color: white; }}
            .info-badge {{ font-size: 13px; color: #94a3b8; margin-top: 8px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚦 Semáforo Inteligente - Panel del Agente Dual</h1>
            <div class="grid">
                <div class="card">
                    <h3>Carril 1 ({camera_info['lane1']['device']})</h3>
                    <div class="stream-box"><img src="/lane1/stream" alt="Carril 1"></div>
                    <div class="info-badge">{camera_info['lane1']['name']} - {camera_info['lane1']['status']}</div>
                    <div class="btn-row">
                        <button class="btn btn-g" onclick="fetch('/lane1/leds?r=0&y=0&g=1')">🟢 Verde</button>
                        <button class="btn btn-y" onclick="fetch('/lane1/leds?r=0&y=1&g=0')">🟡 Amarillo</button>
                        <button class="btn btn-r" onclick="fetch('/lane1/leds?r=1&y=0&g=0')">🔴 Rojo</button>
                    </div>
                </div>
                <div class="card">
                    <h3>Carril 2 ({camera_info['lane2']['device']})</h3>
                    <div class="stream-box"><img src="/lane2/stream" alt="Carril 2"></div>
                    <div class="info-badge">{camera_info['lane2']['name']} - {camera_info['lane2']['status']}</div>
                    <div class="btn-row">
                        <button class="btn btn-g" onclick="fetch('/lane2/leds?r=0&y=0&g=1')">🟢 Verde</button>
                        <button class="btn btn-y" onclick="fetch('/lane2/leds?r=0&y=1&g=0')">🟡 Amarillo</button>
                        <button class="btn btn-r" onclick="fetch('/lane2/leds?r=1&y=0&g=0')">🔴 Rojo</button>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

if __name__ == "__main__":
    print("=================================================================")
    print(f"Iniciando Agente Dual en http://0.0.0.0:{args.port}")
    print(f"  - Feed Carril 1: http://{get_local_ip()}:{args.port}/lane1/stream")
    print(f"  - Feed Carril 2: http://{get_local_ip()}:{args.port}/lane2/stream")
    print(f"  - Panel de control web: http://{get_local_ip()}:{args.port}/")
    print("=================================================================")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
