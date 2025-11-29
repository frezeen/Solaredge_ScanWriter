"""delete_web_measurement.py
Script per cancellare il measurement 'web' dal bucket InfluxDB.

ATTENZIONE: Questa operazione è IRREVERSIBILE!
"""
import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from influxdb_client import InfluxDBClient
from influxdb_client.client.delete_api import DeleteApi


def delete_web_measurement():
    """Cancella il measurement 'web' dal bucket Solaredge."""
    
    # Carica configurazione da .env
    url = os.environ.get('INFLUXDB_URL')
    token = os.environ.get('INFLUXDB_TOKEN')
    org = os.environ.get('INFLUXDB_ORG')
    bucket = os.environ.get('INFLUXDB_BUCKET')
    
    if not all([url, token, org, bucket]):
        print("[X] Errore: Variabili ambiente InfluxDB mancanti")
        print("[i] Assicurati che .env sia caricato correttamente")
        return False
    
    print(f"[i] Connessione a InfluxDB: {url}")
    print(f"[i] Bucket: {bucket}")
    print(f"[i] Organization: {org}")
    print()
    
    # Conferma utente
    print("[!] ATTENZIONE: Stai per cancellare TUTTI i dati del measurement 'web'")
    print("[!] Questa operazione e' IRREVERSIBILE!")
    print()
    response = input("Sei sicuro di voler procedere? Digita 'CANCELLA' per confermare: ")
    
    if response != 'CANCELLA':
        print("[i] Operazione annullata dall'utente")
        return False
    
    print()
    print("[>>>] Cancellazione in corso...")
    
    try:
        # Crea client InfluxDB
        with InfluxDBClient(url=url, token=token, org=org) as client:
            delete_api = client.delete_api()
            
            # Definisci il range temporale (dal 1970 a oggi + 1 giorno per sicurezza)
            start = "1970-01-01T00:00:00Z"
            stop = datetime.now().strftime("%Y-%m-%dT23:59:59Z")
            
            # Predicate per cancellare solo il measurement 'web'
            predicate = '_measurement="web"'
            
            print(f"[i] Range temporale: {start} -> {stop}")
            print(f"[i] Predicate: {predicate}")
            print()
            
            # Esegui cancellazione
            delete_api.delete(
                start=start,
                stop=stop,
                predicate=predicate,
                bucket=bucket,
                org=org
            )
            
            print("[OK] Measurement 'web' cancellato con successo!")
            print()
            print("[i] Verifica la cancellazione con una query InfluxDB:")
            print(f'    from(bucket: "{bucket}") |> range(start: -30d) |> filter(fn: (r) => r._measurement == "web")')
            
            return True
            
    except Exception as e:
        print(f"[X] Errore durante la cancellazione: {e}")
        return False


if __name__ == "__main__":
    # Carica .env se disponibile
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent.parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            print("[OK] File .env caricato")
            print()
    except ImportError:
        print("[!] python-dotenv non disponibile, assicurati che le variabili ambiente siano impostate")
        print()
    
    success = delete_web_measurement()
    sys.exit(0 if success else 1)
