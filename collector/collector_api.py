#!/usr/bin/env python3
"""Collector API — SolarEdge Monitoring API v2 (Site Access / OAuth 2.0).

Qui non c'è niente da comporre: né URL né api key. Il client vive in
`collector/solaredge_v2.py` e risponde con `energyDetails.meters[].values`, la
forma che il parser e Influx si aspettano.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from scheduler.scheduler_loop import SchedulerLoop
from config.config_manager import get_config_manager
from collector.solaredge_v2 import SolarEdgeV2, ROME

logger = logging.getLogger(__name__)

# Gli unici endpoint del sito, tutti e due serviti dalla V2
V2_ENDPOINTS = ('site_details', 'site_energy_details')


def _merge_series(old: List[Dict[str, Any]], new: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Fonde due serie per data; sulla stessa data vince la nuova.

    I file delle versioni vecchie hanno slot con la sola `date` (il quarto d'ora
    ancora aperto): non portano un valore, e non devono ne' rompere la fusione ne'
    sovrascrivere uno slot buono.
    """
    merged = {it["date"]: it["value"] for it in old if it.get("value") is not None}
    merged.update({it["date"]: it["value"] for it in new if it.get("value") is not None})
    return [{"date": d, "value": v} for d, v in sorted(merged.items())]


class CollectorAPI:
    """Legge gli endpoint abilitati nel YAML e li serve dalla V2."""

    def __init__(self, config_path: str = "config/main.yaml", cache=None,
                 scheduler: Optional[SchedulerLoop] = None):
        self.cache = cache
        self.scheduler = scheduler
        self._config_manager = get_config_manager(config_path)
        api_config = self._config_manager.get_solaredge_api_config()
        self.site_id = api_config.site_id or self._config_manager.get_global_config().site_id
        self.config = self._config_manager.get_raw_config()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def _get_enabled_endpoints(self) -> Dict[str, Any]:
        """Ottieni endpoint abilitati dal YAML"""
        api_config = self.config.get('sources', {}).get('api_ufficiali', {})
        return {
            name: cfg for name, cfg in api_config.get('endpoints', {}).items()
            if cfg.get('enabled', False)
        }

    def collect(self) -> Dict[str, Any]:
        """Raccolta dati da endpoint abilitati"""
        results = {}

        for endpoint_name, endpoint_config in self._get_enabled_endpoints().items():
            try:
                if endpoint_name in V2_ENDPOINTS:
                    payload = self._v2_payload(endpoint_name)
                else:
                    payload = self._v2_generic(endpoint_name, endpoint_config)
                if payload:              # saltato dal gate: nessun avviso
                    results[endpoint_name] = payload
                    self.archive_payload(endpoint_name, payload)
            except Exception as e:
                logger.error(f"Errore raccolta {endpoint_name}: {e}")

        return results

    def archive_payload(self, endpoint_name: str, payload: Dict[str, Any]) -> None:
        """Archivia nella cache: un file per giorno,
        stesso wrapper `{data, source, endpoint, date, data_hash}`.

        Nessuno la legge piu' (la coda di un giorno letto dal vivo non e' quella
        definitiva), ma resta una sola cache: `--history` scrive con lo stesso
        formato delle call live, e i giorni passati si sigillano da soli.
        """
        if not self.cache or not payload:
            return
        meters = (payload.get("energyDetails") or {}).get("meters")
        if not meters:
            self.cache.save_to_cache("api_ufficiali", endpoint_name,
                                     datetime.now(ROME).date().isoformat(), payload,
                                     is_metadata=True)
            return

        per_day: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        for meter in meters:
            for value in meter.get("values") or []:
                per_day.setdefault(value["date"][:10], {}).setdefault(meter["type"], []).append(value)

        for day, by_type in per_day.items():
            # si fonde con cio' che e' gia' archiviato: di notte la produzione non
            # si legge, e un giro senza produzione non deve cancellare quella di
            # una giornata gia' archiviata
            old = self.cache.peek_cached_data("api_ufficiali", endpoint_name, day) or {}
            for meter in ((old.get("energyDetails") or {}).get("meters") or []):
                values = meter.get("values") or []
                if not values:
                    continue
                if meter.get("type") in by_type:
                    by_type[meter["type"]] = _merge_series(values, by_type[meter["type"]])
                else:
                    # canale assente in questo giro: si riporta quello vecchio,
                    # ripulito dagli slot senza valore delle versioni vecchie
                    by_type[meter["type"]] = _merge_series([], values)
            self.cache.save_to_cache("api_ufficiali", endpoint_name, day, {"energyDetails": {
                "unit": payload["energyDetails"].get("unit", "Wh"),
                "timeUnit": payload["energyDetails"].get("timeUnit"),
                "meters": [{"type": t, "values": v} for t, v in by_type.items()],
            }})

    def _v2_generic(self, endpoint_name: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Endpoint dichiarato nel catalogo: GET sul percorso V2, risposta com'e'.

        Basta aggiungere `path` e `params` nel YAML per raccogliere un endpoint
        nuovo: il payload arriva al parser come JSON grezzo, senza codice nuovo.
        """
        path = cfg.get('path')
        if not path:
            logger.warning(f"{endpoint_name}: nessun percorso V2 nel catalogo, ignorato")
            return {}
        if '{serialNumber}' in path:
            logger.warning(f"{endpoint_name}: serve un seriale, non gestito in automatico")
            return {}
        if getattr(self, '_v2', None) is None:
            self._v2 = SolarEdgeV2(self.site_id)
        return self._v2.get(path.format(siteId=self.site_id), cfg.get('params') or {})

    def _v2_payload(self, endpoint_name: str, force: bool = False) -> Dict[str, Any]:
        """Endpoint serviti dalla V2: anagrafica dal cache, energia a ore, contatori ogni giro."""
        if getattr(self, '_v2', None) is None:
            self._v2 = SolarEdgeV2(self.site_id)
        if endpoint_name == 'site_details':
            return self._v2.site_details_payload()
        if not force and not self._v2.meters_due():
            return {}          # contatori gia' letti entro l'ora
        with_prod, why = (True, 'forzato') if force else self._v2.energy_due()
        if not with_prod:
            logger.debug(f"produzione non letta: {why}")
        # finestra di 7 giorni, sempre la stessa: una giornata o un'ora persa
        # mentre le chiamate erano giu' torna da sola al giro dopo, e il giorno
        # prima e' dentro la finestra senza una rilettura dedicata
        payload = self._v2.recent_payload(with_production=with_prod)
        if with_prod:
            self._v2.mark_energy_done()
        self._v2.mark_meters_done()
        return payload
