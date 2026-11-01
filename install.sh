#!/bin/bash
# SolarEdge Data Collector - Installation Script
# Usage: curl -sSL https://raw.githubusercontent.com/frezeen/Solaredge_ScanWriter/main/install.sh | bash

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"; }
warn() { echo -e "${YELLOW}[$(date +'%H:%M:%S')] WARNING: $1${NC}"; }
error() { echo -e "${RED}[$(date +'%H:%M:%S')] ERROR: $1${NC}"; }
info() { echo -e "${BLUE}[$(date +'%H:%M:%S')] INFO: $1${NC}"; }

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                SolarEdge Data Collector                      ║"
echo "║                    Installation Script                       ║"
echo "║              github.com/frezeen/Solaredge_ScanWriter         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Require root
if [[ $EUID -ne 0 ]]; then
    error "This script must be run as root"
    echo "Please run: sudo $0"
    exit 1
fi

# Detect platform and architecture
ARCH=$(uname -m)
OS_ID=$(grep '^ID=' /etc/os-release | cut -d'=' -f2 | tr -d '"')
OS_VERSION=$(grep '^VERSION_ID=' /etc/os-release | cut -d'=' -f2 | tr -d '"')
IS_RASPBERRY_PI=false

# Check if running on Raspberry Pi
if [[ -f /proc/device-tree/model ]] && grep -q "Raspberry Pi" /proc/device-tree/model; then
    IS_RASPBERRY_PI=true
    info "🍓 Raspberry Pi detected: $(cat /proc/device-tree/model)"
elif [[ "$ARCH" == "armv7l" || "$ARCH" == "aarch64" ]] && [[ "$OS_ID" == "debian" ]]; then
    IS_RASPBERRY_PI=true
    info "🍓 ARM-based Debian detected (likely Raspberry Pi): $ARCH"
fi

# Check if running on supported OS
if ! grep -qE "(Debian|Ubuntu)" /etc/os-release; then
    warn "This script is designed for Debian/Ubuntu. Proceeding anyway..."
fi

if [[ "$IS_RASPBERRY_PI" == "true" ]]; then
    info "🔧 Applying Raspberry Pi optimizations..."
fi

log "🚀 Starting SolarEdge Data Collector installation..."

# Ask for passwords before installation
echo ""
info "📝 Configuration Setup"
echo "Please provide passwords for InfluxDB and Grafana."
echo "Press Enter to use default values."
echo ""

# Check if running via pipe (no interactive terminal)
if [ -t 0 ]; then
    # Interactive mode - prompt for passwords
    read -p "InfluxDB admin password (default: solaredge123): " CUSTOM_INFLUX_PASSWORD
    INFLUX_PASSWORD="${CUSTOM_INFLUX_PASSWORD:-solaredge123}"

    read -p "Grafana admin password (default: admin): " CUSTOM_GRAFANA_PASSWORD
    GRAFANA_PASS="${CUSTOM_GRAFANA_PASSWORD:-admin}"
else
    # Non-interactive mode (piped from curl) - use defaults
    warn "Running in non-interactive mode, using default passwords"
    INFLUX_PASSWORD="solaredge123"
    GRAFANA_PASS="admin"
fi

# Set other credentials
INFLUX_USERNAME="admin"
GRAFANA_USER="admin"
GRAFANA_URL="http://localhost:3000"

echo ""
log "✅ Configuration saved"
echo ""

# Install basic dependencies
log "📦 Installing basic dependencies..."
apt-get update -qq

# Install packages in groups to handle potential failures
log "Installing core packages..."
apt-get install -y -qq curl wget git unzip >/dev/null 2>&1

log "Installing Python packages..."
apt-get install -y -qq python3 python3-pip python3-dev >/dev/null 2>&1

# Verify Python 3 installation
log "Verifying Python 3 installation..."
if ! command -v python3 &> /dev/null; then
    error "Python 3 not found after installation"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
log "Python version detected: $PYTHON_VERSION"

# Check if Python 3.11+ is available
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
    warn "Python $PYTHON_VERSION found, but Python 3.11+ is required"

    # Try to install Python 3.11 from deadsnakes PPA (Ubuntu/Debian)
    log "Attempting to install Python 3.11..."

    if command -v add-apt-repository &> /dev/null || apt-get install -y -qq software-properties-common >/dev/null 2>&1; then
        log "Adding deadsnakes PPA for Python 3.11..."
        add-apt-repository -y ppa:deadsnakes/ppa >/dev/null 2>&1 || true
        apt-get update -qq >/dev/null 2>&1

        if apt-get install -y -qq python3.11 python3.11-dev python3.11-venv >/dev/null 2>&1; then
            log "✅ Python 3.11 installed successfully"
            # Update alternatives to use Python 3.11 as default python3
            update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 >/dev/null 2>&1
            update-alternatives --set python3 /usr/bin/python3.11 >/dev/null 2>&1

            # Reinstall pip for Python 3.11
            curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11 >/dev/null 2>&1

            PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
            log "Python updated to version: $PYTHON_VERSION"
        else
            error "Failed to install Python 3.11 from deadsnakes PPA"
            error "Your system has Python $PYTHON_VERSION, but this project requires Python 3.11+"
            error ""
            error "Please use Docker installation instead:"
            error "  curl -sSL https://get.docker.com | sh"
            error "  git clone https://github.com/frezeen/Solaredge_ScanWriter.git"
            error "  cd Solaredge_ScanWriter"
            error "  docker compose up -d"
            exit 1
        fi
    else
        error "Cannot install Python 3.11 automatically on this system"
        error "Your system has Python $PYTHON_VERSION, but this project requires Python 3.11+"
        error ""
        error "Please use Docker installation instead:"
        error "  curl -sSL https://get.docker.com | sh"
        error "  git clone https://github.com/frezeen/Solaredge_ScanWriter.git"
        error "  cd Solaredge_ScanWriter"
        error "  docker compose up -d"
        exit 1
    fi
fi

# Final verification
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
log "✅ Python $PYTHON_VERSION is ready"

log "Installing build tools..."
apt-get install -y -qq build-essential >/dev/null 2>&1

log "Installing system utilities..."
apt-get install -y -qq nano htop systemd cron >/dev/null 2>&1

log "Installing repository tools..."
apt-get install -y -qq apt-transport-https gnupg ca-certificates >/dev/null 2>&1

# Clone project from GitHub
log "📥 Cloning project from GitHub..."
APP_DIR="/opt/Solaredge_ScanWriter"

# Rimuovi directory esistente se presente
if [[ -d "$APP_DIR" ]]; then
    log "⚠️  Directory esistente trovata, creando backup..."
    mv "$APP_DIR" "${APP_DIR}.backup.$(date +%Y%m%d_%H%M%S)"
fi

# Clone repository
{
    git clone --quiet https://github.com/frezeen/Solaredge_ScanWriter.git "$APP_DIR"
} >/dev/null 2>&1
if [[ $? -eq 0 ]]; then
    log "✅ Repository clonato con successo"

    # Entra nella directory
    cd "$APP_DIR"

    if [[ -d "$APP_DIR" ]]; then
        log "🔧 Starting installation process..."

        # Create required directories
        log "📂 Creating required directories..."
        mkdir -p "$APP_DIR"/{logs,cache,cookies,config,systemd,scripts,grafana}

        # Create requirements.txt if not exists
        if [[ ! -f "$APP_DIR/requirements.txt" ]]; then
            log "📝 Creating requirements.txt..."
            tee "$APP_DIR/requirements.txt" > /dev/null << 'REQS'
aiohttp>=3.8.0
influxdb-client>=1.36.0
PyYAML>=6.0
pymodbus==3.5.4
solaredge-modbus>=0.8.0
requests>=2.28.0
python-dotenv>=1.0.0
python-dateutil>=2.8.0
aiofiles>=22.1.0
jinja2>=3.1.0
aiohttp-jinja2>=1.5.0
pytz>=2023.3
REQS
        fi

        # Install Python dependencies system-wide
        log "🐍 Installing Python dependencies..."

        # Raspberry Pi specific optimizations
        if [[ "$IS_RASPBERRY_PI" == "true" ]]; then
            log "🍓 Installing Raspberry Pi specific packages..."
            # Install system packages that are better from apt on RPi
            apt-get install -y -qq python3-yaml python3-requests python3-dateutil python3-tz >/dev/null 2>&1 || true

            # Use piwheels for faster ARM builds
            export PIP_EXTRA_INDEX_URL="https://www.piwheels.org/simple"
            log "🔧 Using piwheels for ARM-optimized packages"
        fi

        # Try different installation methods
        if ! pip3 install -r "$APP_DIR/requirements.txt"; then
            warn "Failed to install Python dependencies with standard pip3"

            if [[ "$IS_RASPBERRY_PI" == "true" ]]; then
                log "🍓 Trying Raspberry Pi specific installation..."
                # Try with no-build-isolation for problematic packages
                if ! pip3 install -r "$APP_DIR/requirements.txt" --no-build-isolation; then
                    log "Trying with --break-system-packages flag..."
                    pip3 install -r "$APP_DIR/requirements.txt" --break-system-packages --no-build-isolation
                fi
            else
                log "Trying with --break-system-packages flag (Python 3.11+)..."
                if ! pip3 install -r "$APP_DIR/requirements.txt" --break-system-packages; then
                    error "Failed to install Python dependencies"
                    echo "Please run manually: cd $APP_DIR && pip3 install -r requirements.txt"
                    echo "Or try: pip3 install -r requirements.txt --break-system-packages"
                    exit 1
                fi
            fi
        fi

        # Install InfluxDB
        log "🗄️ Installing InfluxDB..."

        if [[ "$IS_RASPBERRY_PI" == "true" ]]; then
            log "🍓 Installing InfluxDB for Raspberry Pi (ARM)..."
            # For Raspberry Pi, try repository first, then fallback to direct download
            rm -f /usr/share/keyrings/influxdata-archive-keyring.gpg
            curl -s https://repos.influxdata.com/influxdata-archive_compat.key | gpg --dearmor -o /usr/share/keyrings/influxdata-archive-keyring.gpg 2>/dev/null
            echo "deb [signed-by=/usr/share/keyrings/influxdata-archive-keyring.gpg] https://repos.influxdata.com/debian stable main" | tee /etc/apt/sources.list.d/influxdb.list >/dev/null

            apt-get update -qq >/dev/null 2>&1
            if ! apt-get install -y -qq influxdb2 >/dev/null 2>&1; then
                warn "InfluxDB repository failed on ARM, trying direct download..."
                INFLUX_VERSION="2.7.4"
                DEB_ARCH=$(dpkg --print-architecture)

                # Map architecture names for InfluxDB downloads
                case "$DEB_ARCH" in
                    "armhf") INFLUX_ARCH="armhf" ;;
                    "arm64") INFLUX_ARCH="arm64" ;;
                    "amd64") INFLUX_ARCH="amd64" ;;
                    *) INFLUX_ARCH="$DEB_ARCH" ;;
                esac

                INFLUX_URL="https://dl.influxdata.com/influxdb/releases/influxdb2_${INFLUX_VERSION}-1_${INFLUX_ARCH}.deb"
                log "Downloading InfluxDB for $INFLUX_ARCH..."

                if curl -LO "$INFLUX_URL" >/dev/null 2>&1; then
                    dpkg -i "influxdb2_${INFLUX_VERSION}-1_${INFLUX_ARCH}.deb" >/dev/null 2>&1 || apt-get install -f -y -qq
                    rm -f "influxdb2_${INFLUX_VERSION}-1_${INFLUX_ARCH}.deb"
                else
                    error "Failed to download InfluxDB for ARM architecture"
                    warn "You may need to install InfluxDB manually"
                    warn "See: https://docs.influxdata.com/influxdb/v2.7/install/"
                fi
            fi
        else
            # Standard x86_64 installation
            rm -f /usr/share/keyrings/influxdata-archive-keyring.gpg
            curl -s https://repos.influxdata.com/influxdata-archive_compat.key | gpg --dearmor -o /usr/share/keyrings/influxdata-archive-keyring.gpg 2>/dev/null
            echo "deb [signed-by=/usr/share/keyrings/influxdata-archive-keyring.gpg] https://repos.influxdata.com/debian stable main" | tee /etc/apt/sources.list.d/influxdb.list >/dev/null

            apt-get update -qq >/dev/null 2>&1
            if ! apt-get install -y -qq influxdb2 >/dev/null 2>&1; then
                warn "Failed to install InfluxDB from repository, trying direct download..."
                INFLUX_VERSION="2.7.4"
                ARCH=$(dpkg --print-architecture)
                curl -LO "https://dl.influxdata.com/influxdb/releases/influxdb2_${INFLUX_VERSION}-1_${ARCH}.deb" >/dev/null 2>&1
                dpkg -i "influxdb2_${INFLUX_VERSION}-1_${ARCH}.deb" >/dev/null 2>&1 || apt-get install -f -y -qq
                rm -f "influxdb2_${INFLUX_VERSION}-1_${ARCH}.deb"
            fi
        fi

        systemctl enable influxdb >/dev/null 2>&1
        systemctl start influxdb >/dev/null 2>&1
        sleep 10

        # Configure InfluxDB
        log "⚙️ Configuring InfluxDB..."
        # INFLUX_USERNAME and INFLUX_PASSWORD already set at script start
        INFLUX_ORG="fotovoltaico"
        INFLUX_BUCKET="Solaredge"
        INFLUX_BUCKET_REALTIME="Solaredge_Realtime"

        # Wait for InfluxDB to be ready
        log "Waiting for InfluxDB to be ready..."
        for i in {1..30}; do
            if curl -s http://localhost:8086/health >/dev/null 2>&1; then
                break
            fi
            if [[ $i -eq 30 ]]; then
                warn "InfluxDB may not be ready, continuing anyway..."
            fi
            sleep 2
        done

        # Install jq for JSON parsing
        apt-get install -y -qq jq >/dev/null 2>&1

        # Check if InfluxDB needs setup
        SETUP_STATUS=$(curl -s http://localhost:8086/api/v2/setup 2>/dev/null)

        if [[ -z "$SETUP_STATUS" ]] || echo "$SETUP_STATUS" | jq -e '.allowed == true' >/dev/null 2>&1; then
            log "Setting up InfluxDB initial configuration..."

            SETUP_RESPONSE=$(curl -s -X POST http://localhost:8086/api/v2/setup \
                -H "Content-Type: application/json" \
                -d "{
                    \"username\": \"$INFLUX_USERNAME\",
                    \"password\": \"$INFLUX_PASSWORD\",
                    \"org\": \"$INFLUX_ORG\",
                    \"bucket\": \"$INFLUX_BUCKET\"
                }")



            # Extract token using jq
            INFLUX_TOKEN=$(echo "$SETUP_RESPONSE" | jq -r '.auth.token // empty' 2>/dev/null)

            # Fallback: try different JSON structure
            if [[ -z "$INFLUX_TOKEN" || "$INFLUX_TOKEN" == "null" ]]; then
                INFLUX_TOKEN=$(echo "$SETUP_RESPONSE" | jq -r '.token // empty' 2>/dev/null)
            fi

            # Fallback: grep method
            if [[ -z "$INFLUX_TOKEN" || "$INFLUX_TOKEN" == "null" ]]; then
                INFLUX_TOKEN=$(echo "$SETUP_RESPONSE" | grep -o '"token":"[^"]*"' | cut -d'"' -f4)
            fi

            # Validate token
            if [[ -n "$INFLUX_TOKEN" && "$INFLUX_TOKEN" != "null" && ${#INFLUX_TOKEN} -gt 20 ]]; then
                log "✅ InfluxDB configured successfully (${INFLUX_TOKEN:0:20}...)"

                # Get organization ID for bucket creation
                ORG_RESPONSE=$(curl -s -X GET http://localhost:8086/api/v2/orgs \
                    -H "Authorization: Token $INFLUX_TOKEN")
                INFLUX_ORG_ID=$(echo "$ORG_RESPONSE" | jq -r ".orgs[] | select(.name==\"$INFLUX_ORG\") | .id" 2>/dev/null)

                if [[ -n "$INFLUX_ORG_ID" && "$INFLUX_ORG_ID" != "null" ]]; then
                    # Create realtime bucket with 2-day retention
                    log "📦 Creating realtime bucket with 2-day retention..."
                    REALTIME_BUCKET_RESPONSE=$(curl -s -X POST http://localhost:8086/api/v2/buckets \
                        -H "Authorization: Token $INFLUX_TOKEN" \
                        -H "Content-Type: application/json" \
                        -d "{
                            \"orgID\": \"$INFLUX_ORG_ID\",
                            \"name\": \"$INFLUX_BUCKET_REALTIME\",
                            \"description\": \"Realtime data with 2-day retention\",
                            \"retentionRules\": [{
                                \"type\": \"expire\",
                                \"everySeconds\": 172800
                            }]
                        }")
                else
                    warn "Could not retrieve organization ID for bucket creation"
                fi

                if echo "$REALTIME_BUCKET_RESPONSE" | grep -q '"name"'; then
                    log "✅ Realtime bucket created successfully"
                else
                    warn "Could not create realtime bucket automatically"
                fi
            else
                warn "❌ Could not extract InfluxDB token from setup"
                INFLUX_TOKEN="SETUP_FAILED_CONFIGURE_MANUALLY"
            fi
        else
            log "InfluxDB already configured"
            INFLUX_TOKEN="ALREADY_CONFIGURED_GET_FROM_UI"
        fi

        # Install Grafana
        log "📊 Installing Grafana..."

        if [[ "$IS_RASPBERRY_PI" == "true" ]]; then
            log "🍓 Installing Grafana for Raspberry Pi (ARM)..."

            # Try repository first
            rm -f /usr/share/keyrings/grafana-archive-keyring.gpg
            curl -s https://packages.grafana.com/gpg.key | gpg --dearmor -o /usr/share/keyrings/grafana-archive-keyring.gpg 2>/dev/null
            echo "deb [signed-by=/usr/share/keyrings/grafana-archive-keyring.gpg] https://packages.grafana.com/oss/deb stable main" | tee /etc/apt/sources.list.d/grafana.list >/dev/null

            apt-get update -qq >/dev/null 2>&1
            if ! apt-get install -y -qq grafana >/dev/null 2>&1; then
                warn "Grafana repository failed on ARM, trying direct download..."
                GRAFANA_VERSION="10.2.3"
                DEB_ARCH=$(dpkg --print-architecture)

                # Map architecture names for Grafana downloads
                case "$DEB_ARCH" in
                    "armhf") GRAFANA_ARCH="armhf" ;;
                    "arm64") GRAFANA_ARCH="arm64" ;;
                    "amd64") GRAFANA_ARCH="amd64" ;;
                    *) GRAFANA_ARCH="$DEB_ARCH" ;;
                esac

                GRAFANA_URL="https://dl.grafana.com/oss/release/grafana_${GRAFANA_VERSION}_${GRAFANA_ARCH}.deb"
                log "Downloading Grafana for $GRAFANA_ARCH..."

                if curl -LO "$GRAFANA_URL" >/dev/null 2>&1; then
                    dpkg -i "grafana_${GRAFANA_VERSION}_${GRAFANA_ARCH}.deb" >/dev/null 2>&1 || apt-get install -f -y -qq
                    rm -f "grafana_${GRAFANA_VERSION}_${GRAFANA_ARCH}.deb"
                else
                    error "Failed to download Grafana for ARM architecture"
                    warn "You may need to install Grafana manually"
                    warn "See: https://grafana.com/docs/grafana/latest/setup-grafana/installation/debian/"
                    # Continue without Grafana - not critical for core functionality
                fi
            fi
        else
            # Standard x86_64 installation
            rm -f /usr/share/keyrings/grafana-archive-keyring.gpg
            curl -s https://packages.grafana.com/gpg.key | gpg --dearmor -o /usr/share/keyrings/grafana-archive-keyring.gpg 2>/dev/null
            echo "deb [signed-by=/usr/share/keyrings/grafana-archive-keyring.gpg] https://packages.grafana.com/oss/deb stable main" | tee /etc/apt/sources.list.d/grafana.list >/dev/null

            apt-get update -qq >/dev/null 2>&1
            if ! apt-get install -y -qq grafana >/dev/null 2>&1; then
                warn "Failed to install Grafana from repository, trying direct download..."
                GRAFANA_VERSION="10.2.3"
                ARCH=$(dpkg --print-architecture)
                curl -LO "https://dl.grafana.com/oss/release/grafana_${GRAFANA_VERSION}_${ARCH}.deb" >/dev/null 2>&1
                dpkg -i "grafana_${GRAFANA_VERSION}_${ARCH}.deb" >/dev/null 2>&1 || apt-get install -f -y -qq
                rm -f "grafana_${GRAFANA_VERSION}_${ARCH}.deb"
            fi
        fi

        # Install Grafana plugins
        log "🔌 Installing Grafana plugins..."

        # Check if Grafana was installed successfully
        if command -v grafana-cli &> /dev/null; then
            if [[ "$IS_RASPBERRY_PI" == "true" ]]; then
                log "🍓 Installing Grafana plugins for Raspberry Pi..."
                # Some plugins might not be available for ARM, so we're more tolerant
                grafana-cli plugins install fetzerch-sunandmoon-datasource >/dev/null 2>&1 || warn "Sun-and-moon plugin not available for ARM (optional)"
                grafana-cli plugins install grafana-clock-panel >/dev/null 2>&1 || warn "Clock plugin not available for ARM (optional)"
            else
                grafana-cli plugins install fetzerch-sunandmoon-datasource >/dev/null 2>&1 || warn "Failed to install sun-and-moon plugin"
                grafana-cli plugins install grafana-clock-panel >/dev/null 2>&1 || warn "Failed to install clock plugin"
            fi
        else
            warn "Grafana CLI not available - skipping plugin installation"
        fi

        systemctl enable grafana-server >/dev/null 2>&1

        # Configure Grafana date formats BEFORE starting
        log "📅 Configuring Grafana date formats..."
        GRAFANA_INI="/etc/grafana/grafana.ini"
        if [[ -f "$GRAFANA_INI" ]]; then
            # Check if full_date is already configured correctly
            if ! grep -q "^full_date = DD/MM/YYYY HH:mm:ss" "$GRAFANA_INI"; then
                # Remove existing [date_formats] section if present (including commented lines)
                sed -i '/^\[date_formats\]/,/^\[/{/^\[date_formats\]/d; /^[^[].*=/d; /^#.*date.*format/d;}' "$GRAFANA_INI"

                # Add new date_formats section at the end
                cat >> "$GRAFANA_INI" << 'DATEFORMATS'

[date_formats]
# For information on what formatting patterns that are supported https://momentjs.com/docs/#/displaying/
# Default system date format used in time range picker and other places where full time is displayed
full_date = DD/MM/YYYY HH:mm:ss
# Used by graph and other places where we only show small intervals
interval_second = HH:mm:ss
interval_minute = HH:mm
interval_hour = HH:mm
interval_day = DD MMMM dddd
interval_month = MMMM YYYY
interval_year = YYYY
# Experimental feature
;use_browser_locale = false
# Default timezone for user preferences. Options are 'browser' for the browser local timezone or a timezone name from IANA Time Zone database, e.g. 'UTC' or 'Europe/Amsterdam' etc.
;default_timezone = browser
DATEFORMATS
                log "✅ Grafana date formats configured"
            else
                log "ℹ️ Grafana date formats already correctly configured"
            fi
        else
            warn "Grafana configuration file not found at $GRAFANA_INI"
        fi

        # Start Grafana AFTER configuration
        systemctl start grafana-server >/dev/null 2>&1

        # Wait for Grafana to be ready
        log "Waiting for Grafana to be ready..."

        # Disable exit on error for health checks
        set +e

        GRAFANA_READY=false
        for i in {1..60}; do
            # Simple HTTP 200 check is most reliable
            HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/health 2>/dev/null)
            if [[ "$HTTP_CODE" == "200" ]]; then
                log "✅ Grafana is ready"
                GRAFANA_READY=true
                break
            fi

            # Show progress every 10 iterations (20 seconds)
            if [[ $((i % 10)) -eq 0 ]]; then
                log "Still waiting... (${i}/60 attempts)"
            fi

            sleep 2
        done

        # Re-enable exit on error
        set -e

        if [[ "$GRAFANA_READY" != "true" ]]; then
            warn "Grafana did not become ready after 120 seconds"
            warn "Attempting configuration anyway - you may need to configure manually"
        fi

        # Configure Grafana data source
        log "⚙️ Configuring Grafana data source..."
        # Note: GRAFANA_URL, GRAFANA_USER, GRAFANA_PASS already set at script start

        # Disable exit on error for Grafana configuration
        set +e

        # Test if default credentials work, if not try to set password
        log "Testing Grafana authentication..."
        AUTH_TEST=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/datasources -u "$GRAFANA_USER:$GRAFANA_PASS" 2>/dev/null)
        log "Auth test with configured credentials: HTTP $AUTH_TEST"

        if [[ "$AUTH_TEST" != "200" ]]; then
            # Try with default admin:admin first
            AUTH_TEST_DEFAULT=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/datasources -u "admin:admin" 2>/dev/null)
            log "Auth test with admin:admin: HTTP $AUTH_TEST_DEFAULT"

            if [[ "$AUTH_TEST_DEFAULT" == "200" ]] && [[ "$GRAFANA_PASS" != "admin" ]]; then
                # Default credentials work, change password
                log "Setting Grafana admin password..."
                PASS_CHANGE=$(curl -s -X PUT http://localhost:3000/api/user/password \
                    -u "admin:admin" \
                    -H "Content-Type: application/json" \
                    -d "{\"oldPassword\":\"admin\",\"newPassword\":\"$GRAFANA_PASS\",\"confirmNew\":\"$GRAFANA_PASS\"}")
                log "Password change response: $PASS_CHANGE"
            elif [[ "$AUTH_TEST_DEFAULT" == "200" ]]; then
                # Using default admin:admin
                log "Using default Grafana credentials (admin:admin)"
                GRAFANA_USER="admin"
                GRAFANA_PASS="admin"
            else
                warn "Grafana authentication failed with both configured and default credentials"
                warn "HTTP codes: configured=$AUTH_TEST, default=$AUTH_TEST_DEFAULT"
            fi
        else
            log "Configured Grafana credentials work"
        fi

        # Create InfluxDB data source in Grafana
        DATASOURCE_RESPONSE=$(curl -s -X POST http://localhost:3000/api/datasources \
            -u "$GRAFANA_USER:$GRAFANA_PASS" \
            -H "Content-Type: application/json" \
            -d "{
                \"name\": \"Solaredge\",
                \"type\": \"influxdb\",
                \"access\": \"proxy\",
                \"url\": \"http://localhost:8086\",
                \"jsonData\": {
                    \"version\": \"Flux\",
                    \"organization\": \"$INFLUX_ORG\",
                    \"defaultBucket\": \"$INFLUX_BUCKET\",
                    \"tlsSkipVerify\": true
                },
                \"secureJsonData\": {
                    \"token\": \"$INFLUX_TOKEN\"
                },
                \"isDefault\": true
            }" 2>/dev/null)

        if echo "$DATASOURCE_RESPONSE" | grep -q '"id"'; then
            log "✅ Grafana InfluxDB data source configured successfully"
        else
            warn "Could not configure Grafana InfluxDB data source automatically"
            log "Response: $DATASOURCE_RESPONSE"
            warn "You can configure it manually in Grafana UI"
        fi

        # Configure Sun and Moon data source
        log "☀️ Configuring Sun and Moon data source..."
        SUNMOON_RESPONSE=$(curl -s -X POST http://localhost:3000/api/datasources \
            -u "$GRAFANA_USER:$GRAFANA_PASS" \
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
            log "✅ Grafana Sun and Moon data source configured successfully"
        else
            warn "Could not configure Sun and Moon data source automatically. You can configure it manually in Grafana UI."
        fi

        # Import Grafana dashboard with correct UIDs
        DASHBOARD_FILE="$APP_DIR/grafana/dashboard-solaredge.json"

        if [[ -f "$DASHBOARD_FILE" ]]; then
            log "📊 Importing Grafana dashboard..."

            # Disable exit on error for this section
            set +e

            # Stessa logica dell'update: gli uid dei datasource stanno in
            # {"datasource": {"name": ...}} con il plugin in "group", fuori dalla
            # portata di un filtro su {"type": "influxdb"}, e la dashboard v2 va
            # scritta con l'API v2 o i pannelli si perdono.
            GRAFANA_URL="$GRAFANA_URL" GRAFANA_USER="$GRAFANA_USER" \
                GRAFANA_PASSWORD="$GRAFANA_PASS" \
                python3 "$APP_DIR/scripts/smart_update.py" --dashboard-only \
                || warn "Could not import Grafana dashboard automatically. You can import it manually from grafana/dashboard-solaredge.json"
        else
            warn "Dashboard file not found at $APP_DIR/grafana/dashboard-solaredge.json"
        fi

        # Re-enable exit on error
        set -e

        # Create .env file
        log "📝 Creating configuration file..."
        if [[ ! -f "$APP_DIR/.env" ]]; then
            tee "$APP_DIR/.env" > /dev/null << ENV
# SolarEdge ScanWriter - Environment Variables
# Generated by installation script

# === SOLAREDGE API CONFIGURATION ===
SOLAREDGE_API_KEY=REPLACE_WITH_YOUR_API_KEY
SOLAREDGE_USERNAME=your.email@example.com
SOLAREDGE_PASSWORD=REPLACE_WITH_YOUR_PASSWORD
SOLAREDGE_SITE_ID=123456
SOLAREDGE_API_BASE_URL=https://monitoringapi.solaredge.com
SOLAREDGE_BASE_URL=https://monitoring.solaredge.com
SOLAREDGE_LOGIN_URL=https://monitoring.solaredge.com/solaredge-apigw/api/login
API_TIMEOUT_SECONDS=30
API_RATE_LIMIT_SECONDS=1
API_RETRY_ATTEMPTS=3
API_RETRY_DELAY_SECONDS=2

# === SCHEDULER CONFIGURATION ===
SCHEDULER_API_DELAY_SECONDS=1
SCHEDULER_WEB_DELAY_SECONDS=2
SCHEDULER_REALTIME_DELAY_SECONDS=0
SCHEDULER_SKIP_DELAY_ON_CACHE_HIT=true

# === LOOP INTERVALS CONFIGURATION ===
LOOP_API_INTERVAL_MINUTES=15
LOOP_WEB_INTERVAL_MINUTES=15
LOOP_REALTIME_INTERVAL_SECONDS=5

# === REALTIME CONFIGURATION ===
REALTIME_MODBUS_HOST=192.168.1.100
REALTIME_MODBUS_PORT=1502
REALTIME_MODBUS_TIMEOUT=1
REALTIME_MODBUS_UNIT=1
MODBUS_RETRIES=3
MODBUS_ENABLED=true

# === INFLUXDB CONFIGURATION ===
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=$INFLUX_TOKEN
INFLUXDB_ORG=$INFLUX_ORG
INFLUXDB_BUCKET=Solaredge
INFLUXDB_BUCKET_REALTIME=Solaredge_Realtime
INFLUX_DRY_FILE=logs/influx_dry_points.jsonl
INFLUX_DRY_MODE=false
INFLUX_BATCH_SIZE=500
INFLUX_FLUSH_INTERVAL_MS=1000
INFLUX_JITTER_INTERVAL_MS=100
INFLUX_RETRY_INTERVAL_MS=1000
INFLUX_MAX_RETRIES=5

# === LOGGING CONFIGURATION ===
LOG_LEVEL=INFO
LOG_FILE_LOGGING=true
LOG_DIRECTORY=logs

# === GUI CONFIGURATION ===
GUI_HOST=127.0.0.1
GUI_PORT=8092

# === GRAFANA CONFIGURATION ===
GRAFANA_URL=$GRAFANA_URL
GRAFANA_USER=$GRAFANA_USER
GRAFANA_PASSWORD=$GRAFANA_PASS

# === ENVIRONMENT SETTINGS ===
ENVIRONMENT=production
TIMEZONE=Europe/Rome

# === GLOBAL CONFIGURATION ===
GLOBAL_TIMEOUT_SECONDS=30
GLOBAL_WEB_REQUEST_TIMEOUT=40
GLOBAL_API_REQUEST_TIMEOUT=20
GLOBAL_BATCH_REQUEST_TIMEOUT=60
FILTER_DEBUG=false

# === WEB SCRAPING CONFIGURATION ===
SOLAREDGE_WEB_BASE_URL=https://monitoring.solaredge.com
SOLAREDGE_COOKIE_FILE=cookies/web_cookies.json
SOLAREDGE_SESSION_TIMEOUT_SECONDS=3600
ENV
        fi

        # Create systemd service
        log "🔧 Creating systemd service..."
        tee /etc/systemd/system/solaredge-scanwriter.service > /dev/null << 'SERVICE'
[Unit]
Description=Solaredge_ScanWriter (GUI + Loop 24/7)
After=network.target influxdb.service
Wants=network.target
Requires=influxdb.service

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/Solaredge_ScanWriter
Environment=PYTHONPATH=/opt/Solaredge_ScanWriter

# Run with system Python
ExecStart=/usr/bin/python3 /opt/Solaredge_ScanWriter/main.py

# Restart configuration
Restart=always
RestartSec=10
StartLimitInterval=300
StartLimitBurst=5

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=solaredge-scanwriter

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/Solaredge_ScanWriter

[Install]
WantedBy=multi-user.target
SERVICE

        systemctl daemon-reload >/dev/null 2>&1

        # Configure log rotation
        log "🔄 Configuring log rotation..."
        if [[ -f "$APP_DIR/config/logrotate.conf" ]]; then
            cp "$APP_DIR/config/logrotate.conf" /etc/logrotate.d/solaredge-collector
            chown root:root /etc/logrotate.d/solaredge-collector
            chmod 644 /etc/logrotate.d/solaredge-collector

            # Update paths in logrotate config to match actual installation
            sed -i "s|/opt/solaredge-collector|$APP_DIR|g" /etc/logrotate.d/solaredge-collector

            # Update service names to match actual systemd service
            sed -i "s|solaredge-collector|solaredge-scanwriter|g" /etc/logrotate.d/solaredge-collector
            sed -i "s|solaredge-gui|solaredge-scanwriter|g" /etc/logrotate.d/solaredge-collector

            log "✅ Log rotation configured - logs will be rotated daily and kept for 7 days"
        else
            warn "Logrotate configuration file not found at $APP_DIR/config/logrotate.conf, skipping log rotation setup"
        fi

        # Configure systemd journal retention
        log "📰 Configuring systemd journal retention..."

        # Create journald configuration directory if not exists
        mkdir -p /etc/systemd/journald.conf.d

        # Configure journal retention for our service specifically
        tee /etc/systemd/journald.conf.d/solaredge-retention.conf > /dev/null << 'JOURNAL'
# SolarEdge Data Collector - Journal Retention Configuration
# Keep journal logs for maximum 48 hours to prevent disk space issues

[Journal]
# Maximum retention time (48 hours)
MaxRetentionSec=48h

# Maximum disk usage for journal (100MB)
SystemMaxUse=100M

# Maximum size for individual journal files (10MB)
SystemMaxFileSize=10M

# Force sync every 5 minutes to ensure logs are written
SyncIntervalSec=5m

# Compress journal files
Compress=yes

# Forward to syslog (optional - disable if not needed)
ForwardToSyslog=no
JOURNAL

        # Apply journal configuration
        systemctl restart systemd-journald >/dev/null 2>&1 || warn "Could not restart journald service"

        # Configure journal vacuum for immediate cleanup of old logs
        log "🧹 Cleaning up old journal logs..."
        journalctl --vacuum-time=48h >/dev/null 2>&1 || warn "Could not vacuum old journal logs"
        journalctl --vacuum-size=100M >/dev/null 2>&1 || warn "Could not vacuum journal by size"

        log "✅ Journal retention configured - systemd logs kept for max 48 hours (100MB limit)"

        # Optional: Create cron job for automatic journal cleanup (runs daily at 3 AM)
        log "⏰ Setting up automatic journal cleanup..."
        CRON_JOB="0 3 * * * /usr/bin/journalctl --vacuum-time=48h --vacuum-size=100M >/dev/null 2>&1"

        # Add cron job for root user (journalctl requires root privileges)
        if ! crontab -l 2>/dev/null | grep -q "journalctl --vacuum"; then
            (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
            log "✅ Daily journal cleanup scheduled at 3:00 AM"
        else
            log "ℹ️ Journal cleanup cron job already exists"
        fi

        # Create helper scripts
        log "📝 Creating helper scripts..."
        tee "$APP_DIR/test.sh" > /dev/null << 'TEST'
#!/bin/bash
# SolarEdge Installation Test Script

cd /opt/Solaredge_ScanWriter

echo "=== SolarEdge Installation Test ==="
echo ""

# Test System Python
echo "🐍 System Python:"
if command -v python3 &> /dev/null; then
    echo "✅ System Python exists"
    echo "  Python path: $(which python3)"
    echo "  Python version: $(python3 --version)"
else
    echo "❌ System Python not found"
fi
echo ""

# Test installed packages
echo "📦 Installed Python packages:"
if command -v pip3 &> /dev/null; then
    pip3 list | grep -E "(aiohttp|influxdb|yaml|pymodbus|solaredge)" | head -10
else
    echo "❌ pip3 not found"
fi
echo ""

# Test services
echo "🔧 Services status:"
echo "  SolarEdge: $(systemctl is-active solaredge-scanwriter 2>/dev/null || echo 'not-found')"
echo "  InfluxDB: $(systemctl is-active influxdb 2>/dev/null || echo 'not-found')"
echo "  Grafana: $(systemctl is-active grafana-server 2>/dev/null || echo 'not-found')"
echo ""

# Test directories and permissions
echo "📁 Directory structure:"
ls -la /opt/Solaredge_ScanWriter/ | head -10
echo ""

# Test configuration
echo "⚙️ Configuration:"
if [[ -f .env ]]; then
    echo "✅ .env file exists"
    echo "  Key variables:"
    grep -E "^[A-Z].*=" .env | head -5 | sed 's/=.*/=***/' | sed 's/^/    /'
else
    echo "❌ .env file missing"
fi
echo ""

# Test main application
echo "🧪 Application test:"
if [[ -f main.py ]]; then
    echo "✅ main.py exists"
    if python3 -c "import main" 2>/dev/null; then
        echo "✅ Main module imports successfully"
    else
        echo "⚠️ Main module has import issues (check dependencies)"
    fi
else
    echo "❌ main.py not found"
fi

echo ""
echo "=== Test Complete ==="
TEST

        tee "$APP_DIR/status.sh" > /dev/null << 'STATUS'
#!/bin/bash
# SolarEdge Service Status Script

echo "=== Solaredge_ScanWriter Status ==="
echo ""

# Service status (only if service is loaded)
echo "🔧 Service Status:"
if systemctl is-enabled solaredge-scanwriter >/dev/null 2>&1; then
    systemctl status solaredge-scanwriter --no-pager 2>/dev/null || echo "  Service not started yet"
else
    echo "  Service created but not enabled yet"
    echo "  Run: systemctl enable --now solaredge-scanwriter"
fi
echo ""

# Process information
echo "🔍 Process Information:"
if pgrep -f "solaredge" >/dev/null; then
    echo "✅ SolarEdge processes running:"
    ps aux | grep -E "(solaredge|main\.py)" | grep -v grep | head -5
else
    echo "❌ No SolarEdge processes found"
fi
echo ""

# System Python check
echo "🐍 System Python:"
if command -v python3 &> /dev/null; then
    echo "✅ System Python available"
    echo "  Python: $(python3 --version)"
else
    echo "❌ System Python not found"
fi
echo ""

# Recent logs
echo "📋 Recent Logs (last 15 lines):"
journalctl -u solaredge-scanwriter --lines=15 --no-pager
echo ""

# Log files
echo "📁 Log Files:"
if [[ -d /opt/Solaredge_ScanWriter/logs ]]; then
    find /opt/Solaredge_ScanWriter/logs -name "*.log" -type f 2>/dev/null | head -5 | while read file; do
        size=$(du -h "$file" 2>/dev/null | cut -f1)
        modified=$(stat -c %y "$file" 2>/dev/null | cut -d' ' -f1)
        echo "  • $(basename "$file"): $size (modified: $modified)"
    done
else
    echo "  ❌ Log directory not found"
fi
STATUS

        # Create manual run script for testing
        tee "$APP_DIR/run-manual.sh" > /dev/null << 'MANUAL'
#!/bin/bash
# Manual run script for testing SolarEdge application

cd /opt/Solaredge_ScanWriter

echo "🚀 SolarEdge Manual Run Script"
echo "============================="
echo ""

# Show Python info
echo "🐍 Python Environment:"
echo "  Python: $(which python3)"
echo "  Version: $(python3 --version)"
echo ""

# Show available options
echo "📋 Available run modes:"
echo "  1. GUI mode (default): python3 main.py"
echo "  2. API test: python3 main.py --api"
echo "  3. Web test: python3 main.py --web"
echo "  4. Realtime test: python3 main.py --realtime"
echo "  5. History mode: python3 main.py --history"
echo ""

# Ask user what to run
read -p "Enter mode number (1-5) or press Enter for GUI mode: " choice

case $choice in
    2)
        echo "🔄 Running API test..."
        python3 main.py --api
        python main.py --api
        ;;
    3)
        echo "🔄 Running Web test..."
        python main.py --web
        ;;
    4)
        python3 main.py --api
        ;;
    3)
        echo "🔄 Running Web test..."
        python3 main.py --web
        ;;
    4)
        echo "🔄 Running Realtime test..."
        python3 main.py --realtime
        ;;
    5)
        echo "🔄 Running History mode..."
        python3 main.py --history
        ;;
    *)
        echo "🔄 Running GUI mode..."
        echo "   Access GUI at: http://$(hostname -I | awk '{print $1}'):8092"
        echo "   Press Ctrl+C to stop"
        echo ""
        python3 main.py
        ;;
esac
MANUAL

        # Create bucket verification script
        tee "$APP_DIR/check-buckets.sh" > /dev/null << 'BUCKETS'
#!/bin/bash
# Script per verificare configurazione bucket InfluxDB

source .env 2>/dev/null || { echo "❌ File .env non trovato"; exit 1; }

echo "🗄️ Verifica Configurazione Bucket InfluxDB"
echo "=========================================="
echo ""
echo "📋 Configurazione:"
echo "  URL: $INFLUXDB_URL"
echo "  Org: $INFLUXDB_ORG"
echo "  Bucket principale: $INFLUXDB_BUCKET"
echo "  Bucket realtime: $INFLUXDB_BUCKET_REALTIME"
echo ""

if command -v curl &> /dev/null; then
    echo "🔍 Verifica connessione InfluxDB..."
    if curl -s "$INFLUXDB_URL/health" >/dev/null 2>&1; then
        echo "✅ InfluxDB raggiungibile"

        if command -v jq &> /dev/null; then
            echo ""
            echo "📦 Bucket esistenti:"
            BUCKETS=$(curl -s -H "Authorization: Token $INFLUXDB_TOKEN" "$INFLUXDB_URL/api/v2/buckets" 2>/dev/null)

            if echo "$BUCKETS" | jq -e '.buckets' >/dev/null 2>&1; then
                echo "$BUCKETS" | jq -r '.buckets[] | "  • \(.name) (retention: \(if .retentionRules[0].everySeconds then "\(.retentionRules[0].everySeconds)s" else "infinite" end))"' 2>/dev/null || echo "  Errore parsing bucket"
            else
                echo "  ❌ Errore recupero bucket (verifica token)"
            fi
        else
            echo "  ⚠️  jq non installato - installa per dettagli bucket"
        fi
    else
        echo "❌ InfluxDB non raggiungibile"
    fi
else
    echo "⚠️  curl non disponibile - verifica manuale necessaria"
fi

echo ""
echo "💡 I bucket vengono creati automaticamente durante l'installazione"
BUCKETS

        # Create logrotate verification script
        tee "$APP_DIR/check-logrotate.sh" > /dev/null << 'LOGROTATE'
#!/bin/bash
# Script per verificare configurazione logrotate

echo "🔄 Verifica Configurazione Log Rotation"
echo "======================================"
echo ""

# Check if logrotate config exists
if [[ -f /etc/logrotate.d/solaredge-collector ]]; then
    echo "✅ File configurazione logrotate trovato: /etc/logrotate.d/solaredge-collector"
    echo ""
    echo "📋 Configurazione attuale:"
    cat /etc/logrotate.d/solaredge-collector
    echo ""

    # Test logrotate configuration
    echo "🧪 Test configurazione logrotate..."
    if sudo logrotate -d /etc/logrotate.d/solaredge-collector 2>/dev/null; then
        echo "✅ Configurazione logrotate valida"
    else
        echo "❌ Errore nella configurazione logrotate"
    fi

    echo ""
    echo "📁 File di log attuali:"
    find /opt/Solaredge_ScanWriter/logs -name "*.log" -type f 2>/dev/null | head -10 | while read file; do
        size=$(du -h "$file" 2>/dev/null | cut -f1)
        echo "  • $(basename "$file"): $size"
    done

    echo ""
    echo "🗂️ File di log ruotati (se presenti):"
    find /opt/Solaredge_ScanWriter/logs -name "*.log.*" -type f 2>/dev/null | head -5 | while read file; do
        size=$(du -h "$file" 2>/dev/null | cut -f1)
        echo "  • $(basename "$file"): $size"
    done

else
    echo "❌ File configurazione logrotate non trovato"
    echo "   Dovrebbe essere in: /etc/logrotate.d/solaredge-collector"
fi

echo ""
echo "💡 La rotazione dei log avviene automaticamente ogni giorno via cron"
echo "💡 Per forzare una rotazione manuale: sudo logrotate -f /etc/logrotate.d/solaredge-collector"
LOGROTATE

        # Create journal management script
        tee "$APP_DIR/manage-journal.sh" > /dev/null << 'JOURNAL_SCRIPT'
#!/bin/bash
# Script per gestire i log systemd journal

echo "📰 Gestione Journal Systemd"
echo "==========================="
echo ""

case "${1:-status}" in
    "status"|"")
        echo "📊 Stato attuale del journal:"
        echo ""

        # Journal disk usage
        echo "💾 Utilizzo disco journal:"
        sudo journalctl --disk-usage 2>/dev/null || echo "  Errore recupero utilizzo disco"
        echo ""

        # Journal configuration
        echo "⚙️ Configurazione journal:"
        if [[ -f /etc/systemd/journald.conf.d/solaredge-retention.conf ]]; then
            echo "  ✅ Configurazione personalizzata attiva:"
            grep -E "^[A-Z]" /etc/systemd/journald.conf.d/solaredge-retention.conf | sed 's/^/    /'
        else
            echo "  ⚠️ Configurazione personalizzata non trovata"
        fi
        echo ""

        # Recent logs for our service
        echo "📋 Log recenti del servizio (ultime 10 righe):"
        sudo journalctl -u solaredge-scanwriter --lines=10 --no-pager 2>/dev/null || echo "  Servizio non trovato o non attivo"
        echo ""

        # Journal files info
        echo "📁 File journal attuali:"
        sudo find /var/log/journal -name "*.journal*" -type f 2>/dev/null | head -5 | while read file; do
            size=$(sudo du -h "$file" 2>/dev/null | cut -f1)
            modified=$(sudo stat -c %y "$file" 2>/dev/null | cut -d' ' -f1)
            echo "  • $(basename "$file"): $size (modificato: $modified)"
        done
        ;;

    "clean")
        echo "🧹 Pulizia journal logs..."
        echo ""

        echo "Prima della pulizia:"
        sudo journalctl --disk-usage
        echo ""

        # Clean logs older than 48 hours
        echo "Rimozione log più vecchi di 48 ore..."
        sudo journalctl --vacuum-time=48h
        echo ""

        # Limit total size to 100MB
        echo "Limitazione dimensione totale a 100MB..."
        sudo journalctl --vacuum-size=100M
        echo ""

        echo "Dopo la pulizia:"
        sudo journalctl --disk-usage
        ;;

    "logs")
        echo "📋 Log del servizio SolarEdge (ultime 50 righe):"
        echo ""
        sudo journalctl -u solaredge-scanwriter --lines=50 --no-pager
        ;;

    "follow")
        echo "📡 Monitoraggio log in tempo reale (Ctrl+C per uscire):"
        echo ""
        sudo journalctl -u solaredge-scanwriter -f
        ;;

    "help")
        echo "Utilizzo: $0 [comando]"
        echo ""
        echo "Comandi disponibili:"
        echo "  status  - Mostra stato journal e configurazione (default)"
        echo "  clean   - Pulisce log vecchi (>48h) e limita dimensione"
        echo "  logs    - Mostra log recenti del servizio"
        echo "  follow  - Monitora log in tempo reale"
        echo "  help    - Mostra questo aiuto"
        ;;

    *)
        echo "❌ Comando non riconosciuto: $1"
        echo "Usa '$0 help' per vedere i comandi disponibili"
        exit 1
        ;;
esac
JOURNAL_SCRIPT

        chmod +x "$APP_DIR"/{test.sh,status.sh,check-buckets.sh,check-logrotate.sh,manage-journal.sh}

        # Configure executable permissions for all scripts
        log "🔧 Configuring script permissions..."
        EXECUTABLE_FILES=(
            "update.sh"
            "install.sh"
            "setup-permissions.sh"
            "scripts/smart_update.py"
            "scripts/cleanup_logs.sh"
            "test.sh"
            "status.sh"
            "check-buckets.sh"
            "check-logrotate.sh"
            "manage-journal.sh"
            "main.py"
            "run-manual.sh"
            "# venv.sh removed"
        )

        for file in "${EXECUTABLE_FILES[@]}"; do
            if [[ -f "$APP_DIR/$file" ]]; then
                chmod +x "$APP_DIR/$file"
            fi
        done

        # Configure directory and file permissions for config files
        log "🔧 Configuring config directory permissions..."
        chmod -R 755 "$APP_DIR/config"
        chmod -R 664 "$APP_DIR/config"/*.yaml "$APP_DIR/config"/*/*.yaml 2>/dev/null || true

        # Ensure specific directories have correct permissions
        CONFIG_DIRS=(
            "config"
            "config/sources"
            "logs"
            "cache"
            "cookies"
            "storage"
            "backups"
        )

        for dir in "${CONFIG_DIRS[@]}"; do
            if [[ -d "$APP_DIR/$dir" ]] || mkdir -p "$APP_DIR/$dir"; then
                chmod -R 755 "$APP_DIR/$dir"
            fi
        done

        # Ensure config files are writable by the solaredge user
        CONFIG_FILES=(
            "config/main.yaml"
            "config/sources/api_endpoints.yaml"
            "config/sources/web_endpoints.yaml"
            "config/sources/modbus_endpoints.yaml"
            ".env"
        )

        for file in "${CONFIG_FILES[@]}"; do
            if [[ -f "$APP_DIR/$file" ]]; then
                chmod 664 "$APP_DIR/$file"
            fi
        done

        # Setup Git hooks for automatic permission restoration
        if [[ -d "$APP_DIR/.git" ]]; then
            log "📁 Setting up Git hooks for automatic permissions..."

            # Create Git hooks directory if not exists
            mkdir -p "$APP_DIR/.git/hooks"

            # Copy hooks from .githooks if they exist
            if [[ -d "$APP_DIR/.githooks" ]]; then
                cp "$APP_DIR/.githooks"/* "$APP_DIR/.git/hooks/" 2>/dev/null || true
                chmod +x "$APP_DIR/.git/hooks"/* 2>/dev/null || true
            fi

            # Configure Git to preserve file permissions
            if [[ $EUID -eq 0 ]]; then
                su solaredge -c "cd $APP_DIR && git config core.filemode true" 2>/dev/null || true
            else
                sudo -u solaredge bash -c "cd $APP_DIR && git config core.filemode true" 2>/dev/null || true
            fi
        fi

        # Configure firewall
        if command -v ufw &> /dev/null; then
            log "🔥 Configuring firewall..."
            ufw --force enable >/dev/null 2>&1 || true
            ufw allow 8092/tcp comment "SolarEdge GUI" >/dev/null 2>&1 || true
            ufw allow 8086/tcp comment "InfluxDB" >/dev/null 2>&1 || true
            ufw allow 3000/tcp comment "Grafana" >/dev/null 2>&1 || true
        fi

        log "✅ Installation completed successfully!"
        echo ""
        echo "╔════════════════════════════════════════════════════════════╗"
        echo "║           🎉 Installation Complete!                       ║"
        echo "╚════════════════════════════════════════════════════════════╝"
        echo ""
        echo "📋 System Information:"
        echo "  • Installation path: /opt/Solaredge_ScanWriter"
        echo "  • Service name: solaredge-scanwriter"
        echo "  • Running as: root"
        echo ""
        echo "🌐 Access URLs:"
        echo "  • SolarEdge GUI: http://$(hostname -I | awk '{print $1}'):8092"
        echo "  • InfluxDB UI:   http://$(hostname -I | awk '{print $1}'):8086"
        echo "  • Grafana:       http://$(hostname -I | awk '{print $1}'):3000"
        echo ""
        echo "🔑 Credentials:"
        echo "  • InfluxDB: $INFLUX_USERNAME / $INFLUX_PASSWORD"
        echo "  • Grafana:  $GRAFANA_USER / $GRAFANA_PASS"
        echo ""
        echo "📝 InfluxDB Token (save this!):"
        echo "  Token: $INFLUX_TOKEN"
        echo "  Already configured in .env file"
        echo ""
        echo "⚙️ Next Steps:"
        echo ""
        echo "1️⃣  Configure SolarEdge credentials:"
        echo "    nano /opt/Solaredge_ScanWriter/.env"
        echo "    # Update these values:"
        echo "    #   SOLAREDGE_API_KEY=your_api_key"
        echo "    #   SOLAREDGE_USERNAME=your_email"
        echo "    #   SOLAREDGE_PASSWORD=your_password"
        echo "    #   SOLAREDGE_SITE_ID=your_site_id"
        echo ""
        echo "2️⃣  Verify InfluxDB token (if you get 401 errors):"
        echo "    cat /opt/Solaredge_ScanWriter/.env | grep INFLUXDB_TOKEN"
        echo "    # Or get it from InfluxDB UI → Data → API Tokens"
        echo ""
        echo "3️⃣  Start the service:"
        echo "    systemctl enable --now solaredge-scanwriter"
        echo ""
        echo "4️⃣  Monitor the logs:"
        echo "    journalctl -u solaredge-scanwriter -f"
        echo ""
        echo "🛠️  Utility Scripts (in /opt/Solaredge_ScanWriter):"
        echo "  • ./test.sh           - Test installation"
        echo "  • ./status.sh         - Check service status"
        echo "  • ./run-manual.sh     - Run manually for testing"
        echo "  • ./check-buckets.sh  - Verify InfluxDB buckets"
        echo "  • ./update.sh         - Update system"
        echo ""
        echo "✨ Features Configured:"
        echo "  ✅ Dual bucket setup (Solaredge + Solaredge_Realtime)"
        echo "  ✅ 2-day retention for realtime data"
        echo "  ✅ Log rotation (7 days main, 3 days debug)"
        echo "  ✅ Journal retention (48h, 100MB limit)"
        echo "  ✅ System Python with global dependencies"
        echo "  ✅ Grafana dashboard pre-configured"
        echo ""
        echo "📚 Documentation:"
        echo "  • README: /opt/Solaredge_ScanWriter/README.md"
        echo "  • API Docs: /opt/Solaredge_ScanWriter/docs/"
        echo ""
        echo "⚠️  Important: Configure .env before starting the service!"
        echo ""

        # Create installation report file
        REPORT_FILE="/opt/Solaredge_ScanWriter/install_report.md"
        cat > "$REPORT_FILE" << REPORT_EOF
# SolarEdge Data Collector - Installation Report

**Installation Date:** $(date '+%Y-%m-%d %H:%M:%S')
**Hostname:** $(hostname)
**IP Address:** $(hostname -I | awk '{print $1}')

---

## 📋 System Information

- **Installation Path:** /opt/Solaredge_ScanWriter
- **Service Name:** solaredge-scanwriter
- **Running As:** root
- **Python Version:** $(python3 --version)

---

## 🌐 Access URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| SolarEdge GUI | http://$(hostname -I | awk '{print $1}'):8092 | - |
| InfluxDB UI | http://$(hostname -I | awk '{print $1}'):8086 | admin / solaredge123 |
| Grafana | http://$(hostname -I | awk '{print $1}'):3000 | admin / admin |

---

## 🔑 InfluxDB Configuration

**Token:** \`$INFLUX_TOKEN\`

**Organization:** fotovoltaico
**Buckets:**
- \`Solaredge\` - Main data (API/Web)
- \`Solaredge_Realtime\` - Realtime data (2-day retention)

> ⚠️ **Important:** This token is already configured in \`.env\` file.
> If you get 401 errors, verify the token with:
> \`\`\`bash
> cat /opt/Solaredge_ScanWriter/.env | grep INFLUXDB_TOKEN
> \`\`\`

---

## ⚙️ Next Steps

### 1️⃣ Configure SolarEdge Credentials

Edit the \`.env\` file:
\`\`\`bash
nano /opt/Solaredge_ScanWriter/.env
\`\`\`

Update these values:
\`\`\`bash
SOLAREDGE_API_KEY=your_api_key_here
SOLAREDGE_USERNAME=your_email@example.com
SOLAREDGE_PASSWORD=your_password_here
SOLAREDGE_SITE_ID=your_site_id_here
\`\`\`

### 2️⃣ Start the Service

\`\`\`bash
systemctl enable --now solaredge-scanwriter
\`\`\`

### 3️⃣ Monitor the Logs

\`\`\`bash
journalctl -u solaredge-scanwriter -f
\`\`\`

---

## 🛠️ Utility Scripts

All scripts are located in \`/opt/Solaredge_ScanWriter/\`:

| Script | Description |
|--------|-------------|
| \`./test.sh\` | Test installation and dependencies |
| \`./status.sh\` | Check service status and logs |
| \`./run-manual.sh\` | Run manually for testing |
| \`./check-buckets.sh\` | Verify InfluxDB buckets |
| \`./check-logrotate.sh\` | Verify log rotation |
| \`./manage-journal.sh\` | Manage systemd journal logs |
| \`./update.sh\` | Update system (preserves config) |

---

## ✨ Features Configured

- ✅ Dual bucket setup (Solaredge + Solaredge_Realtime)
- ✅ 2-day retention for realtime data
- ✅ Log rotation (7 days main, 3 days debug)
- ✅ Journal retention (48h, 100MB limit)
- ✅ System Python with global dependencies
- ✅ Grafana dashboard pre-configured

---

## 📚 Documentation

- **README:** /opt/Solaredge_ScanWriter/README.md
- **API Docs:** /opt/Solaredge_ScanWriter/docs/
- **Configuration:** /opt/Solaredge_ScanWriter/.env

---

## 🔧 Troubleshooting

### Service won't start
\`\`\`bash
# Check service status
systemctl status solaredge-scanwriter

# View logs
journalctl -u solaredge-scanwriter -n 50
\`\`\`

### InfluxDB 401 Unauthorized
\`\`\`bash
# Verify token in .env
cat .env | grep INFLUXDB_TOKEN

# Or get token from InfluxDB UI
# Go to: http://YOUR_IP:8086 → Data → API Tokens
\`\`\`

### Python dependencies issues
\`\`\`bash
# Reinstall dependencies
pip3 install -r requirements.txt
\`\`\`

---

## 📞 Support

- **GitHub:** https://github.com/frezeen/Solaredge_ScanWriter
- **Issues:** https://github.com/frezeen/Solaredge_ScanWriter/issues

---

*Report generated by install.sh on $(date)*
REPORT_EOF

        chmod 644 "$REPORT_FILE"

        echo "📄 Installation report saved to: $REPORT_FILE"
        echo ""
        echo "╔════════════════════════════════════════════════════════════╗"
        echo "║  💡 To start working, run:                                ║"
        echo "║                                                            ║"
        echo "║     cd /opt/Solaredge_ScanWriter                          ║"
        echo "║                                                            ║"
        echo "╚════════════════════════════════════════════════════════════╝"
        echo ""

    else
        error "Git clone failed or directory not created"
        exit 1
    fi
else
    error "Failed to clone repository from GitHub"
    exit 1
fi



