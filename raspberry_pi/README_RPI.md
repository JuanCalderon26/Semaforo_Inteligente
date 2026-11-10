# Guía de Instalación: 1x Raspberry Pi Zero 2 W con 2 Cámaras (CSI v1.3 + Webcam USB)

Esta guía explica la arquitectura de **un solo nodo centralizado** utilizando **1 Raspberry Pi Zero 2 W** capaz de capturar simultáneamente los dos carriles y gobernar los 6 LEDs de ambos semáforos.

---

## 1. Arquitectura de Hardware

```
                     +----------------------------------------+
                     |         Raspberry Pi Zero 2 W          |
                     |  SoC BCM2710A1 Quad-Core @ 1GHz        |
                     +---+--------------------------------+---+
                         |                                |
       Puerto CSI (Ribbon 22p)                 Puerto Micro-USB (OTG)
                         |                                |
        +----------------+---+                  +---------+----------+
        |  Pi Camera v1.3    |                  |  Adaptador OTG     |
        |  (Sensor OV5647)   |                  |  + Webcam USB      |
        +--------------------+                  +--------------------+
             [ CARRIL 1 ]                            [ CARRIL 2 ]

                     GPIO Header de 40 Pines (Lógica 3.3V)
     +-----------------------------------+-----------------------------------+
     | Semáforo Carril 1:                | Semáforo Carril 2:                |
     | - Rojo:     GPIO 17 (Pin 11)      | - Rojo:     GPIO 23 (Pin 16)      |
     | - Amarillo: GPIO 27 (Pin 13)      | - Amarillo: GPIO 24 (Pin 18)      |
     | - Verde:    GPIO 22 (Pin 15)      | - Verde:    GPIO 25 (Pin 22)      |
     | - GND:      Pin 6 / 9 / 14        | - GND:      Pin 20 / 30 / 34      |
     +-----------------------------------+-----------------------------------+
```

---

## 2. Diagrama de Pines GPIO (40 Pines)

Conecta cada LED en serie con una resistencia de **220Ω o 330Ω**:

| Señal | Carril | Pin Físico | Pin BCM (GPIO) | Conexión en Protoboard |
| :--- | :---: | :---: | :---: | :--- |
| **Luz Roja C1** | Carril 1 | Pin 11 | `GPIO 17` | Ánodo -> Resistencia 220Ω -> Pin 11 / Cátodo a GND |
| **Luz Amarilla C1**| Carril 1 | Pin 13 | `GPIO 27` | Ánodo -> Resistencia 220Ω -> Pin 13 / Cátodo a GND |
| **Luz Verde C1** | Carril 1 | Pin 15 | `GPIO 22` | Ánodo -> Resistencia 220Ω -> Pin 15 / Cátodo a GND |
| **GND Común C1** | Carril 1 | Pin 6 o 9 | `GND` | Riel negativo del protoboard |
| | | | | |
| **Luz Roja C2** | Carril 2 | Pin 16 | `GPIO 23` | Ánodo -> Resistencia 220Ω -> Pin 16 / Cátodo a GND |
| **Luz Amarilla C2**| Carril 2 | Pin 18 | `GPIO 24` | Ánodo -> Resistencia 220Ω -> Pin 18 / Cátodo a GND |
| **Luz Verde C2** | Carril 2 | Pin 22 | `GPIO 25` | Ánodo -> Resistencia 220Ω -> Pin 22 / Cátodo a GND |
| **GND Común C2** | Carril 2 | Pin 20 o 30 | `GND` | Riel negativo del protoboard |

---

## 3. Conexión de las 2 Cámaras

1. **Cámara 1 - Pi Camera v1.3 (CSI)**:
   - Requiere el cable flex específico para Raspberry Pi Zero (15 pines a 22 pines estrechos).
   - En la Pi Zero 2 W: Contactos dorados hacia la placa (hacia abajo).
   - En la cámara v1.3: Contactos dorados hacia el respaldo.
2. **Cámara 2 - Cámara Web USB (OTG)**:
   - Conecta un cable adaptador **Micro-USB macho a USB-A hembra (OTG)** en el puerto Micro-USB de datos de la Pi Zero 2 W (el conector más cercano al centro, NO el de alimentación PWR IN).
   - Conecta tu cámara web USB al adaptador OTG.

---

## 4. Instalación de Software en la Raspberry Pi Zero 2 W

Conéctate por SSH a la Raspberry Pi (`ssh pi@raspberrypi.local` o tu IP):

```bash
# 1. Instalar paquetes de sistema y dependencias de cámara / GPIO
sudo apt update
sudo apt install -y python3-pip python3-picamera2 python3-opencv python3-gpiozero v4l-utils

# 2. Descargar o clonar el repositorio
cd ~
git clone <URL_REPOSITORIO> semaforo_inteligente
cd semaforo_inteligente/raspberry_pi

# 3. Instalar FastAPI y Uvicorn
pip install fastapi uvicorn --break-system-packages
```

### Comprobación de cámaras conectadas:
```bash
# Verificar que se detecta la cámara USB y el sensor CSI
v4l2-ctl --list-devices
```

---

## 5. Configuración de Hostname y Red Wi-Fi Propia (Hotspot Autónomo)

Para que la Raspberry Pi no dependa de ningún router externo ni de internet:

```bash
# Ejecutar script de configuración automática de red:
./configurar_hotspot.sh
```

Esto configura:
- **Hostname:** `semaforo` (accesible en `http://semaforo.local:8000`)
- **Red Wi-Fi (SSID):** `Semaforo-Inteligente`
- **Contraseña:** `semaforo123`
- **IP Fija Gateway:** `10.42.0.1`

---

## 6. Autoinicio al Encender la Raspberry Pi

Para que todo el sistema (Cámaras, Motor de Visión, LEDs y Dashboard Web) arranque automáticamente en cada booteo:

```bash
sudo cp semaforo_completo.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now semaforo_completo.service
```

### Visualización y Verificación:
1. Enciende la Raspberry Pi.
2. Desde tu smartphone o laptop, conéctate a la red Wi-Fi **`Semaforo-Inteligente`** con la clave **`semaforo123`**.
3. Abre el navegador web en:
   - **`http://10.42.0.1:8000`**  o  **`http://semaforo.local:8000`**
4. Verás el Dashboard en tiempo real con las dos transmisiones de video, conteo vehicular y los estados de los semáforos activos.

