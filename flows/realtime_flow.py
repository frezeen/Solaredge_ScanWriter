from typing import Dict, Any
from logging import Logger
from cache.cache_manager import CacheManager
from collector.collector_realtime import RealtimeCollector
from parser.parser_realtime import RealtimeParser
from filtro.regole_filtraggio import filter_structured_points
from storage.writer_influx import InfluxWriter
from utils.color_logger import color

def run_realtime_flow(log: Logger, cache: CacheManager, config: Dict[str, Any]) -> int:
    """Pipeline realtime: collector → parser → filtro → writer (coerente con altri flussi)"""
    log.info(color.bold("🚀 Avvio flusso realtime"))
    
    try:
        # Step 1: Collector - raccolta dati raw (dizionario)
        collector = RealtimeCollector()
        raw_data = collector.collect_raw_data()
        
        if not raw_data:
            log.error("Collector non ha restituito dati raw")
            return 1
        
        log.info("✅ Collector: dati raw raccolti")
        
        # Step 2: Parser - elabora dati raw → struttura dati
        parser = RealtimeParser()
        structured_points = parser.parse_raw_data(raw_data)
        
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
