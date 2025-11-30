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

    def _get_category_for_device(self, device_type: str) -> str:
        """Determina la categoria appropriata basata sul device type"""
        device_type_upper = device_type.upper()

        # Mapping diretto device type -> categoria
        if device_type_upper == 'INVERTER':
            return 'Inverter'
        elif device_type_upper == 'METER':
            return 'Meter'
        elif device_type_upper == 'SITE':
            return 'Site'
        elif device_type_upper == 'STRING':
            return 'String'
        elif device_type_upper == 'WEATHER':
            return 'Weather'
        elif device_type_upper == 'OPTIMIZER':
            return 'Optimizer group'
        else:
            # Fallback per device types non riconosciuti
            return 'Site'

    def _create_device_endpoint(self, item, item_id, device_type, device_id, device_name):
        """Helper: crea configurazione endpoint per un dispositivo"""
        endpoint_key = f"{device_type.lower()}_{device_id}"

        # Determina la categoria basata sul device type
        device_category = self._get_category_for_device(device_type)

        # Converti device_id in stringa se necessario (per compatibilità YAML)
        device_id_str = str(device_id)

        # Determina se il device deve essere abilitato di default
        # OPTIMIZER, WEATHER e SITE sono abilitati, tutto il resto disabled
        default_enabled = device_type in ['OPTIMIZER', 'WEATHER', 'SITE']

        # Struttura endpoint con ordine preciso dei campi come nel file attuale
        endpoint = {}
        endpoint['device_id'] = device_id_str
        endpoint['device_name'] = device_name
        endpoint['device_type'] = device_type
        endpoint['enabled'] = default_enabled  # Solo OPTIMIZER e WEATHER abilitati di default
        endpoint['category'] = device_category  # Aggiungi categoria al device

        # Aggiungi date_range basato sul device type
        # OPTIMIZER e WEATHER supportano max 7 giorni, altri dispositivi supportano range mensili
        if device_type in ['OPTIMIZER', 'WEATHER']:
            endpoint['date_range'] = '7days'
        else:
            endpoint['date_range'] = 'monthly'

        # Gestione connessioni per OPTIMIZER e STRING (prima dei measurements)
        if device_type in ['OPTIMIZER', 'STRING']:
            connected_to = item_id.get('connectedToInverter', '')
            if connected_to:
                endpoint['inverter'] = connected_to
                self.logger.debug(f"    🔗 {device_type} {device_id} connesso a inverter: {connected_to}")
            else:
                self.logger.debug(f"    ⚠️  {device_type} {device_id} senza connectedToInverter")

        # Per STRING, usa identifier se disponibile (dopo inverter, prima measurements)
        if device_type == 'STRING':
            identifier = item_id.get('identifier', '')
            if identifier and identifier != '0':
                endpoint['identifier'] = identifier
                self.logger.debug(f"    🆔 {device_type} {device_id} ha identifier: {identifier}")

        # Measurements sempre per ultimo
        endpoint['measurements'] = {}
        if 'parameters' in item and item['parameters']:
            for param in item['parameters']:
                # Per SITE, abilita solo i measurement che contengono "ENERGY"
                if device_type == 'SITE':
                    measurement_enabled = 'ENERGY' in param
                else:
                    # Altri device: measurements abilitati solo se il device è abilitato
                    measurement_enabled = default_enabled

                endpoint['measurements'][param] = {'enabled': measurement_enabled}

        return endpoint_key, endpoint

    def _extract_device_from_item(self, item, endpoints):
        """Helper: estrae dispositivo da un item del snapshot"""
        if not isinstance(item, dict):
            return

        # Se ha itemId, è un dispositivo
        if 'itemId' in item:
            item_id = item['itemId']
            device_type = item_id.get('itemType', 'GENERIC')
            device_id_raw = item_id.get('id', f'{device_type.lower()}_default')
            device_name = item.get('name', f'{device_type}_{device_id_raw}')

            # Gestione speciale per device_id basata sul device_type
            if device_type == 'WEATHER':
                device_id = 'weather_default'
            else:
                device_id = device_id_raw

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
                    category = config.get('category', 'Info')
                    self.logger.info(f"  - {key}: {len(config['measurements'])} measurements (categoria: {category})")

            return endpoints

        except Exception as e:
            self.logger.error(f"ERRORE lettura snapshot web: {e}")
            return {}





    def _load_existing_config(self):
        """Carica configurazione esistente per preservare impostazioni enabled"""
        web_endpoints_path = self.root_dir / "config" / "sources" / "web_endpoints.yaml"

        if not web_endpoints_path.exists():
            return {}

        try:
            with open(web_endpoints_path, 'r', encoding='utf-8') as f:
                existing_config = yaml.safe_load(f)

            if isinstance(existing_config, dict) and 'web_scraping' in existing_config:
                endpoints = existing_config['web_scraping'].get('endpoints', {})
                self.logger.info(f"Caricata configurazione esistente con {len(endpoints)} endpoints")
                return endpoints
            else:
                return {}

        except Exception as e:
            self.logger.warning(f"Errore caricamento configurazione esistente: {e}")
            return {}

    def _merge_with_existing_config(self, new_endpoints, existing_endpoints):
        """Merge nuovi endpoints con configurazione esistente preservando enabled states"""
        merged_endpoints = {}

        for endpoint_key, new_endpoint in new_endpoints.items():
            if endpoint_key in existing_endpoints:
                # Preserva impostazioni enabled esistenti
                existing_endpoint = existing_endpoints[endpoint_key]

                # Copia la struttura nuova
                merged_endpoint = new_endpoint.copy()

                # Preserva enabled del device se esiste
                if 'enabled' in existing_endpoint:
                    merged_endpoint['enabled'] = existing_endpoint['enabled']

                # Preserva enabled dei measurements se esistono
                if 'measurements' in existing_endpoint and 'measurements' in merged_endpoint:
                    for measurement_name, new_measurement in merged_endpoint['measurements'].items():
                        if measurement_name in existing_endpoint['measurements']:
                            existing_measurement = existing_endpoint['measurements'][measurement_name]
                            if 'enabled' in existing_measurement:
                                new_measurement['enabled'] = existing_measurement['enabled']

                merged_endpoints[endpoint_key] = merged_endpoint
                self.logger.debug(f"Merged endpoint {endpoint_key} con configurazione esistente")
            else:
                # Nuovo endpoint, usa configurazione di default
                merged_endpoints[endpoint_key] = new_endpoint
                self.logger.debug(f"Nuovo endpoint {endpoint_key}")

        return merged_endpoints

    def save_web_endpoints_file(self, web_endpoints):
        """Salva solo il file web_endpoints.yaml preservando configurazioni esistenti"""
        try:
            web_endpoints_path = self.root_dir / "config" / "sources" / "web_endpoints.yaml"

            # Carica configurazione esistente
            existing_endpoints = self._load_existing_config()

            # Merge con configurazione esistente
            if existing_endpoints:
                web_endpoints = self._merge_with_existing_config(web_endpoints, existing_endpoints)
                self.logger.info("Configurazioni enabled preservate dalla versione esistente")

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

            # Se non ci sono endpoint (snapshot mancante), crea file vuoto ma valido
            if not web_endpoints:
                self.logger.warning("⚠️  Nessun endpoint trovato (snapshot mancante?)")
                self.logger.info("📝 Creando file web_endpoints.yaml vuoto ma valido...")
                web_endpoints = {}

            # Salva solo il file web_endpoints.yaml
            if self.save_web_endpoints_file(web_endpoints):
                if web_endpoints:
                    self.logger.info("✅ File web_endpoints.yaml generato con successo")
                    self.logger.info(f"  📊 Web endpoints: {len(web_endpoints)}")
                else:
                    self.logger.info("✅ File web_endpoints.yaml vuoto creato")
                    self.logger.info("  ℹ️  Esegui 'python main.py --scan' per rilevare i device")
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
