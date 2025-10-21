"""web_tree_scanner.py
Scanner dedicato (Fase 3B):
 - Usa CollectorWeb per autenticarsi e ottenere il JSON 'tree'.
 - Salva snapshot raw versionato in cache/snapshots/web_tree/.
 - NON modifica config/main.yaml - lascia che sia il YawlManager a farlo.

Limiti attuali:
 - Crea solo il file snapshot per il YawlManager
 - Non estrae metriche o modifica configurazioni
 - Funzionalità minima e focalizzata
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict
import requests

from app_logging import get_logger
from collector.collector_web import CollectorWeb

LOG = get_logger("scanner.web_tree")

SNAP_DIR = Path("cache/snapshots/web_tree")


class WebTreeScanner:
    def __init__(self) -> None:
        # Lazy init: crea CollectorWeb solo quando serve _fetch_tree
        self.collector: CollectorWeb | None = None

    # ---------------- Public API -----------------
    def scan(self, from_snapshot: bool = False, snapshot_path: str | None = None) -> Dict[str, Any]:
        """Esegue la scansione e salva snapshot.

        - from_snapshot=True: usa uno snapshot locale (snapshot_path o latest.json)
        - altrimenti: effettua la richiesta di rete via CollectorWeb
        """
        if from_snapshot:
            tree = self._load_snapshot(snapshot_path)
        else:
            tree = self._fetch_tree()
        snapshot_path = self._write_snapshot(tree)
        LOG.info("Snapshot salvato: %s", snapshot_path)
        return tree

    # ---------------- Internal -------------------
    def _fetch_tree(self) -> Dict[str, Any]:
        """Tenta una lista di endpoint candidati per ottenere il JSON tree."""
        if self.collector is None:
            self.collector = CollectorWeb()
        self.collector.ensure_session()
        site_id = getattr(self.collector, "_site_id", None)
        if not site_id:
            raise RuntimeError("site_id non disponibile nel collector")

        # Normalizza numerico se possibile
        try:
            site_id_norm = str(int(str(site_id).strip()))
        except Exception:
            site_id_norm = str(site_id).strip()

        base = getattr(self.collector, "_base_url", "https://monitoring.solaredge.com").rstrip('/')
        cookie = getattr(self.collector, "_cookie", None)
        csrf = getattr(self.collector, "_csrf_token", None)

        candidates = [
            f"/services/charts/site/{site_id_norm}/tree",
        ]

        headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (compatible; se-scanner/0.1)",
            "Referer": f"{base}/solaredge-web/p/site/{site_id_norm}/",
            "Origin": base,
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
        }
        if cookie:
            headers["Cookie"] = cookie
        if csrf:
            headers["X-CSRF-TOKEN"] = csrf

        session = requests.Session()
        for rel in candidates:
            url = base + rel
            try:
                LOG.info("Provo endpoint tree: %s", rel)
                resp = session.get(url, headers=headers, timeout=40, allow_redirects=True)
            except requests.RequestException as e:
                LOG.error("Errore richiesta %s: %s", rel, e)
                continue

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception as je:
                    LOG.error("Errore parsing JSON da %s: %s", rel, je)
                    continue

                if isinstance(data, dict) and data:
                    LOG.info("Tree ottenuto da endpoint: %s (chiavi=%d)", rel, len(data))
                    return data
                else:
                    LOG.warning("Risposta vuota o non dict da %s", rel)
                    continue
            else:
                LOG.warning("Status %d da %s", resp.status_code, rel)
                continue

        # Nessun successo
        raise RuntimeError("Impossibile ottenere tree da SolarEdge")

    def _write_snapshot(self, tree: Dict[str, Any]) -> Path:
        """Salva snapshot in formato JSON."""
        SNAP_DIR.mkdir(parents=True, exist_ok=True)
        # Mantieni UNA sola snapshot: latest.json
        latest = SNAP_DIR / "latest.json"
        with latest.open("w", encoding="utf-8") as f:
            json.dump(tree, f, ensure_ascii=False, indent=2)
        return latest

    def _load_snapshot(self, snapshot_path: str | None) -> Dict[str, Any]:
        """Carica uno snapshot locale."""
        if snapshot_path:
            p = Path(snapshot_path)
        else:
            p = SNAP_DIR / "latest.json"
        if not p.exists():
            raise FileNotFoundError(f"Snapshot non trovato: {p}")
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            raise RuntimeError(f"Snapshot non leggibile {p}: {e}")


__all__ = ["WebTreeScanner"]
