"""writer_influx.py - Clean InfluxDB Writer (refactored)
Responsabilità unica: Scrivere Point objects su InfluxDB
Tutta l'elaborazione dati è stata spostata nei parser
"""

from __future__ import annotations
from typing import List, Union, Any
import os
import json
from pathlib import Path
from app_logging import get_logger
from config.config_manager import get_config_manager

try:
    from influxdb_client import InfluxDBClient, Point, WriteOptions
    INFLUX_CLIENT_AVAILABLE = True
except ImportError:
    INFLUX_CLIENT_AVAILABLE = False
    Point = None


class InfluxWriter:
    """Writer InfluxDB pulito - solo scrittura, nessuna elaborazione"""

    def __init__(self):
        """Inizializza InfluxWriter con bucket unificato."""
        self._log = get_logger("storage.influx_writer")
        
        if not INFLUX_CLIENT_AVAILABLE:
            raise RuntimeError("InfluxWriter: influxdb-client package non installato")
        
        self._config_manager = get_config_manager()
        self._influx_config = self._config_manager.get_influxdb_config()
        self._init_client()



    def _init_client(self):
        """Inizializza client InfluxDB ottimizzato"""
        try:
            # Verifica configurazione richiesta
            if not all([self._influx_config.url, self._influx_config.token, 
                       self._influx_config.org, self._influx_config.bucket]):
                raise RuntimeError("InfluxWriter: configurazione InfluxDB incompleta")
            
            self._client = InfluxDBClient(
                url=self._influx_config.url, 
                token=self._influx_config.token, 
                org=self._influx_config.org
            )
            
            # Test connessione
            health = self._client.health()
            if health.status != "pass":
                raise RuntimeError(f"InfluxDB health check failed: {health.message}")
            
            # Assicura esistenza bucket
            self._ensure_bucket_exists()
            
            # Write API con configurazione ottimizzata
            write_options = WriteOptions(
                batch_size=self._influx_config.batch_size,
                flush_interval=self._influx_config.flush_interval_ms,
                jitter_interval=self._influx_config.jitter_interval_ms,
                retry_interval=self._influx_config.retry_interval_ms,
                max_retries=self._influx_config.max_retries
            )
            self._write_api = self._client.write_api(write_options=write_options)
            
            self._log.info(f"InfluxWriter inizializzato: {self._influx_config.url}, bucket={self._influx_config.bucket}")
            
        except Exception as e:
            raise RuntimeError(f"InfluxWriter: errore inizializzazione - {e}")

    def _ensure_bucket_exists(self):
        """Crea bucket se non esistono"""
        try:
            buckets_api = self._client.buckets_api()
            
            # Bucket principale (API/Web)
            if not buckets_api.find_buckets(name=self._influx_config.bucket).buckets:
                buckets_api.create_bucket(bucket_name=self._influx_config.bucket, org=self._influx_config.org, retention_rules=[])
                self._log.info(f"Bucket principale creato: {self._influx_config.bucket}")
            
            # Bucket realtime (se diverso dal principale)
            if (self._influx_config.bucket_realtime != self._influx_config.bucket and 
                not buckets_api.find_buckets(name=self._influx_config.bucket_realtime).buckets):
                
                # Retention di 2 giorni (172800 secondi)
                from influxdb_client import BucketRetentionRules
                retention_rules = BucketRetentionRules(type="expire", every_seconds=172800)
                
                buckets_api.create_bucket(
                    bucket_name=self._influx_config.bucket_realtime, 
                    org=self._influx_config.org, 
                    retention_rules=[retention_rules]
                )
                self._log.info(f"Bucket realtime creato con retention 2 giorni: {self._influx_config.bucket_realtime}")
                
        except Exception as e:
            raise RuntimeError(f"Errore creazione bucket: {e}")

    def _write_dry_run(self, points: List[Point]):
        """Modalità dry-run per debug"""
        path = Path(self._influx_config.dry_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with path.open("a", encoding="utf-8") as f:
            for point in points:
                if hasattr(point, 'to_line_protocol'):
                    f.write(point.to_line_protocol() + "\n")
                else:
                    # Fallback per dict (compatibilità)
                    f.write(json.dumps(point) + "\n")
        
        self._log.info(f"DRY-RUN: {len(points)} punti scritti su {self._influx_config.dry_file}")

    def _get_bucket_for_measurement(self, measurement: str) -> str:
        """Determina il bucket corretto in base al measurement.
        
        Args:
            measurement: Nome del measurement
            
        Returns:
            Nome del bucket da utilizzare
        """
        if measurement == "realtime":
            return self._influx_config.bucket_realtime
        else:
            # API e Web vanno nel bucket principale
            return self._influx_config.bucket

    def write_points(self, points: List[Union[Point, Any]], measurement_type: str = None):
        """Scrive Point objects su InfluxDB con bucket appropriato
        
        Args:
            points: Lista di InfluxDB Point objects pronti per scrittura
            measurement_type: Tipo di measurement per determinare il bucket (opzionale)
            
        Note:
            - Accetta solo Point objects (elaborazione fatta nei parser)
            - Supporta fallback per dict (compatibilità temporanea)
            - Usa bucket diversi per realtime (2 giorni) vs API/Web (retention default)
        """
        if not points:
            self._log.warning("Lista punti vuota")
            return
        
        # Filtra solo Point objects validi + compatibilità dict
        valid_points = []
        for point in points:
            if hasattr(point, 'to_line_protocol'):
                # Point object InfluxDB
                valid_points.append(point)
            elif isinstance(point, dict) and all(k in point for k in ['measurement', 'fields']):
                # Fallback per dict (compatibilità con parser che restituiscono dict)
                self._log.debug("Ricevuto dict invece di Point object - conversione automatica")
                valid_points.append(point)
        
        if not valid_points:
            raise RuntimeError("Nessun Point object valido da scrivere")
        
        if self._influx_config.dry_mode:
            self._write_dry_run(valid_points)
            return
        
        # Raggruppa punti per bucket
        points_by_bucket = {}
        
        for point in valid_points:
            # Determina measurement dal point
            if hasattr(point, '_name'):
                measurement = point._name
            elif isinstance(point, dict) and 'measurement' in point:
                measurement = point['measurement']
            elif measurement_type:
                measurement = measurement_type
            else:
                # Fallback al bucket principale
                measurement = "api"
            
            bucket = self._get_bucket_for_measurement(measurement)
            
            if bucket not in points_by_bucket:
                points_by_bucket[bucket] = []
            points_by_bucket[bucket].append(point)
        
        # Log dettagliato per debugging
        self._log.debug(f"📊 Distribuzione punti per bucket:")
        for bucket, bucket_points in points_by_bucket.items():
            self._log.debug(f"  • {bucket}: {len(bucket_points)} punti")
        
        try:
            # Scrivi su ogni bucket
            total_written = 0
            for bucket, bucket_points in points_by_bucket.items():
                self._write_api.write(bucket=bucket, org=self._influx_config.org, record=bucket_points)
                total_written += len(bucket_points)
                self._log.info(f"✅ Scritti {len(bucket_points)} punti su bucket {bucket}")
            
            self._write_api.flush()
            self._log.info(f"✅ Totale scritti {total_written} punti su {len(points_by_bucket)} bucket")
            
        except Exception as e:
            self._log.error(f"Errore scrittura InfluxDB: {e}")
            raise RuntimeError(f"InfluxWriter: errore scrittura - {e}")

    def close(self):
        """Chiude client InfluxDB"""
        if hasattr(self, '_write_api') and self._write_api:
            self._write_api.close()
        if hasattr(self, '_client') and self._client:
            self._client.close()
        self._log.debug("InfluxWriter chiuso")

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


__all__ = ["InfluxWriter"]
