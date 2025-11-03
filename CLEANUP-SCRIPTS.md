# 🧹 Script di Pulizia Debian

## 📋 Panoramica Script

### 1. `debian-clean-machine.sh` - Pulizia Completa
**⚠️ ATTENZIONE: OPERAZIONE NON REVERSIBILE!**

Rimuove completamente:
- ✅ Tutti i container Docker
- ✅ Tutte le immagini Docker  
- ✅ Tutti i volumi Docker
- ✅ Tutti i network Docker
- ✅ Docker Engine completamente
- ✅ Tutte le directory del progetto SolarEdge
- ✅ Cache e file temporanei
- ✅ Configurazioni residue

**Quando usarlo:**
- Prima installazione su macchina nuova
- Problemi gravi con Docker
- Reset completo per test puliti
- Preparazione macchina per altri progetti

### 2. `debian-clean-project.sh` - Pulizia Progetto
**✅ Operazione sicura - mantiene Docker**

Rimuove solo:
- ✅ Container SolarEdge
- ✅ Immagini SolarEdge
- ✅ Volumi SolarEdge  
- ✅ Network SolarEdge
- ✅ Directory progetto SolarEdge
- ✅ Cache progetto SolarEdge

**Quando usarlo:**
- Reset del progetto mantenendo Docker
- Pulizia prima di nuovi test
- Rimozione progetto senza toccare altri container
- Sviluppo iterativo

## 🚀 Utilizzo

### Pulizia Completa Macchina
```bash
# Rendi eseguibile
chmod +x debian-clean-machine.sh

# Esegui (richiede conferma)
./debian-clean-machine.sh

# Conferma digitando: PULISCI
```

### Pulizia Solo Progetto
```bash
# Rendi eseguibile  
chmod +x debian-clean-project.sh

# Esegui (richiede conferma)
./debian-clean-project.sh

# Conferma con: y
```

## 🔒 Sicurezza

### Conferme Richieste

**`debian-clean-machine.sh`:**
- Richiede di digitare `PULISCI` per confermare
- Mostra chiaramente cosa verrà rimosso
- Avvisa che l'operazione non è reversibile

**`debian-clean-project.sh`:**
- Richiede conferma `[y/N]` per procedere
- Chiede conferma per ogni directory trovata
- Mostra cosa mantiene (Docker Engine)

### Backup Automatico
Gli script NON fanno backup automatici. Se hai dati importanti:

```bash
# Backup volumi Docker prima della pulizia
docker run --rm -v solaredge-data:/data -v $(pwd):/backup alpine tar czf /backup/solaredge-backup.tar.gz /data

# Backup directory progetto
tar czf solaredge-project-backup.tar.gz Solaredge_ScanWriter/
```

## 🔍 Verifica Post-Pulizia

### Dopo `debian-clean-machine.sh`
```bash
# Verifica Docker rimosso
docker --version  # Dovrebbe dare errore

# Verifica directory rimosse
ls -la /var/lib/docker  # Dovrebbe dare errore

# Verifica processi
ps aux | grep docker  # Nessun risultato
```

### Dopo `debian-clean-project.sh`
```bash
# Verifica Docker funzionante
docker --version  # Dovrebbe mostrare versione

# Verifica container SolarEdge rimossi
docker ps -a | grep solaredge  # Nessun risultato

# Verifica immagini SolarEdge rimosse
docker images | grep solaredge  # Nessun risultato
```

## 🔄 Reinstallazione Post-Pulizia

### Dopo Pulizia Completa
```bash
# 1. Clone progetto
git clone https://github.com/frezeen/Solaredge_ScanWriter.git
cd Solaredge_ScanWriter
git checkout dev

# 2. Setup completo (installa Docker + progetto)
chmod +x dev-docker-rebuild.sh
./dev-docker-rebuild.sh
```

### Dopo Pulizia Progetto
```bash
# 1. Clone progetto (se rimosso)
git clone https://github.com/frezeen/Solaredge_ScanWriter.git
cd Solaredge_ScanWriter
git checkout dev

# 2. Setup rapido (Docker già installato)
chmod +x dev-docker-rebuild.sh
./dev-docker-rebuild.sh
```

## 🐛 Troubleshooting

### Script Non Eseguibile
```bash
# Problema: Permission denied
chmod +x debian-clean-*.sh

# Verifica permessi
ls -la debian-clean-*.sh
```

### Docker Non Si Rimuove
```bash
# Forza stop servizi
sudo systemctl stop docker docker.socket containerd

# Rimozione manuale
sudo apt-get purge -y docker* containerd*
sudo rm -rf /var/lib/docker
```

### Directory Non Si Rimuovono
```bash
# Verifica processi che usano la directory
sudo lsof +D /path/to/directory

# Forza rimozione
sudo rm -rf /path/to/directory
```

### Permessi Insufficienti
```bash
# Esegui con sudo se necessario
sudo ./debian-clean-machine.sh

# O cambia proprietario
sudo chown $USER:$USER debian-clean-*.sh
```

## ⚠️ Avvertenze Importanti

1. **`debian-clean-machine.sh` è IRREVERSIBILE**
   - Rimuove tutto Docker dalla macchina
   - Perdi tutti i container, immagini, volumi
   - Richiede reinstallazione completa

2. **Backup Prima della Pulizia**
   - Salva dati importanti prima di procedere
   - Gli script non fanno backup automatici

3. **Verifica Directory Corrente**
   - Non eseguire dalla directory del progetto se vuoi mantenerla
   - `debian-clean-project.sh` può rimuovere la directory corrente

4. **Riavvio Raccomandato**
   - Dopo `debian-clean-machine.sh` riavvia la sessione
   - Alcuni servizi potrebbero richiedere riavvio completo

## 📞 Supporto

Se gli script non funzionano correttamente:

1. Verifica i log degli script (output dettagliato)
2. Controlla permessi file e directory
3. Verifica spazio disco disponibile
4. Prova esecuzione manuale dei comandi singoli