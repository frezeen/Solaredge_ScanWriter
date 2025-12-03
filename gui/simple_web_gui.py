#!/usr/bin/env python3
"""
SolarEdge ScanWriter - Modern Web GUI
Dashboard moderno per gestione device e API endpoints
"""

import asyncio
import json
import logging
import os
import socket
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from aiohttp import web

from app_logging.universal_logger import get_logger
from utils.yaml_loader import load_yaml, save_yaml

# Costanti
MAX_LOG_BUFFER = 1000
TCP_BACKLOG = 128
GIT_TIMEOUT_SECONDS = 10
DEFAULT_LOG_LIMIT = 2000
UPDATE_RECONNECT_DELAY_SECONDS = 30

class SimpleWebGUI:
    """Modern web GUI for SolarEdge ScanWriter dashboard."""

    def __init__(self, config_file: str = "config/main.yaml", port: Optional[int] = 8092,
                 cache=None, auto_start_loop: bool = False):
        """Initialize SimpleWebGUI.

        Args:
            config_file: Path to main configuration file
            port: Server port (default: 8092)
            cache: CacheManager instance (optional)
            auto_start_loop: Auto-start loop on server start
        """
        self.config_file = Path(config_file)
        self.logger = get_logger("SimpleWebGUI")
        self.real_ip = self._get_real_ip()
        self.app: Optional[web.Application] = None
        self.config: Dict[str, Any] = {}
        self.cache = cache
        self.auto_start_loop = auto_start_loop

        # Server configuration
        from gui.components.web_server import ServerConfig
        self.server_config = ServerConfig(
            host=os.getenv('GUI_HOST', '0.0.0.0'),
            port=port or int(os.getenv('GUI_PORT', 8092)),
            template_dir=Path("gui/templates"),
            static_dir=Path("gui/static")
        )
        self.port = self.server_config.port

        # Components (Single Responsibility)
        from gui.core.config_handler import ConfigHandler
        from gui.core.state_manager import StateManager
        from gui.core.unified_toggle_handler import UnifiedToggleHandler
        from gui.core.error_handler import UnifiedErrorHandler
        from gui.core.loop_executor import LoopExecutor

        self.config_handler = ConfigHandler()
        self.state_manager = StateManager(max_log_buffer=MAX_LOG_BUFFER)
        self.unified_toggle_handler = UnifiedToggleHandler()
        self.error_handler = UnifiedErrorHandler(self.logger)
        self.loop_executor = LoopExecutor(self.state_manager, self.logger, cache)

        # Setup log capture
        self._setup_log_capture()



    async def _auto_start_loop(self):
        """Avvia automaticamente il loop senza richiesta HTTP - Delega a LoopExecutor"""
        await self.loop_executor.auto_start()

    def _get_real_ip(self) -> str:
        """Ottiene l'IP reale della macchina.

        Returns:
            IP address string (fallback: 127.0.0.1)
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"

    async def load_config(self) -> Dict[str, Any]:
        """Carica la configurazione YAML dal main.yaml."""
        self.config = await self.config_handler.load_main_config(self.config_file)
        return self.config

    async def save_config(self) -> bool:
        """Salva la configurazione YAML principale."""
        return await self.config_handler.save_main_config(self.config_file, self.config)

    async def _load_source_config(self, source_type: str) -> Dict[str, Any]:
        """Carica configurazione sorgente (delega a ConfigHandler)."""
        return await self.config_handler.load_source_config(source_type)



    async def handle_index(self, request: web.Request) -> web.Response:
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

    async def handle_static(self, request: web.Request) -> web.Response:
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

    async def handle_favicon(self, request: web.Request) -> web.Response:
        """Serve favicon.ico if present, otherwise return 204 No Content."""
        from pathlib import Path
        favicon_path = Path('gui/static/favicon.png')
        if favicon_path.is_file():
            return web.FileResponse(path=favicon_path)
        # No favicon file – return an empty 204 response to silence the error
        return web.Response(status=204)

    async def handle_ping(self, request: web.Request) -> web.Response:
        """Endpoint di ping per verificare connessione"""
        return web.json_response({
            "status": "ok",
            "message": "SolarEdge Dashboard Online",
            "timestamp": asyncio.get_event_loop().time()
        })

    async def handle_get_config(self, request: web.Request) -> web.Response:
        """Restituisce la configurazione completa"""
        await self.load_config()
        return web.json_response(self.config)

    async def handle_get_yaml_file(self, request: web.Request) -> web.Response:
        """Restituisce il contenuto di un file di configurazione specifico"""
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

    async def handle_save_yaml_file(self, request: web.Request) -> web.Response:
        """Salva il contenuto di un file di configurazione specifico"""
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

    async def handle_get_sources(self, request: web.Request) -> web.Response:
        """Restituisce sorgenti unificate (web devices, api endpoints o modbus endpoints)"""
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

    async def handle_loop_status(self, request: web.Request) -> web.Response:
        """Restituisce lo stato del loop mode"""
        try:
            # Delega a StateManager (gestisce serializzazione datetime)
            status = self.state_manager.get_loop_status()
            # Add retention config for dynamic UI
            status['retention_config'] = self.state_manager.retention_config
            return web.json_response(status)

        except Exception as e:
            return self.error_handler.handle_api_error(e, "getting loop status", "Error retrieving loop status")
    async def handle_loop_logs(self, request: web.Request) -> web.Response:
        """Restituisce i log del loop mode con filtro opzionale per flow"""
        try:
            # Parametri query
            limit = int(request.query.get('limit', DEFAULT_LOG_LIMIT))
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



    async def handle_loop_start(self, request: web.Request) -> web.Response:
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

            # Avvia il loop asincrono personalizzato tramite LoopExecutor
            asyncio.create_task(self.loop_executor.run(self.cache, config))

            self.logger.info("[GUI] 🚀 Loop avviato con configurazione aggiornata")

            return self.error_handler.create_success_response("Loop avviato con configurazione ricaricata")
        except Exception as e:
            return self.error_handler.handle_api_error(e, "starting loop", "Error starting loop")

    async def handle_loop_stop(self, request: web.Request) -> web.Response:
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

    async def handle_clear_logs(self, request: web.Request) -> web.Response:
        """Pulisce i log e le run salvate"""
        try:
            self.logger.info("[GUI] Richiesta clear logs ricevuta")

            # Delega a StateManager
            self.state_manager.clear_logs()

            self.logger.info("[GUI] ✅ Log puliti con successo")

            return self.error_handler.create_success_response("Log puliti con successo")
        except Exception as e:
            return self.error_handler.handle_api_error(e, "clearing logs", "Error clearing logs")

    async def handle_log(self, request: web.Request) -> web.Response:
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

    def create_app(self) -> web.Application:
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

    async def start(self, host: Optional[str] = None, port: Optional[int] = None) -> Tuple[web.AppRunner, web.TCPSite]:
        """Metodo start per compatibilità con main.py"""
        # Usa configurazione da server_config o parametri forniti
        bind_host = host if host else self.server_config.host
        bind_port = port if port else self.server_config.port
        runner, site = await self.start_server(bind_host, bind_port)

        # Ritorna subito dopo aver avviato il server, senza loop infinito
        return runner, site

    async def start_server(self, host: str = '0.0.0.0', port: Optional[int] = None) -> Tuple[web.AppRunner, web.TCPSite]:
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
                    import os
                    sched = cm.get_scheduler_config()
                    
                    # Get loop intervals from environment
                    api_interval = int(os.getenv('LOOP_API_INTERVAL_MINUTES', '15'))
                    web_interval = int(os.getenv('LOOP_WEB_INTERVAL_MINUTES', '15'))
                    realtime_interval = int(os.getenv('LOOP_REALTIME_INTERVAL_SECONDS', '5'))
                    gme_interval = int(os.getenv('LOOP_GME_INTERVAL_MINUTES', '1440'))
                    
                    self.logger.info(
                        f"[SYSTEM] ⏱️  Scheduler Rate configurato (API: {sched.api_delay_seconds}s, "
                        f"Web: {sched.web_delay_seconds}s, Realtime: {sched.realtime_delay_seconds}s, GME: {sched.gme_delay_seconds}s)"
                    )
                    self.logger.info(
                        f"[SYSTEM] 🔄 Scheduler Loop configurato (API: {api_interval}min, Web: {web_interval}min, "
                        f"Realtime: {realtime_interval}s, GME: {gme_interval}min)"
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
                
                # Log settings info (dynamic from retention_config)
                all_hours = self.state_manager.retention_config['all_hours']
                flow_runs = self.state_manager.retention_config['flow_runs']
                self.logger.info(f"[SYSTEM] 📝 Log inizializzati (TUTTI: reset {all_hours}h, Flow: ultime {flow_runs} run, SISTEMA: mai resettati)")

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

    async def handle_toggle_endpoint(self, request: web.Request) -> web.Response:
        """Toggle API endpoint enabled/disabled state - Uses UnifiedToggleHandler"""
        try:
            endpoint_id = request.query.get('id')
            if not endpoint_id:
                return self.error_handler.handle_validation_error('endpoint ID', 'toggling endpoint')

            success, response_data = await self.unified_toggle_handler.handle_toggle_endpoint(endpoint_id)

            if not success:
                status = 404 if 'not found' in response_data.get('error', '').lower() else 400
                return web.json_response(response_data, status=status)

            return web.json_response(response_data)

        except Exception as e:
            return self.error_handler.handle_api_error(e, "toggling endpoint", "Error toggling endpoint")

    async def handle_toggle_device(self, request: web.Request) -> web.Response:
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

    async def handle_toggle_modbus_device(self, request: web.Request) -> web.Response:
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

    async def handle_toggle_device_metric(self, request: web.Request) -> web.Response:
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

    async def handle_toggle_modbus_metric(self, request: web.Request) -> web.Response:
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

    async def handle_toggle_gme(self, request: web.Request) -> web.Response:
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

    async def handle_check_updates(self, request: web.Request) -> web.Response:
        """Controlla se ci sono nuovi aggiornamenti disponibili"""
        try:
            from gui.services.git_service import GitService
            git_service = GitService()

            # Fetch updates
            success, error = await git_service.fetch_updates()
            if not success:
                return web.json_response({
                    'status': 'error',
                    'message': 'Errore durante il controllo degli aggiornamenti',
                    'error': error
                }, status=500)

            # Get commit diff
            success, local, remote, error = await git_service.get_commit_diff()
            if not success:
                return web.json_response({
                    'status': 'error',
                    'message': 'Errore durante il controllo degli aggiornamenti',
                    'error': error
                }, status=500)

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

        except Exception as e:
            return self.error_handler.handle_api_error(e, "checking updates", "Error checking for updates")

    async def handle_run_update(self, request: web.Request) -> web.Response:
        """Esegue l'aggiornamento in un processo separato che sopravvive alla chiusura della GUI"""
        try:
            from gui.services.update_service import UpdateService
            update_service = UpdateService()

            success, message = await update_service.run_update()

            if not success:
                return web.json_response({
                    'status': 'error',
                    'message': message
                }, status=404 if 'non trovato' in message else 500)

            return web.json_response({
                'status': 'success',
                'message': message
            })

        except Exception as e:
            return self.error_handler.handle_api_error(e, "running update", "Error running update")

    async def handle_get_update_status(self, request: web.Request) -> web.Response:
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
        from gui.services.log_handler import GUILogHandler

        gui_handler = GUILogHandler(self.state_manager)
        gui_handler.setLevel(logging.INFO)

        loggers_to_capture = [
            'main', 'SimpleWebGUI', 'collector', 'parser',
            'storage', 'scheduler', 'cache_manager'
        ]
        for logger_name in loggers_to_capture:
            logger = logging.getLogger(logger_name)
            logger.addHandler(gui_handler)

