"""SolarEdge API Parser - Refactored with filtering and Point conversion"""

from datetime import datetime
from typing import Dict, List, Any, Union
import logging
import pytz
import yaml
import json
from pathlib import Path
from filtro.regole_filtraggio import filter_raw_points, filter_structured_points

try:
    from influxdb_client import Point, WritePrecision
    INFLUX_AVAILABLE = True
except ImportError:
    INFLUX_AVAILABLE = False
    Point = None

logger = logging.getLogger(__name__)

# Costanti
ENERGY_DETAILS = 'site_energy_details'
POWER_DETAILS = 'site_power_details'
RAW_JSON_FORMAT = 'raw_json'
STRUCTURED_FORMAT = 'structured'


class SolarEdgeAPIParser:
    """Parser completo per dati API SolarEdge: Parse + Filter + Convert"""

    def __init__(self):
        try:
            from config.config_manager import get_config_manager
            config_manager = get_config_manager()
            self.config = config_manager.get_raw_config()
            self.timezone = pytz.timezone(self.config.get('global', {}).get('timezone', 'Europe/Rome'))
        except Exception:
            self.config = {}
            self.timezone = pytz.timezone('Europe/Rome')

    def _get_endpoint_config(self, endpoint_name: str) -> Dict:
        return self.config.get('sources', {}).get('api_ufficiali', {}).get('endpoints', {}).get(endpoint_name, {})

    def _extract_by_path(self, data: Any, path: str) -> Any:
        """Estrae dati seguendo un path tipo 'field.subfield[]'"""
        if not path:
            return data
            
        parts = path.split('.')
        current = data
        
        for i, part in enumerate(parts):
            if '[]' in part:
                array_part = part.replace('[]', '')
                if not isinstance(current, dict) or array_part not in current:
                    return None
                array_data = current[array_part]
                if not isinstance(array_data, list) or i >= len(parts) - 1:
                    return None
                next_part = parts[i + 1]
                return [item.get(next_part) for item in array_data if isinstance(item, dict)]
            
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
            
        return current

    def _create_raw_point(self, endpoint_name: str, site_id: str, data: Any, extraction: Dict) -> Dict[str, Any]:
        """Crea punto raw per storage"""
        endpoint_cfg = self._get_endpoint_config(endpoint_name)
        
        if 'category' not in endpoint_cfg:
            raise ValueError(f"Endpoint '{endpoint_name}' manca della categoria in main.yaml")
        
        values_path = extraction.get('values_path', '')
        json_data = self._extract_by_path(data, values_path) if values_path else data
        if json_data is None:
            json_data = data

        return {
            'source': 'api',
            'device_type': endpoint_name,
            'metric': extraction.get('metric', 'raw_data'),
            'timestamp': int(datetime.now(pytz.utc).timestamp() * 1_000_000_000),
            'unit': extraction.get('unit', 'raw'),
            'json_data': json_data,
            'data_type': endpoint_cfg.get('data_type', 'metadata'),
            'category': endpoint_cfg['category']
        }

    def _parse_timestamp(self, time_str: str, time_format: str = '%Y-%m-%d %H:%M:%S') -> datetime:
        """Parse timestamp con timezone"""
        try:
            ts_local = datetime.strptime(str(time_str), time_format)
            return self.timezone.localize(ts_local).astimezone(pytz.utc)
        except Exception:
            return None

    def _normalize_unit(self, unit: str | None) -> str | None:
        """Normalizza unità comuni"""
        if not unit:
            return None
        unit_map = {'w': 'W', 'wh': 'Wh', 'kw': 'kW', 'kwh': 'kWh'}
        return unit_map.get(unit.lower().strip(), unit.strip())

    def _create_structured_dict(self, endpoint_name: str, category: str, value: float, 
                              meter_type: str = None, unit: str = None, ts: datetime = None, metric: str = None) -> Dict[str, Any]:
        """Crea dizionario strutturato per filtro"""
        timestamp_ns = None
        if ts:
            timestamp_ns = int(ts.timestamp() * 1_000_000_000)
        
        tags = {"endpoint": endpoint_name}
        if meter_type:
            tags["metric"] = meter_type
        if unit:
            tags["unit"] = str(unit)
        if metric:
            tags["metric"] = metric
            
        fields = {category: float(value)}
        
        return {
            "measurement": "api",
            "tags": tags,
            "fields": fields,
            "timestamp": timestamp_ns
        }

    def _convert_dict_to_point(self, point_dict: Dict[str, Any]) -> Point | None:
        """Converte dizionario in Point InfluxDB"""
        if not INFLUX_AVAILABLE:
            return None
            
        try:
            measurement = point_dict.get("measurement", "api")
            fields = point_dict.get("fields", {})
            
            if not fields:
                return None
            
            point = Point(measurement)
            
            # Tags
            for key, value in point_dict.get("tags", {}).items():
                if value is not None:
                    point.tag(key, str(value))
            
            # Fields
            for key, value in fields.items():
                try:
                    point.field(key, float(value))
                except (ValueError, TypeError):
                    point.field(key, str(value))
            
            # Timestamp
            if timestamp := point_dict.get("timestamp"):
                point.time(timestamp, WritePrecision.NS)
            
            return point
            
        except Exception as e:
            logger.debug(f"Errore conversione punto: {e}")
            return None

    def _convert_raw_to_point(self, raw_point: Dict[str, Any]) -> Point | None:
        """Converte raw point in Point InfluxDB"""
        if not INFLUX_AVAILABLE:
            return None
            
        try:
            device_type = raw_point.get("device_type")
            category = raw_point.get("category")
            unit = self._normalize_unit(raw_point.get("unit"))
            
            point = Point("api")
            
            # Tags minimali
            point.tag("endpoint", device_type)
            if unit:
                point.tag("unit", unit)
            

            
            # Fields con categoria
            if 'json_data' in raw_point:
                # Metadata endpoint
                raw_json = raw_point["json_data"]
                if isinstance(raw_json, dict):
                    raw_json = json.dumps(raw_json)
                point.field(category, raw_json)
            elif category:
                # Altri raw points
                point.field(category, 1.0)
            
            # Timestamp
            if timestamp := raw_point.get("timestamp"):
                point.time(timestamp, WritePrecision.NS)
            
            return point
            
        except Exception as e:
            logger.debug(f"Errore conversione raw point: {e}")
            return None

    def _process_meter_data(self, endpoint_name: str, data: Dict, extraction: Dict, category: str) -> List[Dict[str, Any]]:
        """Processa dati meter per energy/power details -> dizionari per filtro"""
        structured_dicts = []
            
        root_field = 'energyDetails' if endpoint_name == ENERGY_DETAILS else 'powerDetails'
        root = data.get(root_field, {})
        
        if not root or not isinstance(root.get('meters'), list):
            logger.warning(f"Nessun meter trovato per {endpoint_name}")
            return structured_dicts
            
        for meter in root['meters']:
            if not isinstance(meter, dict) or 'values' not in meter:
                continue
                
            meter_type = meter.get('type', 'PRODUCTION')
            values = meter.get('values', [])
            
            # Per Production e FeedIn, aggiungi UN SOLO punto a 0 a mezzanotte per giorno
            # Questo garantisce che Grafana possa fare fill() correttamente
            if meter_type in ['Production', 'FeedIn'] and values and endpoint_name == ENERGY_DETAILS:
                # Raccogli tutti i giorni presenti nei dati
                days_seen = set()
                for item in values:
                    if isinstance(item, dict):
                        time_str = item.get(extraction.get('time_field', 'date'))
                        if time_str:
                            ts = self._parse_timestamp(time_str)
                            if ts:
                                day_key = ts.strftime('%Y-%m-%d')
                                days_seen.add((day_key, ts))
                
                # Aggiungi UN punto a mezzanotte per ogni giorno
                for day_key, sample_ts in days_seen:
                    midnight = sample_ts.replace(hour=0, minute=0, second=1, microsecond=0)
                    unit = extraction.get('unit', 'Wh')
                    
                    midnight_dict = self._create_structured_dict(
                        endpoint_name, category, 0.0,
                        meter_type=meter_type, unit=unit, ts=midnight
                    )
                    if midnight_dict:
                        structured_dicts.append(midnight_dict)
            
            for item in values:
                if not isinstance(item, dict):
                    continue
                    
                time_str = item.get(extraction.get('time_field', 'date'))
                value = item.get(extraction.get('value_field', 'value'))
                
                if value is None:
                    continue
                    
                ts = self._parse_timestamp(time_str) if time_str else None
                unit = extraction.get('unit') or item.get('unit') or item.get('unitType')
                
                struct_dict = self._create_structured_dict(endpoint_name, category, value, 
                                                         meter_type=meter_type, unit=unit, ts=ts)
                if struct_dict:
                    structured_dicts.append(struct_dict)
                    
        return structured_dicts

    def _process_timeframe_energy(self, endpoint_name: str, data: Any, extraction: Dict, category: str) -> List[Dict[str, Any]]:
        """Processa timeframe energy -> dizionari per filtro"""
        structured_dicts = []
            
        values_path = extraction.get('values_path', '')
        timeframe_obj = self._extract_by_path(data, values_path) if values_path else None
        
        if not isinstance(timeframe_obj, dict):
            return structured_dicts
            
        value = timeframe_obj.get(extraction.get('value_field', 'energy'))
        if value is None:
            return structured_dicts
            
        time_str = None
        if 'startLifetimeEnergy' in timeframe_obj and isinstance(timeframe_obj['startLifetimeEnergy'], dict):
            time_str = timeframe_obj['startLifetimeEnergy'].get('date')
            
        ts = self._parse_timestamp(time_str) if time_str else None
        unit = extraction.get('unit') or timeframe_obj.get('unit', 'Wh')
        
        struct_dict = self._create_structured_dict(endpoint_name, category, value, unit=unit, ts=ts)
        if struct_dict:
            structured_dicts.append(struct_dict)
            
        return structured_dicts

    def _process_equipment_data(self, endpoint_name: str, data: Any, extraction: Dict, category: str) -> List[Dict[str, Any]]:
        """Processa equipment data -> dizionari per filtro"""
        structured_dicts = []
            
        telemetries = self._extract_by_path(data, 'data.telemetries')
        if not isinstance(telemetries, list):
            return structured_dicts
            
        fields_to_extract = [
            'totalActivePower', 'dcVoltage', 'powerLimit', 'totalEnergy', 'temperature'
        ]
        
        phase_fields = ['acCurrent', 'acVoltage', 'acFrequency', 'apparentPower', 'activePower', 'reactivePower', 'cosPhi']
        
        for telemetry in telemetries:
            if not isinstance(telemetry, dict):
                continue
                
            time_str = telemetry.get('date')
            ts = self._parse_timestamp(time_str) if time_str else None
            
            # Estrai campi principali
            for field in fields_to_extract:
                value = telemetry.get(field)
                if value is not None and isinstance(value, (int, float)):
                    unit = 'W' if field in ['totalActivePower', 'apparentPower', 'activePower', 'reactivePower'] else (
                        'V' if field in ['dcVoltage', 'acVoltage'] else (
                            '%' if field == 'powerLimit' else (
                                'Wh' if field == 'totalEnergy' else 'C'
                            )
                        )
                    )
                    struct_dict = self._create_structured_dict(endpoint_name, category, value, 
                                                             unit=unit, ts=ts, metric=field)
                    if struct_dict:
                        structured_dicts.append(struct_dict)
            
            # Estrai dati delle fasi
            for phase in ['L1Data', 'L2Data', 'L3Data']:
                phase_data = telemetry.get(phase)
                if isinstance(phase_data, dict):
                    for field in phase_fields:
                        value = phase_data.get(field)
                        if value is not None and isinstance(value, (int, float)):
                            unit = 'A' if field == 'acCurrent' else (
                                'V' if field == 'acVoltage' else (
                                    'Hz' if field == 'acFrequency' else (
                                        'W' if field in ['apparentPower', 'activePower', 'reactivePower'] else ''
                                    )
                                )
                            )
                            metric_name = f"{phase}_{field}"
                            struct_dict = self._create_structured_dict(endpoint_name, category, value, 
                                                                     unit=unit, ts=ts, metric=metric_name)
                            if struct_dict:
                                structured_dicts.append(struct_dict)
        
        return structured_dicts

    def _create_structured_dicts(self, endpoint_name: str, site_id: str, data: Any, extraction: Dict) -> List[Dict[str, Any]]:
        """Crea dizionari strutturati da dati API -> per filtro"""
        endpoint_cfg = self._get_endpoint_config(endpoint_name)
        
        if 'category' not in endpoint_cfg:
            raise ValueError(f"Endpoint '{endpoint_name}' manca della categoria in main.yaml")
        
        category = endpoint_cfg['category']
        
        # Gestione speciale per energy/power details
        if endpoint_name in [ENERGY_DETAILS, POWER_DETAILS]:
            return self._process_meter_data(endpoint_name, data, extraction, category)
        
        # Gestione speciale per timeframe energy
        if endpoint_name == 'site_timeframe_energy':
            return self._process_timeframe_energy(endpoint_name, data, extraction, category)
        
        # Gestione speciale per equipment data
        if endpoint_name == 'equipment_data':
            return self._process_equipment_data(endpoint_name, data, extraction, category)
        
        # Gestione generica
        structured_dicts = []
            
        values_path = extraction.get('values_path', '')
        values_array = self._extract_by_path(data, values_path) if values_path else None
        
        if not isinstance(values_array, list):
            return structured_dicts
            
        for item in values_array:
            if not isinstance(item, dict):
                continue
                
            value = item.get(extraction.get('value_field', 'value'))
            if value is None:
                continue
                
            time_str = item.get(extraction.get('time_field', 'date'))
            ts = self._parse_timestamp(time_str) if time_str else None
            unit = extraction.get('unit') or item.get('unit')
            
            struct_dict = self._create_structured_dict(endpoint_name, category, value, unit=unit, ts=ts)
            if struct_dict:
                structured_dicts.append(struct_dict)
                
        return structured_dicts

    def parse(self, api_data: Dict[str, Any], site_id: str) -> List[Union[Point, Dict[str, Any]]]:
        """Processa endpoint API: Parse + Filter + Convert to Points
        
        Input: Dati raw API
        Output: Lista di InfluxDB Point objects pronti per scrittura
        """
        if not api_data:
            return []
            
        all_structured_dicts = []
        all_raw_points = []
        
        # 1. Parsing: API data -> structured dicts + raw points
        for endpoint_name, response_data in api_data.items():
            endpoint_cfg = self._get_endpoint_config(endpoint_name)
            extraction = endpoint_cfg.get('extraction', {})
            data_format = endpoint_cfg.get('data_format', STRUCTURED_FORMAT)
            
            try:
                if data_format == RAW_JSON_FORMAT:
                    rp = self._create_raw_point(endpoint_name, site_id, response_data, extraction)
                    if rp:
                        all_raw_points.append(rp)
                else:
                    struct_dicts = self._create_structured_dicts(endpoint_name, site_id, response_data, extraction)
                    all_structured_dicts.extend(struct_dicts)
                    
            except Exception as e:
                logger.error(f"Errore parsing endpoint {endpoint_name}: {e}")
        
        # 2. Filtro: applica regole di filtraggio
        filtered_structured = filter_structured_points(all_structured_dicts)
        filtered_raw = filter_raw_points(all_raw_points)
        
        logger.info(f"Filtrati structured: {len(filtered_structured)}/{len(all_structured_dicts)}, "
                   f"raw: {len(filtered_raw)}/{len(all_raw_points)}")
        
        # 3. Conversione: dicts -> InfluxDB Points  
        all_points = []
        
        for struct_dict in filtered_structured:
            if point := self._convert_dict_to_point(struct_dict):
                all_points.append(point)
        
        for raw_point in filtered_raw:
            if point := self._convert_raw_to_point(raw_point):
                all_points.append(point)
        
        if not INFLUX_AVAILABLE:
            # Fallback: restituisce dict se InfluxDB non disponibile
            logger.warning("InfluxDB client non disponibile, restituisco dict")
            return filtered_structured + filtered_raw
        
        logger.info(f"Generati {len(all_points)} InfluxDB Points da API parser")
        return all_points


def create_parser() -> SolarEdgeAPIParser:
    return SolarEdgeAPIParser()
