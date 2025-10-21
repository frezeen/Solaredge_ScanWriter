"""regole_filtraggio.py - Modulo filtro ottimizzato"""

from __future__ import annotations
from typing import Any, Dict, List
import os
from app_logging import get_logger
from config.config_manager import get_config_manager

__all__ = [
    "is_valid_numeric_value",
    "has_valid_values_in_json",
    "filter_raw_points",
    "filter_structured_points",
    "_is_debug_mode"
]

logger = get_logger("filtro.regole_filtraggio")

# Configurazione globale
_config_manager = get_config_manager()
_global_config = _config_manager.get_global_config()
DEBUG_MODE = getattr(_global_config, 'filter_debug', False)
ALLOWED_FIELDS = {
    # Fields API/Web esistenti
    'value', 'energy', 'power', 'consumption', 'production', 'power_flow', 'raw_json', '_field', 'Meter', 'Inverter',
    
    # Fields realtime - Device types (maiuscole per coerenza con API/Web)
    'Inverter', 'Meter', 'Battery',
    
    # Fields realtime - Potenza
    'ac_power', 'dc_power', 'power_ac_scale', 'power_dc_scale',
    'ac_va', 'power_apparent_scale', 'ac_var', 'power_reactive_scale',
    
    # Fields realtime - Tensioni AC
    'ac_voltage_an', 'ac_voltage_bn', 'ac_voltage_cn',
    'ac_voltage_ab', 'ac_voltage_bc', 'ac_voltage_ca', 'voltage_scale',
    
    # Fields realtime - Correnti AC
    'ac_current', 'ac_current_a', 'ac_current_b', 'ac_current_c', 'current_scale',
    
    # Fields realtime - Tensioni/Correnti DC
    'dc_voltage', 'dc_current', 'voltage_dc_scale', 'current_dc_scale',
    
    # Fields realtime - Frequenza
    'ac_frequency', 'frequency_scale',
    
    # Fields realtime - Temperature
    'temperature', 'temperature_scale', 'c_heatsink_temperature',
    'c_transformer_temperature', 'c_other_temperature',
    
    # Fields realtime - Fattore di potenza
    'ac_pf', 'power_factor_scale',
    
    # Fields realtime - Energia
    'ac_energy_wh', 'energy_total_scale',
    
    # Fields realtime - Controlli e efficienza
    'efficiency', 'rrcr_state', 'active_power_limit', 'cosphi',
    'commit_power_control_settings', 'restore_power_control_default_settings',
    'reactive_power_config', 'reactive_power_response_time',
    'advanced_power_control_enable', 'export_control_mode',
    'export_control_limit_mode', 'export_control_site_limit',
    
    # Fields realtime - Identificatori SunSpec
    'c_sunspec_did', 'c_sunspec_length', 'c_length', 'c_did', 'device_address',
    
    # Fields realtime - Stringhe
    'status', 'status_vendor', 'manufacturer', 'model', 'version', 'serial', 'c_id',
    
    # Fields realtime - Meter specifici
    'ac_power_a', 'ac_power_b', 'ac_power_c', 'ac_voltage_ln', 'ac_voltage_ll',
    'ac_current_total', 'ac_frequency_meter', 'ac_real_power', 'ac_apparent_power',
    'ac_reactive_power', 'ac_power_factor', 'ac_energy_wh_exported',
    'ac_energy_wh_imported', 'c_serialnumber', 'c_model', 'c_option',
    'c_version', 'c_device_address', 'c_sunspec_did_meter'
}


def _is_debug_mode() -> bool:
    """Controlla modalità debug"""
    return DEBUG_MODE


def is_valid_numeric_value(value: Any) -> bool:
    """Valida valore numerico (> 0, o qualsiasi in debug mode)"""
    if isinstance(value, bool):
        return False
    
    try:
        num = float(value)
        return True if DEBUG_MODE else num > 0
    except (TypeError, ValueError):
        return False


def has_valid_values_in_json(json_data: Any) -> bool:
    """Verifica ricorsivamente se JSON contiene valori numerici validi"""
    if isinstance(json_data, dict):
        return any(has_valid_values_in_json(v) for v in json_data.values())
    elif isinstance(json_data, list):
        return any(has_valid_values_in_json(item) for item in json_data)
    else:
        return is_valid_numeric_value(json_data)


def _validate_raw_point(raw_point: Dict[str, Any]) -> bool:
    """Valida punto raw"""
    if not isinstance(raw_point, dict):
        return False
    
    # Campi base richiesti
    if not raw_point.get("source") or not raw_point.get("timestamp"):
        return False
    
    # Punti metadata/detailed: accetta qualsiasi json_data non nullo
    data_type = raw_point.get("data_type")
    if data_type in ["metadata", "detailed"]:
        return "json_data" in raw_point
    
    # Altri punti: verifica valore
    if "json_data" in raw_point:
        return has_valid_values_in_json(raw_point["json_data"])
    else:
        return is_valid_numeric_value(raw_point.get("value"))


def filter_raw_points(raw_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filtra punti RAW mantenendo solo valori validi"""
    return [p for p in raw_points if _validate_raw_point(p)]


def filter_structured_points(structured_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filtra punti strutturati secondo regole d'oro.
    
    Supporta sia dict che Point objects nativi InfluxDB.
    """
    result = []
    
    for point in structured_points:
        # Se è un Point object InfluxDB, passa direttamente (già validato)
        if hasattr(point, 'to_line_protocol'):
            result.append(point)
            continue
        
        # Altrimenti valida come dict
        if not isinstance(point, dict) or not point.get('fields'):
            continue
        
        # Filtra fields
        valid_fields = {}
        for field, value in point.get('fields', {}).items():
            if field not in ALLOWED_FIELDS:
                continue
            
            # raw_json: accetta stringhe non vuote
            if field == 'raw_json':
                if isinstance(value, str) and value.strip():
                    valid_fields[field] = value
            # Meter: accetta qualsiasi valore numerico (inclusi 0)
            elif field == 'Meter':
                try:
                    float(value)
                    valid_fields[field] = value
                except (ValueError, TypeError):
                    pass
            # Realtime device fields: solo valori numerici (come API/Web)
            elif field in ['Inverter', 'Meter', 'Battery']:
                if isinstance(value, (int, float)):
                    valid_fields[field] = float(value)
            # Altri campi: valida numerici
            elif is_valid_numeric_value(value):
                valid_fields[field] = value
        
        # Mantieni punto solo se ha fields validi
        if valid_fields:
            filtered_point = point.copy()
            filtered_point['fields'] = valid_fields
            result.append(filtered_point)
    
    return result