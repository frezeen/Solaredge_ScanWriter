"""SolarEdge Monitoring API v2 (Site Access / OAuth 2.0).

Sostituisce la V1, ritirata il 1/11/2026. Due chiamate per endpoint bastano:
ogni risposta contiene la giornata intera a 15 minuti.

I payload tornano nella forma V1 (`energyDetails.meters[].values`) cosi' il
parser, Influx e le dashboard restano identici.
"""

from __future__ import annotations

import gzip
import json
import math
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytz
import requests

BASE = "https://monitoringapi.solaredge.com/v2"
ROME = pytz.timezone("Europe/Rome")

STATE_DIR = Path("cache/oauth")
TOKEN_FILE = STATE_DIR / "solaredge_v2_token.json"
META_FILE = STATE_DIR / "site_meta.json"
STATE_FILE = STATE_DIR / "api_state.json"
LEDGER_FILE = STATE_DIR / "credit_ledger.json"

DAILY_CAP = 64          # 2.000 crediti al mese / 31 giorni: la cadenza vera sta nei gate
METERS_GATE_MIN = 55    # il loop gira a 15': cosi' i contatori si leggono ogni ora
META_TTL_DAYS = 30
CLOSE_AFTER_SUNSET_MIN = 20
SETTLE_HOUR = 6         # ora da cui l'ultimo quarto d'ora di ieri e' chiuso
MAX_RANGE_DAYS = 7      # limite del fornitore su QUARTER_HOUR: una settimana
RATE_CALLS = 10         # limite del fornitore: 10 chiamate al minuto
RATE_WINDOW = 60


class SolarEdgeV2Error(RuntimeError):
    pass


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _write_json(path: Path, obj: Any, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj))
    if private:
        os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _immutable_site_fields() -> Dict[str, Any]:
    """Impianto e moduli: la V2 non li espone e non cambiano nel tempo.

    Si leggono dal payload v1 piu' recente rimasto in archivio; se l'archivio
    non c'e' restano assenti e il pannello mostra quelle colonne vuote.
    """
    try:
        files = sorted(Path("cache/api_ufficiali/site_details").glob("*.json.gz"))
        if not files:
            return {}
        details = json.loads(gzip.GzipFile(files[-1]).read())["data"]["details"]
        return {k: details[k] for k in ("type", "primaryModule") if k in details}
    except Exception:
        return {}


def _series_union(a: List[Dict[str, Any]], b: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Unisce due serie a 15 minuti; in caso di stessa data vince la seconda."""
    merged = {item["date"]: item["value"] for item in a}
    merged.update({item["date"]: item["value"] for item in b})
    return [{"date": d, "value": v} for d, v in sorted(merged.items())]


def sun_times(lat: float, lon: float, day: date, tz=ROME) -> Tuple[datetime, datetime]:
    """Alba e tramonto, approssimazione NOAA (errore di pochi minuti)."""
    n = day.toordinal() - date(2000, 1, 1).toordinal() + 0.0008
    mean = math.radians((357.5291 + 0.98560028 * n) % 360)
    center = 1.9148 * math.sin(mean) + 0.02 * math.sin(2 * mean) + 0.0003 * math.sin(3 * mean)
    lam = math.radians((math.degrees(mean) + center + 180.0 + 102.9372) % 360)
    j_transit = 2451545.0 + n + 0.0053 * math.sin(mean) - 0.0069 * math.sin(2 * lam)
    decl = math.asin(math.sin(lam) * math.sin(math.radians(23.44)))
    try:
        cos_w = (math.sin(math.radians(-0.833)) - math.sin(math.radians(lat)) * math.sin(decl)) / (
            math.cos(math.radians(lat)) * math.cos(decl)
        )
    except ZeroDivisionError:
        cos_w = 1.0
    if cos_w <= -1:      # sole sempre sopra l'orizzonte
        return (ROME.localize(datetime.combine(day, datetime.min.time())),
                ROME.localize(datetime.combine(day, datetime.max.time())))
    if cos_w >= 1:       # sole mai sopra
        noon = ROME.localize(datetime.combine(day, datetime.min.time())) + timedelta(hours=12)
        return noon, noon
    w = math.degrees(math.acos(cos_w))

    def _to_local(j: float) -> datetime:
        return datetime.fromtimestamp((j - 2440587.5) * 86400.0, pytz.utc).astimezone(tz)

    return _to_local(j_transit - w / 360.0), _to_local(j_transit + w / 360.0)


class SolarEdgeV2:
    """Client minimale: token OAuth, due endpoint, registro dei crediti."""

    def __init__(self, site_id: str, timeout: int = 40) -> None:
        self.site_id = str(site_id)
        self.timeout = timeout
        self._access: Optional[str] = None
        self._access_expires: float = 0.0

    # ------------------------------------------------------------------ token
    def _stored_refresh(self) -> str:
        rt = (_read_json(TOKEN_FILE, {}) or {}).get("refresh_token")
        if rt:
            return rt
        rt = os.getenv("SOLAREDGE_V2_REFRESH_TOKEN", "")
        if not rt:
            raise SolarEdgeV2Error("nessun refresh token: manca in .env e in %s" % TOKEN_FILE)
        return rt

    def _save_refresh(self, token: str) -> None:
        _write_json(TOKEN_FILE, {"refresh_token": token, "obtained_at": int(time.time())}, private=True)

    def access_token(self, force: bool = False) -> str:
        if not force and self._access and time.time() < self._access_expires - 300:
            return self._access
        rt = self._stored_refresh()
        payload = {
            "grant_type": "refresh_token",
            "client_id": os.environ["SOLAREDGE_V2_CLIENT_ID"],
            "client_secret": os.environ["SOLAREDGE_V2_CLIENT_SECRET"],
            "refresh_token": rt,
        }
        r = requests.post(BASE + "/oauth2/token", json=payload, timeout=self.timeout)
        if r.status_code != 200:
            raise SolarEdgeV2Error("refresh token rifiutato (%s): %s" % (r.status_code, r.text[:200]))
        data = r.json()
        self._access = data["access_token"]
        self._access_expires = time.time() + int(data.get("expires_in", 7200))
        new_rt = data.get("refresh_token")
        if new_rt and new_rt != rt:
            self._save_refresh(new_rt)      # ruota a ogni refresh: va scritto subito
        return self._access

    # ----------------------------------------------------------------- ledger
    @staticmethod
    def _rate_wait(stamps: List[str], now: float) -> float:
        """Secondi di attesa perche' la prossima chiamata resti dentro 10 al minuto."""
        if len(stamps) < RATE_CALLS:
            return 0.0
        try:
            oldest = ROME.localize(datetime.strptime(stamps[-RATE_CALLS], "%Y-%m-%d %H:%M:%S"))
        except Exception:
            return 0.0
        return max(0.0, RATE_WINDOW - (now - oldest.timestamp()))

    def _throttle(self, led: Dict[str, Any]) -> None:
        """Il fornitore accetta 10 chiamate al minuto: si aspetta sul ledger condiviso."""
        stamps = [c.get("ts", "") for c in led.get("last") or [] if c.get("ts")]
        wait = self._rate_wait(stamps, time.time())
        if wait > 0:
            time.sleep(wait + 0.5)

    def _spend(self, path: str) -> None:
        today = date.today().isoformat()
        month = today[:7]
        led = _read_json(LEDGER_FILE, {}) or {}
        if led.get("day") != today:
            led = {"day": today, "month": month, "day_calls": 0,
                   "month_calls": (led.get("month_calls", 0) if led.get("month") == month else 0),
                   "total_calls": led.get("total_calls", 0), "last": []}
        if led.get("month") != month:
            led["month"] = month
            led["month_calls"] = 0
        if led["day_calls"] >= DAILY_CAP:
            raise SolarEdgeV2Error("tetto giornaliero di %d chiamate raggiunto: fermo" % DAILY_CAP)
        self._throttle(led)
        led["day_calls"] += 1
        led["month_calls"] += 1
        led["total_calls"] = led.get("total_calls", 0) + 1
        led["last"] = (led.get("last") or [])[-19:] + [
            {"ts": datetime.now(ROME).strftime("%Y-%m-%d %H:%M:%S"), "path": path}
        ]
        _write_json(LEDGER_FILE, led)

    def ledger(self) -> Dict[str, Any]:
        return _read_json(LEDGER_FILE, {}) or {}

    # -------------------------------------------------------------------- GET
    def _get(self, path: str, params: Dict[str, Any]) -> Any:
        self._spend(path)
        url = BASE + path
        headers = {"Authorization": "Bearer " + self.access_token(), "Accept": "application/json"}
        r = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        if r.status_code == 401:        # token scaduto a meta': un solo ritentativo
            headers["Authorization"] = "Bearer " + self.access_token(force=True)
            r = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        if r.status_code == 429:        # raffica troppo fitta: aspetta e riprova
            for wait in (5, 15, 30):
                time.sleep(wait)
                r = requests.get(url, headers=headers, params=params, timeout=self.timeout)
                if r.status_code != 429:
                    break
        if r.status_code == 429:
            raise SolarEdgeV2Error("429 rate limit su %s" % path)
        if r.status_code != 200:
            raise SolarEdgeV2Error("%s -> %s: %s" % (path, r.status_code, r.text[:200]))
        return r.json()

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """GET generico su /v2, per gli endpoint dichiarati nel catalogo."""
        return self._get(path, params or {})

    # ------------------------------------------------------------------- dati
    def site_meta(self) -> Dict[str, Any]:
        meta = _read_json(META_FILE, {}) or {}
        fresh = meta.get("_fetched", 0) > time.time() - META_TTL_DAYS * 86400
        if meta and fresh:
            return meta
        data = self._get("/sites/%s" % self.site_id, {})
        meta = dict(data)
        meta["_fetched"] = int(time.time())
        _write_json(META_FILE, meta)
        return meta

    def site_details_payload(self) -> Dict[str, Any]:
        """Forma V1 per il parser: {'details': {...}}.

        La V2 non pubblica `status`, `type` e `primaryModule`: il primo arriva da
        `activationStatus`, gli altri due non cambiano mai e si leggono
        dall'archivio v1 congelato, che e' l'unica cosa che se ne legge ancora.
        """
        meta = self.site_meta()
        details = {k: v for k, v in meta.items() if not k.startswith("_")}
        if details.get("activationStatus"):
            details["status"] = str(details["activationStatus"]).capitalize()
        for key, value in _immutable_site_fields().items():
            details.setdefault(key, value)
        return {"details": details}

    def _window(self, start: date, stop: date) -> Dict[str, str]:
        """Finestra [start, stop) in UTC. La V2 accetta una settimana al massimo."""
        begin = ROME.localize(datetime.combine(start, datetime.min.time()))
        end = ROME.localize(datetime.combine(stop, datetime.min.time())) - timedelta(seconds=1)
        return {"from": begin.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "to": end.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

    @staticmethod
    def _local_stamp(iso: str) -> Optional[str]:
        try:
            return datetime.fromisoformat(iso).astimezone(ROME).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    def energy_values(self, start: date, stop: date) -> Dict[str, float]:
        data = self._get("/sites/%s/energy" % self.site_id,
                         {**self._window(start, stop), "resolution": "QUARTER_HOUR", "unit": "WH"})
        out: Dict[str, float] = {}
        for item in data.get("values") or []:
            stamp = self._local_stamp(item.get("timestamp") or "")
            value = item.get("value")
            if stamp and value is not None:
                out[stamp] = float(value)
        return out

    def meter_values(self, start: date, stop: date) -> Dict[str, Dict[str, Dict[str, float]]]:
        data = self._get("/sites/%s/meters/telemetry" % self.site_id,
                         {**self._window(start, stop), "resolution": "QUARTER_HOUR"})
        out: Dict[str, Dict[str, Dict[str, float]]] = {}
        for serial, metrics in (data.get("meters") or {}).items():
            per_metric: Dict[str, Dict[str, float]] = {}
            for name, series in (metrics or {}).items():
                values = {}
                for item in (series or {}).get("values") or []:
                    stamp = self._local_stamp(item.get("timestamp") or "")
                    value = item.get("value")
                    if stamp and value is not None:
                        values[stamp] = float(value)
                if values:
                    per_metric[name] = values
            if per_metric:
                out[serial] = per_metric
        return out

    def energy_details_payload(self, day: Optional[date] = None,
                               with_production: bool = True,
                               include_previous: bool = False) -> Dict[str, Any]:
        """Forma V1 (`energyDetails.meters[].values`) costruita da V2.

        I contatori si leggono sempre (una chiamata); la produzione solo se
        `with_production`, perche' di notte non cambia. `include_previous`
        aggiunge il giorno prima: l'ultimo quarto d'ora di una giornata viene
        letto mentre e' ancora in corso e il fornitore lo chiude dopo.
        """
        day = day or datetime.now(ROME).date()
        payload = self._payload_for(day, day + timedelta(days=1), with_production)
        if include_previous:
            prev = self._payload_for(day - timedelta(days=1), day, False)
            merged = {m["type"]: m for m in payload["energyDetails"]["meters"]}
            for meter in prev["energyDetails"]["meters"]:
                if meter["values"]:
                    slot = merged.setdefault(meter["type"], {"type": meter["type"], "values": []})
                    slot["values"] = _series_union(slot["values"], meter["values"])
        return payload

    def range_payload(self, start: date, stop: date) -> Dict[str, Any]:
        """Forma V1 per un intervallo [start, stop), al massimo una settimana.

        E' il limite del fornitore su QUARTER_HOUR ("maximum window of 1 week"):
        una settimana costa due chiamate, una per endpoint.
        """
        if (stop - start) > timedelta(days=MAX_RANGE_DAYS):
            raise SolarEdgeV2Error("la V2 accetta al massimo %d giorni per chiamata" % MAX_RANGE_DAYS)
        return self._payload_for(start, stop, True)

    def _payload_for(self, start: date, stop: date, with_production: bool) -> Dict[str, Any]:
        meters = self.meter_values(start, stop)
        prod = self.energy_values(start, stop) if with_production else {}

        def _first(metric: str) -> Dict[str, float]:
            for metrics in meters.values():
                if metric in metrics:
                    return metrics[metric]
            return {}

        imported = _first("importEnergy")      # prelievo dalla rete
        exported = _first("exportEnergy")      # immessa in rete
        consumed = _first("consumptionEnergy")

        self_consumed = {}
        for stamp, value in prod.items():
            if stamp in exported:
                self_consumed[stamp] = max(0.0, value - exported[stamp])

        def _series(values: Dict[str, float]) -> List[Dict[str, Any]]:
            return [{"date": s, "value": v} for s, v in sorted(values.items())]

        return {"energyDetails": {"unit": "Wh", "timeUnit": "QUARTER_OF_AN_HOUR", "meters": [
            {"type": "Production", "values": _series(prod)},
            {"type": "FeedIn", "values": _series(exported)},
            {"type": "Purchased", "values": _series(imported)},
            {"type": "SelfConsumption", "values": _series(self_consumed)},
            {"type": "Consumption", "values": _series(consumed)},
        ]}}

    # --------------------------------------------------------------- cadenza
    def previous_day_due(self, now: Optional[datetime] = None) -> bool:
        """Il giorno prima si rilegge una volta, a giorno inoltrato.

        L'ultimo quarto d'ora di una giornata viene letto dalla chiamata delle
        23:45-23:59, quando il fornitore non l'ha ancora chiuso: il valore
        scritto resta una frazione dello slot e la giornata non si rilegge mai
        piu'. Una chiamata al giorno dopo le 06:00 lo porta a quello definitivo.
        """
        now = (now or datetime.now(ROME)).astimezone(ROME)
        state = _read_json(STATE_FILE, {}) or {}
        if not state.get("meters_at") or now.hour < SETTLE_HOUR:
            return False
        return state.get("prev_day_done") != now.date().isoformat()

    def mark_previous_done(self, now: Optional[datetime] = None) -> None:
        now = (now or datetime.now(ROME)).astimezone(ROME)
        state = _read_json(STATE_FILE, {}) or {}
        state["prev_day_done"] = now.date().isoformat()
        _write_json(STATE_FILE, state)

    def meters_due(self, now: Optional[datetime] = None) -> bool:
        """I contatori si leggono una volta all'ora (il loop gira a 15 minuti).

        Una chiamata restituisce la giornata intera a 15 minuti, quindi la
        cadenza cambia solo la freschezza della curva di oggi, mai il dettaglio.
        """
        now = (now or datetime.now(ROME)).astimezone(ROME)
        state = _read_json(STATE_FILE, {}) or {}
        last = state.get("meters_at")
        if not last:
            return True
        try:
            last_dt = ROME.localize(datetime.strptime(last, "%Y-%m-%d %H:%M:%S"))
        except Exception:
            return True
        return (now - last_dt) >= timedelta(minutes=METERS_GATE_MIN)

    def mark_meters_done(self, now: Optional[datetime] = None) -> None:
        now = (now or datetime.now(ROME)).astimezone(ROME)
        state = _read_json(STATE_FILE, {}) or {}
        state["meters_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
        _write_json(STATE_FILE, state)

    def energy_due(self, now: Optional[datetime] = None) -> Tuple[bool, str]:
        """La produzione si legge a ore, solo con il sole, piu' una chiusura."""
        now = (now or datetime.now(ROME)).astimezone(ROME)
        state = _read_json(STATE_FILE, {}) or {}
        today = now.date().isoformat()
        if state.get("day") != today:
            state = {"day": today, "last_hour": None, "closed": False}
        if state.get("closed"):
            return False, "giornata gia' chiusa"

        meta = _read_json(META_FILE, {}) or {}
        location = meta.get("location") or {}
        lat = location.get("latitude")
        lon = location.get("longitude")
        if lat is None or lon is None:
            rise, sunset = (now.replace(hour=5, minute=0), now.replace(hour=20, minute=0))
        else:
            rise, sunset = sun_times(float(lat), float(lon), now.date())

        if now < rise:
            return False, "prima dell'alba (%s)" % rise.strftime("%H:%M")
        if now > sunset + timedelta(minutes=CLOSE_AFTER_SUNSET_MIN):
            return True, "chiusura dopo il tramonto (%s)" % sunset.strftime("%H:%M")
        hour_key = now.strftime("%Y-%m-%d %H")
        if state.get("last_hour") == hour_key:
            return False, "ora gia' letta (%s)" % now.strftime("%H")
        return True, "ora %s" % now.strftime("%H")

    def mark_energy_done(self, now: Optional[datetime] = None) -> None:
        now = (now or datetime.now(ROME)).astimezone(ROME)
        state = _read_json(STATE_FILE, {}) or {}
        today = now.date().isoformat()
        if state.get("day") != today:
            state = {"day": today, "last_hour": None, "closed": False}
        state["last_hour"] = now.strftime("%Y-%m-%d %H")
        meta = _read_json(META_FILE, {}) or {}
        location = meta.get("location") or {}
        if location.get("latitude") is not None:
            _, sunset = sun_times(float(location["latitude"]), float(location["longitude"]), now.date())
            if now > sunset + timedelta(minutes=CLOSE_AFTER_SUNSET_MIN):
                state["closed"] = True
        _write_json(STATE_FILE, state)
