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

# Start services automatically
log_info "🚀 Starting Docker services..."
docker compose up -d

if [[ $? -eq 0 ]]; then
    log_success "✅ Services started successfully"
    
    # Wait for services to be ready
    log_info "⏳ Waiting for services to be ready..."
    sleep 15
    
    # Configure Grafana automatically
    log_info "📊 Configuring Grafana..."
    
    # Wait for Grafana to be ready
    for i in {1..30}; do
        if curl -s http://localhost:3000/api/health >/dev/null 2>&1; then
            break
        fi
        sleep 2
    done
    
    # Configure Sun and Moon data source
    log_info "☀️ Configuring Sun and Moon data source..."
    SUNMOON_RESPONSE=$(curl -s -X POST http://localhost:3000/api/datasources \
        -u "admin:admin" \
        -H "Content-Type: application/json" \
        -d "{
            \"name\": \"Sun and Moon\",
            \"type\": \"fetzerch-sunandmoon-datasource\",
            \"access\": \"proxy\",
            \"jsonData\": {
                \"latitude\": 40.8199,
                \"longitude\": 14.3413
            }
        }" 2>/dev/null)
    
    if echo "$SUNMOON_RESPONSE" | grep -q '"id"'; then
        log_success "✅ Sun and Moon data source configured"
    fi
    
    # Get data source UIDs and fix dashboard
    sleep 5
    DATASOURCES_LIST=$(curl -s http://localhost:3000/api/datasources -u "admin:admin" 2>/dev/null)
    INFLUX_UID=$(echo "$DATASOURCES_LIST" | jq -r '.[] | select(.name=="Solaredge") | .uid' 2>/dev/null)
    SUNMOON_UID=$(echo "$DATASOURCES_LIST" | jq -r '.[] | select(.name=="Sun and Moon") | .uid' 2>/dev/null)
    
    if [[ -n "$INFLUX_UID" && "$INFLUX_UID" != "null" ]]; then
        log_info "🔧 Importing dashboard with correct UIDs..."
        
        # Create temporary dashboard with fixed UIDs
        TEMP_DASHBOARD="/tmp/dashboard-solaredge-temp.json"
        cp "grafana/dashboard-solaredge.json" "$TEMP_DASHBOARD"
        
        # Fix InfluxDB UID
        jq --arg uid "$INFLUX_UID" '
            walk(
                if type == "object" and .type == "influxdb" then
                    .uid = $uid
                else
                    .
                end
            )
        ' "$TEMP_DASHBOARD" > "${TEMP_DASHBOARD}.tmp" && mv "${TEMP_DASHBOARD}.tmp" "$TEMP_DASHBOARD"
        
        # Fix Sun and Moon UID if available
        if [[ -n "$SUNMOON_UID" && "$SUNMOON_UID" != "null" ]]; then
            jq --arg uid "$SUNMOON_UID" '
                walk(
                    if type == "object" and .type == "fetzerch-sunandmoon-datasource" then
                        .uid = $uid
                    else
                        .
                    end
                )
            ' "$TEMP_DASHBOARD" > "${TEMP_DASHBOARD}.tmp" && mv "${TEMP_DASHBOARD}.tmp" "$TEMP_DASHBOARD"
        fi
        
        # Import dashboard
        IMPORT_PAYLOAD="/tmp/dashboard-import-payload.json"
        jq -n --slurpfile dashboard "$TEMP_DASHBOARD" '{
            dashboard: $dashboard[0],
            overwrite: true,
            message: "Imported by Docker setup"
        }' > "$IMPORT_PAYLOAD" 2>/dev/null
        
        if [[ -f "$IMPORT_PAYLOAD" ]]; then
            IMPORT_RESPONSE=$(curl -s -X POST http://localhost:3000/api/dashboards/db \
                -u "admin:admin" \
                -H "Content-Type: application/json" \
                -d @"$IMPORT_PAYLOAD" 2>/dev/null)
            
            if echo "$IMPORT_RESPONSE" | grep -q '"status":"success"'; then
                log_success "✅ Dashboard imported successfully"
            fi
            
            rm -f "$IMPORT_PAYLOAD" "$TEMP_DASHBOARD"
        fi
    fi
    
    # Generate web endpoints
    log_info "🔍 Generating web endpoints..."
    docker exec solaredge-scanwriter python main.py --scan >/dev/null 2>&1 || true
    
    echo ""
    log_success "🎉 Setup completed!"
    echo ""
    echo -e "${BLUE}📊 Services available:${NC}"
    echo -e "   GUI SolarEdge: ${YELLOW}http://localhost:8092${NC}"
    echo -e "   InfluxDB:      ${YELLOW}http://localhost:8086${NC}"
    echo -e "   Grafana:       ${YELLOW}http://localhost:3000${NC}"
    echo ""
else
    echo "❌ Failed to start services"
    exit 1
fi