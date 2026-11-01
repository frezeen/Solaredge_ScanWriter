"""Backfill storico: SolarEdge e GME dal giorno dell'impianto a oggi.

L'api costa due chiamate ma la finestra decide la spesa: `QUARTER_HOUR` arriva a
una settimana, `DAY` a un mese intero (`HOUR` si ferma a 24 ore), quindi la
history va **un mese per due chiamate** a granularita' giornaliera e scrive solo
i giorni che mancano o che sono corti. Un giorno gia' raccolto a 15 minuti dal
collector non si tocca: due granularita' sullo stesso giorno contano quel giorno
due volte. GME resta un mese per chiamata. La data di partenza e' l'installazione,
letta da `/sites/{id}`; `--history <anno>` limita a un anno. La bolletta non ha
una sorgente storica: il collector legge i valori correnti.
"""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import time

import pytz

from collector.collector_api import CollectorAPI
from collector.solaredge_v2 import SolarEdgeV2, SolarEdgeV2Error, ROME
from flows.gme_flow import run_gme_month_flow
from parser.api_parser import create_parser
from storage.writer_influx import InfluxWriter
from utils.color_logger import color

# Un giorno si ripara solo se manca davvero: sotto un quarto del totale il
# dettaglio orario vale piu' del Wh mancante (l'SSP prezza le fasce per ora), e
# gli ultimi 7 giorni li ripara gia' il collector a 15 minuti.
TOLERANZA = 0.25


class HistoryManager:
    """Rilegge dal fornitore i mesi mancanti o corti e li riscrive in InfluxDB."""

    def __init__(self, log, cache, config, year=None):
        self.log = log
        self.cache = cache
        self.config = config
        self.year = int(year) if year else None

    def _installation_date(self) -> date:
        """Il giorno in cui l'impianto e' partito, da /sites/{id}."""
        meta = SolarEdgeV2(self._site_id()).site_meta()
        for key in ("installationDate", "firstTelemetryTime"):
            stamp = meta.get(key)
            if stamp:
                return date.fromisoformat(str(stamp)[:10])
        return date.today() - timedelta(days=365)

    def _site_id(self) -> str:
        with CollectorAPI(cache=self.cache, scheduler=None) as collector:
            return collector.site_id

    def run(self) -> int:
        if self.year:
            start = date(self.year, 1, 1)
            end = min(date(self.year, 12, 31) + timedelta(days=1), date.today() + timedelta(days=1))
        else:
            start = self._installation_date()
            end = date.today() + timedelta(days=1)

        self.log.info(color.bold(f"📜 Storico dal {start} al {end - timedelta(days=1)}"))
        self._api(start, end)
        self._gme(start, end)
        self.log.info(color.warning("   Bolletta: nessuna sorgente storica da rileggere, i suoi dati sono correnti"))
        return 0

    def _api(self, start: date, end: date) -> None:
        """Un mese per due chiamate; il mese in corso lo tiene il collector live."""
        with CollectorAPI(cache=self.cache, scheduler=None) as collector:
            site_id = collector.site_id
            v2 = SolarEdgeV2(site_id)
            year, month = start.year, start.month
            while (year, month) < (end.year, end.month):
                try:
                    self._api_month(v2, site_id, year, month)
                except SolarEdgeV2Error as e:
                    self.log.error(color.error(f"   api  {year}-{month:02d}: {e}"))
                    self.log.warning(color.warning("   ciclo api fermato"))
                    return
                month += 1
                if month > 12:
                    year, month = year + 1, 1

    def _api_month(self, v2: SolarEdgeV2, site_id: str, year: int, month: int) -> None:
        """Ripara i giorni del mese che mancano o che sono corti, canale per canale."""
        label = f"{year}-{month:02d}"
        # il sigillo e' la cache del mese: un mese gia' guardato non si rilegge,
        # o un backfill lungo non passa mai il tetto giornaliero (ripartirebbe
        # sempre dai primi mesi, spendendo tutto in riletture inutili)
        if self.cache.peek_cached_data("api_ufficiali", "site_energy_details", label):
            self.log.info(color.dim(f"   api  {label}: sigillato, saltato"))
            return
        payload = v2.month_payload(year, month)
        meters = (payload.get("energyDetails") or {}).get("meters") or []
        have = self._api_sums(year, month)
        short: List[Tuple[str, str]] = []
        for meter in meters:
            for value in meter.get("values") or []:
                key = (meter["type"], value["date"][:10])
                if self._needs_repair(have.get(key), float(value.get("value") or 0.0)):
                    short.append(key)
        if short:
            self._repair(payload, short, site_id)
            self.log.info(color.warning(
                f"   api  {label}: {len(short)} giorni/canali riparati a granularita' giornaliera"))
        else:
            self.log.info(color.dim(f"   api  {label}: completo"))
        self.cache.save_to_cache("api_ufficiali", "site_energy_details", label, payload)

    def _api_sums(self, year: int, month: int) -> Dict[Tuple[str, str], float]:
        """Quanto c'e' gia' in Influx, per canale e giorno locale."""
        start = ROME.localize(datetime(year, month, 1))
        stop = ROME.localize(datetime(year + 1, 1, 1) if month == 12
                             else datetime(year, month + 1, 1))
        flux = f'''import "timezone"
option location = timezone.location(name: "Europe/Rome")
from(bucket:"{InfluxWriter().bucket}")
  |> range(start: {start.isoformat()}, stop: {stop.isoformat()})
  |> filter(fn: (r) => r._measurement == "api" and r.endpoint == "site_energy_details" and exists r.metric)
  |> group(columns: ["metric"])
  |> aggregateWindow(every: 1d, fn: sum, createEmpty: false)
  |> keep(columns: ["_time", "_value", "metric"])'''
        out: Dict[Tuple[str, str], float] = {}
        for table in InfluxWriter().query(flux):
            for record in table.records:
                values = record.values
                # aggregateWindow etichetta la finestra con la sua *fine*: il giorno
                # coperto e' quello prima, o si sfaserebbe tutto di 24 ore
                day = (values["_time"].astimezone(ROME) - timedelta(days=1)).date().isoformat()
                out[(values["metric"], day)] = float(values["_value"])
        return out

    @staticmethod
    def _needs_repair(have: Optional[float], want: float) -> bool:
        if want <= 0.0:
            return False            # il fornitore non ha nulla per questo giorno
        if have is None:
            return True             # giorno assente
        return abs(have - want) > TOLERANZA * want

    @staticmethod
    def _day_bounds(day: str) -> Tuple[datetime, datetime]:
        start = ROME.localize(datetime.strptime(day, "%Y-%m-%d")).astimezone(pytz.utc)
        return start, start + timedelta(days=1)

    def _repair(self, payload: Dict[str, Any], short: List[Tuple[str, str]], site_id: str) -> None:
        """Cancella il canale del giorno e ci scrive il totale giornaliero.

        Un giorno mezzo raccolto (meter fino a sera, produzione fino a meta'
        mattina) non si somma al totale: i suoi punti vanno via prima.
        """
        needed = set(short)
        details = {"unit": payload["energyDetails"].get("unit", "Wh"),
                   "timeUnit": payload["energyDetails"].get("timeUnit"),
                   "meters": []}
        for meter in payload["energyDetails"]["meters"]:
            values = [v for v in meter.get("values") or []
                      if (meter["type"], v["date"][:10]) in needed]
            if values:
                details["meters"].append({"type": meter["type"], "values": values})
        with InfluxWriter() as writer:
            for metric, day in sorted(needed):
                start, stop = self._day_bounds(day)
                writer.delete_range(
                    start, stop,
                    f'_measurement="api" AND endpoint="site_energy_details" AND metric="{metric}"')
            points = create_parser().parse({"site_energy_details": {"energyDetails": details}}, site_id)
            writer.write_points(points, measurement_type="api")

    def _gme(self, start: date, end: date) -> None:
        """Un mese per chiamata, con una pausa: GME limita le raffiche."""
        year, month = start.year, start.month
        last = (end.year, end.month)
        while (year, month) <= last:
            try:
                run_gme_month_flow(self.log, self.cache, self.config, year, month)
            except Exception as e:                  # il flusso logga e prosegue
                self.log.error(color.error(f"   gme {year}-{month:02d}: {e}"))
            month += 1
            if month > 12:
                year, month = year + 1, 1
            time.sleep(4)


def run_history_flow(log, cache, config, year=None) -> int:
    """Wrapper per eseguire HistoryManager come flow standard

    Args:
        year: limita a un anno (default: dal giorno dell'impianto)
    """
    return HistoryManager(log, cache, config, year=year).run()
