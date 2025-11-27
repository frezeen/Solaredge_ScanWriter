import os
from typing import Optional, Dict, Any
from logging import Logger
from cache.cache_manager import CacheManager
from collector.collector_gme import CollectorGME
from parser.gme_parser import create_parser
from storage.writer_influx import InfluxWriter
from utils.color_logger import color
from datetime import datetime, timedelta
from scheduler.scheduler_loop import SchedulerLoop, SchedulerConfig

def run_gme_flow(
    log: Logger,
    cache: CacheManager,
    config: Dict[str, Any],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> int:
    """Pipeline GME (Gestore dei Mercati Energetici)
    
    Args:
        start_date: Data inizio (formato YYYY-MM-DD)
        end_date: Data fine (formato YYYY-MM-DD)
    """
    log.info(color.bold("🚀 Avvio flusso GME (Mercato Elettrico Italiano)"))
    
    # Se non specificate date, usa ieri (D+1 availability)
    if not start_date:
        yesterday = datetime.now() - timedelta(days=1)
        start_date = yesterday.strftime('%Y-%m-%d')
        end_date = start_date

    # Raccolta dati
    scheduler_config = SchedulerConfig.from_config(config)
    scheduler = SchedulerLoop(scheduler_config)
    collector = CollectorGME(scheduler=scheduler)
    
    try:
        current_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        total_points = 0
        
        while current_date <= end_dt:
            date_str = current_date.strftime('%Y-%m-%d')
            log.info(f"[*] Elaborazione data: {date_str}")
            
            # 1. Collect
            raw_data = collector.collect(current_date)
            
            if not raw_data or 'prices' not in raw_data:
                log.warning(color.warning(f"   ⚠️ Nessun dato GME raccolto per {date_str}"))
                current_date += timedelta(days=1)
                continue

            # 2. Save to Cache
            cache.save_to_cache("gme", "data", date_str, raw_data)

            # 3. Parse Hourly
            parser = create_parser()
            influx_points = parser.parse(raw_data)
            
            if not influx_points:
                log.warning(f"⚠️ Nessun punto generato per {date_str}")
                current_date += timedelta(days=1)
                continue

            # 4. Calculate Cumulative Monthly Average
            # Carica tutti i giorni del mese finora in cache per calcolare la media progressiva
            month_prices = []
            year = current_date.year
            month = current_date.month
            
            # Itera dal 1° del mese fino a oggi
            for d in range(1, current_date.day + 1):
                d_str = datetime(year, month, d).strftime('%Y-%m-%d')
                d_data = cache.get_cached_data("gme", "data", d_str)
                if d_data:
                    month_prices.extend(d_data.get('prices', []))
            
            monthly_avg_point = None
            if month_prices:
                # Estrai solo i valori pun_kwh per il calcolo
                pun_values = [p.get('pun_kwh') for p in month_prices if p.get('pun_kwh') is not None]
                if pun_values:
                    monthly_avg_point = parser.create_monthly_avg_point(pun_values, current_date)
                    log.info(color.dim(f"   Media mensile progressiva calcolata su {len(pun_values)} ore"))

            # 5. Write to InfluxDB
            with InfluxWriter() as writer:
                writer.write_points(influx_points, measurement_type="gme_prices")
                if monthly_avg_point:
                    writer.write_points([monthly_avg_point], measurement_type="gme_monthly_avg")
                total_points += len(influx_points) + (1 if monthly_avg_point else 0)
            
            log.info(color.success(f"   ✅ Salvati {len(influx_points)} punti orari per {date_str}"))
            current_date += timedelta(days=1)

    except Exception as e:
        log.error(f"❌ Errore flusso GME: {e}")
        raise
    finally:
        collector.close()
    
    return 0

def run_gme_month_flow(
    log: Logger,
    cache: CacheManager,
    config: Dict[str, Any],
    year: int,
    month: int,
    scheduler: Optional[SchedulerLoop] = None
) -> int:
    """
    Pipeline GME per un mese intero (history mode)
    
    Strategia:
    1. Verifica se tutti i giorni del mese sono in cache
    2. Se sì -> Carica da cache e aggrega
    3. Se no -> Scarica mese intero (1 API call), salva in cache giornaliera, aggrega
    """
    import calendar
    
    log.info(color.bold(f"🔄 GME: Elaborazione mese {year}-{month:02d}"))
    
    # Calcola giorni del mese
    num_days = calendar.monthrange(year, month)[1]
    days = [datetime(year, month, d).strftime('%Y-%m-%d') for d in range(1, num_days + 1)]
    
    # 1. Verifica Cache
    missing_days = []
    cached_data = []
    
    for day_str in days:
        # Skip giorni futuri
        if datetime.strptime(day_str, '%Y-%m-%d') > datetime.now():
            continue
            
        if cache.has_gme_day_cached(day_str):
            # Carica da cache
            data = cache.get_cached_data("gme", "data", day_str)
            if data:
                cached_data.append(data)
            else:
                missing_days.append(day_str)
        else:
            missing_days.append(day_str)
            
    # 2. Se mancano giorni, scarica tutto il mese (più efficiente di N chiamate)
    if missing_days:
        log.info(color.dim(f"   📉 Cache miss per {len(missing_days)} giorni. Download mese intero..."))
        
        if not scheduler:
            scheduler_config = SchedulerConfig.from_config(config)
            scheduler = SchedulerLoop(scheduler_config)
            
        collector = CollectorGME(scheduler=scheduler)
        try:
            # Scarica mese intero
            full_month_data = collector.collect_month(year, month)
            
            if not full_month_data or 'prices' not in full_month_data:
                log.warning(color.warning(f"   ⚠️ Nessun dato GME per {year}-{month:02d}"))
                return 1
            
            # Raggruppa per giorno e salva in cache
            prices_by_day = {}
            for price in full_month_data.get('prices', []):
                d = price.get('date')
                if d:
                    if d not in prices_by_day:
                        prices_by_day[d] = {'date': d, 'prices': [], 'source': 'GME', 'market': 'MGP'}
                    prices_by_day[d]['prices'].append(price)
            
            # Salva ogni giorno in cache e aggiungi a cached_data
            # Reset cached_data per evitare duplicati/incongruenze
            cached_data = []
            
            for day_str, day_data in prices_by_day.items():
                cache.save_to_cache("gme", "data", day_str, day_data)
                cached_data.append(day_data)
                
            log.info(color.success(f"   💾 Salvati {len(prices_by_day)} giorni in cache"))
            
        except Exception as e:
            log.error(f"❌ Errore download GME {year}-{month:02d}: {e}")
            return 1
        finally:
            collector.close()
    else:
        log.info(color.success(f"   ✅ Tutti i {len(days)} giorni trovati in cache"))

    # 3. Aggrega e Scrivi
    if not cached_data:
        log.warning(f"⚠️ Nessun dato disponibile per {year}-{month:02d}")
        return 0
        
    # Unisci tutti i prezzi
    all_prices = []
    for day_data in cached_data:
        all_prices.extend(day_data.get('prices', []))
        
    # Parse e Scrivi
    parser = create_parser()
    
    # 1. Parse hourly points
    # Ricostruiamo un oggetto gme_data fittizio per usare parser.parse()
    month_data_combined = {
        'date': f"{year}-{month:02d}-01", 
        'prices': all_prices,
        'source': 'GME',
        'market': 'MGP'
    }
    hourly_points = parser.parse(month_data_combined)
    
    if not hourly_points:
        log.warning(f"⚠️ Nessun punto generato per {year}-{month:02d}")
        return 0
        
    # 2. Calculate monthly average
    pun_values = [p.get('pun_kwh') for p in all_prices if p.get('pun_kwh') is not None]
    monthly_avg_point = parser.create_monthly_avg_point(pun_values, datetime(year, month, 1))
    
    log.info(color.dim(f"   Generati {len(hourly_points)} punti orari + {1 if monthly_avg_point else 0} media mensile"))
    
    with InfluxWriter() as writer:
        # Scrivi punti orari
        writer.write_points(hourly_points, measurement_type="gme_prices")
        # Scrivi media mensile
        if monthly_avg_point:
            writer.write_points([monthly_avg_point], measurement_type="gme_monthly_avg")
        
    log.info(color.success(f"✅ GME {year}-{month:02d} completato"))
    return 0
