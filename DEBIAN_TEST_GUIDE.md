# 🐧 SolarEdge ScanWriter - Test su Debian

## 📋 Prerequisiti Debian

Assicurati che la tua macchina Debian abbia:
- Docker 20.10+ installato e funzionante
- Git installato
- Connessione internet
- Almeno 2GB RAM liberi

### Verifica Prerequisiti

```bash
# Verifica Docker
docker --version
docker compose version

# Verifica Git
git --version

# Verifica risorse
free -h
df -h
```

## 🚀 PROCEDURA COMPLETA

### Step 1: Clone Repository e Branch Dev

```bash
# Vai nella directory di lavoro
cd /home/$USER

# Clone del repository
git clone https://github.com/frezeen/Solaredge_ScanWriter.git
cd Solaredge_ScanWriter

# Crea e switch al branch dev
git checkout -b dev
git push -u origin dev

# Verifica branch attivo
git branch
```

### Step 2: Configurazione Credenziali

```bash
# Copia template configurazione
cp .env.docker.example .env

# Modifica con le tue credenziali SolarEdge
nano .env
```

**Configurazione minima richiesta in `.env`:**
```bash
# CREDENZIALI SOLAREDGE (OBBLIGATORIE)
SOLAREDGE_SITE_ID=123456                    # Il tuo Site ID
SOLAREDGE_USERNAME=your.email@example.com   # Il tuo username
SOLAREDGE_PASSWORD=your_password            # La tua password
SOLAREDGE_API_KEY=your_api_key             # La tua API key

# DATABASE (auto-configurato)
INFLUXDB_TOKEN=solaredge-super-secret-token-2024
INFLUXDB_ORG=fotovoltaico
INFLUXDB_BUCKET=solaredge

# SISTEMA
TZ=Europe/Rome
LOG_LEVEL=INFO
```

### Step 3: Build Container

```bash
# Rendi eseguibile lo script build
chmod +x docker/build.sh
chmod +x docker/entrypoint.sh

# Build automatico con detection architettura
./docker/build.sh build
```

**Output atteso:**
```
🐳 SolarEdge ScanWriter - Universal Build
=======================================
🔍 Platform Detection:
   OS: Linux
   Architecture: x86_64
   Docker Platform: linux/amd64
🔍 Checking prerequisites...
✅ Prerequisites OK
🔨 Building universal image...
✅ Build completed for linux/amd64
🧪 Testing image...
✅ Tests passed
```

### Step 4: Test Container Singolo

```bash
# Test rapido del container
docker run --rm \
  -e SOLAREDGE_SITE_ID=123456 \
  -e SOLAREDGE_API_KEY=test-key \
  solaredge-scanwriter:latest python --version

# Test architettura
docker run --rm solaredge-scanwriter:latest uname -a

# Test configurazione
docker run --rm \
  --env-file .env \
  solaredge-scanwriter:latest python -c "
import os
print(f'✅ Site ID: {os.getenv(\"SOLAREDGE_SITE_ID\")}')
print(f'✅ Docker Mode: {os.getenv(\"DOCKER_MODE\")}')
"
```

### Step 5: Avvio Stack Completo

```bash
# Avvia stack completo (SolarEdge + InfluxDB + Grafana)
docker compose up -d

# Verifica servizi attivi
docker compose ps
```

**Output atteso:**
```
NAME                    IMAGE                    STATUS
solaredge-grafana       grafana/grafana:10.2.0   Up
solaredge-influxdb      influxdb:2.7             Up (healthy)
solaredge-scanwriter    solaredge-scanwriter     Up (healthy)
```

### Step 6: Verifica Funzionamento

```bash
# Log in tempo reale
docker compose logs -f solaredge-scanwriter

# Verifica health check
docker exec solaredge-scanwriter python -c "
import requests
try:
    r = requests.get('http://localhost:8092/health', timeout=5)
    print(f'✅ GUI Health: {r.status_code}')
except Exception as e:
    print(f'❌ GUI Error: {e}')
"

# Verifica connessione InfluxDB
docker exec solaredge-scanwriter python -c "
from storage.writer_influx import InfluxWriter
try:
    with InfluxWriter() as w:
        print('✅ InfluxDB Connection OK')
except Exception as e:
    print(f'❌ InfluxDB Error: {e}')
"
```

## 🌐 Accesso Servizi

Dopo l'avvio, i servizi sono disponibili su:

- **SolarEdge GUI**: http://IP_DEBIAN:8092
- **InfluxDB**: http://IP_DEBIAN:8086 (admin/solaredge123)
- **Grafana**: http://IP_DEBIAN:3000 (admin/admin)

### Trova IP Debian

```bash
# IP della macchina Debian
ip addr show | grep 'inet ' | grep -v '127.0.0.1'
```

## 🧪 Test Funzionalità

### Test Raccolta Dati

```bash
# Test API SolarEdge
docker exec solaredge-scanwriter python main.py --api

# Test web scraping
docker exec solaredge-scanwriter python main.py --web

# Test scan device
docker exec solaredge-scanwriter python main.py --scan

# Test Modbus (se configurato)
docker exec solaredge-scanwriter python main.py --realtime
```

### Monitoraggio

```bash
# Statistiche risorse
docker stats

# Log applicazione
docker logs -f solaredge-scanwriter

# Spazio disco
docker system df
```

## 🔧 Troubleshooting

### Problema: Container non si avvia

```bash
# Verifica log errori
docker logs solaredge-scanwriter

# Verifica configurazione
docker exec solaredge-scanwriter env | grep SOLAREDGE
```

### Problema: InfluxDB non raggiungibile

```bash
# Verifica InfluxDB
docker logs solaredge-influxdb

# Restart InfluxDB
docker compose restart influxdb
```

### Problema: Porta occupata

```bash
# Verifica porte in uso
sudo netstat -tlnp | grep -E ':(8092|8086|3000)'

# Stop servizi conflittuali
sudo systemctl stop apache2 nginx  # se presenti
```

## 🧹 Cleanup (se necessario)

```bash
# Stop stack
docker compose down

# Rimozione completa (ATTENZIONE: cancella dati!)
docker compose down -v
docker system prune -f

# Rimozione immagini
docker rmi solaredge-scanwriter:latest
```

## ✅ Risultati Attesi

Se tutto funziona correttamente dovresti vedere:

1. **Container in esecuzione** senza errori
2. **GUI accessibile** su porta 8092
3. **Log puliti** senza errori critici
4. **Dati raccolti** (se credenziali corrette)
5. **Dashboard Grafana** funzionante

## 📞 Supporto

Se incontri problemi:

1. Controlla i log: `docker compose logs`
2. Verifica configurazione: `cat .env`
3. Testa connettività: `curl -I http://localhost:8092`
4. Riporta errori specifici per assistenza

---

**🎯 Obiettivo**: Verificare che il container universale funzioni perfettamente su Debian