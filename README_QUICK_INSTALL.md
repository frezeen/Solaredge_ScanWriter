# SolarEdge Data Collector - Installazione Rapida

## One-Liner Installation (Raccomandato)

Dal tuo container Debian, esegui semplicemente:

```bash
curl -sSL https://raw.githubusercontent.com/frezeen/Solaredge_ScanWriter/main/install.sh | sudo bash
```

**Nota**: Lo script richiede privilegi root per installare pacchetti di sistema e configurare servizi.

Questo comando:
- ✅ Scarica automaticamente tutto il progetto da GitHub
- ✅ Installa tutte le dipendenze (Python, InfluxDB, Grafana)
- ✅ Configura tutti i servizi
- ✅ Crea l'utente e le directory necessarie
- ✅ Configura firewall e servizi systemd

## Dopo l'Installazione

### 1. Configura le Credenziali SolarEdge
```bash
sudo nano /opt/Solaredge_ScanWriter/.env
```

Modifica almeno questi parametri:
```bash
SOLAREDGE_SITE_ID=123456
SOLAREDGE_USERNAME=your.email@example.com
SOLAREDGE_PASSWORD=your_password
SOLAREDGE_API_KEY=your_api_key
```

### 2. Testa l'Installazione
```bash
/opt/Solaredge_ScanWriter/test.sh
```

### 3. Avvia il Servizio
```bash
sudo systemctl enable --now solaredge-scanwriter
```

### 4. Controlla lo Stato
```bash
/opt/Solaredge_ScanWriter/status.sh
```

## Accesso ai Servizi

Una volta avviato il servizio, puoi accedere a:

- **SolarEdge GUI**: `http://IP_CONTAINER:8092`
- **InfluxDB**: `http://IP_CONTAINER:8086` (admin/solaredge123)
- **Grafana**: `http://IP_CONTAINER:3000` (admin/admin)

## Importare la Dashboard SolarEdge

Dopo l'installazione, importa la dashboard in Grafana:

1. Vai su `http://IP_CONTAINER:3000` (admin/admin)
2. Clicca **"+" → Import**
3. Clicca **"Upload JSON file"**
4. Seleziona: `/opt/Solaredge_ScanWriter/grafana/dashboard-solaredge.json`
5. Clicca **"Import"**

## Comandi Utili

```bash
# Visualizza log in tempo reale
sudo journalctl -u solaredge-scanwriter -f

# Riavvia il servizio
sudo systemctl restart solaredge-scanwriter

# Ferma il servizio
sudo systemctl stop solaredge-scanwriter

# Stato completo del sistema
/opt/Solaredge_ScanWriter/status.sh

# Status check
/opt/Solaredge_ScanWriter/status.sh
```

## Modalità di Test

Per testare singole funzionalità:

```bash
cd /opt/Solaredge_ScanWriter

# Test API SolarEdge
python3 main.py --api

# Test Web Scraping
python3 main.py --web

# Test Real-time (Modbus)
python3 main.py --realtime

# Scansione configurazione web
python3 main.py --scan
```

## Risoluzione Problemi

### Servizio non si avvia
```bash
# Controlla log errori
sudo journalctl -u solaredge-scanwriter --since "10 minutes ago"

# Verifica configurazione
sudo nano /opt/Solaredge_ScanWriter/.env

# Test manuale
cd /opt/Solaredge_ScanWriter
python3 main.py
```

### InfluxDB non funziona
```bash
# Stato servizio
sudo systemctl status influxdb

# Riavvia InfluxDB
sudo systemctl restart influxdb

# Test connessione
curl -I http://localhost:8086/health
```

### Grafana non accessibile
```bash
# Stato servizio
sudo systemctl status grafana-server

# Riavvia Grafana
sudo systemctl restart grafana-server

# Test porta
netstat -tlnp | grep 3000
```

## Installazione Alternativa

Se il one-liner non funziona, puoi usare:

```bash
# Metodo 2: Download manuale
git clone https://github.com/frezeen/Solaredge_ScanWriter.git
cd Solaredge_ScanWriter
chmod +x install.sh
./install.sh
```

## Supporto

Per problemi o domande:
1. Controlla i log: `sudo journalctl -u solaredge-scanwriter -f`
2. Controlla status: `/opt/Solaredge_ScanWriter/status.sh`
3. Verifica configurazione: `nano /opt/Solaredge_ScanWriter/.env`