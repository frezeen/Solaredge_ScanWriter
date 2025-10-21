#!/usr/bin/env python3
"""
SolarEdge ScanWriter - Modern Web GUI
Dashboard moderno per gestione device e API endpoints
"""

import asyncio
import json
import yaml
import socket
from pathlib import Path
from aiohttp import web
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from app_logging.universal_logger import get_logger

class SimpleWebGUI:
    def __init__(self, config_file="config/main.yaml", port=8092, cache=None, auto_start_loop=False):
        self.config_file = Path(config_file)
        self.port = port
        self.logger = get_logger("SimpleWebGUI")
        self.real_ip = self._get_real_ip()
        self.app = None
        self.config = {}
        self.cache = cache  # Cache manager condiviso
        self.auto_start_loop = auto_start_loop  # Flag per avvio automatico
        
        # Attributi per loop mode
        self.loop_mode = False
        self.loop_running = False  # Stato attuale del loop
        self.log_buffer = []  # Buffer per i log realtime
        self.max_log_buffer = 1000  # Massimo numero di log da tenere
        self.stop_requested = False  # Flag per richiesta di stop
        
        # Inizializza statistiche vuote
        from datetime import datetime
        self.loop_stats = {
            'api_stats': {'executed': 0, 'success': 0, 'failed': 0},
            'web_stats': {'executed': 0, 'success': 0, 'failed': 0},
            'realtime_stats': {'executed': 0, 'success': 0, 'failed': 0},
            'start_time': None,
            'last_api_web_run': None,
            'status': 'stopped'
        }
        
        # Setup log capture per la GUI
        self._setup_log_capture()

    async def _auto_start_loop(self):
        """Avvia automaticamente il loop senza richiesta HTTP"""
        try:
            if self.loop_running:
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
            
            # 4. Reset flag di stop e avvia il loop
            self.stop_requested = False
            self.loop_running = True
            self.loop_mode = True  # Abilita modalità loop
            
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
        
    async def load_config(self):
        """Carica la configurazione YAML dal main.yaml (senza sources)"""
        try:
            if self.config_file.exists():
                content = self.config_file.read_text(encoding='utf-8')
                
                # Sostituisci variabili d'ambiente come fa config_manager
                from config.config_manager import get_config_manager
                config_manager = get_config_manager()
                content = config_manager._substitute_env_vars(content)
                
                self.config = yaml.safe_load(content) or {}
            return self.config
        except Exception as e:
            self.logger.error(f"[GUI] Errore caricamento config: {e}")
            return {}

    async def save_config(self):
        """Salva la configurazione YAML principale"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"[GUI] Errore salvataggio config: {e}")
            return False

    def _get_web_devices(self):
        """Helper: ottiene dispositivi web scraping dal file separato"""
        try:
            web_file = Path("config/sources/web_endpoints.yaml")
            if web_file.exists():
                content = web_file.read_text(encoding='utf-8')
                # Sostituisci variabili d'ambiente
                from config.config_manager import get_config_manager
                config_manager = get_config_manager()
                content = config_manager._substitute_env_vars(content)
                web_data = yaml.safe_load(content) or {}
                return web_data.get('web_scraping', {}).get('endpoints', {})
        except Exception as e:
            self.logger.error(f"[GUI] Errore caricamento web endpoints: {e}")
        return {}

    def _get_api_endpoints(self):
        """Helper: ottiene endpoint API dal file separato"""
        try:
            api_file = Path("config/sources/api_endpoints.yaml")
            if api_file.exists():
                content = api_file.read_text(encoding='utf-8')
                # Sostituisci variabili d'ambiente
                from config.config_manager import get_config_manager
                config_manager = get_config_manager()
                content = config_manager._substitute_env_vars(content)
                api_data = yaml.safe_load(content) or {}
                return api_data.get('api_ufficiali', {}).get('endpoints', {})
        except Exception as e:
            self.logger.error(f"[GUI] Errore caricamento API endpoints: {e}")
        return {}

    def _get_modbus_endpoints(self):
        """Helper: ottiene endpoint Modbus dal file separato"""
        try:
            modbus_file = Path("config/sources/modbus_endpoints.yaml")
            if modbus_file.exists():
                content = modbus_file.read_text(encoding='utf-8')
                # Sostituisci variabili d'ambiente
                from config.config_manager import get_config_manager
                config_manager = get_config_manager()
                content = config_manager._substitute_env_vars(content)
                modbus_data = yaml.safe_load(content) or {}
                return modbus_data.get('modbus', {}).get('endpoints', {})
        except Exception as e:
            self.logger.error(f"[GUI] Errore caricamento Modbus endpoints: {e}")
        return {}

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
            self.logger.error(f"[GUI] Errore serving index: {e}")
            return web.Response(text=f"Errore: {e}", status=500)

    async def handle_static(self, request):
        """Serve i file statici"""
        try:
            filename = request.match_info['filename']
            static_path = Path(f"gui/static/{filename}")
            
            if static_path.exists():
                content = static_path.read_text(encoding='utf-8')
                
                # Determina content type
                if filename.endswith('.css'):
                    content_type = 'text/css'
                elif filename.endswith('.js'):
                    content_type = 'application/javascript'
                else:
                    content_type = 'text/plain'
                    
                return web.Response(text=content, content_type=content_type)
            else:
                return web.Response(text="File non trovato", status=404)
        except Exception as e:
            self.logger.error(f"[GUI] Errore serving static {filename}: {e}")
            return web.Response(text=f"Errore: {e}", status=500)

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
        """Restituisce il contenuto di un file di configurazione specifico"""
        try:
            file_type = request.query.get('file', 'main')
            
            # Mappa dei file di configurazione disponibili
            config_files = {
                'main': 'config/main.yaml',
                'web_endpoints': 'config/sources/web_endpoints.yaml',
                'api_endpoints': 'config/sources/api_endpoints.yaml',
                'modbus_endpoints': 'config/sources/modbus_endpoints.yaml',
                'env': '.env'
            }
            
            if file_type not in config_files:
                return web.json_response({'error': f'File di configurazione non valido: {file_type}'}, status=400)
            
            file_path = Path(config_files[file_type])
            if not file_path.exists():
                return web.json_response({'error': f'File non trovato: {file_path}'}, status=404)
            
            content = file_path.read_text(encoding='utf-8')
            
            return web.json_response({
                'file': file_type,
                'path': str(file_path),
                'content': content
            })
            
        except Exception as e:
            self.logger.error(f"[GUI] Errore get YAML file: {e}")
            return web.json_response({'error': f'Errore interno: {str(e)}'}, status=500)

    async def handle_save_yaml_file(self, request):
        """Salva il contenuto di un file di configurazione specifico"""
        try:
            data = await request.json()
            file_type = data.get('file', 'main')
            content = data.get('content', '')
            
            # Mappa dei file di configurazione disponibili
            config_files = {
                'main': 'config/main.yaml',
                'web_endpoints': 'config/sources/web_endpoints.yaml',
                'api_endpoints': 'config/sources/api_endpoints.yaml',
                'modbus_endpoints': 'config/sources/modbus_endpoints.yaml',
                'env': '.env'
            }
            
            if file_type not in config_files:
                return web.json_response({'error': f'File di configurazione non valido: {file_type}'}, status=400)
            
            # Valida il contenuto prima di salvare (solo per file YAML)
            if file_type != 'env':
                try:
                    yaml.safe_load(content)
                except yaml.YAMLError as e:
                    return web.json_response({'error': f'YAML non valido: {str(e)}'}, status=400)
            
            file_path = Path(config_files[file_type])
            
            # Crea la directory se non esiste
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Salva il file
            file_path.write_text(content, encoding='utf-8')
            
            self.logger.info(f"[GUI] Salvato file YAML: {file_path}")
            
            return web.json_response({
                'success': True,
                'file': file_type,
                'path': str(file_path),
                'message': f'File {file_type} salvato con successo'
            })
            
        except Exception as e:
            self.logger.error(f"[GUI] Errore save YAML file: {e}")
            return web.json_response({'error': f'Errore interno: {str(e)}'}, status=500)

    async def handle_get_sources(self, request):
        """Restituisce sorgenti unificate (web devices, api endpoints o modbus endpoints)"""
        try:
            source_type = request.query.get('type', 'web')  # 'web', 'api' o 'modbus'
            
            await self.load_config()
            
            if source_type == 'web':
                sources = self._get_web_devices()
            elif source_type == 'api':
                sources = self._get_api_endpoints()
            elif source_type == 'modbus':
                sources = self._get_modbus_endpoints()
            else:
                return web.json_response({"error": "Tipo sorgente non valido"}, status=400)
            
            return web.json_response(sources)
            
        except Exception as e:
            self.logger.error(f"[GUI] Errore get sources: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_loop_status(self, request):
        """Restituisce lo stato del loop mode"""
        try:
            if not self.loop_mode:
                return web.json_response({
                    "loop_mode": False,
                    "message": "GUI in modalità standalone"
                })
            
            # Calcola statistiche aggiornate
            stats = self.loop_stats.copy()
            if 'start_time' in stats and stats['start_time']:
                stats['uptime_seconds'] = (datetime.now() - stats['start_time']).total_seconds()
                stats['uptime_formatted'] = str(datetime.now() - stats['start_time']).split('.')[0]
                # Rimuovi l'oggetto datetime per la serializzazione JSON
                del stats['start_time']
            
            if 'last_update' in stats and stats['last_update']:
                stats['last_update_formatted'] = stats['last_update'].strftime('%H:%M:%S')
                del stats['last_update']
            
            if 'last_api_web_run' in stats and stats['last_api_web_run']:
                if hasattr(stats['last_api_web_run'], 'strftime'):
                    stats['api_last_run'] = stats['last_api_web_run'].strftime('%H:%M:%S')
                    stats['web_last_run'] = stats['last_api_web_run'].strftime('%H:%M:%S')
                del stats['last_api_web_run']
            
            if 'next_api_web_run' in stats and stats['next_api_web_run']:
                if hasattr(stats['next_api_web_run'], 'strftime'):
                    stats['api_next_run'] = stats['next_api_web_run'].strftime('%H:%M:%S')
                    stats['web_next_run'] = stats['next_api_web_run'].strftime('%H:%M:%S')
                del stats['next_api_web_run']
            
            # Rimuovi tutti gli oggetti datetime e timedelta rimanenti
            for key in list(stats.keys()):
                if hasattr(stats[key], 'strftime') or hasattr(stats[key], 'total_seconds'):  # È un datetime o timedelta
                    del stats[key]
            
            return web.json_response({
                "loop_mode": self.loop_running,
                "stats": stats
            })
            
        except Exception as e:
            self.logger.error(f"[GUI] Errore loop status: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_loop_logs(self, request):
        """Restituisce i log del loop mode"""
        try:
            # Parametri query per paginazione
            limit = int(request.query.get('limit', 100))
            offset = int(request.query.get('offset', 0))
            
            # Restituisci gli ultimi log
            logs = self.log_buffer[-limit-offset:-offset] if offset > 0 else self.log_buffer[-limit:]
            
            return web.json_response({
                "logs": logs,
                "total": len(self.log_buffer),
                "limit": limit,
                "offset": offset
            })
            
        except Exception as e:
            self.logger.error(f"[GUI] Errore loop logs: {e}")
            return web.json_response({"error": str(e)}, status=500)

    def add_log_entry(self, level, message, timestamp=None):
        """Aggiunge un entry al buffer dei log"""
        if timestamp is None:
            timestamp = datetime.now()
        
        log_entry = {
            "timestamp": timestamp.strftime('%H:%M:%S'),
            "level": level,
            "message": message
        }
        
        self.log_buffer.append(log_entry)
        
        # Mantieni solo gli ultimi N log
        if len(self.log_buffer) > self.max_log_buffer:
            self.log_buffer = self.log_buffer[-self.max_log_buffer:]

    async def handle_loop_start(self, request):
        """Avvia il loop mode con ricaricamento configurazione"""
        try:
            if self.loop_running:
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
            self.stop_requested = False
            self.loop_running = True
            self.loop_mode = True  # Abilita modalità loop
            
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
            
            return web.json_response({
                "status": "success",
                "message": "Loop avviato con configurazione ricaricata"
            })
        except Exception as e:
            self.logger.error(f"[GUI] Errore loop start: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_loop_stop(self, request):
        """Ferma il loop mode (senza chiudere la GUI)"""
        try:
            self.logger.info("[GUI] Richiesta stop loop ricevuta")
            
            # Imposta il flag per fermare il loop
            self.stop_requested = True
            self.loop_running = False
            self.loop_mode = False  # Disabilita modalità loop
            
            # Aggiorna statistiche
            self.loop_stats['status'] = 'stopped'
            
            self.logger.info("[GUI] ✅ Loop fermato con successo")
            
            return web.json_response({
                "status": "success", 
                "message": "Loop fermato con successo"
            })
        except Exception as e:
            self.logger.error(f"[GUI] Errore loop stop: {e}")
            return web.json_response({"error": str(e)}, status=500)

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
            self.logger.error(f"[GUI] Errore nell'endpoint log: {e}")
            return web.json_response({"error": str(e)}, status=500)

    def create_app(self):
        """Crea l'applicazione web"""
        self.app = web.Application()

        # Routes
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/static/{filename}', self.handle_static)
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
        
        # Endpoint configuration routes
        self.app.router.add_post('/api/endpoints/toggle', self.handle_toggle_endpoint)
        self.app.router.add_post('/api/devices/toggle', self.handle_toggle_device)
        self.app.router.add_post('/api/devices/metrics/toggle', self.handle_toggle_device_metric)
        self.app.router.add_post('/api/modbus/devices/toggle', self.handle_toggle_modbus_device)
        self.app.router.add_post('/api/modbus/devices/metrics/toggle', self.handle_toggle_modbus_metric)
        
        self.app.router.add_post('/api/log', self.handle_log)

        return self.app

    async def start(self, host=None, port=None):
        """Metodo start per compatibilità con main.py"""
        if port:
            self.port = port
        # Usa host fornito o default a 0.0.0.0 per accesso remoto
        bind_host = host if host else '0.0.0.0'
        runner, site = await self.start_server(bind_host)
        
        # Ritorna subito dopo aver avviato il server, senza loop infinito
        return runner, site

    async def start_server(self, host='0.0.0.0'):
        """Avvia il server web"""
        try:
            await self.load_config()
            
            self.logger.info("[GUI] Avvio GUI Web...")
            
            # Configura logging aiohttp per ridurre verbosità
            import logging
            aiohttp_logger = logging.getLogger('aiohttp.access')
            aiohttp_logger.setLevel(logging.WARNING)
            
            runner = web.AppRunner(self.create_app())
            await runner.setup()
            site = web.TCPSite(runner, host, self.port)
            await site.start()
            
            self.logger.info(f"[GUI] Uso porta {self.port}")
            self.logger.info(f"[GUI] GUI Web avviata su: http://{self.real_ip}:{self.port}")
            
            self.logger.info("="*50)
            self.logger.info("🚀 SOLAREDGE DASHBOARD MODERNA")
            self.logger.info(f"URL: http://{self.real_ip}:{self.port}")
            self.logger.info(f"Config: {self.config_file}")
            self.logger.info("Premi Ctrl+C per fermare")
            self.logger.info("="*50)
            
            # Avvia automaticamente il loop se richiesto
            if self.auto_start_loop:
                self.logger.info("[GUI] 🚀 Avvio automatico del loop...")
                await self._auto_start_loop()
            
            return runner, site
                
        except Exception as e:
            self.logger.error(f"[GUI] Errore avvio server: {e}")
            raise  
    
    async def handle_toggle_endpoint(self, request):
        """Toggle endpoint enabled/disabled state"""
        try:
            # Get endpoint ID from query parameters
            endpoint_id = request.query.get('id')
            if not endpoint_id:
                return web.json_response({'error': 'Missing endpoint ID'}, status=400)
            
            # Parse endpoint ID to determine source file and path
            # Format: "api_ufficiali.site_overview" or simple "site_overview" for API endpoints
            parts = endpoint_id.split('.')
            if len(parts) >= 2:
                source_type = parts[0]  # api_ufficiali, web, modbus
                endpoint_name = parts[1]  # site_overview, measurements, etc.
            else:
                # For simple endpoint names (like from API tab), assume it's an API endpoint
                source_type = 'api_ufficiali'
                endpoint_name = endpoint_id
            
            # Map source type to config file
            config_files = {
                'api_ufficiali': 'config/sources/api_endpoints.yaml',
                'web': 'config/sources/web_endpoints.yaml', 
                'modbus': 'config/sources/modbus_endpoints.yaml'
            }
            
            config_file = config_files.get(source_type)
            if not config_file:
                return web.json_response({'error': f'Unknown source type: {source_type}'}, status=400)
            
            # Load current configuration
            import yaml
            from pathlib import Path
            
            config_path = Path(config_file)
            if not config_path.exists():
                return web.json_response({'error': f'Config file not found: {config_file}'}, status=404)
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # Navigate to the endpoint and toggle its enabled state
            if source_type in config and 'endpoints' in config[source_type]:
                endpoints = config[source_type]['endpoints']
                if endpoint_name in endpoints:
                    # Toggle the enabled state
                    current_state = endpoints[endpoint_name].get('enabled', False)
                    new_state = not current_state
                    endpoints[endpoint_name]['enabled'] = new_state
                    
                    # Save the updated configuration
                    with open(config_path, 'w', encoding='utf-8') as f:
                        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)
                    
                    self.logger.info(f"Toggled endpoint {endpoint_id}: {current_state} -> {new_state}")
                    
                    return web.json_response({
                        'success': True,
                        'endpoint_id': endpoint_id,
                        'enabled': new_state,
                        'message': f'Endpoint {endpoint_id} {"enabled" if new_state else "disabled"}'
                    })
                else:
                    return web.json_response({'error': f'Endpoint not found: {endpoint_name}'}, status=404)
            else:
                return web.json_response({'error': f'Invalid config structure in {config_file}'}, status=500)
                
        except Exception as e:
            self.logger.error(f"Error toggling endpoint: {e}")
            return web.json_response({'error': f'Internal server error: {str(e)}'}, status=500)
    
    async def handle_toggle_device(self, request):
        """Toggle web device enabled/disabled state"""
        try:
            # Get device ID from query parameters
            device_id = request.query.get('id')
            if not device_id:
                return web.json_response({'error': 'Missing device ID'}, status=400)
            
            # Load web endpoints configuration
            import yaml
            from pathlib import Path
            
            config_file = 'config/sources/web_endpoints.yaml'
            config_path = Path(config_file)
            if not config_path.exists():
                return web.json_response({'error': f'Config file not found: {config_file}'}, status=404)
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # Navigate to the device and toggle its enabled state
            if 'web_scraping' in config and 'endpoints' in config['web_scraping']:
                devices = config['web_scraping']['endpoints']
                if device_id in devices:
                    # Toggle the enabled state
                    current_state = devices[device_id].get('enabled', False)
                    new_state = not current_state
                    devices[device_id]['enabled'] = new_state
                    
                    # Cascade toggle to all metrics of this device
                    metrics_updated = 0
                    updated_measurements = {}
                    if 'measurements' in devices[device_id]:
                        for metric_name, metric_config in devices[device_id]['measurements'].items():
                            if isinstance(metric_config, dict):
                                metric_config['enabled'] = new_state
                                updated_measurements[metric_name] = {'enabled': new_state}
                                metrics_updated += 1
                    
                    # Save the updated configuration
                    with open(config_path, 'w', encoding='utf-8') as f:
                        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)
                    
                    self.logger.info(f"Toggled web device {device_id}: {current_state} -> {new_state} (cascaded to {metrics_updated} metrics)")
                    
                    return web.json_response({
                        'success': True,
                        'device_id': device_id,
                        'enabled': new_state,
                        'measurements': updated_measurements,
                        'metrics_updated': metrics_updated,
                        'message': f'Device {device_id} {"enabled" if new_state else "disabled"} (with {metrics_updated} metrics)'
                    })
                else:
                    return web.json_response({'error': f'Device not found: {device_id}'}, status=404)
            else:
                return web.json_response({'error': f'Invalid config structure in {config_file}'}, status=500)
                
        except Exception as e:
            self.logger.error(f"Error toggling web device: {e}")
            return web.json_response({'error': f'Internal server error: {str(e)}'}, status=500)

    async def handle_toggle_modbus_device(self, request):
        """Toggle modbus device enabled/disabled state"""
        try:
            # Get device ID from query parameters
            device_id = request.query.get('id')
            if not device_id:
                return web.json_response({'error': 'Missing device ID'}, status=400)
            
            # Load modbus endpoints configuration
            import yaml
            from pathlib import Path
            
            config_file = 'config/sources/modbus_endpoints.yaml'
            config_path = Path(config_file)
            if not config_path.exists():
                return web.json_response({'error': f'Config file not found: {config_file}'}, status=404)
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # Navigate to the device and toggle its enabled state
            if 'modbus' in config and 'endpoints' in config['modbus']:
                devices = config['modbus']['endpoints']
                if device_id in devices:
                    # Toggle the enabled state
                    current_state = devices[device_id].get('enabled', False)
                    new_state = not current_state
                    devices[device_id]['enabled'] = new_state
                    
                    # Cascade toggle to all metrics of this device
                    metrics_updated = 0
                    updated_measurements = {}
                    if 'measurements' in devices[device_id]:
                        for metric_name, metric_config in devices[device_id]['measurements'].items():
                            if isinstance(metric_config, dict):
                                metric_config['enabled'] = new_state
                                updated_measurements[metric_name] = {'enabled': new_state}
                                metrics_updated += 1
                    
                    # Save the updated configuration
                    with open(config_path, 'w', encoding='utf-8') as f:
                        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)
                    
                    self.logger.info(f"Toggled modbus device {device_id}: {current_state} -> {new_state} (cascaded to {metrics_updated} metrics)")
                    
                    return web.json_response({
                        'success': True,
                        'device_id': device_id,
                        'enabled': new_state,
                        'measurements': updated_measurements,
                        'metrics_updated': metrics_updated,
                        'message': f'Modbus device {device_id} {"enabled" if new_state else "disabled"} (with {metrics_updated} metrics)'
                    })
                else:
                    return web.json_response({'error': f'Modbus device not found: {device_id}'}, status=404)
            else:
                return web.json_response({'error': f'Invalid config structure in {config_file}'}, status=500)
                
        except Exception as e:
            self.logger.error(f"Error toggling modbus device: {e}")
            return web.json_response({'error': f'Internal server error: {str(e)}'}, status=500)
    
    async def handle_toggle_device_metric(self, request):
        """Toggle web device metric enabled/disabled state"""
        try:
            # Get device ID and metric from query parameters
            device_id = request.query.get('id')
            metric = request.query.get('metric')
            if not device_id or not metric:
                return web.json_response({'error': 'Missing device ID or metric'}, status=400)
            
            # Load web endpoints configuration
            import yaml
            from pathlib import Path
            
            config_file = 'config/sources/web_endpoints.yaml'
            config_path = Path(config_file)
            if not config_path.exists():
                return web.json_response({'error': f'Config file not found: {config_file}'}, status=404)
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # Navigate to the device metric and toggle its enabled state
            if 'web_scraping' in config and 'endpoints' in config['web_scraping']:
                devices = config['web_scraping']['endpoints']
                if device_id in devices and 'measurements' in devices[device_id]:
                    measurements = devices[device_id]['measurements']
                    if metric in measurements:
                        # Toggle the enabled state
                        current_state = measurements[metric].get('enabled', False)
                        new_state = not current_state
                        measurements[metric]['enabled'] = new_state
                        
                        # Smart device auto-toggle logic
                        device_current_state = devices[device_id].get('enabled', False)
                        device_new_state = device_current_state
                        device_changed = False
                        
                        if new_state and not device_current_state:
                            # Case 1: Enabling a metric when device is OFF -> enable device
                            devices[device_id]['enabled'] = True
                            device_new_state = True
                            device_changed = True
                            self.logger.info(f"Auto-enabled device {device_id} because metric {metric} was enabled")
                        elif not new_state and device_current_state:
                            # Case 2: Disabling a metric when device is ON -> check if it's the last enabled metric
                            enabled_metrics = [m for m, cfg in measurements.items() if cfg.get('enabled', False)]
                            if len(enabled_metrics) == 0:  # No metrics left enabled
                                devices[device_id]['enabled'] = False
                                device_new_state = False
                                device_changed = True
                                self.logger.info(f"Auto-disabled device {device_id} because no metrics are enabled")
                        
                        # Save the updated configuration
                        with open(config_path, 'w', encoding='utf-8') as f:
                            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)
                        
                        self.logger.info(f"Toggled web device metric {device_id}.{metric}: {current_state} -> {new_state}")
                        
                        response_data = {
                            'success': True,
                            'device_id': device_id,
                            'metric': metric,
                            'enabled': new_state,
                            'device_enabled': device_new_state,
                            'device_changed': device_changed,
                            'message': f'Metric {device_id}.{metric} {"enabled" if new_state else "disabled"}'
                        }
                        
                        if device_changed:
                            response_data['message'] += f' (device auto-{"enabled" if device_new_state else "disabled"})'
                        
                        return web.json_response(response_data)
                    else:
                        return web.json_response({'error': f'Metric not found: {metric}'}, status=404)
                else:
                    return web.json_response({'error': f'Device not found: {device_id}'}, status=404)
            else:
                return web.json_response({'error': f'Invalid config structure in {config_file}'}, status=500)
                
        except Exception as e:
            self.logger.error(f"Error toggling web device metric: {e}")
            return web.json_response({'error': f'Internal server error: {str(e)}'}, status=500)

    async def handle_toggle_modbus_metric(self, request):
        """Toggle modbus device metric enabled/disabled state"""
        try:
            # Get device ID and metric from query parameters
            device_id = request.query.get('id')
            metric = request.query.get('metric')
            if not device_id or not metric:
                return web.json_response({'error': 'Missing device ID or metric'}, status=400)
            
            # Load modbus endpoints configuration
            import yaml
            from pathlib import Path
            
            config_file = 'config/sources/modbus_endpoints.yaml'
            config_path = Path(config_file)
            if not config_path.exists():
                return web.json_response({'error': f'Config file not found: {config_file}'}, status=404)
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # Navigate to the device metric and toggle its enabled state
            if 'modbus' in config and 'endpoints' in config['modbus']:
                devices = config['modbus']['endpoints']
                if device_id in devices and 'measurements' in devices[device_id]:
                    measurements = devices[device_id]['measurements']
                    if metric in measurements:
                        # Toggle the enabled state
                        current_state = measurements[metric].get('enabled', False)
                        new_state = not current_state
                        measurements[metric]['enabled'] = new_state
                        
                        # Smart device auto-toggle logic
                        device_current_state = devices[device_id].get('enabled', False)
                        device_new_state = device_current_state
                        device_changed = False
                        
                        if new_state and not device_current_state:
                            # Case 1: Enabling a metric when device is OFF -> enable device
                            devices[device_id]['enabled'] = True
                            device_new_state = True
                            device_changed = True
                            self.logger.info(f"Auto-enabled modbus device {device_id} because metric {metric} was enabled")
                        elif not new_state and device_current_state:
                            # Case 2: Disabling a metric when device is ON -> check if it's the last enabled metric
                            enabled_metrics = [m for m, cfg in measurements.items() if cfg.get('enabled', False)]
                            if len(enabled_metrics) == 0:  # No metrics left enabled
                                devices[device_id]['enabled'] = False
                                device_new_state = False
                                device_changed = True
                                self.logger.info(f"Auto-disabled modbus device {device_id} because no metrics are enabled")
                        
                        # Save the updated configuration
                        with open(config_path, 'w', encoding='utf-8') as f:
                            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)
                        
                        self.logger.info(f"Toggled modbus device metric {device_id}.{metric}: {current_state} -> {new_state}")
                        
                        response_data = {
                            'success': True,
                            'device_id': device_id,
                            'metric': metric,
                            'enabled': new_state,
                            'device_enabled': device_new_state,
                            'device_changed': device_changed,
                            'message': f'Modbus metric {device_id}.{metric} {"enabled" if new_state else "disabled"}'
                        }
                        
                        if device_changed:
                            response_data['message'] += f' (device auto-{"enabled" if device_new_state else "disabled"})'
                        
                        return web.json_response(response_data)
                    else:
                        return web.json_response({'error': f'Metric not found: {metric}'}, status=404)
                else:
                    return web.json_response({'error': f'Modbus device not found: {device_id}'}, status=404)
            else:
                return web.json_response({'error': f'Invalid config structure in {config_file}'}, status=500)
        except Exception as e:
            self.logger.error(f"[GUI] Errore toggle modbus metric: {e}")
            return web.json_response({'error': str(e)}, status=500)

    def _setup_log_capture(self):
        """Setup log capture per la GUI"""
        import logging
        from datetime import datetime
        
        class GUILogHandler(logging.Handler):
            def __init__(self, gui_instance):
                super().__init__()
                self.gui = gui_instance
                
            def emit(self, record):
                try:
                    # Formatta il log
                    log_entry = {
                        'timestamp': datetime.now().strftime('%H:%M:%S'),
                        'level': record.levelname,
                        'logger': record.name,
                        'message': record.getMessage()
                    }
                    
                    # Aggiungi al buffer della GUI
                    self.gui.log_buffer.append(log_entry)
                    
                    # Mantieni solo gli ultimi N log
                    if len(self.gui.log_buffer) > self.gui.max_log_buffer:
                        self.gui.log_buffer = self.gui.log_buffer[-self.gui.max_log_buffer:]
                        
                except Exception:
                    pass  # Ignora errori nel logging per evitare loop infiniti
        
        # Aggiungi handler ai logger principali
        gui_handler = GUILogHandler(self)
        gui_handler.setLevel(logging.INFO)
        
        # Aggiungi ai logger che ci interessano
        loggers_to_capture = ['main', 'SimpleWebGUI', 'collector', 'parser', 'storage']
        for logger_name in loggers_to_capture:
            logger = logging.getLogger(logger_name)
            logger.addHandler(gui_handler)

    async def _run_existing_loop(self, cache, config):
        """Avvia il loop esistente di main.py in modalità asincrona"""
        self.logger.info("[GUI] 🔄 Avvio loop personalizzato per GUI")
        
        # Aggiorna statistiche per il nuovo loop
        from datetime import datetime
        self.loop_stats['start_time'] = datetime.now()
        self.loop_stats['status'] = 'running'
        self.loop_stats['last_api_web_run'] = datetime.min
        
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
        api_interval_minutes = int(os.getenv('LOOP_API_INTERVAL_MINUTES', '15'))
        web_interval_minutes = int(os.getenv('LOOP_WEB_INTERVAL_MINUTES', '15'))
        realtime_interval_seconds = int(os.getenv('LOOP_REALTIME_INTERVAL_SECONDS', '5'))
        
        api_web_interval = timedelta(minutes=max(api_interval_minutes, web_interval_minutes))
        realtime_interval = timedelta(seconds=realtime_interval_seconds)
        last_realtime_run = datetime.min
        
        self.logger.info(f"[GUI] Intervalli configurati - API/Web: {api_web_interval.total_seconds()/60:.0f} min, Realtime: {realtime_interval.total_seconds():.0f} sec")
        
        try:
            while self.loop_running and not self.stop_requested:
                current_time = datetime.now()
                
                # Esegui API e Web ogni intervallo configurato
                if current_time - last_api_web_run >= api_web_interval:
                    self.logger.info("[GUI] 🌐 Esecuzione raccolta API/Web...")
                    
                    # Esegui Web flow
                    self.loop_stats['web_stats']['executed'] += 1
                    try:
                        run_web_flow(log, cache)
                        self.loop_stats['web_stats']['success'] += 1
                        self.logger.info("[GUI] ✅ Raccolta web completata")
                    except Exception as e:
                        self.loop_stats['web_stats']['failed'] += 1
                        self.logger.error(f"[GUI] ❌ Errore raccolta web: {e}")
                    
                    # Esegui API flow
                    self.loop_stats['api_stats']['executed'] += 1
                    try:
                        run_api_flow(log, cache, config)
                        self.loop_stats['api_stats']['success'] += 1
                        self.logger.info("[GUI] ✅ Raccolta API completata")
                    except Exception as e:
                        self.loop_stats['api_stats']['failed'] += 1
                        self.logger.error(f"[GUI] ❌ Errore raccolta API: {e}")
                    
                    last_api_web_run = current_time
                    self.loop_stats['last_api_web_run'] = current_time
                    self.loop_stats['last_update'] = current_time
                    
                    # Calcola next run per API/Web
                    next_api_web_run = current_time + api_web_interval
                    self.loop_stats['next_api_web_run'] = next_api_web_run
                
                # Esegui Realtime ogni 5 secondi
                if current_time - last_realtime_run >= realtime_interval:
                    self.loop_stats['realtime_stats']['executed'] += 1
                    try:
                        run_realtime_flow(log, cache, config)
                        self.loop_stats['realtime_stats']['success'] += 1
                        self.logger.debug("[GUI] ✅ Raccolta realtime completata")
                    except Exception as e:
                        self.loop_stats['realtime_stats']['failed'] += 1
                        self.logger.error(f"[GUI] ❌ Errore raccolta realtime: {e}")
                    
                    last_realtime_run = current_time
                    self.loop_stats['last_update'] = current_time
                
                # Pausa breve per permettere controllo stop
                await asyncio.sleep(1)
                
        except Exception as e:
            self.logger.error(f"[GUI] Errore nel loop: {e}")
            self.loop_running = False
        finally:
            self.loop_stats['status'] = 'stopped'
            self.loop_mode = False  # Disabilita modalità loop
            self.logger.info("[GUI] Loop terminato")