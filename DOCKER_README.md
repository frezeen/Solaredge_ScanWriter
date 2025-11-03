# 🐳 SolarEdge ScanWriter - Docker Universal

## 📁 File Docker Essenziali

### File Principali
- **`Dockerfile`** - Container universale multi-architettura
- **`docker-compose.yml`** - Stack completo (SolarEdge + InfluxDB + Grafana)
- **`requirements.txt`** - Dipendenze Python (include supporto Docker)
- **`.env.docker.example`** - Template configurazione

### Script e Documentazione
- **`docker/build.sh`** - Script build automatico
- **`docker/entrypoint.sh`** - Inizializzazione container
- **`docker/platform-fixes.py`** - Fix cross-platform
- **`DOCKER_SETUP.md`** - Documentazione completa

## 🚀 Quick Start

```bash
# 1. Configurazione
cp .env.docker.example .env
nano .env  # Inserisci credenziali SolarEdge

# 2. Build e avvio
chmod +x docker/build.sh
./docker/build.sh build
docker compose up -d

# 3. Accesso servizi
# GUI: http://localhost:8092
# InfluxDB: http://localhost:8086
# Grafana: http://localhost:3000
```

## 🌍 Compatibilità

✅ **Windows** (Docker Desktop)  
✅ **Linux** (Ubuntu, Debian, CentOS, etc.)  
✅ **macOS** (Intel + Apple Silicon)  
✅ **Raspberry Pi** (ARM64/ARMv7)  

## 🧹 File Rimossi (Cleanup)

- ❌ `Dockerfile.multiarch` (duplicato)
- ❌ `docker-compose.production.yml` (duplicato)  
- ❌ `requirements.docker.txt` (consolidato in requirements.txt)

## 📋 Prossimi Passi

1. Test su Debian
2. Verifica multi-architettura
3. Push su Docker Hub (opzionale)
4. Merge in main branch

---

**Documentazione completa**: `DOCKER_SETUP.md`