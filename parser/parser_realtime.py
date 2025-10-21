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
    
    def parse_realtime_data(self, formatted_output: str) -> List[Point]:
        """Parse output formattato e restituisce Point objects InfluxDB.
        
        Args:
            formatted_output: Output testuale dal RealtimeCollector
            
        Returns:
            Lista di Point objects nativi InfluxDB
            
        Raises:
            ValueError: Se output vuoto o None
            TypeError: Se output non è una stringa
            
        Example:
            >>> parser = RealtimeParser()
            >>> output = "=== INVERTER REGISTERS ===\\n\\tModel: SE6000H\\n\\tPower: 2500W"
            >>> points = parser.parse_realtime_data(output)
            >>> assert len(points) > 0
            >>> assert hasattr(points[0], 'to_line_protocol')
        """
        start_time = time.perf_counter()
        
        if not formatted_output:
            raise ValueError("Output formattato vuoto o None")
        
        if not isinstance(formatted_output, str):
            raise TypeError(f"Expected str, got {type(formatted_output).__name__}")
        
        parsed_data = []
        parsed_data.extend(self._parse_inverter_section(formatted_output))
        parsed_data.extend(self._parse_meter_sections(formatted_output))
        parsed_data.extend(self._parse_battery_sections(formatted_output))
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        self._log.info(f"Parsing completato: {len(parsed_data)} punti", extra={
            "points_count": len(parsed_data),
            "duration_ms": f"{duration_ms:.2f}",
            "input_size_bytes": len(formatted_output)
        })
        return parsed_data
    
    def _parse_inverter_section(self, output: str) -> List[Point]:
        """Parse sezione INVERTER REGISTERS dall'output formattato.
        
        Estrae le metriche numeriche dalla sezione inverter,
        filtrando in base alla configurazione modbus_endpoints.yaml.
        
        Args:
            output: Output formattato completo dal collector
            
        Returns:
            Lista di Point objects InfluxDB per metriche inverter abilitate
            Lista vuota se sezione non trovata o errore parsing
            
        Example:
            >>> output = "=== INVERTER REGISTERS ===\\n\\tModel: SE6000H\\n\\tPower: 2500W"
            >>> points = parser._parse_inverter_section(output)
            >>> assert hasattr(points[0], 'to_line_protocol')
        """
        try:
            # Controlla se inverter è abilitato
            endpoints = self._modbus_endpoints.get('endpoints', {})
            inverter_config = endpoints.get('inverter_realtime', {})
            
            if not inverter_config.get('enabled', False):
                self._log.debug("Inverter disabilitato nella configurazione")
                return []
            
            inverter_match = re.search(r'=== INVERTER REGISTERS ===(.*?)(?:=== METERS|=== BATTERIES|=== SUMMARY|$)', 
                                     output, re.DOTALL)
            if not inverter_match:
                return []
            
            inverter_section = inverter_match.group(1)
            model_match = re.search(r'\tModel: (.+)', inverter_section)
            device_id = model_match.group(1) if model_match else "Unknown"
            
            # Ottieni measurements abilitati
            enabled_measurements = self._get_enabled_measurements(inverter_config)
            
            parsed_data = []
            for line in inverter_section.strip().split('\n'):
                if not line.strip() or not (line.startswith('\t') or line.startswith('    ')):
                    continue
                
                line = line.lstrip('\t ')
                if ':' not in line:
                    continue
                
                endpoint, value_part = line.split(':', 1)
                endpoint_clean = endpoint.strip()
                
                # Controlla se questa metrica è abilitata
                if not self._is_measurement_enabled(endpoint_clean, enabled_measurements):
                    continue
                
                value, unit = self._extract_value_and_unit(value_part.strip())
                
                # Processa tutte le metriche: numeriche e testuali
                if value is not None:
                    if isinstance(value, (int, float)):
                        # Valore numerico
                        point = Point("realtime") \
                            .tag("device_id", device_id) \
                            .tag("endpoint", endpoint_clean) \
                            .tag("unit", unit) \
                            .field("Inverter", float(value)) \
                            .time(datetime.now(timezone.utc))
                        parsed_data.append(point)
                    else:
                        # Valore testuale - usa field separato
                        point = Point("realtime") \
                            .tag("device_id", device_id) \
                            .tag("endpoint", endpoint_clean) \
                            .tag("unit", unit) \
                            .field("Inverter_Text", str(value)) \
                            .time(datetime.now(timezone.utc))
                        parsed_data.append(point)
            
            self._log.info(f"Inverter: {len(parsed_data)} metriche abilitate")
            return parsed_data
            
        except Exception as e:
            self._log.error(f"Errore parsing inverter: {e}")
            return []
    
    def _parse_meter_sections(self, output: str) -> List[Point]:
        """Parse sezioni METERS dall'output formattato.
        
        Estrae metriche da tutti i meter presenti, filtrando in base alla configurazione.
        
        Args:
            output: Output formattato completo dal collector
            
        Returns:
            Lista di Point objects InfluxDB per metriche meter abilitate
            Lista vuota se nessun meter trovato o disabilitato
            
        Example:
            >>> output = "=== METERS (1 found) ===\\n--- Meter 1 ---\\n\\tPower: 2131.7W"
            >>> points = parser._parse_meter_sections(output)
            >>> assert len(points) > 0
        """
        try:
            # Controlla se meters sono abilitati
            endpoints = self._modbus_endpoints.get('endpoints', {})
            meters_config = endpoints.get('meters', {})
            
            if not meters_config.get('enabled', False):
                self._log.debug("Meters disabilitati nella configurazione")
                return []
            
            meters_match = re.search(r'=== METERS.*?===(.*?)(?:=== BATTERIES|=== SUMMARY|$)', 
                                   output, re.DOTALL)
            if not meters_match:
                return []
            
            # Ottieni measurements abilitati
            enabled_measurements = self._get_enabled_measurements(meters_config)
            
            meters_section = meters_match.group(1)
            meter_matches = re.finditer(r'--- (.+?) ---(.*?)(?=--- |=== |$)', meters_section, re.DOTALL)
            
            parsed_data = []
            for meter_match in meter_matches:
                meter_name = meter_match.group(1)
                meter_content = meter_match.group(2)
                
                # Usa serial number per device_id unico, fallback su model o meter_name
                serial_match = re.search(r'Serial: (.+)', meter_content)
                model_match = re.search(r'Model: (.+)', meter_content)
                
                if serial_match:
                    device_id = f"meter_{serial_match.group(1)}"
                elif model_match:
                    device_id = model_match.group(1)
                else:
                    device_id = meter_name
                
                for line in meter_content.strip().split('\n'):
                    if not line.strip() or not (line.startswith('\t') or line.startswith('    ')):
                        continue
                    
                    line = line.lstrip('\t ')
                    if ':' not in line:
                        continue
                    
                    endpoint, value_part = line.split(':', 1)
                    endpoint_clean = endpoint.strip()
                    
                    # Controlla se questa metrica è abilitata
                    if not self._is_meter_measurement_enabled(endpoint_clean, enabled_measurements):
                        continue
                    
                    value, unit = self._extract_value_and_unit(value_part.strip())
                    
                    # Processa TUTTE le metriche: numeriche, alfanumeriche, N/A, etc.
                    if value is not None:
                        # Processa tutte le metriche: numeriche e testuali
                        if isinstance(value, (int, float)):
                            # Valore numerico
                            point = Point("realtime") \
                                .tag("device_id", device_id) \
                                .tag("endpoint", endpoint_clean) \
                                .tag("unit", unit) \
                                .field("Meter", float(value)) \
                                .time(datetime.now(timezone.utc))
                            parsed_data.append(point)
                        else:
                            # Valore testuale - usa field separato
                            point = Point("realtime") \
                                .tag("device_id", device_id) \
                                .tag("endpoint", endpoint_clean) \
                                .tag("unit", unit) \
                                .field("Meter_Text", str(value)) \
                                .time(datetime.now(timezone.utc))
                            parsed_data.append(point)
            
            self._log.info(f"Meter: {len(parsed_data)} metriche abilitate")
            return parsed_data
            
        except Exception as e:
            self._log.error(f"Errore parsing meters: {e}")
            return []
    
    def _parse_battery_sections(self, output: str) -> List[Point]:
        """Parse sezioni BATTERIES dall'output formattato.
        
        Estrae metriche da tutte le batterie presenti, filtrando in base alla configurazione.
        
        Args:
            output: Output formattato completo dal collector
            
        Returns:
            Lista di Point objects InfluxDB per metriche battery abilitate
            Lista vuota se nessuna batteria trovata o disabilitata
            
        Example:
            >>> output = "=== BATTERIES ===\\nNo batteries found"
            >>> points = parser._parse_battery_sections(output)
            >>> assert len(points) == 0
        """
        try:
            # Controlla se batteries sono abilitate
            endpoints = self._modbus_endpoints.get('endpoints', {})
            batteries_config = endpoints.get('batteries', {})
            
            if not batteries_config.get('enabled', False):
                self._log.debug("Batteries disabilitate nella configurazione")
                return []
            
            batteries_match = re.search(r'=== BATTERIES.*?===(.*?)(?:=== SUMMARY|$)', 
                                      output, re.DOTALL)
            if not batteries_match or "No batteries found" in batteries_match.group(1):
                return []
            
            # Ottieni measurements abilitati
            enabled_measurements = self._get_enabled_measurements(batteries_config)
            
            batteries_section = batteries_match.group(1)
            battery_matches = re.finditer(r'--- (.+?) ---(.*?)(?=--- |=== |$)', batteries_section, re.DOTALL)
            
            parsed_data = []
            for battery_match in battery_matches:
                battery_name = battery_match.group(1)
                battery_content = battery_match.group(2)
                
                model_match = re.search(r'\tModel: (.+)', battery_content)
                device_id = model_match.group(1) if model_match else battery_name
                
                for line in battery_content.strip().split('\n'):
                    if not line.strip() or not (line.startswith('\t') or line.startswith('    ')):
                        continue
                    
                    line = line.lstrip('\t ')
                    if ':' not in line:
                        continue
                    
                    endpoint, value_part = line.split(':', 1)
                    endpoint_clean = endpoint.strip()
                    
                    # Per le batterie, accetta tutte le metriche numeriche se enabled_measurements è vuoto
                    # oppure controlla se la metrica specifica è abilitata
                    if enabled_measurements and not self._is_battery_measurement_enabled(endpoint_clean, enabled_measurements):
                        continue
                    
                    value, unit = self._extract_value_and_unit(value_part.strip())
                    
                    # Processa TUTTE le metriche: numeriche, alfanumeriche, N/A, etc.
                    if value is not None:
                        if isinstance(value, (int, float)):
                            # Valore numerico
                            point = Point("realtime") \
                                .tag("device_id", device_id) \
                                .tag("endpoint", endpoint_clean) \
                                .tag("unit", unit) \
                                .field("Battery", float(value)) \
                                .time(datetime.now(timezone.utc))
                            parsed_data.append(point)
                        else:
                            # Valore stringa/alfanumerico/N/A
                            point = Point("realtime") \
                                .tag("device_id", device_id) \
                                .tag("endpoint", endpoint_clean) \
                                .tag("unit", unit) \
                                .field("Battery_Text", str(value)) \
                                .time(datetime.now(timezone.utc))
                            parsed_data.append(point)
            
            if parsed_data:
                self._log.info(f"Battery: {len(parsed_data)} metriche abilitate")
            return parsed_data
            
        except Exception as e:
            self._log.error(f"Errore parsing batteries: {e}")
            return []
    
    def _extract_value_and_unit(self, value_part: str) -> tuple:
        """Estrae valore numerico e unità di misura da stringa formattata.
        
        Supporta formati: "100", "100.5", "100W", "100.5 kWh", "-50°C"
        Ritorna (None, "") per valori non numerici o "N/A".
        
        Args:
            value_part: Stringa con valore e unità opzionale
            
        Returns:
            Tupla (valore_numerico, unità) o (None, "") se non numerico
            
        Example:
            >>> parser._extract_value_and_unit("2500W")
            (2500, 'W')
            >>> parser._extract_value_and_unit("N/A")
            (None, '')
            >>> parser._extract_value_and_unit("SolarEdge")
            ('SolarEdge', '')
        """
        try:
            value_part = value_part.strip()
            if not value_part:
                return None, ""
            
            # Prova prima il pattern numerico
            numeric_pattern = r'^(-?\d+(?:\.\d+)?)\s*([A-Za-z°%]+)?$'
            match = re.match(numeric_pattern, value_part)
            if match:
                value_str = match.group(1)
                unit = match.group(2) or ""
                try:
                    value = float(value_str) if '.' in value_str else int(value_str)
                    return value, unit
                except ValueError:
                    pass
            
            # Se non è numerico, restituisci come stringa (inclusi N/A, nomi, etc.)
            return value_part, ""
            
        except Exception:
            return value_part, ""
    
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
    
    def _is_measurement_enabled(self, endpoint_name: str, enabled_measurements: dict) -> bool:
        """Controlla se una metrica è abilitata nella configurazione.
        
        Args:
            endpoint_name: Nome endpoint dal parsing (es: "Power", "Temperature")
            enabled_measurements: Measurements abilitati dalla configurazione
            
        Returns:
            True se metrica abilitata, False altrimenti
        """
        # Mappa nomi endpoint a nomi configurazione
        endpoint_mapping = {
            'Manufacturer': 'manufacturer',
            'Model': 'model', 
            'Type': 'type',  # Ora mappato
            'Version': 'version',
            'Serial': 'serial',
            'Status': 'status',  # Ora mappato
            'Temperature': 'temperature',
            'Current': 'current',
            'Phase 1 Current': 'l1_current',
            'Phase 2 Current': 'l2_current', 
            'Phase 3 Current': 'l3_current',
            'Phase 1 voltage': 'l1_voltage',
            'Phase 2 voltage': 'l2_voltage',
            'Phase 3 voltage': 'l3_voltage',
            'Phase 1-N voltage': 'l1n_voltage',
            'Phase 2-N voltage': 'l2n_voltage',
            'Phase 3-N voltage': 'l3n_voltage',
            'Voltage': 'l1_voltage',
            'Frequency': 'frequency',
            'Power': 'power_ac',
            'Power (Apparent)': 'power_apparent',
            'Power (Reactive)': 'power_reactive',
            'Power Factor': 'power_factor',
            'Total Energy': 'energy_total',
            'DC Current': 'current_dc',
            'DC Voltage': 'voltage_dc',
            'DC Power': 'power_dc',
            # Metriche aggiuntive inverter
            'Device Address': 'device_address',
            'SunSpec DID': 'sunspec_did',
            'SunSpec Length': 'sunspec_length',
            'Vendor Status': 'vendor_status',
            'RRCR State': 'rrcr_state',
            'Active Power Limit': 'active_power_limit',
            'CosPhi': 'cosphi',
            'Commit Power Control Settings': 'commit_power_control_settings',
            'Restore Power Control Default': 'restore_power_control_default_settings',
            'Reactive Power Config': 'reactive_power_config',
            'Reactive Power Response Time': 'reactive_power_response_time',
            'Advanced Power Control': 'advanced_power_control_enable',
            'Export Control Mode': 'export_control_mode',
            'Export Control Limit Mode': 'export_control_limit_mode',
            'Export Control Site Limit': 'export_control_site_limit',
            'Common ID': 'common_id',
            'Common DID': 'common_did',
            'Common Length': 'common_length'
        }
        
        config_name = endpoint_mapping.get(endpoint_name)
        if config_name is None:
            # Metrica non trovata nel mapping - prova match diretto
            return endpoint_name.lower().replace(' ', '_') in enabled_measurements
        if not config_name:
            # Se config_name è stringa vuota, fallback a True per compatibilità
            return True
        
        return config_name in enabled_measurements
    
    def _is_meter_measurement_enabled(self, endpoint_name: str, enabled_measurements: dict) -> bool:
        """Controlla se una metrica meter è abilitata nella configurazione.
        
        Args:
            endpoint_name: Nome endpoint dal parsing (es: "Power", "L1 Current")
            enabled_measurements: Measurements abilitati dalla configurazione
            
        Returns:
            True se metrica abilitata, False altrimenti
        """
        # Mappa nomi endpoint meter a nomi configurazione
        meter_mapping = {
            'Manufacturer': 'manufacturer',
            'Model': 'model',
            'Version': 'version', 
            'Serial': 'serial',
            'Option': 'option',
            'Current': 'current',
            'L1 Current': 'l1_current',
            'L2 Current': 'l2_current',
            'L3 Current': 'l3_current',
            'Voltage L-N': 'voltage_ln',
            'L1-N Voltage': 'l1n_voltage',
            'L2-N Voltage': 'l2n_voltage',
            'L3-N Voltage': 'l3n_voltage',
            'Voltage L-L': 'voltage_ll',
            'L1-L2 Voltage': 'l12_voltage',
            'L2-L3 Voltage': 'l23_voltage',
            'L3-L1 Voltage': 'l31_voltage',
            'Frequency': 'frequency',
            'Power': 'power',
            'L1 Power': 'l1_power',
            'L2 Power': 'l2_power',
            'L3 Power': 'l3_power',
            'Apparent Power': 'power_apparent',
            'L1 Apparent Power': 'l1_power_apparent',
            'L2 Apparent Power': 'l2_power_apparent',
            'L3 Apparent Power': 'l3_power_apparent',
            'Reactive Power': 'power_reactive',
            'L1 Reactive Power': 'l1_power_reactive',
            'L2 Reactive Power': 'l2_power_reactive',
            'L3 Reactive Power': 'l3_power_reactive',
            'Power Factor': 'power_factor',
            'L1 Power Factor': 'l1_power_factor',
            'L2 Power Factor': 'l2_power_factor',
            'L3 Power Factor': 'l3_power_factor',
            'Export Energy': 'export_energy_active',
            'L1 Export Energy': 'l1_export_energy_active',
            'L2 Export Energy': 'l2_export_energy_active',
            'L3 Export Energy': 'l3_export_energy_active',
            'Import Energy': 'import_energy_active',
            'L1 Import Energy': 'l1_import_energy_active',
            'L2 Import Energy': 'l2_import_energy_active',
            'L3 Import Energy': 'l3_import_energy_active',
            # Metriche aggiuntive meter
            'Device Address': 'device_address',
            'SunSpec DID': 'sunspec_did',
            'SunSpec Length': 'sunspec_length',
            # Energie apparenti
            'Export Apparent Energy': 'export_energy_apparent',
            'L1 Export Apparent Energy': 'l1_export_energy_apparent',
            'L2 Export Apparent Energy': 'l2_export_energy_apparent',
            'L3 Export Apparent Energy': 'l3_export_energy_apparent',
            'Import Apparent Energy': 'import_energy_apparent',
            'L1 Import Apparent Energy': 'l1_import_energy_apparent',
            'L2 Import Apparent Energy': 'l2_import_energy_apparent',
            'L3 Import Apparent Energy': 'l3_import_energy_apparent',
            # Energie reattive
            'Import Reactive Energy Q1': 'import_energy_reactive_q1',
            'L1 Import Reactive Energy Q1': 'l1_import_energy_reactive_q1',
            'L2 Import Reactive Energy Q1': 'l2_import_energy_reactive_q1',
            'L3 Import Reactive Energy Q1': 'l3_import_energy_reactive_q1',
            'Import Reactive Energy Q2': 'import_energy_reactive_q2',
            'L1 Import Reactive Energy Q2': 'l1_import_energy_reactive_q2',
            'L2 Import Reactive Energy Q2': 'l2_import_energy_reactive_q2',
            'L3 Import Reactive Energy Q2': 'l3_import_energy_reactive_q2',
            'Export Reactive Energy Q3': 'export_energy_reactive_q3',
            'L1 Export Reactive Energy Q3': 'l1_export_energy_reactive_q3',
            'L2 Export Reactive Energy Q3': 'l2_export_energy_reactive_q3',
            'L3 Export Reactive Energy Q3': 'l3_export_energy_reactive_q3',
            'Export Reactive Energy Q4': 'export_energy_reactive_q4',
            'L1 Export Reactive Energy Q4': 'l1_export_energy_reactive_q4',
            'L2 Export Reactive Energy Q4': 'l2_export_energy_reactive_q4',
            'L3 Export Reactive Energy Q4': 'l3_export_energy_reactive_q4',
            # Metriche condizionali (possono essere N/A)
            'Apparent Energy': 'apparent_energy_status',  # Ora mappato
            'Reactive Energy': 'reactive_energy_status'   # Ora mappato
        }
        
        config_name = meter_mapping.get(endpoint_name)
        if config_name is None:
            # Metrica non trovata nel mapping - prova match diretto
            return endpoint_name.lower().replace(' ', '_') in enabled_measurements
        if not config_name:
            # Se config_name è stringa vuota, fallback a True per compatibilità
            return True
        
        return config_name in enabled_measurements
    
    def _is_battery_measurement_enabled(self, endpoint_name: str, enabled_measurements: dict) -> bool:
        """Controlla se una metrica battery è abilitata nella configurazione.
        
        Args:
            endpoint_name: Nome endpoint dal parsing (es: "Manufacturer", "State Of Charge")
            enabled_measurements: Measurements abilitati dalla configurazione
            
        Returns:
            True se metrica abilitata, False altrimenti
        """
        # Mappa nomi endpoint battery a nomi configurazione
        battery_mapping = {
            'Manufacturer': 'manufacturer',
            'Model': 'model',
            'Version': 'version',
            'Serial': 'serial'
        }
        
        config_name = battery_mapping.get(endpoint_name)
        if config_name:
            return config_name in enabled_measurements
        
        # Per le batterie, se non è un campo base mappato, accetta tutto
        # (le metriche dinamiche delle batterie sono troppo variabili per mapparle tutte)
        return True