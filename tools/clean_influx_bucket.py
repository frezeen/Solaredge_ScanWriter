"""clean_influx_bucket.py
Script per cancellazione dati InfluxDB bucket per test con dati freschi.
Sorgente: web_scraping (bucket API+WEB).
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

# Aggiungi path progetto per import
sys.path.insert(0, str(Path(__file__).parent.parent))

# Carica .env (FLUSSO_CONFIG)
from config.env_loader import load_env
load_env()

from app_logging import get_logger
from config.config_manager import get_config_manager

try:
    from influxdb_client import InfluxDBClient
    from influxdb_client.client.delete_api import DeleteApi
    from datetime import datetime, timezone
    INFLUX_CLIENT_AVAILABLE = True
except ImportError:
    INFLUX_CLIENT_AVAILABLE = False

def clean_bucket() -> None:
    """Cancella tutti i dati nel bucket API+WEB per test con dati freschi.
    
    STORAGE_INFLUX_REGOLE: bucket API+WEB utilizzato da web_scraping.
    ESECUZIONE_STRICT_NO_FALLBACK: se configurazione mancante -> stop.
    """
    log = get_logger("tools.clean_influx_bucket")
    
    # Configurazione da ConfigManager
    config_manager = get_config_manager()
    influx_config = config_manager.get_influxdb_config()
    
    if not all([influx_config.url, influx_config.org, influx_config.bucket, influx_config.token]):
        raise RuntimeError("clean_bucket: configurazione InfluxDB incompleta - stop")
    
    url = influx_config.url
    org = influx_config.org
    bucket = influx_config.bucket
    token = influx_config.token
        
    if not INFLUX_CLIENT_AVAILABLE:
        raise RuntimeError("clean_bucket: influxdb-client package non installato - stop")
    
    try:
        with InfluxDBClient(url=url, token=token, org=org) as client:
            # Test connessione
            health = client.health()
            if health.status != "pass":
                raise RuntimeError(f"InfluxDB health check failed: {health.message}")
            
            # Delete API per cancellazione dati
            delete_api = client.delete_api()
            
            # Cancella tutti i dati dal 1970 ad oggi (tutto il bucket)
            start = datetime(1970, 1, 1, tzinfo=timezone.utc)
            stop = datetime.now(timezone.utc)
            
            log.info("Cancellazione dati bucket=%s dal %s al %s", bucket, start, stop)
            
            delete_api.delete(
                start=start,
                stop=stop,
                predicate='',  # Predicate vuoto = cancella tutto
                bucket=bucket,
                org=org
            )
            
            log.info("Bucket %s pulito con successo - dati freschi per prossima scrittura", bucket)
            # ✅ Bucket pulito - ready per dati freschi
            
    except Exception as e:
        log.error("Errore cancellazione bucket: %s", e)
        raise RuntimeError(f"clean_bucket: errore cancellazione - {e}")

def main() -> int:
    """Entry point script."""
    log = get_logger("tools.clean_influx_bucket")
    try:
        clean_bucket()
        return 0
    except Exception as e:
        log.error("❌ Errore esecuzione script: %s", e)
        return 1

if __name__ == "__main__":
    sys.exit(main())
