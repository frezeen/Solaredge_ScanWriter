#!/bin/bash
# Script per pulire completamente la macchina Debian
# Rimuove Docker, containers, immagini, volumi, network e tutto il progetto SolarEdge
# ATTENZIONE: Questo script rimuove TUTTO Docker dalla macchina!

set -e

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_header() { echo -e "${MAGENTA}$1${NC}"; }

echo -e "${RED}⚠️  ATTENZIONE: PULIZIA COMPLETA MACCHINA DEBIAN ⚠️${NC}"
echo -e "${RED}=================================================${NC}"
echo ""
echo -e "${YELLOW}Questo script rimuoverà:${NC}"
echo -e "${CYAN}- Tutti i container Docker${NC}"
echo -e "${CYAN}- Tutte le immagini Docker${NC}"
echo -e "${CYAN}- Tutti i volumi Docker${NC}"
echo -e "${CYAN}- Tutti i network Docker${NC}"
echo -e "${CYAN}- Docker Engine completamente${NC}"
echo -e "${CYAN}- Tutte le directory del progetto SolarEdge${NC}"
echo -e "${CYAN}- Cache e file temporanei${NC}"
echo ""
echo -e "${RED}⚠️  QUESTA OPERAZIONE NON È REVERSIBILE! ⚠️${NC}"
echo ""

# Conferma dall'utente
read -p "Sei sicuro di voler procedere? Digita 'PULISCI' per confermare: " confirm
if [[ "$confirm" != "PULISCI" ]]; then
    log_info "Operazione annullata dall'utente"
    exit 0
fi

echo ""
log_header "🧹 INIZIO PULIZIA COMPLETA MACCHINA DEBIAN"
echo ""

# 1. FERMA TUTTI I SERVIZI DOCKER
log_info "🛑 Fermando tutti i servizi Docker..."

if command -v docker &> /dev/null; then
    # Ferma tutti i container in esecuzione
    log_info "Fermando tutti i container..."
    docker ps -q | xargs -r docker stop 2>/dev/null || true
    
    # Rimuovi tutti i container
    log_info "Rimuovendo tutti i container..."
    docker ps -aq | xargs -r docker rm -f 2>/dev/null || true
    
    # Rimuovi tutte le immagini
    log_info "Rimuovendo tutte le immagini Docker..."
    docker images -q | xargs -r docker rmi -f 2>/dev/null || true
    
    # Rimuovi tutti i volumi
    log_info "Rimuovendo tutti i volumi Docker..."
    docker volume ls -q | xargs -r docker volume rm -f 2>/dev/null || true
    
    # Rimuovi tutti i network personalizzati
    log_info "Rimuovendo tutti i network Docker..."
    docker network ls --filter type=custom -q | xargs -r docker network rm 2>/dev/null || true
    
    # Pulizia completa sistema Docker
    log_info "Pulizia completa sistema Docker..."
    docker system prune -af --volumes 2>/dev/null || true
    
    # Ferma il servizio Docker
    log_info "Fermando servizio Docker..."
    sudo systemctl stop docker 2>/dev/null || true
    sudo systemctl stop docker.socket 2>/dev/null || true
    sudo systemctl stop containerd 2>/dev/null || true
    
    log_success "✅ Servizi Docker fermati"
else
    log_info "Docker non installato, saltando pulizia container"
fi

echo ""

# 2. RIMOZIONE COMPLETA DOCKER
log_info "🗑️  Rimozione completa Docker Engine..."

# Rimuovi pacchetti Docker
log_info "Rimuovendo pacchetti Docker..."
sudo apt-get purge -y docker-ce docker-ce-cli containerd.io docker-compose-plugin docker-buildx-plugin 2>/dev/null || true
sudo apt-get purge -y docker.io docker-doc docker-compose podman-docker containerd runc 2>/dev/null || true
sudo apt-get autoremove -y 2>/dev/null || true

# Rimuovi directory Docker
log_info "Rimuovendo directory Docker..."
sudo rm -rf /var/lib/docker 2>/dev/null || true
sudo rm -rf /var/lib/containerd 2>/dev/null || true
sudo rm -rf /etc/docker 2>/dev/null || true
sudo rm -rf /var/run/docker.sock 2>/dev/null || true
sudo rm -rf ~/.docker 2>/dev/null || true

# Rimuovi repository Docker
log_info "Rimuovendo repository Docker..."
sudo rm -f /etc/apt/sources.list.d/docker.list 2>/dev/null || true
sudo rm -f /usr/share/keyrings/docker-archive-keyring.gpg 2>/dev/null || true

# Rimuovi gruppo docker
log_info "Rimuovendo gruppo docker..."
sudo groupdel docker 2>/dev/null || true

log_success "✅ Docker completamente rimosso"
echo ""

# 3. PULIZIA PROGETTI SOLAREDGE
log_info "🗂️  Rimozione progetti SolarEdge..."

# Lista delle possibili directory del progetto
project_dirs=(
    "$HOME/Solaredge_ScanWriter"
    "$HOME/solaredge"
    "$HOME/solaredge-scanwriter"
    "$HOME/SolarEdge"
    "/opt/solaredge"
    "/var/lib/solaredge"
    "/tmp/solaredge*"
)

for dir in "${project_dirs[@]}"; do
    if [[ -d "$dir" ]] || [[ "$dir" == *"*"* ]]; then
        log_info "Rimuovendo: $dir"
        sudo rm -rf $dir 2>/dev/null || true
    fi
done

# Cerca altre directory che potrebbero contenere il progetto
log_info "Cercando altre directory SolarEdge..."
find /home -name "*solaredge*" -type d 2>/dev/null | while read -r dir; do
    if [[ -n "$dir" ]]; then
        log_info "Trovata directory: $dir"
        sudo rm -rf "$dir" 2>/dev/null || true
    fi
done

log_success "✅ Progetti SolarEdge rimossi"
echo ""

# 4. PULIZIA CACHE E FILE TEMPORANEI
log_info "🧽 Pulizia cache e file temporanei..."

# Cache apt
log_info "Pulizia cache APT..."
sudo apt-get clean 2>/dev/null || true
sudo apt-get autoclean 2>/dev/null || true

# File temporanei
log_info "Pulizia file temporanei..."
sudo rm -rf /tmp/docker* 2>/dev/null || true
sudo rm -rf /tmp/solaredge* 2>/dev/null || true
sudo rm -rf /var/tmp/docker* 2>/dev/null || true

# Log di sistema relativi a Docker
log_info "Pulizia log Docker..."
sudo rm -rf /var/log/docker* 2>/dev/null || true
sudo journalctl --vacuum-time=1d 2>/dev/null || true

# Cache utente
log_info "Pulizia cache utente..."
rm -rf ~/.cache/docker* 2>/dev/null || true
rm -rf ~/.local/share/docker* 2>/dev/null || true

log_success "✅ Cache e file temporanei puliti"
echo ""

# 5. PULIZIA CONFIGURAZIONI RESIDUE
log_info "⚙️  Pulizia configurazioni residue..."

# File di configurazione utente
rm -rf ~/.docker 2>/dev/null || true
rm -rf ~/.dockercfg 2>/dev/null || true

# Variabili d'ambiente Docker nel profilo
log_info "Rimuovendo variabili Docker dai profili..."
sed -i '/DOCKER/d' ~/.bashrc 2>/dev/null || true
sed -i '/docker/d' ~/.bashrc 2>/dev/null || true
sed -i '/DOCKER/d' ~/.profile 2>/dev/null || true
sed -i '/docker/d' ~/.profile 2>/dev/null || true

# Alias Docker
sed -i '/alias.*docker/d' ~/.bashrc 2>/dev/null || true
sed -i '/alias.*docker/d' ~/.bash_aliases 2>/dev/null || true

log_success "✅ Configurazioni residue pulite"
echo ""

# 6. AGGIORNAMENTO SISTEMA
log_info "🔄 Aggiornamento sistema..."

sudo apt-get update 2>/dev/null || true
sudo apt-get upgrade -y 2>/dev/null || true
sudo apt-get autoremove -y 2>/dev/null || true
sudo apt-get autoclean 2>/dev/null || true

log_success "✅ Sistema aggiornato"
echo ""

# 7. VERIFICA PULIZIA
log_info "🔍 Verifica pulizia completata..."

# Verifica Docker rimosso
if ! command -v docker &> /dev/null; then
    log_success "✅ Docker completamente rimosso"
else
    log_warning "⚠️  Docker ancora presente nel sistema"
fi

# Verifica directory Docker
if [[ ! -d "/var/lib/docker" ]]; then
    log_success "✅ Directory Docker rimosse"
else
    log_warning "⚠️  Alcune directory Docker ancora presenti"
fi

# Verifica processi Docker
if ! pgrep -f docker > /dev/null; then
    log_success "✅ Nessun processo Docker in esecuzione"
else
    log_warning "⚠️  Alcuni processi Docker ancora attivi"
fi

echo ""

# 8. RIEPILOGO FINALE
log_header "🎯 PULIZIA COMPLETA TERMINATA"
echo ""
log_success "✅ Tutti i container Docker rimossi"
log_success "✅ Tutte le immagini Docker rimosse"
log_success "✅ Tutti i volumi Docker rimossi"
log_success "✅ Docker Engine completamente disinstallato"
log_success "✅ Progetti SolarEdge rimossi"
log_success "✅ Cache e file temporanei puliti"
log_success "✅ Sistema aggiornato"
echo ""

log_info "🔄 La macchina Debian è ora pulita come una installazione fresca"
log_info "📋 Per reinstallare Docker e il progetto SolarEdge:"
echo ""
echo -e "${CYAN}# 1. Clone del progetto${NC}"
echo -e "${YELLOW}git clone https://github.com/frezeen/Solaredge_ScanWriter.git${NC}"
echo -e "${YELLOW}cd Solaredge_ScanWriter${NC}"
echo -e "${YELLOW}git checkout dev${NC}"
echo ""
echo -e "${CYAN}# 2. Setup automatico${NC}"
echo -e "${YELLOW}chmod +x dev-docker-rebuild.sh${NC}"
echo -e "${YELLOW}./dev-docker-rebuild.sh${NC}"
echo ""

log_warning "⚠️  Riavvia la sessione o riavvia il sistema per completare la pulizia"
echo ""
log_header "🎉 PULIZIA COMPLETATA CON SUCCESSO!"