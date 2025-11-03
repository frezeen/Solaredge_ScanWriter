#!/bin/bash
# SolarEdge ScanWriter - Clean and Test Script
# Pulizia completa sistema e test da zero

set -e

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🧹 SolarEdge ScanWriter - Clean and Test Script${NC}"
echo -e "${BLUE}===============================================${NC}"

# Funzione per conferma utente
confirm() {
    read -p "$(echo -e ${YELLOW}$1${NC}) [y/N]: " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

# Step 1: Pulizia Docker completa
cleanup_docker() {
    echo -e "${YELLOW}🐳 Pulizia Docker completa...${NC}"
    
    # Stop tutti i container
    if [ "$(docker ps -aq)" ]; then
        echo "Stopping all containers..."
        docker stop $(docker ps -aq) 2>/dev/null || true
    fi
    
    # Rimuovi tutti i container
    if [ "$(docker ps -aq)" ]; then
        echo "Removing all containers..."
        docker rm $(docker ps -aq) 2>/dev/null || true
    fi
    
    # Rimuovi tutte le immagini
    if [ "$(docker images -q)" ]; then
        echo "Removing all images..."
        docker rmi $(docker images -q) 2>/dev/null || true
    fi
    
    # Rimuovi tutti i volumi
    if [ "$(docker volume ls -q)" ]; then
        echo "Removing all volumes..."
        docker volume rm $(docker volume ls -q) 2>/dev/null || true
    fi
    
    # Rimuovi reti custom
    if [ "$(docker network ls -q --filter type=custom)" ]; then
        echo "Removing custom networks..."
        docker network rm $(docker network ls -q --filter type=custom) 2>/dev/null || true
    fi
    
    # Pulizia sistema completa
    echo "System cleanup..."
    docker system prune -a -f --volumes
    
    echo -e "${GREEN}✅ Docker cleanup completato${NC}"
}

# Step 2: Rimozione progetto esistente
cleanup_project() {
    echo -e "${YELLOW}📁 Pulizia progetto esistente...${NC}"
    
    cd /root
    if [ -d "Solaredge_ScanWriter" ]; then
        echo "Removing existing project directory..."
        rm -rf Solaredge_ScanWriter
    fi
    
    echo -e "${GREEN}✅ Project cleanup completato${NC}"
}

# Step 3: Clone fresh del progetto
clone_project() {
    echo -e "${YELLOW}📥 Clone fresh del progetto...${NC}"
    
    cd /root
    git clone https://github.com/frezeen/Solaredge_ScanWriter.git
    cd Solaredge_ScanWriter
    git checkout dev
    
    echo -e "${GREEN}✅ Clone completato${NC}"
}

# Step 4: Configurazione automatica
setup_config() {
    echo -e "${YELLOW}⚙️ Configurazione automatica...${NC}"
    
    # Copia template
    cp .env.docker.example .env
    
    echo -e "${BLUE}📝 Configurazione .env creata${NC}"
    echo -e "${YELLOW}⚠️ IMPORTANTE: Devi modificare le credenziali SolarEdge!${NC}"
    echo
    echo -e "${BLUE}Modifica queste variabili in .env:${NC}"
    echo "SOLAREDGE_API_KEY=LA_TUA_API_KEY"
    echo "SOLAREDGE_USERNAME=la.tua.email@example.com"
    echo "SOLAREDGE_PASSWORD=LA_TUA_PASSWORD"
    echo "SOLAREDGE_SITE_ID=IL_TUO_SITE_ID"
    echo
    
    if confirm "Vuoi aprire nano per modificare .env ora?"; then
        nano .env
    fi
    
    echo -e "${GREEN}✅ Configurazione completata${NC}"
}

# Step 5: Build e test
build_and_test() {
    echo -e "${YELLOW}🔨 Build e test container...${NC}"
    
    # Rendi eseguibili gli script
    chmod +x docker/build.sh docker/entrypoint.sh
    
    # Build container
    echo -e "${BLUE}Building container...${NC}"
    ./docker/build.sh build
    
    # Avvio stack
    echo -e "${BLUE}Starting stack...${NC}"
    docker compose up -d
    
    # Attendi avvio
    echo -e "${BLUE}Waiting for services to start...${NC}"
    sleep 10
    
    # Verifica stato
    echo -e "${BLUE}📊 Stato servizi:${NC}"
    docker compose ps
    
    echo -e "${GREEN}✅ Build e avvio completati${NC}"
}

# Step 6: Verifica funzionamento
verify_deployment() {
    echo -e "${YELLOW}🔍 Verifica funzionamento...${NC}"
    
    # Trova IP
    local_ip=$(ip addr show | grep 'inet ' | grep -v '127.0.0.1' | head -1 | awk '{print $2}' | cut -d'/' -f1)
    
    echo -e "${BLUE}📊 Informazioni accesso:${NC}"
    echo "🎯 SolarEdge GUI: http://$local_ip:8092"
    echo "📊 InfluxDB: http://$local_ip:8086 (admin/solaredge123)"
    echo "📈 Grafana: http://$local_ip:3000 (admin/admin)"
    echo
    
    # Test log
    echo -e "${BLUE}📋 Ultimi log (primi 20 righe):${NC}"
    docker logs --tail 20 solaredge-scanwriter
    
    echo
    echo -e "${BLUE}💡 Comandi utili:${NC}"
    echo "docker logs -f solaredge-scanwriter  # Log in tempo reale"
    echo "docker compose ps                    # Stato servizi"
    echo "docker compose down                  # Stop tutto"
    echo "docker exec solaredge-scanwriter python main.py --api  # Test API"
    
    echo -e "${GREEN}✅ Verifica completata${NC}"
}

# Funzione principale
main() {
    echo -e "${BLUE}Questo script eseguirà:${NC}"
    echo "1. 🐳 Pulizia completa Docker (container, immagini, volumi)"
    echo "2. 📁 Rimozione progetto esistente"
    echo "3. 📥 Clone fresh dal repository"
    echo "4. ⚙️ Configurazione automatica"
    echo "5. 🔨 Build e avvio container"
    echo "6. 🔍 Verifica funzionamento"
    echo
    
    if ! confirm "⚠️ ATTENZIONE: Questo cancellerà TUTTO Docker. Continuare?"; then
        echo -e "${YELLOW}Operazione annullata${NC}"
        exit 0
    fi
    
    echo
    echo -e "${GREEN}🚀 Avvio pulizia e test...${NC}"
    
    cleanup_docker
    cleanup_project
    clone_project
    setup_config
    build_and_test
    verify_deployment
    
    echo
    echo -e "${GREEN}🎉 COMPLETATO! Container universale pronto!${NC}"
    echo -e "${BLUE}Accedi alla GUI: http://$local_ip:8092${NC}"
}

# Verifica prerequisiti
check_prerequisites() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker non installato${NC}"
        exit 1
    fi
    
    if ! docker compose version &> /dev/null; then
        echo -e "${RED}❌ Docker Compose non disponibile${NC}"
        exit 1
    fi
    
    if ! command -v git &> /dev/null; then
        echo -e "${RED}❌ Git non installato${NC}"
        exit 1
    fi
}

# Esecuzione
check_prerequisites
main "$@"