#!/usr/bin/env python3
"""
Update Service - Gestione aggiornamenti sistema
Responsabilità: Esecuzione update.sh in background (Windows/Linux)
"""

import os
import platform
import subprocess
from pathlib import Path
from typing import Tuple

from app_logging.universal_logger import get_logger

# Costanti
UPDATE_TIMEOUT_SECONDS = 5
UPDATE_LOG_FILE = 'logs/update_gui.log'


class UpdateService:
    """Servizio per gestione aggiornamenti sistema"""

    def __init__(self):
        self.logger = get_logger("UpdateService")

    async def run_update(self) -> Tuple[bool, str]:
        """Esegue l'aggiornamento in un processo separato che sopravvive alla chiusura della GUI.

        Returns:
            Tuple (success: bool, message: str)
        """
        update_script = Path('update.sh')
        if not update_script.exists():
            return False, 'Script update.sh non trovato'

        self.logger.info("[UpdateService] 🚀 Avvio aggiornamento in processo separato...")

        try:
            log_file = os.path.join(os.getcwd(), UPDATE_LOG_FILE)

            if platform.system() == 'Windows':
                success, message = await self._run_update_windows(log_file)
            else:
                success, message = await self._run_update_linux(log_file)

            if success:
                self.logger.info(f"[UpdateService] ✅ Update avviato - Log: {log_file}")
            else:
                self.logger.error(f"[UpdateService] ❌ Errore: {message}")

            return success, message

        except Exception as e:
            error_msg = f'Errore durante l\'avvio dell\'aggiornamento: {str(e)}'
            self.logger.error(f"[UpdateService] ❌ {error_msg}", exc_info=True)
            return False, error_msg

    async def _run_update_windows(self, log_file: str) -> Tuple[bool, str]:
        """Esegue update su Windows usando Task Scheduler.

        Args:
            log_file: Path del file di log

        Returns:
            Tuple (success: bool, message: str)
        """
        script_content = f"""
@echo off
cd /d {os.getcwd()}
echo === Update avviato da GUI === > {log_file}
date /t >> {log_file}
time /t >> {log_file}
powershell -NoProfile -Command "bash update.sh" >> {log_file} 2>&1
echo === Update completato === >> {log_file}
date /t >> {log_file}
time /t >> {log_file}
"""
        script_path = os.path.join(os.getcwd(), '.update_gui.bat')
        with open(script_path, 'w') as f:
            f.write(script_content)

        # Crea task con Task Scheduler
        result = subprocess.run(
            [
                'schtasks', '/Create',
                '/TN', 'SolarEdgeUpdate',
                '/TR', script_path,
                '/SC', 'ONCE',
                '/ST', '00:00',
                '/F'
            ],
            capture_output=True,
            text=True,
            timeout=UPDATE_TIMEOUT_SECONDS
        )

        if result.returncode != 0:
            return False, f"Task Scheduler failed: {result.stderr}"

        # Esegui subito il task
        subprocess.run(['schtasks', '/Run', '/TN', 'SolarEdgeUpdate'], timeout=UPDATE_TIMEOUT_SECONDS)

        return True, 'Aggiornamento avviato! Il servizio si riavvierà automaticamente. La GUI si riconnetterà tra circa 30 secondi.'

    async def _run_update_linux(self, log_file: str) -> Tuple[bool, str]:
        """Esegue update su Linux usando systemd-run.

        Args:
            log_file: Path del file di log

        Returns:
            Tuple (success: bool, message: str)
        """
        result = subprocess.run(
            [
                'systemd-run',
                '--unit=solaredge-update',
                '--description=SolarEdge Update from GUI',
                f'--working-directory={os.getcwd()}',
                'bash', '-c',
                f'./update.sh > {log_file} 2>&1'
            ],
            capture_output=True,
            text=True,
            timeout=UPDATE_TIMEOUT_SECONDS
        )

        if result.returncode != 0:
            return False, f"systemd-run failed: {result.stderr}"

        return True, 'Aggiornamento avviato! Il servizio si riavvierà automaticamente. La GUI si riconnetterà tra circa 30 secondi.'


__all__ = ['UpdateService']
