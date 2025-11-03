#!/bin/bash
# Script per rilevare automaticamente l'architettura e configurare Docker

# Colori
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }

# Rileva architettura sistema
detect_system_arch() {
    local os=$(uname -s 2>/dev/null || echo "Unknown")
    local arch=$(uname -m 2>/dev/null || echo "Unknown")
    
    # Rilevamento specifico per Windows
    if [[ "$os" == "MINGW"* ]] || [[ "$os" == "MSYS"* ]] || [[ "$os" == "CYGWIN"* ]] || [[ -n "$WINDIR" ]]; then
        os="Windows"
        # Su Windows, usa variabili d'ambiente per architettura
        if [[ -n "$PROCESSOR_ARCHITECTURE" ]]; then
            case "$PROCESSOR_ARCHITECTURE" in
                AMD64|x64) arch="x86_64" ;;
                ARM64) arch="aarch64" ;;
                x86) arch="i386" ;;
            esac
        fi
        echo -e "${CYAN}🖥️  Sistema Rilevato:${NC}"
        echo -e "   OS: $os (Docker Desktop)"
        echo -e "   Architettura Host: $arch"
        echo -e "   Container Runtime: WSL2 o Hyper-V"
    elif [[ "$os" == "Darwin" ]]; then
        echo -e "${CYAN}🖥️  Sistema Rilevato:${NC}"
        echo -e "   OS: macOS (Docker Desktop)"
        echo -e "   Architettura: $arch"
    else
        echo -e "${CYAN}🖥️  Sistema Rilevato:${NC}"
        echo -e "   OS: $os"
        echo -e "   Architettura: $arch"
    fi
    
    case $arch in
        x86_64|amd64|AMD64)
            echo -e "   Tipo: ${GREEN}AMD64/Intel 64-bit${NC}"
            echo -e "   Docker Platform: linux/amd64"
            if [[ "$os" == "Windows" ]]; then
                echo -e "   Ottimizzazioni: Windows + Linux containers"
            else
                echo -e "   Ottimizzazioni: Build standard, performance elevate"
            fi
            ;;
        aarch64|arm64|ARM64)
            echo -e "   Tipo: ${GREEN}ARM64 (Apple Silicon, Raspberry Pi 4+)${NC}"
            echo -e "   Docker Platform: linux/arm64"
            if [[ "$os" == "Windows" ]]; then
                echo -e "   Ottimizzazioni: Windows ARM + Linux containers"
            elif [[ "$os" == "Darwin" ]]; then
                echo -e "   Ottimizzazioni: Apple Silicon nativo"
            else
                echo -e "   Ottimizzazioni: ARM64 nativo, efficienza energetica"
            fi
            ;;
        armv7l|armhf)
            echo -e "   Tipo: ${GREEN}ARMv7 (Raspberry Pi 3/4 32-bit)${NC}"
            echo -e "   Docker Platform: linux/arm/v7"
            echo -e "   Ottimizzazioni: ARM 32-bit, risorse limitate"
            ;;
        i386|i686)
            echo -e "   Tipo: ${YELLOW}i386 32-bit${NC}"
            echo -e "   Docker Platform: linux/386"
            echo -e "   Ottimizzazioni: Architettura legacy, supporto limitato"
            ;;
        armv6l)
            echo -e "   Tipo: ${YELLOW}ARMv6 (Raspberry Pi Zero/1)${NC}"
            echo -e "   Docker Platform: linux/arm/v6 (limitato)"
            echo -e "   Ottimizzazioni: Risorse molto limitate"
            ;;
        *)
            echo -e "   Tipo: ${YELLOW}Sconosciuta ($arch)${NC}"
            echo -e "   Docker Platform: linux/amd64 (fallback)"
            echo -e "   Ottimizzazioni: Default AMD64"
            ;;
    esac
}

# Rileva capacità Docker
detect_docker_capabilities() {
    echo ""
    echo -e "${CYAN}🐳 Capacità Docker:${NC}"
    
    if ! command -v docker &> /dev/null; then
        echo -e "   Docker: ${YELLOW}Non installato${NC}"
        return 1
    fi
    
    local docker_version=$(docker --version 2>/dev/null | cut -d' ' -f3 | cut -d',' -f1)
    echo -e "   Docker: ${GREEN}$docker_version${NC}"
    
    # Verifica buildx
    if docker buildx version &> /dev/null; then
        local buildx_version=$(docker buildx version 2>/dev/null | head -1 | cut -d' ' -f2)
        echo -e "   Buildx: ${GREEN}$buildx_version${NC}"
        echo -e "   Multi-arch: ${GREEN}Supportato${NC}"
        
        # Lista builder disponibili
        echo -e "   Builder disponibili:"
        docker buildx ls 2>/dev/null | tail -n +2 | while read line; do
            echo -e "     $line"
        done
    else
        echo -e "   Buildx: ${YELLOW}Non disponibile${NC}"
        echo -e "   Multi-arch: ${YELLOW}Limitato${NC}"
    fi
    
    # Verifica compose
    if docker compose version &> /dev/null; then
        local compose_version=$(docker compose version --short 2>/dev/null)
        echo -e "   Compose: ${GREEN}$compose_version${NC}"
    elif command -v docker-compose &> /dev/null; then
        local compose_version=$(docker-compose --version 2>/dev/null | cut -d' ' -f3 | cut -d',' -f1)
        echo -e "   Compose: ${GREEN}$compose_version (standalone)${NC}"
    else
        echo -e "   Compose: ${YELLOW}Non disponibile${NC}"
    fi
}

# Raccomandazioni per architettura
show_recommendations() {
    local os=$(uname -s 2>/dev/null || echo "Unknown")
    local arch=$(uname -m 2>/dev/null || echo "Unknown")
    
    # Rilevamento Windows
    if [[ "$os" == "MINGW"* ]] || [[ "$os" == "MSYS"* ]] || [[ "$os" == "CYGWIN"* ]] || [[ -n "$WINDIR" ]]; then
        os="Windows"
        if [[ -n "$PROCESSOR_ARCHITECTURE" ]]; then
            case "$PROCESSOR_ARCHITECTURE" in
                AMD64|x64) arch="x86_64" ;;
                ARM64) arch="aarch64" ;;
                x86) arch="i386" ;;
            esac
        fi
    fi
    
    echo ""
    echo -e "${CYAN}💡 Raccomandazioni per il tuo sistema:${NC}"
    
    # Raccomandazioni specifiche per OS
    if [[ "$os" == "Windows" ]]; then
        echo -e "   🪟 ${GREEN}Windows con Docker Desktop${NC}"
        echo -e "   ✅ Assicurati che Docker Desktop sia avviato"
        echo -e "   ✅ Usa WSL2 backend per performance migliori"
        echo -e "   ✅ Linux containers supportati nativamente"
        echo -e "   📋 Prerequisiti Windows:"
        echo -e "      - Docker Desktop 4.0+"
        echo -e "      - WSL2 abilitato (raccomandato)"
        echo -e "      - Hyper-V abilitato (alternativa)"
        echo -e "      - Memoria: 4GB+ (8GB raccomandati)"
    elif [[ "$os" == "Darwin" ]]; then
        echo -e "   🍎 ${GREEN}macOS con Docker Desktop${NC}"
        echo -e "   ✅ Supporto nativo Apple Silicon"
        echo -e "   ✅ Performance eccellenti"
    else
        echo -e "   🐧 ${GREEN}Linux nativo${NC}"
        echo -e "   ✅ Performance ottimali"
        echo -e "   ✅ Supporto completo Docker"
    fi
    
    # Raccomandazioni per architettura
    case $arch in
        x86_64|amd64|AMD64)
            echo -e "   ✅ Architettura ottimale per Docker"
            echo -e "   ✅ Supporto completo multi-architettura"
            echo -e "   ✅ Performance elevate"
            echo -e "   📋 Configurazione consigliata:"
            if [[ "$os" == "Windows" ]]; then
                echo -e "      - Memoria Windows: 8GB+ (4GB per Docker)"
                echo -e "      - CPU: 4+ core (2+ per Docker)"
                echo -e "      - WSL2: 4GB+ allocati"
            else
                echo -e "      - Memoria: 2GB+ (4GB raccomandati)"
                echo -e "      - CPU: 2+ core"
            fi
            echo -e "      - Build: Buildx multi-platform"
            ;;
        aarch64|arm64|ARM64)
            echo -e "   ✅ Ottima compatibilità Docker"
            echo -e "   ✅ Efficienza energetica elevata"
            if [[ "$os" == "Darwin" ]]; then
                echo -e "   ✅ Apple Silicon: performance native"
            elif [[ "$os" == "Windows" ]]; then
                echo -e "   ⚠️  Windows ARM: supporto limitato"
            fi
            echo -e "   📋 Configurazione consigliata:"
            echo -e "      - Memoria: 2GB+ (4GB+ per Apple Silicon)"
            echo -e "      - CPU: 4+ core ARM"
            echo -e "      - Build: Nativo ARM64"
            ;;
        armv7l|armhf)
            echo -e "   ⚠️  Architettura con risorse limitate"
            echo -e "   ⚠️  Build più lenti"
            echo -e "   ✅ Compatibile con Docker"
            echo -e "   📋 Configurazione consigliata:"
            echo -e "      - Memoria: 1GB+ (2GB raccomandati)"
            echo -e "      - CPU: 4 core ARM Cortex-A"
            echo -e "      - Build: Singola architettura"
            echo -e "      - Swap: Abilitato per build pesanti"
            ;;
        i386|i686)
            echo -e "   ⚠️  Architettura 32-bit legacy"
            echo -e "   ⚠️  Supporto Docker limitato"
            echo -e "   📋 Raccomandazioni:"
            echo -e "      - Considera upgrade a 64-bit"
            echo -e "      - Usa immagini 32-bit quando disponibili"
            ;;
        *)
            echo -e "   ⚠️  Architettura non testata"
            echo -e "   📋 Usa configurazione AMD64 come fallback"
            ;;
    esac
}

# Genera configurazione ottimale
generate_config() {
    local arch=$(uname -m)
    
    echo ""
    echo -e "${CYAN}⚙️  Configurazione Docker Ottimale:${NC}"
    
    case $arch in
        x86_64|amd64)
            cat << EOF
   # docker-compose.yml - Sezione deploy ottimizzata
   deploy:
     resources:
       limits:
         memory: 1G
         cpus: '2.0'
       reservations:
         memory: 512M
         cpus: '1.0'
EOF
            ;;
        aarch64|arm64)
            cat << EOF
   # docker-compose.yml - Sezione deploy ottimizzata
   deploy:
     resources:
       limits:
         memory: 768M
         cpus: '1.5'
       reservations:
         memory: 384M
         cpus: '0.75'
EOF
            ;;
        armv7l|armhf)
            cat << EOF
   # docker-compose.yml - Sezione deploy ottimizzata
   deploy:
     resources:
       limits:
         memory: 512M
         cpus: '1.0'
       reservations:
         memory: 256M
         cpus: '0.5'
EOF
            ;;
    esac
}

# Funzione principale
main() {
    echo -e "${CYAN}🔍 Rilevamento Automatico Architettura Docker${NC}"
    echo "=============================================="
    
    detect_system_arch
    detect_docker_capabilities
    show_recommendations
    generate_config
    
    echo ""
    log_success "✅ Rilevamento completato!"
    echo ""
    log_info "🚀 Per avviare il build ottimizzato:"
    echo -e "   ${YELLOW}./dev-docker-rebuild.sh${NC}"
}

# Esegui se chiamato direttamente
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi