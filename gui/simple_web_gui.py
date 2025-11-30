#!/usr/bin/env python3
"""
SolarEdge ScanWriter - Modern Web GUI
Dashboard moderno per gestione device e API endpoints
"""

import asyncio
import json
import socket
from pathlib import Path
from aiohttp import web
from datetime import datetime
from app_logging.universal_logger import get_logger
from utils.yaml_loader import load_yaml, save_yaml

class SimpleWebGUI:
    # Lookup table for endpoint config file paths (class-level constant)
    ENDPOINT_CONFIG_FILES = {
        'api_ufficiali': 'config/sources/api_endpoints.yaml',
        'web': 'config/sources/web_endpoints.yaml',
        'modbus': 'config/sources/modbus_endpoints.yaml'
    }

    def __init__(self, config_file="config/main.yaml", port=8092, cache=None, auto_start_loop=False):
        self.config_file = Path(config_file)
        self.logger = get_logger("SimpleWebGUI")
        self.real_ip = self._get_real_ip()
        self.app = None
        self.config = {}
        self.cache = cache  # Cache manager condiviso
        self.auto_start_loop = auto_start_loop  # Flag per avvio automatico

        # Server configuration (immutable)
        from gui.components.web_server import ServerConfig
        import os
        self.server_config = ServerConfig(
            host=os.getenv('GUI_HOST', '0.0.0.0'),
            port=port or int(os.getenv('GUI_PORT', 8092)),
            template_dir=Path("gui/templates"),
            static_dir=Path("gui/static")
        )
        self.port = self.server_config.port  # Backward compatibility

        # REFACTORED: Usa componenti separati per Single Responsibility
        from gui.core.config_handler import ConfigHandler
        from gui.core.state_manager import StateManager
        from gui.core.unified_toggle_handler import UnifiedToggleHandler
        from gui.core.error_handler import UnifiedErrorHandler

        self.config_handler = ConfigHandler()
        self.state_manager = StateManager(max_log_buffer=1000)
        self.unified_toggle_handler = UnifiedToggleHandler(auto_update_source_callback=self._auto_update_source_enabled)
        self.error_handler = UnifiedErrorHandler(self.logger)

        # Setup log capture per la GUI
        self._setup_log_capture()



    async def _auto_start_loop(self):
        """Avvia automaticamente il loop senza richiesta HTTP"""
        try:
            if self.state_manager.loop_running:
                self.logger.info("[GUI] Loop già in esecuzione")
                return

            self.logger.info("[GUI] Avvio automatico loop - ricaricamento configurazione...")

            # 1. Ricarica variabili d'ambiente dal file .env
            try:
                from config.env_loader import load_env
                load_env()
                self.logger.info("[GUI] ✅ Variabili d'ambiente ricaricate da .env")
            except Exception as e:
                self.logger.error(f"[GUI] ❌ Errore ricaricamento .env: {e}")

            # 2. Ricarica configurazione YAML principale
            try:
                await self.load_config()
                self.logger.info("[GUI] ✅ Configurazione YAML principale ricaricata")
            except Exception as e:
                self.logger.error(f"[GUI] ❌ Errore ricaricamento config: {e}")

            # 3. Ricarica config manager globale
            try:
                from config.config_manager import get_config_manager
                config_manager = get_config_manager()
                config_manager.reload()
                self.logger.info("[GUI] ✅ Config manager globale ricaricato")
            except Exception as e:
                self.logger.error(f"[GUI] ❌ Errore ricaricamento config manager: {e}")
                config_manager = None


            # 4. Reset flag di stop e avvia il loop
            self.state_manager.stop_requested = False
            self.state_manager.loop_running = True
            self.state_manager.loop_mode = True  # Abilita modalità loop

            # 5. Avvia il loop personalizzato per GUI
            import asyncio

            # IMPORTANTE: Usa config_manager.get_raw_config() invece di self.load_config()
            # per assicurarsi che i sources (web_scraping, api, modbus) siano caricati
            # dai file in config/sources/, altrimenti mancano i device_id e category mappings
            if config_manager:
                config = config_manager.get_raw_config()
                self.logger.info("[GUI] ✅ Config completo caricato con sources da config_manager")
            else:
                # Fallback a self.load_config() se config_manager non disponibile
                config = await self.load_config()
                self.logger.warning("[GUI] ⚠️ Usando config da self.load_config() (senza sources)")

            # Usa il cache manager condiviso passato dal main
            if not self.cache:
                from cache.cache_manager import CacheManager
                self.cache = CacheManager()
                self.logger.warning("[GUI] Cache non passato, creando nuova istanza")

            # Avvia il loop asincrono personalizzato
            asyncio.create_task(self._run_existing_loop(self.cache, config))

            self.logger.info("[GUI] 🚀 Loop avviato automaticamente con configurazione aggiornata")

        except Exception as e:
            self.logger.error(f"[GUI] Errore avvio automatico loop: {e}")

    def _get_real_ip(self):
        """Ottiene l'IP reale della macchina"""
        try:
            # Crea una connessione socket temporanea per ottenere l'IP locale
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # Connessione a un indirizzo esterno (non invia dati)
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            # Fallback a localhost se non riesce
            return "127.0.0.1"

    def _auto_update_source_enabled(self, update_context: dict) -> tuple[bool, bool]:
        """Helper per auto-aggiornare source.enabled basandosi sugli endpoint/device.

        Args:
            update_context: Dictionary containing:
                - config: Configurazione completa caricata
                - source_key: Chiave della sorgente (es: 'api_ufficiali', 'web_scraping', 'modbus')
                - endpoints_or_devices: Dizionario degli endpoint o device
                - config_path: Path del file di configurazione
                - source_name: Nome leggibile della sorgente per i log (es: 'API', 'Web scraping', 'Modbus')

        Returns:
            Tuple (source_updated, new_enabled_state)
        """
        config = update_context['config']
        source_key = update_context['source_key']
        entities = update_context['endpoints_or_devices']
        source_name = update_context['source_name']

        # Controlla se almeno un endpoint/device è abilitato
        any_enabled = any(
            ep.get('enabled', False)
            for ep in entities.values()
            if isinstance(ep, dict)
        )

        old_enabled = config[source_key].get('enabled', False)

        if old_enabled != any_enabled:
            config[source_key]['enabled'] = any_enabled
            enabled_count = sum(1 for ep in entities.values() if isinstance(ep, dict) and ep.get('enabled', False))
            self.logger.info(f"{source_name} auto-{'abilitato' if any_enabled else 'disabilitato'} (endpoint attivi: {enabled_count})")
            return True, any_enabled

        return False, old_enabled

    async def load_config(self):
        """Carica la configurazione YAML dal main.yaml - REFACTORED"""
        self.config = await self.config_handler.load_main_config(self.config_file)
        return self.config

    async def save_config(self):
        """Salva la configurazione YAML principale - REFACTORED"""
        return await self.config_handler.save_main_config(self.config_file, self.config)

    async def _load_source_config(self, source_type: str) -> dict:
        """Delega a ConfigHandler - REFACTORED"""
        return await self.config_handler.load_source_config(source_type)



    async def handle_index(self, request):
        """Serve la pagina principale"""
        try:
            template_path = Path("gui/templates/index.html")
            if template_path.exists():
                html_content = template_path.read_text(encoding='utf-8')

                # Sostituisce l'IP hardcoded con l'IP reale
                html_content = html_content.replace('127.0.0.1:8092', f'{self.real_ip}:{self.port}')

                # Sostituisce gli intervalli con quelli reali dal .env
                import os
                api_interval = int(os.getenv('LOOP_API_INTERVAL_MINUTES', '15'))
                web_interval = int(os.getenv('LOOP_WEB_INTERVAL_MINUTES', '15'))
                realtime_interval = int(os.getenv('LOOP_REALTIME_INTERVAL_SECONDS', '5'))

                intervals_text = f"⏰ Intervalli: API/Web ogni {max(api_interval, web_interval)} min, Realtime ogni {realtime_interval} sec"
                html_content = html_content.replace('⏰ Intervalli: API/Web ogni 15 min, Realtime ogni 5 sec', intervals_text)

                return web.Response(text=html_content, content_type='text/html')
            else:
                return web.Response(text="Template non trovato", status=404)
        except Exception as e:
            return self.error_handler.handle_api_error(e, "serving index", "Error loading page")

    async def handle_static(self, request):
        """Serve i file statici (testo e binari)"""
        try:
            filename = request.match_info['filename']
            static_path = Path(f"gui/static/{filename}")

            if static_path.exists():
                # Determina content type e se è un file binario
                if filename.endswith('.css'):
                    content_type = 'text/css'
                    is_binary = False
                elif filename.endswith('.js'):
                    content_type = 'application/javascript'
                    is_binary = False
                elif filename.endswith('.png'):
                    content_type = 'image/png'
                    is_binary = True
                elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
                    content_type = 'image/jpeg'
                    is_binary = True
                elif filename.endswith('.gif'):
                    content_type = 'image/gif'
                    is_binary = True
                elif filename.endswith('.svg'):
                    content_type = 'image/svg+xml'
                    is_binary = False
                elif filename.endswith('.ico'):
                    content_type = 'image/x-icon'
                    is_binary = True
                else:
                    content_type = 'text/plain'
                    is_binary = False

                # Leggi file in base al tipo
                if is_binary:
                    content = static_path.read_bytes()
                    return web.Response(body=content, content_type=content_type)
                else:
                    content = static_path.read_text(encoding='utf-8')
                    return web.Response(text=content, content_type=content_type)
            else:
                return self.error_handler.handle_not_found_error("file", filename, "serving static")
        except UnicodeDecodeError as e:
            self.logger.error(f"Errore decodifica UTF-8 per {filename}: {e}")
            return self.error_handler.handle_api_error(e, "serving static file", "Errore decodifica file")
        except Exception as e:
            return self.error_handler.handle_api_error(e, "serving static file", "Error loading static file")

    async def handle_favicon(self, request):
        """Serve a favicon.ico if present, otherwise return a no‑content response."""
        from pathlib import Path
        favicon_path = Path('gui/static/favicon.png')
        if favicon_path.is_file():
            return web.FileResponse(path=favicon_path)
        # No favicon file – return an empty 204 response to silence the error
        return web.Response(status=204)

    async def handle_ping(self, request):
        """Endpoint di ping per verificare connessione"""
        return web.json_response({
            "status": "ok",
            "message": "SolarEdge Dashboard Online",
            "timestamp": asyncio.get_event_loop().time()
        })

    async def handle_get_config(self, request):
        """Restituisce la configurazione completa"""
        await self.load_config()
        return web.json_response(self.config)

    async def handle_get_yaml_file(self, request):
        """Restituisce il contenuto di un file di configurazione specifico - REFACTORED"""
        try:
            file_type = request.query.get('file', 'main')

            # Delega a ConfigHandler
            content, error = await self.config_handler.get_yaml_file_content(file_type)

            if error:
                status = 404 if 'non trovato' in error else 400
                return web.json_response({'error': error}, status=status)

            # Use ConfigHandler's lookup table for consistency
            from gui.core.config_handler import ConfigHandler
            config_file_path = ConfigHandler.CONFIG_FILE_PATHS.get(file_type, '')

            return web.json_response({
                'file': file_type,
                'path': config_file_path,
                'content': content
            })

        except Exception as e:
            return self.error_handler.handle_api_error(e, "getting YAML file", "Error loading configuration file")

    async def handle_save_yaml_file(self, request):
        """Salva il contenuto di un file di configurazione specifico - REFACTORED"""
        try:
            data = await request.json()
            file_type = data.get('file', 'main')
            content = data.get('content', '')

            # Delega a ConfigHandler
            success, error = await self.config_handler.save_yaml_file(file_type, content)

            if not success:
                return web.json_response({'error': error}, status=400)

            # Use ConfigHandler's lookup table for consistency
            from gui.core.config_handler import ConfigHandler
            config_file_path = ConfigHandler.CONFIG_FILE_PATHS.get(file_type, '')

            return self.error_handler.create_success_response(
                f'File {file_type} salvato con successo',
                {
                    'file': file_type,
                    'path': config_file_path
                }
            )

        except Exception as e:
            return self.error_handler.handle_api_error(e, "saving YAML file", "Error saving configuration file")

    async def handle_get_sources(self, request):
        """Restituisce sorgenti unificate (web devices, api endpoints o modbus endpoints) - OTTIMIZZATO"""
        try:
            source_type = request.query.get('type', 'web')  # 'web', 'api' o 'modbus'

            # Validazione input
            if source_type not in ('web', 'api', 'modbus'):
                return self.error_handler.handle_validation_error("type must be 'web', 'api', or 'modbus'", "getting sources")

            await self.load_config()

            # Usa metodo unificato async (no executor needed!)
            sources = await self._load_source_config(source_type)

            return web.json_response(sources)

        except Exception as e:
            return self.error_handler.handle_api_error(e, "getting sources", "Error loading sources")

    async def handle_loop_status(self, request):
        """Restituisce lo stato del loop mode - REFACTORED"""
        try:
            # Delega a StateManager (gestisce serializzazione datetime)
            return web.json_response(self.state_manager.get_loop_status())

        except Exception as e:
            return self.error_handler.handle_api_error(e, "getting loop status", "Error retrieving loop status")
    async def handle_loop_logs(self, request):
        """Restituisce i log del loop mode con filtro opzionale per flow - REFACTORED"""
        try:
            # Parametri query
            limit = int(request.query.get('limit', 2000))
            flow_filter = request.query.get('flow', 'all')

            # Delega a StateManager
            filtered_logs = self.state_manager.get_filtered_logs(flow_filter, limit)
            return web.json_response({
                "logs": filtered_logs,
                "total": len(filtered_logs),
                "flow_filter": flow_filter
            })

        except Exception as e:
            return self.error_handler.handle_api_error(e, "getting loop logs", "Error retrieving logs")



    async def handle_loop_start(self, request):
        """Avvia il loop mode con ricaricamento configurazione"""
        try:
            if self.state_manager.loop_running:
                return web.json_response({
                    "status": "info",
                    "message": "Loop già in esecuzione"
                })

            self.logger.info("[GUI] Richiesta start loop ricevuta - ricaricamento configurazione...")

            # 1. Ricarica variabili d'ambiente dal file .env
            try:
                from config.env_loader import load_env
                load_env()
                self.logger.info("[GUI] ✅ Variabili d'ambiente ricaricate da .env")
            except Exception as e:
                self.logger.error(f"[GUI] ❌ Errore ricaricamento .env: {e}")

            # 2. Ricarica configurazione YAML principale
            try:
                await self.load_config()
                self.logger.info("[GUI] ✅ Configurazione YAML principale ricaricata")
            except Exception as e:
                self.logger.error(f"[GUI] ❌ Errore ricaricamento config: {e}")

            # 3. Ricarica config manager globale
            try:
                from config.config_manager import get_config_manager
                config_manager = get_config_manager()
                config_manager.reload()
                self.logger.info("[GUI] ✅ Config manager globale ricaricato")
            except Exception as e:
                self.logger.error(f"[GUI] ❌ Errore ricaricamento config manager: {e}")

            # 4. Reset flag di stop e avvia il loop
            self.state_manager.stop_requested = False
            self.state_manager.loop_running = True
            self.state_manager.loop_mode = True  # Abilita modalità loop

            # 5. Avvia il loop personalizzato per GUI
            import asyncio

            config = await self.load_config()

            # Usa il cache manager condiviso passato dal main
            if not self.cache:
                from cache.cache_manager import CacheManager
                self.cache = CacheManager()
                self.logger.warning("[GUI] Cache non passato, creando nuova istanza")

            # Avvia il loop asincrono personalizzato
            asyncio.create_task(self._run_existing_loop(self.cache, config))

            self.logger.info("[GUI] 🚀 Loop avviato con configurazione aggiornata")

            return self.error_handler.create_success_response("Loop avviato con configurazione ricaricata")
        except Exception as e:
            return self.error_handler.handle_api_error(e, "starting loop", "Error starting loop")

    async def handle_loop_stop(self, request):
        """Ferma il loop mode (senza chiudere la GUI)"""
        try:
            self.logger.info("[GUI] Richiesta stop loop ricevuta")

            # Imposta il flag per fermare il loop
            self.state_manager.stop_requested = True
            self.state_manager.loop_running = False
            self.state_manager.loop_mode = False  # Disabilita modalità loop

            # Aggiorna statistiche
            self.state_manager.loop_stats['status'] = 'stopped'

            self.logger.info("[GUI] ✅ Loop fermato con successo")

            return self.error_handler.create_success_response("Loop fermato con successo")
        except Exception as e:
            return self.error_handler.handle_api_error(e, "stopping loop", "Error stopping loop")

    async def handle_clear_logs(self, request):
        """Pulisce i log e le run salvate - REFACTORED"""
        try:
            self.logger.info("[GUI] Richiesta clear logs ricevuta")

            # Delega a StateManager
            self.state_manager.clear_logs()

            self.logger.info("[GUI] ✅ Log puliti con successo")

            return self.error_handler.create_success_response("Log puliti con successo")
        except Exception as e:
            return self.error_handler.handle_api_error(e, "clearing logs", "Error clearing logs")

    async def handle_log(self, request):
        """Endpoint per logging dal frontend"""
        try:
            data = await request.json()
            level = data.get('level', 'info')
            message = data.get('message', '')
            error = data.get('error')

            if level == 'error':
                if error:
                    self.logger.error(f"[FRONTEND] {message}: {error}")
                else:
                    self.logger.error(f"[FRONTEND] {message}")
            elif level == 'warning':
                self.logger.warning(f"[FRONTEND] {message}")
            else:
                self.logger.info(f"[FRONTEND] {message}")

            return web.json_response({"status": "logged"})
        except Exception as e:
            return self.error_handler.handle_api_error(e, "logging from frontend", "Error processing log")

    def create_app(self):
        """Crea l'applicazione web"""
        self.app = web.Application()

        # Setup middleware stack
        from gui.core.middleware import create_middleware_stack
        self.app.middlewares.extend(create_middleware_stack(self.logger))
        self.logger.info("[GUI] ✅ Middleware stack configurato (Error, Logging, CORS, Security)")

        # Routes
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/static/{filename}', self.handle_static)
        self.app.router.add_get('/favicon.ico', self.handle_favicon)
        self.app.router.add_get('/api/ping', self.handle_ping)
        self.app.router.add_get('/api/config', self.handle_get_config)
        self.app.router.add_get('/api/config/yaml', self.handle_get_yaml_file)
        self.app.router.add_post('/api/config/yaml', self.handle_save_yaml_file)
        self.app.router.add_get('/api/sources', self.handle_get_sources)

        # Loop mode routes
        self.app.router.add_get('/api/loop/status', self.handle_loop_status)
        self.app.router.add_get('/api/loop/logs', self.handle_loop_logs)
        self.app.router.add_post('/api/loop/start', self.handle_loop_start)
        self.app.router.add_post('/api/loop/stop', self.handle_loop_stop)
        self.app.router.add_post('/api/loop/logs/clear', self.handle_clear_logs)

        # Endpoint configuration routes
        self.app.router.add_post('/api/endpoints/toggle', self.handle_toggle_endpoint)
        self.app.router.add_post('/api/devices/toggle', self.handle_toggle_device)
        self.app.router.add_post('/api/devices/metrics/toggle', self.handle_toggle_device_metric)
        self.app.router.add_post('/api/modbus/devices/toggle', self.handle_toggle_modbus_device)
        self.app.router.add_post('/api/modbus/devices/metrics/toggle', self.handle_toggle_modbus_metric)
        self.app.router.add_post('/api/gme/toggle', self.handle_toggle_gme)

        self.app.router.add_post('/api/log', self.handle_log)

        # Update check routes
        self.app.router.add_get('/api/updates/check', self.handle_check_updates)
        self.app.router.add_post('/api/updates/run', self.handle_run_update)
        self.app.router.add_get('/api/updates/status', self.handle_get_update_status)

        return self.app

    async def start(self, host=None, port=None):
        """Metodo start per compatibilità con main.py"""
        # Usa configurazione da server_config o parametri forniti
        bind_host = host if host else self.server_config.host
        bind_port = port if port else self.server_config.port
        runner, site = await self.start_server(bind_host, bind_port)

        # Ritorna subito dopo aver avviato il server, senza loop infinito
        return runner, site

    async def start_server(self, host='0.0.0.0', port=None):
        """Avvia il server web"""
        try:
            await self.load_config()

            # Usa port da parametro o da server_config
            bind_port = port if port else self.server_config.port

            self.logger.info("[GUI] Avvio GUI Web...")

            # Configura logging aiohttp per ridurre verbosità
            import logging
            aiohttp_logger = logging.getLogger('aiohttp.access')
            aiohttp_logger.setLevel(logging.WARNING)

            # Configura app con backlog ridotto per evitare busy-wait
            runner = web.AppRunner(self.create_app(), access_log=None)
            await runner.setup()

            # TCPSite con backlog limitato per ridurre overhead
            site = web.TCPSite(runner, host, bind_port, backlog=128)
            await site.start()

            self.logger.info(f"[GUI] Uso porta {bind_port}")
            self.logger.info(f"[GUI] GUI Web avviata su: http://{self.real_ip}:{bind_port}")

            self.logger.info("="*50)
            self.logger.info("🚀 SOLAREDGE SCANWRITER")
            self.logger.info("="*50)

            # Log configurazione sistema per GUI (General tab)
            # Log configurazione sistema per GUI (General tab)
            from config.config_manager import get_config_manager
            try:
                cm = get_config_manager()
                
                # Startup banner
                self.logger.info("[SYSTEM] " + "="*50)
                self.logger.info("[SYSTEM] 🚀 SOLAREDGE SCANWRITER")
                self.logger.info("[SYSTEM] " + "="*50)
                
                # Configuration
                self.logger.info(f"[SYSTEM] ⚙️  Configurazione caricata da {self.config_file} (YAML + variabili d'ambiente)")

                # Scheduler
                try:
                    sched = cm.get_scheduler_config()
                    self.logger.info(
                        f"[SYSTEM] ⏱️  Scheduler configurato (API: {sched.api_delay_seconds}s, "
                        f"Web: {sched.web_delay_seconds}s, "
                        f"Realtime: {sched.realtime_delay_seconds}s, "
                        f"GME: {sched.gme_delay_seconds}s)"
                    )
                except Exception as e:
                    self.logger.warning(f"[SYSTEM] ⚠️ Errore log Scheduler: {e}")

                # InfluxDB
                try:
                    influx = cm.get_influxdb_config()
                    self.logger.info(
                        f"[SYSTEM] 💾 InfluxDB connesso a {influx.url} (Buckets: {influx.bucket}, {influx.bucket_realtime}, {influx.bucket_gme})"
                    )
                except Exception as e:
                    self.logger.warning(f"[SYSTEM] ⚠️ Errore log InfluxDB: {e}")

                # Web Server & GUI
                try:
                    self.logger.info(f"[SYSTEM] 🌐 Web Server in ascolto su http://{self.real_ip}:{bind_port}")
                    self.logger.info(f"[SYSTEM] 📊 GUI Dashboard inizializzata e pronta")
                except Exception as e:
                    self.logger.warning(f"[SYSTEM] ⚠️ Errore log Web/GUI: {e}")

                # Cache
                self.logger.info("[SYSTEM] 🗄️  Cache centralizzata inizializzata e operativa")
                
                # Log settings info
                self.logger.info("[SYSTEM] 📝 Log inizializzati (TUTTI: reset 24h, Flow: ultime 3 run, SISTEMA: mai resettati)")

            except Exception as e:
                self.logger.warning(f"Impossibile inizializzare config manager per log: {e}")


            # Avvia automaticamente il loop se richiesto
            if self.auto_start_loop:
                self.logger.info("[GUI] 🚀 Avvio automatico del loop...")
                await self._auto_start_loop()

            return runner, site

        except Exception as e:
            self.logger.error(f"[GUI] Errore avvio server: {e}")
            raise

    def _parse_endpoint_id(self, endpoint_id):
        """Parse endpoint ID to determine source type and endpoint name"""
        parts = endpoint_id.split('.')
        if len(parts) >= 2:
            return parts[0], parts[1]  # source_type, endpoint_name
        return 'api_ufficiali', endpoint_id  # Default to API for simple names

    def _get_config_file_path(self, source_type):
        """Map source type to config file path using class-level lookup table"""
        return self.ENDPOINT_CONFIG_FILES.get(source_type)

    def _load_endpoint_config(self, config_path):
        """Load endpoint configuration from file"""
        try:
            return load_yaml(config_path, substitute_env=True, use_cache=True), None
        except FileNotFoundError:
            return None, f'Config file not found: {config_path}'
        except Exception as e:
            return None, f'Error loading config: {str(e)}'

    def _toggle_endpoint_state(self, config, source_type, endpoint_name):
        """Toggle endpoint enabled state and return result"""
        if source_type not in config or 'endpoints' not in config[source_type]:
            return None, f'Invalid config structure'

        endpoints = config[source_type]['endpoints']
        if endpoint_name not in endpoints:
            return None, f'Endpoint not found: {endpoint_name}'

        current_state = endpoints[endpoint_name].get('enabled', False)
        new_state = not current_state
        endpoints[endpoint_name]['enabled'] = new_state

        return (current_state, new_state, endpoints), None

    def _save_endpoint_config(self, config_path, config):
        """Save endpoint configuration to file"""
        if not save_yaml(config_path, config, invalidate_cache=True):
            return False, 'Failed to save configuration'
        return True, None

    async def handle_toggle_endpoint(self, request):
        """Toggle endpoint enabled/disabled state"""
        try:
            endpoint_id = request.query.get('id')
            if not endpoint_id:
                return web.json_response({'error': 'Missing endpoint ID'}, status=400)

            source_type, endpoint_name = self._parse_endpoint_id(endpoint_id)

            config_file = self._get_config_file_path(source_type)
            if not config_file:
                return web.json_response({'error': f'Unknown source type: {source_type}'}, status=400)

            config_path = Path(config_file)
            config, error = self._load_endpoint_config(config_path)
            if error:
                status = 404 if 'not found' in error else 500
                return web.json_response({'error': error}, status=status)

            toggle_result, error = self._toggle_endpoint_state(config, source_type, endpoint_name)
            if error:
                status = 404 if 'not found' in error else 500
                return web.json_response({'error': error}, status=status)

            current_state, new_state, endpoints = toggle_result

            # Auto-update source.enabled for API endpoints
            source_updated = False
            any_enabled = False
            if source_type == 'api_ufficiali':
                update_context = {
                    'config': config,
                    'source_key': source_type,
                    'endpoints_or_devices': endpoints,
                    'config_path': config_path,
                    'source_name': 'API'
                }
                source_updated, any_enabled = self._auto_update_source_enabled(update_context)

            success, error = self._save_endpoint_config(config_path, config)
            if not success:
                return web.json_response({'error': error}, status=500)

            self.logger.info(f"Toggled endpoint {endpoint_id}: {current_state} -> {new_state}")

            response_data = {
                'success': True,
                'endpoint_id': endpoint_id,
                'enabled': new_state,
                'message': f'Endpoint {endpoint_id} {"enabled" if new_state else "disabled"}'
            }

            if source_updated:
                response_data['source_auto_updated'] = True
                response_data['source_enabled'] = any_enabled
                response_data['message'] += f" - API {'abilitato' if any_enabled else 'disabilitato'} automaticamente"

            return web.json_response(response_data)

        except Exception as e:
            self.logger.error(f"Error toggling endpoint: {e}")
            return web.json_response({'error': f'Internal server error: {str(e)}'}, status=500)

    async def handle_toggle_device(self, request):
        """Toggle web device enabled/disabled state - Uses UnifiedToggleHandler"""
        try:
            device_id = request.query.get('id')
            if not device_id:
                return self.error_handler.handle_validation_error('device ID', 'toggling device')

            success, response_data = await self.unified_toggle_handler.handle_toggle_device(device_id)

            if not success:
                status = 404 if 'not found' in response_data.get('error', '').lower() else 400
                return web.json_response(response_data, status=status)

            return web.json_response(response_data)

        except Exception as e:
            return self.error_handler.handle_api_error(e, "toggling web device", "Error toggling device")

    async def handle_toggle_modbus_device(self, request):
        """Toggle modbus device enabled/disabled state - Uses UnifiedToggleHandler"""
        try:
            device_id = request.query.get('id')
            if not device_id:
                return self.error_handler.handle_validation_error('device ID', 'toggling modbus device')

            success, response_data = await self.unified_toggle_handler.handle_toggle_modbus_device(device_id)

            if not success:
                status = 404 if 'not found' in response_data.get('error', '').lower() else 400
                return web.json_response(response_data, status=status)

            return web.json_response(response_data)

        except Exception as e:
            return self.error_handler.handle_api_error(e, "toggling modbus device", "Error toggling modbus device")

    async def handle_toggle_device_metric(self, request):
        """Toggle web device metric enabled/disabled state - Uses UnifiedToggleHandler"""
        try:
            device_id = request.query.get('id')
            metric = request.query.get('metric')
            if not device_id or not metric:
                return self.error_handler.handle_validation_error('device ID and metric', 'toggling device metric')

            success, response_data = await self.unified_toggle_handler.handle_toggle_device_metric(device_id, metric)

            if not success:
                status = 404 if 'not found' in response_data.get('error', '').lower() else 400
                return web.json_response(response_data, status=status)

            return web.json_response(response_data)

        except Exception as e:
            return self.error_handler.handle_api_error(e, "toggling web device metric", "Error toggling device metric")

    async def handle_toggle_modbus_metric(self, request):
        """Toggle modbus device metric enabled/disabled state - Uses UnifiedToggleHandler"""
        try:
            device_id = request.query.get('id')
            metric = request.query.get('metric')
            if not device_id or not metric:
                return self.error_handler.handle_validation_error('device ID and metric', 'toggling modbus metric')

            success, response_data = await self.unified_toggle_handler.handle_toggle_modbus_metric(device_id, metric)

            if not success:
                status = 404 if 'not found' in response_data.get('error', '').lower() else 400
                return web.json_response(response_data, status=status)

            return web.json_response(response_data)

        except Exception as e:
            return self.error_handler.handle_api_error(e, "toggling modbus device metric", "Error toggling modbus metric")

    async def handle_toggle_gme(self, request):
        """Toggle GME flow enabled/disabled state"""
        try:
            await self.load_config()

            # Toggle GME enabled state
            current_state = self.config.get('gme', {}).get('enabled', False)
            new_state = not current_state

            if 'gme' not in self.config:
                self.config['gme'] = {}

            self.config['gme']['enabled'] = new_state

            # Save config
            await self.save_config()

            self.logger.info(f"[GUI] GME {'abilitato' if new_state else 'disabilitato'}")

            return web.json_response({
                'status': 'success',
                'message': f'GME {"abilitato" if new_state else "disabilitato"}',
                'enabled': new_state
            })

        except Exception as e:
            return self.error_handler.handle_api_error(e, "toggling GME", "Error toggling GME")

    async def handle_check_updates(self, request):
        """Controlla se ci sono nuovi aggiornamenti disponibili"""
        try:
            import subprocess
            import os

            # Esegui git fetch per aggiornare le informazioni remote
            result = subprocess.run(
                ['git', 'fetch', 'origin'],
                cwd=os.getcwd(),
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                return web.json_response({
                    'status': 'error',
                    'message': 'Errore durante il controllo degli aggiornamenti',
                    'error': result.stderr
                }, status=500)

            # Controlla se il branch locale è dietro rispetto al remote
            result = subprocess.run(
                ['git', 'rev-list', '--left-right', '--count', 'HEAD...origin/main'],
                cwd=os.getcwd(),
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                # Prova con 'master' se 'main' non esiste
                result = subprocess.run(
                    ['git', 'rev-list', '--left-right', '--count', 'HEAD...origin/master'],
                    cwd=os.getcwd(),
                    capture_output=True,
                    text=True,
                    timeout=10
                )

            if result.returncode == 0:
                local, remote = map(int, result.stdout.strip().split())
                updates_available = remote > 0

                # Salva lo stato nel state manager
                self.state_manager.updates_available = updates_available
                self.state_manager.last_update_check = datetime.now()

                return web.json_response({
                    'status': 'success',
                    'updates_available': updates_available,
                    'local_commits': local,
                    'remote_commits': remote,
                    'message': f'Aggiornamenti disponibili: {remote} commit' if updates_available else 'Sei già aggiornato'
                })
            else:
                return web.json_response({
                    'status': 'error',
                    'message': 'Errore durante il controllo degli aggiornamenti',
                    'error': result.stderr
                }, status=500)

        except subprocess.TimeoutExpired:
            return web.json_response({
                'status': 'error',
                'message': 'Timeout durante il controllo degli aggiornamenti'
            }, status=500)
        except Exception as e:
            return self.error_handler.handle_api_error(e, "checking updates", "Error checking for updates")

    async def handle_run_update(self, request):
        """Esegue l'aggiornamento in un processo separato che sopravvive alla chiusura della GUI"""
        try:
            import subprocess
            import os

            update_script = Path('update.sh')
            if not update_script.exists():
                return web.json_response({
                    'status': 'error',
                    'message': 'Script update.sh non trovato'
                }, status=404)

            self.logger.info("[GUI] 🚀 Avvio aggiornamento in processo separato...")

            # Usa 'at now' per eseguire update.sh in un processo completamente separato
            # che continua anche se la GUI viene chiusa
            # L'input 'y\n' conferma automaticamente il prompt di update.sh

            try:
                import platform
                log_file = os.path.join(os.getcwd(), 'logs', 'update_gui.log')

                if platform.system() == 'Windows':
                    # Windows: usa Task Scheduler per eseguire update in background
                    script_content = f"""
@echo off
cd /d {os.getcwd()}
echo === Update avviato da GUI === > {log_file}
date /t >> {log_file}
time /t >> {log_file}
powershell -NoProfile -Command "bash update.sh" >> {log_file} 2>&1
echo === Update completato === >> {log_file}
date /t >> {log_file}
time /t >> {log_file}
"""
                    script_path = os.path.join(os.getcwd(), '.update_gui.bat')
                    with open(script_path, 'w') as f:
                        f.write(script_content)

                    # Esegui con Task Scheduler
                    result = subprocess.run(
                        [
                            'schtasks', '/Create',
                            '/TN', 'SolarEdgeUpdate',
                            '/TR', script_path,
                            '/SC', 'ONCE',
                            '/ST', '00:00',
                            '/F'
                        ],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )

                    if result.returncode == 0:
                        # Esegui subito il task
                        subprocess.run(['schtasks', '/Run', '/TN', 'SolarEdgeUpdate'], timeout=5)
                        self.logger.info(f"[GUI] ✅ Update avviato con Task Scheduler - Log: {log_file}")
                    else:
                        raise Exception(f"Task Scheduler failed: {result.stderr}")

                else:
                    # Linux: usa systemd-run
                    result = subprocess.run(
                        [
                            'systemd-run',
                            '--unit=solaredge-update',
                            '--description=SolarEdge Update from GUI',
                            f'--working-directory={os.getcwd()}',
                            'bash', '-c',
                            f'./update.sh > {log_file} 2>&1'
                        ],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )

                    if result.returncode == 0:
                        self.logger.info(f"[GUI] ✅ Update avviato come servizio systemd - Log: {log_file}")
                    else:
                        self.logger.error(f"[GUI] ❌ Errore systemd-run: {result.stderr}")
                        raise Exception(f"systemd-run failed: {result.stderr}")

                return web.json_response({
                    'status': 'success',
                    'message': 'Aggiornamento avviato! Il servizio si riavvierà automaticamente. La GUI si riconnetterà tra circa 30 secondi.'
                })

            except Exception as e:
                self.logger.error(f"[GUI] ❌ Errore avvio update: {e}")
                return web.json_response({
                    'status': 'error',
                    'message': f'Errore durante l\'avvio dell\'aggiornamento: {str(e)}'
                }, status=500)

        except Exception as e:
            self.logger.error(f"[GUI] ❌ Errore: {e}", exc_info=True)
            return self.error_handler.handle_api_error(e, "running update", "Error running update")

    async def handle_get_update_status(self, request):
        """Restituisce lo stato attuale degli aggiornamenti"""
        try:
            return web.json_response({
                'updates_available': getattr(self.state_manager, 'updates_available', False),
                'last_check': getattr(self.state_manager, 'last_update_check', None),
                'last_check_str': self.state_manager.last_update_check.strftime('%H:%M:%S') if getattr(self.state_manager, 'last_update_check', None) else 'Mai'
            })
        except Exception as e:
            return self.error_handler.handle_api_error(e, "getting update status", "Error getting update status")

    def _setup_log_capture(self):
        """Setup log capture per la GUI con identificazione flow"""
        import logging

        gui_handler = self._create_gui_log_handler()
        gui_handler.setLevel(logging.INFO)

        loggers_to_capture = [
            'main', 'SimpleWebGUI', 'collector', 'parser',
            'storage', 'scheduler', 'cache_manager'
        ]
        for logger_name in loggers_to_capture:
            logger = logging.getLogger(logger_name)
            logger.addHandler(gui_handler)

    def _create_gui_log_handler(self):
        """Create and configure GUI log handler"""
        import logging
        from datetime import datetime
        import re

        class GUILogHandler(logging.Handler):
            def __init__(self, gui_instance):
                super().__init__()
                self.gui = gui_instance
                self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                self.flow_stack = []  # Stack per tracking flow annidati

            def emit(self, record):
                try:
                    message = self.ansi_escape.sub('', record.getMessage())

                    # Filtra messaggi di orchestrazione [GUI] - non mostrarli nella GUI
                    if message.startswith('[GUI]'):
                        return

                    # Parse SYSTEM markers [SYSTEM]
                    if '[SYSTEM]' in message:
                        # Remove [SYSTEM] prefix and route to sistema tab
                        clean_message = message.replace('[SYSTEM]', '').strip()
                        self.gui.state_manager.add_log_entry(
                            level=record.levelname,
                            message=clean_message,
                            flow_type='sistema',
                            timestamp=datetime.now()
                        )
                        return

                    # Parse flow markers [FLOW:TYPE:ACTION]
                    if '[FLOW:' in message:
                        parts = message.split('[FLOW:')[1].split(']')[0].split(':')
                        flow_type = parts[0].lower()
                        action = parts[1]

                        if action == 'START':
                            self.flow_stack.append(flow_type)
                            return  # Non mostrare START
                        elif action == 'STOP' and self.flow_stack:
                            self.flow_stack.pop()
                            return  # Non mostrare STOP
                        elif action == 'COMPLETION':
                            # Messaggi di completamento: rimuovi marker e mostra nel flow corretto
                            clean_message = message.split(']', 1)[1] if ']' in message else message
                            self.gui.state_manager.add_log_entry(
                                level=record.levelname,
                                message=clean_message,
                                flow_type=flow_type,
                                timestamp=datetime.now()
                            )
                            return

                    # Determina flow corrente dallo stack
                    current_flow = self.flow_stack[-1] if self.flow_stack else 'general'

                    self.gui.state_manager.add_log_entry(
                        level=record.levelname,
                        message=message,
                        flow_type=current_flow,
                        timestamp=datetime.now()
                    )
                except Exception:
                    pass

        return GUILogHandler(self)

    async def _run_existing_loop(self, cache, config):
        """Avvia il loop esistente di main.py in modalità asincrona"""
        self.logger.info("[GUI] 🔄 Avvio loop personalizzato per GUI")

        # Aggiorna statistiche per il nuovo loop
        from datetime import datetime
        self.state_manager.loop_stats['start_time'] = datetime.now()
        self.state_manager.loop_stats['status'] = 'running'
        self.state_manager.loop_stats['last_api_web_run'] = datetime.min

        # Usa il loop personalizzato che aggiorna le statistiche della GUI
        from datetime import datetime, timedelta
        from main import run_api_flow, run_web_flow, run_realtime_flow
        from app_logging import get_logger
        import asyncio

        log = get_logger("main")

        # Timestamp per tracking esecuzioni
        last_api_web_run = datetime.min

        # Leggi intervalli dal file .env (stessi del main.py)
        import os
        api_mins = int(os.getenv('LOOP_API_INTERVAL_MINUTES', '15'))
        web_mins = int(os.getenv('LOOP_WEB_INTERVAL_MINUTES', '15'))
        realtime_secs = int(os.getenv('LOOP_REALTIME_INTERVAL_SECONDS', '5'))
        gme_mins = int(os.getenv('LOOP_GME_INTERVAL_MINUTES', '1440'))

        api_web_interval = timedelta(minutes=max(api_mins, web_mins))
        realtime_interval = timedelta(seconds=realtime_secs)
        gme_interval = timedelta(minutes=gme_mins)
        last_realtime_run = datetime.min
        # Initialize GME to trigger immediately on first loop iteration
        # GME uses cache, so it's safe to run at startup
        last_gme_run = datetime.min

        # Controlla quali flow sono abilitati nella configurazione
        # Carica i file sources separatamente perché non sono nel config principale
        from pathlib import Path

        # Carica stato enabled dai file, ma verifica anche se ci sono endpoint attivi
        def load_source_enabled_with_check(file_path, key):
            try:
                if Path(file_path).exists():
                    data = load_yaml(file_path, substitute_env=True, use_cache=True)

                    source_enabled = data.get(key, {}).get('enabled', False)

                    # Se il source è enabled, verifica che ci sia almeno un endpoint abilitato
                    if source_enabled:
                        endpoints = data.get(key, {}).get('endpoints', {})
                        has_enabled = any(
                            ep.get('enabled', False)
                            for ep in endpoints.values()
                            if isinstance(ep, dict)
                        )

                        # Se non ci sono endpoint abilitati, considera il source come disabilitato
                        if not has_enabled:
                            self.logger.warning(f"[GUI] ⚠️ {key} è enabled ma non ha endpoint attivi - considerato disabilitato")
                            return False

                    return source_enabled
            except Exception as e:
                self.logger.error(f"[GUI] Errore caricamento {file_path}: {e}")
            return False

        api_enabled = load_source_enabled_with_check('config/sources/api_endpoints.yaml', 'api_ufficiali')
        web_enabled = load_source_enabled_with_check('config/sources/web_endpoints.yaml', 'web_scraping')
        modbus_enabled = load_source_enabled_with_check('config/sources/modbus_endpoints.yaml', 'modbus')
        gme_enabled = os.getenv('GME_ENABLED', 'false').lower() == 'true'

        # Log configurazione dettagliata per ogni flow
        status_parts = []

        # API
        if api_enabled:
            status_parts.append(f"API: {api_mins} min")
        else:
            status_parts.append("API: DISABILITATO")

        # Web
        if web_enabled:
            status_parts.append(f"Web: {web_mins} min")
        else:
            status_parts.append("Web: DISABILITATO")

        # Realtime
        if modbus_enabled:
            status_parts.append(f"Realtime: {realtime_secs} sec")
        else:
            status_parts.append("Realtime: DISABILITATO")

        # GME
        if gme_enabled:
            status_parts.append(f"GME: {gme_mins} min")
        else:
            status_parts.append("GME: DISABILITATO")

        self.logger.info(f"[GUI] Intervalli configurati - {', '.join(status_parts)}")

        # Log dettagliato per flow disabilitati
        if not api_enabled:
            self.logger.info("[GUI] ℹ️ API disabilitato nella configurazione, API flow non verrà eseguito")
        if not web_enabled:
            self.logger.info("[GUI] ℹ️ Web scraping disabilitato nella configurazione, Web flow non verrà eseguito")
        if not modbus_enabled:
            self.logger.info("[GUI] ℹ️ Modbus disabilitato nella configurazione, Realtime flow non verrà eseguito")
        if not gme_enabled:
            self.logger.info("[GUI] ℹ️ GME disabilitato nella configurazione, GME flow non verrà eseguito")

        try:
            while self.state_manager.loop_running and not self.state_manager.stop_requested:
                current_time = datetime.now()

                # Calcola tempo fino alla prossima operazione
                time_until_api_web = (last_api_web_run + api_web_interval - current_time).total_seconds()
                time_until_realtime = (last_realtime_run + realtime_interval - current_time).total_seconds()
                time_until_gme = (last_gme_run + gme_interval - current_time).total_seconds()

                # Debug logging per GME (solo se abilitato e vicino all'esecuzione)
                if gme_enabled and time_until_gme < 60:
                    self.logger.debug(f"[GME DEBUG] time_until_gme={time_until_gme:.1f}s, last_run={last_gme_run}, interval={gme_interval}")

                # Esegui API e Web ogni intervallo configurato (solo se almeno uno è abilitato)
                if (api_enabled or web_enabled) and time_until_api_web <= 0:
                    self.logger.info("[GUI] 🌐 Esecuzione raccolta API/Web...")

                    # Esegui Web flow solo se abilitato (in thread separato per non bloccare GUI)
                    if web_enabled:
                        self.state_manager.loop_stats['web_stats']['executed'] += 1
                        try:
                            await asyncio.get_event_loop().run_in_executor(
                                None, run_web_flow, log, cache, config
                            )
                            self.state_manager.loop_stats['web_stats']['success'] += 1
                            log.info("[FLOW:WEB:COMPLETION]✅ Raccolta web completata")
                        except Exception as e:
                            self.state_manager.loop_stats['web_stats']['failed'] += 1
                            self.logger.error(f"[GUI] ❌ Errore raccolta web: {e}")

                    # Esegui API flow solo se abilitato (in thread separato per non bloccare GUI)
                    if api_enabled:
                        self.state_manager.loop_stats['api_stats']['executed'] += 1
                        try:
                            await asyncio.get_event_loop().run_in_executor(
                                None, run_api_flow, log, cache, config
                            )
                            self.state_manager.loop_stats['api_stats']['success'] += 1
                            log.info("[FLOW:API:COMPLETION]✅ Raccolta API completata")
                        except Exception as e:
                            self.state_manager.loop_stats['api_stats']['failed'] += 1
                            self.logger.error(f"[GUI] ❌ Errore raccolta API: {e}")

                    last_api_web_run = current_time
                    self.state_manager.loop_stats['last_api_web_run'] = current_time
                    self.state_manager.loop_stats['last_update'] = current_time

                    # Calcola next run per API/Web
                    next_api_web_run = current_time + api_web_interval
                    self.state_manager.loop_stats['next_api_web_run'] = next_api_web_run

                    # Ricalcola tempi dopo l'esecuzione
                    time_until_api_web = api_web_interval.total_seconds()
                    time_until_realtime = (last_realtime_run + realtime_interval - datetime.now()).total_seconds()
                elif not api_enabled and not web_enabled:
                    # Se entrambi disabilitati, non calcolare time_until_api_web
                    time_until_api_web = 999999

                # Esegui Realtime solo se Modbus è abilitato
                if modbus_enabled and time_until_realtime <= 0:
                    self.state_manager.loop_stats['realtime_stats']['executed'] += 1
                    try:
                        # Esegui in thread separato per evitare blocco su timeout Modbus
                        result = await asyncio.get_event_loop().run_in_executor(
                            None, run_realtime_flow, log, cache, config
                        )
                        # result == 0 significa successo
                        if result == 0:
                            self.state_manager.loop_stats['realtime_stats']['success'] += 1
                            log.info("[FLOW:REALTIME:COMPLETION]✅ Raccolta realtime completata")
                        else:
                            self.state_manager.loop_stats['realtime_stats']['failed'] += 1
                    except Exception as e:
                        self.state_manager.loop_stats['realtime_stats']['failed'] += 1
                        self.logger.error(f"[GUI] ❌ Errore raccolta realtime: {e}")

                    last_realtime_run = datetime.now()
                    self.state_manager.loop_stats['last_update'] = datetime.now()

                    # Ricalcola tempo dopo l'esecuzione
                    time_until_realtime = realtime_interval.total_seconds()
                elif not modbus_enabled:
                    # Se Modbus disabilitato, non calcolare time_until_realtime
                    # Imposta a un valore alto per non influenzare il next_wake
                    time_until_realtime = 999999

                # Esegui GME solo se abilitato
                if gme_enabled and time_until_gme <= 0:
                    from main import run_gme_flow
                    self.logger.info(f"[GUI] 🔋 Esecuzione raccolta GME... (last_run: {last_gme_run}, interval: {gme_interval}, time_until: {time_until_gme:.1f}s)")
                    self.state_manager.loop_stats['gme_stats']['executed'] += 1
                    try:
                        await asyncio.get_event_loop().run_in_executor(
                            None, run_gme_flow, log, cache, config
                        )
                        self.state_manager.loop_stats['gme_stats']['success'] += 1
                        log.info("[FLOW:GME:COMPLETION]✅ Raccolta GME completata")
                    except Exception as e:
                        self.state_manager.loop_stats['gme_stats']['failed'] += 1
                        self.logger.error(f"[GUI] ❌ Errore raccolta GME: {e}")

                    last_gme_run = current_time
                    self.state_manager.loop_stats['last_gme_run'] = current_time
                    self.state_manager.loop_stats['last_update'] = current_time

                    # Calcola next run per GME
                    next_gme_run = current_time + gme_interval
                    self.state_manager.loop_stats['next_gme_run'] = next_gme_run

                    # Ricalcola tempi dopo l'esecuzione
                    time_until_gme = gme_interval.total_seconds()
                    time_until_api_web = (last_api_web_run + api_web_interval - datetime.now()).total_seconds()
                    self.logger.debug(f"[GUI] GME completato. Prossima esecuzione tra {time_until_gme/60:.1f} minuti")
                elif not gme_enabled:
                    # Se GME disabilitato, imposta a un valore alto
                    time_until_gme = 999999

                # Sleep intelligente: dormi fino alla prossima operazione (max 5 secondi per responsività)
                # Questo riduce drasticamente l'utilizzo CPU quando non ci sono operazioni da fare
                next_wake = min(max(time_until_api_web, 0), max(time_until_realtime, 0), max(time_until_gme, 0), 5.0)
                if next_wake > 0:
                    await asyncio.sleep(next_wake)
                else:
                    # Pausa minima per evitare busy-wait
                    await asyncio.sleep(0.1)

        except Exception as e:
            self.logger.error(f"[GUI] Errore nel loop: {e}")
            self.state_manager.loop_running = False
        finally:
            self.state_manager.loop_stats['status'] = 'stopped'
            self.state_manager.loop_mode = False  # Disabilita modalità loop
            self.logger.info("[GUI] Loop terminato")
