#!/usr/bin/env python3
"""Collector Realtime per SolarEdge via Modbus TCP."""

import time
from contextlib import contextmanager
from typing import Optional
from io import StringIO

import solaredge_modbus
from config.config_manager import get_config_manager
from app_logging import get_logger


@contextmanager
def timed_operation(logger, operation_name: str):
    """Context manager per misurare durata operazioni.
    
    Args:
        logger: Logger per output timing
        operation_name: Nome operazione da loggare
        
    Yields:
        None
        
    Example:
        >>> with timed_operation(logger, "modbus_read"):
        ...     data = inverter.read_all()
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.debug(f"{operation_name}", extra={
            "duration_ms": f"{duration_ms:.2f}",
            "operation": operation_name
        })


class RealtimeCollector:
    """Collector realtime via Modbus TCP."""
    
    def __init__(self):
        self._log = get_logger(__name__)
        self._config_manager = get_config_manager()
        self._realtime_config = self._config_manager.get_realtime_config()
        
        # Carica configurazione endpoints modbus
        try:
            self._modbus_endpoints = self._config_manager.get_modbus_endpoints()
            if not self._modbus_endpoints.get('enabled', False):
                raise ValueError("Modbus collection disabilitato nella configurazione")
        except Exception as e:
            self._log.error(f"Errore caricamento configurazione modbus: {e}")
            raise
        
        self._log.debug(f"RealtimeCollector: {self._realtime_config.host}:{self._realtime_config.port}")
        self._log.debug(f"Endpoints abilitati: {self._get_enabled_endpoints_summary()}")
    
    def _get_enabled_endpoints_summary(self) -> str:
        """Restituisce riassunto degli endpoints abilitati.
        
        Returns:
            Stringa con conteggio endpoints abilitati per tipo
        """
        endpoints = self._modbus_endpoints.get('endpoints', {})
        enabled_count = {}
        
        for endpoint_name, endpoint_config in endpoints.items():
            if endpoint_config.get('enabled', False):
                device_type = endpoint_config.get('device_type', 'Unknown')
                enabled_count[device_type] = enabled_count.get(device_type, 0) + 1
        
        return ', '.join(f"{device_type}: {count}" for device_type, count in enabled_count.items())

    def collect_raw_data(self) -> dict:
        """Raccoglie dati raw (dizionario) dal dispositivo Modbus.
        
        Returns:
            Dizionario con dati grezzi (inverter, meters, batteries)
        """
        try:
            with timed_operation(self._log, "realtime_collection_raw"):
                return self._fetch_raw_data(
                    self._realtime_config.host,
                    self._realtime_config.port
                )
        except Exception as e:
            self._log.error(f"Errore raccolta dati raw: {e}")
            raise RuntimeError(f"Errore durante raccolta dati raw: {e}") from e

    def _fetch_raw_data(self, host: str, port: int) -> dict:
        """Esegue lettura Modbus e restituisce dizionario dati."""
        try:
            inverter = solaredge_modbus.Inverter(
                host=host,
                port=port,
                timeout=self._realtime_config.timeout,
                unit=self._realtime_config.unit
            )
            
            # Leggi tutti i dati disponibili
            values = inverter.read_all()
            meters = inverter.meters()
            batteries = inverter.batteries()
            
            # Struttura dati raw
            raw_data = {
                "inverter": values,
                "meters": {},
                "batteries": {}
            }
            
            # Controlla se meters sono abilitati nella configurazione
            endpoints = self._modbus_endpoints.get('endpoints', {})
            meters_enabled = endpoints.get('meters', {}).get('enabled', False)
            batteries_enabled = endpoints.get('batteries', {}).get('enabled', False)
            
            if meters_enabled:
                for meter, params in meters.items():
                    raw_data["meters"][meter] = params.read_all()
            
            if batteries_enabled:
                for battery, params in batteries.items():
                    raw_data["batteries"][battery] = params.read_all()
                    
            return raw_data
            
        except Exception as e:
            # self._log.error(f"Errore fetch raw data: {e}") # Evita doppio log se gestito dal chiamante
            raise
