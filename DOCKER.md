# 🐳 Guida Docker - SolarEdge Data Collector

Questa guida ti accompagna passo dopo passo nell'installazione e utilizzo di SolarEdge Data Collector tramite Docker.

## 🎯 Cosa Otterrai

Al termine di questa guida avrai:
- **SolarEdge Data Collector** funzionante
- **Database InfluxDB** per memorizzare i dati
- **Dashboard Grafana** per visualizzare grafici e statistiche
- **Sistema automatico** di raccolta dati dal tuo impianto fotovoltaico



## 📋 Prima di Iniziare

**Cosa ti serve:**
- Computer con Windows, Linux o Raspberry Pi
- Docker installato (ti spiego come fare)
- Account SolarEdge con accesso API
- 30 minuti di tempo

## 🚀 Passo 1: Installazione Docker

### Su Windows
1. Scarica **Docker Desktop** da: https://www.docker.com/products/docker-desktop/
2. Installa seguendo la procedura guidata
3. Riavvia il computer quando richiesto
4. Apri Docker Desktop e attendi che si avvii

### Su Linux/Raspberry Pi
```bash
# Installa Docker automaticamente
curl -fsSL https://get.docker.com | sh

# Aggiungi il tuo utente al gruppo docker
sudo usermod -aG docker $USER

# Riavvia la sessione (o riavvia il sistema)
```

## 📥 Passo 2: Scarica il Progetto

```bash
# Scarica il progetto
git clone https://github.com/frezeen/Solaredge_ScanWriter.git
cd Solaredge_ScanWriter
```

## ⚙️ Passo 3: Configurazione

### Trova le Tue Credenziali SolarEdge

1. **Site ID**: Vai su https://monitoring.solaredge.com, il numero nell'URL è il tuo Site ID
2. **API Key**: Nel portale SolarEdge, vai su Admin → API → Genera nuova chiave
3. **Username/Password**: Le credenziali del tuo account SolarEdge

### Configura il File .env

```bash
# Copia il file di esempio
cp .env.example .env

# Modifica con le tue credenziali
nano .env  # Linux/Mac
notepad .env  # Windows
```

**Modifica queste righe nel file .env:**
```bash
SOLAREDGE_SITE_ID=123456                    # ← Il tuo Site ID
SOLAREDGE_API_KEY=ABC123XYZ                 # ← La tua API Key
SOLAREDGE_USERNAME=tuaemail@example.com     # ← La tua email SolarEdge
SOLAREDGE_PASSWORD=tuapassword              # ← La tua password SolarEdge
```

**Opzionale - Per dati in tempo reale (Modbus):**
```bash
REALTIME_MODBUS_HOST=192.168.1.100          # ← IP del tuo inverter
REALTIME_MODBUS_PORT=1502                   # ← Porta Modbus (di solito 1502)
```

## 🏗️ Passo 4: Installazione Automatica

### Su Linux/Raspberry Pi
```bash
chmod +x docker-build.sh
./docker-build.sh
```

### Su Windows (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File .\docker-build.ps1
```

**Cosa succede automaticamente:**
1. ✅ Costruisce il container Docker
2. ✅ Avvia tutti i servizi (SolarEdge, InfluxDB, Grafana)
3. ✅ Configura automaticamente Grafana con dashboard
4. ✅ Genera gli endpoint per la raccolta dati web
5. ✅ Verifica che tutto funzioni

## 🎉 Passo 5: Accesso ai Servizi

Dopo l'installazione, apri il browser e vai su:

- **🏠 Dashboard Principale**: http://localhost:8092
- **📊 Grafana (Grafici)**: http://localhost:3000 (admin/admin)
- **🗄️ InfluxDB (Database)**: http://localhost:8086 (admin/solaredge123)

## 📈 Passo 6: Primo Utilizzo

### Verifica Raccolta Dati
1. Vai su http://localhost:8092
2. Controlla che i dati vengano raccolti
3. Vai su Grafana (http://localhost:3000) per vedere i grafici

### Scarica Dati Storici (Opzionale)
```bash
# Scarica tutto lo storico disponibile
docker exec solaredge-scanwriter python main.py --history
```

## 🔄 Aggiornamenti

Quando rilascio nuove funzionalità o correzioni:

```bash
# Un solo comando per aggiornare tutto
git pull origin main
./docker-build.sh  # Linux/Mac/Pi
# oppure
.\docker-build.ps1  # Windows
```

**Le tue configurazioni sono sempre al sicuro:**
- ✅ File `.env` con le tue credenziali
- ✅ Endpoint personalizzati in `config/sources/`
- ✅ Tutti i dati storici in InfluxDB
- ✅ Dashboard personalizzate in Grafana

## 🛠️ Gestione Quotidiana

### Comandi Utili
```bash
# Vedere i log in tempo reale
docker compose logs -f

# Stato dei servizi
docker compose ps

# Fermare tutto
docker compose down

# Riavviare tutto
docker compose up -d

# Test singoli componenti
docker exec solaredge-scanwriter python main.py --api
docker exec solaredge-scanwriter python main.py --web
```

### Backup dei Dati
```bash
# Backup automatico dei volumi Docker
docker run --rm -v solaredge_scanwriter_influxdb-data:/data -v $(pwd):/backup alpine tar czf /backup/backup-$(date +%Y%m%d).tar.gz /data
```

## ❓ Risoluzione Problemi

### Script PowerShell bloccato (Windows)
```powershell
# Usa sempre questo comando per eseguire lo script
powershell -ExecutionPolicy Bypass -File .\docker-build.ps1
```

### Docker non installato o non funziona
```powershell
# Errore: "Image not found after build" o comandi docker non trovati
# Verifica che Docker sia installato e in esecuzione
docker --version
docker compose version

# Se non installato, scarica Docker Desktop da:
# https://www.docker.com/products/docker-desktop/
```

### Il container non si avvia
```bash
# Controlla i log per errori
docker logs solaredge-scanwriter
```

### Credenziali sbagliate
```bash
# Verifica le credenziali nel container
docker exec solaredge-scanwriter env | grep SOLAREDGE
```

### Problemi di rete
```bash
# Testa la connessione a SolarEdge
docker exec solaredge-scanwriter python main.py --api
```

### Porte occupate
Se le porte 8092, 8086 o 3000 sono già in uso, modifica `docker-compose.yml`:
```yaml
ports:
  - "8093:8092"  # Usa porta 8093 invece di 8092
```

## 🎯 Risultato Finale

Avrai un sistema completo che:
- 📡 Raccoglie automaticamente i dati dal tuo impianto
- 💾 Li memorizza in un database professionale
- 📊 Li visualizza in grafici bellissimi
- 🔄 Si aggiorna facilmente con nuove funzionalità
- 🛡️ Mantiene sempre al sicuro le tue configurazioni

**Buon monitoraggio del tuo impianto fotovoltaico!** ☀️
