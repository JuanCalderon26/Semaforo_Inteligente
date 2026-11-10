/**
 * ============================================================================
 * SMART TRAFFIC CONTROL - DASHBOARD CLIENT JAVASCRIPT
 * ============================================================================
 * Manejo de WebSockets en tiempo real, renderizado de luces LED 3D,
 * cronómetro radial, actualización de historial de trazabilidad y controles.
 * ============================================================================
 */

document.addEventListener("DOMContentLoaded", () => {
    // Referencias al DOM
    const wsStatusChip = document.getElementById("ws-status-chip");
    const wsStatusText = document.getElementById("ws-status-text");
    const liveClock = document.getElementById("live-clock");

    // Luces Carril 1
    const l1Red = document.getElementById("light-l1-red");
    const l1Yellow = document.getElementById("light-l1-yellow");
    const l1Green = document.getElementById("light-l1-green");
    const statusL1Label = document.getElementById("status-l1-label");
    const valCarsLane1 = document.getElementById("val-cars-lane1");

    // Luces Carril 2
    const l2Red = document.getElementById("light-l2-red");
    const l2Yellow = document.getElementById("light-l2-yellow");
    const l2Green = document.getElementById("light-l2-green");
    const statusL2Label = document.getElementById("status-l2-label");
    const valCarsLane2 = document.getElementById("val-cars-lane2");

    // Temporizador Central
    const timerProgressBar = document.getElementById("timer-progress-bar");
    const timerPhaseName = document.getElementById("timer-phase-name");
    const timerRemaining = document.getElementById("timer-remaining");
    const timerElapsed = document.getElementById("timer-elapsed");
    const ruleStatusBadge = document.getElementById("rule-status-badge");
    const ruleExplanationText = document.getElementById("rule-explanation-text");

    // Controles
    const btnForceChange = document.getElementById("btn-force-change");
    const btnTogglePause = document.getElementById("btn-toggle-pause");
    const toggleSim = document.getElementById("toggle-sim");
    const btnModeMog2 = document.getElementById("btn-mode-mog2");
    const btnModeYolo = document.getElementById("btn-mode-yolo");

    // KPIs
    const kpiTotalCycles = document.getElementById("kpi-total-cycles");
    const kpiAvgDuration = document.getElementById("kpi-avg-duration");
    const kpiExtCount = document.getElementById("kpi-ext-count");
    const kpiCutCount = document.getElementById("kpi-cut-count");
    const kpiCarsTotal = document.getElementById("kpi-cars-total");

    // Tabla de Trazabilidad
    const traceTableBody = document.getElementById("trace-table-body");
    const btnDownloadCsv = document.getElementById("btn-download-csv");
    const btnClearHistory = document.getElementById("btn-clear-history");

    // Modal de Ajustes
    const settingsModal = document.getElementById("settings-modal");
    const btnOpenSettings = document.getElementById("btn-open-settings");
    const btnCloseModal = document.getElementById("btn-close-modal");
    const btnCancelSettings = document.getElementById("btn-cancel-settings");
    const btnSaveSettings = document.getElementById("btn-save-settings");
    const inputUrlLane1 = document.getElementById("input-url-lane1");
    const inputUrlLane2 = document.getElementById("input-url-lane2");

    // Perímetro del círculo radial: 2 * PI * 85 ≈ 534.07
    const CIRCLE_CIRCUMFERENCE = 534.07;
    let ws = null;
    let lastCycleCount = -1;
    let cachedHistoryData = [];

    // Reloj digital en vivo
    function updateClock() {
        const now = new Date();
        liveClock.textContent = now.toTimeString().split(" ")[0];
    }
    setInterval(updateClock, 1000);
    updateClock();

    // ==========================================
    // CONEXIÓN WEBSOCKET RESILIENTE
    // ==========================================
    function connectWebSocket() {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            wsStatusChip.style.background = "rgba(16, 185, 129, 0.1)";
            wsStatusChip.style.borderColor = "rgba(16, 185, 129, 0.25)";
            wsStatusChip.style.color = "var(--emerald-success)";
            wsStatusText.textContent = "SISTEMA EN LÍNEA";
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                renderTelemetry(data);
            } catch (err) {
                console.error("Error parseando telemetría WS:", err);
            }
        };

        ws.onclose = () => {
            wsStatusChip.style.background = "rgba(239, 68, 68, 0.1)";
            wsStatusChip.style.borderColor = "rgba(239, 68, 68, 0.25)";
            wsStatusChip.style.color = "#f87171";
            wsStatusText.textContent = "DESCONECTADO (REINTENTANDO...)";
            setTimeout(connectWebSocket, 2000);
        };

        ws.onerror = () => {
            ws.close();
        };
    }

    // ==========================================
    // RENDERIZADO DE TELEMETRÍA EN TIEMPO REAL
    // ==========================================
    function renderTelemetry(data) {
        // Actualizar Luces del Semáforo 1
        const l1 = data.lights.lane1;
        updateBulb(l1Red, l1.red);
        updateBulb(l1Yellow, l1.yellow);
        updateBulb(l1Green, l1.green);
        updateStatusLabel(statusL1Label, l1);

        // Actualizar Luces del Semáforo 2
        const l2 = data.lights.lane2;
        updateBulb(l2Red, l2.red);
        updateBulb(l2Yellow, l2.yellow);
        updateBulb(l2Green, l2.green);
        updateStatusLabel(statusL2Label, l2);

        // Actualizar Conteos de Autos
        valCarsLane1.textContent = data.vehicles_lane1;
        valCarsLane2.textContent = data.vehicles_lane2;

        // Actualizar Cronómetro Central
        const rem = data.remaining_seconds;
        const target = data.target_seconds;
        const elapsed = data.elapsed_seconds;

        timerRemaining.innerHTML = `${rem.toFixed(1)}<small>s</small>`;
        timerElapsed.textContent = `Transcurrido: ${elapsed.toFixed(1)}s / ${target.toFixed(1)}s`;

        // Nombre de la Fase y color del círculo radial
        if (data.state === "LANE1_GREEN") {
            timerPhaseName.textContent = "CARRIL 1 • VERDE";
            timerProgressBar.style.stroke = "var(--led-green-on)";
        } else if (data.state === "LANE1_YELLOW") {
            timerPhaseName.textContent = "CARRIL 1 • TRANSICIÓN AMARILLO";
            timerProgressBar.style.stroke = "var(--led-yellow-on)";
        } else if (data.state === "LANE2_GREEN") {
            timerPhaseName.textContent = "CARRIL 2 • VERDE";
            timerProgressBar.style.stroke = "var(--led-green-on)";
        } else if (data.state === "LANE2_YELLOW") {
            timerPhaseName.textContent = "CARRIL 2 • TRANSICIÓN AMARILLO";
            timerProgressBar.style.stroke = "var(--led-yellow-on)";
        }

        // Progreso circular
        const progressFraction = Math.max(0, Math.min(1, (target - rem) / target));
        const offset = CIRCLE_CIRCUMFERENCE * (1 - progressFraction);
        timerProgressBar.style.strokeDashoffset = offset;

        // Badge de Explicación de la Regla en Ejecución
        renderRuleNotice(data);

        // Botón de Pausa
        btnTogglePause.innerHTML = data.paused ? "▶️ Reanudar Temporizador" : "⏸️ Pausar Temporizador";
        btnTogglePause.style.color = data.paused ? "#fbbf24" : "var(--text-secondary)";

        // Toggle de Simulación
        if (toggleSim.checked !== data.use_simulation) {
            toggleSim.checked = data.use_simulation;
        }

        // Modos de Visión
        if (data.detection_mode === "mog2") {
            btnModeMog2.classList.add("active");
            btnModeYolo.classList.remove("active");
        } else {
            btnModeYolo.classList.add("active");
            btnModeMog2.classList.remove("active");
        }

        // Actualizar KPIs si cambiaron los ciclos
        if (data.stats) {
            kpiTotalCycles.textContent = data.stats.total_cycles;
            kpiAvgDuration.innerHTML = `${data.stats.avg_duration.toFixed(1)}<small>s</small>`;
            kpiExtCount.textContent = data.stats.cause_counts.extension_20s || 0;
            kpiCutCount.textContent = data.stats.cause_counts.empty_lane_cut_5s || 0;
            kpiCarsTotal.textContent = (data.stats.total_vehicles_lane1 + data.stats.total_vehicles_lane2) || 0;

            if (data.stats.total_cycles !== lastCycleCount) {
                lastCycleCount = data.stats.total_cycles;
                loadHistoryTable();
            }
        }
    }

    function updateBulb(element, state) {
        if (state) {
            element.classList.add("active");
        } else {
            element.classList.remove("active");
        }
    }

    function updateStatusLabel(labelElement, lights) {
        labelElement.className = "light-status-label";
        if (lights.green) {
            labelElement.classList.add("state-green");
            labelElement.textContent = "EN VERDE (PASO)";
        } else if (lights.yellow) {
            labelElement.classList.add("state-yellow");
            labelElement.textContent = "EN AMARILLO (PRECAUCIÓN)";
        } else {
            labelElement.classList.add("state-red");
            labelElement.textContent = "EN ROJO (DETENIDO)";
        }
    }

    function renderRuleNotice(data) {
        const state = data.state;
        const elapsed = data.elapsed_seconds;
        const activeCars = data.active_lane === 1 ? data.vehicles_lane1 : data.vehicles_lane2;

        if (state.includes("YELLOW")) {
            ruleStatusBadge.textContent = "⚠️ SEGURIDAD: FASE AMARILLA (2s)";
            ruleStatusBadge.style.color = "var(--led-yellow-on)";
            ruleExplanationText.textContent = "Despejando intersección antes de ceder el paso al carril opuesto.";
        } else if (data.is_extended) {
            ruleStatusBadge.textContent = "🔥 +5s EXTENSIÓN ACTIVA (20s TOTAL)";
            ruleStatusBadge.style.color = "#fbbf24";
            ruleExplanationText.textContent = `Menos de 2 autos detectados (${activeCars}). Se amplió el tiempo a 20s para desahogo continuo.`;
        } else if (elapsed < 5.0) {
            ruleStatusBadge.textContent = "🔍 MONITOREO DE COLA INICIAL (< 5s)";
            ruleStatusBadge.style.color = "var(--primary-cyan)";
            ruleExplanationText.textContent = `Autos detectados: ${activeCars}. Si a los 5s no hay autos (0), se corta anticipadamente al otro carril.`;
        } else {
            ruleStatusBadge.textContent = "⚡ CICLO REGULAR: BASE 15s";
            ruleStatusBadge.style.color = "var(--primary-cyan)";
            ruleExplanationText.textContent = `Evaluación al seg 15: si hay < 2 autos, se activará extensión a 20s. Autos actuales: ${activeCars}.`;
        }
    }

    // ==========================================
    // CARGA DE TABLA DE TRAZABILIDAD
    // ==========================================
    async function loadHistoryTable() {
        try {
            const res = await fetch("/api/history?limit=40");
            const data = await res.json();
            cachedHistoryData = data;

            if (!data || data.length === 0) {
                traceTableBody.innerHTML = `<tr><td colspan="8" class="text-center empty-state">No hay registros de trazabilidad aún. El semáforo registrará cada cambio automáticamente.</td></tr>`;
                return;
            }

            let html = "";
            data.forEach((row) => {
                let badgeClass = "badge-base";
                let causeLabel = "Ciclo Base 15s";

                if (row.cause === "extension_20s") {
                    badgeClass = "badge-extended";
                    causeLabel = "Extensión a 20s (+5s flujo < 2)";
                } else if (row.cause === "empty_lane_cut_5s") {
                    badgeClass = "badge-cut";
                    causeLabel = "Corte Rápido 5s (Carril Vacío)";
                } else if (row.cause === "manual_override") {
                    badgeClass = "badge-manual";
                    causeLabel = "Cambio Manual Forzado";
                }

                html += `
                    <tr>
                        <td><strong>#${row.id}</strong></td>
                        <td>${row.timestamp}</td>
                        <td><span class="lane-num">C${row.lane}</span> Carril ${row.lane}</td>
                        <td><strong>${row.duration_seconds.toFixed(1)}s</strong></td>
                        <td><span class="badge-cause ${badgeClass}">${causeLabel}</span></td>
                        <td>${row.vehicles_lane1}</td>
                        <td>${row.vehicles_lane2}</td>
                        <td><span style="color: var(--emerald-success)">COMPLETADO</span></td>
                    </tr>
                `;
            });
            traceTableBody.innerHTML = html;
        } catch (err) {
            console.error("Error cargando historial de trazabilidad:", err);
        }
    }

    // ==========================================
    // ACCIONES Y CONTROLES INTERACTIVOS
    // ==========================================
    btnForceChange.addEventListener("click", () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send("force_change");
        } else {
            fetch("/api/control/force_change", { method: "POST" });
        }
    });

    btnTogglePause.addEventListener("click", () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send("toggle_pause");
        }
    });

    toggleSim.addEventListener("change", async () => {
        await fetch("/api/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ use_simulation: toggleSim.checked })
        });
    });

    btnModeMog2.addEventListener("click", async () => {
        await fetch("/api/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ detection_mode: "mog2" })
        });
    });

    btnModeYolo.addEventListener("click", async () => {
        await fetch("/api/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ detection_mode: "yolo" })
        });
    });

    btnClearHistory.addEventListener("click", async () => {
        if (confirm("¿Estás seguro de que deseas vaciar el historial de trazabilidad?")) {
            await fetch("/api/control/clear_history", { method: "POST" });
            loadHistoryTable();
        }
    });

    // Exportar CSV
    btnDownloadCsv.addEventListener("click", () => {
        if (!cachedHistoryData || cachedHistoryData.length === 0) {
            alert("No hay datos para exportar.");
            return;
        }

        let csv = "ID,Timestamp,Carril,Duracion_Segundos,Causa,Vehiculos_Carril_1,Vehiculos_Carril_2\n";
        cachedHistoryData.forEach((r) => {
            csv += `${r.id},"${r.timestamp}",${r.lane},${r.duration_seconds},"${r.cause}",${r.vehicles_lane1},${r.vehicles_lane2}\n`;
        });

        const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `trazabilidad_semaforos_${new Date().toISOString().slice(0, 10)}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    });

    // Modal de Configuración
    btnOpenSettings.addEventListener("click", () => {
        settingsModal.classList.add("open");
    });

    btnCloseModal.addEventListener("click", () => {
        settingsModal.classList.remove("open");
    });

    btnCancelSettings.addEventListener("click", () => {
        settingsModal.classList.remove("open");
    });

    btnSaveSettings.addEventListener("click", async () => {
        const urlL1 = inputUrlLane1.value.trim() || null;
        const urlL2 = inputUrlLane2.value.trim() || null;

        await fetch("/api/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                lane1_url: urlL1,
                lane2_url: urlL2
            })
        });

        settingsModal.classList.remove("open");
        alert("Configuración de Raspberry Pi Zero 2 W guardada exitosamente.");
    });

    // Iniciar conexión y carga inicial
    connectWebSocket();
    loadHistoryTable();
});
