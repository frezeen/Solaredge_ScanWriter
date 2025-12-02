"""web_parser.py - Refactored with filtering and Point conversion
SORGENTE: web_scraping
SCOPO: Parser completo per dati web. Parse + Filter + Convert to InfluxDB Points.
"""
from __future__ import annotations

from typing import Any, Dict, List, Union
from datetime import datetime, timezone
import json

from app_logging import get_logger
from filtro.regole_filtraggio import filter_raw_points

try:
    from influxdb_client import Point, WritePrecision
    INFLUX_AVAILABLE = True
except ImportError:
    INFLUX_AVAILABLE = False
    Point = None

_log = get_logger("parser.web")

def _validate_input(measurements_raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Valida input e restituisce container measurements."""
    if not isinstance(measurements_raw, dict):
        _log.error("parse_web input non dict")
        raise RuntimeError("parse_web: input non dict - stop")

    container = measurements_raw.get("list")
    if container is None:
        _log.error("parse_web lista mancante")
        raise RuntimeError("parse_web: chiave list mancante - stop")
    if not isinstance(container, list):
        _log.error("parse_web container non lista")
        raise RuntimeError("parse_web: container non lista - stop")
    return container

def _extract_device_info(item: Dict[str, Any]) -> tuple[str, str, str, str, List[Dict[str, Any]]] | None:
    """Estrae informazioni device da un item. Ritorna None se invalido."""
    if not isinstance(item, dict):
        return None
    device = item.get("device", {})
    if not isinstance(device, dict):
        return None
    device_type = str(device.get("itemType") or "").strip()
    if device_type.upper() == "WEATHER":
        device_id = "weather_default"
    else:
        device_id = str(device.get("id") or device.get("identifier") or "").strip()
    measurement_type = str(item.get("measurementType") or "").strip()
    unit_type = str(item.get("unitType") or "").strip()
    measurements = item.get("measurements", [])
    if not device_type or not measurement_type or not isinstance(measurements, list):
        return None
    return device_id, device_type, measurement_type, unit_type, measurements

def _convert_timestamp(time_raw: Any) -> int | None:
    """Converte timestamp in epoch ms. Ritorna None se fallisce."""
    if time_raw is None or time_raw == "":
        return None
    # Numerico o stringa numerica
    try:
        return int(float(time_raw))
    except Exception:
        pass
    # ISO8601
    if isinstance(time_raw, str):
        try:
            iso_str = time_raw.strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        except Exception:
            pass
    return None

def _create_raw_point(
    device_id: str,
    device_type: str,
    measurement_type: str,
    unit_type: str,
    value_raw: Any,
    ts_ms: int,
    category: str = "Info",
) -> Dict[str, Any]:
    """Crea un punto RAW data standardizzato."""
    return {
        "source": "web",
        "device_id": device_id,
        "device_type": device_type,
        "metric": measurement_type,
        "value": value_raw,
        "timestamp": ts_ms,
        "unit": unit_type if unit_type else None,
        "category": category,
    }

def _normalize_unit(unit: str | None) -> str | None:
    """Normalizza unità comuni"""
    if not unit:
        return None
    unit_map = {"w": "W", "wh": "Wh", "kw": "kW", "kwh": "kWh"}
    return unit_map.get(unit.lower().strip(), unit.strip())

def _convert_raw_point_to_influx_point(raw_point: Dict[str, Any]) -> Point | None:
    """Converte raw point in InfluxDB Point object"""
    if not INFLUX_AVAILABLE:
        return None
    try:
        metric = raw_point.get("metric")
        category = raw_point.get("category")
        unit = _normalize_unit(raw_point.get("unit"))
        value = raw_point.get("value")
        if value is None:
            return None
        point = Point("web")
        point.tag("endpoint", metric)
        if unit:
            point.tag("unit", unit)
        if device_id := raw_point.get("device_id"):
            point.tag("device_id", device_id)
        if category:
            try:
                point.field(category, float(value))
            except (ValueError, TypeError):
                point.field(category, str(value))
        else:
            point.field("value", float(value))
        if timestamp := raw_point.get("timestamp"):
            timestamp_ns = timestamp * 1_000_000 if timestamp < 1e15 else timestamp
            point.time(timestamp_ns, WritePrecision.NS)
        return point
    except Exception as e:
        _log.debug(f"Errore conversione punto: {e}")
        return None

def _get_endpoint_info(measurement_type: str, device_id: str, config: Dict[str, Any]) -> tuple[str, str]:
    """Estrae category e date_range dal YAML config."""
    web_endpoints = config.get('sources', {}).get('web_scraping', {}).get('endpoints', {})
    _log.debug(f"🔍 Cercando info per device_id: '{device_id}', measurement: '{measurement_type}'")
    
    for endpoint_name, endpoint_config in web_endpoints.items():
        if isinstance(endpoint_config, dict):
            endpoint_device_id = str(endpoint_config.get('device_id', ''))
            if endpoint_device_id == device_id:
                category = endpoint_config.get('category', 'Info')
                date_range = endpoint_config.get('date_range', 'daily')
                _log.debug(f"✅ Trovato endpoint per {device_id}: cat={category}, range={date_range}")
                return category, date_range
                
    # Diagnostica avanzata per mancata corrispondenza
    available_ids = [str(cfg.get('device_id', '')) for cfg in web_endpoints.values() if isinstance(cfg, dict)]
    _log.warning(f"❌ INFO MISSING: device_id='{device_id}' non trovato in {len(web_endpoints)} endpoints.")
    if available_ids:
        _log.warning(f"   Primi 3 ID disponibili: {available_ids[:3]}")
        if device_id in available_ids:
            _log.warning("   ⚠️ L'ID è presente nella lista ma il match è fallito! Verifica spazi o caratteri invisibili.")
            
    return 'Info', 'daily'

def _aggregate_measurements_to_daily(measurements_raw: Dict[str, Any]) -> Dict[str, Any]:
    """Aggrega measurements sub-giornalieri a 1 punto/giorno a mezzanotte.
    
    Riutilizza logica esistente: raggruppa per (device, metric, giorno), somma valori.
    """
    from collections import defaultdict
    
    items = measurements_raw.get('list', [])
    aggregated_items = []
    
    for item in items:
        measurements = item.get('measurements', [])
        if not measurements:
            continue
        
        # Verifica se serve aggregazione (più di 1 punto per giorno)
        daily_groups = defaultdict(list)
        for m in measurements:
            time_str = m.get('time', '')
            if not time_str:
                continue
            date_part = time_str[:10]
            daily_groups[date_part].append(m)
        
        # Se già 1 punto/giorno, skip aggregazione
        if all(len(points) == 1 for points in daily_groups.values()):
            aggregated_items.append(item)
            continue
        
        # Aggrega per giorno
        aggregated_measurements = []
        for date_part in sorted(daily_groups.keys()):
            day_points = daily_groups[date_part]
            total = sum(p.get('measurement', 0) for p in day_points if p.get('measurement') is not None and p.get('measurement') > 0)
            
            aggregated_measurements.append({
                'time': f"{date_part}T00:00:00+01:00",
                'measurement': total
            })
        
        aggregated_item = item.copy()
        aggregated_item['measurements'] = aggregated_measurements
        aggregated_items.append(aggregated_item)
    
    return {'list': aggregated_items}

def parse_web(measurements_raw: Dict[str, Any], config: Dict[str, Any] = None) -> List[Union[Point, Dict[str, Any]]]:
    """Trasforma misure raw web in InfluxDB Points filtrati.

    Input: Raw measurements da collector web, config YAML
    Output: Lista di InfluxDB Point objects pronti per scrittura
    """
    if config is None:
        config = {}
    
    # Aggrega dati sub-giornalieri a 1 punto/giorno prima del parsing
    measurements_raw = _aggregate_measurements_to_daily(measurements_raw)
    
    container = _validate_input(measurements_raw)
    raw_points: List[Dict[str, Any]] = []
    for item in container:
        device_info = _extract_device_info(item)
        if device_info is None:
            continue
        device_id, device_type, measurement_type, unit_type, measurements = device_info
        
        # Recupera info configurazione una volta per device
        category, date_range = _get_endpoint_info(measurement_type, device_id, config)
        
        for m in measurements:
            if not isinstance(m, dict):
                continue
            
            time_raw = m.get("time")
            ts_ms = _convert_timestamp(time_raw)
            
            if ts_ms is None or ts_ms <= 0:
                continue

            raw_point = _create_raw_point(
                device_id,
                device_type,
                measurement_type,
                unit_type,
                m.get("measurement"),
                ts_ms,
                category,
            )
            raw_points.append(raw_point)
    if not raw_points:
        _log.warning("parse_web nessun punto RAW generato")
        raise RuntimeError("parse_web: nessun punto RAW generato - stop")
    
    raw_points.sort(key=lambda p: (p["device_id"], p["metric"], p["timestamp"]))
    filtered_points = filter_raw_points(raw_points)
    _log.info(f"Filtrati {len(filtered_points)}/{len(raw_points)} punti validi")
    if not filtered_points:
        _log.warning("Nessun punto valido dopo filtro")
        return []
    influx_points: List[Point] = []
    for raw_point in filtered_points:
        if point := _convert_raw_point_to_influx_point(raw_point):
            influx_points.append(point)
    if not INFLUX_AVAILABLE:
        _log.warning("InfluxDB client non disponibile, restituisco raw points")
        return filtered_points
    _log.info(f"Generati {len(influx_points)} InfluxDB Points da web parser")
    return influx_points

__all__ = ["parse_web"]
