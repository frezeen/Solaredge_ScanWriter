#!/usr/bin/env python3
"""
Toggle Handler - Strategy Pattern per gestione toggle unificata
Single Responsibility: gestione toggle device/metric/endpoint
"""

import yaml
import aiofiles
from pathlib import Path
from typing import Dict, Optional, Protocol
from app_logging.universal_logger import get_logger


class ToggleStrategy(Protocol):
    """Interface per strategie di toggle"""
    async def execute(self, **kwargs) -> Dict:
        """Esegue toggle e restituisce nuovo stato"""
        ...


class DeviceToggleStrategy:
    """Strategia per toggle device web scraping"""
    
    def __init__(self):
        self.logger = get_logger("DeviceToggle")
        self.config_file = Path("config/sources/web_endpoints.yaml")
    
    async def execute(self, device_id: str) -> Dict:
        """Toggle device enabled/disabled"""
        try:
            # Carica config
            async with aiofiles.open(self.config_file, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            from config.config_manager import get_config_manager
            config_manager = get_config_manager()
            content = config_manager._substitute_env_vars(content)
            config = yaml.safe_load(content) or {}
            
            # Toggle device
            device = config.get('web_scraping', {}).get('endpoints', {}).get(device_id)
            if not device:
                raise ValueError(f"Device non trovato: {device_id}")
            
            device['enabled'] = not device.get('enabled', False)
            
            # Salva config
            async with aiofiles.open(self.config_file, 'w', encoding='utf-8') as f:
                await f.write(yaml.dump(config, default_flow_style=False, allow_unicode=True, indent=2))
            
            self.logger.info(f"Device {device_id} {'abilitato' if device['enabled'] else 'disabilitato'}")
            
            return {
                'enabled': device['enabled'],
                'device_id': device_id
            }
            
        except Exception as e:
            self.logger.error(f"Errore toggle device {device_id}: {e}")
            raise


class MetricToggleStrategy:
    """Strategia per toggle metrica device"""
    
    def __init__(self):
        self.logger = get_logger("MetricToggle")
        self.config_file = Path("config/sources/web_endpoints.yaml")
    
    async def execute(self, device_id: str, metric: str) -> Dict:
        """Toggle metrica enabled/disabled con cascade su device"""
        try:
            # Carica config
            async with aiofiles.open(self.config_file, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            from config.config_manager import get_config_manager
            config_manager = get_config_manager()
            content = config_manager._substitute_env_vars(content)
            config = yaml.safe_load(content) or {}
            
            # Toggle metrica
            device = config.get('web_scraping', {}).get('endpoints', {}).get(device_id)
            if not device:
                raise ValueError(f"Device non trovato: {device_id}")
            
            measurements = device.get('measurements', {})
            if metric not in measurements:
                raise ValueError(f"Metrica non trovata: {metric}")
            
            measurements[metric]['enabled'] = not measurements[metric].get('enabled', False)
            
            # Auto-toggle device se necessario
            device_changed = False
            any_metric_enabled = any(m.get('enabled', False) for m in measurements.values())
            
            if any_metric_enabled and not device.get('enabled', False):
                # Abilita device se almeno una metrica è abilitata
                device['enabled'] = True
                device_changed = True
            elif not any_metric_enabled and device.get('enabled', False):
                # Disabilita device se nessuna metrica è abilitata
                device['enabled'] = False
                device_changed = True
            
            # Salva config
            async with aiofiles.open(self.config_file, 'w', encoding='utf-8') as f:
                await f.write(yaml.dump(config, default_flow_style=False, allow_unicode=True, indent=2))
            
            self.logger.info(f"Metrica {device_id}.{metric} {'abilitata' if measurements[metric]['enabled'] else 'disabilitata'}")
            
            return {
                'enabled': measurements[metric]['enabled'],
                'device_id': device_id,
                'metric': metric,
                'device_changed': device_changed,
                'device_enabled': device.get('enabled', False)
            }
            
        except Exception as e:
            self.logger.error(f"Errore toggle metrica {device_id}.{metric}: {e}")
            raise


class EndpointToggleStrategy:
    """Strategia per toggle endpoint API"""
    
    def __init__(self):
        self.logger = get_logger("EndpointToggle")
        self.config_file = Path("config/sources/api_endpoints.yaml")
    
    async def execute(self, endpoint_id: str) -> Dict:
        """Toggle endpoint enabled/disabled"""
        try:
            # Carica config
            async with aiofiles.open(self.config_file, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            from config.config_manager import get_config_manager
            config_manager = get_config_manager()
            content = config_manager._substitute_env_vars(content)
            config = yaml.safe_load(content) or {}
            
            # Toggle endpoint
            endpoint = config.get('api_ufficiali', {}).get('endpoints', {}).get(endpoint_id)
            if not endpoint:
                raise ValueError(f"Endpoint non trovato: {endpoint_id}")
            
            endpoint['enabled'] = not endpoint.get('enabled', False)
            
            # Salva config
            async with aiofiles.open(self.config_file, 'w', encoding='utf-8') as f:
                await f.write(yaml.dump(config, default_flow_style=False, allow_unicode=True, indent=2))
            
            self.logger.info(f"Endpoint {endpoint_id} {'abilitato' if endpoint['enabled'] else 'disabilitato'}")
            
            return {
                'enabled': endpoint['enabled'],
                'endpoint_id': endpoint_id
            }
            
        except Exception as e:
            self.logger.error(f"Errore toggle endpoint {endpoint_id}: {e}")
            raise


class ModbusDeviceToggleStrategy:
    """Strategia per toggle device Modbus"""
    
    def __init__(self):
        self.logger = get_logger("ModbusDeviceToggle")
        self.config_file = Path("config/sources/modbus_endpoints.yaml")
    
    async def execute(self, device_id: str) -> Dict:
        """Toggle device Modbus enabled/disabled"""
        try:
            # Carica config
            async with aiofiles.open(self.config_file, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            from config.config_manager import get_config_manager
            config_manager = get_config_manager()
            content = config_manager._substitute_env_vars(content)
            config = yaml.safe_load(content) or {}
            
            # Toggle device
            device = config.get('modbus', {}).get('endpoints', {}).get(device_id)
            if not device:
                raise ValueError(f"Device Modbus non trovato: {device_id}")
            
            device['enabled'] = not device.get('enabled', False)
            
            # Salva config
            async with aiofiles.open(self.config_file, 'w', encoding='utf-8') as f:
                await f.write(yaml.dump(config, default_flow_style=False, allow_unicode=True, indent=2))
            
            self.logger.info(f"Device Modbus {device_id} {'abilitato' if device['enabled'] else 'disabilitato'}")
            
            return {
                'enabled': device['enabled'],
                'device_id': device_id
            }
            
        except Exception as e:
            self.logger.error(f"Errore toggle device Modbus {device_id}: {e}")
            raise


class ModbusMetricToggleStrategy:
    """Strategia per toggle metrica Modbus"""
    
    def __init__(self):
        self.logger = get_logger("ModbusMetricToggle")
        self.config_file = Path("config/sources/modbus_endpoints.yaml")
    
    async def execute(self, device_id: str, metric: str) -> Dict:
        """Toggle metrica Modbus enabled/disabled con cascade su device"""
        try:
            # Carica config
            async with aiofiles.open(self.config_file, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            from config.config_manager import get_config_manager
            config_manager = get_config_manager()
            content = config_manager._substitute_env_vars(content)
            config = yaml.safe_load(content) or {}
            
            # Toggle metrica
            device = config.get('modbus', {}).get('endpoints', {}).get(device_id)
            if not device:
                raise ValueError(f"Device Modbus non trovato: {device_id}")
            
            measurements = device.get('measurements', {})
            if metric not in measurements:
                raise ValueError(f"Metrica Modbus non trovata: {metric}")
            
            measurements[metric]['enabled'] = not measurements[metric].get('enabled', False)
            
            # Auto-toggle device se necessario
            device_changed = False
            any_metric_enabled = any(m.get('enabled', False) for m in measurements.values())
            
            if any_metric_enabled and not device.get('enabled', False):
                device['enabled'] = True
                device_changed = True
            elif not any_metric_enabled and device.get('enabled', False):
                device['enabled'] = False
                device_changed = True
            
            # Salva config
            async with aiofiles.open(self.config_file, 'w', encoding='utf-8') as f:
                await f.write(yaml.dump(config, default_flow_style=False, allow_unicode=True, indent=2))
            
            self.logger.info(f"Metrica Modbus {device_id}.{metric} {'abilitata' if measurements[metric]['enabled'] else 'disabilitata'}")
            
            return {
                'enabled': measurements[metric]['enabled'],
                'device_id': device_id,
                'metric': metric,
                'device_changed': device_changed,
                'device_enabled': device.get('enabled', False)
            }
            
        except Exception as e:
            self.logger.error(f"Errore toggle metrica Modbus {device_id}.{metric}: {e}")
            raise


class ToggleHandler:
    """Handler unificato per tutti i toggle con Strategy Pattern"""
    
    def __init__(self):
        self.logger = get_logger("ToggleHandler")
        
        # Registra strategie
        self.strategies = {
            'device': DeviceToggleStrategy(),
            'metric': MetricToggleStrategy(),
            'endpoint': EndpointToggleStrategy(),
            'modbus_device': ModbusDeviceToggleStrategy(),
            'modbus_metric': ModbusMetricToggleStrategy()
        }
    
    async def toggle(self, toggle_type: str, **kwargs) -> Dict:
        """
        Esegue toggle usando strategia appropriata
        
        Args:
            toggle_type: Tipo toggle ('device', 'metric', 'endpoint', 'modbus_device', 'modbus_metric')
            **kwargs: Parametri specifici per la strategia
            
        Returns:
            Dizionario con nuovo stato
        """
        if toggle_type not in self.strategies:
            raise ValueError(f"Tipo toggle non valido: {toggle_type}")
        
        strategy = self.strategies[toggle_type]
        return await strategy.execute(**kwargs)
