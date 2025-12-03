#!/usr/bin/env python3
"""
Unified Toggle Handler - Consolidates all toggle logic
Follows REDUNDANCY_DUPLICATION_REPORT.md recommendations
Single Responsibility: Unified toggle operations for all entity types
"""

from pathlib import Path
from typing import Tuple, Dict, Optional
from app_logging.universal_logger import get_logger
from utils.yaml_loader import load_yaml, save_yaml


class UnifiedToggleHandler:
    """
    Unified handler for all toggle operations (devices, metrics, endpoints).
    Consolidates duplicate logic from 5 separate handlers into one.

    Reduces codebase by ~430 lines (70% reduction in toggle logic).
    """

    def __init__(self):
        """Initialize unified toggle handler."""
        self.logger = get_logger("UnifiedToggleHandler")

        # Entity type configuration mapping
        self.entity_config = {
            'web_device': {
                'config_file': 'config/sources/web_endpoints.yaml',
                'source_key': 'web_scraping',
                'source_name': 'Web scraping',
                'entity_container': 'endpoints'
            },
            'web_metric': {
                'config_file': 'config/sources/web_endpoints.yaml',
                'source_key': 'web_scraping',
                'source_name': 'Web scraping',
                'entity_container': 'endpoints'
            },
            'modbus_device': {
                'config_file': 'config/sources/modbus_endpoints.yaml',
                'source_key': 'modbus',
                'source_name': 'Modbus',
                'entity_container': 'endpoints'
            },
            'modbus_metric': {
                'config_file': 'config/sources/modbus_endpoints.yaml',
                'source_key': 'modbus',
                'source_name': 'Modbus',
                'entity_container': 'endpoints'
            },
            'api_endpoint': {
                'config_file': 'config/sources/api_endpoints.yaml',
                'source_key': 'api_ufficiali',
                'source_name': 'API',
                'entity_container': 'endpoints'
            }
        }

    async def _toggle_entity(self, entity_type: str, entity_id: str, metric: Optional[str] = None) -> Tuple[bool, Dict]:
        """
        Unified toggle logic for all entity types.

        Steps (as per report):
        1. Load config based on entity_type
        2. Navigate to entity
        3. Toggle state
        4. Cascade if needed (device → metrics)
        5. Auto-update source.enabled
        6. Save config
        7. Return response

        Args:
            entity_type: Type of entity ('web_device', 'web_metric', 'modbus_device', 'modbus_metric', 'api_endpoint')
            entity_id: ID of the entity to toggle
            metric: Metric name (only for metric toggles)

        Returns:
            Tuple of (success: bool, response_data: dict)
        """
        try:
            # Validate entity type
            if entity_type not in self.entity_config:
                return False, {'error': f'Unknown entity type: {entity_type}'}

            config_info = self.entity_config[entity_type]
            config_file = config_info['config_file']
            source_key = config_info['source_key']
            source_name = config_info['source_name']
            entity_container = config_info['entity_container']

            # Step 1: Load configuration (using unified YAML loader)
            config_path = Path(config_file)
            try:
                config = load_yaml(config_path, substitute_env=True, use_cache=True)
            except FileNotFoundError:
                return False, {'error': f'Config file not found: {config_file}'}
            except Exception as e:
                return False, {'error': f'Error loading config: {str(e)}'}

            # Step 2: Navigate to entity
            if source_key not in config or entity_container not in config[source_key]:
                return False, {'error': f'Invalid config structure in {config_file}'}

            entities = config[source_key][entity_container]

            # Step 3-4: Toggle state (with cascade if needed)
            # Build toggle context dictionary to reduce parameter count
            toggle_context = {
                'entities': entities,
                'entity_id': entity_id,
                'source_name': source_name,
                'source_key': source_key,
                'config': config,
                'config_path': config_path
            }

            if entity_type in ('web_device', 'modbus_device'):
                success, response_data = self._toggle_device(toggle_context)
            elif entity_type in ('web_metric', 'modbus_metric'):
                if not metric:
                    return False, {'error': 'Missing metric name'}
                toggle_context['metric'] = metric
                success, response_data = self._toggle_metric(toggle_context)
            elif entity_type == 'api_endpoint':
                success, response_data = self._toggle_endpoint(toggle_context)
            else:
                return False, {'error': f'Unsupported entity type: {entity_type}'}

            if not success:
                return False, response_data

            # Step 6: Save configuration (using unified YAML saver)
            if not save_yaml(config_path, config, invalidate_cache=True):
                return False, {'error': 'Failed to save configuration'}

            # Step 7: Return response
            return True, response_data

        except Exception as e:
            self.logger.error(f"Error in _toggle_entity({entity_type}, {entity_id}, {metric}): {e}")
            return False, {'error': f'Internal server error: {str(e)}'}

    def _toggle_device(self, toggle_context: Dict) -> Tuple[bool, Dict]:
        """Toggle device with cascade to all metrics.

        Args:
            toggle_context: Dictionary containing:
                - entities: Dict of entities
                - entity_id: ID of entity to toggle
                - source_name: Display name of source
                - source_key: Config key for source
                - config: Full configuration dict
                - config_path: Path to config file
        """
        entities = toggle_context['entities']
        entity_id = toggle_context['entity_id']
        source_name = toggle_context['source_name']
        source_key = toggle_context['source_key']
        config = toggle_context['config']
        config_path = toggle_context['config_path']

        if entity_id not in entities:
            return False, {'error': f'Device not found: {entity_id}'}

        device = entities[entity_id]
        current_state = device.get('enabled', False)
        new_state = not current_state
        device['enabled'] = new_state

        # Cascade toggle to all metrics
        metrics_updated = 0
        updated_measurements = {}
        if 'measurements' in device:
            for metric_name, metric_config in device['measurements'].items():
                if isinstance(metric_config, dict):
                    metric_config['enabled'] = new_state
                    updated_measurements[metric_name] = {'enabled': new_state}
                    metrics_updated += 1

        # Step 5: Auto-update source.enabled
        source_auto_updated, any_entity_enabled = self._auto_update_source(
            config, source_key, entities, config_path, source_name
        )

        self.logger.info(f"Toggled {source_name} device {entity_id}: {current_state} -> {new_state} (cascaded to {metrics_updated} metrics)")

        response_data = {
            'success': True,
            'device_id': entity_id,
            'enabled': new_state,
            'measurements': updated_measurements,
            'metrics_updated': metrics_updated,
            'message': f'{source_name} device {entity_id} {"enabled" if new_state else "disabled"} (with {metrics_updated} metrics)'
        }

        if source_auto_updated:
            response_data['source_auto_updated'] = True
            response_data['source_enabled'] = any_entity_enabled
            response_data['message'] += f" - {source_name} {'abilitato' if any_entity_enabled else 'disabilitato'} automaticamente"

        return True, response_data

    def _toggle_metric(self, toggle_context: Dict) -> Tuple[bool, Dict]:
        """Toggle metric with smart device auto-toggle using guard clauses.

        Args:
            toggle_context: Dictionary containing:
                - entities: Dict of entities
                - entity_id: ID of entity to toggle
                - metric: Name of metric to toggle
                - source_name: Display name of source
                - source_key: Config key for source
                - config: Full configuration dict
                - config_path: Path to config file
        """
        entities = toggle_context['entities']
        entity_id = toggle_context['entity_id']
        metric = toggle_context['metric']
        source_name = toggle_context['source_name']
        source_key = toggle_context['source_key']
        config = toggle_context['config']
        config_path = toggle_context['config_path']

        # Guard clause: Check device exists
        if entity_id not in entities:
            return False, {'error': f'Device not found: {entity_id}'}

        device = entities[entity_id]

        # Guard clause: Check metric exists
        if 'measurements' not in device or metric not in device['measurements']:
            return False, {'error': f'Metric not found: {metric}'}

        # Toggle metric state
        measurements = device['measurements']
        current_state = measurements[metric].get('enabled', False)
        new_state = not current_state
        measurements[metric]['enabled'] = new_state

        # Smart device auto-toggle logic with guard clauses
        device_current_state = device.get('enabled', False)
        device_new_state = device_current_state
        device_changed = False

        # Guard clause: Auto-enable device if metric enabled and device off
        if new_state and not device_current_state:
            device['enabled'] = True
            device_new_state = True
            device_changed = True
            self.logger.info(f"Auto-enabled {source_name} device {entity_id} because metric {metric} was enabled")

        # Guard clause: Auto-disable device if metric disabled and no other metrics enabled
        if not new_state and device_current_state:
            enabled_metrics = [m for m, cfg in measurements.items() if cfg.get('enabled', False)]
            if len(enabled_metrics) == 0:
                device['enabled'] = False
                device_new_state = False
                device_changed = True
                self.logger.info(f"Auto-disabled {source_name} device {entity_id} because no metrics are enabled")

        # Auto-update source.enabled
        source_auto_updated, any_entity_enabled = self._auto_update_source(
            config, source_key, entities, config_path, source_name
        )

        self.logger.info(f"Toggled {source_name} metric {entity_id}.{metric}: {current_state} -> {new_state}")

        # Build response
        response_data = {
            'success': True,
            'device_id': entity_id,
            'metric': metric,
            'enabled': new_state,
            'device_enabled': device_new_state,
            'device_changed': device_changed,
            'message': f'{source_name} metric {entity_id}.{metric} {"enabled" if new_state else "disabled"}'
        }

        if device_changed:
            response_data['message'] += f' (device auto-{"enabled" if device_new_state else "disabled"})'

        if source_auto_updated:
            response_data['source_auto_updated'] = True
            response_data['source_enabled'] = any_entity_enabled
            response_data['message'] += f' - {source_name} {'abilitato' if any_entity_enabled else 'disabilitato'} automaticamente'

        return True, response_data

    def _toggle_endpoint(self, toggle_context: Dict) -> Tuple[bool, Dict]:
        """Toggle API endpoint.

        Args:
            toggle_context: Dictionary containing:
                - entities: Dict of entities
                - entity_id: ID of entity to toggle
                - source_name: Display name of source
                - source_key: Config key for source
                - config: Full configuration dict
                - config_path: Path to config file
        """
        entities = toggle_context['entities']
        entity_id = toggle_context['entity_id']
        source_name = toggle_context['source_name']
        source_key = toggle_context['source_key']
        config = toggle_context['config']
        config_path = toggle_context['config_path']

        if entity_id not in entities:
            return False, {'error': f'Endpoint not found: {entity_id}'}

        endpoint = entities[entity_id]
        current_state = endpoint.get('enabled', False)
        new_state = not current_state
        endpoint['enabled'] = new_state

        # Step 5: Auto-update source.enabled
        source_auto_updated, any_entity_enabled = self._auto_update_source(
            config, source_key, entities, config_path, source_name
        )

        self.logger.info(f"Toggled {source_name} endpoint {entity_id}: {current_state} -> {new_state}")

        response_data = {
            'success': True,
            'endpoint_id': entity_id,
            'enabled': new_state,
            'message': f'{source_name} endpoint {entity_id} {"enabled" if new_state else "disabled"}'
        }

        if source_auto_updated:
            response_data['source_auto_updated'] = True
            response_data['source_enabled'] = any_entity_enabled
            response_data['message'] += f" - {source_name} {'abilitato' if any_entity_enabled else 'disabilitato'} automaticamente"

        return True, response_data

    def _auto_update_source(self, config: Dict, source_key: str, entities: Dict,
                           config_path: Path, source_name: str) -> Tuple[bool, bool]:
        """Auto-update source.enabled based on entity states."""
        # Enable source if any entity is enabled
        any_entity_enabled = any(
            entity.get('enabled', False)
            for entity in entities.values()
            if isinstance(entity, dict)
        )

        old_enabled = config[source_key].get('enabled', False)

        if old_enabled != any_entity_enabled:
            config[source_key]['enabled'] = any_entity_enabled
            enabled_count = sum(1 for e in entities.values() if isinstance(e, dict) and e.get('enabled', False))
            self.logger.info(f"{source_name} auto-{'abilitato' if any_entity_enabled else 'disabilitato'} (endpoint attivi: {enabled_count})")
            return True, any_entity_enabled

        return False, old_enabled

    # Public API methods (as per report)
    async def handle_toggle_endpoint(self, entity_id: str) -> Tuple[bool, Dict]:
        """Toggle API endpoint."""
        return await self._toggle_entity('api_endpoint', entity_id)

    async def handle_toggle_device(self, entity_id: str) -> Tuple[bool, Dict]:
        """Toggle web device."""
        return await self._toggle_entity('web_device', entity_id)

    async def handle_toggle_modbus_device(self, entity_id: str) -> Tuple[bool, Dict]:
        """Toggle modbus device."""
        return await self._toggle_entity('modbus_device', entity_id)

    async def handle_toggle_device_metric(self, entity_id: str, metric: str) -> Tuple[bool, Dict]:
        """Toggle web device metric."""
        return await self._toggle_entity('web_metric', entity_id, metric)

    async def handle_toggle_modbus_metric(self, entity_id: str, metric: str) -> Tuple[bool, Dict]:
        """Toggle modbus device metric."""
        return await self._toggle_entity('modbus_metric', entity_id, metric)
