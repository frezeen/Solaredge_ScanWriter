#!/bin/bash
# SolarEdge ScanWriter - Universal Docker Build Script
# Compatibile con: Linux, macOS, Windows (WSL), Raspberry Pi

set -e

# Configurazione
IMAGE_NAME="solaredge-scanwriter"
IMAGE_TAG="${1:-latest}"

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🐳 SolarEdge ScanWriter - Universal Build${NC}"
echo -e "${BLUE}=======================================${NC}"

# Rileva piattaforma
detect_platform() {
    local arch=$(uname -m)
    local os=$(uname -s)
    
    echo -e "${YELLOW}🔍 Platform Detection:${NC}"
    echo -e "   OS: $os"
    echo -e "   Architecture: $arch"
    
    case "$arch" in
        x86_64|amd64)
            PLATFORM="linux/amd64"
            ;;
        aarch64|arm64)
            PLATFORM="linux/arm64"
            ;;
        armv7l|armhf)
            PLATFORM="linux/arm/v7"
            ;;
        *)
            echo -e "${YELLOW}⚠️ Unknown architecture: $arch, using default${NC}"
            PLATFORM="linux/amd64"
            ;;
    esac
    
    echo -e "   Docker Platform: ${GREEN}$PLATFORM${NC}"
}

# Verifica prerequisiti
check_prerequisites() {
    echo -e "${YELLOW}🔍 Checking prerequisites...${NC}"
    
    # Verifica Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker not installed${NC}"
        exit 1
    fi
    
    # Verifica Docker Compose
    if ! docker compose version &> /dev/null; then
        echo -e "${YELLOW}⚠️ Docker Compose v2 not found, trying legacy...${NC}"
        if ! docker-compose --version &> /dev/null; then
            echo -e "${RED}❌ Docker Compose not available${NC}"
            exit 1
        fi
        COMPOSE_CMD="docker-compose"
    else
        COMPOSE_CMD="docker compose"
    fi
    
    echo -e "${GREEN}✅ Prerequisites OK${NC}"
    echo -e "   Docker: $(docker --version)"
    echo -e "   Compose: $($COMPOSE_CMD --version)"
}

# Build immagine
build_image() {
    echo -e "${YELLOW}🔨 Building universal image...${NC}"
    
    # Build con platform detection automatica
    docker build \
        --platform "$PLATFORM" \
        --tag "${IMAGE_NAME}:${IMAGE_TAG}" \
        --tag "${IMAGE_NAME}:latest" \
        .
    
    echo -e "${GREEN}✅ Build completed for $PLATFORM${NC}"
}

# Test immagine
test_image() {
    echo -e "${YELLOW}🧪 Testing image...${NC}"
    
    # Test di base
    docker run --rm --platform "$PLATFORM" "${IMAGE_NAME}:${IMAGE_TAG}" python --version
    
    # Test piattaforma
    echo -e "${BLUE}📋 Container info:${NC}"
    docker run --rm --platform "$PLATFORM" "${IMAGE_NAME}:${IMAGE_TAG}" uname -a
    
    # Test configurazione (usa .env se esiste)
    local env_args=""
    if [ -f ".env" ]; then
        echo -e "${BLUE}📋 Using .env file for test${NC}"
        # Carica variabili da .env
        source .env 2>/dev/null || true
        env_args="-e SOLAREDGE_SITE_ID=${SOLAREDGE_SITE_ID:-123456} -e SOLAREDGE_API_KEY=${SOLAREDGE_API_KEY:-test-key}"
    else
        echo -e "${BLUE}📋 Using default test values${NC}"
        env_args="-e SOLAREDGE_SITE_ID=123456 -e SOLAREDGE_API_KEY=test-key"
    fi
    
    docker run --rm --platform "$PLATFORM" \
        $env_args \
        "${IMAGE_NAME}:${IMAGE_TAG}" python -c "
import os, platform
print(f'✅ Python: {platform.python_version()}')
print(f'✅ Platform: {platform.platform()}')
site_id = os.getenv('SOLAREDGE_SITE_ID', 'NOT_SET')
print(f'✅ Site ID: {site_id}')
if site_id != 'NOT_SET' and site_id != '123456':
    print('✅ Real credentials detected - test successful!')
else:
    print('ℹ️ Using test credentials')
"
    
    echo -e "${GREEN}✅ Tests passed${NC}"
}

# Mostra informazioni immagine
show_info() {
    echo -e "${BLUE}📊 Image Information:${NC}"
    
    # Dimensione immagine
    local size=$(docker images "${IMAGE_NAME}:${IMAGE_TAG}" --format "table {{.Size}}" | tail -n 1)
    echo -e "   Size: ${GREEN}$size${NC}"
    
    # Layers
    echo -e "   Layers: $(docker history "${IMAGE_NAME}:${IMAGE_TAG}" --quiet | wc -l)"
    
    # Tag disponibili
    echo -e "   Tags:"
    docker images "${IMAGE_NAME}" --format "table {{.Tag}}\t{{.CreatedAt}}" | tail -n +2 | sed 's/^/     /'
}

# Menu principale
show_menu() {
    echo -e "${BLUE}🎯 Available commands:${NC}"
    echo "   build    - Build universal image"
    echo "   test     - Test built image"
    echo "   info     - Show image information"
    echo "   compose  - Build with docker-compose"
    echo "   clean    - Clean up images"
    echo
}

# Build con compose
build_compose() {
    echo -e "${YELLOW}🔨 Building with Docker Compose...${NC}"
    
    $COMPOSE_CMD build --no-cache
    
    echo -e "${GREEN}✅ Compose build completed${NC}"
}

# Cleanup
cleanup() {
    echo -e "${YELLOW}🧹 Cleaning up...${NC}"
    
    # Rimuovi immagini dangling
    docker image prune -f
    
    # Rimuovi immagini vecchie del progetto (opzionale)
    read -p "Remove old ${IMAGE_NAME} images? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker images "${IMAGE_NAME}" --format "table {{.ID}}\t{{.Tag}}" | tail -n +2 | grep -v latest | awk '{print $1}' | xargs -r docker rmi
    fi
    
    echo -e "${GREEN}✅ Cleanup completed${NC}"
}

# Main
main() {
    detect_platform
    check_prerequisites
    
    case "${1:-menu}" in
        "build")
            build_image
            test_image
            show_info
            ;;
        "test")
            test_image
            ;;
        "info")
            show_info
            ;;
        "compose")
            build_compose
            ;;
        "clean")
            cleanup
            ;;
        "menu"|*)
            show_menu
            echo -e "${YELLOW}💡 Usage: $0 [build|test|info|compose|clean]${NC}"
            echo -e "${YELLOW}💡 Example: $0 build${NC}"
            ;;
    esac
}

# Esegui main con tutti gli argomenti
main "$@"