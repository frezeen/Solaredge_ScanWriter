"""CUsf SSP: scarica il valore ARERA dell'anno e lo conserva in Bolletta/ssp_cusf.

ARERA pubblica a marzo dell'anno successivo, con URL e nomi file che cambiano
ogni anno: si provano alcuni schemi noti e, se nessuno risponde, resta il valore
stimato (ultimo noto) marcato come tale.
"""

import io
import os
import re
import urllib.request
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import openpyxl
from influxdb_client import InfluxDBClient, Point, WritePrecision

BUCKET = 'Bolletta'
ORG = 'fotovoltaico'
BASE = 'https://www.arera.it/comunicati-operatore/dettaglio/'

# Valori verificati (utenze domestiche BT, c€/kWh) — seeding iniziale
KNOWN = {2021: 5.078, 2022: 2.816, 2023: 4.714, 2024: 6.42, 2025: 6.487}

UA = {'User-Agent': 'Mozilla/5.0'}


def _urls(year: int) -> List[str]:
    nxt = str(year + 1)[-2:]
    return [
        BASE + f'valori-del-corrispettivo-unitario-di-scambio-forfetario-anno-{year}-{nxt}',
        BASE + f'valori-corrispettivo-unitario-scambio-forfetario-anno-{year}-{nxt}',
        BASE + f'valori-del-corrispettivo-unitario-di-scambio-forfetario-per-lanno-{year}',
        BASE + f'valori-del-corrispettivo-unitario-di-scambio-forfetario-{year}',
    ]


def _get(url: str, timeout: int = 60) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def fetch_year(year: int) -> Optional[Tuple[float, str]]:
    """Cerca l'allegato xlsx del comunicato e legge la riga utenze domestiche BT."""
    for page in _urls(year):
        try:
            html = _get(page).decode('utf-8', 'ignore')
        except Exception:
            continue
        links = re.findall(r'href="([^"]+\.xlsx)"', html)
        for link in links:
            url = link if link.startswith('http') else 'https://www.arera.it' + link
            try:
                wb = openpyxl.load_workbook(io.BytesIO(_get(url)), data_only=True)
            except Exception:
                continue
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True):
                    first = str(row[0] or '')
                    if 'domestiche' in first.lower() and 'bt' in first.lower():
                        nums = [c for c in row if isinstance(c, (int, float))]
                        if len(nums) >= 3:
                            return round(float(nums[-3]), 3), url
    return None


def _client() -> InfluxDBClient:
    return InfluxDBClient(url=os.getenv('INFLUXDB_URL', 'http://localhost:8086').rstrip('/'),
                         token=os.getenv('INFLUXDB_TOKEN'),
                         org=os.getenv('INFLUXDB_ORG', ORG),
                         timeout=60000)


def _stored(client: InfluxDBClient, year: int) -> Optional[Tuple[float, str]]:
    q = (f'from(bucket:"{BUCKET}") |> range(start: 2021-01-01T00:00:00Z) '
         f'|> filter(fn:(r)=>r._measurement=="ssp_cusf" and r.year=="{year}") '
         '|> last() |> keep(columns:["_value","fonte"])')
    for table in client.query_api().query(q):
        for r in table.records:
            return float(r.values.get('_value') or 0.0), str(r.values.get('fonte') or '')
    return None


def _write(client: InfluxDBClient, year: int, value: float, fonte: str) -> None:
    point = (Point('ssp_cusf')
             .tag('year', str(year))
             .tag('fonte', fonte)
             .field('cusf_c', float(value))
             .time(datetime(year, 1, 1).replace(tzinfo=None), WritePrecision.S))
    with client.write_api() as writer:
        writer.write(bucket=BUCKET, org=ORG, record=point)


def ensure(log=None, years: Optional[List[int]] = None) -> Dict[int, float]:
    """Garantisce un valore per ogni anno: reale se ARERA lo ha pubblicato, stimato altrimenti."""
    now = datetime.now()
    if years is None:
        years = [now.year, now.year - 1]
    out: Dict[int, float] = {}
    with _client() as client:
        last_known = max(KNOWN.values())
        for year in years:
            stored = _stored(client, year)
            if stored and stored[1] == 'ARERA':
                out[year] = stored[0]
                continue
            # Pubblicato a marzo dell'anno successivo: prima non ha senso chiedere
            due = year < now.year or now.month >= 3
            fetched = fetch_year(year) if due else None
            if fetched:
                value, _ = fetched
                _write(client, year, value, 'ARERA')
                out[year] = value
                if log:
                    log.info(f'CUsf {year} = {value} c€/kWh (ARERA)')
            else:
                value = stored[0] if stored else KNOWN.get(year, last_known)
                _write(client, year, value, 'stimato')
                out[year] = value
                if log:
                    log.warning(f'CUsf {year}: non pubblicato, uso {value} c€/kWh (stimato)')
    return out


def seed(log=None) -> None:
    """Scrive i valori storici verificati (idempotente)."""
    with _client() as client:
        for year, value in KNOWN.items():
            _write(client, year, value, 'ARERA')
    if log:
        log.info(f'CUsf: seminati {len(KNOWN)} anni ({min(KNOWN)}-{max(KNOWN)})')
