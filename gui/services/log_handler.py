#!/usr/bin/env python3
"""
GUI Log Handler - Gestione cattura log per GUI
Responsabilità: Cattura log da logger globali e routing a StateManager
"""

import logging
import re
from datetime import datetime


class GUILogHandler(logging.Handler):
    """Handler per catturare log e inviarli alla GUI con identificazione flow"""

    def __init__(self, state_manager):
        """Initialize GUI log handler.

        Args:
            state_manager: StateManager instance per storage log
        """
        super().__init__()
        self.state_manager = state_manager
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        self.flow_stack = []  # Stack per tracking flow annidati

    def emit(self, record: logging.LogRecord):
        """Processa log record e invia a StateManager.

        Args:
            record: Log record da processare
        """
        try:
            message = self.ansi_escape.sub('', record.getMessage())

            # Filtra messaggi di orchestrazione [GUI] - non mostrarli nella GUI
            if message.startswith('[GUI]'):
                return

            # Parse SYSTEM markers [SYSTEM]
            if '[SYSTEM]' in message:
                # Remove [SYSTEM] prefix and route to sistema tab
                clean_message = message.replace('[SYSTEM]', '').strip()
                self.state_manager.add_log_entry(
                    level=record.levelname,
                    message=clean_message,
                    flow_type='sistema',
                    timestamp=datetime.now()
                )
                return

            # Parse flow markers [FLOW:TYPE:ACTION]
            if '[FLOW:' in message:
                parts = message.split('[FLOW:')[1].split(']')[0].split(':')
                flow_type = parts[0].lower()
                action = parts[1]

                if action == 'START':
                    self.flow_stack.append(flow_type)
                    return  # Non mostrare START
                elif action == 'STOP' and self.flow_stack:
                    self.flow_stack.pop()
                    return  # Non mostrare STOP
                elif action == 'COMPLETION':
                    # Messaggi di completamento: rimuovi marker e mostra nel flow corretto
                    clean_message = message.split(']', 1)[1] if ']' in message else message
                    self.state_manager.add_log_entry(
                        level=record.levelname,
                        message=clean_message,
                        flow_type=flow_type,
                        timestamp=datetime.now()
                    )
                    return

            # Determina flow corrente dallo stack
            current_flow = self.flow_stack[-1] if self.flow_stack else 'general'

            self.state_manager.add_log_entry(
                level=record.levelname,
                message=message,
                flow_type=current_flow,
                timestamp=datetime.now()
            )
        except Exception as e:
            # Evita loop infiniti - non loggare errori del log handler
            pass


__all__ = ['GUILogHandler']
