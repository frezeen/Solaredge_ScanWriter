#!/bin/bash
# Script di sviluppo per Debian - Pulizia completa e rebuild Docker
# Uso: ./dev-docker-rebuild.sh

set -e

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo -e "${CYAN}================================${NC}"
echo -e "${CYAN} SolarEdge Docker Dev Rebuild${NC}"
echo -e "${CYAN}================================${NC}"
echo ""

# 0. AGGIORNAMENTO GIT
log_info "🔄 Aggiornamento codice da Git..."

# Verifica se siamo in un repository git
if [[ ! -d ".git" ]]; then
    log_error "❌ Non siamo in un repository Git!"
    log_info "Assicurati di essere nella directory del progetto SolarEdge"
    exit 1
fi

# Salva eventuali modifiche locali
if ! git diff --quiet || ! git diff --cached --quiet; then
    log_warning "⚠️  Rilevate modifiche locali non committate"
    log_info "Salvando modifiche locali in stash..."
    git stash push -m "Auto-stash before rebuild $(date)"
fi

# Fetch ultime modifiche
log_info "Scaricando ultime modifiche..."
git fetch origin

# Verifica branch corrente
current_branch=$(git branch --show-current)
log_info "Branch corrente: $current_branch"

# Pull delle ultime modifiche
if git pull origin "$current_branch"; then
    log_success "✅ Codice aggiornato da Git"
else
    log_error "❌ Errore nell'aggiornamento Git"
    log_info "Continuando con il codice locale..."
fi

echo ""

# 1. PULIZIA COMPLETA DOCKER
log_info "🧹 Pulizia completa Docker..."

# Ferma tutti i container SolarEdge
log_info "Fermando container SolarEdge..."
docker ps -a --filter "name=solaredge" --format "{{.Names}}" | xargs -r docker stop 2>/dev/null || true

# Rimuovi tutti i container SolarEdge
log_info "Rimuovendo container SolarEdge..."
docker ps -a --filter "name=solaredge" --format "{{.Names}}" | xargs -r docker rm -f 2>/dev/null || true

# Rimuovi tutte le immagini SolarEdge
log_info "Rimuovendo immagini SolarEdge..."
docker images --filter "reference=*solaredge*" --format "{{.Repository}}:{{.Tag}}" | xargs -r docker rmi -f 2>/dev/null || true
docker images --filter "reference=*collector*" --format "{{.Repository}}:{{.Tag}}" | xargs -r docker rmi -f 2>/dev/null || true

# Ferma e rimuovi stack docker-compose
log_info "Fermando stack docker-compose..."
docker compose down --remove-orphans --volumes 2>/dev/null || true

# Rimuovi volumi SolarEdge
log_info "Rimuovendo volumi SolarEdge..."
docker volume ls --filter "name=solaredge" --format "{{.Name}}" | xargs -r docker volume rm 2>/dev/null || true

# Rimuovi network SolarEdge
log_info "Rimuovendo network SolarEdge..."
docker network ls --filter "name=solaredge" --format "{{.Name}}" | xargs -r docker network rm 2>/dev/null || true

# Pulizia generale Docker
log_info "Pulizia generale Docker..."
docker system prune -f --volumes 2>/dev/null || true

log_success "✅ Pulizia Docker completata"
echo ""

# 2. VERIFICA CONFIGURAZIONE
log_info "🔍 Verifica configurazione..."

if [[ ! -f ".env" ]]; then
    if [[ -f ".env.example" ]]; then
        log_warning "File .env non trovato, copiando da .env.example"
        cp .env.example .env
        log_warning "⚠️  IMPORTANTE: Modifica .env con le tue credenziali SolarEdge!"
        echo ""
        echo -e "${YELLOW}Credenziali richieste in .env:${NC}"
        echo -e "${CYAN}SOLAREDGE_SITE_ID=123456${NC}"
        echo -e "${CYAN}SOLAREDGE_API_KEY=your_api_key${NC}"
        echo -e "${CYAN}SOLAREDGE_USERNAME=your.email@example.com${NC}"
        echo -e "${CYAN}SOLAREDGE_PASSWORD=your_password${NC}"
        echo ""
        read -p "Premi ENTER dopo aver configurato .env per continuare..."
    else
        log_error "❌ File .env.example non trovato!"
        exit 1
    fi
fi

# Verifica file essenziali
required_files=("Dockerfile" "docker-compose.yml" "requirements.txt" "main.py")
for file in "${required_files[@]}"; do
    if [[ ! -f "$file" ]]; then
        log_error "❌ File mancante: $file"
        exit 1
    fi
done

log_success "✅ Configurazione verificata"
echo ""

# 3. BUILD MULTI-ARCHITETTURA
log_info "🏗️  Build immagine Docker multi-architettura..."

# Configura buildx se necessario
if ! docker buildx ls | grep -q "solaredge-builder"; then
    log_info "Configurando Docker Buildx..."
    docker buildx create --name solaredge-builder --use --bootstrap
fi

# Build per architetture multiple
log_info "Building per linux/amd64,linux/arm64,linux/arm/v7..."
docker buildx build \
    --platform linux/amd64,linux/arm64,linux/arm/v7 \
    --tag solaredge-collector:latest \
    --tag solaredge-collector:dev \
    --load \
    .

if [[ $? -eq 0 ]]; then
    log_success "✅ Build multi-architettura completata"
else
    log_warning "⚠️  Build multi-arch fallito, provo build singola architettura..."
    docker build -t solaredge-collector:latest -t solaredge-collector:dev .
    log_success "✅ Build singola architettura completata"
fi

echo ""

# 4. AVVIO STACK
log_info "🚀 Avvio stack Docker..."

# Avvia solo i servizi base (senza Grafana per default)
docker compose up -d

if [[ $? -eq 0 ]]; then
    log_success "✅ Stack avviato con successo"
else
    log_error "❌ Errore nell'avvio dello stack"
    log_info "Mostrando log per debug..."
    docker compose logs --tail=20
    exit 1
fi

echo ""

# 5. VERIFICA SERVIZI
log_info "🔍 Verifica servizi..."

# Attendi che i servizi siano pronti
sleep 10

# Verifica container in esecuzione
log_info "Container in esecuzione:"
docker compose ps

echo ""

# Test connessioni
log_info "🧪 Test connessioni..."

# Test GUI
if curl -f http://localhost:8092/health >/dev/null 2>&1; then
    log_success "✅ GUI SolarEdge: http://localhost:8092"
else
    log_warning "⚠️  GUI SolarEdge non ancora disponibile"
fi

# Test InfluxDB
if curl -f http://localhost:8086/health >/dev/null 2>&1; then
    log_success "✅ InfluxDB: http://localhost:8086"
else
    log_warning "⚠️  InfluxDB non ancora disponibile"
fi

echo ""

# 6. INFORMAZIONI FINALI
log_success "🎉 Rebuild completato!"
echo ""
echo -e "${CYAN}📊 Servizi disponibili:${NC}"
echo -e "   GUI SolarEdge: ${YELLOW}http://localhost:8092${NC}"
echo -e "   InfluxDB:      ${YELLOW}http://localhost:8086${NC}"
echo ""
echo -e "${CYAN}📋 Comandi utili:${NC}"
echo -e "   ${YELLOW}docker compose logs -f${NC}           # Log in tempo reale"
echo -e "   ${YELLOW}docker compose ps${NC}                # Status servizi"
echo -e "   ${YELLOW}docker compose down${NC}              # Ferma tutto"
echo -e "   ${YELLOW}docker exec -it solaredge-collector bash${NC}  # Shell nel container"
echo ""
echo -e "${CYAN}🧪 Test componenti:${NC}"
echo -e "   ${YELLOW}docker exec solaredge-collector python main.py --api${NC}"
echo -e "   ${YELLOW}docker exec solaredge-collector python main.py --web${NC}"
echo -e "   ${YELLOW}docker exec solaredge-collector python main.py --scan${NC}"
echo ""

# Mostra log iniziali
log_info "📋 Log iniziali (ultimi 10 righe):"
docker compose logs --tail=10 solaredge

echo ""
log_success "🎯 Sviluppo Docker pronto!"