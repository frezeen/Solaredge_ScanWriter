# ⚡ SolarEdge ScanWriter

**Sistema completo di monitoraggio per impianti fotovoltaici SolarEdge**

Raccogli, analizza e visualizza i dati del tuo impianto fotovoltaico con dashboard Grafana professionali. Gestione semplice tramite interfaccia web, nessuna configurazione manuale richiesta.

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
│                    SolarEdge ScanWriter                      │
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

## 📦 Requisiti

### Sistema
- **OS**: Linux (Debian/Ubuntu consigliato) o Windows
- **Python**: 3.11+
- **RAM**: 512MB minimo, 1GB consigliato
- **Disco**: 10GB per dati storici
- **InfluxDB**: 2.x
- **Grafana**: 10.x+

### Credenziali SolarEdge
- **API Key**: Ottienila dal portale SolarEdge
- **Site ID**: ID del tuo impianto
- **Username/Password**: Credenziali portale web

### ⚠️ Requisito Web Scraping (Optimizer)
Per raccogliere dati dettagliati degli optimizer tramite web scraping, devi avere **abilitata la visualizzazione Charts** nel portale SolarEdge.

**Come abilitare**:
1. Contatta il supporto SolarEdge
2. Richiedi l'abilitazione della funzionalità "Charts" per il tuo account
3. Una volta abilitata, potrai visualizzare i grafici dettagliati degli optimizer nel portale web
4. Solo a quel punto il web scraping potrà raccogliere questi dati

**Nota**: Senza Charts abilitato, il web scraping non funzionerà. Puoi comunque usare API e Modbus per raccogliere dati.

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

Aggiungi le tue credenziali:
```bash
SOLAREDGE_SITE_ID=123456
SOLAREDGE_USERNAME=your.email@example.com
SOLAREDGE_PASSWORD=your_password
SOLAREDGE_API_KEY=your_api_key
```

**Nota**: Con `install.sh` il token InfluxDB è già configurato automaticamente.

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

Questo avvia GUI Dashboard (`http://localhost:8092`), loop di raccolta dati e scrittura su InfluxDB.

#### 4. Accedi a Grafana
Apri `http://localhost:3000` (admin/admin) - La dashboard è già importata e configurata!

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

La GUI offre 5 sezioni:

1. **Device Web Scraping** - Gestisci device rilevati (Optimizer, Meter, Weather)
2. **API Endpoints** - Configura 22 endpoint API per categoria
3. **Modbus Realtime** - Gestisci telemetria in tempo reale
4. **Loop Monitor** - Start/Stop loop, statistiche, log live
5. **YAML Config** - Editor configurazioni con syntax highlighting

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

```bash
cd /opt/Solaredge_ScanWriter
./update.sh  # Backup automatico, pull, update dipendenze, restart
```

Lo script `update.sh`:
- ✅ Backup automatico configurazione
- ✅ Pull da GitHub e aggiornamento dipendenze
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
