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
    
    def __init__(self, max_log_buffer: int = 1000, max_runs_per_flow: int = 3):
        self.logger = get_logger("StateManager")
        
        # Loop state
        self.loop_mode = False
        self.loop_running = False
        self.stop_requested = False
        
        # Log tracking con deque per auto-eviction
        self.log_buffer = deque(maxlen=max_log_buffer)
        self.max_runs_per_flow = max_runs_per_flow
        
        # Flow runs tracking (ultime N run per tipo)
        self.flow_runs: Dict[str, deque] = {
            'api': deque(maxlen=max_runs_per_flow),
            'web': deque(maxlen=max_runs_per_flow),
            'realtime': deque(maxlen=max_runs_per_flow),
            'gme': deque(maxlen=max_runs_per_flow),
            'general': deque(maxlen=max_runs_per_flow)
        }
        
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
    
    def add_log_entry(self, level: str, message: str, flow_type: str = 'general', timestamp: Optional[datetime] = None):
        """
        Aggiunge entry al buffer log
        
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
            "level": level,
            "message": message,
            "flow_type": flow_type
        }
        
        self.log_buffer.append(log_entry)
        self._add_log_to_flow_runs(log_entry)
        
        # Aggiorna timestamp ultimo update
        self.loop_stats['last_update'] = timestamp
    
    def _is_run_start_marker(self, message: str) -> bool:
        """Verifica se il messaggio è un marker di inizio run"""
        message_lower = message.lower()
        return any(marker in message_lower for marker in [
            '🚀 avvio flusso api',
            '🚀 avvio flusso web',
            '🚀 avvio flusso realtime',
            '🚀 avvio flusso gme'
        ])
    
    def _add_log_to_flow_runs(self, log_entry: dict):
        """Aggiunge log alla struttura delle run per flow type"""
        flow_type = log_entry.get('flow_type', 'general')
        
        if flow_type not in self.flow_runs:
            flow_type = 'general'
        
        # Se è un marker di inizio run, crea una nuova run
        if self._is_run_start_marker(log_entry['message']):
            self.flow_runs[flow_type].append([log_entry])
        else:
            # Aggiungi alla run corrente (se esiste)
            if self.flow_runs[flow_type]:
                self.flow_runs[flow_type][-1].append(log_entry)
            else:
                # Se non c'è una run corrente, creane una nuova
                self.flow_runs[flow_type].append([log_entry])
    
    def get_filtered_logs(self, flow_filter: str = 'all', limit: int = 500) -> List[dict]:
        """
        Ottiene log filtrati per flow type dalle ultime N run
        
        Args:
            flow_filter: Filtro flow ('all', 'api', 'web', 'realtime', 'general')
            limit: Numero massimo log da restituire
            
        Returns:
            Lista di log entries
        """
        filtered_logs = []
        
        if flow_filter == 'all':
            # Combina le ultime N run di tutti i flow types
            for flow_type in ['api', 'web', 'realtime', 'gme', 'general']:
                for run in self.flow_runs[flow_type]:
                    filtered_logs.extend(run)
            
            # Ordina per timestamp
            def timestamp_to_seconds(ts_str):
                try:
                    h, m, s = map(int, ts_str.split(':'))
                    return h * 3600 + m * 60 + s
                except:
                    return 0
            
            filtered_logs.sort(key=lambda log: timestamp_to_seconds(log.get('timestamp', '00:00:00')))
        else:
            # Solo le ultime N run del flow type specifico
            if flow_filter in self.flow_runs:
                for run in self.flow_runs[flow_filter]:
                    filtered_logs.extend(run)
        
        # Applica limit (prendi gli ultimi N log)
        return filtered_logs[-limit:] if len(filtered_logs) > limit else filtered_logs
    
    def clear_logs(self):
        """Pulisce tutti i log e le run"""
        self.log_buffer.clear()
        for flow_type in self.flow_runs:
            self.flow_runs[flow_type].clear()
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
    
    def get_run_counts(self) -> Dict[str, int]:
        """Restituisce conteggio run per flow type"""
        return {
            flow_type: len(runs)
            for flow_type, runs in self.flow_runs.items()
        }
