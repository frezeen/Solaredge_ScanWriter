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
        """Parse dati raw da dizionario strutturato."""
        start_time = time.perf_counter()
        parsed_data = []
        
        if not raw_data:
            raise ValueError("Dati raw vuoti o None")
            
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
                                # Per tutti gli altri scale (0, -1, -2, etc.), usa scaling standard
                                final_value = value * (10 ** scale)
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
                        
                    # Mappa speciale per scale factor che non seguono pattern standard
                    # Esempio: import_energy_active -> energy_active_scale
                    special_scale_keys = {
                        'import_energy_active': 'energy_active_scale',
                        'export_energy_active': 'energy_active_scale',
                        'l1_import_energy_active': 'energy_active_scale',
                        'l2_import_energy_active': 'energy_active_scale',
                        'l3_import_energy_active': 'energy_active_scale',
                        'l1_export_energy_active': 'energy_active_scale',
                        'l2_export_energy_active': 'energy_active_scale',
                        'l3_export_energy_active': 'energy_active_scale',
                        
                        'import_energy_apparent': 'energy_apparent_scale',
                        'export_energy_apparent': 'energy_apparent_scale',
                        'l1_import_energy_apparent': 'energy_apparent_scale',
                        'l2_import_energy_apparent': 'energy_apparent_scale',
                        'l3_import_energy_apparent': 'energy_apparent_scale',
                        'l1_export_energy_apparent': 'energy_apparent_scale',
                        'l2_export_energy_apparent': 'energy_apparent_scale',
                        'l3_export_energy_apparent': 'energy_apparent_scale',
                        
                        'import_energy_reactive_q1': 'energy_reactive_scale',
                        'import_energy_reactive_q2': 'energy_reactive_scale',
                        'export_energy_reactive_q3': 'energy_reactive_scale',
                        'export_energy_reactive_q4': 'energy_reactive_scale',
                        'l1_import_energy_reactive_q1': 'energy_reactive_scale',
                        'l1_import_energy_reactive_q2': 'energy_reactive_scale',
                        'l1_export_energy_reactive_q3': 'energy_reactive_scale',
                        'l1_export_energy_reactive_q4': 'energy_reactive_scale',
                        'l2_import_energy_reactive_q1': 'energy_reactive_scale',
                        'l2_import_energy_reactive_q2': 'energy_reactive_scale',
                        'l2_export_energy_reactive_q3': 'energy_reactive_scale',
                        'l2_export_energy_reactive_q4': 'energy_reactive_scale',
                        'l3_import_energy_reactive_q1': 'energy_reactive_scale',
                        'l3_import_energy_reactive_q2': 'energy_reactive_scale',
                        'l3_export_energy_reactive_q3': 'energy_reactive_scale',
                        'l3_export_energy_reactive_q4': 'energy_reactive_scale',
                        
                        'voltage_ln': 'voltage_scale',
                        'l1n_voltage': 'voltage_scale',
                        'l2n_voltage': 'voltage_scale',
                        'l3n_voltage': 'voltage_scale',
                        'voltage_ll': 'voltage_scale',
                        'l12_voltage': 'voltage_scale',
                        'l23_voltage': 'voltage_scale',
                        'l31_voltage': 'voltage_scale',
                        
                        'frequency': 'frequency_scale',
                        
                        'power': 'power_scale',
                        'l1_power': 'power_scale',
                        'l2_power': 'power_scale',
                        'l3_power': 'power_scale',
                        
                        'power_apparent': 'power_apparent_scale',
                        'l1_power_apparent': 'power_apparent_scale',
                        'l2_power_apparent': 'power_apparent_scale',
                        'l3_power_apparent': 'power_apparent_scale',
                        
                        'power_reactive': 'power_reactive_scale',
                        'l1_power_reactive': 'power_reactive_scale',
                        'l2_power_reactive': 'power_reactive_scale',
                        'l3_power_reactive': 'power_reactive_scale',
                        
                        'power_factor': 'power_factor_scale',
                        'l1_power_factor': 'power_factor_scale',
                        'l2_power_factor': 'power_factor_scale',
                        'l3_power_factor': 'power_factor_scale',
                        
                        'current': 'current_scale',
                        'l1_current': 'current_scale',
                        'l2_current': 'current_scale',
                        'l3_current': 'current_scale'
                    }
                        
                    scale_key = special_scale_keys.get(clean_key, f"{key}_scale")
                    scale = data.get(scale_key)
                    
                    # Fallback: se non trovato, prova con suffisso _scale standard
                    if scale is None and f"{key}_scale" in data:
                        scale = data.get(f"{key}_scale")
                    
                    # DEBUG GENERALE: Logga tutto per capire cosa arriva
                    # if 'energy' in clean_key and 'scale' not in clean_key:
                    #      print(f"DEBUG ALL: {clean_key} raw={value} scale_key={scale_key} scale={scale}", flush=True)

                    final_value = value
                    # Get unit from config if available
                    measurement_config = enabled_measurements.get(clean_key, {})
                    unit = measurement_config.get('unit', '')
                    # Normalizza unità (C → °C, F → °F)
                    unit = self._unit_normalization.get(unit, unit)
                    
                    if isinstance(value, (int, float)) and scale is not None:
                        try:
                            if scale == -32768: continue
                            
                            # ENERGY COUNTERS: Compensazione sistematica per bug firmware
                            # Il meter sembra riportare sistematicamente uno scale factor errato di 2 ordini di grandezza.
                            # Esempio noto: Report scale=1 (x10), ma reale è /10 (x0.1) -> Differenza 10^2
                            # Esempio osservato: Report scale=-2 (x0.01), ma valori troppo alti -> Probabile reale -4 (x0.0001)
                            # Soluzione: Applicare sempre (scale - 2) per i contatori di energia
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
                                # Applica correzione sistematica: scale - 2
                                # scale=1 -> -1 (x0.1)
                                # scale=-2 -> -4 (x0.0001)
                                corrected_scale = scale - 2
                                final_value = value * (10 ** corrected_scale)
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
