# SolarEdge Data Collector

Sistema completo di raccolta, elaborazione e visualizzazione dati per impianti fotovoltaici SolarEdge con integrazione InfluxDB e Grafana.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows-lightgrey.svg)

## 📋 Indice

- [Caratteristiche](#-caratteristiche)
- [Architettura](#-architettura)
- [Requisiti](#-requisiti)
- [Installazione](#-installazione)
- [Configurazione](#-configurazione)
- [Utilizzo](#-utilizzo)
- [Dashboard Grafana](#-dashboard-grafana)
- [Documentazione](#-documentazione)
- [Troubleshooting](#-troubleshooting)

## ✨ Caratteristiche

### Raccolta Dati Multi-Sorgente
- **API Ufficiale SolarEdge**: Dati storici e aggregati (produzione, consumo, meter, inverter)
- **Web Scraping**: Dati dettagliati optimizer e pannelli (risoluzione 15 minuti)
- **Modbus TCP Realtime**: Telemetria in tempo reale dall'inverter (5 secondi)

### Elaborazione Intelligente
- **Pipeline Modulare**: Collector → Parser → Filter → Writer
- **Cache Avanzata**: Sistema di caching con TTL per ridurre chiamate API
- **Filtraggio Dati**: Validazione automatica e rimozione outlier
- **Gestione Errori**: Retry automatico e logging dettagliato

### Storage e Visualizzazione
- **InfluxDB 2.x**: Database time-series ottimizzato
- **Grafana**: Dashboard pre-configurate con metriche chiave
- **Retention Policy**: Gestione automatica ritenzione dati

### Modalità Operative
- **GUI Dashboard**: Interfaccia web per controllo e monitoraggio
- **Loop 24/7**: Raccolta automatica continua
- **History Mode**: Download storico completo con suddivisione mensile
- **Single Run**: Esecuzione singola per test e debug

## 🏗️ Architettura

```
┌─────────────────────────────────────────────────────────────┐
│                    SolarEdge Data Collector                  │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   API        │  │   Web        │  │   Modbus     │      │
│  │  Collector   │  │  Scraping    │  │   Realtime   │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │               │
│         └──────────────────┴──────────────────┘               │
│                            │                                  │
│                     ┌──────▼───────┐                         │
│                     │    Parser    │                         │
│                     │   + Filter   │                         │
│                     └──────┬───────┘                         │
│                            │                                  │
│                     ┌──────▼───────┐                         │
│                     │   InfluxDB   │                         │
│                     │    Writer    │                         │
│                     └──────┬───────┘                         │
│                            │                                  │
│         ┌──────────────────┴──────────────────┐              │
│         │                                      │              │
│  ┌──────▼───────┐                    ┌────────▼────────┐    │
│  │   InfluxDB   │                    │     Grafana     │    │
│  │   Database   │◄───────────────────┤    Dashboard    │    │
│  └──────────────┘                    └─────────────────┘    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Componenti Principali

#### Collectors
- `collector/collector_api.py`: Raccolta dati da API ufficiale SolarEdge
- `collector/collector_web.py`: Web scraping per dati optimizer
- `collector/collector_realtime.py`: Telemetria Modbus TCP in tempo reale

#### Parsers
- `parser/api_parser.py`: Parsing dati API → InfluxDB Points
- `parser/web_parser.py`: Parsing dati web → InfluxDB Points
- `parser/parser_realtime.py`: Parsing telemetria Modbus → InfluxDB Points

#### Storage
- `storage/writer_influx.py`: Scrittura batch su InfluxDB con retry

#### Utilities
- `cache/cache_manager.py`: Sistema di caching con TTL
- `filtro/regole_filtraggio.py`: Validazione e filtraggio dati
- `scheduler/scheduler_loop.py`: Gestione timing e rate limiting
- `gui/simple_web_gui.py`: Dashboard web di controllo

## 📦 Requisiti

### Sistema
- **OS**: Linux (Debian/Ubuntu consigliato) o Windows
- **Python**: 3.11+
- **RAM**: 512MB minimo, 1GB consigliato
- **Disco**: 10GB per dati storici

### Software
- **InfluxDB**: 2.x
- **Grafana**: 10.x+
- **Docker** (opzionale): Per deployment containerizzato

### Credenziali SolarEdge
- API Key (da portale SolarEdge)
- Site ID
- Username/Password per web scraping
- IP inverter per Modbus (opzionale)

## 🚀 Installazione

### Metodo 1: Installazione One-Liner (Raccomandato)

**Con password di default:**
```bash
curl -sSL https://raw.githubusercontent.com/frezeen/Solaredge_ScanWriter/main/install.sh | sudo bash
```

**Con password personalizzate (consigliato):**
```bash
# Scarica lo script
curl -sSL https://raw.githubusercontent.com/frezeen/Solaredge_ScanWriter/main/install.sh -o install.sh

# Esegui (ti chiederà le password)
sudo bash install.sh
```

Lo script installa automaticamente:
- ✅ Dipendenze Python system-wide
- ✅ InfluxDB 2.x (porta 8086)
- ✅ Grafana con plugin (porta 3000)
- ✅ Configurazione iniziale (.env)
- ✅ Servizio systemd
- ✅ Dashboard Grafana pre-configurate
- ✅ Log rotation e cleanup automatico
- ✅ Formati data italiani in Grafana

**Password di default:**
- InfluxDB: `admin` / `solaredge123`
- Grafana: `admin` / `admin` (cambiale al primo accesso)

### Metodo 2: Installazione Manuale

```bash
# 1. Clone repository
git clone https://github.com/frezeen/Solaredge_ScanWriter.git
cd Solaredge_ScanWriter

# 2. Configura permessi automaticamente (RACCOMANDATO)
chmod +x setup-permissions.sh
./setup-permissions.sh

# 3. Installa dipendenze
pip3 install -r requirements.txt --break-system-packages

# 4. Copia e configura .env
cp .env.example .env
nano .env

# 5. Installa InfluxDB e Grafana manualmente
# Vedi sezione "Installazione Servizi" sotto
```

### Metodo 3: Installazione Docker

```bash
# Build e avvio con docker-compose
docker-compose up -d

# Verifica servizi
docker-compose ps

# Log
docker-compose logs -f solaredge
```

### Installazione Servizi (Manuale)

#### InfluxDB 2.x

```bash
# Aggiungi repository
curl -s https://repos.influxdata.com/influxdata-archive_compat.key | gpg --dearmor -o /usr/share/keyrings/influxdata-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/influxdata-archive-keyring.gpg] https://repos.influxdata.com/debian stable main" | tee /etc/apt/sources.list.d/influxdb.list

# Installa
apt-get update
apt-get install -y influxdb2

# Avvia
systemctl enable influxdb
systemctl start influxdb

# Setup iniziale (http://localhost:8086)
# Org: fotovoltaico
# Bucket: Solaredge
# Bucket Realtime: Solaredge_Realtime (retention 2 giorni)
```

#### Grafana

```bash
# Aggiungi repository
curl -s https://packages.grafana.com/gpg.key | gpg --dearmor -o /usr/share/keyrings/grafana-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/grafana-archive-keyring.gpg] https://packages.grafana.com/oss/deb stable main" | tee /etc/apt/sources.list.d/grafana.list

# Installa
apt-get update
apt-get install -y grafana

# Installa plugin
grafana-cli plugins install fetzerch-sunandmoon-datasource
grafana-cli plugins install grafana-clock-panel

# Avvia
systemctl enable grafana-server
systemctl start grafana-server

# Accedi: http://localhost:3000 (admin/admin)
```

### Post-Installazione

#### 1. Configura Credenziali SolarEdge
```bash
nano /opt/Solaredge_ScanWriter/.env
```

Parametri obbligatori:
```bash
SOLAREDGE_SITE_ID=123456
SOLAREDGE_USERNAME=your.email@example.com
SOLAREDGE_PASSWORD=your_password
SOLAREDGE_API_KEY=your_api_key

INFLUXDB_TOKEN=your_influxdb_token
```

#### 2. Test Installazione
```bash
cd /opt/Solaredge_ScanWriter
./test.sh  # Script creato automaticamente dall'installer
```

**Nota**: Gli script `test.sh` e `status.sh` vengono creati automaticamente dall'installer.

#### 3. Avvia Servizio
```bash
sudo systemctl enable --now solaredge-scanwriter
```

#### 4. Importa Dashboard Grafana

1. Accedi a Grafana: `http://localhost:3000` (admin/admin)
2. Vai su **"+" → Import**
3. Upload file: `/opt/Solaredge_ScanWriter/grafana/dashboard-solaredge.json`
4. Clicca **"Import"**

## ⚙️ Configurazione

### Struttura Configurazione

Il progetto usa una configurazione modulare suddivisa in file separati:

```
config/
├── main.yaml                    # Configurazione principale
├── sources/                     # Configurazioni sorgenti dati
│   ├── api_endpoints.yaml      # 22 endpoint API SolarEdge
│   ├── web_endpoints.yaml      # 21 device web scraping
│   └── modbus_endpoints.yaml   # Endpoint Modbus realtime
└── .env                         # Credenziali (root directory)
```

**Vantaggi:**
- ✅ File più piccoli e gestibili
- ✅ Separazione logica per tipo di sorgente
- ✅ Meno conflitti Git
- ✅ Facile trovare e modificare configurazioni

### File Principali

#### `.env` - Credenziali e Parametri (Root Directory)
```bash
# SolarEdge API
SOLAREDGE_API_KEY=your_api_key_here
SOLAREDGE_SITE_ID=123456
SOLAREDGE_USERNAME=your.email@example.com
SOLAREDGE_PASSWORD=your_password

# Modbus Realtime
REALTIME_MODBUS_HOST=192.168.1.100
REALTIME_MODBUS_PORT=1502
MODBUS_ENABLED=true

# InfluxDB
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=your_influxdb_token
INFLUXDB_ORG=fotovoltaico
INFLUXDB_BUCKET=Solaredge
INFLUXDB_BUCKET_REALTIME=Solaredge_Realtime

# Intervalli Loop
LOOP_API_INTERVAL_MINUTES=15
LOOP_WEB_INTERVAL_MINUTES=15
LOOP_REALTIME_INTERVAL_SECONDS=5

# GUI
GUI_HOST=127.0.0.1
GUI_PORT=8092
```

#### `config/main.yaml` - Configurazione Avanzata
```yaml
logging:
  level: INFO
  log_directory: logs
  file_logging: true

scheduler:
  api_delay_seconds: 1
  web_delay_seconds: 2
  realtime_delay_seconds: 0

cache:
  enabled: true
  ttl_seconds: 900
```

#### `config/sources/api_endpoints.yaml` - Endpoint API (22 endpoint)

Configura quali endpoint API abilitare. Ogni endpoint include:
- `enabled`: Abilitazione endpoint
- `endpoint`: URL endpoint
- `method`: Metodo HTTP
- `parameters`: Parametri richiesta
- `extraction`: Regole estrazione dati
- `category`: Tipo dati (Info, Inverter, Meter, Flusso)

**Esempio:**
```yaml
api_ufficiali:
  enabled: true
  endpoints:
    site_energy_details:
      enabled: true
      category: Meter
      endpoint: /site/{siteId}/energyDetails
      method: GET
      parameters:
        meters: PRODUCTION,CONSUMPTION,SELFCONSUMPTION,FEEDIN,PURCHASED
        timeUnit: QUARTER_OF_AN_HOUR
      extraction:
        time_field: date
        unit: Wh
        value_field: value
        values_path: energyDetails.meters[].values
      description: "Dettagli energia con granularità 15 minuti"
```

**Abilitare/Disabilitare endpoint:**

⚠️ **Importante**: Non modificare i file YAML manualmente! Usa la GUI Dashboard per gestire gli endpoint.

```bash
# Avvia la GUI
python main.py

# Accedi a: http://localhost:8092
# Sezione: "API Endpoints" → Toggle on/off per ogni endpoint
```

Se proprio necessario modificare manualmente:
```yaml
site_overview:
  enabled: false  # ← Disabilita questo endpoint
```

#### `config/sources/web_endpoints.yaml` - Optimizer Web (Auto-generato)

**Nota**: Questo file è specifico per il tuo impianto e non è incluso nel repository. Devi generarlo con il comando scan.

**Prima configurazione:**
```bash
# Genera automaticamente la configurazione
python main.py --scan
```

Configurazione device web scraping. Ogni device include:
- `device_id`: ID univoco device
- `device_name`: Nome descrittivo
- `device_type`: Tipo (Inverter, Meter, Optimizer, Site, Weather)
- `measurements`: Metriche da raccogliere

**Esempio:**
```yaml
web_scraping:
  enabled: true
  endpoints:
    optimizer_21830A42-F0:
      enabled: true
      device_id: 21830A42-F0
      device_name: Optimizer 1.0.11
      device_type: OPTIMIZER
      inverter: 7403D7C5-13
      measurements:
        PRODUCTION_POWER:
          enabled: true
        MODULE_CURRENT:
          enabled: true
```

**Configurazione automatica tramite scan (Raccomandato):**

```bash
# Prima configurazione - genera web_endpoints.yaml
python main.py --scan
```

**Cosa fa il comando scan:**
1. 🔍 **Scansiona** il portale web SolarEdge (monitoring.solaredge.com)
2. 🔎 **Rileva automaticamente** tutti i device del tuo impianto:
   - Inverter (con serial number e modello)
   - Optimizer (tutti i pannelli con ID univoci)
   - Meter (contatori import/export)
   - Sensori meteo (se presenti)
3. 📝 **Genera** il file `config/sources/web_endpoints.yaml` con configurazione completa
4. ✅ **Abilita** automaticamente tutte le metriche disponibili

**Quando usare il comando scan:**
- ✅ Prima installazione (per generare la configurazione iniziale)
- ✅ Dopo aggiunta/sostituzione di optimizer o device
- ✅ Per aggiornare la configurazione dopo modifiche hardware

**Requisiti:**
- Credenziali web SolarEdge configurate in `.env`:
  ```bash
  SOLAREDGE_USERNAME=your.email@example.com
  SOLAREDGE_PASSWORD=your_password
  SOLAREDGE_SITE_ID=123456
  ```

**Output esempio:**
```
🔍 Modalità scan: scansione web tree
🌐 Login al portale SolarEdge...
✅ Login effettuato con successo
📊 Scansione device in corso...
   ✓ Trovato inverter: 7403D7C5-13
   ✓ Trovati 16 optimizer
   ✓ Trovato meter: 606483640
📝 Aggiornando file web_endpoints.yaml...
✅ File web_endpoints.yaml aggiornato
```

**Nota**: Il file generato è specifico per il tuo impianto e non viene committato su Git (è in `.gitignore`)

#### `config/sources/modbus_endpoints.yaml` - Modbus Realtime

Configurazione endpoint Modbus TCP per telemetria in tempo reale:
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

## 🎯 Utilizzo

### 🌐 GUI Dashboard - Interfaccia Web

La GUI Dashboard è l'interfaccia principale per gestire il sistema. Offre 5 sezioni principali:

#### 1. **Device Web Scraping** 🔌
Gestisci i dispositivi rilevati dal portale SolarEdge:
- Toggle on/off per ogni device (Inverter, Optimizer, Meter, Weather)
- Abilita/disabilita metriche specifiche per device
- Modifica `config/sources/web_endpoints.yaml` tramite interfaccia

#### 2. **API Endpoints** 🌐
Configura gli endpoint dell'API REST SolarEdge:
- Filtra per categoria: Info, Inverter, Meter, Flusso
- Toggle on/off per ogni endpoint
- Visualizza descrizione e parametri endpoint
- Modifica `config/sources/api_endpoints.yaml` tramite interfaccia

#### 3. **Modbus Realtime** ⚡
Gestisci la telemetria in tempo reale:
- Toggle device Modbus
- Abilita/disabilita metriche specifiche
- Modifica `config/sources/modbus_endpoints.yaml` tramite interfaccia

#### 4. **Loop Monitor** 🔄
Controlla il loop di raccolta dati:
- **Start/Stop** loop con un click
- Visualizza statistiche in tempo reale (API, Web, Realtime)
- Log live con filtri per tipo (info, warning, error)
- Cronologia esecuzioni con successi/fallimenti

#### 5. **YAML Config** ⚙️
Editor configurazioni avanzato:
- Visualizza e modifica file YAML direttamente
- Syntax highlighting
- Validazione automatica
- Salvataggio con backup automatico

**Accesso GUI:**
```bash
# Avvia
python main.py

# Accedi da browser
http://localhost:8092

# Accesso da rete locale (se firewall permette)
http://[IP_SERVER]:8092
```

### Setup Iniziale - Prima Esecuzione

Prima di avviare il sistema, devi generare la configurazione web:

```bash
# 1. Configura credenziali in .env
nano /opt/Solaredge_ScanWriter/.env

# 2. Genera configurazione web_endpoints.yaml
python main.py --scan

# 3. Verifica che il file sia stato creato
ls -la config/sources/web_endpoints.yaml
```

**Importante**: Il comando `--scan` è necessario solo la prima volta o dopo modifiche hardware all'impianto.

### GUI Dashboard (Consigliato)

```bash
# Avvia GUI con loop automatico
python main.py

# Accedi a: http://localhost:8092
```

La GUI permette di:
- ✅ **Gestire Device Web Scraping**: Toggle on/off device e metriche
- ✅ **Configurare API Endpoints**: Abilitare/disabilitare endpoint per categoria
- ✅ **Gestire Modbus Realtime**: Configurare device e metriche Modbus
- ✅ **Controllare Loop**: Avviare/fermare il loop di raccolta dati
- ✅ **Monitorare in Tempo Reale**: Statistiche, log live, stato esecuzioni
- ✅ **Editare YAML**: Visualizzare e modificare configurazioni direttamente

**⚠️ Importante**: Usa sempre la GUI per modificare le configurazioni YAML. Le modifiche manuali possono causare errori di sintassi.

### Modalità Command Line

#### Single Run - Test e Debug
```bash
# Solo API
python main.py --api

# Solo Web Scraping
python main.py --web

# Solo Realtime
python main.py --realtime

# Scan optimizer (aggiorna config web)
python main.py --scan
```

#### History Mode - Download Storico
```bash
# Scarica tutto lo storico disponibile
python main.py --history

# Suddivide automaticamente per mesi
# Usa cache per evitare duplicati
# Interrompibile con Ctrl+C (riprende dal punto di interruzione)
```

#### Loop 24/7 - Produzione
```bash
# Avvio manuale
python main.py

# Oppure con systemd (dopo install.sh)
sudo systemctl start solaredge-scanwriter
sudo systemctl enable solaredge-scanwriter

# Verifica stato
sudo systemctl status solaredge-scanwriter

# Log
sudo journalctl -u solaredge-scanwriter -f
```

### Docker

```bash
# Avvio
docker-compose up -d

# Log
docker-compose logs -f solaredge

# Stop
docker-compose down
```

## 📊 Dashboard Grafana

### Accesso
- URL: `http://localhost:3000`
- User: `admin`
- Password: configurata durante install

### Dashboard Pre-Configurate

Il sistema include dashboard complete con:

#### Metriche Principali
- 📈 Produzione totale (giornaliera, mensile, annuale, lifetime)
- 🏠 Consumo e autoconsumo
- ⚡ Prelievo e immissione rete
- 💰 Calcoli economici SSP (Scambio Sul Posto)
- 🌍 Emissioni CO2 evitate

#### Grafici Avanzati
- 📊 Produzione mensile storica per anno (barre raggruppate)
- 🔥 Heatmap produzione giornaliera
- ⚡ Potenza optimizer in tempo reale
- 📉 Trend e confronti anno su anno
- 🎯 Percentuali autoconsumo e prelievo

#### Telemetria Inverter
- 🌡️ Temperatura
- ⚡ Tensioni AC/DC
- 📊 Potenze attiva/reattiva/apparente
- 🔌 Correnti per fase
- ⚙️ Stato operativo

### Query Flux Personalizzate

Esempi di query disponibili nella documentazione:
- `docs/api_endpoints_reference.md`: Query per dati API
- `docs/web_endpoints_reference.md`: Query per dati optimizer
- `docs/realtime_endpoints_reference.md`: Query per telemetria

## 📚 Documentazione

### Guide Installazione
- `docs/retention_policy_setup.md`: Configurazione retention InfluxDB
- Questo README contiene tutte le informazioni per installazione e configurazione

### Reference API
- `docs/api_endpoints_reference.md`: Tutti gli endpoint API con esempi query
- `docs/web_endpoints_reference.md`: Struttura dati web scraping
- `docs/realtime_endpoints_reference.md`: Registri Modbus e telemetria

### Manutenzione
- `docs/UPDATE_SYSTEM.md`: Procedura aggiornamento sistema
- `scripts/cleanup_logs.sh`: Pulizia log automatica
- `scripts/smart_update.py`: Update intelligente con backup

## 🔧 Troubleshooting

### Problemi Comuni

#### InfluxDB non risponde
```bash
# Verifica servizio
sudo systemctl status influxdb

# Restart
sudo systemctl restart influxdb

# Log
sudo journalctl -u influxdb -f
```

#### Grafana non mostra dati
1. Verifica data source InfluxDB in Grafana
2. Controlla token e bucket name
3. Testa query manualmente in InfluxDB UI

#### API Rate Limit
- Limite: 300 richieste/giorno per site
- Soluzione: Usa cache (già abilitata di default)
- Verifica: `cache/api_ufficiali/` per file cached

#### Web Scraping fallisce
```bash
# 1. Verifica che web_endpoints.yaml esista
ls -la config/sources/web_endpoints.yaml

# 2. Se manca, genera la configurazione
python main.py --scan

# 3. Rigenera cookie se login fallisce
rm cookies/web_cookies.json

# 4. Verifica credenziali in .env
nano .env

# 5. Test login
python main.py --web
```

**Errore comune**: `FileNotFoundError: config/sources/web_endpoints.yaml`
- **Causa**: File di configurazione web non generato
- **Soluzione**: Esegui `python main.py --scan` per generarlo

#### Modbus non connette
```bash
# Verifica IP inverter
ping 192.168.1.100

# Test porta Modbus
telnet 192.168.1.100 1502

# Abilita Modbus su inverter (vedi manuale SolarEdge)
```

### Log e Debug

```bash
# Log applicazione
tail -f logs/main/app.log

# Log systemd
sudo journalctl -u solaredge-scanwriter -f

# Debug mode
LOG_LEVEL=DEBUG python main.py --api
```

### Backup e Restore

```bash
# Backup configurazione
./scripts/smart_update.py --backup

# Backup InfluxDB
influx backup /path/to/backup -t your_token

# Restore
influx restore /path/to/backup -t your_token
```

### Aggiornamenti

```bash
# Metodo 1: Script automatico (raccomandato)
cd /opt/Solaredge_ScanWriter
./update.sh

# Metodo 2: Manuale
sudo systemctl stop solaredge-scanwriter
cd /opt/Solaredge_ScanWriter
git pull
pip3 install -r requirements.txt --upgrade --break-system-packages
sudo systemctl start solaredge-scanwriter
```

Lo script `update.sh`:
- ✅ Backup automatico configurazione
- ✅ Pull da GitHub
- ✅ Aggiornamento dipendenze
- ✅ Risoluzione conflitti automatica
- ✅ Restart servizio

### Permessi e Sicurezza

#### Configurazione Permessi Automatica

Il progetto include un sistema per mantenere automaticamente i permessi:

```bash
# Dopo il clone, esegui UNA VOLTA:
./setup-permissions.sh
```

Questo configura:
- ✅ Permessi di esecuzione su tutti gli script
- ✅ Git hooks per ripristino automatico dopo `git pull`
- ✅ Configurazione Git ottimale

**Risultato**: Non dovrai più fare `chmod +x` manualmente!

#### Firewall

```bash
# Abilita firewall
ufw enable

# Permetti GUI
ufw allow 8092/tcp

# Permetti Grafana (se accesso remoto)
ufw allow 3000/tcp

# Permetti InfluxDB (se accesso remoto)
ufw allow 8086/tcp

# Permetti SSH
ufw allow ssh
```

#### Permessi File

```bash
# Verifica permessi
ls -la /opt/Solaredge_ScanWriter/

# Correggi se necessario
chown -R solaredge:solaredge /opt/Solaredge_ScanWriter/
chmod 600 /opt/Solaredge_ScanWriter/.env
```

## 🤝 Contributi

Contributi benvenuti! Per favore:
1. Fork del repository
2. Crea feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Apri Pull Request

## 📝 License

Questo progetto è rilasciato sotto licenza MIT. Vedi `LICENSE` per dettagli.

## 🙏 Ringraziamenti

- SolarEdge per le API ufficiali
- Community InfluxDB e Grafana
- Contributori del progetto

## 📧 Supporto

- **Issues**: [GitHub Issues](https://github.com/frezeen/Solaredge_ScanWriter/issues)
- **Discussions**: [GitHub Discussions](https://github.com/frezeen/Solaredge_ScanWriter/discussions)
- **Email**: [Contatta il maintainer]

---

**Made with ❤️ for the Solar Community**
