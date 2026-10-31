"""SSP - aggregato mensile per zona, con il metodo del conguaglio GSE.

  CEI = somma oraria (energia immessa x K x prezzo zonale orario)
  OE  = somma_mese,fascia (energia prelevata x PUN medio di fascia)
  ES  = minimo annuale tra immessa e prelevata
  CS  = min(OE, CEI) + CUsf x ES / 100

K e' il coefficiente di perdita (1,052 in BT).

Due pesature, tarate sui conguagli ufficiali 2022-2024:
  - CEI orario dal 2023; fino al 2022 la misura immessa e' ripartita piatta
    dentro la fascia (delibera 118/03), quindi vale il prezzo medio di fascia.
  - OE sempre a fascia: il prelievo orario sovrastima del 5-6%, la pesatura a
    fascia riproduce il conguaglio entro l'1%.
Le fasce sono F1/F2/F3 con festivi e sabato secondo la regola ARERA; i prezzi
di fascia sono la media delle ore del mese nella fascia.

Misura: Bolletta/ssp_monthly, un punto per mese e zona.
"""

import calendar
import os
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import pytz
from influxdb_client import InfluxDBClient, Point, WritePrecision

BUCKET_ENERGY = 'Solaredge'
BUCKET_PRICES = 'GME'
BUCKET_OUT = 'Bolletta'
ORGANIZATION = 'fotovoltaico'

ZONES = ('NORD', 'CNOR', 'CSUD', 'SUD', 'SICI', 'SARD', 'CALA')
ROME = pytz.timezone('Europe/Rome')
K_LOSS = 1.052  # coefficiente di perdita, reti BT
HOURLY_CEI_FROM = 2023  # dal 2023 la misura immessa e' oraria, prima era piatta per fascia

HOLIDAYS = {(1, 1), (1, 6), (4, 25), (5, 1), (6, 2), (8, 15), (11, 1), (12, 8), (12, 25), (12, 26)}

# Conguagli GSE ufficiali per anno solare, dal Dettaglio Benestare: CS ed
# eccedenza liquidata, piu' le componenti del conguaglio (OE, CEI, immessa,
# prelevata).  Scritti sui punti mensili perche' il pannello confronti la stima
# una componente alla volta e dica se l'errore e' energia o prezzo.
# L'eccedenza di un anno e' liquidata l'anno dopo (colonna "Credito anno
# precedente liquidato"), quindi la cassa dell'anno Y e' CS(Y) + eccedenza(Y-1).
# Chiave assente = anno non ancora liquidato.
UFFICIALE = {
    2021: dict(cs=0.0),
    # 2022: solo l'esito (CS ed eccedenza).  Le sue componenti non chiudono con
    # l'eccedenza dichiarata (CEI - OE darebbe 3,92 euro in meno), quindi non si
    # scrivono finche' non arriva il benestare di quell'anno.
    2022: dict(cs=0.0, ecc=0.0),
    2023: dict(cs=0.0, ecc=0.0, oe=0.0, cei=0.0, es=0.0,
               immessa=0.0, prelevata=0.0),
    2024: dict(cs=0.0, ecc=0.0, oe=0.0, cei=0.0, es=0.0,
               immessa=0.0, prelevata=0.0),
    2025: dict(cs=0.0, ecc=0.0, oe=0.0, cei=0.0, es=0.0,
               immessa=0.0, prelevata=0.0),
}


def _ufficiale(year: int, key: str) -> float:
    return float(UFFICIALE.get(year, {}).get(key, 0.0))

ENERGY_QUERY = '''
from(bucket: "{bucket}")
  |> range(start: {start}, stop: {stop})
  |> filter(fn: (r) => r._measurement == "api" and r.endpoint == "site_energy_details"
      and (r.metric == "Purchased" or r.metric == "Production" or r.metric == "SelfConsumption")
      and exists r._value)
  |> group(columns: ["metric"])
  |> aggregateWindow(every: 1h, fn: sum, createEmpty: false)
  |> group()
  |> pivot(rowKey: ["_time"], columnKey: ["metric"], valueColumn: "_value")
'''

PUN_QUERY = '''
from(bucket: "{bucket}")
  |> range(start: {start}, stop: {stop})
  |> filter(fn: (r) => r._measurement == "gme_prices" and r._field == "pun_mwh" and exists r._value)
  |> group()
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
'''

PZO_QUERY = '''
from(bucket: "{bucket}")
  |> range(start: {start}, stop: {stop})
  |> filter(fn: (r) => r._measurement == "gme_zonal" and r._field == "price_mwh" and exists r._value)
  |> group(columns: ["zone"])
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
'''


def _client() -> InfluxDBClient:
    return InfluxDBClient(url=os.getenv('INFLUXDB_URL', 'http://localhost:8086').rstrip('/'),
                         token=os.getenv('INFLUXDB_TOKEN'),
                         org=os.getenv('INFLUXDB_ORG', ORGANIZATION),
                         timeout=120000)


def _range_literal(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def band(local_dt: datetime) -> str:
    """Fascia ARERA: F1 feriale 8-19, F2 contorno, F3 notte/domenica/festivi."""
    if (local_dt.month, local_dt.day) in HOLIDAYS or local_dt.weekday() == 6:
        return 'F3'
    if local_dt.weekday() == 5:
        return 'F2' if 7 <= local_dt.hour < 23 else 'F3'
    if 8 <= local_dt.hour < 19:
        return 'F1'
    if 7 <= local_dt.hour < 8 or 19 <= local_dt.hour < 23:
        return 'F2'
    return 'F3'


def compute_month(client: InfluxDBClient, year: int, month: int,
                  zones: Tuple[str, ...] = ZONES) -> List[Point]:
    start = ROME.localize(datetime(year, month, 1)).astimezone(timezone.utc)
    last_day = calendar.monthrange(year, month)[1]
    stop = ROME.localize(datetime(year, month, last_day, 23, 59, 59)).astimezone(timezone.utc)

    api = client.query_api()
    energy: Dict[datetime, list] = {}
    for table in api.query(ENERGY_QUERY.format(bucket=BUCKET_ENERGY, start=_range_literal(start), stop=_range_literal(stop))):
        for r in table.records:
            v = r.values
            hour = r.get_time().astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
            acc = energy.setdefault(hour, [0.0, 0.0, 0.0])
            acc[0] += float(v.get('Production') or 0.0)      # Wh prodotti
            acc[1] += float(v.get('SelfConsumption') or 0.0) # Wh autoconsumati
            acc[2] += float(v.get('Purchased') or 0.0)       # Wh prelevati

    pun: Dict[datetime, float] = {}
    for table in api.query(PUN_QUERY.format(bucket=BUCKET_PRICES, start=_range_literal(start), stop=_range_literal(stop))):
        for r in table.records:
            pun[r.get_time()] = float(r.get_value() or 0.0) / 1000.0

    pzo: Dict[Tuple[str, datetime], float] = {}
    for table in api.query(PZO_QUERY.format(bucket=BUCKET_PRICES, start=_range_literal(start), stop=_range_literal(stop))):
        for r in table.records:
            zone = str(r.values.get('zone') or '')
            if zone in zones:
                pzo[(zone, r.get_time())] = float(r.get_value() or 0.0) / 1000.0

    # energia per fascia (la zona non cambia l'energia), prezzi medi di fascia
    e_imm: Dict[str, float] = {}
    e_pre: Dict[str, float] = {}
    pun_acc: Dict[str, List[float]] = {}
    pzo_acc: Dict[Tuple[str, str], List[float]] = {}

    cei_hourly: Dict[str, float] = {}
    for h, (prod, selfc, prel) in energy.items():
        b = band(h.astimezone(ROME))
        imm = max(0.0, prod - selfc) / 1000.0
        e_imm[b] = e_imm.get(b, 0.0) + imm
        e_pre[b] = e_pre.get(b, 0.0) + prel / 1000.0
        if h in pun:
            pun_acc.setdefault(b, []).append(pun[h])
        for zone in zones:
            if (zone, h) in pzo:
                pzo_acc.setdefault((zone, b), []).append(pzo[(zone, h)])
                cei_hourly[zone] = cei_hourly.get(zone, 0.0) + imm * K_LOSS * pzo[(zone, h)]

    pun_band = {b: sum(v) / len(v) for b, v in pun_acc.items() if v}
    pzo_band = {k: sum(v) / len(v) for k, v in pzo_acc.items() if v}

    oe = sum(e_pre.get(b, 0.0) * pun_band.get(b, 0.0) for b in e_pre)

    # Giorni del mese in cui la misura dell'API non e' credibile: produzione e
    # prelievo entrambi a zero (giorno non pubblicato) oppure prelievo nullo con
    # produzione presente, che vorrebbe dire nessun consumo notturno.  Il mese
    # resta stimato sui giorni validi, ma il pannello lo dichiara invece di far
    # sembrare l'errore un difetto del modello.
    per_day: Dict[date, Tuple[float, float]] = {}
    for h, (prod, _selfc, prel) in energy.items():
        local = h.astimezone(ROME)
        p_kwh, notte_kwh = per_day.get(local.date(), (0.0, 0.0))
        if local.hour < 6:  # nessun impianto produce, la casa preleva sempre
            notte_kwh += prel / 1000.0
        per_day[local.date()] = (p_kwh + prod / 1000.0, notte_kwh)
    giorni_incompleti = 0
    oggi = datetime.now(ROME).date()
    for day in range(1, last_day + 1):
        d = date(year, month, day)
        if d > oggi:
            break
        p_kwh, notte_kwh = per_day.get(d, (0.0, 0.0))
        # Un impianto produce qualcosa ogni giorno; e la notte la casa preleva
        # sempre almeno la standby (0,1 kWh in sei ore e' un limite basso).
        if p_kwh <= 0.0 or (p_kwh > 0.5 and notte_kwh < 0.1):
            giorni_incompleti += 1

    points = []
    ts = ROME.localize(datetime(year, month, 1)).astimezone(timezone.utc)
    for zone in zones:
        if year >= HOURLY_CEI_FROM:
            cei = cei_hourly.get(zone, 0.0)
        else:
            cei = sum(e_imm.get(b, 0.0) * K_LOSS * pzo_band.get((zone, b), 0.0) for b in e_imm)
        points.append(
            Point('ssp_monthly')
            .tag('zone', zone)
            .tag('year', str(year))
            .field('prelievo_kwh', round(sum(e_pre.values()), 3))
            .field('immessa_kwh', round(sum(e_imm.values()), 3))
            .field('oe_eur', round(oe, 4))
            .field('cei_eur', round(cei, 4))
            .field('ufficiale_cs_eur', _ufficiale(year, 'cs'))
            .field('ufficiale_ecc_eur', _ufficiale(year, 'ecc'))
            .field('ufficiale_oe_eur', _ufficiale(year, 'oe'))
            .field('ufficiale_cei_eur', _ufficiale(year, 'cei'))
            .field('ufficiale_immessa_kwh', _ufficiale(year, 'immessa'))
            .field('ufficiale_prelievo_kwh', _ufficiale(year, 'prelevata'))
            .field('ufficiale_ecc_prec_eur', _ufficiale(year - 1, 'ecc'))
            .field('giorni_incompleti', giorni_incompleti)
            .time(ts, WritePrecision.S)
        )
    return points


def write_points(points: List[Point]) -> int:
    if not points:
        return 0
    with _client() as client:
        with client.write_api() as writer:
            writer.write(bucket=BUCKET_OUT, org=ORGANIZATION, record=points)
    return len(points)


def update_range(start_day: date, end_day: date) -> int:
    total = 0
    y, m = start_day.year, start_day.month
    while (y, m) <= (end_day.year, end_day.month):
        with _client() as client:
            points = compute_month(client, y, m)
        total += write_points(points)
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return total


def update_recent(months: int = 2) -> int:
    today = datetime.now(ROME).date()
    start = today.replace(day=1)
    for _ in range(max(0, months - 1)):
        start = (start - timedelta(days=1)).replace(day=1)
    return update_range(start, today)
