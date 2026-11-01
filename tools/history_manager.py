"""Backfill storico: SolarEdge e GME dal giorno dell'impianto a oggi.

L'api si rilegge **una settimana per due chiamate, a 15 minuti**: e' la
finestra massima su `QUARTER_HOUR` ed e' la granularita' che serve all'SSP, che
prezza le fasce F1/F2/F3 per ora (`aggregateWindow(every: 1h)`). Le alternative
non reggono: `HOUR` si ferma a 24 ore e `DAY`, che pure accetta un mese, torna un
solo totale giornaliero — l'SSP lo metterebbe tutto in F3. GME resta un mese per
chiamata. Ogni settimana letta si **sigilla** in cache e si salta la volta dopo,
cosi' un backfill lungo attraversa il tetto giornaliero senza ricominciare da
capo. L'ultima settimana e' del collector live, che rilegge gli ultimi 7 giorni a
ogni giro. La data di partenza e' l'installazione, letta da `/sites/{id}`;
`--history <anno>` limita a un anno. La bolletta non ha una sorgente storica: il
collector legge i valori correnti.
"""

from datetime import date, datetime, timedelta
import time

from collector.collector_api import CollectorAPI
from collector.solaredge_v2 import SolarEdgeV2, SolarEdgeV2Error, MAX_RANGE_DAYS
from flows.gme_flow import run_gme_month_flow
from parser.api_parser import create_parser
from storage.writer_influx import InfluxWriter
from utils.color_logger import color

WEEK_ENDPOINT = "site_energy_details_week"     # il sigillo settimanale, separato dai file giorno


class HistoryManager:
    """Rilegge dal fornitore le settimane e i mesi che mancano e li riscrive in InfluxDB."""

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
        """Una settimana per due chiamate a 15 minuti; l'ultima settimana la tiene il live."""
        with CollectorAPI(cache=self.cache, scheduler=None) as collector:
            site_id = collector.site_id
            v2 = SolarEdgeV2(site_id)
            tail = date.today() - timedelta(days=MAX_RANGE_DAYS)
            day = start
            while day < min(end, tail):
                stop = min(day + timedelta(days=MAX_RANGE_DAYS), tail)
                if self.cache.peek_cached_data("api_ufficiali", WEEK_ENDPOINT, day.isoformat()):
                    self.log.info(color.dim(
                        f"   api  {day} .. {stop - timedelta(days=1)}: sigillata, saltata"))
                    day = stop
                    continue
                try:
                    payload = v2.range_payload(day, stop)
                except SolarEdgeV2Error as e:
                    self.log.error(color.error(f"   api  {day}: {e}"))
                    self.log.warning(color.warning("   ciclo api fermato"))
                    return
                points = create_parser().parse({'site_energy_details': payload}, site_id)
                with InfluxWriter() as writer:
                    writer.write_points(points, measurement_type="api")
                collector.archive_payload('site_energy_details', payload)
                self.cache.save_to_cache("api_ufficiali", WEEK_ENDPOINT, day.isoformat(), payload)
                self.log.info(color.dim(
                    f"   api  {day} .. {stop - timedelta(days=1)} -> {len(points)} punti"))
                day = stop

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
