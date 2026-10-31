#!/usr/bin/env python3
"""
State Manager - Gestione stato applicazione
Single Responsibility: tracking stato loop, log, statistiche
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from collections import deque
from app_logging.universal_logger import get_logger


class StateManager:
    """Gestisce stato applicazione e buffer log"""

    def __init__(self, max_log_buffer: int = 1000):
        self.logger = get_logger("StateManager")

        # Loop state
        self.loop_mode = False
        self.loop_running = False
        self.stop_requested = False

        # Log tracking: il buffer ha una cap manuale, cosi' un errore non viene
        # mai espulso dall'auto-eviction; errori e avvisi hanno un archivio
        # persistente che nessuna pulizia tocca.
        self.max_log_buffer = max_log_buffer
        self.log_buffer = deque()
        self.error_max = 2000
        self._error_path = Path('cache/error_log.json')
        self.error_archive: List[dict] = self._load_error_archive()
        # Un solo log: gli errori e gli avvisi gia' archiviati rientrano nel buffer
        # all'avvio, cosi' la pagina Logs li mostra anche dopo un riavvio.
        for entry in self.error_archive:
            seeded = dict(entry)
            seeded['timestamp_obj'] = None
            self.log_buffer.append(seeded)

        # Retention: giorni di vita del log, non delle singole run. Errori e
        # avvisi non scadono mai.
        days = int(os.getenv('LOG_RETENTION_DAYS', '7') or 7)
        self.retention_config = {
            'days': days,
            'sistema_reset': False
        }

        # Update tracking
        self.updates_available = False
        self.last_update_check = None
        self.restart_required = False

        # Statistiche loop
        self.loop_stats = {
            'api_stats': {'executed': 0, 'success': 0, 'failed': 0},
            'web_stats': {'executed': 0, 'success': 0, 'failed': 0},
            'realtime_stats': {'executed': 0, 'success': 0, 'failed': 0},
            'gme_stats': {'executed': 0, 'success': 0, 'failed': 0},
            'bolletta_stats': {'executed': 0, 'success': 0, 'failed': 0},
            'start_time': None,
            'last_update': None,
            'last_api_web_run': None,
            'next_api_web_run': None,
            'last_gme_run': None,
            'next_gme_run': None,
            'last_bolletta_run': None,
            'next_bolletta_run': None,
            'status': 'stopped'
        }

    def start_loop(self):
        """Avvia loop mode"""
        self.loop_running = True
        self.loop_mode = True
        self.stop_requested = False
        self.loop_stats['status'] = 'running'
        self.loop_stats['start_time'] = datetime.now()
        self.logger.info("Loop mode avviato")

    def stop_loop(self):
        """Ferma loop mode"""
        self.loop_running = False
        self.loop_mode = False
        self.stop_requested = True
        self.loop_stats['status'] = 'stopped'
        self.logger.info("Loop mode fermato")

    def add_log_entry(self, level: str, message: str, flow_type: str = 'general', timestamp: Optional[datetime] = None):
        """
        Aggiunge entry al buffer log con retention policy (24h)
        
        Args:
            level: Livello log (info, error, warning, success)
            message: Messaggio log
            flow_type: Tipo flow (api, web, realtime, general)
            timestamp: Timestamp (default: now)
        """
        if timestamp is None:
            timestamp = datetime.now()

        log_entry = {
            "timestamp": timestamp.strftime('%H:%M:%S'),
            "timestamp_obj": timestamp,  # Per check retention
            "level": level,
            "message": message,
            "flow_type": flow_type
        }

        self.log_buffer.append(log_entry)

        if self._is_important(log_entry):
            # timestamp_obj e' un datetime: nell'archivio va solo la stringa
            archived = {k: v for k, v in log_entry.items() if k != 'timestamp_obj'}
            archived['at'] = log_entry['timestamp_obj'].isoformat(timespec='seconds')
            self.error_archive.append(archived)
            del self.error_archive[:-self.error_max]
            self._save_error_archive()

        # Retention: scade solo cio' che non e' un errore o un avviso.
        retention_seconds = self.retention_config['days'] * 86400
        cutoff = datetime.fromtimestamp(timestamp.timestamp() - retention_seconds)
        while True:
            idx = next((i for i, e in enumerate(self.log_buffer)
                        if not self._is_important(e)
                        and e.get('timestamp_obj') and e['timestamp_obj'] < cutoff), None)
            if idx is None:
                break
            del self.log_buffer[idx]

        # Cap del buffer: espelle il piu' vecchio non importante, mai un errore.
        while len(self.log_buffer) > self.max_log_buffer:
            idx = next((i for i, e in enumerate(self.log_buffer)
                        if not self._is_important(e)), None)
            if idx is None:
                break
            del self.log_buffer[idx]

        # Aggiorna timestamp ultimo update
        self.loop_stats['last_update'] = timestamp

    @staticmethod
    def _is_important(entry: dict) -> bool:
        """Errore o avviso: non scade, non si cancella, non si espelle."""
        level = str(entry.get('level', '')).lower()
        msg = str(entry.get('message', ''))
        return level in ('error', 'warning', 'critical') or '❌' in msg or '⚠' in msg

    def _load_error_archive(self) -> List[dict]:
        try:
            if self._error_path.exists():
                data = json.loads(self._error_path.read_text(encoding='utf-8'))
                return data if isinstance(data, list) else []
        except Exception as e:
            self.logger.warning(f"Archivio errori non leggibile: {e}")
        return []

    def _save_error_archive(self) -> None:
        try:
            self._error_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._error_path.with_suffix('.tmp')
            tmp.write_text(json.dumps(self.error_archive[-self.error_max:], ensure_ascii=False),
                           encoding='utf-8')
            os.replace(tmp, self._error_path)
        except Exception as e:
            self.logger.warning(f"Archivio errori non scrivibile: {e}")

    def get_errors(self, limit: Optional[int] = None) -> List[dict]:
        """Errori e avvisi accumulati, dal piu' vecchio al piu' recente."""
        rows = self.error_archive[-limit:] if limit else list(self.error_archive)
        return [{k: v for k, v in e.items() if k != 'timestamp_obj'} for e in rows]

    def get_logs(self, limit: int = 5000) -> List[dict]:
        """Ultime `limit` righe del buffer, dalla piu' vecchia alla piu' recente."""
        result = []
        for log in list(self.log_buffer)[-limit:]:
            log_copy = log.copy()
            log_copy.pop('timestamp_obj', None)
            result.append(log_copy)
        return result

    def set_retention_days(self, days: int) -> None:
        self.retention_config['days'] = days
        cutoff = datetime.now().timestamp() - days * 86400
        self.log_buffer = deque(
            e for e in self.log_buffer
            if self._is_important(e)
            or not e.get('timestamp_obj')
            or e['timestamp_obj'].timestamp() >= cutoff
        )

    def clear_logs(self) -> Dict[str, int]:
        """Pulisce i log informativi; errori e avvisi restano."""
        kept = [e for e in self.log_buffer if self._is_important(e)]
        removed = len(self.log_buffer) - len(kept)
        self.log_buffer.clear()
        self.log_buffer.extend(kept)
        self.logger.info(f"Log puliti ({removed} righe); errori e avvisi conservati")
        return {'removed': removed, 'kept': len(self.error_archive)}

    def update_stats(self, flow_type: str, success: bool):
        """
        Aggiorna statistiche flow

        Args:
            flow_type: Tipo flow ('api', 'web', 'realtime')
            success: True se successo, False se fallito
        """
        stats_key = f'{flow_type}_stats'
        if stats_key not in self.loop_stats:
            return

        self.loop_stats[stats_key]['executed'] += 1
        if success:
            self.loop_stats[stats_key]['success'] += 1
        else:
            self.loop_stats[stats_key]['failed'] += 1

        # Aggiorna timestamp ultimo update
        self.loop_stats['last_update'] = datetime.now()

    def get_loop_status(self) -> dict:
        """
        Restituisce stato loop con statistiche serializzabili

        Returns:
            Dizionario con stato e statistiche
        """
        stats = self.loop_stats.copy()

        # Converti datetime in stringhe per JSON serialization
        if stats.get('start_time'):
            stats['uptime_seconds'] = (datetime.now() - stats['start_time']).total_seconds()
            stats['uptime_formatted'] = str(datetime.now() - stats['start_time']).split('.')[0]
            del stats['start_time']

        if stats.get('last_update') and hasattr(stats['last_update'], 'strftime'):
            stats['last_update_formatted'] = stats['last_update'].strftime('%H:%M:%S')
            del stats['last_update']

        for flow in ('api', 'web'):
            last_key, next_key = f'last_{flow}_run', f'next_{flow}_run'
            if stats.get(last_key) and hasattr(stats[last_key], 'strftime'):
                stats[f'{flow}_last_run'] = stats[last_key].strftime('%H:%M:%S')
                stats[f'{flow}_last_at'] = stats[last_key].isoformat()
                del stats[last_key]
            if stats.get(next_key) and hasattr(stats[next_key], 'strftime'):
                stats[f'{flow}_next_run'] = stats[next_key].strftime('%H:%M:%S')
                stats[f'{flow}_next_at'] = stats[next_key].isoformat()
                del stats[next_key]

        if stats.get('last_gme_run') and hasattr(stats['last_gme_run'], 'strftime'):
            stats['gme_last_run'] = stats['last_gme_run'].strftime('%H:%M:%S')
            stats['gme_last_at'] = stats['last_gme_run'].isoformat()
            del stats['last_gme_run']

        if stats.get('next_gme_run') and hasattr(stats['next_gme_run'], 'strftime'):
            stats['gme_next_run'] = stats['next_gme_run'].strftime('%H:%M:%S')
            stats['gme_next_at'] = stats['next_gme_run'].isoformat()
            del stats['next_gme_run']

        if stats.get('last_bolletta_run') and hasattr(stats['last_bolletta_run'], 'strftime'):
            stats['bolletta_last_run'] = stats['last_bolletta_run'].strftime('%H:%M:%S')
            stats['bolletta_last_at'] = stats['last_bolletta_run'].isoformat()
            del stats['last_bolletta_run']

        if stats.get('next_bolletta_run') and hasattr(stats['next_bolletta_run'], 'strftime'):
            stats['bolletta_next_run'] = stats['next_bolletta_run'].strftime('%H:%M:%S')
            stats['bolletta_next_at'] = stats['next_bolletta_run'].isoformat()
            del stats['next_bolletta_run']

        # Rimuovi oggetti datetime/timedelta rimanenti
        for key in list(stats.keys()):
            if hasattr(stats[key], 'strftime') or hasattr(stats[key], 'total_seconds'):
                del stats[key]

        return {
            'loop_mode': self.loop_running,
            'stats': stats
        }
