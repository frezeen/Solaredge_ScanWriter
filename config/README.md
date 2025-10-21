# 📁 Struttura Configurazione

La configurazione del progetto è suddivisa in file separati per migliorare manutenibilità e organizzazione.

## 📂 Struttura File

```
config/
├── main.yaml                    # Configurazione principale (55 righe)
├── sources/                     # Configurazioni sorgenti dati
│   ├── api_endpoints.yaml      # Endpoint API ufficiali SolarEdge (22 endpoint)
│   ├── web_endpoints.yaml      # Endpoint web scraping (21 device)
│   └── modbus_endpoints.yaml   # Endpoint Modbus TCP realtime (1 endpoint)
├── main.yaml.backup             # Backup file originale completo
└── README.md                    # Questa documentazione
```

## 📋 File Principali

### `main.yaml` (55 righe)
Configurazione base del sistema:
- **global**: Configurazioni globali (site_id, timeout, timezone)
- **influxdb**: Configurazione database InfluxDB
- **logging**: Configurazione logging
- **scheduler**: Configurazione scheduler (intervalli raccolta dati)
- **solaredge**: Configurazione connessioni SolarEdge (API, Web, Modbus)
- **workflow**: Metadata workflow
- **sources**: Placeholder (caricato da file separati)

### `sources/api_endpoints.yaml` (~400 righe)
Configurazione endpoint API ufficiali SolarEdge:
- 22 endpoint API configurati
- Categorie: Info, Inverter, Meter, Flusso
- Ogni endpoint include:
  - `enabled`: Abilitazione endpoint
  - `endpoint`: URL endpoint
  - `method`: Metodo HTTP
  - `parameters`: Parametri richiesta
  - `extraction`: Regole estrazione dati
  - `description`: Descrizione funzionalità

**Esempio:**
```yaml
api_ufficiali:
  enabled: true
  endpoints:
    site_overview:
      enabled: true
      endpoint: /site/{siteId}/overview
      method: GET
      category: Info
      data_format: raw_json
      description: "Panoramica corrente del sito..."
```

### `sources/web_endpoints.yaml` (~400 righe)
Configurazione endpoint web scraping:
- 21 device configurati (inverter, meter, optimizer, site, weather)
- Ogni device include:
  - `enabled`: Abilitazione device
  - `device_id`: ID univoco device
  - `device_name`: Nome descrittivo
  - `device_type`: Tipo device (Inverter, Meter, Optimizer, etc.)
  - `measurements`: Metriche da raccogliere

**Esempio:**
```yaml
web_scraping:
  enabled: true
  endpoints:
    inverter_7403D7C5-13:
      enabled: true
      device_id: 7403D7C5-13
      device_name: Inverter 1
      device_type: Inverter
      measurements:
        AC_PRODUCTION_POWER:
          enabled: true
```

### `sources/modbus_endpoints.yaml` (~13 righe)
Configurazione endpoint Modbus TCP realtime:
- 1 endpoint configurato (inverter realtime)
- Raccolta dati in tempo reale via protocollo Modbus

**Esempio:**
```yaml
modbus:
  enabled: true
  endpoints:
    inverter_realtime:
      enabled: true
      device_id: ${MODBUS_UNIT}
      device_name: Inverter Modbus
      device_type: Inverter
```

## 🔧 Come Funziona

### Caricamento Automatico
Il `ConfigManager` carica automaticamente tutti i file:

```python
from config.config_manager import get_config_manager

# Carica configurazione completa (main.yaml + sources/)
config_manager = get_config_manager()

# Accedi alle configurazioni
global_config = config_manager.get_global_config()
sources = config_manager.get_raw_config()['sources']
```

### Ordine di Caricamento
1. Carica `main.yaml`
2. Sostituisce variabili d'ambiente (`${VAR_NAME}`)
3. Carica file da `sources/` (se esistono)
4. Merge delle configurazioni sources in `main.yaml`

### Fallback
Se la cartella `sources/` non esiste, il sistema usa la sezione `sources` da `main.yaml` (backward compatibility).

## ✏️ Modificare la Configurazione

### Abilitare/Disabilitare Endpoint API
Modifica `sources/api_endpoints.yaml`:
```yaml
api_ufficiali:
  endpoints:
    site_overview:
      enabled: false  # ← Disabilita questo endpoint
```

### Aggiungere Nuovo Device Web
Modifica `sources/web_endpoints.yaml`:
```yaml
web_scraping:
  endpoints:
    nuovo_device:
      enabled: true
      device_id: "12345"
      device_name: "Nuovo Device"
      device_type: "Meter"
      measurements:
        POWER:
          enabled: true
```

### Modificare Configurazioni Base
Modifica `main.yaml`:
```yaml
scheduler:
  api_delay_seconds: 2.0  # ← Cambia intervallo API
  realtime_delay_seconds: 1.0  # ← Cambia intervallo realtime
```

## 🔄 Ricarica Configurazione

Per ricaricare la configurazione senza riavviare:
```python
config_manager.reload()
```

## 📊 Vantaggi della Suddivisione

✅ **Manutenibilità**: File più piccoli e gestibili  
✅ **Organizzazione**: Separazione logica per tipo di sorgente  
✅ **Performance**: Parsing più veloce di file YAML più piccoli  
✅ **Collaborazione**: Meno conflitti Git, review più facili  
✅ **Chiarezza**: Facile trovare e modificare configurazioni specifiche  

## 🔙 Ripristino File Originale

Se necessario, ripristina il file originale completo:
```bash
cp config/main.yaml.backup config/main.yaml
rm -rf config/sources/
```

## 📝 Note

- Tutti i file YAML supportano sostituzione variabili d'ambiente: `${VAR_NAME}`
- Le variabili sono definite nel file `.env`
- I file in `sources/` sono opzionali (fallback su `main.yaml`)
- Il backup originale è in `config/main.yaml.backup`
