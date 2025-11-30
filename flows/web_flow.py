import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from logging import Logger
from cache.cache_manager import CacheManager
from collector.collector_web import CollectorWeb
from parser.web_parser import parse_web
from storage.writer_influx import InfluxWriter
from scheduler.scheduler_loop import SchedulerLoop, SchedulerConfig
from utils.color_logger import color

def run_web_flow(
    log: Logger,
    cache: CacheManager,
    config: Dict[str, Any],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    allowed_date_ranges: Optional[list] = None
) -> int:
    """Pipeline web scraping con supporto date storiche
    
    Args:
        start_date: Data inizio per history mode (formato YYYY-MM-DD)
        end_date: Data fine per history mode (formato YYYY-MM-DD)
        allowed_date_ranges: Lista opzionale di range da processare (es. ['monthly'])
        
    Se start_date/end_date sono fornite, raccoglie dati giorno per giorno.
    Altrimenti raccoglie solo i dati di oggi.
    """
    log.info("[FLOW:WEB:START]")
    log.info(color.bold("🚀 Avvio flusso web"))
    
    # Inizializza scheduler usando config ricevuto come parametro
    scheduler_config = SchedulerConfig.from_config(config)
    scheduler = SchedulerLoop(scheduler_config)
    
    scheduler.set_log(log) # Assicura che lo scheduler usi il logger corretto
    
    collector = CollectorWeb(scheduler=scheduler)
    collector.set_cache(cache)
    
    # Costruzione richieste
    device_reqs = collector.build_requests_with_real_ids()
    
    # Filtra per date_range se richiesto
    if allowed_date_ranges and device_reqs:
        original_count = len(device_reqs)
        device_reqs = [
            req for req in device_reqs 
            if req.get('date_range') in allowed_date_ranges
        ]
        log.info(color.dim(f"   Filtro device attivi per range: {len(device_reqs)}/{original_count} (Ranges: {allowed_date_ranges})"))
    
    if not device_reqs:
        log.info("Nessun dispositivo abilitato (o nessuno corrisponde al filtro) - chiusura")
        return 0
    
    # Determina modalità e processa
    total_points_written = 0
    
    try:
        with InfluxWriter() as writer:
            if start_date and end_date:
                # --- HISTORY MODE: Smart Split ---
                log.info(color.info(f"🔄 Web scraping HISTORY: {start_date} → {end_date}"))
                
                # 1. Separa device per tipo di range
                daily_reqs = []
                monthly_reqs = []
                
                for req in device_reqs:
                    if req.get('date_range') == 'monthly':
                        monthly_reqs.append(req)
                    else:
                        # Per history mode, forza 'daily' su device 7days/daily per precisione
                        # ed evitare sovrapposizioni inutili
                        req_copy = req.copy()
                        req_copy['date_range'] = 'daily'
                        daily_reqs.append(req_copy)
                
                # 2. Processa Daily Devices (Giorno per Giorno)
                if daily_reqs:
                    current = datetime.strptime(start_date, '%Y-%m-%d')
                    end = datetime.strptime(end_date, '%Y-%m-%d')
                    
                    log.info(color.dim(f"   Processando {len(daily_reqs)} device giornalieri..."))
                    
                    while current <= end:
                        date_str = current.strftime('%Y-%m-%d')
                        log.info(color.dim(f"   📅 [Daily] Fetching {date_str}"))
                        
                        measurements = collector.fetch_measurements_for_date(daily_reqs, date_str)
                        points = parse_web(measurements, config)
                        
                        if points:
                            writer.write_points(points, measurement_type="web")
                            total_points_written += len(points)
                            
                        current += timedelta(days=1)

                # 3. Processa Monthly Devices (Mese per Mese)
                if monthly_reqs:
                    log.info(color.dim(f"   Processando {len(monthly_reqs)} device mensili..."))
                    
                    # Calcola i target dates (fine mese o fine range)
                    current = datetime.strptime(start_date, '%Y-%m-%d')
                    end_final = datetime.strptime(end_date, '%Y-%m-%d')
                    
                    processed_months = set()
                    
                    while current <= end_final:
                        # Trova l'ultimo giorno del mese corrente
                        # (Logica semplice: vai al 1° del prox mese e torna indietro di 1 giorno)
                        next_month = current.replace(day=28) + timedelta(days=4)
                        last_day_month = next_month - timedelta(days=next_month.day)
                        
                        # Il target è il minore tra fine mese e fine range richiesto
                        target_dt = min(last_day_month, end_final)
                        target_str = target_dt.strftime('%Y-%m-%d')
                        
                        # Evita duplicati se il loop incrementa in modo strano
                        month_key = target_dt.strftime('%Y-%m')
                        if month_key not in processed_months:
                            log.info(color.dim(f"   📅 [Monthly] Fetching chunk ending {target_str}"))
                            
                            # Fetch usa target_date come fine range -> start sarà inizio mese
                            measurements = collector.fetch_measurements_for_date(monthly_reqs, target_str)
                            points = parse_web(measurements, config)
                            
                            if points:
                                writer.write_points(points, measurement_type="web")
                                total_points_written += len(points)
                            
                            processed_months.add(month_key)
                        
                        # Avanza al primo giorno del prossimo mese
                        current = last_day_month + timedelta(days=1)
            
            else:
                # --- SMART RANGE MODE (Loop) ---
                log.info(color.info(f"🔄 Web scraping SMART RANGE (usa configurazioni device)"))
                
                # Nessuna data specifica, il collector usa i range configurati
                measurements_raw = collector.fetch_measurements(device_reqs)
                
                influx_points = parse_web(measurements_raw, config)
                log.info(color.dim(f"   Parser web generato {len(influx_points)} InfluxDB Points"))
                
                if influx_points:
                    writer.write_points(influx_points, measurement_type="web")
                    total_points_written += len(influx_points)
                else:
                    log.warning(color.warning(f"   ⚠️ Nessun punto generato"))
            
    except KeyboardInterrupt:
        log.info(color.warning("🛑 Interruzione utente durante raccolta web"))
        if total_points_written > 0:
            log.info(color.info(f"📊 Punti scritti prima dell'interruzione: {total_points_written}"))
        log.info("[FLOW:WEB:STOP]")
        raise  # Propaga l'interruzione
    except ImportError as e:
        log.error(color.error(f"❌ Modulo web scraping mancante: {e}. Verifica installazione"))
        log.info("[FLOW:WEB:STOP]")
        raise
    except ConnectionError as e:
        log.error(color.error(f"❌ Errore connessione web SolarEdge: {e}. Verifica rete e login"))
        log.info("[FLOW:WEB:STOP]")
        raise
    
    # Log finale con statistiche (solo warning se nessun punto)
    if total_points_written == 0:
        log.warning(color.warning("⚠️ Nessun punto scritto - verifica configurazione e connettività"))
    
    log.info("[FLOW:WEB:STOP]")
    return 0
