# ⚡ SolarEdge ScanWriter

**Sistema completo di monitoraggio per impianti fotovoltaici SolarEdge**

Raccogli, analizza e visualizza i dati del tuo impianto fotovoltaico con dashboard Grafana professionali. Gestione semplice tramite interfaccia web, nessuna configurazione manuale richiesta.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows-lightgrey.svg)

## � Indice

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

### 🔄 Raccolta Dati Multi-Sorgente Completa

**22 Endpoint API Ufficiali SolarEdge**
- 📊 **Produzione Energetica**: Dati giornalieri, orari e 15-minutali con storico completo
- 🏠 **Bilancio Energetico**: Produzione, consumo, autoconsumo, prelievo e immissione rete
- ⚡ **Telemetria Inverter**: Tensioni AC/DC, correnti, frequenza, temperatura, modalità operative
- 🔋 **Sistema Storage**: Stato batterie, energia caricata/scaricata, capacità e cicli
- 🌍 **Impatto Ambientale**: CO2 evitata, equivalente alberi piantati, benefici sostenibilità
- 📋 **Inventario Hardware**: Lista completa inverter, contatori, sensori con dettagli tecnici

**Web Scraping Avanzato (Risoluzione 15 minuti)**
- 🔧 **Optimizer Individuali**: Performance di ogni singolo pannello fotovoltaico
- 🌡️ **Sensori Ambientali**: Irradianza, temperatura ambiente, velocità vento
- 📈 **Curve di Produzione**: Analisi dettagliata prestazioni per ottimizzazione impianto
- 🔍 **Diagnostica Avanzata**: Identificazione pannelli sottoperformanti o guasti

**Modbus TCP Realtime (5 secondi)**
- ⚡ **Telemetria Live**: Potenza istantanea, tensioni, correnti in tempo reale
- 🌡️ **Monitoraggio Termico**: Temperature inverter, dissipatori, componenti critici
- 🔧 **Stato Operativo**: Modalità funzionamento, allarmi, controlli di sicurezza
- 📊 **Metriche Performance**: Efficienza conversione, fattore di potenza, THD

### 🧠 Elaborazione Intelligente e Affidabile

**Pipeline Modulare Robusta**
- 🔄 **Architettura Scalabile**: Collector → Parser → Filter → Writer per massima flessibilità
- 🛡️ **Validazione Dati**: Controllo automatico range, rimozione outlier, sanity check
- 🔄 **Retry Intelligente**: Gestione automatica errori temporanei e rate limiting
- 📝 **Logging Dettagliato**: Tracciabilità completa per debugging e monitoraggio

**Sistema Cache Avanzato**
- ⚡ **Performance Ottimizzate**: TTL intelligente per ridurre chiamate API del 90%
- 💾 **Persistenza Dati**: Cache su disco per sopravvivere a riavvii sistema
- 🔄 **Invalidazione Smart**: Aggiornamento automatico solo quando necessario
- 📊 **Statistiche Cache**: Monitoraggio hit/miss ratio per ottimizzazione

### 📊 Storage e Visualizzazione Professionale

**Database Time-Series InfluxDB 2.x**
- ⚡ **Performance Elevate**: Ottimizzato per milioni di punti dati temporali
- 🗜️ **Compressione Avanzata**: Riduzione spazio disco fino al 95%
- 🔄 **Retention Policy**: Gestione automatica lifecycle dati (alta risoluzione → aggregati)
- 🔍 **Query Potenti**: Flux query language per analisi complesse

**Dashboard Grafana Pre-Configurate**
- 📈 **Metriche Chiave**: Produzione, consumo, autoconsumo, bilancio energetico
- 💰 **Calcoli Economici**: ROI, risparmio SSP, costi energia, payback period
- 🌍 **Impatto Ambientale**: CO2 evitata, equivalente combustibili fossili
- 📊 **Analisi Storiche**: Trend mensili, heatmap giornaliere, confronti annuali
- ⚡ **Monitoraggio Realtime**: Potenza istantanea, stato inverter, allarmi
- 🔧 **Diagnostica Optimizer**: Performance individuali pannelli, identificazione guasti

### 🎛️ Modalità Operative Flessibili

**GUI Dashboard Web Intuitiva**
- 🖥️ **Controllo Centralizzato**: Start/stop processi, configurazione endpoint, monitoraggio live
- 📝 **Editor Configurazione**: Syntax highlighting per modifiche YAML in tempo reale
- 📊 **Statistiche Live**: Contatori richieste, errori, performance cache
- 🔧 **Gestione Device**: Abilitazione/disabilitazione singoli endpoint e sensori

**Automazione 24/7 Completa**
- 🔄 **Loop Continuo**: Raccolta automatica senza intervento manuale
- 🛡️ **Resilienza Errori**: Continua operazioni anche con fallimenti parziali
- 📅 **Scheduling Intelligente**: Rispetto rate limit API, ottimizzazione orari
- 🔄 **Auto-Recovery**: Riavvio automatico processi in caso di problemi

**History Mode Professionale**
- 📜 **Download Completo**: Scarica tutto lo storico disponibile (anche anni di dati)
- 📅 **Suddivisione Mensile**: Gestione automatica grandi volumi senza timeout
- 💾 **Resume Capability**: Riprende da interruzioni senza perdere progressi
- ⚡ **Parallelizzazione**: Esecuzione contemporanea con loop normale

**Testing e Debug Avanzati**
- 🧪 **Single Run Mode**: Test singoli endpoint per validazione configurazione
- 📊 **Modalità Scan**: Auto-discovery device per configurazione automatica
- 🔍 **Diagnostica Dettagliata**: Log granulari per troubleshooting rapido
- 📈 **Metriche Performance**: Monitoraggio tempi risposta, throughput, errori

## 🏗️ Architettura

```
┌─────────────────────────────────────────────────────────────┐
│                    SolarEdge ScanWriter                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   API        │  │   Web        │  │   Modbus     │       │
│  │  Collector   │  │  Scraping    │  │   Realtime   │       │
│  └──────┬───────┘  └───────┬──────┘  └──────┬───────┘       │
│         │                  │                │               │
│         └──────────────────┴────────────────┘               │
│                            │                                │
│                     ┌──────▼───────┐                        │
│                     │    Parser    │                        │
│                     │   + Filter   │                        │
│                     └──────┬───────┘                        │
│                            │                                │
│                     ┌──────▼───────┐                        │
│                     │   InfluxDB   │                        │
│                     │    Writer    │                        │
│                     └──────┬───────┘                        │
│                            │                                │
│                     ┌──────▼───────┐                        │
│                     │   InfluxDB   │                        │
│                     │   Database   │                        │
│                     └──────┬───────┘                        │
│                            │                                │
│                     ┌──────▼───────┐                        │
│                     │   Grafana    │                        │
│                     │   Dashboard  │                        │
│                     └──────────────┘                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 📦 Requisiti

### Sistema

- **OS**: Linux (Debian/Ubuntu consigliato) o Windows
- **Python**: 3.11+
- **RAM**: 2GB minimo, 4GB consigliato
- **Disco**: 16GB per dati storici
- **InfluxDB**: 2.x
- **Grafana**: 10.x+

### Credenziali SolarEdge

- **API Key**: Ottienila dal portale o dal supporto SolarEdge
- **Site ID**: ID del tuo impianto
- **Username/Password**: Credenziali portale web

### ⚠️ Requisito Web Scraping

Per raccogliere dati tramite web scraping (optimizer, inverter, meter, sensori meteo), devi avere **abilitata la visualizzazione Charts** nel portale SolarEdge.

**Come abilitare**:

1. Contatta il supporto SolarEdge
2. Richiedi l'abilitazione della funzionalità "Charts" per il tuo account
3. Una volta abilitata, potrai visualizzare i grafici dettagliati di tutti i device nel portale web
4. Solo a quel punto il web scraping potrà raccogliere questi dati

**Nota**: Senza Charts abilitato, il web scraping non funzionerà per nessun device. Puoi comunque usare API e Modbus per raccogliere dati.

## 🚀 Installazione

### Metodo 1: One-Liner (Raccomandato)

**Opzione A: Con password personalizzate (consigliato)**

```bash
curl -sSL https://raw.githubusercontent.com/frezeen/Solaredge_ScanWriter/main/install.sh -o install.sh
sudo bash install.sh
```

**Opzione B: Con password di default**

```bash
curl -sSL https://raw.githubusercontent.com/frezeen/Solaredge_ScanWriter/main/install.sh | sudo bash
```

Lo script installa automaticamente:

- ✅ Dipendenze Python, InfluxDB 2.x, Grafana con plugin
- ✅ Configurazione iniziale (.env), servizio systemd
- ✅ Dashboard Grafana pre-configurate, formati data italiani
- ✅ Log rotation e cleanup automatico

**Password di default:**

- InfluxDB: `admin` / `solaredge123`
- Grafana: `admin` / `admin` (cambiale al primo accesso)

### Metodo 2: Installazione Manuale

**⚠️ Nota**: Dovrai configurare manualmente il token InfluxDB in `.env` dopo il setup.

```bash
git clone https://github.com/frezeen/Solaredge_ScanWriter.git
cd Solaredge_ScanWriter
chmod +x setup-permissions.sh && ./setup-permissions.sh
pip3 install -r requirements.txt --break-system-packages

# Installa InfluxDB e Grafana (vedi documentazione ufficiale)
# Poi configura .env con token InfluxDB e credenziali SolarEdge
cp .env.example .env && nano .env
```

### Post-Installazione

#### 1. Configura Credenziali SolarEdge

```bash
nano /opt/Solaredge_ScanWriter/.env
```

**Parametri obbligatori da configurare**:

```bash
# Credenziali SolarEdge (OBBLIGATORI)
SOLAREDGE_SITE_ID=123456
SOLAREDGE_USERNAME=your.email@example.com
SOLAREDGE_PASSWORD=your_password
SOLAREDGE_API_KEY=your_api_key

# Modbus Realtime (OPZIONALE - solo se hai l'inverter in rete)
REALTIME_MODBUS_HOST=192.168.1.100  # IP del tuo inverter
REALTIME_MODBUS_PORT=1502
```

**Note**:
- ✅ **Con install.sh**: Il token InfluxDB è già configurato automaticamente
- ⚙️ **Modbus**: Configura IP/porta solo se vuoi telemetria realtime dall'inverter
- 🔧 **Abilitare/Disabilitare Modbus**: Usa la GUI (`http://localhost:8092`) → Modbus Realtime → Toggle
- 🔧 **Altri parametri**: Già preconfigurati con valori ottimali

#### 2. Genera Configurazione Device

```bash
cd /opt/Solaredge_ScanWriter
python3 main.py --scan
```

Questo comando:

- 🔍 Scansiona il portale web SolarEdge
- 📝 Rileva automaticamente tutti i device (inverter, optimizer, meter, sensori)
- 💾 Genera il file `config/sources/web_endpoints.yaml`

**⚠️ Importante**: Se non hai Charts abilitato, lo scan creerà un file yaml vuoto ma valido. Potrai comunque usare API e Modbus.

#### 3. Avvia Servizio

```bash
sudo systemctl enable --now solaredge-scanwriter
```

Questo avvia GUI Dashboard (`http://localhost:8092`), loop di raccolta dati e scrittura su InfluxDB. Dalla GUI è possibile modificare manualmente tutti i file di configurazione tramite il Config Editor.

#### 4. Accedi a Grafana

Apri `http://localhost:3000` (admin/admin) - La dashboard è già importata e configurata!

#### 5. Download Storico (Opzionale)

Se vuoi scaricare tutti i dati storici del tuo impianto:

```bash
cd /opt/Solaredge_ScanWriter
python3 main.py --history
```

**Caratteristiche**:
- 🔄 **Run-once**: Esecuzione singola con output dettagliato in console
- 📅 **Suddivisione mensile**: Processa automaticamente mese per mese
- 💾 **Cache intelligente**: Skip mesi già scaricati, riprende da interruzioni
- 📊 **Visualizzazione immediata**: I dati appaiono in Grafana ogni 5 secondi

**Durata tipica**: 5-15 minuti per impianti fino a 5 anni (con endpoint di default)

**Monitoraggio**: Il progresso è visibile direttamente in console con statistiche dettagliate per ogni mese

## ⚙️ Configurazione

### Struttura File

```
config/
├── main.yaml                    # Configurazione principale
├── sources/
│   ├── api_endpoints.yaml      # 22 endpoint API SolarEdge
│   ├── web_endpoints.yaml      # Device web (auto-generato con --scan)
│   └── modbus_endpoints.yaml   # Endpoint Modbus realtime
└── .env                         # Credenziali (root directory)
```

### Endpoint Abilitati di Default

La configurazione di default è ottimizzata per la dashboard Grafana inclusa:

**API (9/22 endpoint)**: equipment_data, equipment_list, site_details, site_energy_day, site_energy_details, site_env_benefits, site_overview, site_power_details, site_timeframe_energy

**Web Scraping**: Optimizer ✅, Weather ✅, Inverter ❌, Meter ❌

**Modbus Realtime**: Inverter ✅, Meter ✅, Batteries ❌

### Personalizzazione

Accedi alla GUI (`http://localhost:8092`) per abilitare/disabilitare endpoint aggiuntivi secondo le tue esigenze. Tutti i 22 endpoint API sono disponibili per analisi personalizzate.

**Quando personalizzare**:

- Dashboard Grafana personalizzate con metriche aggiuntive
- Dati specifici non inclusi nella dashboard default
- Monitoraggio batterie o sensori aggiuntivi

## 🎯 Utilizzo

### GUI Dashboard

**URL**: `http://localhost:8092`

![Loop Monitor](screenshoot/loop%20monitor.png)

La GUI offre 5 sezioni:

1. **Device Web Scraping** - Gestisci device rilevati (Optimizer, Meter, Weather)
2. **API Endpoints** - Configura 22 endpoint API per categoria  
   ![API Endpoints](screenshoot/api%20endpoints.png)
3. **Modbus Realtime** - Gestisci telemetria in tempo reale  
   ![Modbus Endpoints](screenshoot/modbus%20endpoints.png)
4. **Loop Monitor** - Start/Stop loop, statistiche, log live
5. **Config Editor** - Editor per modificare manualmente tutti i file di configurazione con syntax highlighting

### Modalità Command Line

```bash
# Test singoli
python main.py --api        # Solo API
python main.py --web        # Solo web scraping
python main.py --realtime   # Solo Modbus
python main.py --scan       # Aggiorna config device

# Download storico
python main.py --history

# Loop 24/7
python main.py              # GUI + loop automatico
sudo systemctl start solaredge-scanwriter  # Con systemd
```

### Docker

```bash
docker-compose up -d
docker-compose logs -f solaredge-scanwriter
```



## 📊 Dashboard Grafana

![Dashboard Grafana](screenshoot/dash%20grafana.png)

### Accesso

- URL: `http://localhost:3000`
- Credenziali: admin/admin (default)

### Configurazione Automatica

L'installer configura automaticamente:

- Data source InfluxDB "Solaredge" e "Sun and Moon"
- Dashboard completa importata via API
- Formati data italiani (DD-MM-YYYY, HH:mm)
- Plugin: fetzerch-sunandmoon-datasource, grafana-clock-panel

### Metriche Disponibili

- 📈 Produzione totale (giornaliera, mensile, annuale, lifetime)
- 🏠 Consumo e autoconsumo
- ⚡ Prelievo e immissione rete
- 💰 Calcoli economici SSP
- 🌍 Emissioni CO2 evitate
- 📊 Produzione mensile storica, heatmap giornaliera
- ⚡ Potenza optimizer in tempo reale
- 🌡️ Telemetria inverter (temperatura, tensioni, correnti, stato)

## 📚 Documentazione

- `docs/api_endpoints_reference.md`: Tutti gli endpoint API con esempi query
- `docs/web_endpoints_reference.md`: Struttura dati web scraping
- `docs/realtime_endpoints_reference.md`: Registri Modbus e telemetria
- `docs/retention_policy_setup.md`: Configurazione retention InfluxDB

## 🔧 Troubleshooting

### InfluxDB non risponde

```bash
sudo systemctl status influxdb
sudo systemctl restart influxdb
sudo journalctl -u influxdb -f
```

### Grafana non mostra dati

1. Verifica data source InfluxDB in Grafana
2. Controlla token e bucket name
3. Con installazione manuale: Recupera token da InfluxDB UI → Load Data → API Tokens

### Web Scraping fallisce

```bash
# Genera/rigenera configurazione
python main.py --scan

# Rigenera cookie se login fallisce
rm cookies/web_cookies.json
```

**Errore comune**: `FileNotFoundError: config/sources/web_endpoints.yaml`

- **Soluzione**: Esegui `python main.py --scan`

### API Rate Limit

- Limite: 300 richieste/giorno per site
- Soluzione: Cache già abilitata di default
- Verifica: `cache/api_ufficiali/` per file cached

### Aggiornamenti

**Aggiornamento standard (raccomandato)**:

```bash
cd /opt/Solaredge_ScanWriter
./update.sh
```

**Comandi avanzati**:

```bash
# Solo controllo aggiornamenti (senza applicare)
python3 scripts/smart_update.py --check-only

# Aggiornamento forzato
python3 scripts/smart_update.py --force
```

**Lo script `update.sh`**:

- ✅ Controlla aggiornamenti disponibili
- ✅ Backup automatico configurazione
- ✅ Pull da GitHub e aggiornamento dipendenze
- ✅ Preserva configurazioni locali (`.env`, `config/*.yaml`)
- ✅ Corregge permessi automaticamente
- ✅ Restart servizio
- ✅ **Importa automaticamente dashboard Grafana aggiornata**

**⚠️ Importante - Dashboard Personalizzate**:
Se hai creato dashboard personalizzate in Grafana, salvale con un **nome diverso** da "SolarEdge". Lo script `update.sh` sovrascrive automaticamente la dashboard "SolarEdge" con la versione aggiornata dal repository.

**Esempio**:

- Dashboard originale: "SolarEdge" → Verrà sovrascritta da update.sh
- Dashboard personalizzata: "SolarEdge - Custom" → Sarà preservata

## 🤝 Contributi

Contributi benvenuti! Fork, crea feature branch, commit, push e apri Pull Request.

## 📝 License

MIT License - Vedi `LICENSE` per dettagli.

## 📧 Supporto

- **Issues**: [GitHub Issues](https://github.com/frezeen/Solaredge_ScanWriter/issues)
- **Discussions**: [GitHub Discussions](https://github.com/frezeen/Solaredge_ScanWriter/discussions)

---

**Made with ❤️ for the Solar Community**
