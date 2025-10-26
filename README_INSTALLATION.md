# SolarEdge Data Collector - Guida Installazione

## Installazione One-Liner (Raccomandato)

Dal tuo container Debian/Ubuntu, esegui semplicemente:

```bash
curl -sSL https://raw.githubusercontent.com/frezeen/Solaredge_ScanWriter/main/install.sh | sudo bash
```

**Nota**: Lo script richiede privilegi root per installare pacchetti di sistema e configurare servizi.

Questo comando fa tutto automaticamente:
- ✅ Scarica il progetto completo da GitHub
- ✅ Installa tutte le dipendenze (Python, InfluxDB, Grafana)
- ✅ Configura tutti i servizi
- ✅ Crea utente e directory necessarie
- ✅ Configura firewall e servizi systemd

## Installazione Manuale (Alternativa)

Se preferisci l'installazione manuale:

```bash
# Clona il repository
git clone https://github.com/frezeen/Solaredge_ScanWriter.git
cd Solaredge_ScanWriter

# Configura permessi automaticamente (RACCOMANDATO)
chmod +x setup-permissions.sh
./setup-permissions.sh

# OPPURE configura manualmente
chmod +x install.sh

# Esegui l'installazione
./install.sh
```

### Configurazione Permessi Automatica

Il progetto include un sistema per mantenere automaticamente i permessi di esecuzione:

```bash
# Dopo il clone, esegui UNA VOLTA:
./setup-permissions.sh
```

Questo configura:
- ✅ Permessi di esecuzione su tutti gli script
- ✅ Git hooks per ripristino automatico dopo `git pull`
- ✅ Configurazione Git ottimale

**Risultato**: Non dovrai più fare `chmod +x` manualmente!

### 3. Configurazione

```bash
# Modifica il file di configurazione
nano /opt/solaredge-collector/.env

# Configura almeno questi parametri:
# SOLAREDGE_SITE_ID=123456
# SOLAREDGE_USERNAME=your.email@example.com
# SOLAREDGE_PASSWORD=your_password
# SOLAREDGE_API_KEY=your_api_key
# INFLUXDB_URL=http://your-influxdb:8086
# INFLUXDB_TOKEN=your_influxdb_token
# INFLUXDB_ORG=fotovoltaico
# INFLUXDB_BUCKET=solaredge_test
```

### 4. Test e Avvio

```bash
# Test delle funzionalità
cd /opt/solaredge-collector
./test.sh

# Abilita e avvia il servizio
systemctl enable --now solaredge-collector

# Verifica lo stato
./status.sh
```

## Installazione Manuale Dettagliata

### 1. Preparazione Sistema

```bash
# Aggiorna pacchetti
apt update && apt upgrade -y

# Installa dipendenze sistema
apt install -y python3 python3-pip python3-dev \
               build-essential curl wget git nano htop systemd cron

# Verifica versione Python (richiesta 3.10+)
python3 --version
```

### 2. Creazione Utente e Directory

```bash
# Crea utente applicazione
useradd --create-home --shell /bin/bash --groups sudo solaredge

# Crea directory applicazione
mkdir -p /opt/solaredge-collector
chown solaredge:solaredge /opt/solaredge-collector
```

### 3. Installazione Applicazione

```bash
# Copia file applicazione
cp -r . /opt/solaredge-collector/
chown -R solaredge:solaredge /opt/solaredge-collector

# Installa dipendenze Python system-wide
pip3 install -r /opt/solaredge-collector/requirements.txt --break-system-packages
```

### 4. Configurazione Servizi Systemd

Il servizio principale:
```bash
systemctl enable solaredge-collector
systemctl start solaredge-collector
```

#### Permessi per Controllo Servizio (Opzionale)

Per permettere all'utente `solaredge` di controllare il servizio senza sudo (utile per update automatici):

```bash
# Installa regola polkit
sudo cp systemd/solaredge-user-service.conf /etc/polkit-1/rules.d/10-solaredge-service.rules
sudo systemctl restart polkit

# Ora l'utente solaredge può controllare il servizio senza sudo
sudo -u solaredge systemctl stop solaredge-collector
sudo -u solaredge systemctl start solaredge-collector
```

## Configurazione

### File .env Principale

Copia `.env.example` in `.env` e configura:

```bash
# === Identificazione Sito (OBBLIGATORIO) ===
SOLAREDGE_SITE_ID=123456
SOLAREDGE_SITE_NAME="My Solar Site"

# === Credenziali Web SolarEdge (OBBLIGATORIO per web scraping) ===
SOLAREDGE_USERNAME=your.username@example.com
SOLAREDGE_PASSWORD=REPLACE_ME

# === API Ufficiale SolarEdge (OBBLIGATORIO se usi API) ===
SOLAREDGE_API_KEY=REPLACE_ME

# === InfluxDB Storage (OBBLIGATORIO) ===
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=your-auto-generated-token
INFLUXDB_ORG=fotovoltaico
INFLUXDB_BUCKET=solaredge_test

# === Modbus (Opzionale per dati real-time) ===
MODBUS_HOST=192.168.1.100
MODBUS_PORT=1502
MODBUS_UNIT_ID=1
```

### Configurazione InfluxDB e Grafana

Lo script di installazione configura automaticamente:

- **InfluxDB 2.x** su porta 8086
- **Grafana** su porta 3000
- **Datasource** InfluxDB configurato automaticamente in Grafana

#### Accesso ai Servizi

```bash
# InfluxDB Web UI
http://IP_CONTAINER:8086
# Credenziali: admin / solaredge123
# Org: fotovoltaico
# Bucket: solaredge_test

# Grafana Dashboard
http://IP_CONTAINER:3000
# Credenziali: admin / admin (cambiale al primo accesso)
```

#### Controllo Servizi

```bash
# Stato InfluxDB
sudo systemctl status influxdb

# Stato Grafana
sudo systemctl status grafana-server

# Restart servizi se necessario
sudo systemctl restart influxdb
sudo systemctl restart grafana-server
```

#### Importare la Dashboard SolarEdge in Grafana

Dopo l'installazione, importa la dashboard tramite Web UI:

1. Accedi a Grafana: `http://IP_CONTAINER:3000` (admin/admin)
2. Vai su **"+" → Import**
3. Clicca **"Upload JSON file"**
4. Seleziona il file: `/opt/solaredge-collector/grafana/dashboard-solaredge.json`
5. Clicca **"Import"**

## Modalità di Esecuzione

### 1. Modalità Test (Singola Esecuzione)

```bash
cd /opt/solaredge-collector

# Test API
python3 main.py --api

# Test Web Scraping
python3 main.py --web

# Test Real-time (Modbus)
python3 main.py --realtime
```

### 2. Modalità Interattiva (GUI + Loop controllabile)

```bash
# Avvia GUI interattiva (modalità predefinita senza argomenti)
python3 main.py

# La GUI include controlli per start/stop del loop
```

Accedi a: `http://IP_CONTAINER:8092`

### 3. Modalità Produzione (GUI + Loop 24/7)

```bash
# Avvia servizio completo (GUI + Loop automatico)
systemctl start solaredge-collector

# Verifica stato
systemctl status solaredge-collector

# Accedi alla GUI
# http://IP_CONTAINER:8092
```

## Monitoraggio e Manutenzione

### Log e Diagnostica

```bash
# Visualizza log in tempo reale
journalctl -u solaredge-collector -f

# Log degli ultimi errori
journalctl -u solaredge-collector --since "1 hour ago" -p err

# Stato del servizio
systemctl status solaredge-collector
```

### Script di Utilità

```bash
# Stato completo
/opt/solaredge-collector/status.sh

# Test funzionalità
/opt/solaredge-collector/test.sh

# Avvio/Stop
/opt/solaredge-collector/start.sh
/opt/solaredge-collector/stop.sh
```

### Manutenzione Automatica

Il sistema include:
- Rotazione log automatica (7 giorni)
- Pulizia cache automatica (7 giorni)
- Monitoraggio memoria e restart automatico
- Cron job di manutenzione giornaliera

## Risoluzione Problemi

### Problemi Comuni

1. **Errore Python Version**
   ```bash
   # Verifica versione
   python3 --version
   # Deve essere >= 3.10
   ```

2. **Errore Dipendenze**
   ```bash
   # Reinstalla dipendenze
   cd /opt/solaredge-collector
   pip3 install -r requirements.txt --force-reinstall --break-system-packages
   ```

3. **Errore Connessione InfluxDB**
   ```bash
   # Testa connessione locale
   curl -I http://localhost:8086/health
   
   # Verifica servizio
   sudo systemctl status influxdb
   
   # Restart se necessario
   sudo systemctl restart influxdb
   ```

4. **Errore Credenziali SolarEdge**
   ```bash
   # Verifica credenziali nel file .env
   nano /opt/solaredge-collector/.env
   ```

### Log di Debug

```bash
# Abilita debug nel .env
LOG_LEVEL=DEBUG

# Riavvia servizio
systemctl restart solaredge-collector

# Visualizza log dettagliati
journalctl -u solaredge-collector -f
```

## Aggiornamenti

```bash
# Ferma servizio
systemctl stop solaredge-collector

# Backup configurazione
cp /opt/solaredge-collector/.env /tmp/env_backup

# Aggiorna codice
cd /opt/solaredge-collector
git pull

# Aggiorna dipendenze
pip3 install -r requirements.txt --upgrade --break-system-packages

# Riavvia servizio
systemctl start solaredge-collector
```

## Sicurezza

### Firewall

```bash
# Abilita firewall
ufw enable

# Permetti GUI (se necessario)
ufw allow 8092/tcp

# Permetti SSH
ufw allow ssh
```

### Permessi File

```bash
# Verifica permessi
ls -la /opt/solaredge-collector/

# Correggi se necessario
chown -R solaredge:solaredge /opt/solaredge-collector/
chmod 600 /opt/solaredge-collector/.env
```

## Supporto

Per problemi o domande:
1. Controlla i log: `journalctl -u solaredge-collector -f`
2. Verifica configurazione: `nano /opt/solaredge-collector/.env`
3. Testa singole funzionalità: `/opt/solaredge-collector/test.sh`
4. Controlla stato servizi: `/opt/solaredge-collector/status.sh`
#
# Troubleshooting

### Common Issues

1. **Permission denied errors**: Make sure you're running as root or with sudo
2. **InfluxDB connection failed**: Check if InfluxDB is running with `systemctl status influxdb`
3. **Python import errors**: Verify virtual environment activation
4. **Service won't start**: Check logs with `journalctl -u solaredge-scanwriter.service -f`

### pymodbus Dependency Conflict

If you see the error: `cannot import name 'Endian' from 'pymodbus.constants'`

**Quick Fix:**
```bash
# I problemi di dipendenze vengono risolti automaticamente
# dal sistema di update durante l'aggiornamento
./update.sh
```

**Manual Fix:**
```bash
cd /opt/Solaredge_ScanWriter
sudo systemctl stop solaredge-scanwriter.service
pip3 cache purge
pip3 uninstall -y pymodbus solaredge-modbus
pip3 install pymodbus==3.5.4 --break-system-packages
pip3 install solaredge-modbus==0.8.0 --break-system-packages
sudo systemctl start solaredge-scanwriter.service
```

### Checking Service Status

```bash
# Check service status
sudo systemctl status solaredge-scanwriter.service

# View real-time logs
sudo journalctl -u solaredge-scanwriter.service -f

# Check InfluxDB status
sudo systemctl status influxdb

# Check Grafana status
sudo systemctl status grafana-server
```