#!/usr/bin/env python3
"""main.py - Orchestratore principale per SolarEdge ScanWriter

Entry point CLI che gestisce routing verso flow handlers appropriati.
Supporta 7 modalità operative: gui, api, web, realtime, gme, scan, history.
"""

import sys
import argparse
import os
from typing import Any, Dict, Callable, Optional
from logging import Logger

from config.env_loader import load_env
from app_logging import configure_logging, get_logger
from cache.cache_manager import CacheManager
from config.config_manager import get_config_manager
from utils.color_logger import color

# Import Flows
from flows import (
    run_api_flow,
    run_web_flow,
    run_realtime_flow,
    run_scan_flow,
    run_gui_mode,
    run_gme_flow
)
from tools.history_manager import run_history_flow

load_env()

# Costanti
DEFAULT_MODE = 'gui'
DEFAULT_CONFIG_PATH = 'config/main.yaml'


# Definizione delle modalita' operative
# Ogni modalita' ha configurazione di log e funzione handler
MODES: Dict[str, Dict[str, Any]] = {
    'gui': {
        'help': 'Avvia GUI Dashboard con loop in modalita\' stop (Default)',
        'log_env': 'LOG_FILE_GUI',
        'default_log': 'loop_mode.log',
        'handler': run_gui_mode
    },
    'web': {
        'help': 'Esegui singola raccolta dati web',
        'log_env': 'LOG_FILE_WEB',
        'default_log': 'web_flow.log',
        'handler': run_web_flow
    },
    'api': {
        'help': 'Esegui singola raccolta dati API',
        'log_env': 'LOG_FILE_API',
        'default_log': 'api_flow.log',
        'handler': run_api_flow
    },
    'realtime': {
        'help': 'Esegui singola raccolta dati realtime',
        'log_env': 'LOG_FILE_REALTIME',
        'default_log': 'realtime_flow.log',
        'handler': run_realtime_flow
    },
    'gme': {
        'help': 'Esegui raccolta dati GME (Mercato Elettrico Italiano)',
        'log_env': 'LOG_FILE_GME',
        'default_log': 'gme_flow.log',
        'handler': run_gme_flow
    },
    'scan': {
        'help': 'Esegui scansione web tree e aggiorna configurazione',
        'log_env': 'LOG_FILE_SCAN',
        'default_log': 'scanner.log',
        'handler': run_scan_flow
    },
    'history': {
        'help': 'Scarica storico completo da SolarEdge (suddivisione mensile)',
        'log_env': 'LOG_FILE_HISTORY',
        'default_log': 'history.log',
        'handler': run_history_flow
    }
}

def get_active_mode(args: argparse.Namespace) -> str:
    """Determina modalità operativa attiva dagli argomenti CLI.

    Args:
        args: Argomenti parsati da argparse

    Returns:
        Nome della modalità attiva (default: 'gui')
    """
    for mode in MODES:
        if mode == DEFAULT_MODE:
            continue  # Skip gui check in args as it's default
        if getattr(args, mode, False):
            return mode
    return DEFAULT_MODE

def setup_logging(active_mode: str, config: Dict[str, Any]) -> None:
    """Configura sistema di logging per la modalità attiva.

    Imposta livello log, directory e file specifico per la modalità.
    Supporta override tramite variabili d'ambiente.

    Args:
        active_mode: Modalità operativa attiva
        config: Configurazione completa caricata da YAML
    """
    logging_config = config.get('logging', {})
    os.environ["LOG_LEVEL"] = logging_config.get('level', 'INFO')
    os.environ["LOG_DIR"] = logging_config.get('log_directory', 'logs')

    # Determina il file di log per la modalità
    mode_conf = MODES.get(active_mode, {})
    log_file = os.getenv(mode_conf.get('log_env', ''), mode_conf.get('default_log', 'app.log'))

    if logging_config.get('file_logging', True) and log_file:
        configure_logging(log_file=log_file, script_name="main")
    else:
        configure_logging(script_name="main")

def execute_flow(
    flow_name: str,
    log: Logger,
    cache: CacheManager,
    config: Dict[str, Any],
    **kwargs
) -> int:
    """Esegue un singolo flow handler.

    API pubblica per esecuzione flow on-demand (usata da GUI).

    Args:
        flow_name: Nome del flow ('api', 'web', 'realtime', 'gme', 'scan', 'history', 'gui')
        log: Logger instance
        cache: CacheManager instance
        config: Configurazione completa
        **kwargs: Parametri aggiuntivi per il flow (es. year per history)

    Returns:
        Exit code (0 = success, 1 = error)

    Raises:
        KeyError: Se flow_name non esiste in MODES
    """
    if flow_name not in MODES:
        available = ', '.join(MODES.keys())
        raise KeyError(f"Flow '{flow_name}' non esiste. Disponibili: {available}")

    handler = MODES[flow_name]['handler']
    return handler(log, cache, config, **kwargs)


def main() -> int:
    """Entry point principale per esecuzione CLI.

    Gestisce:
    - Parsing argomenti CLI
    - Caricamento configurazione
    - Setup logging per modalità
    - Routing a flow handler appropriato
    - Gestione errori top-level

    Returns:
        Exit code (0 = success, 1 = error)
    """
    ap = argparse.ArgumentParser(
        description="SolarEdge Data Collector",
        epilog="Senza argomenti: avvia GUI Dashboard con loop in modalita' stop"
    )

    # Generazione dinamica degli argomenti
    grp = ap.add_mutually_exclusive_group(required=False)
    for mode, conf in MODES.items():
        if mode == DEFAULT_MODE:
            continue  # Non aggiungere flag per gui (è default)
        if mode == 'history':
            # History accetta opzionalmente un anno
            grp.add_argument(
                f'--{mode}',
                nargs='?',
                const=True,
                metavar='YEAR',
                help=f"{conf['help']} (opzionale: specifica anno, es. --history 2024)"
            )
        else:
            grp.add_argument(f'--{mode}', action='store_true', help=conf['help'])

    args = ap.parse_args()

    # Caricamento configurazione
    config_path = os.getenv('CONFIG_PATH', DEFAULT_CONFIG_PATH)
    config_manager = get_config_manager(config_path)
    config = config_manager.get_raw_config()

    # Setup Logging
    active_mode = get_active_mode(args)
    setup_logging(active_mode, config)
    log = get_logger("main")
    log.info("[SYSTEM] ✅ Config manager caricato")

    # Inizializzazione Cache
    cache = CacheManager()
    log.info("[SYSTEM] ✅ Cache manager inizializzato")

    try:
        # Esecuzione flow con parametri opzionali
        kwargs = {}
        if active_mode == 'history' and args.history and args.history is not True:
            kwargs['year'] = args.history

        return execute_flow(active_mode, log, cache, config, **kwargs)

    except KeyboardInterrupt:
        log.info(color.warning("👋 Uscita pulita richiesta dall'utente"))
        return 0
    except Exception as e:
        log.error(color.error(f"Errore esecuzione: {e}"))
        return 1

__all__ = ['execute_flow', 'MODES', 'main']


if __name__ == '__main__':
    sys.exit(main())
