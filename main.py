#!/usr/bin/env python3
"""main.py - Orchestratore semplificato dopo refactor"""

import sys, argparse, os, asyncio, webbrowser, re, signal
from pathlib import Path
from typing import Any, Dict
import yaml
from datetime import datetime, timedelta
import time
import threading

from config.env_loader import load_env
from app_logging import configure_logging, get_logger
from cache.cache_manager import CacheManager
from config.config_manager import get_config_manager
from scheduler.scheduler_loop import SchedulerLoop, SchedulerConfig, SourceType

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


def setup_logging(args, config: Dict[str, Any]) -> str:
    """Configura logging basato su modalità"""
    logging_config = config.get('logging', {})
    os.environ["LOG_LEVEL"] = logging_config.get('level', 'INFO')
    os.environ["LOG_DIR"] = logging_config.get('log_directory', 'logs')
    
    log_files = {
        'scan': 'scanner.log',
        'web': 'web_flow.log',
        'api': 'api_flow.log',
        'realtime': 'realtime_flow.log',
        'gui': 'loop_mode.log'
    }
    
    mode = 'scan' if args.scan else ('web' if args.web else 'api' if args.api else 'realtime' if args.realtime else 'gui')
    log_file = log_files.get(mode)
    
    if logging_config.get('file_logging', True) and log_file:
        configure_logging(log_file=log_file, script_name="main")
    else:
        configure_logging(script_name="main")
    
    return log_file


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
    """Killa il processo che occupa una porta specifica (Windows)"""
    import subprocess
    
    try:
        # Trova il PID del processo sulla porta
        result = subprocess.run(
            ['netstat', '-ano', '-p', 'TCP'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return False
        
        # Cerca la riga con la porta
        for line in result.stdout.split('\n'):
            if f':{port}' in line and 'LISTENING' in line:
                # Estrai il PID (ultima colonna)
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    log.info(f"🔍 Trovato processo PID {pid} sulla porta {port}")
                    
                    # Killa il processo
                    kill_result = subprocess.run(
                        ['taskkill', '/F', '/PID', pid],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if kill_result.returncode == 0:
                        log.info(f"✅ Processo PID {pid} terminato")
                        time.sleep(1)  # Aspetta che la porta si liberi
                        return True
                    else:
                        log.warning(f"⚠️ Impossibile terminare processo PID {pid}")
                        return False
        
        return False
        
    except Exception as e:
        log.error(f"Errore durante kill processo: {e}")
        return False


def run_gui_mode(log, cache, config) -> int:
    """Avvia GUI con loop automatico"""
    log.info("🌐 Avvio GUI Dashboard con loop automatico")
    from gui.simple_web_gui import SimpleWebGUI
    
    gui = SimpleWebGUI(cache=cache, auto_start_loop=True)
    
    async def run_gui():
        port = 8092
        runner = None
        site = None
        
        # Prova ad avviare sulla porta 8092 (usa default host='127.0.0.1')
        try:
            runner, site = await gui.start(port=port)
            log.info(f"✅ Server GUI avviato su porta {port}")
        except OSError as e:
            error_msg = str(e).lower()
            
            # Porta occupata - prova a killare
            if "address already in use" in error_msg:
                log.warning(f"⚠️ Porta {port} occupata, tento di liberarla...")
                if kill_process_on_port(port, log):
                    log.info("🔄 Riprovo ad avviare il server...")
                    try:
                        runner, site = await gui.start(port=port)
                        log.info(f"✅ Server GUI avviato su porta {port}")
                    except Exception as retry_error:
                        log.error(f"❌ Impossibile avviare GUI dopo kill: {retry_error}")
                        return 1
                else:
                    log.error(f"❌ Impossibile liberare porta {port}")
                    return 1
            else:
                log.error(f"❌ Errore avvio GUI: {e}")
                raise
        
        # Apri browser SUBITO dopo che il server è avviato
        url = f"http://127.0.0.1:{port}"
        log.info(f"🌐 GUI disponibile su: {url}")
        log.info(f"📡 Accesso rete locale: http://{gui.real_ip}:{port} (se firewall permette)")
        log.info("Loop avviato automaticamente - usa la GUI per controllarlo")
        log.info("Premi Ctrl+C per fermare la GUI")
        
        # Aspetta un attimo che il server sia pronto
        await asyncio.sleep(0.5)
        
        try:
            webbrowser.open(url)
        except Exception:
            pass
        
        try:
            # Loop infinito con gestione interruzioni
            while True:
                await asyncio.sleep(1)
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
        asyncio.run(run_gui())
    except KeyboardInterrupt:
        # Questo è normale quando si preme Ctrl+C
        pass
    except Exception as e:
        log.error(f"Errore GUI: {e}")
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
    from datetime import datetime, timedelta
    import yaml
    from pathlib import Path
    
    # Carica configurazione per passarla al parser e scheduler
    config = load_config_with_env_substitution("config/main.yaml")
    
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
        
        log.info(f"🔄 Web scraping per {len(dates_to_process)} giorni: {start_date} → {end_date}")
    else:
        # Modalità normale: solo oggi
        today = datetime.now().strftime('%Y-%m-%d')
        dates_to_process = [today]
        log.info(f"🔄 Web scraping per oggi: {today}")
    
    # Raccolta dati per ogni giorno
    all_influx_points = []
    
    try:
        for date in dates_to_process:
            log.info(f"📅 Raccogliendo dati web per {date}")
            
            # Raccolta dati per questa data specifica
            measurements_raw = collector.fetch_measurements_for_date(device_reqs, date)
            
            # Parsing + Filtro + Conversione -> InfluxDB Points pronti (con config)
            influx_points = parse_web(measurements_raw, config)
            log.info(f"Parser web generato {len(influx_points)} InfluxDB Points per {date}")
            
            all_influx_points.extend(influx_points)
            
    except KeyboardInterrupt:
        log.info("🛑 Interruzione durante raccolta web")
        raise  # Propaga l'interruzione
    
    # Storage di tutti i punti raccolti
    if all_influx_points:
        with InfluxWriter() as writer:
            writer.write_points(all_influx_points, measurement_type="web")
            log.info(f"✅ Pipeline web completata - {len(all_influx_points)} punti scritti")
    else:
        log.warning("Nessun punto da scrivere")
    
    return 0


def run_api_flow(log, cache, config, start_date=None, end_date=None) -> int:
    """Pipeline API semplificata
    
    Args:
        start_date: Data inizio per history mode (formato YYYY-MM-DD)
        end_date: Data fine per history mode (formato YYYY-MM-DD)
    """
    from collector.collector_api import CollectorAPI
    from parser.api_parser import create_parser
    from storage.writer_influx import InfluxWriter
    
    # Inizializza scheduler
    scheduler_config = SchedulerConfig.from_config(config)
    scheduler = SchedulerLoop(scheduler_config)
    
    # Raccolta dati con scheduler
    collector = CollectorAPI(cache=cache, scheduler=scheduler)
    
    # Raccolta dati (scheduler gestito internamente dal collector)
    try:
        if start_date and end_date:
            # Modalità history con date specifiche
            raw_data = collector.collect_with_dates(start_date, end_date)
        else:
            # Modalità normale (oggi)
            raw_data = collector.collect()
    except KeyboardInterrupt:
        log.info("🛑 Interruzione durante raccolta dati")
        raise  # Propaga l'interruzione
    
    log.info(f"Raccolti dati da {len(raw_data)} endpoint")
    
    # Log dettagliato per debugging cache hits
    for endpoint, data in raw_data.items():
        if data:
            log.info(f"📊 Endpoint {endpoint}: {len(str(data))} caratteri di dati raccolti")
        else:
            log.warning(f"⚠️ Endpoint {endpoint}: nessun dato raccolto")
    
    # Parsing + Filtro + Conversione -> InfluxDB Points pronti
    parser = create_parser()
    influx_points = parser.parse(raw_data, collector.site_id)
    log.info(f"Parser API generato {len(influx_points)} InfluxDB Points pronti")
    
    # Log per verificare se i punti vengono generati anche da cache
    if influx_points:
        log.info(f"🔄 Processando {len(influx_points)} punti (da API o cache) per scrittura DB")
    else:
        log.warning("⚠️ Nessun punto generato dal parser - possibile problema con dati da cache")
    
    # Storage diretto - nessuna elaborazione nel writer
    if influx_points:
        with InfluxWriter() as writer:
            writer.write_points(influx_points, measurement_type="api")
            log.info("✅ Pipeline API completata")
    else:
        log.warning("Nessun punto da scrivere")
    
    return 0


def run_realtime_flow(log, cache, config) -> int:
    """Pipeline realtime: collector → parser → filtro → writer (coerente con altri flussi)"""
    from collector.collector_realtime import RealtimeCollector
    from parser.parser_realtime import RealtimeParser
    from filtro.regole_filtraggio import filter_structured_points
    from storage.writer_influx import InfluxWriter
    
    log.info("🚀 Avvio flusso realtime")
    
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
        
    except Exception as e:
        log.error(f"Errore pipeline realtime: {e}")
        raise RuntimeError(f"Pipeline realtime fallita: {e}") from e


def run_loop_mode(log, cache, config, should_continue=None) -> int:
    """Modalità loop 24/7: api/web ogni 15 minuti, realtime ogni 5 secondi + GUI."""
    log.info("🔄 Avvio modalità loop 24/7 con GUI integrata")
    log.info("📊 API/Web: ogni 15 minuti | ⚡ Realtime: ogni 5 secondi")
    log.info("🌐 GUI Dashboard disponibile su http://0.0.0.0:8092")
    
    # Timestamp per tracking esecuzioni
    last_api_web_run = datetime.min
    
    # Leggi intervalli dal file .env
    api_interval_minutes = int(os.getenv('LOOP_API_INTERVAL_MINUTES', '15'))
    web_interval_minutes = int(os.getenv('LOOP_WEB_INTERVAL_MINUTES', '15'))
    realtime_interval_seconds = int(os.getenv('LOOP_REALTIME_INTERVAL_SECONDS', '5'))
    
    api_web_interval = timedelta(minutes=max(api_interval_minutes, web_interval_minutes))
    realtime_interval = timedelta(seconds=realtime_interval_seconds)
    
    # Contatori per statistiche (eseguite/successi/fallimenti)
    api_stats = {'executed': 0, 'success': 0, 'failed': 0}
    web_stats = {'executed': 0, 'success': 0, 'failed': 0}
    realtime_stats = {'executed': 0, 'success': 0, 'failed': 0}
    start_time = datetime.now()
    
    try:
        while True:
            # Controlla se deve continuare (per controllo GUI)
            if should_continue and not should_continue():
                log.info("🛑 Loop fermato dal controllo esterno")
                break
                
            current_time = datetime.now()
            
            # Esegui API e Web ogni 15 minuti
            if current_time - last_api_web_run >= api_web_interval:
                log.info(f"🚀 Esecuzione API/Web schedulata - {current_time.strftime('%H:%M:%S')}")
                
                # Esegui API flow
                api_stats['executed'] += 1
                try:
                    run_api_flow(log, cache, config)
                    api_stats['success'] += 1
                    log.info("✅ API flow completato")
                except Exception as e:
                    api_stats['failed'] += 1
                    log.error(f"❌ Errore API flow: {e}")
                
                # Esegui Web flow
                web_stats['executed'] += 1
                try:
                    run_web_flow(log, cache)
                    web_stats['success'] += 1
                    log.info("✅ Web flow completato")
                except Exception as e:
                    web_stats['failed'] += 1
                    log.error(f"❌ Errore Web flow: {e}")
                
                last_api_web_run = current_time
                
                # Statistiche ogni ora
                uptime = current_time - start_time
                if uptime.total_seconds() % 3600 < 60:  # Ogni ora circa
                    api_fmt = f"{api_stats['executed']}/{api_stats['success']}/{api_stats['failed']}"
                    web_fmt = f"{web_stats['executed']}/{web_stats['success']}/{web_stats['failed']}"
                    realtime_fmt = f"{realtime_stats['executed']}/{realtime_stats['success']}/{realtime_stats['failed']}"
                    log.info(f"📈 Statistiche - Uptime: {uptime}, API: {api_fmt}, Web: {web_fmt}, Realtime: {realtime_fmt}")
            
            # Esegui Realtime ogni 5 secondi
            realtime_stats['executed'] += 1
            try:
                run_realtime_flow(log, cache, config)
                realtime_stats['success'] += 1
            except Exception as e:
                realtime_stats['failed'] += 1
                log.error(f"❌ Errore Realtime flow: {e}")
            
            # Pausa di 5 secondi
            time.sleep(5)
            
    except KeyboardInterrupt:
        uptime = datetime.now() - start_time
        log.info(f"🛑 Loop interrotto dall'utente")
        api_fmt = f"{api_stats['executed']}/{api_stats['success']}/{api_stats['failed']}"
        web_fmt = f"{web_stats['executed']}/{web_stats['success']}/{web_stats['failed']}"
        realtime_fmt = f"{realtime_stats['executed']}/{realtime_stats['success']}/{realtime_stats['failed']}"
        log.info(f"📊 Statistiche finali - Uptime: {uptime}, API: {api_fmt}, Web: {web_fmt}, Realtime: {realtime_fmt}")
        return 0
    except Exception as e:
        log.error(f"💥 Errore critico nel loop: {e}")
        return 1


def run_history_mode(log, cache, config) -> int:
    """Modalità history: scarica storico completo con suddivisione mensile"""
    from collector.collector_api import CollectorAPI
    from datetime import datetime
    import calendar
    
    log.info("📜 Avvio modalità History - Scaricamento storico completo")
    
    # Inizializza collector per ottenere date range
    collector = CollectorAPI(cache=cache, scheduler=None)
    
    # Ottieni range temporale dall'API dataPeriod
    log.info("🔍 Recupero range temporale da API dataPeriod...")
    date_range = collector.get_production_date_range()
    
    if not date_range:
        log.error("❌ Impossibile recuperare range temporale")
        return 1
    
    start_date = date_range['start']
    end_date = date_range['end']
    
    log.info(f"📅 Range temporale: {start_date} → {end_date}")
    
    # Genera lista di mesi da processare
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
    
    log.info(f"📊 Totale mesi da processare: {len(months)}")
    
    # Processa ogni mese con gestione interruzione pulita
    success_count = 0
    failed_count = 0
    interrupted = False
    web_executed = False
    
    try:
        for idx, month_data in enumerate(months, 1):
            log.info(f"🔄 [{idx}/{len(months)}] Processando {month_data['label']}: {month_data['start']} → {month_data['end']}")
            
            try:
                # 1. API Flow con date personalizzate (sempre)
                log.info(f"🔄 API flow per {month_data['label']}")
                api_result = run_api_flow(log, cache, config, 
                                         start_date=month_data['start'], 
                                         end_date=month_data['end'])
                
                # 2. Web Flow solo per gli ultimi 7 giorni (alla fine)
                web_result = 0
                if idx == len(months) and not web_executed:
                    # Calcola gli ultimi 7 giorni dalla data di fine
                    from datetime import datetime, timedelta
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                    start_dt = end_dt - timedelta(days=6)  # 7 giorni totali (incluso end_date)
                    
                    web_start = start_dt.strftime('%Y-%m-%d')
                    web_end = end_dt.strftime('%Y-%m-%d')
                    
                    log.info(f"🔄 Web flow per ultimi 7 giorni: {web_start} → {web_end}")
                    web_result = run_web_flow(log, cache, start_date=web_start, end_date=web_end)
                    web_executed = True
                
                # Considera successo se API è ok (web è opzionale)
                if api_result == 0:
                    success_count += 1
                    if web_executed and web_result == 0:
                        log.info(f"✅ {month_data['label']} completato (API + Web)")
                    elif web_executed:
                        log.info(f"✅ {month_data['label']} completato (API ok, Web warning)")
                    else:
                        log.info(f"✅ {month_data['label']} completato (API)")
                else:
                    failed_count += 1
                    log.error(f"❌ {month_data['label']} fallito (API: {api_result})")
                    
            except KeyboardInterrupt:
                # Propaga l'interruzione al livello superiore
                raise
            except Exception as e:
                failed_count += 1
                log.error(f"❌ Errore processando {month_data['label']}: {e}")
                
    except KeyboardInterrupt:
        interrupted = True
        log.info("🛑 Interruzione richiesta dall'utente (Ctrl+C)")
        log.info(f"📊 Processati {success_count + failed_count}/{len(months)} mesi prima dell'interruzione")
    
    # Statistiche finali
    log.info("=" * 60)
    if interrupted:
        log.info(f"📈 History Mode Interrotto")
        log.info(f"✅ API: {success_count}/{len(months)} mesi")
        if failed_count > 0:
            log.info(f"❌ Fallimenti API: {failed_count}/{len(months)}")
        log.info(f"⏸️ Rimanenti: {len(months) - success_count - failed_count}/{len(months)}")
        if web_executed:
            log.info(f"🌐 Web: 7/7 giorni")
        log.info("💡 Riavvia con --history per continuare dal punto di interruzione")
    else:
        log.info(f"📈 History Mode Completato")
        log.info(f"✅ API: {success_count}/{len(months)} mesi")
        if failed_count > 0:
            log.info(f"❌ Fallimenti API: {failed_count}/{len(months)}")
        if web_executed:
            log.info(f"🌐 Web: 7/7 giorni")
    log.info("=" * 60)
    
    # Ritorna 0 se interrotto pulitamente o completato con successo
    if interrupted:
        return 0  # Uscita pulita per interruzione
    else:
        return 0 if failed_count == 0 else 1


def run_loop_mode_with_gui(log, cache, config) -> int:
    """Modalità loop 24/7 con GUI integrata."""
    
    async def run_combined():
        # Avvia la GUI in background
        from gui.simple_web_gui import SimpleWebGUI
        gui = SimpleWebGUI()
        
        # Configura la GUI per il loop mode
        gui.loop_mode = True
        gui.loop_stats = {
            'api_stats': {'executed': 0, 'success': 0, 'failed': 0},
            'web_stats': {'executed': 0, 'success': 0, 'failed': 0},
            'realtime_stats': {'executed': 0, 'success': 0, 'failed': 0},
            'start_time': datetime.now(),
            'last_api_web_run': datetime.min,
            'status': 'running'
        }
        
        # Avvia il server GUI sulla porta 8092
        port = 8092
        runner = None
        site = None
        
        try:
            runner, site = await gui.start(port=port)
            log.info(f"✅ Server GUI avviato su porta {port}")
        except OSError as e:
            error_msg = str(e).lower()
            
            # Porta occupata - prova a killare
            if "address already in use" in error_msg:
                log.warning(f"⚠️ Porta {port} occupata, tento di liberarla...")
                if kill_process_on_port(port, log):
                    log.info("🔄 Riprovo ad avviare il server...")
                    try:
                        runner, site = await gui.start(port=port)
                        log.info(f"✅ Server GUI avviato su porta {port}")
                    except Exception as retry_error:
                        log.error(f"❌ Impossibile avviare GUI dopo kill: {retry_error}")
                        return 1
                else:
                    log.error(f"❌ Impossibile liberare porta {port}")
                    return 1
            else:
                log.error(f"❌ Errore avvio GUI: {e}")
                raise
        
        # Apri il browser
        try:
            import webbrowser
            webbrowser.open(f'http://127.0.0.1:{port}')
        except Exception:
            pass
        
        log.info("🔄 Avvio modalità loop 24/7 con GUI integrata")
        log.info("📊 API/Web: ogni 15 minuti | ⚡ Realtime: ogni 5 secondi")
        log.info(f"🌐 GUI Dashboard disponibile su http://127.0.0.1:{port}")
        log.info(f"📡 Accesso rete locale: http://{gui.real_ip}:{port} (se firewall permette)")
        
        # Aggiungi log di avvio alla GUI
        gui.add_log_entry("info", "🔄 Avvio modalità loop 24/7 con GUI integrata")
        gui.add_log_entry("info", "📊 API/Web: ogni 15 minuti | ⚡ Realtime: ogni 5 secondi")
        gui.add_log_entry("success", f"🌐 GUI Dashboard disponibile su http://127.0.0.1:{port}")
        gui.add_log_entry("info", f"📡 Accesso rete locale: http://{gui.real_ip}:{port}")
        
        # Imposta il loop come attivo
        gui.loop_running = True
        
        # Timestamp per tracking esecuzioni
        last_api_web_run = datetime.min
        
        # Leggi intervalli dal file .env
        api_interval_minutes = int(os.getenv('LOOP_API_INTERVAL_MINUTES', '15'))
        web_interval_minutes = int(os.getenv('LOOP_WEB_INTERVAL_MINUTES', '15'))
        realtime_interval_seconds = int(os.getenv('LOOP_REALTIME_INTERVAL_SECONDS', '5'))
        
        api_web_interval = timedelta(minutes=max(api_interval_minutes, web_interval_minutes))
        realtime_interval = timedelta(seconds=realtime_interval_seconds)
        
        # Contatori per statistiche (eseguite/successi/fallimenti)
        api_stats = {'executed': 0, 'success': 0, 'failed': 0}
        web_stats = {'executed': 0, 'success': 0, 'failed': 0}
        realtime_stats = {'executed': 0, 'success': 0, 'failed': 0}
        start_time = datetime.now()
        

        
        try:
            # Loop principale che può essere riavviato
            while True:
                # Aspetta che il loop sia attivo
                while not gui.loop_running:
                    await asyncio.sleep(1)
                    # Non uscire mai completamente, mantieni la GUI attiva
                
                # Reset contatori se il loop è stato riavviato
                if gui.stop_requested:
                    gui.stop_requested = False
                    api_stats = {'executed': 0, 'success': 0, 'failed': 0}
                    web_stats = {'executed': 0, 'success': 0, 'failed': 0}
                    realtime_stats = {'executed': 0, 'success': 0, 'failed': 0}
                    start_time = datetime.now()
                    last_api_web_run = datetime.min
                    log.info("🔄 Loop riavviato")
                
                # Loop di esecuzione
                while gui.loop_running and not gui.stop_requested:
                    
                    current_time = datetime.now()
                    
                    # Calcola timing per API/Web
                    next_api_web = last_api_web_run + api_web_interval if last_api_web_run != datetime.min else current_time + api_web_interval
                    api_last_run = last_api_web_run.strftime('%H:%M:%S') if last_api_web_run != datetime.min else '--'
                    api_next_run = next_api_web.strftime('%H:%M:%S')
                    
                    # Aggiorna statistiche GUI
                    gui.loop_stats.update({
                        'api_stats': api_stats,
                        'web_stats': web_stats,
                        'realtime_stats': realtime_stats,
                        'uptime': current_time - start_time,
                        'last_update': current_time,
                        'api_last_run': api_last_run,
                        'api_next_run': api_next_run,
                        'web_last_run': api_last_run,  # API e Web vengono eseguiti insieme
                        'web_next_run': api_next_run
                    })
                    
                    # Esegui API e Web ogni 15 minuti
                    if current_time - last_api_web_run >= api_web_interval:
                        log.info(f"🚀 Esecuzione API/Web schedulata - {current_time.strftime('%H:%M:%S')}")
                        
                        # Esegui API flow
                        api_stats['executed'] += 1
                        try:
                            run_api_flow(log, cache, config)
                            api_stats['success'] += 1
                            log.info("✅ API flow completato")
                        except Exception as e:
                            api_stats['failed'] += 1
                            log.error(f"❌ Errore API flow: {e}")
                        
                        # Esegui Web flow
                        web_stats['executed'] += 1
                        try:
                            run_web_flow(log, cache)
                            web_stats['success'] += 1
                            log.info("✅ Web flow completato")
                        except Exception as e:
                            web_stats['failed'] += 1
                            log.error(f"❌ Errore Web flow: {e}")
                        
                        last_api_web_run = current_time
                    
                    # Esegui Realtime ogni 5 secondi
                    realtime_stats['executed'] += 1
                    try:
                        run_realtime_flow(log, cache, config)
                        realtime_stats['success'] += 1
                        # Rimuoviamo i log frequenti di realtime completato
                    except Exception as e:
                        realtime_stats['failed'] += 1
                        log.error(f"❌ Errore Realtime flow: {e}")
                        gui.add_log_entry("error", f"❌ Errore Realtime flow: {e}")
                    
                    # Pausa asincrona di 5 secondi
                    await asyncio.sleep(5)
                
                # Il loop interno è finito (stop richiesto)
                log.info("🛑 Loop fermato, GUI rimane attiva per riavvio")
                gui.loop_stats.update({
                    'api_stats': api_stats,
                    'web_stats': web_stats,
                    'realtime_stats': realtime_stats,
                    'uptime': datetime.now() - start_time,
                    'last_update': datetime.now()
                })
                
        except (KeyboardInterrupt, asyncio.CancelledError):
            uptime = datetime.now() - start_time
            log.info(f"🛑 Loop interrotto dall'utente")
            api_fmt = f"{api_stats['executed']}/{api_stats['success']}/{api_stats['failed']}"
            web_fmt = f"{web_stats['executed']}/{web_stats['success']}/{web_stats['failed']}"
            realtime_fmt = f"{realtime_stats['executed']}/{realtime_stats['success']}/{realtime_stats['failed']}"
            log.info(f"📊 Statistiche finali - Uptime: {uptime}, API: {api_fmt}, Web: {web_fmt}, Realtime: {realtime_fmt}")
        finally:
            log.info("🔄 Chiusura server GUI...")
            await runner.cleanup()
            log.info("✅ Loop e GUI chiusi correttamente")
    
    try:
        asyncio.run(run_combined())
        return 0
    except KeyboardInterrupt:
        log.info("🛑 Loop interrotto dall'utente")
        return 0
    except Exception as e:
        log.error(f"💥 Errore critico nel loop: {e}")
        return 1


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
    config = load_config_with_env_substitution("config/main.yaml")
    
    setup_logging(args, config)
    log = get_logger("main")
    
    # Cache centralizzata
    cache = CacheManager()
    log.info("✅ Cache centralizzata inizializzata")
    
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
        log.info("👋 Uscita pulita richiesta dall'utente")
        return 0
    except Exception as e:
        log.error(f"Errore esecuzione: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())