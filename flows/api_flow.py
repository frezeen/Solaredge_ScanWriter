import os
from typing import Optional, Dict, Any
from logging import Logger
from cache.cache_manager import CacheManager
from collector.collector_api import CollectorAPI
from parser.api_parser import create_parser
from storage.writer_influx import InfluxWriter
from scheduler.scheduler_loop import SchedulerLoop, SchedulerConfig
from utils.color_logger import color

def run_api_flow(
    log: Logger,
    cache: CacheManager,
    config: Dict[str, Any]
) -> int:
    """Pipeline API semplificata"""
    log.info("[FLOW:API:START]")
    log.info(color.bold("🚀 Avvio flusso API"))

    # Inizializza scheduler
    scheduler_config = SchedulerConfig.from_config(config)
    scheduler = SchedulerLoop(scheduler_config)

    # Raccolta dati con scheduler (usa context manager per session pooling)
    with CollectorAPI(cache=cache, scheduler=scheduler) as collector:

        # Raccolta dati (scheduler gestito internamente dal collector)
        try:
            raw_data = collector.collect()
        except KeyboardInterrupt:
            log.info("🛑 Interruzione utente durante raccolta dati API")
            log.info("[FLOW:API:STOP]")
            raise  # Propaga l'interruzione
        except ImportError as e:
            log.error(f"❌ Modulo API mancante: {e}. Verifica installazione dipendenze")
            log.info("[FLOW:API:STOP]")
            raise
        except ConnectionError as e:
            log.error(f"❌ Errore connessione API SolarEdge: {e}. Verifica rete e credenziali")
            log.info("[FLOW:API:STOP]")
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
            log.info(color.dim(f"   🔄 Processando {len(influx_points)} InfluxDB Points da API (o cache) per scrittura DB"))
        else:
            log.warning(color.warning("   ⚠️ Nessun punto generato dal parser - possibile problema con dati da cache"))

        # Storage diretto - nessuna elaborazione nel writer
        if influx_points:
            with InfluxWriter() as writer:
                writer.write_points(influx_points, measurement_type="api")
        else:
            log.warning(color.warning("   Nessun punto da scrivere"))

    log.info("[FLOW:API:STOP]")
    return 0
