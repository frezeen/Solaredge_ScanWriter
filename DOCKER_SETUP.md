# 🐳 SolarEdge ScanWriter - Setup Docker Universale

## 📋 Prerequisiti

**Compatibile con:**
- 🐧 **Linux** (Ubuntu, Debian, CentOS, etc.)
- 🍎 **macOS** (Intel e Apple Silicon)
- 🪟 **Windows** (Docker Desktop)
- 🥧 **Raspberry Pi** (ARM64/ARMv7)

**Requisiti:**
- Docker 20.10+ installato
- Docker Compose v2+
- Git per gestione repository
- 2GB RAM minimo, 4GB consigliato
- Accesso internet per download immagini

## 🚀 Setup Iniziale

### 1. Preparazione Repository

```bash
# Clone del repository (se non già fatto)
git clone https://github.com/frezeen/Solaredge_ScanWriter.git
cd Solaredge_ScanWriter

# Crea e switch al branch dev
git checkout -b dev
git push -u origin dev

# Verifica branch attivo
git branch
```

### 2. Preparazione File Docker

I file Docker universali sono già presenti:
- `Dockerfile` - Container multi-architettura universale
- `docker-compose.yml` - Stack completo (SolarEdge + InfluxDB + Grafana)
- `docker/entrypoint.sh` - Script di inizializzazione cross-platform
- `.env.docker.example` - Template configurazione

### 3. Configurazione Environment

```bash
# Copia template configurazione
cp .env.docker.example .env

# Modifica con le tue credenziali SolarEdge
nano .env
```

**Configurazione minima richiesta in `.env`:**
```bash
# Credenziali SolarEdge (OBBLIGATORIE)
SOLAREDGE_SITE_ID=123456
SOLAREDGE_USERNAME=your.email@example.com
SOLAREDGE_PASSWORD=your_password
SOLAREDGE_API_KEY=your_api_key

# Database InfluxDB (auto-configurato)
INFLUXDB_TOKEN=solaredge-super-secret-token-2024
INFLUXDB_ORG=fotovoltaico
INFLUXDB_BUCKET=solaredge

# Grafana (opzionale)
GRAFANA_USER=admin
GRAFANA_PASSWORD=admin

# Timezone
TZ=Europe/Rome
```

## 🔨 Build e Deploy

### Metodo 1: Script Automatico (Raccomandato)

```bash
# Rendi eseguibile lo script
chmod +x docker/build.sh

# Build automatico con detection piattaforma
./docker/build.sh build

# Solo test (se già buildato)
./docker/build.sh test

# Informazioni immagine
./docker/build.sh info
```

### Metodo 2: Build Manuale

```bash
# Build immagine universale
docker build -t solaredge-scanwriter:latest .

# Test cross-platform
docker run --rm -e SOLAREDGE_SITE_ID=123456 -e SOLAREDGE_API_KEY=test solaredge-scanwriter:latest python --version

# Verifica architettura
docker run --rm solaredge-scanwriter:latest uname -a
```

### Metodo 3: Stack Completo con Docker Compose

```bash
# Avvia stack completo (SolarEdge + InfluxDB + Grafana)
docker compose up -d

# Verifica servizi
docker compose ps

# Log in tempo reale
docker compose logs -f solaredge-scanwriter

# Verifica multi-architettura
docker exec solaredge-scanwriter uname -a
```

## 🌐 Accesso Servizi

Dopo l'avvio, i servizi sono disponibili su:

- **SolarEdge GUI**: http://localhost:8092
- **InfluxDB**: http://localhost:8086 (admin/solaredge123)
- **Grafana**: http://localhost:3000 (admin/admin)

## 🔍 Verifica Funzionamento

### Test Singoli Componenti

```bash
# Test raccolta API
docker exec solaredge-scanwriter python main.py --api

# Test web scraping
docker exec solaredge-scanwriter python main.py --web

# Test Modbus (se configurato)
docker exec solaredge-scanwriter python main.py --realtime

# Scan device web
docker exec solaredge-scanwriter python main.py --scan
```

### Monitoraggio

```bash
# Log applicazione
docker logs -f solaredge-scanwriter

# Statistiche risorse
docker stats solaredge-scanwriter

# Health check
docker exec solaredge-scanwriter python -c "
import requests
try:
    r = requests.get('http://localhost:8092/health', timeout=5)
    print(f'✅ GUI Health: {r.status_code}')
except:
    print('❌ GUI non raggiungibile')
"
```

## 🛠️ Troubleshooting

### Problemi Comuni

**1. Container non si avvia**
```bash
# Verifica log errori
docker logs solaredge-scanwriter

# Verifica configurazione
docker exec solaredge-scanwriter env | grep SOLAREDGE
```

**2. InfluxDB non raggiungibile**
```bash
# Verifica InfluxDB
docker logs solaredge-influxdb

# Test connessione
docker exec solaredge-scanwriter python -c "
from storage.writer_influx import InfluxWriter
try:
    with InfluxWriter() as w:
        print('✅ InfluxDB OK')
except Exception as e:
    print(f'❌ InfluxDB Error: {e}')
"
```

**3. Credenziali SolarEdge errate**
```bash
# Verifica credenziali
docker exec solaredge-scanwriter python -c "
import os
print(f'Site ID: {os.getenv(\"SOLAREDGE_SITE_ID\")}')
print(f'API Key: {os.getenv(\"SOLAREDGE_API_KEY\", \"NOT_SET\")}')
"
```

## 🔄 Aggiornamenti

```bash
# Pull ultime modifiche
git pull origin dev

# Rebuild immagine universale
docker compose build --no-cache

# Restart servizi
docker compose restart
```

## 🧹 Cleanup

```bash
# Stop e rimozione stack
docker compose down

# Rimozione volumi (ATTENZIONE: cancella dati!)
docker compose down -v

# Pulizia immagini
docker image prune -f
```

## 📊 Performance Tuning

### Limiti Risorse (per Raspberry Pi o VPS piccoli)

Modifica `docker-compose.yml`:
```yaml
services:
  solaredge-scanwriter:
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: '0.5'
```

### Ottimizzazioni Cache

```bash
# Verifica cache hit ratio
docker exec solaredge-scanwriter ls -la cache/

# Pulizia cache se necessario
docker exec solaredge-scanwriter rm -rf cache/*
```

## 🎯 Prossimi Passi

1. **Test Completo**: Verifica tutti i flussi (API, Web, Modbus)
2. **Monitoraggio**: Setup alerting per errori
3. **Backup**: Configurazione backup automatico dati InfluxDB
4. **Scaling**: Multi-container per alta disponibilità

---

**📞 Supporto**: Per problemi specifici, controlla i log e la documentazione del progetto principale.