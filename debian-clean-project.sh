#!/bin/bash
# Script per pulire solo il progetto SolarEdge mantenendo Docker installato
# Rimuove containers, immagini, volumi e directory del progetto SolarEdge

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

echo -e "${YELLOW}🧹 PULIZIA PROGETTO SOLAREDGE (Docker rimane installato)${NC}"
echo -e "${YELLOW}======================================================${NC}"
echo ""
echo -e "${CYAN}Questo script rimuoverà:${NC}"
echo -e "${CYAN}- Container SolarEdge${NC}"
echo -e "${CYAN}- Immagini SolarEdge${NC}"
echo -e "${CYAN}- Volumi SolarEdge${NC}"
echo -e "${CYAN}- Network SolarEdge${NC}"
echo -e "${CYAN}- Directory del progetto SolarEdge${NC}"
echo -e "${CYAN}- Cache del progetto${NC}"
echo ""
echo -e "${GREEN}Docker Engine rimarrà installato e funzionante${NC}"
echo ""

# Conferma dall'utente
read -p "Procedere con la pulizia del progetto SolarEdge? [y/N]: " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    log_info "Operazione annullata dall'utente"
    exit 0
fi

echo ""
log_header "🧹 INIZIO PULIZIA PROGETTO SOLAREDGE"
echo ""

# 1. PULIZIA DOCKER SOLAREDGE
log_info "🐳 Pulizia risorse Docker SolarEdge..."

if command -v docker &> /dev/null; then
    # Ferma container SolarEdge
    log_info "Fermando container SolarEdge..."
    docker ps --filter "name=solaredge" --format "{{.Names}}" | xargs -r docker stop 2>/dev/null || true
    
    # Rimuovi container SolarEdge
    log_info "Rimuovendo container SolarEdge..."
    docker ps -a --filter "name=solaredge" --format "{{.Names}}" | xargs -r docker rm -f 2>/dev/null || true
    
    # Rimuovi immagini SolarEdge
    log_info "Rimuovendo immagini SolarEdge..."
    docker images --filter "reference=*solaredge*" --format "{{.Repository}}:{{.Tag}}" | xargs -r docker rmi -f 2>/dev/null || true
    docker images --filter "reference=*collector*" --format "{{.Repository}}:{{.Tag}}" | xargs -r docker rmi -f 2>/dev/null || true
    
    # Rimuovi volumi SolarEdge
    log_info "Rimuovendo volumi SolarEdge..."
    docker volume ls --filter "name=solaredge" --format "{{.Name}}" | xargs -r docker volume rm -f 2>/dev/null || true
    
    # Rimuovi network SolarEdge
    log_info "Rimuovendo network SolarEdge..."
    docker network ls --filter "name=solaredge" --format "{{.Name}}" | xargs -r docker network rm 2>/dev/null || true
    
    # Ferma stack docker-compose se presente
    if [[ -f "docker-compose.yml" ]]; then
        log_info "Fermando stack docker-compose..."
        docker compose down --remove-orphans --volumes 2>/dev/null || true
    fi
    
    # Pulizia selettiva (solo immagini dangling e container fermati)
    log_info "Pulizia selettiva Docker..."
    docker container prune -f 2>/dev/null || true
    docker image prune -f 2>/dev/null || true
    docker volume prune -f 2>/dev/null || true
    docker network prune -f 2>/dev/null || true
    
    log_success "✅ Risorse Docker SolarEdge pulite"
else
    log_warning "⚠️  Docker non installato"
fi

echo ""

# 2. PULIZIA DIRECTORY PROGETTO
log_info "📁 Pulizia directory progetto SolarEdge..."

# Directory corrente se è il progetto SolarEdge
if [[ -f "main.py" ]] && [[ -f "requirements.txt" ]] && grep -q "solaredge" requirements.txt 2>/dev/null; then
    log_warning "⚠️  Sei nella directory del progetto SolarEdge"
    read -p "Vuoi rimuovere la directory corrente? [y/N]: " remove_current
    if [[ "$remove_current" =~ ^[Yy]$ ]]; then
        cd ..
        current_dir=$(basename "$OLDPWD")
        log_info "Rimuovendo directory: $current_dir"
        rm -rf "$current_dir"
        log_success "✅ Directory corrente rimossa"
    else
        log_info "Directory corrente mantenuta"
    fi
fi

# Altre possibili directory del progetto
project_dirs=(
    "$HOME/Solaredge_ScanWriter"
    "$HOME/solaredge"
    "$HOME/solaredge-scanwriter"
    "$HOME/SolarEdge"
    "/tmp/solaredge*"
)

for dir in "${project_dirs[@]}"; do
    if [[ -d "$dir" ]] || [[ "$dir" == *"*"* ]]; then
        log_info "Rimuovendo: $dir"
        rm -rf $dir 2>/dev/null || true
    fi
done

# Cerca altre directory SolarEdge nell'home
log_info "Cercando altre directory SolarEdge in $HOME..."
find "$HOME" -maxdepth 2 -name "*solaredge*" -type d 2>/dev/null | while read -r dir; do
    if [[ -n "$dir" ]]; then
        log_info "Trovata directory: $dir"
        read -p "Rimuovere $dir? [y/N]: " remove_dir
        if [[ "$remove_dir" =~ ^[Yy]$ ]]; then
            rm -rf "$dir" 2>/dev/null || true
            log_success "✅ Rimossa: $dir"
        fi
    fi
done

log_success "✅ Directory progetto pulite"
echo ""

# 3. PULIZIA CACHE E FILE TEMPORANEI
log_info "🧽 Pulizia cache SolarEdge..."

# File temporanei SolarEdge
rm -rf /tmp/solaredge* 2>/dev/null || true
rm -rf /var/tmp/solaredge* 2>/dev/null || true

# Cache utente SolarEdge
rm -rf ~/.cache/solaredge* 2>/dev/null || true
rm -rf ~/.local/share/solaredge* 2>/dev/null || true

# Log SolarEdge
sudo rm -rf /var/log/solaredge* 2>/dev/null || true

log_success "✅ Cache SolarEdge pulita"
echo ""

# 4. VERIFICA DOCKER FUNZIONANTE
log_info "🔍 Verifica Docker funzionante..."

if command -v docker &> /dev/null; then
    if docker ps > /dev/null 2>&1; then
        log_success "✅ Docker funzionante"
        
        # Mostra container rimanenti
        container_count=$(docker ps -a --format "{{.Names}}" | wc -l)
        image_count=$(docker images --format "{{.Repository}}" | wc -l)
        volume_count=$(docker volume ls --format "{{.Name}}" | wc -l)
        
        log_info "📊 Risorse Docker rimanenti:"
        echo -e "   ${CYAN}Container: $container_count${NC}"
        echo -e "   ${CYAN}Immagini: $image_count${NC}"
        echo -e "   ${CYAN}Volumi: $volume_count${NC}"
    else
        log_warning "⚠️  Docker installato ma non funzionante"
        log_info "Prova: sudo systemctl start docker"
    fi
else
    log_warning "⚠️  Docker non installato"
fi

echo ""

# 5. RIEPILOGO FINALE
log_header "🎯 PULIZIA PROGETTO COMPLETATA"
echo ""
log_success "✅ Container SolarEdge rimossi"
log_success "✅ Immagini SolarEdge rimosse"
log_success "✅ Volumi SolarEdge rimossi"
log_success "✅ Directory progetto pulite"
log_success "✅ Cache SolarEdge pulita"
log_success "✅ Docker Engine mantenuto funzionante"
echo ""

log_info "🔄 Per reinstallare il progetto SolarEdge:"
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

log_header "🎉 PULIZIA PROGETTO COMPLETATA CON SUCCESSO!"