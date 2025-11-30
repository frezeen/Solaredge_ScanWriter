#!/usr/bin/env python3
"""main.py - Orchestratore ottimizzato e data-driven"""

import sys
import argparse
import os
from typing import Any, Dict, Callable

from config.env_loader import load_env
from app_logging import configure_logging, get_logger
from cache.cache_manager import CacheManager
from config.config_manager import get_config_manager
from utils.color_logger import color

# Import Flows
from flows.api_flow import run_api_flow
from flows.web_flow import run_web_flow
from flows.realtime_flow import run_realtime_flow
from flows.scan_flow import run_scan_flow
from flows.gui_flow import run_gui_mode
from flows.gme_flow import run_gme_flow
from tools.history_manager import run_history_flow

load_env()


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

def get_active_mode(args) -> str:
    """Restituisce la modalita' attiva basata sugli argomenti CLI, default 'gui'."""
    for mode in MODES:
        if mode == 'gui': continue # Skip gui check in args as it's default
        if getattr(args, mode, False):
            return mode
    return 'gui'

def setup_logging(active_mode: str, config: Dict[str, Any]) -> None:
    """Configura logging basato sulla modalita' attiva."""
    logging_config = config.get('logging', {})
    os.environ["LOG_LEVEL"] = logging_config.get('level', 'INFO')
    os.environ["LOG_DIR"] = logging_config.get('log_directory', 'logs')
    
    # Determina il file di log
    mode_conf = MODES.get(active_mode, {})
    log_file = os.getenv(mode_conf.get('log_env', ''), mode_conf.get('default_log', 'app.log'))
    
    if logging_config.get('file_logging', True) and log_file:
        configure_logging(log_file=log_file, script_name="main")
    else:
        configure_logging(script_name="main")

def main() -> int:
    """Entry point principale ottimizzato"""
    ap = argparse.ArgumentParser(
        description="SolarEdge Data Collector",
        epilog="Senza argomenti: avvia GUI Dashboard con loop in modalita' stop"
    )
    
    # Generazione dinamica degli argomenti
    grp = ap.add_mutually_exclusive_group(required=False)
    for mode, conf in MODES.items():
        if mode == 'gui': continue # Non aggiungere flag per gui (è default)
        grp.add_argument(f'--{mode}', action='store_true', help=conf['help'])
        
    args = ap.parse_args()
    
    # Caricamento configurazione
    config_path = os.getenv('CONFIG_PATH', 'config/main.yaml')
    config_manager = get_config_manager(config_path)
    config = config_manager.get_raw_config()
    
    # Setup Logging
    active_mode = get_active_mode(args)
    setup_logging(active_mode, config)
    log = get_logger("main")
    
    # Log configurazione sistema (una volta all'avvio)
    scheduler_config = config_manager.get_scheduler_config()
    log.info(
        f"⏱️  Scheduler configurato - "
        f"API: {scheduler_config.api_delay_seconds}s, "
        f"Web: {scheduler_config.web_delay_seconds}s, "
        f"Realtime: {scheduler_config.realtime_delay_seconds}s, "
        f"GME: {scheduler_config.gme_delay_seconds}s"
    )
    
    influx_config = config_manager.get_influxdb_config()
    log.info(
        f"✅ InfluxDB configurato - "
        f"URL: {influx_config.url}, "
        f"Org: {influx_config.org}, "
        f"Bucket: {influx_config.bucket}, "
        f"Gzip: {influx_config.enable_gzip}, "
        f"Precision: {influx_config.write_precision}"
    )
    
    # Inizializzazione Cache
    cache = CacheManager()
    log.info(color.success("✅ Cache centralizzata inizializzata"))
    
    try:
        # Esecuzione dinamica handler
        handler = MODES[active_mode]['handler']
        return handler(log, cache, config)
            
    except KeyboardInterrupt:
        log.info(color.warning("👋 Uscita pulita richiesta dall'utente"))
        return 0
    except Exception as e:
        log.error(color.error(f"Errore esecuzione: {e}"))
        return 1

if __name__ == '__main__':
    sys.exit(main())
