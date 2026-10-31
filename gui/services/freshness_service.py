"""Freschezza delle destinazioni: quando ogni bucket ha ricevuto l'ultimo punto.

Read-only. Serve alla Overview per distinguere un collector che scrive da uno
fermo. Non espone i valori: quelli restano su Grafana.
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict

from influxdb_client import InfluxDBClient

CACHE_TTL_SECONDS = 30

# Finestra di scansione per bucket: copre la cadenza senza leggere tutto lo storico.
WINDOWS = [
    ("Solaredge_Realtime", "-2h", "2h"),
    ("Solaredge", "-2d", "48h"),
    ("GME", "-7d", "7g"),
    ("Bolletta", "-30d", "30g"),
]

_cache: Dict[str, Any] = {"ts": 0.0, "data": None}


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _bucket(client: InfluxDBClient, name: str, window: str, label: str) -> Dict[str, Any]:
    api = client.query_api()
    last_query = (
        f'from(bucket: "{name}") |> range(start: {window}) '
        '|> keep(columns: ["_time"]) |> group() |> max(column: "_time")'
    )
    count_query = (
        f'from(bucket: "{name}") |> range(start: {window}) '
        '|> group() |> count() |> keep(columns: ["_value"])'
    )

    last = None
    for table in api.query(last_query):
        for record in table.records:
            last = record.get_time()

    points = None
    for table in api.query(count_query):
        for record in table.records:
            points = int(record.get_value() or 0)

    age = None
    if last:
        age = max(0, int((datetime.now(timezone.utc) - last).total_seconds()))

    return {
        "name": name,
        "last": _iso(last) if last else None,
        "age_seconds": age,
        "points": points,
        "window": label,
    }


def _build(config: Dict) -> Dict[str, Any]:
    influx = config.get("influxdb", {})
    url, token, org = influx.get("url"), influx.get("token"), influx.get("org")
    result: Dict[str, Any] = {
        "generated_at": _iso(datetime.now(timezone.utc)),
        "reachable": False,
        "buckets": [],
        "errors": [],
    }
    if not (url and token and org):
        result["errors"].append("config influxdb incompleta")
        return result

    try:
        with InfluxDBClient(url=url, token=token, org=org, timeout=10000) as client:
            result["reachable"] = bool(client.ping())
            for name, window, label in WINDOWS:
                try:
                    result["buckets"].append(_bucket(client, name, window, label))
                except Exception as exc:
                    result["errors"].append(f"{name}: {exc}")
    except Exception as exc:
        result["errors"].append(str(exc))
    return result


async def get_freshness(config: Dict) -> Dict[str, Any]:
    """Ultimo punto scritto per bucket, con cache breve per non martellare InfluxDB."""
    now = time.time()
    if _cache["data"] and now - _cache["ts"] < CACHE_TTL_SECONDS:
        return _cache["data"]
    data = await asyncio.to_thread(_build, config)
    _cache["ts"] = now
    _cache["data"] = data
    return data
