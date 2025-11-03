#!/bin/bash
# SolarEdge Multi-Platform Docker Setup
# Compatible with: Linux, macOS, Raspberry Pi, WSL

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }
log_header() { echo -e "${MAGENTA}$1${NC}"; }

# Detect architecture
detect_architecture() {
    local arch=$(uname -m)
    case $arch in
        x86_64|amd64) echo "amd64" ;;
        aarch64|arm64) echo "arm64" ;;
        armv7l|armhf) echo "arm/v7" ;;
        *) echo "unknown" ;;
    esac
}

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [[ -f /etc/debian_version ]]; then
            echo "debian"
        elif [[ -f /etc/redhat-release ]]; then
            echo "redhat"
        elif [[ -f /etc/alpine-release ]]; then
            echo "alpine"
        else
            echo "linux"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        echo "windows"
    else
        echo "unknown"
    fi
}

# Check if Docker is installed
check_docker() {
    command -v docker &> /dev/null
}

# Check Docker Compose
check_docker_compose() {
    if command -v docker-compose &> /dev/null; then
        echo "docker-compose"
    elif docker compose version &> /dev/null; then
        echo "docker compose"
    else
        echo ""
    fi
}

# Install Docker
install_docker() {
    local os=$(detect_os)
    log_info "Installing Docker for $os..."
    
    case $os in
        "debian")
            sudo apt-get update
            sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
            sudo apt-get update
            sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
            ;;
        "redhat")
            sudo yum install -y yum-utils
            sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
            ;;
        "alpine")
            sudo apk add docker docker-compose
            ;;
        "macos")
            log_warning "On macOS, install Docker Desktop manually:"
            log_info "https://docs.docker.com/desktop/mac/install/"
            log_info "Or use Homebrew: brew install --cask docker"
            exit 1
            ;;
        *)
            log_error "Unsupported OS for automatic installation"
            log_info "Install Docker manually: https://docs.docker.com/engine/install/"
            exit 1
            ;;
    esac
    
    # Start Docker service
    sudo systemctl start docker 2>/dev/null || true
    sudo systemctl enable docker 2>/dev/null || true
    
    # Add user to docker group
    sudo usermod -aG docker $USER
    
    log_success "Docker installed. Please restart your session to apply permissions."
}

# Setup Docker Buildx
setup_buildx() {
    log_info "Configuring Docker Buildx for multi-architecture..."
    
    # Create builder if it doesn't exist
    docker buildx create --name solaredge-builder --use --bootstrap 2>/dev/null || true
    docker buildx inspect --bootstrap > /dev/null
    
    log_success "Docker Buildx configured"
}

# Clean Docker resources
clean_docker() {
    log_info "Cleaning Docker resources..."
    
    local compose_cmd=$(check_docker_compose)
    if [[ -n "$compose_cmd" ]]; then
        $compose_cmd down --remove-orphans --volumes 2>/dev/null || true
    fi
    
    # Remove SolarEdge containers
    local containers=$(docker ps -a --filter "name=solaredge" --format "{{.ID}}" 2>/dev/null || true)
    if [[ -n "$containers" ]]; then
        echo "$containers" | xargs docker rm -f 2>/dev/null || true
    fi
    
    # Remove SolarEdge images
    local images=$(docker images --filter "reference=*solaredge*" --format "{{.ID}}" 2>/dev/null || true)
    if [[ -n "$images" ]]; then
        echo "$images" | xargs docker rmi -f 2>/dev/null || true
    fi
    
    # System cleanup
    docker system prune -f --volumes 2>/dev/null || true
    
    log_success "Cleanup completed"
}

# Build multi-architecture image
build_multiarch() {
    log_info "Building multi-architecture image..."
    
    local platforms="linux/amd64,linux/arm64,linux/arm/v7"
    local current_arch=$(detect_architecture)
    
    log_info "Target platforms: $platforms"
    log_info "Current architecture: $current_arch"
    
    # Build for multiple architectures
    if docker buildx build \
        --platform "$platforms" \
        --tag solaredge-collector:latest \
        --load \
        . 2>/dev/null; then
        log_success "Multi-architecture build completed"
    else
        log_warning "Multi-arch build failed, trying single platform..."
        docker build -t solaredge-collector:latest .
        log_success "Single platform build completed"
    fi
}

# Start services
start_services() {
    log_info "Starting SolarEdge services..."
    
    local compose_cmd=$(check_docker_compose)
    if [[ -z "$compose_cmd" ]]; then
        log_error "Docker Compose not found"
        exit 1
    fi
    
    local compose_args="up -d"
    
    if $compose_cmd $compose_args; then
        log_success "Services started successfully"
        show_service_info "$1"
    else
        log_error "Failed to start services"
        show_logs
        exit 1
    fi
}

# Stop services
stop_services() {
    log_info "Stopping services..."
    
    local compose_cmd=$(check_docker_compose)
    if [[ -n "$compose_cmd" ]]; then
        $compose_cmd down
    fi
    
    log_success "Services stopped"
}

# Show logs
show_logs() {
    local compose_cmd=$(check_docker_compose)
    if [[ -n "$compose_cmd" ]]; then
        $compose_cmd logs -f --tail=50
    fi
}

# Show status
show_status() {
    log_info "Service Status:"
    
    local compose_cmd=$(check_docker_compose)
    if [[ -n "$compose_cmd" ]]; then
        $compose_cmd ps
    fi
}

# Show service information
show_service_info() {
    echo ""
    log_success "🎉 SolarEdge Data Collector is running!"
    echo ""
    echo -e "${CYAN}📊 GUI Dashboard: http://localhost:8092${NC}"
    echo -e "${CYAN}🗄️ InfluxDB: http://localhost:8086${NC}"
    echo -e "${CYAN}📈 Grafana: http://localhost:3000${NC}"
    echo ""
    log_info "📋 Useful commands:"
    echo -e "${CYAN}   ./docker-setup.sh logs     # View logs${NC}"
    echo -e "${CYAN}   ./docker-setup.sh stop     # Stop services${NC}"
    echo -e "${CYAN}   ./docker-setup.sh status   # Service status${NC}"
    echo -e "${CYAN}   ./docker-setup.sh clean    # Full cleanup${NC}"
    echo ""
}

# Check configuration
check_config() {
    log_info "Checking configuration..."
    
    local required_files=("docker-compose.yml" "Dockerfile" ".env.example")
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            log_error "Missing file: $file"
            exit 1
        fi
    done
    
    if [[ ! -f ".env" ]]; then
        log_warning ".env file not found, copying from .env.example"
        cp .env.example .env
        log_info "📝 Please edit .env with your SolarEdge credentials"
    fi
    
    log_success "Configuration verified"
}

# Main function
main() {
    local os=$(detect_os)
    local arch=$(detect_architecture)
    
    log_header "🌍 SolarEdge Multi-Platform Docker Setup"
    log_header "======================================="
    echo -e "${BLUE}🖥️ OS: $os${NC}"
    echo -e "${BLUE}🏗️ Architecture: $arch${NC}"
    echo -e "${BLUE}🐳 Docker: $(docker --version 2>/dev/null || echo 'Not installed')${NC}"
    echo ""
    
    case "${1:-setup}" in
        "clean")
            clean_docker
            ;;
        "build")
            setup_buildx
            build_multiarch
            ;;
        "start")
            start_services "$2"
            ;;
        "stop")
            stop_services
            ;;
        "logs")
            show_logs
            ;;
        "status")
            show_status
            ;;
        "setup"|"")
            if ! check_docker; then
                install_docker
                exit 0
            fi
            
            if [[ -z "$(check_docker_compose)" ]]; then
                log_error "Docker Compose not found"
                log_info "Install Docker Compose or use Docker Desktop"
                exit 1
            fi
            
            check_config
            setup_buildx
            clean_docker
            build_multiarch
            start_services "$2"
            
            log_success "🎯 Multi-platform setup completed!"
            ;;
        *)
            echo "Usage: $0 [setup|clean|build|start|stop|logs|status] [--grafana]"
            echo ""
            echo "Commands:"
            echo "  setup    - Full setup (default)"
            echo "  clean    - Clean Docker resources"
            echo "  build    - Build multi-platform image"
            echo "  start    - Start services"
            echo "  stop     - Stop services"
            echo "  logs     - Show logs"
            echo "  status   - Show service status"
            echo ""
            echo "Options:"
            echo "  --grafana - Include Grafana dashboard"
            exit 1
            ;;
    esac
}

# Execute main function
main "$@"