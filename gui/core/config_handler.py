#!/usr/bin/env python3
"""
Config Handler - Gestione centralizzata configurazioni
Single Responsibility: caricamento/salvataggio/validazione config
"""

import yaml
import aiofiles
from pathlib import Path
from typing import Dict, Optional
from app_logging.universal_logger import get_logger


class ConfigHandler:
    """Gestisce caricamento e salvataggio configurazioni YAML"""
    
    def __init__(self):
        self.logger = get_logger("ConfigHandler")
        self._config_cache: Dict[str, dict] = {}
        
    async def load_main_config(self, config_file: Path) -> dict:
        """Carica configurazione principale da main.yaml"""
        try:
            if not config_file.exists():
                self.logger.warning(f"Config file non trovato: {config_file}")
                return {}
            
            async with aiofiles.open(config_file, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            # Sostituisci variabili d'ambiente
            from config.config_manager import get_config_manager
            config_manager = get_config_manager()
            content = config_manager._substitute_env_vars(content)
            
            config = yaml.safe_load(content) or {}
            self._config_cache['main'] = config
            return config
            
        except Exception as e:
            self.logger.error(f"Errore caricamento config principale: {e}")
            return {}
    
    async def save_main_config(self, config_file: Path, config: dict) -> bool:
        """Salva configurazione principale"""
        try:
            content = yaml.dump(config, default_flow_style=False, allow_unicode=True, indent=2)
            async with aiofiles.open(config_file, 'w', encoding='utf-8') as f:
                await f.write(content)
            
            self._config_cache['main'] = config
            self.logger.info(f"Config salvato: {config_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Errore salvataggio config: {e}")
            return False
    
    async def load_source_config(self, source_type: str) -> dict:
        """
        Carica configurazione da file sources/ in modo unificato
        
        Args:
            source_type: Tipo di sorgente ('web', 'api', 'modbus')
            
        Returns:
            Dizionario con endpoints/devices della sorgente
        """
        # Check cache first
        if source_type in self._config_cache:
            return self._config_cache[source_type]
        
        # Mappa configurazione per tipo
        config_map = {
            'web': {
                'file': 'config/sources/web_endpoints.yaml',
                'root_key': 'web_scraping',
                'data_key': 'endpoints'
            },
            'api': {
                'file': 'config/sources/api_endpoints.yaml',
                'root_key': 'api_ufficiali',
                'data_key': 'endpoints'
            },
            'modbus': {
                'file': 'config/sources/modbus_endpoints.yaml',
                'root_key': 'modbus',
                'data_key': 'endpoints'
            }
        }
        
        if source_type not in config_map:
            self.logger.error(f"Tipo sorgente non valido: {source_type}")
            return {}
        
        config_info = config_map[source_type]
        file_path = Path(config_info['file'])
        
        try:
            if not file_path.exists():
                return {}
            
            # Async I/O
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            # Sostituisci variabili d'ambiente
            from config.config_manager import get_config_manager
            config_manager = get_config_manager()
            content = config_manager._substitute_env_vars(content)
            
            # Parse YAML
            data = yaml.safe_load(content) or {}
            
            # Estrai dati specifici
            root_data = data.get(config_info['root_key'], {})
            endpoints = root_data.get(config_info['data_key'], {})
            
            # Cache result
            self._config_cache[source_type] = endpoints
            
            return endpoints
            
        except Exception as e:
            self.logger.error(f"Errore caricamento {source_type} endpoints: {e}")
            return {}
    
    async def save_yaml_file(self, file_type: str, content: str) -> tuple[bool, Optional[str]]:
        """
        Salva file YAML generico
        
        Args:
            file_type: Tipo file ('main', 'web_endpoints', 'api_endpoints', 'modbus_endpoints', 'env')
            content: Contenuto da salvare
            
        Returns:
            Tuple (success, error_message)
        """
        config_files = {
            'main': 'config/main.yaml',
            'web_endpoints': 'config/sources/web_endpoints.yaml',
            'api_endpoints': 'config/sources/api_endpoints.yaml',
            'modbus_endpoints': 'config/sources/modbus_endpoints.yaml',
            'env': '.env'
        }
        
        if file_type not in config_files:
            return False, f'File di configurazione non valido: {file_type}'
        
        # Valida YAML (skip per .env)
        if file_type != 'env':
            try:
                yaml.safe_load(content)
            except yaml.YAMLError as e:
                return False, f'YAML non valido: {str(e)}'
        
        file_path = Path(config_files[file_type])
        
        try:
            # Crea directory se non esiste
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Salva file
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(content)
            
            # Invalida cache
            if file_type in self._config_cache:
                del self._config_cache[file_type]
            
            self.logger.info(f"Salvato file: {file_path}")
            return True, None
            
        except Exception as e:
            error_msg = f'Errore salvataggio: {str(e)}'
            self.logger.error(error_msg)
            return False, error_msg
    
    async def get_yaml_file_content(self, file_type: str) -> tuple[Optional[str], Optional[str]]:
        """
        Legge contenuto file YAML
        
        Args:
            file_type: Tipo file
            
        Returns:
            Tuple (content, error_message)
        """
        config_files = {
            'main': 'config/main.yaml',
            'web_endpoints': 'config/sources/web_endpoints.yaml',
            'api_endpoints': 'config/sources/api_endpoints.yaml',
            'modbus_endpoints': 'config/sources/modbus_endpoints.yaml',
            'env': '.env'
        }
        
        if file_type not in config_files:
            return None, f'File non valido: {file_type}'
        
        file_path = Path(config_files[file_type])
        
        if not file_path.exists():
            return None, f'File non trovato: {file_path}'
        
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            return content, None
            
        except Exception as e:
            return None, f'Errore lettura: {str(e)}'
    
    def invalidate_cache(self, source_type: Optional[str] = None):
        """Invalida cache configurazioni"""
        if source_type:
            self._config_cache.pop(source_type, None)
        else:
            self._config_cache.clear()
