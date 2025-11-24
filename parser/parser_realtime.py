#!/usr/bin/env python3
"""Parser per output formattato realtime SolarEdge."""

import re
import time
from typing import List
from datetime import datetime, timezone
from influxdb_client import Point
from app_logging import get_logger
from config.config_manager import get_config_manager


class RealtimeParser:
    """Parser per output formattato realtime."""
    
    def __init__(self):
        self._log = get_logger(__name__)
        self._config_manager = get_config_manager()
        
        # Carica configurazione endpoints modbus
        try:
            self._modbus_endpoints = self._config_manager.get_modbus_endpoints()
        except Exception as e:
            self._log.error(f"Errore caricamento configurazione modbus: {e}")
            raise
            
        # Cache per device_id dinamici
        self._cached_device_ids = {
            'inverter': None,
            'meters': {},
            'batteries': {}
        }
        
        # Mappa di normalizzazione unità (abbreviazioni → forma completa)
        self._unit_normalization = {
            'C': '°C',
            'F': '°F'
        }
    
    def _get_enabled_measurements(self, endpoint_config: dict) -> dict:
        """Ottieni measurements abilitati da configurazione endpoint.
        
        Args:
            endpoint_config: Configurazione endpoint (inverter_realtime, meters, batteries)
            
        Returns:
            Dizionario con measurements abilitati {measurement_name: config}
        """
        measurements = endpoint_config.get('measurements', {})
        return {name: config for name, config in measurements.items() 
                if config.get('enabled', False)}

    def parse_raw_data(self, raw_data: dict) -> List[Point]:
        """Parse dati raw (dizionario) e restituisce Point objects InfluxDB."""
        start_time = time.perf_counter()
        
        if not raw_data:
            raise ValueError("Dati raw vuoti o None")
            
        parsed_data = []
        
        if "inverter" in raw_data:
            parsed_data.extend(self._parse_inverter_raw(raw_data["inverter"]))
            
        if "meters" in raw_data:
            parsed_data.extend(self._parse_meters_raw(raw_data["meters"]))
            
        if "batteries" in raw_data:
            parsed_data.extend(self._parse_batteries_raw(raw_data["batteries"]))
            
        duration_ms = (time.perf_counter() - start_time) * 1000
        self._log.info(f"Parsing raw completato: {len(parsed_data)} punti", extra={
            "points_count": len(parsed_data),
            "duration_ms": f"{duration_ms:.2f}"
        })
        return parsed_data

    def _parse_inverter_raw(self, data: dict) -> List[Point]:
        """Parse dati raw inverter."""
        try:
            endpoints = self._modbus_endpoints.get('endpoints', {})
            inverter_config = endpoints.get('inverter_realtime', {})
            
            if not inverter_config.get('enabled', False):
                return []
                
            # Usa c_model dai dati, o cache, o device_name da config, o fallback a 'Unknown'
            current_model = data.get('c_model')
            if current_model:
                self._cached_device_ids['inverter'] = current_model
                device_id = current_model
            else:
                device_id = self._cached_device_ids['inverter'] or inverter_config.get('device_name') or 'Unknown'
            enabled_measurements = self._get_enabled_measurements(inverter_config)
            
            points = []
            
            for key, value in data.items():
                clean_key = key[2:] if key.startswith('c_') else key
                
                if enabled_measurements and clean_key not in enabled_measurements:
                    continue
                
                # Use automatic Title Case conversion for endpoint name
                endpoint_name = clean_key.replace('_', ' ').title()
                
                scale_key = f"{key}_scale"
                scale = data.get(scale_key)
                
                final_value = value
                # Get unit from config if available
                measurement_config = enabled_measurements.get(clean_key, {})
                unit = measurement_config.get('unit', '')
                # Normalizza unità (C → °C, F → °F)
                unit = self._unit_normalization.get(unit, unit)
                
                if isinstance(value, (int, float)) and scale is not None:
                    try:
                        if scale == -32768: continue
                        
                        # ENERGY COUNTER: Compensazione per bug firmware
                        # Documentazione: energy_total_scale dovrebbe essere 0
                        # Se scale=1, dividi per 10 per compensare
                        if clean_key == 'energy_total':
                            if scale == 1:
                                final_value = value / 10
                            else:
                                final_value = value
                        else:
                            final_value = value * (10 ** scale)
                    except: continue
                
                if isinstance(final_value, (int, float)):
                    point = Point("realtime") \
                        .tag("device_id", device_id) \
                        .tag("endpoint", endpoint_name) \
                        .tag("unit", unit) \
                        .field("Inverter", float(final_value)) \
                        .time(datetime.now(timezone.utc))
                    points.append(point)
                else:
                    point = Point("realtime") \
                        .tag("device_id", device_id) \
                        .tag("endpoint", endpoint_name) \
                        .tag("unit", unit) \
                        .field("Inverter_Text", str(final_value)) \
                        .time(datetime.now(timezone.utc))
                    points.append(point)
                    
            return points
        except Exception as e:
            self._log.error(f"Errore parsing raw inverter: {e}")
            return []

    def _parse_meters_raw(self, meters_data: dict) -> List[Point]:
        """Parse dati raw meters."""
        points = []
        try:
            endpoints = self._modbus_endpoints.get('endpoints', {})
            meters_config = endpoints.get('meters', {})
            
            if not meters_config.get('enabled', False):
                return []
                
            enabled_measurements = self._get_enabled_measurements(meters_config)
            
            for meter_name, data in meters_data.items():
                serial = data.get('c_serialnumber')
                if serial:
                    device_id = f"meter_{serial}"
                    self._cached_device_ids['meters'][meter_name] = device_id
                else:
                    # Prova a usare cache o model
                    current_model = data.get('c_model')
                    if current_model:
                        device_id = current_model
                        self._cached_device_ids['meters'][meter_name] = device_id
                    else:
                        device_id = self._cached_device_ids['meters'].get(meter_name) or meter_name
                
                for key, value in data.items():
                    clean_key = key[2:] if key.startswith('c_') else key
                    
                    if enabled_measurements and clean_key not in enabled_measurements:
                        continue
                        
                    endpoint_name = clean_key.replace('_', ' ').title()
                        
                    scale_key = f"{key}_scale"
                    scale = data.get(scale_key)
                    
                    final_value = value
                    # Get unit from config if available
                    measurement_config = enabled_measurements.get(clean_key, {})
                    unit = measurement_config.get('unit', '')
                    # Normalizza unità (C → °C, F → °F)
                    unit = self._unit_normalization.get(unit, unit)
                    
                    if isinstance(value, (int, float)) and scale is not None:
                        try:
                            if scale == -32768: continue
                            
                            # ENERGY COUNTERS: Compensazione per bug firmware meter
                            # Documentazione solaredge_modbus: energy_total_scale dovrebbe essere 0
                            # Ma alcuni meter riportano scale=1, causando moltiplicazione x10
                            # Soluzione: se scale=1 per contatori energia, dividi per 10
                            energy_counters = [
                                'import_energy_active', 'export_energy_active',
                                'import_energy_apparent', 'export_energy_apparent',
                                'import_energy_reactive_q1', 'import_energy_reactive_q2',
                                'export_energy_reactive_q3', 'export_energy_reactive_q4',
                                # L1
                                'l1_import_energy_active', 'l1_export_energy_active',
                                'l1_import_energy_apparent', 'l1_export_energy_apparent',
                                'l1_import_energy_reactive_q1', 'l1_import_energy_reactive_q2',
                                'l1_export_energy_reactive_q3', 'l1_export_energy_reactive_q4',
                                # L2
                                'l2_import_energy_active', 'l2_export_energy_active',
                                'l2_import_energy_apparent', 'l2_export_energy_apparent',
                                'l2_import_energy_reactive_q1', 'l2_import_energy_reactive_q2',
                                'l2_export_energy_reactive_q3', 'l2_export_energy_reactive_q4',
                                # L3
                                'l3_import_energy_active', 'l3_export_energy_active',
                                'l3_import_energy_apparent', 'l3_export_energy_apparent',
                                'l3_import_energy_reactive_q1', 'l3_import_energy_reactive_q2',
                                'l3_export_energy_reactive_q3', 'l3_export_energy_reactive_q4'
                            ]
                            
                            if clean_key in energy_counters:
                                # Se scale=1, il meter sta riportando valore x10 (bug firmware)
                                # Dividi per 10 per compensare
                                if scale == 1:
                                    final_value = value / 10
                                else:
                                    # Se scale=0 (corretto), usa valore raw
                                    final_value = value
                            else:
                                # Altri valori: usa scaling normale
                                final_value = value * (10 ** scale)
                        except: continue
                    
                    if isinstance(final_value, (int, float)):
                        point = Point("realtime") \
                            .tag("device_id", device_id) \
                            .tag("endpoint", endpoint_name) \
                            .tag("unit", unit) \
                            .field("Meter", float(final_value)) \
                            .time(datetime.now(timezone.utc))
                        points.append(point)
                    else:
                        point = Point("realtime") \
                            .tag("device_id", device_id) \
                            .tag("endpoint", endpoint_name) \
                            .tag("unit", unit) \
                            .field("Meter_Text", str(final_value)) \
                            .time(datetime.now(timezone.utc))
                        points.append(point)
        except Exception as e:
            self._log.error(f"Errore parsing raw meters: {e}")
            
        return points

    def _parse_batteries_raw(self, batteries_data: dict) -> List[Point]:
        """Parse dati raw batteries."""
        points = []
        try:
            endpoints = self._modbus_endpoints.get('endpoints', {})
            batteries_config = endpoints.get('batteries', {})
            
            if not batteries_config.get('enabled', False):
                return []
                
            enabled_measurements = self._get_enabled_measurements(batteries_config)
            
            for battery_name, data in batteries_data.items():
                current_model = data.get('c_model')
                if current_model:
                    device_id = current_model
                    self._cached_device_ids['batteries'][battery_name] = device_id
                else:
                    device_id = self._cached_device_ids['batteries'].get(battery_name) or battery_name
                
                for key, value in data.items():
                    clean_key = key[2:] if key.startswith('c_') else key
                    
                    if enabled_measurements and clean_key not in enabled_measurements:
                        if enabled_measurements: 
                            continue
                            
                    endpoint_name = clean_key.replace('_', ' ').title()
                            
                    scale_key = f"{key}_scale"
                    scale = data.get(scale_key)
                    
                    final_value = value
                    # Get unit from config if available
                    measurement_config = enabled_measurements.get(clean_key, {})
                    unit = measurement_config.get('unit', '')
                    # Normalizza unità (C → °C, F → °F)
                    unit = self._unit_normalization.get(unit, unit)
                    
                    if isinstance(value, (int, float)) and scale is not None:
                        try:
                            if scale == -32768: continue
                            final_value = value * (10 ** scale)
                        except: continue
                    
                    if isinstance(final_value, (int, float)):
                        point = Point("realtime") \
                            .tag("device_id", device_id) \
                            .tag("endpoint", endpoint_name) \
                            .tag("unit", unit) \
                            .field("Battery", float(final_value)) \
                            .time(datetime.now(timezone.utc))
                        points.append(point)
                    else:
                        point = Point("realtime") \
                            .tag("device_id", device_id) \
                            .tag("endpoint", endpoint_name) \
                            .tag("unit", unit) \
                            .field("Battery_Text", str(final_value)) \
                            .time(datetime.now(timezone.utc))
                        points.append(point)
        except Exception as e:
            self._log.error(f"Errore parsing raw batteries: {e}")
            
        return points
