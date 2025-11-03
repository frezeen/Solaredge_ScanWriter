# 🚀 Quick Start - Debian Docker

## Setup Iniziale su Debian

```bash
# 1. Clone del repository (se non già fatto)
git clone https://github.com/frezeen/Solaredge_ScanWriter.git
cd Solaredge_ScanWriter

# 2. Switch al branch dev
git checkout dev

# 3. Configura credenziali
cp .env.example .env
nano .env  # Inserisci le tue credenziali SolarEdge

# 4. Lancia il setup completo
chmod +x dev-docker-rebuild.sh
./dev-docker-rebuild.sh
```

## Credenziali Richieste in .env

```bash
SOLAREDGE_SITE_ID=123456
SOLAREDGE_API_KEY=your_api_key_here
SOLAREDGE_USERNAME=your.email@example.com
SOLAREDGE_PASSWORD=your_password_here
```

## Servizi Disponibili

- **GUI SolarEdge**: http://localhost:8092
- **InfluxDB**: http://localhost:8086 (admin/solaredge123)

## Comandi Rapidi

```bash
# Deploy rapido dopo modifiche codice
./dev-quick-deploy.sh

# Log in tempo reale
./dev-logs.sh solaredge

# Test componenti
docker exec solaredge-collector python main.py --api
docker exec solaredge-collector python main.py --web
docker exec solaredge-collector python main.py --scan
```

## Note Importanti

- ✅ Lo script `dev-docker-rebuild.sh` fa automaticamente `git pull` delle ultime modifiche
- ✅ Pulisce completamente Docker da qualsiasi traccia del progetto precedente
- ✅ Ricostruisce tutto da zero con le ultime modifiche
- ✅ Supporta multi-architettura (AMD64, ARM64, ARMv7)

## 🧹 Script di Pulizia Aggiuntivi

### Pulizia Completa Macchina
```bash
# ⚠️ ATTENZIONE: Rimuove TUTTO Docker dalla macchina!
chmod +x debian-clean-machine.sh
./debian-clean-machine.sh
```

### Pulizia Solo Progetto SolarEdge
```bash
# Rimuove solo SolarEdge, mantiene Docker
chmod +x debian-clean-project.sh
./debian-clean-project.sh
```

Tutto è pronto per il test su Debian! 🎯