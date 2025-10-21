"""universal_logger.py
SORGENTE: logging_universale (modulo trasversale)
Logger universale (Step 14) evitando shadow del modulo stdlib 'logging'.
"""
from __future__ import annotations
import logging as _logging
import os
from pathlib import Path
from config.config_manager import get_config_manager

__all__ = ["get_logger", "configure_logging"]

# Configurazione lazy-loaded
_config_manager = None
_logging_config = None
_DEFAULT_LEVEL = "INFO"
_DEFAULT_DIR = Path("logs")
_configured = False


def _get_logging_config():
    """Ottieni configurazione logging con lazy loading."""
    global _config_manager, _logging_config, _DEFAULT_LEVEL, _DEFAULT_DIR
    if _config_manager is None:
        _config_manager = get_config_manager()
        _logging_config = _config_manager.get_logging_config()
        _DEFAULT_LEVEL = _logging_config.level
        _DEFAULT_DIR = Path(_logging_config.log_directory)
    return _logging_config


def configure_logging(level: str | None = None, log_file: str | None = None, script_name: str | None = None) -> None:
    # Carica configurazione lazy
    _get_logging_config()
    
    root_logger = _logging.getLogger()
    # Rimuovi tutti gli handler esistenti per evitare duplicazioni
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    lvl = (level or _DEFAULT_LEVEL).upper()
    _DEFAULT_DIR.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    
    # Configura il logger di base (console)
    _logging.basicConfig(level=lvl, format=fmt)

    # Aggiungi il file handler se specificato
    if log_file:
        if script_name:
            script_dir = _DEFAULT_DIR / script_name
            script_dir.mkdir(parents=True, exist_ok=True)
            file_path = script_dir / log_file
        else:
            file_path = _DEFAULT_DIR / log_file
        if file_path.exists():
            try:
                os.remove(file_path)
            except OSError as e:
                _logging.getLogger(__name__).warning(f"Impossibile rimuovere il file di log {file_path}: {e}")
        fh = _logging.FileHandler(file_path, encoding="utf-8")
        fh.setLevel(lvl)
        fh.setFormatter(_logging.Formatter(fmt))
        root_logger.addHandler(fh)

def get_logger(name: str):
    # La configurazione viene chiamata al bisogno o esplicitamente
    if not _logging.getLogger().hasHandlers():
        configure_logging()
    return _logging.getLogger(name)
