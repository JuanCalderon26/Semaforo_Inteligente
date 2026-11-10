# 🚦 Semáforo Inteligente Adaptativo con Visión Artificial

Sistema integral de control de tráfico inteligente para maquetas y vías a escala, utilizando **Visión por Computadora (Computer Vision)**, una **Máquina de Estados Finita (FSM)** adaptativa y hardware embebido con **Raspberry Pi Zero 2 W** (con cámara CSI v1.3 y Webcam USB).

El sistema analiza en tiempo real el flujo y la cola de vehículos de juguete en dos carriles independientes, ajustando dinámicamente los tiempos de las fases verde y amarilla para optimizar el tráfico y registrar trazabilidad completa en SQLite.

---

## 📸 Arquitectura del Sistema

El proyecto está diseñado bajo una arquitectura modular y desacoplada:

```
                                  +-----------------------------+
                                  |   1x RASPBERRY PI ZERO 2 W  |
                                  |   (Nodo Periférico Edge)    |
                                  +--------------+--------------+
                                                 |
                       +-------------------------+-------------------------+
                       |                                                   |
              Puerto CSI (Ribbon 22p)                             Puerto Micro-USB (OTG)
                       |                                                   |
            [ CARRIL 1: Pi Cam v1.3 ]                            [ CARRIL 2: Webcam USB ]
               Sensor OV5647 5MP                                    Webcam estándar USB
                       |                                                   |
                       +-------------------------+-------------------------+
                                                 |
                                  40 Pines GPIO (Lógica 3.3V)
                     +-----------------------------------+-----------------------------------+
                     | Semáforo Carril 1:                | Semáforo Carril 2:                |
                     | - Rojo:     GPIO 17 (Pin 11)      | - Rojo:     GPIO 23 (Pin 16)      |
                     | - Amarillo: GPIO 27 (Pin 13)      | - Amarillo: GPIO 24 (Pin 18)      |
                     | - Verde:    GPIO 22 (Pin 15)      | - Verde:    GPIO 25 (Pin 22)      |
                     | - GND:      Pin 6 / 9             | - GND:      Pin 20 / 30           |
                     +-----------------------------------+-----------------------------------+
                                                 ▲
                                                 │ HTTP REST / MJPEG (Wi-Fi o Red Local)
                                                 ▼
                                  +-----------------------------+
                                  |   SERVIDOR CENTRAL CONTROL  |
                                  |   (PC o Raspberry Pi)       |
                                  +--------------+--------------+
                                  | • FastAPI + WebSockets      |
                                  | • OpenCV (MOG2 / YOLOv8)    |
                                  | • Trazabilidad SQLite       |
                                  +--------------+--------------+
                                                 ▲
                                                 │ WebSockets (10 Hz)
                                                 ▼
                                  +-----------------------------+
                                  |    PANEL DE CONTROL WEB     |
                                  |  Dashboard en Tiempo Real   |
                                  |  HTML5 + Vanilla CSS + JS   |
                                  +-----------------------------+
```

---

## ⚙️ Reglas de la Máquina de Estados Adaptativa

1. **Fase Verde Base (15 segundos):** Tiempo asignado por defecto para el carril activo.
2. **Corte Temprano por Carril Vacío (5 segundos):** Si a los 5 segundos de iniciada la fase verde se detectan **0 vehículos** en espera, se cancela el tiempo restante y se inicia la transición al carril contrario.
3. **Extensión Adaptativa a 20 segundos:** Si al alcanzar los 15 segundos no hay flujo continuo (**menos de 2 vehículos** en la zona de retención), se otorgan **5 segundos adicionales** (total 20s) para permitir el desahogo completo del carril.
4. **Fase de Seguridad en Amarillo (2 segundos):** Transición segura de advertencia antes de dar el paso verde al carril opuesto.
5. **Trazabilidad 100% en Base de Datos:** Cada transición almacena fecha y hora exacta, carril, duración efectiva, causa del cambio y vehículos presentes.

---

## 🔌 Conexiones de Hardware y Pines GPIO

La Raspberry Pi Zero 2 W gestiona ambos semáforos a través de su cabezal de 40 pines. Cada LED debe llevar una resistencia limitadora de **220Ω o 330Ω**:

| Señal | Carril | Pin Físico | Pin BCM (GPIO) | Conexión en Protoboard |
| :--- | :---: | :---: | :---: | :--- |
| **Luz Roja** | Carril 1 | Pin 11 | `GPIO 17` | Ánodo -> Resistencia 220Ω -> Pin 11 / Cátodo a GND |
| **Luz Amarilla** | Carril 1 | Pin 13 | `GPIO 27` | Ánodo -> Resistencia 220Ω -> Pin 13 / Cátodo a GND |
| **Luz Verde** | Carril 1 | Pin 15 | `GPIO 22` | Ánodo -> Resistencia 220Ω -> Pin 15 / Cátodo a GND |
| **GND** | Carril 1 | Pin 6 o 9 | `GND` | Riel común negativo |
| | | | | |
| **Luz Roja** | Carril 2 | Pin 16 | `GPIO 23` | Ánodo -> Resistencia 220Ω -> Pin 16 / Cátodo a GND |
| **Luz Amarilla** | Carril 2 | Pin 18 | `GPIO 24` | Ánodo -> Resistencia 220Ω -> Pin 18 / Cátodo a GND |
| **Luz Verde** | Carril 2 | Pin 22 | `GPIO 25` | Ánodo -> Resistencia 220Ω -> Pin 22 / Cátodo a GND |
| **GND** | Carril 2 | Pin 20 o 30 | `GND` | Riel común negativo |

> [!NOTE]
> - **Cámara 1 (Pi Camera v1.3):** Conectar al puerto CSI con el cable plano adaptador para Pi Zero (22 pines, paso 0.5 mm).
> - **Cámara 2 (Webcam USB):** Conectar al puerto Micro-USB de datos de la Pi mediante un cable o adaptador Micro-USB OTG.

---

## 🚀 Guía de Instalación y Uso

### 1. Preparar la Raspberry Pi Zero 2 W

En la Raspberry Pi (con Raspberry Pi OS Bookworm o Bullseye):

```bash
# 1. Instalar dependencias de sistema, cámara y GPIO
sudo apt update
sudo apt install -y python3-pip python3-picamera2 python3-opencv python3-gpiozero v4l-utils

# 2. Clonar el repositorio
cd ~
git clone https://github.com/<tu-usuario>/semaforo_inteligente.git
cd semaforo_inteligente/raspberry_pi

# 3. Instalar dependencias del agente
pip install fastapi uvicorn --break-system-packages

### 1. Preparar la Raspberry Pi Zero 2 W (Modo Autónomo / Punto de Acceso)

En la Raspberry Pi (con Raspberry Pi OS Bookworm o Bullseye):

```bash
# 1. Instalar dependencias de sistema, cámara y GPIO
sudo apt update
sudo apt install -y python3-pip python3-picamera2 python3-opencv python3-gpiozero v4l-utils

# 2. Clonar el repositorio
cd ~
git clone https://github.com/<tu-usuario>/semaforo_inteligente.git
cd semaforo_inteligente/raspberry_pi

# 3. Instalar dependencias web
pip install fastapi uvicorn --break-system-packages

# 4. Configurar Hostname ('semaforo') y Red Wi-Fi Propia (Hotspot):
./configurar_hotspot.sh

# 5. Configurar autoinicio para que al encender la Pi levante todo el sistema:
sudo cp semaforo_completo.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now semaforo_completo.service
```

---

### 2. Conexión y Visualización del Dashboard

1. Enciende la Raspberry Pi Zero 2 W.
2. Desde tu celular, tablet o laptop, conéctate a la red Wi-Fi emitida por la Pi:
   - **Nombre de Red (SSID):** `Semaforo-Inteligente`
   - **Contraseña:** `semaforo123`
3. Abre tu navegador web y entra a:
   - **`http://10.42.0.1:8000`**  o  **`http://semaforo.local:8000`**

¡El dashboard web cargará de inmediato con ambas cámaras en vivo, conteo de autos y control de los semáforos en tiempo real sin requerir routers externos ni conexión a internet!

---

## 🗂️ Estructura del Repositorio

```text
semaforo_inteligente/
├── raspberry_pi/                  # Código y scripts para Raspberry Pi Zero 2 W
│   ├── dual_camera_agent.py      # Agente para 1 Pi Zero 2 W + 2 cámaras (CSI v1.3 + USB) y 6 LEDs
│   ├── configurar_hotspot.sh     # Script para crear red Wi-Fi propia automática
│   ├── start_all.sh              # Script de arranque unificado
│   ├── semaforo_completo.service # Servicio systemd de autoinicio
│   ├── requirements_pi.txt       # Dependencias de la Raspberry Pi Zero 2 W
│   └── README_RPI.md             # Guía técnica detallada de cableado y setup de la Pi
├── server/                       # Servidor central de control y visión artificial
│   ├── app.py                    # Aplicación FastAPI, WebSockets y streaming MJPEG
│   ├── traffic_controller.py     # Máquina de estados (FSM) y lógica adaptativa
│   ├── vision_tracker.py         # Motor de visión (Lazos virtuales MOG2 + YOLOv8 + Simulación)
│   └── database.py               # Persistencia de trazabilidad con SQLite
├── web/                          # Dashboard web interactivo de monitoreo
│   ├── index.html                # Interfaz moderna con semáforos 3D y telemetría
│   ├── style.css                 # Diseño CSS3 premium (glassmorphism y modo oscuro)
│   └── app.js                    # Cliente WebSockets y renderizado en tiempo real
├── tests/                        # Pruebas unitarias automatizadas
│   └── test_traffic_fsm.py       # Cobertura de base de datos, FSM y agente de hardware
└── requirements.txt              # Dependencias de Python para el servidor central
```

---

## 🧪 Pruebas Unitarias

Para ejecutar el conjunto de pruebas del sistema:

```bash
python3 -m unittest discover tests
```

---

## 📄 Licencia

Este proyecto está distribuido bajo la licencia MIT. Consulta el archivo `LICENSE` para más información.
