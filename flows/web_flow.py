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
    end_date: Optional[str] = None
) -> int:
    """Pipeline web scraping con supporto date storiche
    
    Args:
        start_date: Data inizio per history mode (formato YYYY-MM-DD)
        end_date: Data fine per history mode (formato YYYY-MM-DD)
        
    Se start_date/end_date sono fornite, raccoglie dati giorno per giorno.
    Altrimenti raccoglie solo i dati di oggi.
    """
    log.info(color.bold("🚀 Avvio flusso web"))
    
    # Inizializza scheduler usando config ricevuto come parametro
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
