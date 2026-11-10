#!/bin/bash
# ==============================================================================
# SCRIPT DE INICIO INTEGRADO: AGENTE DUAL + SERVIDOR WEB (FRONTEND)
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=================================================================="
echo "Iniciando Sistema Completo de Semáforo Inteligente en Raspberry Pi"
echo "=================================================================="

# 1. Iniciar Agente Dual de Cámaras y LEDs en puerto 8080
echo "[1/2] Iniciando Agente Dual de Cámaras (CSI + USB) y LEDs en puerto 8080..."
python3 "$SCRIPT_DIR/dual_camera_agent.py" --port 8080 --usb-index 0 &
AGENT_PID=$!

# Esperar 2 segundos a que el agente esté listo
sleep 2

# 2. Iniciar Servidor Central y Frontend Web en puerto 8000
echo "[2/2] Iniciando Servidor Central y Dashboard Web en puerto 8000..."
export LANE1_URL="http://127.0.0.1:8080/lane1"
export LANE2_URL="http://127.0.0.1:8080/lane2"

python3 "$ROOT_DIR/server/app.py" &
SERVER_PID=$!

trap "kill $AGENT_PID $SERVER_PID 2>/dev/null; exit" SIGINT SIGTERM

echo "=================================================================="
echo "Semáforo Inteligente OPERATIVO al 100%"
echo "Acceso al Dashboard Web:"
echo "  - Desde Hotspot: http://10.42.0.1:8000"
echo "  - Por mDNS:      http://semaforo.local:8000"
echo "=================================================================="

wait
