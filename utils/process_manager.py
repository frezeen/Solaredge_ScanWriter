"""Process Management Utilities

Cross-platform utilities for process management.
"""

import os
import re
import time
import subprocess
import platform
from logging import Logger


def kill_process_on_port(port: int, log: Logger) -> bool:
    """Killa il processo che occupa una porta specifica (Cross-Platform)

    Args:
        port: Numero della porta da liberare
        log: Logger instance per output

    Returns:
        True se il processo è stato terminato, False altrimenti
    """
    try:
        system = platform.system().lower()

        if system == "windows":
            # Windows: usa netstat + taskkill
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True,
                text=True,
                timeout=int(os.getenv('GLOBAL_TIMEOUT_SECONDS', '30'))
            )

            if result.returncode != 0:
                log.warning(f"⚠️ Comando netstat fallito per porta {port}")
                return False

            # Cerca il PID nella output di netstat
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        log.info(f"🔍 Trovato processo PID {pid} sulla porta {port}")

                        # Termina il processo usando taskkill
                        kill_result = subprocess.run(
                            ['taskkill', '/F', '/PID', pid],
                            capture_output=True,
                            text=True,
                            timeout=int(os.getenv('GLOBAL_TIMEOUT_SECONDS', '30'))
                        )

                        if kill_result.returncode == 0:
                            log.info(f"✅ Processo PID {pid} terminato")
                            time.sleep(int(os.getenv('SCHEDULER_API_DELAY_SECONDS', '1')))
                            return True
                        else:
                            log.warning(f"⚠️ Impossibile terminare processo PID {pid}: {kill_result.stderr}")
                            return False

        else:
            # Linux/macOS: usa ss o netstat + kill
            # Prova prima ss (più moderno)
            try:
                result = subprocess.run(
                    ['ss', '-tlnp', f'sport = :{port}'],
                    capture_output=True,
                    text=True,
                    timeout=int(os.getenv('GLOBAL_TIMEOUT_SECONDS', '30'))
                )
            except FileNotFoundError:
                # Fallback a netstat se ss non disponibile
                result = subprocess.run(
                    ['netstat', '-tlnp'],
                    capture_output=True,
                    text=True,
                    timeout=int(os.getenv('GLOBAL_TIMEOUT_SECONDS', '30'))
                )

            if result.returncode != 0:
                log.warning(f"⚠️ Comando di ricerca processo fallito per porta {port}")
                return False

            # Cerca il PID nella output
            for line in result.stdout.split('\n'):
                if f':{port}' in line and ('LISTEN' in line or 'LISTENING' in line):
                    pid_match = re.search(r'(\d+)/', line)  # Formato: PID/nome_processo
                    if not pid_match:
                        pid_match = re.search(r'pid=(\d+)', line)  # Formato ss alternativo

                    if pid_match:
                        pid = pid_match.group(1)
                        log.info(f"🔍 Trovato processo PID {pid} sulla porta {port}")

                        # Termina il processo usando kill
                        kill_result = subprocess.run(
                            ['kill', '-TERM', pid],  # Usa TERM invece di -9 per shutdown graceful
                            capture_output=True,
                            text=True,
                            timeout=int(os.getenv('GLOBAL_TIMEOUT_SECONDS', '30'))
                        )

                        if kill_result.returncode == 0:
                            log.info(f"✅ Processo PID {pid} terminato")
                            time.sleep(int(os.getenv('SCHEDULER_API_DELAY_SECONDS', '1')))
                            return True
                        else:
                            log.warning(f"⚠️ Impossibile terminare processo PID {pid}: {kill_result.stderr}")
                            return False

        log.info(f"ℹ️ Nessun processo trovato sulla porta {port}")
        return False

    except subprocess.TimeoutExpired:
        log.error(f"❌ Timeout durante ricerca processo su porta {port}")
        return False
    except FileNotFoundError as e:
        log.error(f"❌ Comando non trovato: {e}")
        return False
    except Exception as e:
        log.error(f"❌ Errore durante kill processo su porta {port}: {e}")
        return False
