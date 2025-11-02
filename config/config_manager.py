#!/usr/bin/env python3
"""config_manager.py
Sistema centralizzato per lettura configurazione da YAML.
Sostituisce accessi diretti a os.environ con configurazione tipizzata.
"""
from __future__ import annotations
import os
import re
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass(frozen=True)
class GlobalConfig:
    """Configurazione globale del sistema."""
    site_id: str
    timeout_seconds: int = 30
    timezone: str = "Europe/Rome"
    web_request_timeout: int = 40
    api_request_timeout: int = 20
    batch_request_timeout: int = 60
    filter_debug: bool = False


@dataclass(frozen=True)
class LoggingConfig:
    """Configurazione logging."""
    file_logging: bool = True
    level: str = "INFO"
    log_directory: str = "logs"


@dataclass(frozen=True)
class SchedulerConfig:
    """Configurazione scheduler."""
    api_delay_seconds: float = 1.0
    web_delay_seconds: float = 2.0
    realtime_delay_seconds: float = 0.0
    skip_delay_on_cache_hit: bool = True


@dataclass(frozen=True)
class SolarEdgeAPIConfig:
    """Configurazione API SolarEdge."""
    api_key: str
    base_url: str = "https://monitoringapi.solaredge.com"
    rate_limit_seconds: float = 1.0
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    site_id: str = ""
    timeout_seconds: int = 30


@dataclass(frozen=True)
class SolarEdgeWebConfig:
    """Configurazione Web SolarEdge."""
    base_url: str = "https://monitoring.solaredge.com"
    cookie_file: str = "cookies/web_cookies.json"
    login_url: str = "https://monitoring.solaredge.com/solaredge-web/p/login"
    password: str = ""
    session_timeout_seconds: int = 3600
    username: str = ""


@dataclass(frozen=True)
class RealtimeConfig:
    """Configurazione Modbus Realtime."""
    host: str = "192.168.2.59"
    port: int = 1502
    timeout: int = 1
    unit: int = 1


@dataclass(frozen=True)
class InfluxDBConfig:
    """Configurazione InfluxDB."""
    url: str
    org: str
    bucket: str
    bucket_realtime: str
    token: str
    dry_mode: bool = False
    dry_file: str = "influx_dry_output.txt"
    batch_size: int = 5000
    flush_interval_ms: int = 10000
    jitter_interval_ms: int = 2000
    retry_interval_ms: int = 5000
    max_retries: int = 5


class ConfigManager:
    """Manager centralizzato per configurazione da YAML."""
    
    def __init__(self, config_path: str = "config/main.yaml"):
        # Carica variabili d'ambiente dal file .env
        load_dotenv()
        
        self.config_path = Path(config_path)
        self._config_data: Dict[str, Any] = {}
        self._load_config()
    
    def _substitute_env_vars(self, text: str) -> str:
        """Sostituisce variabili d'ambiente nel formato ${VAR_NAME}."""
        def replace_var(match):
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))
        
        return re.sub(r'\$\{([^}]+)\}', replace_var, text)
    
    def _create_empty_web_endpoints(self, web_file: Path) -> None:
        """Crea un file web_endpoints.yaml vuoto con struttura base."""
        # Assicurati che la directory esista
        web_file.parent.mkdir(parents=True, exist_ok=True)
        
        empty_content = """# Web endpoints configuration
# Questo file è stato creato automaticamente
# Esegui 'python main.py --scan' per popolarlo con gli endpoint reali

web_scraping:
  # Gli endpoint verranno aggiunti automaticamente dalla scansione
  # Esempio di struttura:
  # - endpoint: "/solaredge-web/p/sites/12345/dashboard"
  #   name: "dashboard"
  #   enabled: true
"""
        
        web_file.write_text(empty_content, encoding='utf-8')
    
    def _load_config(self) -> None:
        """Carica configurazione YAML con sostituzione variabili d'ambiente."""
        try:
            if not self.config_path.exists():
                raise FileNotFoundError(f"File configurazione non trovato: {self.config_path}")
            
            yaml_content = self.config_path.read_text(encoding='utf-8')
            yaml_content = self._substitute_env_vars(yaml_content)
            self._config_data = yaml.safe_load(yaml_content) or {}
            
            # Carica sources da file separati
            self._load_sources()
            
        except Exception as e:
            raise RuntimeError(f"Errore caricamento configurazione {self.config_path}: {e}") from e
    
    def _load_sources(self) -> None:
        """Carica configurazioni sources da file separati."""
        sources_dir = self.config_path.parent / 'sources'
        
        if not sources_dir.exists():
            # Se la cartella sources non esiste, usa sources dal main.yaml
            return
        
        sources = {}
        
        # Carica API endpoints
        api_file = sources_dir / 'api_endpoints.yaml'
        if api_file.exists():
            api_content = api_file.read_text(encoding='utf-8')
            api_content = self._substitute_env_vars(api_content)
            api_data = yaml.safe_load(api_content) or {}
            if 'api_ufficiali' in api_data:
                sources['api_ufficiali'] = api_data['api_ufficiali']
        
        # Carica Modbus endpoints
        modbus_file = sources_dir / 'modbus_endpoints.yaml'
        if modbus_file.exists():
            modbus_content = modbus_file.read_text(encoding='utf-8')
            modbus_content = self._substitute_env_vars(modbus_content)
            modbus_data = yaml.safe_load(modbus_content) or {}
            if 'modbus' in modbus_data:
                sources['modbus'] = modbus_data['modbus']
        
        # Carica Web endpoints
        web_file = sources_dir / 'web_endpoints.yaml'
        if web_file.exists():
            web_content = web_file.read_text(encoding='utf-8')
            web_content = self._substitute_env_vars(web_content)
            web_data = yaml.safe_load(web_content) or {}
            if 'web_scraping' in web_data:
                sources['web_scraping'] = web_data['web_scraping']
        else:
            # File web_endpoints.yaml mancante - crea file vuoto
            self._create_empty_web_endpoints(web_file)
            # Il file vuoto non avrà sezione web_scraping, quindi sources['web_scraping'] rimane vuoto
        
        # Merge sources nel config principale
        if sources:
            self._config_data['sources'] = sources
    
    def reload(self) -> None:
        """Ricarica configurazione da file."""
        self._load_config()
    
    def get_global_config(self) -> GlobalConfig:
        """Ottieni configurazione globale."""
        global_data = self._config_data.get('global', {})
        return GlobalConfig(
            site_id=global_data.get('site_id', ''),
            timeout_seconds=int(global_data.get('timeout_seconds', 30)),
            timezone=global_data.get('timezone', 'Europe/Rome'),
            web_request_timeout=int(global_data.get('web_request_timeout', 40)),
            api_request_timeout=int(global_data.get('api_request_timeout', 20)),
            batch_request_timeout=int(global_data.get('batch_request_timeout', 60)),
            filter_debug=str(global_data.get('filter_debug', 'false')).lower() == 'true'
        )
    
    def get_logging_config(self) -> LoggingConfig:
        """Ottieni configurazione logging."""
        logging_data = self._config_data.get('logging', {})
        return LoggingConfig(
            file_logging=bool(logging_data.get('file_logging', True)),
            level=logging_data.get('level', 'INFO'),
            log_directory=logging_data.get('log_directory', 'logs')
        )
    
    def get_scheduler_config(self) -> SchedulerConfig:
        """Ottieni configurazione scheduler."""
        scheduler_data = self._config_data.get('scheduler', {})
        return SchedulerConfig(
            api_delay_seconds=float(scheduler_data.get('api_delay_seconds', 1.0)),
            web_delay_seconds=float(scheduler_data.get('web_delay_seconds', 2.0)),
            realtime_delay_seconds=float(scheduler_data.get('realtime_delay_seconds', 0.0)),
            skip_delay_on_cache_hit=bool(scheduler_data.get('skip_delay_on_cache_hit', True))
        )
    
    def get_solaredge_api_config(self) -> SolarEdgeAPIConfig:
        """Ottieni configurazione API SolarEdge."""
        api_data = self._config_data.get('solaredge', {}).get('api', {})
        return SolarEdgeAPIConfig(
            api_key=api_data.get('api_key', ''),
            base_url=api_data.get('base_url', 'https://monitoringapi.solaredge.com'),
            rate_limit_seconds=float(api_data.get('rate_limit_seconds', 1.0)),
            retry_attempts=int(api_data.get('retry_attempts', 3)),
            retry_delay_seconds=float(api_data.get('retry_delay_seconds', 1.0)),
            site_id=api_data.get('site_id', ''),
            timeout_seconds=int(api_data.get('timeout_seconds', 30))
        )
    
    def get_solaredge_web_config(self) -> SolarEdgeWebConfig:
        """Ottieni configurazione Web SolarEdge."""
        web_data = self._config_data.get('solaredge', {}).get('web', {})
        return SolarEdgeWebConfig(
            base_url=web_data.get('base_url', 'https://monitoring.solaredge.com'),
            cookie_file=web_data.get('cookie_file', 'cookies/web_cookies.json'),
            login_url=web_data.get('login_url', 'https://monitoring.solaredge.com/solaredge-web/p/login'),
            password=web_data.get('password', ''),
            session_timeout_seconds=int(web_data.get('session_timeout_seconds', 3600)),
            username=web_data.get('username', '')
        )
    
    def get_influxdb_config(self) -> InfluxDBConfig:
        """Ottieni configurazione InfluxDB dalle variabili d'ambiente.
        
        Supporta bucket separati per dati API/Web e Realtime con retention diverse.
        """
        return InfluxDBConfig(
            url=os.environ.get('INFLUXDB_URL', ''),
            org=os.environ.get('INFLUXDB_ORG', ''),
            bucket=os.environ.get('INFLUXDB_BUCKET', ''),
            bucket_realtime=os.environ.get('INFLUXDB_BUCKET_REALTIME', os.environ.get('INFLUXDB_BUCKET', '')),
            token=os.environ.get('INFLUXDB_TOKEN', ''),
            dry_mode=os.environ.get('INFLUX_DRY_MODE', 'false').lower() == 'true',
            dry_file=os.environ.get('INFLUX_DRY_FILE', 'influx_dry_output.txt'),
            batch_size=int(os.environ.get('INFLUX_BATCH_SIZE', '5000')),
            flush_interval_ms=int(os.environ.get('INFLUX_FLUSH_INTERVAL_MS', '10000')),
            jitter_interval_ms=int(os.environ.get('INFLUX_JITTER_INTERVAL_MS', '2000')),
            retry_interval_ms=int(os.environ.get('INFLUX_RETRY_INTERVAL_MS', '5000')),
            max_retries=int(os.environ.get('INFLUX_MAX_RETRIES', '5'))
        )
    
    def get_realtime_config(self) -> RealtimeConfig:
        """Ottieni configurazione Realtime dalle variabili d'ambiente."""
        return RealtimeConfig(
            host=os.environ.get('REALTIME_MODBUS_HOST', '192.168.2.59'),
            port=int(os.environ.get('REALTIME_MODBUS_PORT', '1502')),
            timeout=int(os.environ.get('REALTIME_MODBUS_TIMEOUT', '1')),
            unit=int(os.environ.get('REALTIME_MODBUS_UNIT', '1'))
        )
    
    def get_modbus_endpoints(self) -> Dict[str, Any]:
        """Ottieni configurazione endpoints Modbus da file YAML.
        
        Returns:
            Dizionario con configurazione modbus endpoints
            
        Raises:
            FileNotFoundError: Se file modbus_endpoints.yaml non trovato
            ValueError: Se configurazione modbus non valida
        """
        modbus_config_path = Path("config/sources/modbus_endpoints.yaml")
        
        if not modbus_config_path.exists():
            raise FileNotFoundError(f"File configurazione modbus non trovato: {modbus_config_path}")
        
        try:
            with open(modbus_config_path, 'r', encoding='utf-8') as f:
                raw_content = f.read()
            
            # Sostituisci variabili d'ambiente
            expanded_content = self._substitute_env_vars(raw_content)
            modbus_config = yaml.safe_load(expanded_content)
            
            if not modbus_config or 'modbus' not in modbus_config:
                raise ValueError("Configurazione modbus non valida: sezione 'modbus' mancante")
            
            return modbus_config['modbus']
            
        except yaml.YAMLError as e:
            raise ValueError(f"Errore parsing YAML modbus_endpoints.yaml: {e}") from e
    
    def get_raw_config(self) -> Dict[str, Any]:
        """Ottieni configurazione raw per compatibilità."""
        return self._config_data.copy()


# Istanza globale singleton
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_path: str = "config/main.yaml") -> ConfigManager:
    """Ottieni istanza singleton del ConfigManager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_path)
    return _config_manager


__all__ = [
    "ConfigManager", "get_config_manager",
    "GlobalConfig", "LoggingConfig", "SchedulerConfig",
    "SolarEdgeAPIConfig", "SolarEdgeWebConfig", "RealtimeConfig", "InfluxDBConfig"
]