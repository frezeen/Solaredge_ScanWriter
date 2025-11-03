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

# Rilevamento automatico architettura
log_info "🔍 Rilevamento automatico architettura..."
chmod +x detect-arch.sh
source detect-arch.sh
detect_system_arch
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
        log_warning "File .env non trovato, copiando TUTTO il contenuto da .env.example"
        cp .env.example .env
        log_success "✅ Copiato file .env completo con tutte le configurazioni"
        echo ""
        log_warning "⚠️  IMPORTANTE: Configura le credenziali SolarEdge nel file .env"
        echo ""
        echo -e "${YELLOW}Variabili OBBLIGATORIE da modificare:${NC}"
        echo -e "${CYAN}SOLAREDGE_SITE_ID=123456${NC} → Il tuo Site ID"
        echo -e "${CYAN}SOLAREDGE_API_KEY=YOUR_API_KEY_HERE${NC} → La tua API Key"
        echo -e "${CYAN}SOLAREDGE_USERNAME=your.email@example.com${NC} → La tua email"
        echo -e "${CYAN}SOLAREDGE_PASSWORD=YOUR_PASSWORD_HERE${NC} → La tua password"
        echo ""
        echo -e "${GREEN}Tutte le altre configurazioni sono già ottimizzate per Docker!${NC}"
        echo ""
        log_info "📝 Aprendo nano per modificare SOLO le credenziali..."
        sleep 3
        nano .env
        echo ""
        log_info "✅ Configurazione .env completata"
    else
        log_error "❌ File .env.example non trovato!"
        exit 1
    fi
else
    log_info "File .env già esistente, verifico che sia completo..."
    
    # Verifica che il .env contenga tutte le variabili del .env.example
    missing_vars=()
    while IFS= read -r line; do
        if [[ "$line" =~ ^[A-Z_]+=.* ]]; then
            var_name=$(echo "$line" | cut -d'=' -f1)
            if ! grep -q "^$var_name=" .env; then
                missing_vars+=("$var_name")
            fi
        fi
    done < .env.example
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        log_warning "⚠️  Il file .env esistente è incompleto!"
        log_warning "Variabili mancanti: ${missing_vars[*]}"
        log_info "Ricreo .env completo da .env.example..."
        cp .env.example .env
        log_info "📝 Apri nano per riconfigurare le credenziali..."
        nano .env
    else
        log_success "✅ File .env completo trovato"
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

# Fix terminatori di riga e verifica configurazione
sed -i 's/\r$//' .env 2>/dev/null || true
chmod +x check-env.sh
if ! ./check-env.sh; then
    nano .env
    sed -i 's/\r$//' .env 2>/dev/null || true
    ./check-env.sh || exit 1
fi
log_success "✅ Configurazione verificata"
echo ""

# 3. BUILD AUTOMATICO BASATO SU ARCHITETTURA
log_info "🏗️  Build immagine Docker (rilevamento automatico architettura)..."

# Rileva sistema operativo e architettura
os_type=$(uname -s 2>/dev/null || echo "Unknown")
current_arch=$(uname -m 2>/dev/null || echo "Unknown")

# Rilevamento specifico per Windows
if [[ "$os_type" == "MINGW"* ]] || [[ "$os_type" == "MSYS"* ]] || [[ "$os_type" == "CYGWIN"* ]] || [[ -n "$WINDIR" ]]; then
    os_name="Windows"
    # Su Windows, rileva architettura dal processore
    if [[ -n "$PROCESSOR_ARCHITECTURE" ]]; then
        case "$PROCESSOR_ARCHITECTURE" in
            AMD64|x64)
                current_arch="x86_64"
                ;;
            ARM64)
                current_arch="aarch64"
                ;;
            x86)
                current_arch="i386"
                ;;
        esac
    fi
elif [[ "$os_type" == "Darwin" ]]; then
    os_name="macOS"
elif [[ "$os_type" == "Linux" ]]; then
    os_name="Linux"
else
    os_name="Unknown ($os_type)"
fi

# Determina architettura Docker target
case $current_arch in
    x86_64|amd64|AMD64)
        docker_arch="linux/amd64"
        arch_name="AMD64"
        ;;
    aarch64|arm64|ARM64)
        docker_arch="linux/arm64"
        arch_name="ARM64"
        ;;
    armv7l|armhf)
        docker_arch="linux/arm/v7"
        arch_name="ARMv7"
        ;;
    i386|i686)
        docker_arch="linux/386"
        arch_name="i386"
        log_warning "⚠️  Architettura 32-bit, supporto limitato"
        ;;
    *)
        docker_arch="linux/amd64"
        arch_name="AMD64 (default)"
        log_warning "⚠️  Architettura $current_arch non riconosciuta, uso AMD64 come default"
        ;;
esac

log_info "🖥️  Sistema: $os_name"
log_info "🏗️  Architettura rilevata: $current_arch → $arch_name"
log_info "🐳 Target Docker: $docker_arch"

# Avvisi specifici per Windows
if [[ "$os_name" == "Windows" ]]; then
    log_info "💡 Rilevato Windows - assicurati che Docker Desktop sia in esecuzione"
    log_info "💡 I container useranno Linux containers tramite WSL2 o Hyper-V"
fi

# Prova prima buildx per architettura specifica
log_info "Tentativo build con buildx per $docker_arch..."
if command -v docker &> /dev/null && docker buildx version &> /dev/null; then
    # Configura buildx se necessario
    if ! docker buildx ls | grep -q "solaredge-builder"; then
        log_info "Configurando Docker Buildx..."
        docker buildx create --name solaredge-builder --use --bootstrap 2>/dev/null || true
    fi
    
    # Build con buildx per architettura specifica
    if docker buildx build \
        --platform "$docker_arch" \
        --tag solaredge-collector:latest \
        --tag solaredge-collector:dev \
        --load \
        . 2>/dev/null; then
        log_success "✅ Build buildx completato per $arch_name"
    else
        log_warning "⚠️  Buildx fallito, usando build standard..."
        # Fallback a build standard
        if docker build -t solaredge-collector:latest -t solaredge-collector:dev .; then
            log_success "✅ Build standard completato per $arch_name"
        else
            log_error "❌ Errore nel build dell'immagine"
            exit 1
        fi
    fi
else
    log_info "Buildx non disponibile, usando build standard..."
    # Build standard
    if docker build -t solaredge-collector:latest -t solaredge-collector:dev .; then
        log_success "✅ Build standard completato per $arch_name"
    else
        log_error "❌ Errore nel build dell'immagine"
        exit 1
    fi
fi

# Verifica immagine creata
log_info "🔍 Verifica immagine creata..."
if docker images solaredge-collector:latest --format "{{.Repository}}:{{.Tag}}" | grep -q "solaredge-collector:latest"; then
    image_arch=$(docker inspect solaredge-collector:latest --format '{{.Architecture}}' 2>/dev/null || echo "unknown")
    image_size=$(docker images solaredge-collector:latest --format "{{.Size}}" 2>/dev/null || echo "unknown")
    log_success "✅ Immagine creata: $arch_name ($image_arch) - Dimensione: $image_size"
else
    log_error "❌ Immagine non trovata dopo il build"
    exit 1
fi

echo ""

# 4. AVVIO STACK
log_info "🚀 Avvio stack Docker..."

docker compose up -d

if [[ $? -eq 0 ]]; then
    log_success "✅ Stack avviato con successo"
else
    log_error "❌ Errore nell'avvio dello stack"
    log_info "Mostrando log per debug..."
    docker compose logs --tail=20
    exit 1
fi

# 5. GENERAZIONE WEB ENDPOINTS
log_info "🔍 Generazione file web endpoints..."

# Attendi che il container sia pronto
sleep 5

# Esegui scan per generare web endpoints
log_info "Esecuzione scan per web endpoints..."
if docker exec solaredge-collector python main.py --scan; then
    log_success "✅ Web endpoints generati con successo"
else
    log_warning "⚠️  Scan fallito, continuo comunque"
fi

# 6. CONFIGURAZIONE GRAFANA
log_info "📊 Grafana configurato automaticamente con provisioning"
log_info "Dashboard e data source saranno disponibili all'avvio di Grafana"

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