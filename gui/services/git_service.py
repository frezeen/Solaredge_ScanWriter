#!/usr/bin/env python3
"""
Git Service - Gestione operazioni Git
Responsabilità: Check updates, fetch, commit diff
"""

import os
import subprocess
from typing import Tuple, Optional

from app_logging.universal_logger import get_logger

# Costanti
GIT_TIMEOUT_SECONDS = 10


class GitService:
    """Servizio per operazioni Git"""

    def __init__(self):
        self.logger = get_logger("GitService")

    async def fetch_updates(self) -> Tuple[bool, Optional[str]]:
        """Esegue git fetch per aggiornare informazioni remote.

        Returns:
            Tuple (success: bool, error_message: Optional[str])
        """
        try:
            result = subprocess.run(
                ['git', 'fetch', 'origin'],
                cwd=os.getcwd(),
                capture_output=True,
                text=True,
                timeout=GIT_TIMEOUT_SECONDS
            )

            if result.returncode != 0:
                return False, result.stderr

            return True, None

        except subprocess.TimeoutExpired:
            return False, 'Timeout durante git fetch'
        except Exception as e:
            return False, str(e)

    async def get_commit_diff(self) -> Tuple[bool, Optional[int], Optional[int], Optional[str]]:
        """Ottiene differenza commit tra locale e remote.

        Returns:
            Tuple (success: bool, local_commits: Optional[int], remote_commits: Optional[int], error: Optional[str])
        """
        try:
            # Prova con 'main'
            result = subprocess.run(
                ['git', 'rev-list', '--left-right', '--count', 'HEAD...origin/main'],
                cwd=os.getcwd(),
                capture_output=True,
                text=True,
                timeout=GIT_TIMEOUT_SECONDS
            )

            # Fallback a 'master' se 'main' non esiste
            if result.returncode != 0:
                result = subprocess.run(
                    ['git', 'rev-list', '--left-right', '--count', 'HEAD...origin/master'],
                    cwd=os.getcwd(),
                    capture_output=True,
                    text=True,
                    timeout=GIT_TIMEOUT_SECONDS
                )

            if result.returncode == 0:
                local, remote = map(int, result.stdout.strip().split())
                return True, local, remote, None
            else:
                return False, None, None, result.stderr

        except subprocess.TimeoutExpired:
            return False, None, None, 'Timeout durante git rev-list'
        except Exception as e:
            return False, None, None, str(e)


__all__ = ['GitService']
