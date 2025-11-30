#!/usr/bin/env python3
"""
State Manager - Gestione stato applicazione
Single Responsibility: tracking stato loop, log, statistiche
"""

from datetime import datetime
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

        # Log tracking con deque per auto-eviction
        self.log_buffer = deque(maxlen=max_log_buffer)

        # Flow runs tracking - logs raggruppati per flow type
        # Ogni flow ha una deque di liste (runs), max 3 run
        self.flow_runs: Dict[str, deque] = {
            'api': deque(maxlen=3),
            'web': deque(maxlen=3),
            'realtime': deque(maxlen=3),
            'gme': deque(maxlen=3),
            'sistema': deque(maxlen=1)  # Sistema ha solo una "run" continua
        }
        
        # Inizializza la prima run per ogni flow
        for flow in self.flow_runs:
            self.flow_runs[flow].append([])

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
            'start_time': None,
            'last_update': None,
            'last_api_web_run': None,
            'next_api_web_run': None,
            'last_gme_run': None,
            'next_gme_run': None,
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

    def start_new_run(self, flow_type: str):
        """
        Inizia una nuova run per un flow specifico (ruota i log)
        
        Args:
            flow_type: Tipo flow ('api', 'web', 'realtime', 'gme')
        """
        if flow_type in self.flow_runs and flow_type != 'sistema':
            # Aggiunge nuova lista vuota, la deque gestisce automaticamente l'eviction della più vecchia
            self.flow_runs[flow_type].append([])

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
        
        # Retention policy 12h per log_buffer (pulizia lazy)
        # Controlla solo il primo elemento (il più vecchio)
        if self.log_buffer:
            oldest = self.log_buffer[0]
            if oldest.get('timestamp_obj'):
                age = (timestamp - oldest['timestamp_obj']).total_seconds()
                if age > 43200:  # 12 ore
                    self.log_buffer.popleft()

        self._add_log_to_flow_runs(log_entry)

        # Aggiorna timestamp ultimo update
        self.loop_stats['last_update'] = timestamp

    def _add_log_to_flow_runs(self, log_entry: dict):
        """Aggiunge log alla run corrente del flow"""
        flow_type = log_entry.get('flow_type', 'general')

        # Solo i flow specifici vengono tracciati
        if flow_type in self.flow_runs:
            # Aggiunge alla run corrente (l'ultima della deque)
            self.flow_runs[flow_type][-1].append(log_entry)

    def get_filtered_logs(self, flow_filter: str = 'all', limit: int = 2000) -> List[dict]:
        """
        Ottiene log filtrati per flow type
        
        Args:
            flow_filter: Filtro flow ('all', 'api', 'web', 'realtime', 'gme', 'sistema')
            limit: Numero massimo log da restituire (usato solo per 'all')
            
        Returns:
            Lista di log entries
        """
        if flow_filter == 'all':
            # Tab "Tutti": mostra tutto il log buffer (ultimi N)
            # Rimuovi timestamp_obj prima di inviare al frontend
            result = []
            for log in list(self.log_buffer)[-limit:]:
                log_copy = log.copy()
                if 'timestamp_obj' in log_copy:
                    del log_copy['timestamp_obj']
                result.append(log_copy)
            return result
            
        elif flow_filter == 'general':
            # Backward compatibility: redirect to sistema
            flow_filter = 'sistema'

        # Tab specifici: appiattisci le run correnti
        if flow_filter in self.flow_runs:
            result = []
            # Itera su tutte le run salvate (max 3)
            for run in self.flow_runs[flow_filter]:
                for log in run:
                    log_copy = log.copy()
                    if 'timestamp_obj' in log_copy:
                        del log_copy['timestamp_obj']
                    result.append(log_copy)
            return result
            
        return []

    def clear_logs(self):
        """Pulisce tutti i log e le run"""
        self.log_buffer.clear()
        for flow_type in self.flow_runs:
            self.flow_runs[flow_type].clear()
            self.flow_runs[flow_type].append([])  # Ripristina run corrente vuota
        self.logger.info("Log puliti")

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

        if stats.get('last_api_web_run') and hasattr(stats['last_api_web_run'], 'strftime'):
            stats['api_last_run'] = stats['last_api_web_run'].strftime('%H:%M:%S')
            stats['web_last_run'] = stats['last_api_web_run'].strftime('%H:%M:%S')
            del stats['last_api_web_run']

        if stats.get('next_api_web_run') and hasattr(stats['next_api_web_run'], 'strftime'):
            stats['api_next_run'] = stats['next_api_web_run'].strftime('%H:%M:%S')
            stats['web_next_run'] = stats['next_api_web_run'].strftime('%H:%M:%S')
            del stats['next_api_web_run']

        if stats.get('last_gme_run') and hasattr(stats['last_gme_run'], 'strftime'):
            stats['gme_last_run'] = stats['last_gme_run'].strftime('%H:%M:%S')
            del stats['last_gme_run']

        if stats.get('next_gme_run') and hasattr(stats['next_gme_run'], 'strftime'):
            stats['gme_next_run'] = stats['next_gme_run'].strftime('%H:%M:%S')
            del stats['next_gme_run']

        # Rimuovi oggetti datetime/timedelta rimanenti
        for key in list(stats.keys()):
            if hasattr(stats[key], 'strftime') or hasattr(stats[key], 'total_seconds'):
                del stats[key]

        return {
            'loop_mode': self.loop_running,
            'stats': stats
        }
