"""GME Parser - Conversione prezzi GME in InfluxDB Points"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
import logging
import pytz

try:
    from influxdb_client import Point, WritePrecision
    INFLUX_AVAILABLE = True
except ImportError:
    INFLUX_AVAILABLE = False
    Point = None

logger = logging.getLogger(__name__)


class GMEParser:
    """Parser per convertire dati GME in InfluxDB Points"""

    def __init__(self, timezone: str = 'Europe/Rome'):
        """
        Inizializza il parser GME

        Args:
            timezone: Timezone per i timestamp (default: Europe/Rome)
        """
        self.timezone = pytz.timezone(timezone)

    def parse(self, gme_data: Dict[str, Any]) -> List[Point]:
        """
        Converte dati GME in InfluxDB Points

        Args:
            gme_data: Dizionario con:
                - date: data in formato YYYY-MM-DD
                - prices: lista di prezzi orari
                - source: "GME"
                - market: "MGP"

        Returns:
            Lista di InfluxDB Point objects pronti per scrittura
        """
        if not INFLUX_AVAILABLE:
            logger.error("InfluxDB client non disponibile, impossibile creare Points")
            return []

        if not gme_data or 'prices' not in gme_data:
            logger.warning("Dati GME vuoti o malformati")
            return []

        date_str = gme_data.get('date')
        prices = gme_data.get('prices', [])
        source = gme_data.get('source', 'GME')
        market = gme_data.get('market', 'MGP')

        if not date_str:
            logger.error("Data mancante nei dati GME")
            return []

        points = []

        for price_data in prices:
            try:
                point = self._create_gme_point(price_data, date_str, source, market)
                if point:
                    points.append(point)
            except Exception as e:
                logger.error(f"Errore creazione point GME per ora {price_data.get('hour')}: {e}")
                continue

        logger.info(f"✅ Generati {len(points)} InfluxDB Points GME per {date_str}")
        return points

    def _create_gme_point(self, price_data: Dict[str, Any], date_str: str,
                         source: str, market: str) -> Point:
        """
        Crea un singolo InfluxDB Point per un prezzo orario

        Args:
            price_data: Dizionario con hour, pun_mwh, pun_kwh, e opzionalmente date
            date_str: Data di fallback in formato YYYY-MM-DD
            source: Fonte dati (es. "GME")
            market: Mercato (es. "MGP")

        Returns:
            InfluxDB Point object
        """
        hour = price_data.get('hour')
        pun_mwh = price_data.get('pun_mwh')
        pun_kwh = price_data.get('pun_kwh')

        # Usa la data specifica del prezzo se presente (per history mode), altrimenti quella del contenitore
        item_date_str = price_data.get('date', date_str)

        if hour is None or pun_kwh is None:
            logger.warning(f"Dati incompleti per punto GME: {price_data}")
            return None

        # Crea timestamp per l'ora specifica
        # Ora 1 = 00:00-01:00, Ora 2 = 01:00-02:00, etc.
        # Usiamo l'inizio dell'ora (hour - 1)
        # Gestione speciale per ora 25 (cambio ora solare): diventa 00:00 del giorno dopo
        if hour == 25:
            # Ora 25 = mezzanotte del giorno successivo
            date_obj = datetime.strptime(item_date_str, '%Y-%m-%d')
            next_day = date_obj + timedelta(days=1)
            timestamp_str = next_day.strftime('%Y-%m-%d') + " 00:00:00"
        else:
            timestamp_str = f"{item_date_str} {hour-1:02d}:00:00"

        try:
            # Parse timestamp con timezone
            ts_local = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            ts_aware = self.timezone.localize(ts_local)
            ts_utc = ts_aware.astimezone(pytz.utc)
            ts_ns = int(ts_utc.timestamp() * 1_000_000_000)
        except Exception as e:
            logger.error(f"Errore parsing timestamp {timestamp_str}: {e}")
            return None

        # Crea Point InfluxDB
        point = Point("gme_prices")

        # Tags (aggiunti year e month per query efficienti in history mode)
        point.tag("source", source)
        point.tag("market", market)
        point.tag("hour", str(hour))
        point.tag("year", str(ts_local.year))
        point.tag("month", ts_local.strftime('%B'))
        point.tag("day", str(ts_local.day))

        # Fields (manteniamo i nomi standard PUN del mercato elettrico)
        # Salviamo solo MWh come richiesto (valore originale)
        point.field("pun_mwh", float(pun_mwh))

        # Timestamp
        point.time(ts_ns, WritePrecision.NS)

        return point

    def create_monthly_avg_point(self, prices: List[float], date: datetime) -> Optional[Point]:
        """
        Crea un punto per la media mensile da una lista di prezzi

        Args:
            prices: Lista di prezzi in €/kWh
            date: Data di riferimento (usata per anno/mese)

        Returns:
            InfluxDB Point o None se lista vuota
        """
        if not prices:
            return None

        avg_kwh = round(sum(prices) / len(prices), 3)

        # Create monthly average point
        monthly_point = Point("gme_monthly_avg")
        monthly_point.tag("source", "GME")
        monthly_point.tag("market", "MGP")
        monthly_point.tag("year", str(date.year))
        monthly_point.tag("month", date.strftime('%B'))

        # Solo €/kWh come richiesto
        monthly_point.field("pun_kwh_avg", float(avg_kwh))

        # Use first day of month as timestamp
        first_day = datetime(date.year, date.month, 1)
        ts_aware = self.timezone.localize(first_day)
        ts_utc = ts_aware.astimezone(pytz.utc)
        ts_ns = int(ts_utc.timestamp() * 1_000_000_000)
        monthly_point.time(ts_ns, WritePrecision.NS)

        logger.info(f"📊 PUN medio mensile calcolato: {avg_kwh:.6f} €/kWh ({len(prices)} ore)")
        return monthly_point



def create_parser(timezone: str = 'Europe/Rome') -> GMEParser:
    """Factory function per creare un parser GME"""
    return GMEParser(timezone=timezone)
