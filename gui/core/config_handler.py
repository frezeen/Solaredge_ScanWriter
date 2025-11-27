#!/usr/bin/env python3
"""
Config Handler - Gestione centralizzata configurazioni
Single Responsibility: caricamento/salvataggio/validazione config
"""

import aiofiles
from pathlib import Path
from typing import Dict, Optional
from app_logging.universal_logger import get_logger
from utils.yaml_loader import get_yaml_loader


class ConfigHandler:
    """Gestisce caricamento e salvataggio configurazioni YAML"""
    
    def __init__(self):
        self.logger = get_logger("ConfigHandler")
        self._config_cache: Dict[str, dict] = {}
        
    async def load_main_config(self, config_file: Path) -> dict:
        """Carica configurazione principale da main.yaml (using unified YAML loader)"""
        try:
            # Use unified YAML loader with caching
            yaml_loader = get_yaml_loader()
            config = yaml_loader.load_yaml(config_file, substitute_env=True, use_cache=True)
            self._config_cache['main'] = config
            return config
            
        except FileNotFoundError:
            self.logger.warning(f"Config file non trovato: {config_file}")
            return {}
        except Exception as e:
            self.logger.error(f"Errore caricamento config principale: {e}")
            return {}
    
    async def save_main_config(self, config_file: Path, config: dict) -> bool:
        """Salva configurazione principale (using unified YAML saver)"""
        try:
            # Use unified YAML saver with cache invalidation
            yaml_loader = get_yaml_loader()
            success = yaml_loader.save_yaml(config_file, config, invalidate_cache=True)
            
            if success:
                self._config_cache['main'] = config
                self.logger.info(f"Config salvato: {config_file}")
            
            return success
            
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
            # Use unified YAML loader with caching
            yaml_loader = get_yaml_loader()
            data = yaml_loader.load_yaml(file_path, substitute_env=True, use_cache=True)
            
            # Estrai dati specifici
            root_data = data.get(config_info['root_key'], {})
            endpoints = root_data.get(config_info['data_key'], {})
            
            # Cache result
            self._config_cache[source_type] = endpoints
            
            return endpoints
            
        except FileNotFoundError:
            return {}
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
            yaml_loader = get_yaml_loader()
            is_valid, error = yaml_loader.validate_yaml(content)
            if not is_valid:
                return False, f'YAML non valido: {error}'
        
        file_path = Path(config_files[file_type])
        
        try:
            # For .env files, write directly; for YAML, use unified saver
            if file_type == 'env':
                # Crea directory se non esiste
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Salva file .env
                async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                    await f.write(content)
            else:
                # Use unified YAML saver for YAML files
                # Parse content string to dict first using unified loader
                yaml_loader = get_yaml_loader()
                
                # Validate and parse YAML content
                is_valid, error = yaml_loader.validate_yaml(content)
                if not is_valid:
                    return False, f'YAML parsing error: {error}'
                
                # Parse to dict (we know it's valid now)
                import yaml
                data = yaml.safe_load(content)
                
                # Save using unified saver
                if not yaml_loader.save_yaml(file_path, data, invalidate_cache=True):
                    return False, 'Errore salvataggio YAML'
            
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
