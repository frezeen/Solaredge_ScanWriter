#!/bin/bash
# Build script per immagini Docker multi-architettura
# Supporta: AMD64, ARM64, ARM/v7 (Raspberry Pi)

set -e

# Configurazione
IMAGE_NAME="solaredge-scanwriter"
IMAGE_TAG="${1:-latest}"
REGISTRY="${REGISTRY:-}"  # Opzionale: docker.io/username

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🐳 SolarEdge ScanWriter - Multi-Architecture Build${NC}"
echo -e "${BLUE}=================================================${NC}"

# Verifica prerequisiti
check_prerequisites() {
    echo -e "${YELLOW}🔍 Verifica prerequisiti...${NC}"
    
    # Verifica Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker non installato${NC}"
        exit 1
    fi
    
    # Verifica Docker Buildx
    if ! docker buildx version &> /dev/null; then
        echo -e "${RED}❌ Docker Buildx non disponibile${NC}"
        echo -e "${YELLOW}💡 Installa con: docker buildx install${NC}"
        exit 1
    fi
    
    # Verifica QEMU per emulazione cross-platform
    if ! docker run --rm --privileged multiarch/qemu-user-static --reset -p yes &> /dev/null; then
        echo -e "${YELLOW}⚠️ Configurazione QEMU per emulazione cross-platform...${NC}"
        docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
    fi
    
    echo -e "${GREEN}✅ Prerequisiti verificati${NC}"
}

# Crea builder multi-architettura
setup_builder() {
    echo -e "${YELLOW}🏗️ Configurazione builder multi-architettura...${NC}"
    
    # Crea builder se non esiste
    if ! docker buildx ls | grep -q "solaredge-builder"; then
        docker buildx create --name solaredge-builder --driver docker-container --bootstrap
    fi
    
    # Usa il builder
    docker buildx use solaredge-builder
    
    # Verifica piattaforme supportate
    echo -e "${BLUE}📋 Piattaforme supportate:${NC}"
    docker buildx ls | grep solaredge-builder
    
    echo -e "${GREEN}✅ Builder configurato${NC}"
}

# Build per singola piattaforma (sviluppo)
build_single_platform() {
    local platform=$1
    local tag_suffix=$2
    
    echo -e "${YELLOW}🔨 Build per ${platform}...${NC}"
    
    docker buildx build \
        --platform "$platform" \
        --file Dockerfile.multiarch \
        --tag "${IMAGE_NAME}:${IMAGE_TAG}${tag_suffix}" \
        --load \
        .
    
    echo -e "${GREEN}✅ Build completato per ${platform}${NC}"
}

# Build multi-architettura (produzione)
build_multiarch() {
    echo -e "${YELLOW}🔨 Build multi-architettura...${NC}"
    
    # Piattaforme target
    PLATFORMS="linux/amd64,linux/arm64,linux/arm/v7"
    
    # Build command
    BUILD_CMD="docker buildx build \
        --platform $PLATFORMS \
        --file Dockerfile.multiarch \
        --tag ${IMAGE_NAME}:${IMAGE_TAG}"
    
    # Aggiungi registry se specificato
    if [ -n "$REGISTRY" ]; then
        BUILD_CMD="$BUILD_CMD --tag ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
    fi
    
    # Push se non è build locale
    if [ "$2" != "--local" ]; then
        BUILD_CMD="$BUILD_CMD --push"
    else
        BUILD_CMD="$BUILD_CMD --load"
    fi
    
    # Aggiungi context
    BUILD_CMD="$BUILD_CMD ."
    
    echo -e "${BLUE}📋 Comando build:${NC}"
    echo "$BUILD_CMD"
    echo
    
    # Esegui build
    eval "$BUILD_CMD"
    
    echo -e "${GREEN}✅ Build multi-architettura completato${NC}"
}

# Test immagine
test_image() {
    local platform=${1:-"linux/amd64"}
    local image_tag="${IMAGE_NAME}:${IMAGE_TAG}"
    
    echo -e "${YELLOW}🧪 Test immagine per ${platform}...${NC}"
    
    # Test di base: verifica che il container si avvii
    docker run --rm --platform "$platform" "$image_tag" python --version
    
    # Test configurazione
    docker run --rm --platform "$platform" \
        -e SOLAREDGE_SITE_ID=123456 \
        -e SOLAREDGE_API_KEY=test-key \
        "$image_tag" python -c "
import os
print('✅ Variabili d\'ambiente caricate')
print(f'Site ID: {os.getenv(\"SOLAREDGE_SITE_ID\")}')
"
    
    echo -e "${GREEN}✅ Test completati per ${platform}${NC}"
}

# Mostra informazioni immagine
show_image_info() {
    echo -e "${BLUE}📊 Informazioni immagine:${NC}"
    
    # Dimensioni immagine per piattaforma
    for platform in "linux/amd64" "linux/arm64" "linux/arm/v7"; do
        if docker buildx imagetools inspect "${IMAGE_NAME}:${IMAGE_TAG}" --format "{{.Manifest}}" 2>/dev/null | grep -q "$platform"; then
            echo -e "${GREEN}✅ $platform: Disponibile${NC}"
        else
            echo -e "${YELLOW}⚠️ $platform: Non disponibile${NC}"
        fi
    done
}

# Menu principale
show_menu() {
    echo -e "${BLUE}🎯 Opzioni build:${NC}"
    echo "1. Build locale (AMD64 only)"
    echo "2. Build multi-architettura (AMD64 + ARM64 + ARM/v7)"
    echo "3. Build e push su registry"
    echo "4. Test immagine"
    echo "5. Informazioni immagine"
    echo "6. Cleanup builder"
    echo
}

# Cleanup
cleanup_builder() {
    echo -e "${YELLOW}🧹 Cleanup builder...${NC}"
    docker buildx rm solaredge-builder || true
    echo -e "${GREEN}✅ Cleanup completato${NC}"
}

# Main
main() {
    check_prerequisites
    
    case "${1:-menu}" in
        "local")
            setup_builder
            build_single_platform "linux/amd64" ""
            test_image "linux/amd64"
            ;;
        "multiarch")
            setup_builder
            build_multiarch "$IMAGE_TAG" "--local"
            ;;
        "push")
            if [ -z "$REGISTRY" ]; then
                echo -e "${RED}❌ REGISTRY non configurato${NC}"
                echo -e "${YELLOW}💡 Usa: REGISTRY=docker.io/username $0 push${NC}"
                exit 1
            fi
            setup_builder
            build_multiarch "$IMAGE_TAG"
            ;;
        "test")
            test_image "${2:-linux/amd64}"
            ;;
        "info")
            show_image_info
            ;;
        "cleanup")
            cleanup_builder
            ;;
        "menu"|*)
            show_menu
            echo -e "${YELLOW}💡 Uso: $0 [local|multiarch|push|test|info|cleanup]${NC}"
            echo -e "${YELLOW}💡 Esempio: $0 local${NC}"
            echo -e "${YELLOW}💡 Esempio: REGISTRY=docker.io/username $0 push${NC}"
            ;;
    esac
}

# Esegui main con tutti gli argomenti
main "$@"