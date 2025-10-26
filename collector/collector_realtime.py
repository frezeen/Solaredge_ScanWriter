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
    
    def _format_value(self, raw_value, scale, unit="", decimals=2):
        """Formatta valori scalati secondo protocollo SunSpec Modbus.
        
        Applica il fattore di scala: valore_reale = raw_value * 10^scale
        
        Args:
            raw_value: Valore grezzo dal registro Modbus
            scale: Fattore di scala (es: -2 per dividere per 100)
            unit: Unità di misura da appendere (es: "W", "V", "A")
            decimals: Numero di decimali nel formato output
            
        Returns:
            Stringa formattata con valore scalato e unità
            "N/A" se scale invalido (-32768)
            
        Example:
            >>> collector._format_value(2500, -1, "W", 1)
            '250.0W'
            >>> collector._format_value(100, -32768, "V")
            'N/A'
        """
        if scale == -32768:
            return "N/A"
        try:
            scaled_value = raw_value * (10 ** scale)
            return f"{scaled_value:.{decimals}f}{unit}" if decimals > 0 else f"{scaled_value:.0f}{unit}"
        except:
            return "N/A"
    
    def _generate_formatted_output(self, host: str, port: int) -> str:
        """Genera output formattato leggibile da dati Modbus TCP.
        
        Connette al dispositivo Modbus, legge tutti i registri (inverter, meter, battery)
        e genera output testuale formattato filtrato per configurazione.
        
        Args:
            host: Indirizzo IP del dispositivo Modbus
            port: Porta TCP Modbus (tipicamente 1502)
            
        Returns:
            Stringa con output formattato multi-sezione
            None se errore durante connessione o lettura
            
        Raises:
            ConnectionError: Se impossibile connettersi
            TimeoutError: Se timeout durante lettura
            
        Example:
            >>> output = collector._generate_formatted_output("192.168.1.100", 1502)
            >>> assert "=== INVERTER REGISTERS ===" in output
        """
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
            values["meters"] = {}
            values["batteries"] = {}
            
            # Controlla se meters sono abilitati nella configurazione
            endpoints = self._modbus_endpoints.get('endpoints', {})
            meters_enabled = endpoints.get('meters', {}).get('enabled', False)
            batteries_enabled = endpoints.get('batteries', {}).get('enabled', False)
            
            if meters_enabled:
                for meter, params in meters.items():
                    values["meters"][meter] = params.read_all()
            
            if batteries_enabled:
                for battery, params in batteries.items():
                    values["batteries"][battery] = params.read_all()
            
            output = StringIO()
            
            output.write(f"{inverter}:\n")
            
            # Sezione inverter (sempre presente se inverter_realtime è abilitato)
            inverter_enabled = endpoints.get('inverter_realtime', {}).get('enabled', False)
            if inverter_enabled:
                output.write("\n=== INVERTER REGISTERS ===\n")
            else:
                # Se inverter disabilitato, non generare output
                return ""
            
            output.write(f"\tManufacturer: {values['c_manufacturer']}\n")
            output.write(f"\tModel: {values['c_model']}\n")
            output.write(f"\tType: {solaredge_modbus.C_SUNSPEC_DID_MAP[str(values['c_sunspec_did'])]}\n")
            output.write(f"\tVersion: {values['c_version']}\n")
            output.write(f"\tSerial: {values['c_serialnumber']}\n")
            output.write(f"\tStatus: {solaredge_modbus.INVERTER_STATUS_MAP[values['status']]}\n")
            output.write(f"\tTemperature: {self._format_value(values['temperature'], values['temperature_scale'], '°C')}\n")
            
            output.write(f"\tCurrent: {self._format_value(values['current'], values['current_scale'], 'A')}\n")
            
            if values['c_sunspec_did'] is solaredge_modbus.sunspecDID.THREE_PHASE_INVERTER.value:
                output.write(f"\tPhase 1 Current: {self._format_value(values['l1_current'], values['current_scale'], 'A')}\n")
                output.write(f"\tPhase 2 Current: {self._format_value(values['l2_current'], values['current_scale'], 'A')}\n")
                output.write(f"\tPhase 3 Current: {self._format_value(values['l3_current'], values['current_scale'], 'A')}\n")
                output.write(f"\tPhase 1 voltage: {self._format_value(values['l1_voltage'], values['voltage_scale'], 'V')}\n")
                output.write(f"\tPhase 2 voltage: {self._format_value(values['l2_voltage'], values['voltage_scale'], 'V')}\n")
                output.write(f"\tPhase 3 voltage: {self._format_value(values['l3_voltage'], values['voltage_scale'], 'V')}\n")
                output.write(f"\tPhase 1-N voltage: {self._format_value(values['l1n_voltage'], values['voltage_scale'], 'V')}\n")
                output.write(f"\tPhase 2-N voltage: {self._format_value(values['l2n_voltage'], values['voltage_scale'], 'V')}\n")
                output.write(f"\tPhase 3-N voltage: {self._format_value(values['l3n_voltage'], values['voltage_scale'], 'V')}\n")
            else:
                output.write(f"\tVoltage: {self._format_value(values['l1_voltage'], values['voltage_scale'], 'V')}\n")
            
            output.write(f"\tFrequency: {self._format_value(values['frequency'], values['frequency_scale'], 'Hz')}\n")
            output.write(f"\tPower: {self._format_value(values['power_ac'], values['power_ac_scale'], 'W')}\n")
            output.write(f"\tPower (Apparent): {self._format_value(values['power_apparent'], values['power_apparent_scale'], 'VA')}\n")
            output.write(f"\tPower (Reactive): {self._format_value(values['power_reactive'], values['power_reactive_scale'], 'VAr')}\n")
            output.write(f"\tPower Factor: {self._format_value(values['power_factor'], values['power_factor_scale'], '%')}\n")
            output.write(f"\tTotal Energy: {self._format_value(values['energy_total'], values['energy_total_scale'], 'Wh', 0)}\n")
            
            output.write(f"\tDC Current: {self._format_value(values['current_dc'], values['current_dc_scale'], 'A')}\n")
            output.write(f"\tDC Voltage: {self._format_value(values['voltage_dc'], values['voltage_dc_scale'], 'V')}\n")
            output.write(f"\tDC Power: {self._format_value(values['power_dc'], values['power_dc_scale'], 'W')}\n")
            
            output.write(f"\tDevice Address: {values.get('c_deviceaddress', 'N/A')}\n")
            output.write(f"\tSunSpec DID: {values.get('c_sunspec_did', 'N/A')}\n")
            output.write(f"\tSunSpec Length: {values.get('c_sunspec_length', 'N/A')}\n")
            output.write(f"\tVendor Status: {values.get('vendor_status', 'N/A')}\n")
            output.write(f"\tRRCR State: {values.get('rrcr_state', 'N/A')}\n")
            output.write(f"\tActive Power Limit: {values.get('active_power_limit', 'N/A')}%\n")
            output.write(f"\tCosPhi: {values.get('cosphi', 'N/A')}\n")
            output.write(f"\tCommit Power Control Settings: {values.get('commit_power_control_settings', 'N/A')}\n")
            output.write(f"\tRestore Power Control Default: {values.get('restore_power_control_default_settings', 'N/A')}\n")
            output.write(f"\tReactive Power Config: {values.get('reactive_power_config', 'N/A')}\n")
            output.write(f"\tReactive Power Response Time: {values.get('reactive_power_response_time', 'N/A')}ms\n")
            output.write(f"\tAdvanced Power Control: {'Enabled' if values.get('advanced_power_control_enable', 0) else 'Disabled'}\n")
            output.write(f"\tExport Control Mode: {values.get('export_control_mode', 'N/A')}\n")
            output.write(f"\tExport Control Limit Mode: {values.get('export_control_limit_mode', 'N/A')}\n")
            output.write(f"\tExport Control Site Limit: {values.get('export_control_site_limit', 'N/A')}\n")
            output.write(f"\tCommon ID: {values.get('c_id', 'N/A')}\n")
            output.write(f"\tCommon DID: {values.get('c_did', 'N/A')}\n")
            output.write(f"\tCommon Length: {values.get('c_length', 'N/A')}\n")
            

            if values.get("meters") and meters_enabled:
                output.write(f"\n=== METERS ({len(values['meters'])} found) ===\n")
                for meter_name, meter_data in values["meters"].items():
                    output.write(f"\n--- {meter_name} ---\n")
                    output.write(f"\tManufacturer: {meter_data.get('c_manufacturer', 'N/A')}\n")
                    output.write(f"\tModel: {meter_data.get('c_model', 'N/A')}\n")
                    output.write(f"\tOption: {meter_data.get('c_option', 'N/A')}\n")
                    output.write(f"\tVersion: {meter_data.get('c_version', 'N/A')}\n")
                    output.write(f"\tSerial: {meter_data.get('c_serialnumber', 'N/A')}\n")
                    
                    # Current measurements
                    current_scale = meter_data.get('current_scale', 0)
                    output.write(f"\tCurrent: {self._format_value(meter_data.get('current', 0), current_scale, 'A')}\n")
                    output.write(f"\tL1 Current: {self._format_value(meter_data.get('l1_current', 0), current_scale, 'A')}\n")
                    output.write(f"\tL2 Current: {self._format_value(meter_data.get('l2_current', 0), current_scale, 'A')}\n")
                    output.write(f"\tL3 Current: {self._format_value(meter_data.get('l3_current', 0), current_scale, 'A')}\n")
                    
                    # Voltage measurements
                    voltage_scale = meter_data.get('voltage_scale', 0)
                    output.write(f"\tVoltage L-N: {self._format_value(meter_data.get('voltage_ln', 0), voltage_scale, 'V')}\n")
                    output.write(f"\tL1-N Voltage: {self._format_value(meter_data.get('l1n_voltage', 0), voltage_scale, 'V')}\n")
                    output.write(f"\tL2-N Voltage: {self._format_value(meter_data.get('l2n_voltage', 0), voltage_scale, 'V')}\n")
                    output.write(f"\tL3-N Voltage: {self._format_value(meter_data.get('l3n_voltage', 0), voltage_scale, 'V')}\n")
                    
                    # Frequency
                    frequency_scale = meter_data.get('frequency_scale', 0)
                    output.write(f"\tFrequency: {self._format_value(meter_data.get('frequency', 0), frequency_scale, 'Hz')}\n")
                    
                    # Power measurements
                    power_scale = meter_data.get('power_scale', 0)
                    output.write(f"\tPower: {self._format_value(meter_data.get('power', 0), power_scale, 'W')}\n")
                    output.write(f"\tL1 Power: {self._format_value(meter_data.get('l1_power', 0), power_scale, 'W')}\n")
                    output.write(f"\tL2 Power: {self._format_value(meter_data.get('l2_power', 0), power_scale, 'W')}\n")
                    output.write(f"\tL3 Power: {self._format_value(meter_data.get('l3_power', 0), power_scale, 'W')}\n")
                    
                    # Apparent power
                    power_apparent_scale = meter_data.get('power_apparent_scale', 0)
                    output.write(f"\tApparent Power: {self._format_value(meter_data.get('power_apparent', 0), power_apparent_scale, 'VA')}\n")
                    output.write(f"\tL1 Apparent Power: {self._format_value(meter_data.get('l1_power_apparent', 0), power_apparent_scale, 'VA')}\n")
                    output.write(f"\tL2 Apparent Power: {self._format_value(meter_data.get('l2_power_apparent', 0), power_apparent_scale, 'VA')}\n")
                    output.write(f"\tL3 Apparent Power: {self._format_value(meter_data.get('l3_power_apparent', 0), power_apparent_scale, 'VA')}\n")
                    
                    # Reactive power
                    power_reactive_scale = meter_data.get('power_reactive_scale', 0)
                    output.write(f"\tReactive Power: {self._format_value(meter_data.get('power_reactive', 0), power_reactive_scale, 'VAr')}\n")
                    output.write(f"\tL1 Reactive Power: {self._format_value(meter_data.get('l1_power_reactive', 0), power_reactive_scale, 'VAr')}\n")
                    output.write(f"\tL2 Reactive Power: {self._format_value(meter_data.get('l2_power_reactive', 0), power_reactive_scale, 'VAr')}\n")
                    output.write(f"\tL3 Reactive Power: {self._format_value(meter_data.get('l3_power_reactive', 0), power_reactive_scale, 'VAr')}\n")
                    
                    # Power factor
                    power_factor_scale = meter_data.get('power_factor_scale', 0)
                    output.write(f"\tPower Factor: {self._format_value(meter_data.get('power_factor', 0), power_factor_scale, '%')}\n")
                    output.write(f"\tL1 Power Factor: {self._format_value(meter_data.get('l1_power_factor', 0), power_factor_scale, '%')}\n")
                    output.write(f"\tL2 Power Factor: {self._format_value(meter_data.get('l2_power_factor', 0), power_factor_scale, '%')}\n")
                    output.write(f"\tL3 Power Factor: {self._format_value(meter_data.get('l3_power_factor', 0), power_factor_scale, '%')}\n")
                    
                    # Energy measurements
                    energy_active_scale = meter_data.get('energy_active_scale', 0)
                    output.write(f"\tExport Energy: {self._format_value(meter_data.get('export_energy_active', 0), energy_active_scale, 'Wh', 0)}\n")
                    output.write(f"\tL1 Export Energy: {self._format_value(meter_data.get('l1_export_energy_active', 0), energy_active_scale, 'Wh', 0)}\n")
                    output.write(f"\tL2 Export Energy: {self._format_value(meter_data.get('l2_export_energy_active', 0), energy_active_scale, 'Wh', 0)}\n")
                    output.write(f"\tL3 Export Energy: {self._format_value(meter_data.get('l3_export_energy_active', 0), energy_active_scale, 'Wh', 0)}\n")
                    output.write(f"\tImport Energy: {self._format_value(meter_data.get('import_energy_active', 0), energy_active_scale, 'Wh', 0)}\n")
                    output.write(f"\tL1 Import Energy: {self._format_value(meter_data.get('l1_import_energy_active', 0), energy_active_scale, 'Wh', 0)}\n")
                    output.write(f"\tL2 Import Energy: {self._format_value(meter_data.get('l2_import_energy_active', 0), energy_active_scale, 'Wh', 0)}\n")
                    output.write(f"\tL3 Import Energy: {self._format_value(meter_data.get('l3_import_energy_active', 0), energy_active_scale, 'Wh', 0)}\n")
                    
                    output.write(f"\tDevice Address: {meter_data.get('c_deviceaddress', 'N/A')}\n")
                    output.write(f"\tSunSpec DID: {meter_data.get('c_sunspec_did', 'N/A')}\n")
                    output.write(f"\tSunSpec Length: {meter_data.get('c_sunspec_length', 'N/A')}\n")
                    

                    output.write(f"\tVoltage L-L: {self._format_value(meter_data.get('voltage_ll', 0), voltage_scale, 'V')}\n")
                    output.write(f"\tL1-L2 Voltage: {self._format_value(meter_data.get('l12_voltage', 0), voltage_scale, 'V')}\n")
                    output.write(f"\tL2-L3 Voltage: {self._format_value(meter_data.get('l23_voltage', 0), voltage_scale, 'V')}\n")
                    output.write(f"\tL3-L1 Voltage: {self._format_value(meter_data.get('l31_voltage', 0), voltage_scale, 'V')}\n")
                    
                    energy_apparent_scale = meter_data.get('energy_apparent_scale', -32768)
                    if energy_apparent_scale != -32768:
                        output.write(f"\tExport Apparent Energy: {self._format_value(meter_data.get('export_energy_apparent', 0), energy_apparent_scale, 'VAh', 0)}\n")
                        output.write(f"\tL1 Export Apparent Energy: {self._format_value(meter_data.get('l1_export_energy_apparent', 0), energy_apparent_scale, 'VAh', 0)}\n")
                        output.write(f"\tL2 Export Apparent Energy: {self._format_value(meter_data.get('l2_export_energy_apparent', 0), energy_apparent_scale, 'VAh', 0)}\n")
                        output.write(f"\tL3 Export Apparent Energy: {self._format_value(meter_data.get('l3_export_energy_apparent', 0), energy_apparent_scale, 'VAh', 0)}\n")
                        output.write(f"\tImport Apparent Energy: {self._format_value(meter_data.get('import_energy_apparent', 0), energy_apparent_scale, 'VAh', 0)}\n")
                        output.write(f"\tL1 Import Apparent Energy: {self._format_value(meter_data.get('l1_import_energy_apparent', 0), energy_apparent_scale, 'VAh', 0)}\n")
                        output.write(f"\tL2 Import Apparent Energy: {self._format_value(meter_data.get('l2_import_energy_apparent', 0), energy_apparent_scale, 'VAh', 0)}\n")
                        output.write(f"\tL3 Import Apparent Energy: {self._format_value(meter_data.get('l3_import_energy_apparent', 0), energy_apparent_scale, 'VAh', 0)}\n")
                    else:
                        output.write(f"\tApparent Energy: N/A (invalid scale)\n")
                    
                    energy_reactive_scale = meter_data.get('energy_reactive_scale', -32768)
                    if energy_reactive_scale != -32768:
                        output.write(f"\tImport Reactive Energy Q1: {self._format_value(meter_data.get('import_energy_reactive_q1', 0), energy_reactive_scale, 'VArh', 0)}\n")
                        output.write(f"\tL1 Import Reactive Energy Q1: {self._format_value(meter_data.get('l1_import_energy_reactive_q1', 0), energy_reactive_scale, 'VArh', 0)}\n")
                        output.write(f"\tL2 Import Reactive Energy Q1: {self._format_value(meter_data.get('l2_import_energy_reactive_q1', 0), energy_reactive_scale, 'VArh', 0)}\n")
                        output.write(f"\tL3 Import Reactive Energy Q1: {self._format_value(meter_data.get('l3_import_energy_reactive_q1', 0), energy_reactive_scale, 'VArh', 0)}\n")
                        output.write(f"\tImport Reactive Energy Q2: {self._format_value(meter_data.get('import_energy_reactive_q2', 0), energy_reactive_scale, 'VArh', 0)}\n")
                        output.write(f"\tL1 Import Reactive Energy Q2: {self._format_value(meter_data.get('l1_import_energy_reactive_q2', 0), energy_reactive_scale, 'VArh', 0)}\n")
                        output.write(f"\tL2 Import Reactive Energy Q2: {self._format_value(meter_data.get('l2_import_energy_reactive_q2', 0), energy_reactive_scale, 'VArh', 0)}\n")
                        output.write(f"\tL3 Import Reactive Energy Q2: {self._format_value(meter_data.get('l3_import_energy_reactive_q2', 0), energy_reactive_scale, 'VArh', 0)}\n")
                        output.write(f"\tExport Reactive Energy Q3: {self._format_value(meter_data.get('export_energy_reactive_q3', 0), energy_reactive_scale, 'VArh', 0)}\n")
                        output.write(f"\tL1 Export Reactive Energy Q3: {self._format_value(meter_data.get('l1_export_energy_reactive_q3', 0), energy_reactive_scale, 'VArh', 0)}\n")
                        output.write(f"\tL2 Export Reactive Energy Q3: {self._format_value(meter_data.get('l2_export_energy_reactive_q3', 0), energy_reactive_scale, 'VArh', 0)}\n")
                        output.write(f"\tL3 Export Reactive Energy Q3: {self._format_value(meter_data.get('l3_export_energy_reactive_q3', 0), energy_reactive_scale, 'VArh', 0)}\n")
                        output.write(f"\tExport Reactive Energy Q4: {self._format_value(meter_data.get('export_energy_reactive_q4', 0), energy_reactive_scale, 'VArh', 0)}\n")
                        output.write(f"\tL1 Export Reactive Energy Q4: {self._format_value(meter_data.get('l1_export_energy_reactive_q4', 0), energy_reactive_scale, 'VArh', 0)}\n")
                        output.write(f"\tL2 Export Reactive Energy Q4: {self._format_value(meter_data.get('l2_export_energy_reactive_q4', 0), energy_reactive_scale, 'VArh', 0)}\n")
                        output.write(f"\tL3 Export Reactive Energy Q4: {self._format_value(meter_data.get('l3_export_energy_reactive_q4', 0), energy_reactive_scale, 'VArh', 0)}\n")
                    else:
                        output.write(f"\tReactive Energy: N/A (invalid scale)\n")
            

            if values.get("batteries") and batteries_enabled:
                output.write(f"\n=== BATTERIES ({len(values['batteries'])} found) ===\n")
                for battery_name, battery_data in values["batteries"].items():
                    output.write(f"\n--- {battery_name} ---\n")
                    output.write(f"\tManufacturer: {battery_data.get('c_manufacturer', 'N/A')}\n")
                    output.write(f"\tModel: {battery_data.get('c_model', 'N/A')}\n")
                    output.write(f"\tVersion: {battery_data.get('c_version', 'N/A')}\n")
                    output.write(f"\tSerial: {battery_data.get('c_serialnumber', 'N/A')}\n")
                    
                    for key, value in battery_data.items():
                        if not key.startswith('c_') and 'scale' not in key:
                            scale_key = f"{key}_scale"
                            scale = battery_data.get(scale_key, 0)
                            if scale_key in battery_data:
                                output.write(f"\t{key.replace('_', ' ').title()}: {self._format_value(value, scale)}\n")
                            else:
                                output.write(f"\t{key.replace('_', ' ').title()}: {value}\n")
            elif batteries_enabled:
                output.write(f"\n=== BATTERIES ===\n")
                output.write("\tNo batteries found\n")
            
            output.write(f"\n=== SUMMARY ===\n")
            output.write(f"\tInverters: 1\n")
            output.write(f"\tMeters: {len(values.get('meters', {}))}\n")
            output.write(f"\tBatteries: {len(values.get('batteries', {}))}\n")
            
            return output.getvalue()
            
        except Exception as e:
            self._log.error(f"Errore generazione output: {e}")
            return None
    
    def collect_data(self) -> str:
        """Raccoglie dati realtime e restituisce output formattato.
        
        Returns:
            Output formattato come stringa
            
        Raises:
            ConnectionError: Se impossibile connettersi al dispositivo Modbus
            TimeoutError: Se la connessione va in timeout
            RuntimeError: Se errore durante la lettura dati
            
        Example:
            >>> collector = RealtimeCollector()
            >>> output = collector.collect_data()
            >>> assert "=== INVERTER REGISTERS ===" in output
        """
        try:
            with timed_operation(self._log, "realtime_collection"):
                formatted_output = self._generate_formatted_output(
                    self._realtime_config.host,
                    self._realtime_config.port
                )
            
            if not formatted_output:
                raise RuntimeError("Generazione output formattato fallita")
            
            self._log.debug("Raccolta dati completata", extra={
                "host": self._realtime_config.host,
                "port": self._realtime_config.port,
                "output_size_bytes": len(formatted_output)
            })
            return formatted_output
            
        except ConnectionError as e:
            self._log.error(f"Errore connessione Modbus: {e}")
            raise
        except TimeoutError as e:
            self._log.error(f"Timeout connessione Modbus: {e}")
            raise
        except Exception as e:
            self._log.error(f"Errore raccolta dati: {e}")
            raise RuntimeError(f"Errore durante raccolta dati: {e}") from e
