# 🛠️ SolarEdge Docker - Sviluppo su Debian

## 🧹 Script di Pulizia

### Pulizia Completa Macchina (ATTENZIONE!)
```bash
# Rimuove TUTTO: Docker, container, immagini, progetto
# ⚠️ OPERAZIONE NON REVERSIBILE ⚠️
chmod +x debian-clean-machine.sh
./debian-clean-machine.sh
```

### Pulizia Solo Progetto SolarEdge
```bash
# Rimuove solo il progetto, mantiene Docker installato
chmod +x debian-clean-project.sh
./debian-clean-project.sh
```

## 🚀 Setup Rapido

### 1. Primo Setup (Pulizia + Build + Deploy)
```bash
# Rendi eseguibile e lancia
chmod +x dev-docker-rebuild.sh
./dev-docker-rebuild.sh
```

Questo script:
- 🧹 Pulisce completamente Docker da tutto il progetto SolarEdge
- 🏗️ Ricostruisce l'immagine multi-architettura
- 🚀 Avvia lo stack completo
- 🔍 Verifica che tutto funzioni

### 2. Deploy Rapido (solo rebuild)
```bash
# Per modifiche veloci al codice
chmod +x dev-quick-deploy.sh
./dev-quick-deploy.sh
```

### 3. Log in Tempo Reale
```bash
# Tutti i servizi
chmod +x dev-logs.sh
./dev-logs.sh all

# Solo SolarEdge
./dev-logs.sh solaredge

# Solo InfluxDB
./dev-logs.sh influx
```

## 📋 Configurazione Richiesta

Prima del primo avvio, configura `.env`:

```bash
# Copia template
cp .env.example .env

# Modifica con le tue credenziali
nano .env
```

**Credenziali minime richieste:**
```bash
SOLAREDGE_SITE_ID=123456
SOLAREDGE_API_KEY=your_api_key_here
SOLAREDGE_USERNAME=your.email@example.com
SOLAREDGE_PASSWORD=your_password_here
```

## 🎯 Servizi Disponibili

Dopo l'avvio:
- **GUI SolarEdge**: http://localhost:8092
- **InfluxDB**: http://localhost:8086 (admin/solaredge123)

## 🧪 Test Componenti

```bash
# Test raccolta API
docker exec solaredge-collector python main.py --api

# Test web scraping
docker exec solaredge-collector python main.py --web

# Scan endpoint web
docker exec solaredge-collector python main.py --scan

# Test Modbus (se configurato)
docker exec solaredge-collector python main.py --realtime
```

## 🔧 Comandi Docker Utili

```bash
# Status servizi
docker compose ps

# Shell nel container
docker exec -it solaredge-collector bash

# Restart singolo servizio
docker compose restart solaredge

# Stop tutto
docker compose down

# Stop e rimuovi volumi (ATTENZIONE: cancella dati!)
docker compose down -v
```

## 🐛 Debug

### Verifica Configurazione
```bash
# Variabili d'ambiente nel container
docker exec solaredge-collector env | grep SOLAREDGE

# File di configurazione
docker exec solaredge-collector cat config/main.yaml
```

### Test Connessioni
```bash
# Test InfluxDB dal container
docker exec solaredge-collector python -c "
from storage.writer_influx import InfluxWriter
try:
    with InfluxWriter() as w:
        print('✅ InfluxDB OK')
except Exception as e:
    print(f'❌ Errore: {e}')
"

# Test GUI health
curl http://localhost:8092/health
```

### Log Dettagliati
```bash
# Log con timestamp
docker compose logs -t -f solaredge

# Log ultimi 50 righe
docker compose logs --tail=50 solaredge

# Log di tutti i servizi
docker compose logs -f
```

## 🔄 Workflow Sviluppo

1. **Modifica codice** nel tuo editor
2. **Quick deploy**: `./dev-quick-deploy.sh`
3. **Verifica log**: `./dev-logs.sh solaredge`
4. **Test componenti** con i comandi sopra
5. **Ripeti** dal punto 1

Per modifiche strutturali (Dockerfile, docker-compose.yml):
```bash
./dev-docker-rebuild.sh
```

## 📊 Monitoraggio Risorse

```bash
# Uso risorse container
docker stats

# Spazio disco Docker
docker system df

# Info dettagliate immagini
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
```