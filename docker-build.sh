#!/bin/bash
# SolarEdge Docker Multi-Platform Builder
# Builds Docker containers for Windows, Linux, and Raspberry Pi

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }

echo -e "${BLUE}🐳 SolarEdge Multi-Platform Docker Builder${NC}"
echo "=========================================="
echo ""

# Detect architecture
ARCH=$(uname -m)
case $ARCH in
    x86_64|amd64) DOCKER_ARCH="linux/amd64"; ARCH_NAME="AMD64" ;;
    aarch64|arm64) DOCKER_ARCH="linux/arm64"; ARCH_NAME="ARM64" ;;
    armv7l|armhf) DOCKER_ARCH="linux/arm/v7"; ARCH_NAME="ARMv7" ;;
    *) DOCKER_ARCH="linux/amd64"; ARCH_NAME="AMD64 (default)" ;;
esac

log_info "🖥️  Detected architecture: $ARCH → $ARCH_NAME"
log_info "🐳 Docker target: $DOCKER_ARCH"
echo ""

# Check required files
log_info "📋 Checking required files..."
required_files=("Dockerfile" "docker-compose.yml" "requirements.txt")
for file in "${required_files[@]}"; do
    if [[ ! -f "$file" ]]; then
        echo "❌ Missing file: $file"
        exit 1
    fi
done
log_success "✅ All required files present"
echo ""

# Build Docker image
log_info "🏗️  Building Docker image for $ARCH_NAME..."

# Try buildx first, fallback to standard build
if command -v docker &> /dev/null && docker buildx version &> /dev/null 2>&1; then
    log_info "Using Docker Buildx for multi-platform build..."
    
    # Create builder if needed
    if ! docker buildx ls | grep -q "solaredge-builder"; then
        docker buildx create --name solaredge-builder --use --bootstrap 2>/dev/null || true
    fi
    
    # Build with buildx
    if docker buildx build \
        --platform "$DOCKER_ARCH" \
        --tag solaredge-scanwriter:latest \
        --load \
        . 2>/dev/null; then
        log_success "✅ Multi-platform build completed"
    else
        log_warning "⚠️  Buildx failed, using standard build..."
        docker build -t solaredge-scanwriter:latest .
        log_success "✅ Standard build completed"
    fi
else
    log_info "Using standard Docker build..."
    docker build -t solaredge-scanwriter:latest .
    log_success "✅ Build completed"
fi

echo ""

# Verify image
log_info "🔍 Verifying built image..."
if docker images solaredge-scanwriter:latest --format "{{.Repository}}:{{.Tag}}" | grep -q "solaredge-scanwriter:latest"; then
    IMAGE_SIZE=$(docker images solaredge-scanwriter:latest --format "{{.Size}}" 2>/dev/null || echo "unknown")
    log_success "✅ Image built successfully - Size: $IMAGE_SIZE"
else
    echo "❌ Image not found after build"
    exit 1
fi

echo ""
log_success "🎉 Docker build completed!"
echo ""
echo -e "${BLUE}📋 Next steps:${NC}"
echo -e "   ${YELLOW}docker compose up -d${NC}     # Start services"
echo -e "   ${YELLOW}docker compose ps${NC}        # Check status"
echo -e "   ${YELLOW}docker compose logs -f${NC}   # View logs"
echo ""