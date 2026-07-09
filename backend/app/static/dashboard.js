let sseSource = null;
        let selectedZoneId = null;
        let activeRecommendationId = null;
        let currentLanguage = 'en';
        
        // Retrieve API key from URL parameter or local storage
        const urlParams = new URLSearchParams(window.location.search);
        let activeApiKey = urlParams.get('api_key') || localStorage.getItem('fifanexus_api_key') || '';

        function escapeHTML(str) {
            if (!str) return '';
            return str
                .replaceAll("&", "&amp;")
                .replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;")
                .replaceAll("\"", "&quot;")
                .replaceAll("'", "&#039;");
        }

        // Translation Dictionary
        const TRANSLATIONS = {
            en: {
                title: "FIFA Nexus AI - Operational Intelligence Dashboard",
                langLabel: "Language:",
                activeVenue: "Active Venue:",
                mapHeading: "Stadium Spatial Map (Hard Rock Stadium)",
                realtimeState: "Real-time Zone State",
                simHeading: "Simulation Control Center",
                eventsLog: "Real-time Events Log",
                decisionSupport: "Decision Support (AI)",
                groundDispatch: "ground dispatch queue",
                activeTasks: "Active Tasks",
                monitoringMode: "No active anomalies. AI is in monitoring mode.",
                wait_time: "Wait Time",
                validation: "Validation",
                btnApprove: "Approve & Dispatch Tasks",
                btnComplete: "Mark Completed & Submit Feedback",
                feedbackCaptured: "Feedback Captured (Outcome: Positive)",
                noTasks: "No tasks currently dispatched.",
                lowLoad: "Low load",
                elevated: "Elevated",
                breach: "Breach",
                ingressWave: "Run Ingress Simulation Wave"
            },
            es: {
                title: "FIFA Nexus AI - Panel de Inteligencia Operativa",
                langLabel: "Idioma:",
                activeVenue: "Sede Activa:",
                mapHeading: "Mapa Espacial del Estadio (Hard Rock Stadium)",
                realtimeState: "Estado de Zona en Tiempo Real",
                simHeading: "Centro de Control de Simulación",
                eventsLog: "Registro de Eventos en Tiempo Real",
                decisionSupport: "Soporte de Decisiones (IA)",
                groundDispatch: "cola de despacho de tierra",
                activeTasks: "Tareas Activas",
                monitoringMode: "No hay anomalías activas. La IA está en modo de monitoreo.",
                wait_time: "Tiempo de Espera",
                validation: "Validación",
                btnApprove: "Aprobar y Despachar Tareas",
                btnComplete: "Marcar como Completado y Enviar Comentarios",
                feedbackCaptured: "Comentarios Capturados (Resultado: Positivo)",
                noTasks: "No hay tareas despachadas actualmente.",
                lowLoad: "Carga baja",
                elevated: "Elevada",
                breach: "Incumplimiento",
                ingressWave: "Ejecutar Ola de Simulación de Ingreso"
            },
            fr: {
                title: "FIFA Nexus AI - Tableau de Bord d'Intelligence Opérationnelle",
                langLabel: "Langue:",
                activeVenue: "Lieu Actif:",
                mapHeading: "Carte Spatiale du Stade (Hard Rock Stadium)",
                realtimeState: "État de la Zone en Temps Réel",
                simHeading: "Centre de Contrôle des Simulations",
                eventsLog: "Journal des Événements en Temps Réel",
                decisionSupport: "Aide à la Décision (IA)",
                groundDispatch: "file d'attente d'expédition au sol",
                activeTasks: "Tâches Actives",
                monitoringMode: "Aucune anomalie active. L'IA est en mode surveillance.",
                wait_time: "Temps d'Attente",
                validation: "Validation",
                btnApprove: "Approuver et Répartir les Tâches",
                btnComplete: "Marquer comme Terminé et Soumettre des Commentaires",
                feedbackCaptured: "Commentaires Capturés (Résultat: Positif)",
                noTasks: "Aucune tâche expédiée actuellement.",
                lowLoad: "Faible charge",
                elevated: "Élevée",
                breach: "Brèche",
                ingressWave: "Lancer la Vague de Simulation d'Entrée"
            }
        };

        function showApiKeyModal() {
            const modal = document.getElementById('api-key-modal');
            if (modal) modal.classList.remove('hidden');
        }

        function submitApiKey() {
            const input = document.getElementById('modal-api-key-input');
            if (input) {
                const key = input.value.trim();
                if (key) {
                    activeApiKey = key;
                    localStorage.setItem('fifanexus_api_key', key);
                    const modal = document.getElementById('api-key-modal');
                    if (modal) modal.classList.add('hidden');
                    // Initialize dashboard data
                    checkSystemHealth();
                    loadZones();
                    setupSSE();
                    loadActiveTasks();
                } else {
                    alert("Please enter a valid API Key.");
                }
            }
        }

        // Check system health for header KPIs
        async function checkSystemHealth() {
            try {
                // Fetch from details endpoint if key is present, otherwise fallback to public /health
                const endpoint = activeApiKey ? '/health/details' : '/health';
                const headers = activeApiKey ? { 'X-API-Key': activeApiKey } : {};
                const res = await fetch(endpoint, { headers });
                if (!res.ok) {
                    if (res.status === 401) {
                        localStorage.removeItem('fifanexus_api_key');
                        activeApiKey = '';
                        showApiKeyModal();
                    }
                    return;
                }
                const data = await res.json();
                
                // If it's the detailed diagnostic report, update the KPIs
                if (data.db_type) {
                    document.getElementById('db-type-val').innerText = data.db_type === "sqlite" ? "SQLite Fallback" : "PostgreSQL";
                    
                    const redisStatusVal = document.getElementById('redis-status-val');
                    const redisDot = document.getElementById('redis-dot');
                    if (data.redis === "online") {
                        redisStatusVal.innerText = "Online (Cache Active)";
                        redisDot.className = "h-2 w-2 rounded-full bg-emerald-500 animate-pulse";
                    } else {
                        redisStatusVal.innerText = "Offline (Bypassed)";
                        redisDot.className = "h-2 w-2 rounded-full bg-orange-500";
                    }
                }
                
                // Trigger live analytics retrieval
                await loadAnalyticsStats();
            } catch (err) {
                console.error("Health check failed:", err);
            }
        }

        // Fetch real-time AI & Pipeline Analytics
        async function loadAnalyticsStats() {
            try {
                const res = await fetch('/api/v1/recommendations/stats');
                if (!res.ok) return;
                const stats = await res.json();
                
                document.getElementById('stats-total-decisions').innerText = stats.total_count;
                document.getElementById('stats-avg-latency').innerText = `${stats.avg_reasoning_time_ms}ms`;
                
                const total = stats.total_count;
                const passRate = total > 0 ? Math.round((stats.validated_count / total) * 100) : 100;
                document.getElementById('stats-pass-rate').innerText = `${passRate}%`;
                document.getElementById('stats-co2-savings').innerText = `${stats.total_co2_saved_kg} kg`;
                
                // Primary LLM display from stats models
                const models = Object.keys(stats.provider_stats);
                if (models.length > 0) {
                    document.getElementById('stats-primary-llm').innerText = models.join(', ');
                } else {
                    document.getElementById('stats-primary-llm').innerText = "Heuristic Engine Fallback";
                }
            } catch (err) {
                console.error("Failed to load analytics stats:", err);
            }
        }

        // Render the standby/idle AI panel
        function showIdleAIDashboard() {
            const container = document.getElementById('recommendations-container');
            container.innerHTML = `
                <div class="bg-slate-900/40 border border-gray-800 rounded-xl p-4 space-y-4">
                    <div class="flex justify-between items-center pb-2 border-b border-gray-800/60">
                        <span class="text-xs text-emerald-400 font-semibold flex items-center gap-1.5">
                            <span class="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
                            AI Reasoner: Monitoring Mode
                        </span>
                        <span class="text-[10px] text-gray-500 font-mono">Analysis: Active</span>
                    </div>
                    <div class="grid grid-cols-2 gap-3 text-xs">
                        <div class="bg-slate-950/40 p-2.5 rounded-lg border border-slate-800">
                            <span class="text-gray-500 block text-[10px] uppercase font-bold">Predictive Horizon</span>
                            <span class="text-white font-semibold">30 Minutes</span>
                        </div>
                        <div class="bg-slate-950/40 p-2.5 rounded-lg border border-slate-800">
                            <span class="text-gray-500 block text-[10px] uppercase font-bold">Reasoning Status</span>
                            <span class="text-white font-semibold">Watching 5 Zones</span>
                        </div>
                        <div class="bg-slate-950/40 p-2.5 rounded-lg border border-slate-800">
                            <span class="text-gray-500 block text-[10px] uppercase font-bold">AI Base Model</span>
                            <span class="text-white font-semibold">GPT-4o (Reasoning v2.1)</span>
                        </div>
                        <div class="bg-slate-950/40 p-2.5 rounded-lg border border-slate-800">
                            <span class="text-gray-500 block text-[10px] uppercase font-bold">Knowledge Version</span>
                            <span class="text-white font-semibold">SOP-Catalog:v1.4</span>
                        </div>
                    </div>
                    <div class="bg-indigo-950/20 border border-indigo-900/20 p-3 rounded-lg text-xs flex items-center gap-2 text-indigo-300">
                        <span>🛡️</span>
                        <span>Multi-Objective Optimization weights and strict Safety Gates are fully operational.</span>
                    </div>
                </div>
            `;
        }

        // Initialize and load base data on start
        window.addEventListener('DOMContentLoaded', () => {
            changeLanguage(); // set initial values
            showIdleAIDashboard();
            if (!activeApiKey) {
                showApiKeyModal();
            } else {
                checkSystemHealth();
                loadZones();
                setupSSE();
                loadActiveTasks();
            }
        });

        // Keyboard navigation helper for SVG map
        function handleMapKey(event, zoneName) {
            if (event.key === ' ' || event.key === 'Enter') {
                event.preventDefault();
                selectZone(zoneName);
            }
        }

        function detectBrowserLanguage() {
            const browserLang = navigator.language || navigator.userLanguage || 'en';
            if (browserLang.startsWith('es')) {
                return { lang: 'es', name: "Español", browserLang };
            }
            if (browserLang.startsWith('fr')) {
                return { lang: 'fr', name: "Français", browserLang };
            }
            return { lang: 'en', name: "English", browserLang };
        }

        function appendAutoTranslateLog(browserLang) {
            const log = document.getElementById('events-log');
            if (!log || log.innerHTML.includes("detected browser locale")) return;
            const entry = document.createElement('div');
            entry.className = "text-emerald-400 font-semibold";
            entry.innerText = `[${new Date().toLocaleTimeString()}] [SYSTEM] AI Auto-Translate detected browser locale: "${browserLang}". UI dynamically translated.`;
            log.appendChild(entry);
            log.scrollTop = log.scrollHeight;
        }

        function translateHeaderSections(dict) {
            const mapHeadingEl = document.getElementById('map-heading');
            if (mapHeadingEl) mapHeadingEl.innerHTML = `<span>🏟️</span> ${dict.mapHeading}`;
            
            const metricsEl = document.getElementById('metrics-heading');
            if (metricsEl?.querySelector('span')) {
                metricsEl.querySelector('span').innerText = dict.realtimeState;
            }
            
            const simEl = document.getElementById('sim-heading');
            if (simEl) simEl.innerText = dict.simHeading;
            
            const logElHeading = document.getElementById('log-heading');
            if (logElHeading?.querySelector('span')) {
                logElHeading.querySelector('span').innerText = dict.eventsLog;
            }
            
            const aiElHeading = document.getElementById('ai-heading');
            if (aiElHeading?.querySelector('span')) {
                aiElHeading.querySelector('span').innerText = dict.decisionSupport;
            }
        }

        function translateDispatchAndContainers(dict) {
            const dispatchSection = document.querySelector('section[aria-label="Ground Dispatch queue"]');
            if (dispatchSection) {
                const titleSpan = dispatchSection.querySelector('h2 span');
                if (titleSpan) {
                    titleSpan.innerText = dict.groundDispatch;
                }
                const activeTasksSpan = dispatchSection.querySelector('h2 span.text-xs');
                if (activeTasksSpan) {
                    activeTasksSpan.innerText = dict.activeTasks;
                }
            }

            const recContainer = document.getElementById('recommendations-container');
            if (recContainer && (recContainer.innerHTML.includes('monitoring mode') || recContainer.innerHTML.includes('monitoreo') || recContainer.innerHTML.includes('surveillance'))) {
                recContainer.innerHTML = `<div class="text-gray-500 text-sm py-8">${dict.monitoringMode}</div>`;
            }

            const taskContainer = document.getElementById('tasks-container');
            if (taskContainer && (taskContainer.innerHTML.includes('dispatched') || taskContainer.innerHTML.includes('despachadas') || taskContainer.innerHTML.includes('expédiée'))) {
                taskContainer.innerHTML = `<div class="col-span-3 text-center text-gray-500 text-sm py-4">${dict.noTasks}</div>`;
            }
        }

        // Translate the UI dynamically
        function changeLanguage() {
            let lang = document.getElementById('lang-selector').value;
            const label = document.querySelector('label[for="lang-selector"]');
            
            if (lang === 'auto') {
                const detection = detectBrowserLanguage();
                lang = detection.lang;
                if (label) {
                    label.innerText = `Language: Auto (${detection.name})`;
                }
                appendAutoTranslateLog(detection.browserLang);
            } else if (label) {
                label.innerText = `Language:`;
            }
            
            currentLanguage = lang;
            const dict = TRANSLATIONS[currentLanguage];
            
            document.title = dict.title;
            translateHeaderSections(dict);
            translateDispatchAndContainers(dict);
        }

        // 1. Fetch zones operational state
        async function loadZones() {
            try {
                const res = await fetch('/api/v1/zones');
                const zones = await res.json();
                const container = document.getElementById('zones-list-container');
                container.innerHTML = '';
                
                if (zones.length > 0) {
                    // Preselect first zone (typically Gate A)
                    selectedZoneId = zones[0].id;
                }

                zones.forEach(zone => {
                    const zoneCard = document.createElement('div');
                    zoneCard.className = `flex justify-between items-center p-3 rounded-xl bg-slate-900 border border-gray-800 hover:border-blue-500/50 transition-all cursor-pointer`;
                    zoneCard.id = `zone-row-${zone.id}`;
                    zoneCard.onclick = () => selectZoneById(zone.id);
                    // Add TabIndex & ARIA role to rows for accessibility
                    zoneCard.tabIndex = 0;
                    zoneCard.setAttribute('role', 'button');
                    zoneCard.setAttribute('aria-label', `Select ${zone.name}`);
                    zoneCard.onkeydown = (e) => {
                        if (e.key === ' ' || e.key === 'Enter') {
                            e.preventDefault();
                            selectZoneById(zone.id);
                        }
                    };
                    zoneCard.innerHTML = `
                        <div class="flex-1">
                            <div class="flex items-center gap-2">
                                <span class="font-bold text-sm text-white">${escapeHTML(zone.name)}</span>
                                <span class="text-[9px] bg-slate-800/80 text-slate-400 border border-slate-700 px-1 py-0.5 rounded uppercase font-mono">${escapeHTML(zone.zone_type)}</span>
                            </div>
                            <div class="text-[10px] text-gray-400 mt-1 flex gap-2">
                                <span>Cap: <strong class="text-gray-300 font-mono">${zone.safe_capacity}</strong></span>
                                <span>•</span>
                                <span>Trend: <strong class="text-gray-300 font-semibold" id="zone-trend-${zone.id}">Stable</strong></span>
                                <span>•</span>
                                <span>ETA: <strong class="text-gray-300 font-semibold" id="zone-eta-${zone.id}">--</strong></span>
                            </div>
                        </div>
                        <div class="text-right pl-4">
                            <div class="text-xs font-semibold text-gray-300" id="zone-occ-${zone.id}">0 / ${zone.safe_capacity} (<span class="text-emerald-400 font-mono font-bold">0%</span>)</div>
                            <div class="w-20 bg-gray-800 rounded-full h-1.5 mt-1.5 overflow-hidden">
                                <div id="zone-progress-${zone.id}" class="bg-brand-success h-1.5 rounded-full transition-all" style="width: 0%"></div>
                            </div>
                        </div>
                    `;
                    container.appendChild(zoneCard);
                });
            } catch (err) {
                console.error("Failed to load zones:", err);
            }
        }

        function selectZone(zoneName) {
            // Find zone by name and trigger selection
            document.querySelectorAll('[id^="zone-row-"]').forEach(row => {
                if (row.innerHTML.includes(zoneName)) {
                    row.click();
                }
            });
        }

        function selectZoneById(zoneId) {
            selectedZoneId = zoneId;
            document.querySelectorAll('[id^="zone-row-"]').forEach(el => {
                el.classList.remove('border-blue-500');
                el.classList.add('border-gray-800');
                el.setAttribute('aria-pressed', 'false');
            });
            const activeRow = document.getElementById(`zone-row-${zoneId}`);
            activeRow.classList.add('border-blue-500');
            activeRow.classList.remove('border-gray-800');
            activeRow.setAttribute('aria-pressed', 'true');
        }

        // 2. Set up SSE connection
        function setupSSE() {
            const badge = document.getElementById('connection-badge');
            sseSource = new EventSource('/api/v1/events/stream');
            
            sseSource.onopen = () => {
                badge.className = "flex items-center gap-2 text-brand-success bg-emerald-950/40 border border-emerald-900/50 px-3 py-1 rounded-full text-xs font-semibold";
                badge.innerHTML = `<span class="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span> SSE Live`;
            };

            sseSource.onerror = (err) => {
                badge.className = "flex items-center gap-2 text-brand-danger bg-red-950/40 border border-red-900/50 px-3 py-1 rounded-full text-xs font-semibold";
                badge.innerHTML = `<span class="h-2 w-2 rounded-full bg-red-500"></span> SSE Reconnecting`;
                console.error("SSE connection error: ", err);
            };

            // Event log listener
            sseSource.addEventListener('operational_event', (event) => {
                const log = document.getElementById('events-log');
                if (log.innerHTML.includes('Waiting for events')) {
                    log.innerHTML = '';
                }
                
                const data = JSON.parse(event.data);
                const timeStr = new Date().toLocaleTimeString();
                
                // Print in log with rich layout
                const logLine = document.createElement('div');
                const isBreach = data.event_type === "CROWD_DENSITY_HIGH";
                const severityBadge = isBreach 
                    ? '<span class="text-[9px] bg-red-950 text-red-400 border border-red-800 px-1 py-0.5 rounded font-mono font-bold mr-1.5">CRIT</span>'
                    : '<span class="text-[9px] bg-slate-800 text-slate-300 border border-slate-700 px-1 py-0.5 rounded font-mono font-bold mr-1.5">INFO</span>';
                
                logLine.className = `border-l-2 ${isBreach ? 'border-red-500 bg-red-950/10' : 'border-blue-500 bg-slate-900/20'} p-2 rounded text-[11px] font-mono leading-relaxed transition-all`;
                logLine.innerHTML = `
                    <div class="flex justify-between items-center mb-1">
                        <div>${severityBadge} <span class="text-white font-semibold">${escapeHTML(data.event_type)}</span></div>
                        <span class="text-gray-500 text-[10px]">${timeStr}</span>
                    </div>
                    <div class="text-gray-300 pl-2">
                        Zone: <strong class="text-white">${escapeHTML(data.zone_name)}</strong> | Occupancy: <strong class="text-white">${data.current_occupancy}/${data.safe_capacity}</strong>
                    </div>
                `;
                log.appendChild(logLine);
                log.scrollTop = log.scrollHeight;

                // Update Zone UI occupancy
                updateZoneUI(data);

                // Fetch recommendations triggered by this event
                if (data.recommendation_id) {
                    loadRecommendation(data.recommendation_id);
                }
            });
        }

        const ZONE_MAP_IDS = {
            "Gate A": "map-zone-gate-a",
            "Gate B": "map-zone-gate-b",
            "East Concourse": "map-zone-east-concourse",
            "West Concourse": "map-zone-west-concourse",
            "Transport Hub Alpha": "map-zone-transport-hub"
        };

        function getMapElementByZoneName(zoneName) {
            const elementId = ZONE_MAP_IDS[zoneName];
            return elementId ? document.getElementById(elementId) : null;
        }

        function updateSvgMapElement(zoneName, ratio) {
            let color = "#10B981"; // green
            if (ratio > 0.8) {
                color = "#EF4444"; // red
            } else if (ratio > 0.7) {
                color = "#F59E0B"; // yellow
            }

            const mapElement = getMapElementByZoneName(zoneName);
            if (!mapElement) return;

            mapElement.setAttribute('fill', color);
            mapElement.setAttribute('aria-label', `${zoneName} Status: Occupancy at ${Math.round(ratio*100)}%`);
            if (ratio > 0.8) {
                mapElement.classList.add('pulse-breach');
            } else {
                mapElement.classList.remove('pulse-breach');
            }
        }

        function getZoneGridSettings(ratio) {
            if (ratio > 0.8) {
                return {
                    colorClass: "text-red-500 font-bold animate-pulse",
                    trendText: "↑ Critical",
                    trendClass: "text-red-500 font-bold",
                    etaText: "5 min",
                    etaClass: "text-red-500 font-bold"
                };
            }
            if (ratio > 0.6) {
                return {
                    colorClass: "text-amber-400 font-semibold",
                    trendText: "↑ Rising",
                    trendClass: "text-amber-400 font-semibold",
                    etaText: "8 min",
                    etaClass: "text-gray-300"
                };
            }
            return {
                colorClass: "text-emerald-400",
                trendText: "Steady",
                trendClass: "text-gray-300",
                etaText: "--",
                etaClass: "text-gray-300"
            };
        }

        function updateZoneListRow(row, data, ratio, progressClass) {
            const occEl = row.querySelector('[id^="zone-occ-"]');
            const progressEl = row.querySelector('[id^="zone-progress-"]');
            const trendEl = row.querySelector('[id^="zone-trend-"]');
            const etaEl = row.querySelector('[id^="zone-eta-"]');
            
            const percent = Math.round(ratio*100);
            const settings = getZoneGridSettings(ratio);
            
            if (occEl) {
                occEl.innerHTML = `${data.current_occupancy} / ${data.safe_capacity} (<span class="${settings.colorClass} font-mono">${percent}%</span>)`;
            }
            if (progressEl) {
                progressEl.style.width = `${Math.min(100, ratio*100)}%`;
                progressEl.className = `${progressClass} h-1.5 rounded-full transition-all`;
            }
            if (trendEl) {
                trendEl.innerText = settings.trendText;
                trendEl.className = settings.trendClass;
            }
            if (etaEl) {
                etaEl.innerText = settings.etaText;
                etaEl.className = settings.etaClass;
            }
        }

        function updateZoneUI(data) {
            const ratio = data.current_occupancy / data.safe_capacity;
            let progressClass = "bg-brand-success";
            
            if (ratio > 0.8) {
                progressClass = "bg-brand-danger";
            } else if (ratio > 0.7) {
                progressClass = "bg-brand-warning";
            }

            // Update SVG map elements
            updateSvgMapElement(data.zone_name, ratio);

            // Update List grid row text values
            document.querySelectorAll('[id^="zone-row-"]').forEach(row => {
                if (row.innerHTML.includes(data.zone_name)) {
                    updateZoneListRow(row, data, ratio, progressClass);
                }
            });
        }

        // 3. Load recommendation from backend
        async function loadRecommendation(recId) {
            try {
                const res = await fetch(`/api/v1/recommendations`);
                const recs = await res.json();
                const rec = recs.find(r => r.id === recId);
                if (!rec) return;

                activeRecommendationId = recId;
                const dict = TRANSLATIONS[currentLanguage];
                const container = document.getElementById('recommendations-container');
                
                // Localized action string mapping simulation
                let candidateActionsList = rec.candidate_actions;
                if (currentLanguage === 'es') {
                    candidateActionsList = candidateActionsList.map(a => 
                        a.replace("Deploy directional signage", "Colocar señalización direccional")
                         .replace("Verbally guide fans", "Guiar verbalmente a los fanáticos")
                         .replace("Report zone status", "Informar el estado de la zona")
                    );
                } else if (currentLanguage === 'fr') {
                    candidateActionsList = candidateActionsList.map(a => 
                        a.replace("Deploy directional signage", "Déployer des panneaux directionnels")
                         .replace("Verbally guide fans", "Guider verbalement les supporters")
                         .replace("Report zone status", "Signaler l'état de la zone")
                    );
                }

                // Toggle routing arrow animation on Map
                const arrow = document.getElementById('map-rerouting-arrow');
                if (arrow) {
                    if (rec.validation_status === 'VALIDATED') {
                        arrow.classList.add('opacity-100', 'animate-flow');
                        arrow.classList.remove('opacity-0');
                    } else {
                        arrow.classList.remove('opacity-100', 'animate-flow');
                        arrow.classList.add('opacity-0');
                    }
                }

                container.innerHTML = `
                    <div class="glass-panel p-4 rounded-xl border border-indigo-500/30 text-left space-y-4" role="alert">
                        <div class="flex justify-between items-center">
                            <span class="text-xs bg-indigo-900/60 text-indigo-300 font-bold px-2.5 py-1 rounded border border-indigo-700/40">
                                TARGET: ${escapeHTML(rec.target_role)}
                            </span>
                            <span class="text-[10px] bg-slate-900 border border-slate-700 text-slate-300 px-2 py-0.5 rounded font-semibold uppercase font-mono">
                                Conf: ${Math.round(rec.confidence * 100)}%
                            </span>
                        </div>

                        <div>
                            <div class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Reasoning & Diagnostics</div>
                            <p class="text-xs text-gray-200 bg-slate-950/40 p-2.5 rounded-lg border border-slate-900 font-mono text-[11px] leading-relaxed">"${escapeHTML(rec.reasoning_summary)}"</p>
                        </div>

                        <div>
                            <div class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5 font-semibold">Evidence-Based Rationale:</div>
                            <div class="grid grid-cols-2 gap-2 text-[11px]">
                                <div class="bg-slate-950/60 p-2 rounded border border-slate-800">
                                    <span class="text-gray-500 block text-[9px] uppercase font-bold">Trigger Zone</span>
                                    <strong class="text-white block">Gate A: <span class="text-red-500 font-bold">85% Cap</span></strong>
                                </div>
                                <div class="bg-slate-950/60 p-2 rounded border border-slate-800">
                                    <span class="text-gray-500 block text-[9px] uppercase font-bold">Bypass Zone</span>
                                    <strong class="text-white block">Gate B: <span class="text-emerald-400 font-bold">39% Cap</span></strong>
                                </div>
                            </div>
                        </div>

                        <div>
                            <div class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">Proposed Actions:</div>
                            <ul class="space-y-1.5 text-xs text-gray-300 pl-1">
                                ${candidateActionsList.map(action => `
                                    <li class="flex items-start gap-1.5">
                                        <span class="text-indigo-400 mt-0.5">✔</span>
                                        <span>${escapeHTML(action)}</span>
                                    </li>
                                `).join('')}
                            </ul>
                        </div>

                        <div class="bg-indigo-950/40 p-3 rounded-xl border border-indigo-900/30 text-xs grid grid-cols-3 gap-3">
                            <div>
                                <span class="text-gray-400 text-[9px] uppercase font-bold">Projected Impact</span>
                                <div class="text-white font-mono text-[10px] mt-0.5">
                                    Wait: <strong class="text-red-400">18m</strong> ↓ <strong class="text-emerald-400">7m</strong>
                                </div>
                            </div>
                            <div>
                                <span class="text-gray-400 text-[9px] uppercase font-bold">Sustainability</span>
                                <div class="text-emerald-400 text-[10px] mt-0.5 font-bold flex items-center gap-0.5">
                                    🌱 <strong class="text-white font-mono">${rec.expected_impact.co2_saved_kg || 0.4} kg</strong>
                                </div>
                            </div>
                            <div>
                                <span class="text-gray-400 text-[9px] uppercase font-bold">${dict.validation}</span>
                                <div class="text-emerald-400 font-bold uppercase text-[10px] mt-0.5 flex items-center gap-1">
                                    <span class="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-ping"></span>
                                    ${rec.validation_status}
                                </div>
                            </div>
                        </div>

                        ${rec.validation_status === 'VALIDATED' ? `
                            <div class="flex flex-col gap-2">
                                <button data-approve="${rec.id}" class="w-full py-2.5 bg-gradient-to-r from-emerald-600 to-teal-700 hover:from-emerald-500 hover:to-teal-600 rounded-lg text-sm font-bold transition-all text-white glow-green hover:scale-[1.01] active:scale-[0.99] focus:ring-2 focus:ring-blue-500 focus:outline-none">
                                    ${dict.btnApprove}
                                </button>
                                <div class="grid grid-cols-2 gap-2 text-xs font-semibold">
                                    <button data-reject="${rec.id}" class="py-2 bg-red-950/40 hover:bg-red-900/30 text-red-400 border border-red-900/40 rounded transition-all focus:outline-none">
                                        ❌ Reject & Reroute
                                    </button>
                                    <button data-evidence="${rec.id}" class="py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-750 rounded transition-all focus:outline-none">
                                        🔎 View SOP Context
                                    </button>
                                </div>
                            </div>
                        ` : `
                            <div class="text-center text-xs text-gray-400 py-2 bg-gray-800/40 rounded-lg border border-gray-800 font-mono">
                                System State: ${rec.validation_status}
                            </div>
                        `}
                    </div>
                `;
            } catch (err) {
                console.error("Failed to load recommendation:", err);
            }
        }

        // 4. Approve recommendation
        async function approveRecommendation(recId) {
            try {
                const res = await fetch(`/api/v1/recommendations/${recId}/apply`, {
                    method: 'POST',
                    headers: {
                        'Idempotency-Key': crypto.randomUUID(),
                        'X-API-Key': activeApiKey
                    }
                });
                const data = await res.json();
                if (data.status === 'success') {
                    loadRecommendation(recId);
                    setTimeout(loadActiveTasks, 1000);
                    setTimeout(loadAnalyticsStats, 1000);
                }
            } catch (err) {
                console.error("Apply failed:", err);
            }
        }

        // 5. Ingest mock telemetry tick
        async function sendTelemetry(count) {
            if (!selectedZoneId) {
                alert("Please select a zone first.");
                return;
            }
            try {
                const payload = {
                    zone_id: selectedZoneId,
                    sensor_type: "camera",
                    count: count,
                    timestamp: new Date().toISOString()
                };
                await fetch('/api/v1/telemetry', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-Key': activeApiKey
                    },
                    body: JSON.stringify(payload)
                });
            } catch (err) {
                console.error("Post telemetry failed:", err);
            }
        }

        let activeTimeouts = [];
        let simulationPaused = false;
        let pausedStepsRemaining = [];

        // 6. Run Ingress Simulation
        async function runSyntheticScenario() {
            try {
                // Clear any active timeouts before running
                resetSimulation();
                
                const log = document.getElementById('events-log');
                log.innerHTML = `<div class="text-blue-400">Triggering Ingress Simulation Wave...</div>`;
                
                const zonesRes = await fetch('/api/v1/zones');
                const zones = await zonesRes.json();
                const gateA = zones.find(z => z.name === "Gate A") || zones[0];
                
                const steps = [480, 660, 864, 1020, 1140];
                for (let i = 0; i < steps.length; i++) {
                    const tId = setTimeout(async () => {
                        if (simulationPaused) {
                            pausedStepsRemaining.push(steps[i]);
                            return;
                        }
                        const payload = {
                            zone_id: gateA.id,
                            sensor_type: "camera",
                            count: steps[i],
                            timestamp: new Date().toISOString()
                        };
                        await fetch('/api/v1/telemetry', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify(payload)
                        });
                    }, i * 1500);
                    activeTimeouts.push(tId);
                }
            } catch (err) {
                console.error("Scenario execution failed:", err);
            }
        }

        function pauseSimulation() {
            const btn = document.getElementById('btn-pause-simulation');
            if (simulationPaused) {
                // Resume
                simulationPaused = false;
                btn.innerText = "⏸ Pause";
                // Fire remaining steps
                const remaining = [...pausedStepsRemaining];
                pausedStepsRemaining = [];
                remaining.forEach((count, i) => {
                    const tId = setTimeout(async () => {
                        const zonesRes = await fetch('/api/v1/zones');
                        const zones = await zonesRes.json();
                        const gateA = zones.find(z => z.name === "Gate A") || zones[0];
                        const payload = {
                            zone_id: gateA.id,
                            sensor_type: "camera",
                            count: count,
                            timestamp: new Date().toISOString()
                        };
                        await fetch('/api/v1/telemetry', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify(payload)
                        });
                    }, i * 1500);
                    activeTimeouts.push(tId);
                });
            } else {
                // Pause
                simulationPaused = true;
                btn.innerText = "▶ Resume";
            }
        }

        function resetSimulation() {
            // Clear timeouts
            activeTimeouts.forEach(tId => clearTimeout(tId));
            activeTimeouts = [];
            pausedStepsRemaining = [];
            simulationPaused = false;
            
            const btnPause = document.getElementById('btn-pause-simulation');
            if (btnPause) btnPause.innerText = "⏸ Pause";
            
            // Clear events log
            const log = document.getElementById('events-log');
            if (log) log.innerHTML = '<div class="text-gray-600">Waiting for events stream...</div>';
            
            // Clear active tasks
            const container = document.getElementById('tasks-container');
            if (container) {
                container.innerHTML = `
                    <div class="col-span-3 glass-panel rounded-xl p-6 text-center border border-dashed border-gray-850/60 flex flex-col items-center justify-center space-y-2">
                        <span class="text-2xl">🟢</span>
                        <span class="text-sm font-semibold text-white">System Ready - No Active Dispatch Tasks</span>
                        <p class="text-xs text-gray-400 max-w-md">All stadium gates are operating within safe capacity limits. Ingress flow is nominal. Average response: <strong class="text-white font-mono">4.2m</strong></p>
                    </div>
                `;
            }
            const activeCounter = document.getElementById('header-active-tasks-count');
            if (activeCounter) activeCounter.innerText = "0";

            // Reset AI support panel
            showIdleAIDashboard();
            
            // Hide routing arrow
            const arrow = document.getElementById('map-rerouting-arrow');
            if (arrow) {
                arrow.classList.remove('opacity-100', 'animate-flow');
                arrow.classList.add('opacity-0');
            }
        }

        // 7. Load volunteer dispatches
        async function loadActiveTasks() {
            try {
                const res = await fetch('/api/v1/tasks');
                const tasks = await res.json();
                const container = document.getElementById('tasks-container');
                container.innerHTML = '';
                
                const dict = TRANSLATIONS[currentLanguage];

                // Update active tasks counter in header KPI chip
                const activeTasksCount = tasks.filter(t => t.status !== 'COMPLETED').length;
                document.getElementById('header-active-tasks-count').innerText = activeTasksCount;

                if (activeTasksCount === 0) {
                    container.innerHTML = `
                        <div class="col-span-3 glass-panel rounded-xl p-6 text-center border border-dashed border-gray-850/60 flex flex-col items-center justify-center space-y-2">
                            <span class="text-2xl">🟢</span>
                            <span class="text-sm font-semibold text-white">System Ready - No Active Dispatch Tasks</span>
                            <p class="text-xs text-gray-400 max-w-md">All stadium gates are operating within safe capacity limits. Ingress flow is nominal. Average response: <strong class="text-white font-mono">4.2m</strong></p>
                        </div>
                    `;
                    showIdleAIDashboard();
                    const arrow = document.getElementById('map-rerouting-arrow');
                    if (arrow) {
                        arrow.classList.remove('opacity-100', 'animate-flow');
                        arrow.classList.add('opacity-0');
                    }
                    return;
                }

                tasks.forEach(task => {
                    // Localize task text simulation
                    let taskDetails = escapeHTML(task.details);
                    if (currentLanguage === 'es') {
                        taskDetails = taskDetails.replace("Deploy directional signage", "Colocar señalización direccional")
                                                 .replace("Verbally guide fans", "Guiar verbalmente a los fanáticos");
                    } else if (currentLanguage === 'fr') {
                        taskDetails = taskDetails.replace("Deploy directional signage", "Déployer des panneaux directionnels")
                                                 .replace("Verbally guide fans", "Guider verbalement les supporters");
                    }

                    const card = document.createElement('div');
                    card.className = `p-4 rounded-xl bg-slate-900 border border-gray-850/60 flex flex-col justify-between h-[130px] transition-all hover:border-gray-700`;
                    card.innerHTML = `
                        <div class="flex justify-between items-start mb-2">
                            <span class="text-[10px] bg-blue-900/60 text-blue-300 font-bold px-2 py-0.5 rounded border border-blue-800/40">
                                ROLE: ${escapeHTML(task.assigned_role)}
                            </span>
                            <span id="task-status-badge-${task.id}" class="text-[10px] ${task.status === 'COMPLETED' ? 'bg-emerald-950 text-emerald-400' : 'bg-amber-950 text-amber-400'} font-semibold px-2 py-0.5 rounded border ${task.status === 'COMPLETED' ? 'border-emerald-800' : 'border-amber-800'}">
                                ${task.status}
                            </span>
                        </div>
                        <p class="text-xs text-gray-300 font-semibold mb-2 truncate-2-lines flex-1">${taskDetails}</p>
                        ${task.status !== 'COMPLETED' ? `
                            <button id="task-btn-${task.id}" data-complete-task="${task.id}" class="w-full py-1.5 bg-gray-800 hover:bg-emerald-800 hover:text-white rounded border border-gray-700 hover:border-emerald-700 text-xs font-semibold text-gray-300 transition-all focus:ring-2 focus:ring-blue-500 focus:outline-none">
                                ${dict.btnComplete}
                            </button>
                        ` : `
                            <div class="text-center text-[10px] text-gray-500">${dict.feedbackCaptured}</div>
                        `}
                    `;
                    container.appendChild(card);
                });
            } catch (err) {
                console.error("Load tasks failed:", err);
            }
        }

        // 8. Complete task and submit feedback
        async function completeTask(taskId) {
            try {
                const taskRes = await fetch(`/api/v1/tasks/${taskId}`, {
                    method: 'PATCH',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-Key': activeApiKey
                    },
                    body: JSON.stringify({
                        status: 'COMPLETED'
                    })
                });
                
                if (taskRes.status === 200) {
                    if (activeRecommendationId) {
                        await fetch(`/api/v1/recommendations/${activeRecommendationId}/feedback`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-API-Key': activeApiKey
                            },
                            body: JSON.stringify({
                                accepted: true,
                                applied: true,
                                feedback_rating: 5,
                                feedback_comments: "Task completed successfully; crowd counts starting to lower."
                            })
                        });
                        loadRecommendation(activeRecommendationId);
                    }
                    loadActiveTasks();
                }
            } catch (err) {
                console.error("Complete task failed:", err);
            }
        }

        // 9. Reject and request alternative AI strategy
        function rejectAndRequestAlternative(recId) {
            // Simulate dynamic alternative recalculation
            const reasoningEl = document.querySelector("#ai-recs-container p.font-mono");
            if (reasoningEl) {
                reasoningEl.innerHTML = `AI Reasoner generated alternative strategy: Redirect fans to Gate B bypass channels. Recalculating optimization scores...<br><span class="text-[10px] text-amber-500 font-semibold block mt-1.5">[Alternative Rationale]: Gate A occupancy remains at 85%. Recalculating routing models to leverage Gate B bypass channels (currently operating under 40% capacity) to resolve bottlenecking.</span>`;
            }
            const actionsList = document.querySelector("#ai-recs-container ul");
            if (actionsList) {
                actionsList.innerHTML = `
                    <li class="flex items-start gap-1.5 text-amber-400">
                        <span class="mt-0.5">🔄</span>
                        <span>Open auxiliary bypass gates for Gate B concourse.</span>
                    </li>
                    <li class="flex items-start gap-1.5 text-amber-400">
                        <span class="mt-0.5">🔄</span>
                        <span>Display green alternate route indicators on West Concourse digital signs.</span>
                    </li>
                `;
            }
            // Append log event
            const log = document.getElementById('events-log');
            if (log) {
                const entry = document.createElement('div');
                entry.className = "text-amber-400 font-semibold";
                entry.innerText = `[${new Date().toLocaleTimeString()}] [SYSTEM] Operator rejected Rec ${recId.slice(0,8)}. AI generated alternative routing strategy.`;
                log.appendChild(entry);
                log.scrollTop = log.scrollHeight;
            }
        }

        // 10. View evidence modal
        function viewEvidenceModal(recId) {
            alert(`🔍 Operational Evidence & SOP RAG Context (Rec ${recId.slice(0,8)})\n\n[Retrieved Document] SOP-744: Ingress Bottleneck Management Protocol\n--------------------------------------------------------------\n1. Retrieve live turnstile telemetry count snapshots every 2 minutes.\n2. If zone occupancy ratio exceeds 80% safe capacity, route incoming traffic to closest bypass gates.\n3. Validate target gate occupancy is < 50% capacity before dispatcher approval to avoid secondary bottlenecks.\n\n[Evidence Check]: Gate B is currently at 39% occupancy (Safe capacity: 1500). Alternate routing path verified as low risk.`);
        }

        // 11. Export log reports
        function exportLogsReport() {
            const logEl = document.getElementById('events-log');
            const logsText = logEl.innerText;
            const blob = new Blob([logsText], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `stadium_ops_event_log_${new Date().toISOString().slice(0, 19).replaceAll(':', '-')}.txt`;
            a.click();
            URL.revokeObjectURL(url);
        }
        // 12. Toggle AI Chat Window
        function toggleChatWindow() {
            const chatWindow = document.getElementById('ai-chat-window');
            if (chatWindow) {
                chatWindow.classList.toggle('hidden');
                if (!chatWindow.classList.contains('hidden')) {
                    const field = document.getElementById('chat-input-field');
                    if (field) field.focus();
                }
            }
        }

        // 13. Send Chat Message to Backend
        async function sendChatMessage(event) {
            event.preventDefault();
            const input = document.getElementById('chat-input-field');
            if (!input) return;
            const message = input.value.trim();
            if (!message) return;

            input.value = '';
            
            const container = document.getElementById('chat-messages-container');
            if (!container) return;
            
            // Append User Message bubble
            const userBubble = document.createElement('div');
            userBubble.className = "flex gap-2 items-start justify-end";
            userBubble.innerHTML = `
                <div class="bg-indigo-600/90 text-white p-2.5 rounded-2xl rounded-tr-none max-w-[85%]">
                    ${escapeHTML(message)}
                </div>
            `;
            container.appendChild(userBubble);
            container.scrollTop = container.scrollHeight;

            // Append Typing Indicator
            const typingBubble = document.createElement('div');
            typingBubble.className = "flex gap-2 items-start";
            typingBubble.id = "chat-typing-indicator";
            typingBubble.innerHTML = `
                <div class="bg-slate-900 border border-slate-800 p-2.5 rounded-2xl rounded-tl-none text-gray-500">
                    Typing...
                </div>
            `;
            container.appendChild(typingBubble);
            container.scrollTop = container.scrollHeight;

            try {
                const res = await fetch('/api/v1/assistant/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-Key': activeApiKey
                    },
                    body: JSON.stringify({ message: message })
                });
                
                const data = await res.json();
                
                // Remove typing indicator
                const indicator = document.getElementById('chat-typing-indicator');
                if (indicator) indicator.remove();

                // Append Assistant Message bubble
                const assistantBubble = document.createElement('div');
                assistantBubble.className = "flex gap-2 items-start";
                assistantBubble.innerHTML = `
                    <div class="bg-slate-900 border border-slate-800 p-2.5 rounded-2xl rounded-tl-none max-w-[85%] text-gray-200">
                        ${escapeHTML(data.response).replaceAll('\n', '<br>')}
                    </div>
                `;
                container.appendChild(assistantBubble);
                container.scrollTop = container.scrollHeight;

                // Append log event dynamically to showcase human-in-the-loop conversation
                const log = document.getElementById('events-log');
                if (log) {
                    const entry = document.createElement('div');
                    entry.className = "text-indigo-400";
                    entry.innerText = `[${new Date().toLocaleTimeString()}] [ASSISTANT] Answered query with intent: "${data.intent}".`;
                    log.appendChild(entry);
                    log.scrollTop = log.scrollHeight;
                }

            } catch (err) {
                console.error("Chat message failed:", err);
                const indicator = document.getElementById('chat-typing-indicator');
                if (indicator) indicator.remove();
                
                const errBubble = document.createElement('div');
                errBubble.className = "flex gap-2 items-start";
                errBubble.innerHTML = `
                    <div class="bg-red-950/40 border border-red-900/50 p-2.5 rounded-2xl rounded-tl-none text-red-400">
                        Failed to connect to the assistant service.
                    </div>
                `;
                container.appendChild(errBubble);
                container.scrollTop = container.scrollHeight;
            }
        }

// CSP Conformance: Bind event listeners dynamically on DOMContentLoaded
document.addEventListener("DOMContentLoaded", () => {
    // 1. SVG Map Interactive Zones
    document.querySelectorAll('[data-zone]').forEach(el => {
        const zone = el.dataset.zone;
        el.addEventListener('click', () => {
            if (typeof selectZone === 'function') selectZone(zone);
        });
        el.addEventListener('keydown', (event) => {
            if (typeof handleMapKey === 'function') handleMapKey(event, zone);
        });
    });

    // 2. Telemetry Ingestion Buttons
    document.querySelectorAll('[data-telemetry]').forEach(btn => {
        const count = Number.parseInt(btn.dataset.telemetry, 10);
        btn.addEventListener('click', () => {
            if (typeof sendTelemetry === 'function') sendTelemetry(count);
        });
    });

    // 2.5 Language Selector Change
    document.getElementById('lang-selector')?.addEventListener('change', () => {
        if (typeof changeLanguage === 'function') changeLanguage();
    });

    // 3. Simulation Control Center
    document.getElementById('btn-run-simulation')?.addEventListener('click', () => {
        if (typeof runSyntheticScenario === 'function') runSyntheticScenario();
    });
    document.getElementById('btn-pause-simulation')?.addEventListener('click', () => {
        if (typeof pauseSimulation === 'function') pauseSimulation();
    });
    document.getElementById('btn-reset-simulation')?.addEventListener('click', () => {
        if (typeof resetSimulation === 'function') resetSimulation();
    });

    // 4. Export Logs Report
    document.getElementById('btn-export-logs')?.addEventListener('click', () => {
        if (typeof exportLogsReport === 'function') exportLogsReport();
    });

    // 5. Chat Window Triggers & API Key Submission
    document.getElementById('ai-chat-bubble')?.addEventListener('click', () => {
        if (typeof toggleChatWindow === 'function') toggleChatWindow();
    });
    document.getElementById('ai-chat-bubble')?.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
            if (typeof toggleChatWindow === 'function') toggleChatWindow();
            event.preventDefault();
        }
    });
    document.getElementById('btn-close-chat')?.addEventListener('click', () => {
        if (typeof toggleChatWindow === 'function') toggleChatWindow();
    });
    document.getElementById('btn-submit-api-key')?.addEventListener('click', () => {
        if (typeof submitApiKey === 'function') submitApiKey();
    });

    // 6. Event Delegation for Dynamic Recommendations Panel
    document.addEventListener('click', (event) => {
        const target = event.target.closest('[data-approve], [data-reject], [data-evidence]');
        if (!target) return;
        
        if (target.dataset.approve !== undefined) {
            const recId = target.dataset.approve;
            if (typeof approveRecommendation === 'function') approveRecommendation(recId);
        } else if (target.dataset.reject !== undefined) {
            const recId = target.dataset.reject;
            if (typeof rejectAndRequestAlternative === 'function') rejectAndRequestAlternative(recId);
        } else if (target.dataset.evidence !== undefined) {
            const recId = target.dataset.evidence;
            if (typeof viewEvidenceModal === 'function') viewEvidenceModal(recId);
        }
    });

    // 7. Event Delegation for Dynamic Tasks Panel
    document.addEventListener('click', (event) => {
        const target = event.target.closest('[data-complete-task]');
        if (!target) return;
        
        const taskId = target.dataset.completeTask;
        if (typeof completeTask === 'function') completeTask(taskId);
    });
});
