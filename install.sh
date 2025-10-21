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

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    warn "Running as root - this is acceptable in containers but not recommended on host systems."
    SUDO_CMD=""
else
    SUDO_CMD="sudo"
fi

# Check if running on Debian/Ubuntu
if ! grep -qE "(Debian|Ubuntu)" /etc/os-release; then
    warn "This script is designed for Debian/Ubuntu. Proceeding anyway..."
fi

log "🚀 Starting SolarEdge Data Collector installation..."

# Install basic dependencies
log "📦 Installing basic dependencies..."
${SUDO_CMD} apt-get update -qq

# Install packages in groups to handle potential failures
log "Installing core packages..."
${SUDO_CMD} apt-get install -y -qq curl wget git unzip

log "Installing Python packages..."
${SUDO_CMD} apt-get install -y -qq python3 python3-pip python3-venv python3-dev

log "Installing build tools..."
${SUDO_CMD} apt-get install -y -qq build-essential

log "Installing system utilities..."
${SUDO_CMD} apt-get install -y -qq nano htop systemd cron

log "Installing repository tools..."
${SUDO_CMD} apt-get install -y -qq apt-transport-https gnupg ca-certificates

# Download and extract project
TEMP_DIR="/tmp/solaredge-installer"
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"
cd "$TEMP_DIR"

log "📥 Downloading project from GitHub..."
if curl -sSL "https://github.com/frezeen/Solaredge_ScanWriter/archive/main.zip" -o project.zip; then
    log "📂 Extracting project files..."
    unzip -q project.zip
    
    # Find the extracted directory
    PROJECT_DIR=$(find . -name "*Solaredge_ScanWriter*" -type d | head -1)
    if [[ -n "$PROJECT_DIR" ]]; then
        log "🔧 Starting installation process..."
        
        # Create application directory
        APP_DIR="/opt/Solaredge_ScanWriter"
        log "📁 Creating application directory: $APP_DIR"
        ${SUDO_CMD} mkdir -p "$APP_DIR"
        
        # Copy project files
        log "📋 Copying project files..."
        ${SUDO_CMD} cp -r "$PROJECT_DIR"/* "$APP_DIR/"
        
        # Create application user
        log "👤 Creating application user..."
        if ! id "solaredge" &>/dev/null; then
            ${SUDO_CMD} useradd --create-home --shell /bin/bash --groups sudo solaredge
        fi
        ${SUDO_CMD} chown -R solaredge:solaredge "$APP_DIR"
        
        # Create Python virtual environment
        log "🐍 Setting up Python environment..."
        if [[ $EUID -eq 0 ]]; then
            su solaredge -c "python3 -m venv $APP_DIR/venv" >/dev/null 2>&1
        else
            sudo -u solaredge python3 -m venv "$APP_DIR/venv" >/dev/null 2>&1
        fi
        
        # Install Python dependencies
        log "📦 Installing Python dependencies..."
        if [[ $EUID -eq 0 ]]; then
            su solaredge -c "$APP_DIR/venv/bin/pip install --upgrade pip" >/dev/null 2>&1
        else
            sudo -u solaredge "$APP_DIR/venv/bin/pip" install --upgrade pip >/dev/null 2>&1
        fi
        
        # Create requirements.txt if not exists
        if [[ ! -f "$APP_DIR/requirements.txt" ]]; then
            log "📝 Creating requirements.txt..."
            ${SUDO_CMD} tee "$APP_DIR/requirements.txt" > /dev/null << 'REQS'
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
            ${SUDO_CMD} chown solaredge:solaredge "$APP_DIR/requirements.txt"
        fi
        
        # Install Python dependencies with proper versions
        if [[ $EUID -eq 0 ]]; then
            su solaredge -c "$APP_DIR/venv/bin/pip install -r $APP_DIR/requirements.txt" >/dev/null 2>&1
        else
            sudo -u solaredge "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt" >/dev/null 2>&1
        fi
        
        # Create directories
        log "📁 Creating directories..."
        if [[ $EUID -eq 0 ]]; then
            su solaredge -c "mkdir -p $APP_DIR/{logs,cache,cookies,config,systemd,scripts,grafana}" >/dev/null 2>&1
        else
            sudo -u solaredge mkdir -p "$APP_DIR"/{logs,cache,cookies,config,systemd,scripts,grafana} >/dev/null 2>&1
        fi
        
        # Install InfluxDB
        log "🗄️ Installing InfluxDB..."
        curl -s https://repos.influxdata.com/influxdata-archive_compat.key | ${SUDO_CMD} gpg --dearmor -o /usr/share/keyrings/influxdata-archive-keyring.gpg 2>/dev/null
        echo "deb [signed-by=/usr/share/keyrings/influxdata-archive-keyring.gpg] https://repos.influxdata.com/debian stable main" | ${SUDO_CMD} tee /etc/apt/sources.list.d/influxdb.list >/dev/null
        
        ${SUDO_CMD} apt-get update -qq
        if ! ${SUDO_CMD} apt-get install -y -qq influxdb2; then
            warn "Failed to install InfluxDB from repository, trying direct download..."
            INFLUX_VERSION="2.7.4"
            ARCH=$(dpkg --print-architecture)
            curl -LO "https://dl.influxdata.com/influxdb/releases/influxdb2_${INFLUX_VERSION}-1_${ARCH}.deb" >/dev/null 2>&1
            ${SUDO_CMD} dpkg -i "influxdb2_${INFLUX_VERSION}-1_${ARCH}.deb" >/dev/null 2>&1 || ${SUDO_CMD} apt-get install -f -y -qq
            rm -f "influxdb2_${INFLUX_VERSION}-1_${ARCH}.deb"
        fi
        
        ${SUDO_CMD} systemctl enable influxdb >/dev/null 2>&1
        ${SUDO_CMD} systemctl start influxdb >/dev/null 2>&1
        sleep 10
        
        # Configure InfluxDB
        log "⚙️ Configuring InfluxDB..."
        INFLUX_USERNAME="admin"
        INFLUX_PASSWORD="solaredge123"
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
        ${SUDO_CMD} apt-get install -y -qq jq
        
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
        curl -s https://packages.grafana.com/gpg.key | ${SUDO_CMD} gpg --dearmor -o /usr/share/keyrings/grafana-archive-keyring.gpg 2>/dev/null
        echo "deb [signed-by=/usr/share/keyrings/grafana-archive-keyring.gpg] https://packages.grafana.com/oss/deb stable main" | ${SUDO_CMD} tee /etc/apt/sources.list.d/grafana.list >/dev/null
        
        ${SUDO_CMD} apt-get update -qq
        if ! ${SUDO_CMD} apt-get install -y -qq grafana; then
            warn "Failed to install Grafana from repository, trying direct download..."
            GRAFANA_VERSION="10.2.3"
            ARCH=$(dpkg --print-architecture)
            curl -LO "https://dl.grafana.com/oss/release/grafana_${GRAFANA_VERSION}_${ARCH}.deb" >/dev/null 2>&1
            ${SUDO_CMD} dpkg -i "grafana_${GRAFANA_VERSION}_${ARCH}.deb" >/dev/null 2>&1 || ${SUDO_CMD} apt-get install -f -y -qq
            rm -f "grafana_${GRAFANA_VERSION}_${ARCH}.deb"
        fi
        
        # Install Grafana plugins
        log "🔌 Installing Grafana plugins..."
        ${SUDO_CMD} grafana-cli plugins install fetzerch-sunandmoon-datasource >/dev/null 2>&1 || warn "Failed to install sun-and-moon plugin"
        ${SUDO_CMD} grafana-cli plugins install grafana-clock-panel >/dev/null 2>&1 || warn "Failed to install clock plugin"
        
        ${SUDO_CMD} systemctl enable grafana-server >/dev/null 2>&1
        ${SUDO_CMD} systemctl start grafana-server >/dev/null 2>&1
        
        # Wait for Grafana to be ready
        log "Waiting for Grafana to be ready..."
        for i in {1..30}; do
            if curl -s http://localhost:3000/api/health >/dev/null 2>&1; then
                break
            fi
            if [[ $i -eq 30 ]]; then
                warn "Grafana may not be ready, continuing anyway..."
            fi
            sleep 2
        done
        
        # Configure Grafana data source
        log "⚙️ Configuring Grafana data source..."
        GRAFANA_USER="admin"
        GRAFANA_PASS="admin"
        
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
            warn "Could not configure Grafana InfluxDB data source automatically. You can configure it manually in Grafana UI."
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
        if [[ -f "$APP_DIR/grafana/dashboard-solaredge.json" ]]; then
            log "📊 Importing Grafana dashboard..."
            
            # Get data source UIDs
            DATASOURCES_LIST=$(curl -s http://localhost:3000/api/datasources -u "$GRAFANA_USER:$GRAFANA_PASS" 2>/dev/null)
            INFLUX_UID=$(echo "$DATASOURCES_LIST" | jq -r '.[] | select(.name=="Solaredge") | .uid' 2>/dev/null)
            SUNMOON_UID=$(echo "$DATASOURCES_LIST" | jq -r '.[] | select(.name=="Sun and Moon") | .uid' 2>/dev/null)
            
            if [[ -n "$INFLUX_UID" && "$INFLUX_UID" != "null" ]]; then
                log "Found Solaredge data source UID: $INFLUX_UID"
                
                # Create temporary dashboard file with updated UIDs
                TEMP_DASHBOARD="/tmp/dashboard-solaredge-temp.json"
                cp "$APP_DIR/grafana/dashboard-solaredge.json" "$TEMP_DASHBOARD"
                
                # Replace data source UIDs in the dashboard JSON
                # This replaces any existing UID with the new ones
                sed -i "s/\"uid\": \"[^\"]*\",.*\"type\": \"influxdb\"/\"uid\": \"$INFLUX_UID\", \"type\": \"influxdb\"/g" "$TEMP_DASHBOARD" 2>/dev/null || \
                    sed "s/\"uid\": \"[^\"]*\",.*\"type\": \"influxdb\"/\"uid\": \"$INFLUX_UID\", \"type\": \"influxdb\"/g" "$TEMP_DASHBOARD" > "${TEMP_DASHBOARD}.new" && mv "${TEMP_DASHBOARD}.new" "$TEMP_DASHBOARD"
                
                if [[ -n "$SUNMOON_UID" && "$SUNMOON_UID" != "null" ]]; then
                    log "Found Sun and Moon data source UID: $SUNMOON_UID"
                    sed -i "s/\"uid\": \"[^\"]*\",.*\"type\": \"fetzerch-sunandmoon-datasource\"/\"uid\": \"$SUNMOON_UID\", \"type\": \"fetzerch-sunandmoon-datasource\"/g" "$TEMP_DASHBOARD" 2>/dev/null || \
                        sed "s/\"uid\": \"[^\"]*\",.*\"type\": \"fetzerch-sunandmoon-datasource\"/\"uid\": \"$SUNMOON_UID\", \"type\": \"fetzerch-sunandmoon-datasource\"/g" "$TEMP_DASHBOARD" > "${TEMP_DASHBOARD}.new" && mv "${TEMP_DASHBOARD}.new" "$TEMP_DASHBOARD"
                fi
                
                # Import dashboard via API
                DASHBOARD_JSON=$(cat "$TEMP_DASHBOARD")
                IMPORT_RESPONSE=$(curl -s -X POST http://localhost:3000/api/dashboards/db \
                    -u "$GRAFANA_USER:$GRAFANA_PASS" \
                    -H "Content-Type: application/json" \
                    -d "{
                        \"dashboard\": $DASHBOARD_JSON,
                        \"overwrite\": true,
                        \"message\": \"Imported by installation script\"
                    }" 2>/dev/null)
                
                if echo "$IMPORT_RESPONSE" | grep -q '"status":"success"'; then
                    DASHBOARD_URL=$(echo "$IMPORT_RESPONSE" | jq -r '.url' 2>/dev/null)
                    log "✅ Grafana dashboard imported successfully"
                    if [[ -n "$DASHBOARD_URL" && "$DASHBOARD_URL" != "null" ]]; then
                        log "Dashboard URL: http://$(hostname -I | awk '{print $1}'):3000$DASHBOARD_URL"
                    fi
                else
                    warn "Could not import Grafana dashboard automatically. You can import it manually from grafana/dashboard-solaredge.json"
                fi
                
                rm -f "$TEMP_DASHBOARD"
            else
                warn "Could not retrieve data source UIDs. Dashboard import skipped."
            fi
        else
            warn "Dashboard file not found at $APP_DIR/grafana/dashboard-solaredge.json"
        fi
        
        # Create .env file
        log "📝 Creating configuration file..."
        if [[ ! -f "$APP_DIR/.env" ]]; then
            ${SUDO_CMD} tee "$APP_DIR/.env" > /dev/null << ENV
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
            ${SUDO_CMD} chown solaredge:solaredge "$APP_DIR/.env"
        fi
        
        # Create systemd service
        log "🔧 Creating systemd service..."
        ${SUDO_CMD} tee /etc/systemd/system/solaredge-scanwriter.service > /dev/null << 'SERVICE'
[Unit]
Description=Solaredge_ScanWriter (GUI + Loop 24/7)
After=network.target
Wants=network.target

[Service]
Type=simple
User=solaredge
Group=solaredge
WorkingDirectory=/opt/Solaredge_ScanWriter
Environment=PATH=/opt/Solaredge_ScanWriter/venv/bin
ExecStart=/opt/Solaredge_ScanWriter/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=solaredge-scanwriter

[Install]
WantedBy=multi-user.target
SERVICE
        
        ${SUDO_CMD} systemctl daemon-reload >/dev/null 2>&1
        
        # Create helper scripts
        log "📝 Creating helper scripts..."
        ${SUDO_CMD} tee "$APP_DIR/test.sh" > /dev/null << 'TEST'
#!/bin/bash
cd /opt/Solaredge_ScanWriter
echo "=== SolarEdge Installation Test ==="
echo "Python version: $(./venv/bin/python --version)"
echo ""
echo "Installed packages:"
./venv/bin/pip list | grep -E "(aiohttp|influxdb|yaml|pymodbus|requests)"
echo ""
echo "Services status:"
echo "InfluxDB: $(systemctl is-active influxdb)"
echo "Grafana: $(systemctl is-active grafana-server)"
echo ""
echo "Directories:"
ls -la /opt/Solaredge_ScanWriter/ | head -10
echo ""
echo "Configuration file:"
if [[ -f .env ]]; then
    echo "✅ .env file exists"
    grep -E "^[A-Z]" .env | head -5
else
    echo "❌ .env file missing"
fi
TEST
        
        ${SUDO_CMD} tee "$APP_DIR/status.sh" > /dev/null << 'STATUS'
#!/bin/bash
echo "=== Solaredge_ScanWriter Status ==="
systemctl status solaredge-scanwriter
echo ""
echo "=== Recent Logs ==="
journalctl -u solaredge-scanwriter --lines=10 --no-pager
STATUS

        # Create bucket verification script
        ${SUDO_CMD} tee "$APP_DIR/check-buckets.sh" > /dev/null << 'BUCKETS'
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
        
        ${SUDO_CMD} chmod +x "$APP_DIR"/{test.sh,status.sh}
        ${SUDO_CMD} chown solaredge:solaredge "$APP_DIR"/{test.sh,status.sh}
        
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
        )
        
        for file in "${EXECUTABLE_FILES[@]}"; do
            if [[ -f "$APP_DIR/$file" ]]; then
                ${SUDO_CMD} chmod +x "$APP_DIR/$file"
                ${SUDO_CMD} chown solaredge:solaredge "$APP_DIR/$file"
            fi
        done
        
        # Configure directory and file permissions for config files
        log "🔧 Configuring config directory permissions..."
        ${SUDO_CMD} chown -R solaredge:solaredge "$APP_DIR/config"
        ${SUDO_CMD} chmod -R 755 "$APP_DIR/config"
        ${SUDO_CMD} chmod -R 664 "$APP_DIR/config"/*.yaml "$APP_DIR/config"/*/*.yaml 2>/dev/null || true
        
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
            if [[ -d "$APP_DIR/$dir" ]] || ${SUDO_CMD} mkdir -p "$APP_DIR/$dir"; then
                ${SUDO_CMD} chown -R solaredge:solaredge "$APP_DIR/$dir"
                ${SUDO_CMD} chmod -R 755 "$APP_DIR/$dir"
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
                ${SUDO_CMD} chown solaredge:solaredge "$APP_DIR/$file"
                ${SUDO_CMD} chmod 664 "$APP_DIR/$file"
            fi
        done
        
        # Setup Git hooks for automatic permission restoration
        if [[ -d "$APP_DIR/.git" ]]; then
            log "📁 Setting up Git hooks for automatic permissions..."
            
            # Create Git hooks directory if not exists
            ${SUDO_CMD} mkdir -p "$APP_DIR/.git/hooks"
            
            # Copy hooks from .githooks if they exist
            if [[ -d "$APP_DIR/.githooks" ]]; then
                ${SUDO_CMD} cp "$APP_DIR/.githooks"/* "$APP_DIR/.git/hooks/" 2>/dev/null || true
                ${SUDO_CMD} chmod +x "$APP_DIR/.git/hooks"/* 2>/dev/null || true
                ${SUDO_CMD} chown -R solaredge:solaredge "$APP_DIR/.git/hooks" 2>/dev/null || true
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
            ${SUDO_CMD} ufw --force enable >/dev/null 2>&1 || true
            ${SUDO_CMD} ufw allow 8092/tcp comment "SolarEdge GUI" >/dev/null 2>&1 || true
            ${SUDO_CMD} ufw allow 8086/tcp comment "InfluxDB" >/dev/null 2>&1 || true
            ${SUDO_CMD} ufw allow 3000/tcp comment "Grafana" >/dev/null 2>&1 || true
        fi
        
        # Cleanup
        cd /
        rm -rf "$TEMP_DIR"
        
        log "✅ Installation completed successfully!"
        echo ""
        echo "=== Installation Complete ==="
        echo ""
        echo "Next Steps:"
        echo "1. Configure your SolarEdge credentials:"
        echo "   nano /opt/Solaredge_ScanWriter/.env"
        echo ""
        echo "2. Test the installation:"
        echo "   /opt/Solaredge_ScanWriter/test.sh"
        echo ""
        echo "3. Start the service:"
        echo "   systemctl enable --now solaredge-scanwriter"
        echo ""
        echo "📋 Features Configured:"
        echo "• ✅ Dual bucket setup (API/Web + Realtime with 2-day retention)"
        echo "• ✅ Smart update system (configurations auto-preserved)"
        echo "• ✅ Automatic permission management"
        echo ""
        echo "Access URLs:"
        echo "• SolarEdge GUI: http://$(hostname -I | awk '{print $1}'):8092"
        echo "• InfluxDB: http://$(hostname -I | awk '{print $1}'):8086 (admin/solaredge123)"
        echo "• Grafana: http://$(hostname -I | awk '{print $1}'):3000 (admin/admin)"
        echo ""
        echo "🛠️ Utility Scripts Available:"
        echo "• ./test.sh - Test installation and dependencies"
        echo "• ./status.sh - Check service status and logs"
        echo "• ./check-buckets.sh - Verify InfluxDB bucket configuration"
        echo "• ./update.sh - Update system (configurations auto-preserved)"
        echo ""
        echo "Don't forget to configure your .env file with SolarEdge credentials!"
        
    else
        error "Could not find extracted project directory"
        exit 1
    fi
else
    error "Failed to download project from GitHub"
    exit 1
fi