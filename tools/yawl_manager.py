#!/usr/bin/env python3
"""
Web Endpoints Manager: Gestore per la generazione del file web_endpoints.yaml
Focalizzato esclusivamente sulla gestione degli endpoint web scraping
"""

import yaml
import json
from pathlib import Path
from app_logging import get_logger

class YawlManager:
    """Manager per generazione file web_endpoints.yaml da scansione web tree"""

    def __init__(self):
        self.logger = get_logger(__name__)
        # Path del progetto
        self.root_dir = Path(__file__).resolve().parent.parent

    def _create_device_endpoint(self, item, item_id, device_type, device_id, device_name):
        """Helper: crea configurazione endpoint per un dispositivo"""
        endpoint_key = f"{device_type.lower()}_{device_id}"
        endpoint = {
            'enabled': False,
            'device_type': device_type,
            'device_id': device_id,
            'device_name': device_name,
            'measurements': {}
        }

        # Gestione connessioni per OPTIMIZER e STRING
        if device_type in ['OPTIMIZER', 'STRING']:
            connected_to = item_id.get('connectedToInverter', '')
            if connected_to:
                endpoint['inverter'] = connected_to
                self.logger.debug(f"    🔗 {device_type} {device_id} connesso a inverter: {connected_to}")
            else:
                self.logger.debug(f"    ⚠️  {device_type} {device_id} senza connectedToInverter")

            # Per STRING, usa identifier se disponibile
            if device_type == 'STRING':
                identifier = item_id.get('identifier', '')
                if identifier and identifier != '0':
                    endpoint['identifier'] = identifier
                    self.logger.debug(f"    🆔 {device_type} {device_id} ha identifier: {identifier}")

        # Converti parameters in measurements
        if 'parameters' in item and item['parameters']:
            for param in item['parameters']:
                endpoint['measurements'][param] = {'enabled': False}

        return endpoint_key, endpoint

    def _extract_device_from_item(self, item, endpoints):
        """Helper: estrae dispositivo da un item del snapshot"""
        if not isinstance(item, dict):
            return

        # Se ha itemId, è un dispositivo
        if 'itemId' in item:
            item_id = item['itemId']
            device_type = item_id.get('itemType', 'GENERIC')
            device_id = item_id.get('id', f'{device_type.lower()}_default')
            device_name = item.get('name', f'{device_type}_{device_id}')

            # Crea endpoint solo se ha parameters
            if 'parameters' in item and item['parameters']:
                endpoint_key, endpoint = self._create_device_endpoint(
                    item, item_id, device_type, device_id, device_name
                )
                endpoints[endpoint_key] = endpoint
                self.logger.debug(f"  Trovato dispositivo: {endpoint_key} con {len(item['parameters'])} parametri")

    def _extract_devices_recursive(self, item, endpoints):
        """Helper: estrae dispositivi ricorsivamente dalla struttura"""
        self._extract_device_from_item(item, endpoints)

        # Esplora children ricorsivamente
        if 'children' in item and isinstance(item['children'], list):
            for child in item['children']:
                self._extract_devices_recursive(child, endpoints)



    def get_web_endpoints(self):
        """Ottiene gli endpoint web dalle snapshot esistenti - COPIATO DA TEMPLATE MANAGER"""
        snapshot_path = self.root_dir / "cache" / "snapshots" / "web_tree" / "latest.json"

        if not snapshot_path.exists():
            self.logger.warning(f"Snapshot web non trovato in {snapshot_path}")
            return {}

        try:
            with open(snapshot_path, 'r', encoding='utf-8') as f:
                snapshot = json.load(f)

            self.logger.info(f"Snapshot caricato, chiavi principali: {list(snapshot.keys())}")

            # Estrai endpoint dai dispositivi nella struttura siteStructure
            endpoints = {}

            # Estrazione dispositivi dalla struttura usando helper methods
            if 'siteStructure' in snapshot:
                self._extract_devices_recursive(snapshot['siteStructure'], endpoints)

            # Controlla anche altre sezioni del snapshot per dispositivi
            for section_name in ['meters', 'storage', 'evChargers', 'smartHome', 'gateways']:
                if section_name in snapshot and isinstance(snapshot[section_name], list):
                    for item in snapshot[section_name]:
                        self._extract_devices_recursive(item, endpoints)

            # Gestione speciale per environmental che ha meteorologicalData
            if 'environmental' in snapshot and isinstance(snapshot['environmental'], dict):
                if 'meteorologicalData' in snapshot['environmental']:
                    self._extract_devices_recursive(snapshot['environmental']['meteorologicalData'], endpoints)

            self.logger.info(f"Trovati {len(endpoints)} endpoint web")
            if endpoints:
                self.logger.info("Endpoint web trovati:")
                for key, config in endpoints.items():
                    self.logger.info(f"  - {key}: {len(config['measurements'])} measurements")

            return endpoints

        except Exception as e:
            self.logger.error(f"ERRORE lettura snapshot web: {e}")
            return {}





    def save_web_endpoints_file(self, web_endpoints):
        """Salva solo il file web_endpoints.yaml"""
        try:
            web_endpoints_path = self.root_dir / "config" / "sources" / "web_endpoints.yaml"
            
            # Crea la struttura per web_endpoints.yaml
            web_config = {
                'web_scraping': {
                    'enabled': True,
                    'endpoints': web_endpoints
                }
            }
            
            # Assicurati che la directory esista
            web_endpoints_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(web_endpoints_path, 'w', encoding='utf-8') as f:
                yaml.dump(web_config, f, default_flow_style=False, allow_unicode=True, indent=2)
            
            self.logger.info(f"✅ File web_endpoints.yaml salvato: {web_endpoints_path}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Errore salvataggio file web_endpoints.yaml: {e}")
            return False

    def generate_web_endpoints_only(self):
        """Genera solo il file web_endpoints.yaml dalla scansione"""
        self.logger.info("📝 Iniziando generazione file web_endpoints.yaml...")

        try:
            # Carica web endpoints
            self.logger.info("🌐 Caricando web endpoints freschi...")
            web_endpoints = self.get_web_endpoints()

            # Salva solo il file web_endpoints.yaml
            if self.save_web_endpoints_file(web_endpoints):
                self.logger.info("✅ File web_endpoints.yaml generato con successo")
                self.logger.info(f"  📊 Web endpoints: {len(web_endpoints)}")
                return True
            else:
                self.logger.error("❌ Errore generazione file web_endpoints.yaml")
                return False

        except Exception as e:
            self.logger.error(f"❌ Errore generazione web_endpoints.yaml: {e}")
            return False

def main():
    """Funzione principale per esecuzione Web Endpoints Manager"""
    logger = get_logger("yawl_manager")
    logger.info("🚀 Web Endpoints Manager: Generazione file web_endpoints.yaml")

    try:
        # Crea Web Endpoints Manager
        ym = YawlManager()

        # Genera il file web_endpoints.yaml
        success = ym.generate_web_endpoints_only()

        if success:
            logger.info("✅ Web Endpoints Manager completato con successo")
            return True
        else:
            logger.error("❌ Web Endpoints Manager: errore generazione")
            return False

    except Exception as e:
        logger.error(f"❌ Errore critico: {e}")
        return False

if __name__ == "__main__":
    main()

__all__ = ["YawlManager"]
