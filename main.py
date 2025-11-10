#!/usr/bin/env python3
"""main.py - Orchestratore semplificato dopo refactor"""

import sys, argparse, os, asyncio, webbrowser, re, platform
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from datetime import datetime, timedelta
import time

from config.env_loader import load_env
from app_logging import configure_logging, get_logger
from cache.cache_manager import CacheManager
from config.config_manager import get_config_manager
from scheduler.scheduler_loop import SchedulerLoop, SchedulerConfig
from utils.color_logger import color

load_env()


def substitute_env_vars(text: str) -> str:
    """Sostituisce variabili d'ambiente nel formato ${VAR_NAME}."""
    def replace_var(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))
    
    return re.sub(r'\$\{([^}]+)\}', replace_var, text)


def load_config_with_env_substitution(config_path: str) -> Dict[str, Any]:
    """Carica configurazione YAML con sostituzione variabili d'ambiente."""
    try:
        with open(Path(config_path), 'r', encoding='utf-8') as f:
            yaml_content = f.read()
        
        # Sostituisce variabili d'ambiente
        yaml_content = substitute_env_vars(yaml_content)
        
        # Carica YAML processato
        return yaml.safe_load(yaml_content) or {}
    except Exception as e:
        get_logger("main").error(f"Errore lettura config {config_path}: {e}")
        return {}


def setup_logging(args, config: Dict[str, Any]) -> None:
    """Configura logging basato su modalità"""
    logging_config = config.get('logging', {})
    os.environ["LOG_LEVEL"] = logging_config.get('level', 'INFO')
    os.environ["LOG_DIR"] = logging_config.get('log_directory', 'logs')
    
    # Log files configurabili tramite environment
    log_files = {
        'scan': os.getenv('LOG_FILE_SCAN', 'scanner.log'),
        'web': os.getenv('LOG_FILE_WEB', 'web_flow.log'),
        'api': os.getenv('LOG_FILE_API', 'api_flow.log'),
        'realtime': os.getenv('LOG_FILE_REALTIME', 'realtime_flow.log'),
        'gui': os.getenv('LOG_FILE_GUI', 'loop_mode.log')
    }
    
    mode = 'scan' if args.scan else ('web' if args.web else 'api' if args.api else 'realtime' if args.realtime else 'gui')
    log_file = log_files.get(mode)
    
    if logging_config.get('file_logging', True) and log_file:
        configure_logging(log_file=log_file, script_name="main")
    else:
        configure_logging(script_name="main")


def handle_scan_mode(log) -> int:
    """Gestisce modalità scan per scansione web tree"""
    log.info("🔍 Modalità scan: scansione web tree")
    from tools.web_tree_scanner import WebTreeScanner
    from tools.yawl_manager import YawlManager
    
    scanner = WebTreeScanner()
    scanner.scan()
    
    # Aggiorna solo il file web_endpoints.yaml
    log.info("Aggiornando file web_endpoints.yaml...")
    ym = YawlManager()
    if ym.generate_web_endpoints_only():
        log.info("✅ File web_endpoints.yaml aggiornato")
    else:
        log.error("❌ Errore aggiornamento web_endpoints.yaml")
    return 0


def kill_process_on_port(port: int, log) -> bool:
    """Killa il processo che occupa una porta specifica (Cross-Platform)"""
    import subprocess
    import platform
    
    try:
        system = platform.system().lower()
        
        if system == "windows":
            # Windows: usa netstat + taskkill
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True,
                text=True,
                timeout=int(os.getenv('GLOBAL_TIMEOUT_SECONDS', '30'))
            )
            
            if result.returncode != 0:
                log.warning(f"⚠️ Comando netstat fallito per porta {port}")
                return False
            
            # Cerca il PID nella output di netstat
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        log.info(f"🔍 Trovato processo PID {pid} sulla porta {port}")
                        
                        # Termina il processo usando taskkill
                        kill_result = subprocess.run(
                            ['taskkill', '/F', '/PID', pid],
                            capture_output=True,
                            text=True,
                            timeout=int(os.getenv('GLOBAL_TIMEOUT_SECONDS', '30'))
                        )
                        
                        if kill_result.returncode == 0:
                            log.info(f"✅ Processo PID {pid} terminato")
                            time.sleep(int(os.getenv('SCHEDULER_API_DELAY_SECONDS', '1')))
                            return True
                        else:
                            log.warning(f"⚠️ Impossibile terminare processo PID {pid}: {kill_result.stderr}")
                            return False
        
        else:
            # Linux/macOS: usa ss o netstat + kill
            # Prova prima ss (più moderno)
            try:
                result = subprocess.run(
                    ['ss', '-tlnp', f'sport = :{port}'],
                    capture_output=True,
                    text=True,
                    timeout=int(os.getenv('GLOBAL_TIMEOUT_SECONDS', '30'))
                )
            except FileNotFoundError:
                # Fallback a netstat se ss non disponibile
                result = subprocess.run(
                    ['netstat', '-tlnp'],
                    capture_output=True,
                    text=True,
                    timeout=int(os.getenv('GLOBAL_TIMEOUT_SECONDS', '30'))
                )
            
            if result.returncode != 0:
                log.warning(f"⚠️ Comando di ricerca processo fallito per porta {port}")
                return False
            
            # Cerca il PID nella output
            for line in result.stdout.split('\n'):
                if f':{port}' in line and ('LISTEN' in line or 'LISTENING' in line):
                    pid_match = re.search(r'(\d+)/', line)  # Formato: PID/nome_processo
                    if not pid_match:
                        pid_match = re.search(r'pid=(\d+)', line)  # Formato ss alternativo
                    
                    if pid_match:
                        pid = pid_match.group(1)
                        log.info(f"🔍 Trovato processo PID {pid} sulla porta {port}")
                        
                        # Termina il processo usando kill
                        kill_result = subprocess.run(
                            ['kill', '-TERM', pid],  # Usa TERM invece di -9 per shutdown graceful
                            capture_output=True,
                            text=True,
                            timeout=int(os.getenv('GLOBAL_TIMEOUT_SECONDS', '30'))
                        )
                        
                        if kill_result.returncode == 0:
                            log.info(f"✅ Processo PID {pid} terminato")
                            time.sleep(int(os.getenv('SCHEDULER_API_DELAY_SECONDS', '1')))
                            return True
                        else:
                            log.warning(f"⚠️ Impossibile terminare processo PID {pid}: {kill_result.stderr}")
                            return False
        
        log.info(f"ℹ️ Nessun processo trovato sulla porta {port}")
        return False
        
    except subprocess.TimeoutExpired:
        log.error(f"❌ Timeout durante ricerca processo su porta {port}")
        return False
    except FileNotFoundError as e:
        log.error(f"❌ Comando non trovato: {e}")
        return False
    except Exception as e:
        log.error(f"❌ Errore durante kill processo su porta {port}: {e}")
        return False


def run_gui_mode(log, cache, config=None) -> int:
    """Avvia GUI con loop automatico"""
    log.info("🌐 Avvio GUI Dashboard con loop automatico")
    from gui.simple_web_gui import SimpleWebGUI
    
    gui = SimpleWebGUI(cache=cache, auto_start_loop=True)
    
    async def run_gui():
        port = int(os.getenv('GUI_PORT', '8092'))
        runner = None
        
        # Prova ad avviare sulla porta 8092 (usa default host='127.0.0.1')
        try:
            runner, _ = await gui.start(port=port)
            log.info(f"✅ Server GUI avviato su porta {port}")
        except OSError as e:
            error_msg = str(e).lower()
            
            # Porta occupata - prova a killare
            if "address already in use" in error_msg:
                log.warning(f"⚠️ Porta {port} occupata, tento di liberarla...")
                if kill_process_on_port(port, log):
                    log.info("🔄 Riprovo ad avviare il server...")
                    try:
                        runner, _ = await gui.start(port=port)
                        log.info(f"✅ Server GUI avviato su porta {port}")
                    except OSError as retry_error:
                        log.error(f"❌ Porta {port} ancora occupata dopo kill: {retry_error}")
                        return 1
                    except Exception as retry_error:
                        log.error(f"❌ Errore imprevisto durante riavvio GUI: {retry_error}")
                        return 1
                else:
                    log.error(f"❌ Impossibile liberare porta {port}. Verifica manualmente: sudo ss -tlnp | grep {port}")
                    return 1
            elif "permission denied" in error_msg:
                log.error(f"❌ Permessi insufficienti per porta {port}. Usa porta > 1024 o esegui come root")
                return 1
            else:
                log.error(f"❌ Errore di rete durante avvio GUI su porta {port}: {e}")
                raise
        
        # Apri browser SUBITO dopo che il server è avviato
        url = f"http://127.0.0.1:{port}"
        log.info(f"🌐 GUI disponibile su: {url}")
        log.info(f"📡 Accesso rete locale: http://{gui.real_ip}:{port} (se firewall permette)")
        log.info("Loop avviato automaticamente - usa la GUI per controllarlo")
        log.info("Premi Ctrl+C per fermare la GUI")
        
        # Aspetta che il server sia pronto (usa delay configurabile)
        await asyncio.sleep(float(os.getenv('SCHEDULER_API_DELAY_SECONDS', '1')))
        
        try:
            webbrowser.open(url)
        except Exception:
            pass
        
        try:
            # Loop infinito con gestione interruzioni
            # Usa un intervallo più lungo per ridurre CPU usage quando idle
            gui_check_interval = 60  # 60 secondi invece di 5
            while True:
                await asyncio.sleep(gui_check_interval)
        except KeyboardInterrupt:
            log.info("🛑 Interruzione ricevuta, chiusura GUI...")
        except asyncio.CancelledError:
            log.info("🛑 Task cancellato, chiusura GUI...")
        finally:
            log.info("🔄 Chiusura server GUI...")
            try:
                await runner.cleanup()
                log.info("✅ GUI chiusa correttamente")
            except Exception as e:
                log.error(f"Errore durante chiusura GUI: {e}")
    
    try:
        # Usa ProactorEventLoop su Windows, o uvloop se disponibile
        # Questo riduce il busy-wait di epoll
        try:
            import uvloop
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            log.info("✅ Usando uvloop per migliori performance")
        except ImportError:
            # uvloop non disponibile, usa default
            pass
        
        asyncio.run(run_gui())
    except KeyboardInterrupt:
        # Questo è normale quando si preme Ctrl+C
        log.info("👋 GUI chiusa dall'utente")
        pass
    except asyncio.CancelledError:
        log.info("🛑 Task GUI cancellato")
        pass
    except ImportError as e:
        log.error(f"❌ Modulo GUI mancante: {e}. Installa: pip install aiohttp")
        return 1
    except Exception as e:
        log.error(f"❌ Errore imprevisto nella GUI: {e}")
        return 1
    
    return 0


def run_web_flow(log, cache, start_date=None, end_date=None) -> int:
    """Pipeline web scraping con supporto date storiche
    
    Args:
        start_date: Data inizio per history mode (formato YYYY-MM-DD)
        end_date: Data fine per history mode (formato YYYY-MM-DD)
        
    Se start_date/end_date sono fornite, raccoglie dati giorno per giorno.
    Altrimenti raccoglie solo i dati di oggi.
    """
    from collector.collector_web import CollectorWeb
    from parser.web_parser import parse_web
    from storage.writer_influx import InfluxWriter
    
    log.info(color.bold("🚀 Avvio flusso web"))
    
    # Carica configurazione completa (inclusi i file sources) per passarla al parser e scheduler
    config_path = os.getenv('CONFIG_PATH', 'config/main.yaml')
    config_manager = get_config_manager(config_path)
    config = config_manager.get_raw_config()
    
    # Inizializza scheduler
    scheduler_config = SchedulerConfig.from_config(config)
    scheduler = SchedulerLoop(scheduler_config)
    
    collector = CollectorWeb(scheduler=scheduler)
    collector.set_cache(cache)
    
    # Costruzione richieste
    device_reqs = collector.build_requests_with_real_ids()
    if not device_reqs:
        log.info("Nessun dispositivo abilitato - chiusura")
        return 0
    
    # Determina le date da processare
    if start_date and end_date:
        # History mode: processa giorno per giorno
        current = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        dates_to_process = []
        
        while current <= end:
            dates_to_process.append(current.strftime('%Y-%m-%d'))
            current += timedelta(days=1)
        
        log.info(color.info(f"🔄 Web scraping per {len(dates_to_process)} giorni: {start_date} → {end_date}"))
    else:
        # Modalità normale: solo oggi
        today = datetime.now().strftime('%Y-%m-%d')
        dates_to_process = [today]
        log.info(color.info(f"🔄 Web scraping per oggi: {today}"))
    
    # Raccolta e scrittura streaming per ottimizzare memoria
    total_points_written = 0
    
    try:
        # Apri writer una volta per tutte le date (più efficiente)
        with InfluxWriter() as writer:
            for date in dates_to_process:
                log.info(color.dim(f"   📅 Raccogliendo dati web per {date}"))
                
                # Raccolta dati per questa data specifica
                measurements_raw = collector.fetch_measurements_for_date(device_reqs, date)
                
                # Parsing + Filtro + Conversione -> InfluxDB Points pronti (con config)
                influx_points = parse_web(measurements_raw, config)
                log.info(color.dim(f"   Parser web generato {len(influx_points)} InfluxDB Points per {date}"))
                
                # Scrittura immediata invece di accumulo (ottimizzazione memoria)
                if influx_points:
                    writer.write_points(influx_points, measurement_type="web")
                    total_points_written += len(influx_points)
                    log.info(color.dim(f"   ✅ Scritti {len(influx_points)} punti per {date}"))
                else:
                    log.warning(color.warning(f"   ⚠️ Nessun punto generato per {date}"))
            
    except KeyboardInterrupt:
        log.info(color.warning("🛑 Interruzione utente durante raccolta web"))
        if total_points_written > 0:
            log.info(color.info(f"📊 Punti scritti prima dell'interruzione: {total_points_written}"))
        raise  # Propaga l'interruzione
    except ImportError as e:
        log.error(color.error(f"❌ Modulo web scraping mancante: {e}. Verifica installazione"))
        raise
    except ConnectionError as e:
        log.error(color.error(f"❌ Errore connessione web SolarEdge: {e}. Verifica rete e login"))
        raise
    
    # Log finale con statistiche
    if total_points_written > 0:
        log.info(color.success(f"✅ Pipeline web completata: {total_points_written} punti scritti per {len(dates_to_process)} giorni"))
    else:
        log.warning(color.warning("⚠️ Nessun punto scritto - verifica configurazione e connettività"))
    
    return 0


def run_api_flow(log, cache, config, start_date: Optional[str] = None, end_date: Optional[str] = None) -> int:
    """Pipeline API semplificata
    
    Args:
        start_date: Data inizio per history mode (formato YYYY-MM-DD)
        end_date: Data fine per history mode (formato YYYY-MM-DD)
    """
    from collector.collector_api import CollectorAPI
    from parser.api_parser import create_parser
    from storage.writer_influx import InfluxWriter
    
    log.info(color.bold("🚀 Avvio flusso API"))
    
    # Inizializza scheduler
    scheduler_config = SchedulerConfig.from_config(config)
    scheduler = SchedulerLoop(scheduler_config)
    
    # Raccolta dati con scheduler (usa context manager per session pooling)
    with CollectorAPI(cache=cache, scheduler=scheduler) as collector:
        
        # Raccolta dati (scheduler gestito internamente dal collector)
        try:
            if start_date and end_date:
                # Modalità history con date specifiche
                raw_data = collector.collect_with_dates(start_date, end_date)
            else:
                # Modalità normale (oggi)
                raw_data = collector.collect()
        except KeyboardInterrupt:
            log.info("🛑 Interruzione utente durante raccolta dati API")
            raise  # Propaga l'interruzione
        except ImportError as e:
            log.error(f"❌ Modulo API mancante: {e}. Verifica installazione dipendenze")
            raise
        except ConnectionError as e:
            log.error(f"❌ Errore connessione API SolarEdge: {e}. Verifica rete e credenziali")
            raise
        
        log.info(color.dim(f"   Raccolti dati da {len(raw_data)} endpoint"))
        
        # Log dettagliato per debugging cache hits
        for endpoint, data in raw_data.items():
            if data:
                log.info(color.dim(f"   📊 Endpoint {endpoint}: {len(str(data))} caratteri di dati raccolti"))
            else:
                log.warning(color.warning(f"   ⚠️ Endpoint {endpoint}: nessun dato raccolto"))
        
        # Parsing + Filtro + Conversione -> InfluxDB Points pronti
        parser = create_parser()
        influx_points = parser.parse(raw_data, collector.site_id)
        log.info(color.dim(f"   Parser API generato {len(influx_points)} InfluxDB Points pronti"))
        
        # Log per verificare se i punti vengono generati anche da cache
        if influx_points:
            log.info(color.dim(f"   🔄 Processando {len(influx_points)} punti (da API o cache) per scrittura DB"))
        else:
            log.warning(color.warning("   ⚠️ Nessun punto generato dal parser - possibile problema con dati da cache"))
        
        # Storage diretto - nessuna elaborazione nel writer
        if influx_points:
            with InfluxWriter() as writer:
                writer.write_points(influx_points, measurement_type="api")
                log.info(color.success("✅ Pipeline API completata con successo"))
        else:
            log.warning(color.warning("   Nessun punto da scrivere"))
    
    return 0


def run_realtime_flow(log, cache, config) -> int:
    """Pipeline realtime: collector → parser → filtro → writer (coerente con altri flussi)"""
    from collector.collector_realtime import RealtimeCollector
    from parser.parser_realtime import RealtimeParser
    from filtro.regole_filtraggio import filter_structured_points
    from storage.writer_influx import InfluxWriter
    
    log.info(color.bold("🚀 Avvio flusso realtime"))
    
    try:
        # Step 1: Collector - raccolta dati (output formattato come example.py)
        collector = RealtimeCollector()
        formatted_output = collector.collect_data()
        
        if not formatted_output:
            log.error("Collector non ha restituito dati")
            return 1
        
        log.info("✅ Collector: output formattato generato")
        
        # Step 2: Parser - elabora output testuale → struttura dati
        parser = RealtimeParser()
        structured_points = parser.parse_realtime_data(formatted_output)
        
        if not structured_points:
            log.warning("Parser non ha generato punti strutturati")
            return 1
        
        log.info(f"✅ Parser: generati {len(structured_points)} punti strutturati")
        
        # Step 3: Filtro - validazione punti strutturati (coerente con altri flussi)
        filtered_points = filter_structured_points(structured_points)
        log.info(f"✅ Filtro: validati {len(filtered_points)}/{len(structured_points)} punti")
        
        # Step 4: Writer - storage diretto (coerente con altri flussi)
        if filtered_points:
            with InfluxWriter() as writer:
                writer.write_points(filtered_points, measurement_type="realtime")
                log.info("✅ Pipeline realtime completata con successo")
        else:
            log.warning("Nessun punto valido da scrivere")
            return 1
        
        return 0
        
    except KeyboardInterrupt:
        log.info("🛑 Interruzione utente durante raccolta realtime")
        raise
    except ValueError as e:
        # Modbus disabilitato nella configurazione - non è un errore
        if "disabilitato nella configurazione" in str(e):
            log.info("ℹ️ Modbus disabilitato nella configurazione, skip realtime")
            return 0  # Ritorna successo, non errore
        log.error(f"❌ Errore valore pipeline realtime: {e}")
        raise
    except ImportError as e:
        log.error(f"❌ Modulo realtime mancante: {e}. Verifica installazione pymodbus")
        raise
    except ConnectionError as e:
        log.error(f"❌ Errore connessione Modbus: {e}. Verifica IP inverter e rete")
        raise
    except Exception as e:
        log.error(f"❌ Errore imprevisto pipeline realtime: {e}")
        raise RuntimeError(f"Pipeline realtime fallita: {e}") from e





def _get_date_range_from_api(collector, log):
    """Recupera range temporale dall'API dataPeriod"""
    log.info(color.info("🔍 Recupero range temporale da API dataPeriod..."))
    date_range = collector.get_production_date_range()
    
    if not date_range:
        log.error(color.error("❌ Impossibile recuperare range temporale"))
        return None
    
    start_date = date_range['start']
    end_date = date_range['end']
    log.info(color.highlight(f"📅 Range temporale: {start_date} → {end_date}"))
    
    return start_date, end_date


def _generate_months_list(start_date: str, end_date: str, log):
    """Genera lista di mesi da processare"""
    import calendar
    
    months = []
    current = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    while current <= end:
        year = current.year
        month = current.month
        
        # Primo giorno del mese
        first_day = datetime(year, month, 1)
        
        # Ultimo giorno del mese
        last_day_num = calendar.monthrange(year, month)[1]
        last_day = datetime(year, month, last_day_num)
        
        # Non superare end_date
        if last_day > end:
            last_day = end
        
        months.append({
            'start': first_day.strftime('%Y-%m-%d'),
            'end': last_day.strftime('%Y-%m-%d'),
            'label': first_day.strftime('%Y-%m')
        })
        
        # Passa al mese successivo
        if month == 12:
            current = datetime(year + 1, 1, 1)
        else:
            current = datetime(year, month + 1, 1)
    
    log.info(color.highlight(f"📊 Totale mesi da processare: {len(months)}"))
    return months


def _process_months(months, end_date: str, log, cache, config):
    """Processa tutti i mesi con gestione interruzioni"""
    success_count = 0
    failed_count = 0
    web_success = False
    web_failed = False
    interrupted = False
    web_executed = False
    
    try:
        # Processa tutti i mesi
        for idx, month_data in enumerate(months, 1):
            log.info(color.info(f"🔄 [{idx}/{len(months)}] Processando {month_data['label']}: {month_data['start']} → {month_data['end']}"))
            
            try:
                # 1. API Flow con date personalizzate (sempre) - CON CACHE
                log.info(color.dim(f"   🔄 API flow per {month_data['label']} (CON CACHE)"))
                api_result = run_api_flow(log, cache, config, 
                                         start_date=month_data['start'], 
                                         end_date=month_data['end'])
                
                # 2. Web Flow solo per gli ultimi 7 giorni (alla fine)
                web_result = 0
                if idx == len(months) and not web_executed:
                    # Calcola gli ultimi 7 giorni dalla data di fine
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                    start_dt = end_dt - timedelta(days=6)  # 7 giorni totali (incluso end_date)
                    
                    web_start = start_dt.strftime('%Y-%m-%d')
                    web_end = end_dt.strftime('%Y-%m-%d')
                    
                    log.info(color.dim(f"   🔄 Web flow per ultimi 7 giorni: {web_start} → {web_end}"))
                    try:
                        web_result = run_web_flow(log, cache, start_date=web_start, end_date=web_end)
                        web_executed = True
                        if web_result == 0:
                            web_success = True
                        else:
                            web_failed = True
                    except Exception as web_error:
                        log.error(color.error(f"   ❌ Web flow fallito: {web_error}"))
                        web_executed = True
                        web_failed = True
                        web_result = 1
                
                # Considera successo se API è ok (web è opzionale)
                if api_result == 0:
                    success_count += 1
                    if web_executed and web_result == 0:
                        log.info(color.success(f"   ✅ {month_data['label']} completato (API + Web)"))
                    elif web_executed:
                        log.info(color.warning(f"   ✅ {month_data['label']} completato (API ok, Web warning)"))
                    else:
                        log.info(color.success(f"   ✅ {month_data['label']} completato (API)"))
                else:
                    failed_count += 1
                    log.error(color.error(f"   ❌ {month_data['label']} fallito (API: {api_result})"))
                    
            except KeyboardInterrupt:
                # Propaga l'interruzione al livello superiore
                raise
            except Exception as e:
                failed_count += 1
                log.error(color.error(f"   ❌ Errore processando {month_data['label']}: {e}"))
                
    except KeyboardInterrupt:
        interrupted = True
        log.info(color.warning("🛑 Interruzione richiesta dall'utente (Ctrl+C)"))
        log.info(color.dim(f"📊 Processati {success_count + failed_count}/{len(months)} mesi prima dell'interruzione"))
    
    return success_count, failed_count, web_success, web_failed, interrupted, web_executed


def _print_final_statistics(success_count, failed_count, web_success, web_failed, 
                           interrupted, web_executed, total_months, log):
    """Stampa statistiche finali del history mode"""
    log.info(color.bold("=" * 60))
    if interrupted:
        log.info(color.warning("📈 History Mode Interrotto"))
        log.info(color.success(f"✅ API: {success_count}/{total_months} mesi"))
        if failed_count > 0:
            log.info(color.error(f"❌ Fallimenti API: {failed_count}/{total_months}"))
        log.info(color.dim(f"⏸️ Rimanenti: {total_months - success_count - failed_count}/{total_months}"))
        if web_executed:
            if web_success:
                log.info(color.success(f"✅ Web: 7/7 giorni"))
            elif web_failed:
                log.info(color.error(f"❌ Web: 0/7 giorni (fallito)"))
        log.info(color.highlight("💡 Riavvia con --history per continuare dal punto di interruzione"))
    else:
        log.info(color.success("📈 History Mode Completato"))
        log.info(color.success(f"✅ API: {success_count}/{total_months} mesi"))
        if failed_count > 0:
            log.info(color.error(f"❌ Fallimenti API: {failed_count}/{total_months}"))
        if web_executed:
            if web_success:
                log.info(color.success(f"✅ Web: 7/7 giorni"))
            elif web_failed:
                log.info(color.error(f"❌ Web: 0/7 giorni (fallito)"))
    log.info(color.bold("=" * 60))


def run_history_mode(log, cache, config) -> int:
    """Modalità history: scarica storico completo con suddivisione mensile"""
    from collector.collector_api import CollectorAPI
    
    log.info(color.bold("📜 Avvio modalità History - Scaricamento storico completo"))
    log.info(color.success("✅ ABILITANDO CACHE per history mode - skip mesi già scaricati"))
    
    # Inizializza collector CON cache per evitare chiamate API duplicate
    collector = CollectorAPI(cache=cache, scheduler=None)
    
    # Inizializza variabili per gestione return
    interrupted = False
    failed_count = 0
    
    try:
        # 1. Recupera range temporale dall'API
        date_range_result = _get_date_range_from_api(collector, log)
        if not date_range_result:
            return 1
        start_date, end_date = date_range_result
        
        # 2. Genera lista di mesi da processare
        months = _generate_months_list(start_date, end_date, log)
        
        # 3. Processa tutti i mesi
        success_count, failed_count, web_success, web_failed, interrupted, web_executed = \
            _process_months(months, end_date, log, cache, config)
        
        # 4. Stampa statistiche finali
        _print_final_statistics(success_count, failed_count, web_success, web_failed,
                               interrupted, web_executed, len(months), log)
        
    finally:
        # Chiudi sessione HTTP per liberare risorse
        collector.close()
    
    # Ritorna 0 se interrotto pulitamente o completato con successo
    if interrupted:
        return 0  # Uscita pulita per interruzione
    else:
        return 0 if failed_count == 0 else 1





def main() -> int:
    """Entry point principale"""
    ap = argparse.ArgumentParser(
        description="SolarEdge Data Collector",
        epilog="Senza argomenti: avvia GUI Dashboard con loop in modalità stop"
    )
    grp = ap.add_mutually_exclusive_group(required=False)
    grp.add_argument('--web', action='store_true', help='Esegui singola raccolta dati web')
    grp.add_argument('--api', action='store_true', help='Esegui singola raccolta dati API')
    grp.add_argument('--realtime', action='store_true', help='Esegui singola raccolta dati realtime')
    grp.add_argument('--scan', action='store_true', help='Esegui scansione web tree e aggiorna configurazione')
    grp.add_argument('--history', action='store_true', help='Scarica storico completo da SolarEdge (suddivisione mensile)')
    args = ap.parse_args()
    
    # Carica configurazione con sostituzione variabili d'ambiente
    config_path = os.getenv('CONFIG_PATH', 'config/main.yaml')
    config = load_config_with_env_substitution(config_path)
    
    setup_logging(args, config)
    log = get_logger("main")
    
    # Cache centralizzata
    cache = CacheManager()
    log.info(color.success("✅ Cache centralizzata inizializzata"))
    
    # Se nessun argomento specificato, avvia GUI con loop in stop
    if not any([args.web, args.api, args.realtime, args.scan, args.history]):
        return run_gui_mode(log, cache, config)
    
    # Esegui modalità richiesta
    try:
        if args.web:
            return run_web_flow(log, cache)
        elif args.api:
            return run_api_flow(log, cache, config)
        elif args.realtime:
            return run_realtime_flow(log, cache, config)
        elif args.scan:
            return handle_scan_mode(log)
        elif args.history:
            return run_history_mode(log, cache, config)
    except KeyboardInterrupt:
        log.info(color.warning("👋 Uscita pulita richiesta dall'utente"))
        return 0
    except Exception as e:
        log.error(color.error(f"Errore esecuzione: {e}"))
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())