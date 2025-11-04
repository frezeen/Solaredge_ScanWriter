#!/bin/bash
set -e

# SolarEdge Multi-Platform Docker Entrypoint
echo "🐳 Starting SolarEdge Data Collector"
echo "📋 Platform: $(uname -m) - $(uname -s)"
echo "🐍 Python: $(python --version)"

# Wait for dependent services
wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    local max_attempts=30
    local attempt=1
    
    echo "⏳ Waiting for $service_name on $host:$port..."
    
    while ! nc -z "$host" "$port" 2>/dev/null; do
        if [ $attempt -eq $max_attempts ]; then
            echo "❌ Timeout: $service_name not available after $max_attempts attempts"
            exit 1
        fi
        
        echo "   Attempt $attempt/$max_attempts..."
        sleep 2
        ((attempt++))
    done
    
    echo "✅ $service_name is available!"
}

# Check essential configuration
check_configuration() {
    echo "🔍 Checking configuration..."
    
    # Check required environment variables
    required_vars=("SOLAREDGE_SITE_ID" "SOLAREDGE_API_KEY")
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            echo "❌ Missing environment variable: $var"
            echo "💡 Configure .env file with SolarEdge credentials"
            exit 1
        fi
    done
    
    # Check configuration file
    if [ ! -f "/app/config/main.yaml" ]; then
        echo "❌ Missing configuration file: config/main.yaml"
        exit 1
    fi
    
    echo "✅ Configuration verified"
}

# Initialize database connection
init_database() {
    if [ "$DOCKER_MODE" = "true" ] && [ -n "$INFLUXDB_URL" ]; then
        echo "🗄️ Initializing InfluxDB connection..."
        
        # Wait for InfluxDB
        influx_host=$(echo "$INFLUXDB_URL" | sed 's|http://||' | cut -d':' -f1)
        influx_port=$(echo "$INFLUXDB_URL" | sed 's|http://||' | cut -d':' -f2 | cut -d'/' -f1)
        
        wait_for_service "$influx_host" "$influx_port" "InfluxDB"
        
        # Test InfluxDB connection
        python -c "
from storage.writer_influx import InfluxWriter
try:
    with InfluxWriter() as writer:
        print('✅ InfluxDB connection verified')
except Exception as e:
    print(f'❌ InfluxDB connection error: {e}')
    exit(1)
" || exit 1
    fi
}

# Setup permissions and directories
setup_permissions() {
    echo "🔐 Setting up permissions..."
    
    # Ensure directories exist with correct permissions
    directories=("/app/logs" "/app/cache" "/app/cookies" "/app/config/sources" "/app/data")
    
    for dir in "${directories[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
        fi
        chmod 755 "$dir"
    done
    
    echo "✅ Permissions configured"
}

# Graceful shutdown handler
cleanup() {
    echo "🛑 Received termination signal..."
    
    # Terminate Python processes gracefully
    if [ -n "$MAIN_PID" ]; then
        kill -TERM "$MAIN_PID" 2>/dev/null || true
        wait "$MAIN_PID" 2>/dev/null || true
    fi
    
    echo "✅ Shutdown completed"
    exit 0
}

# Register signal handlers
trap cleanup SIGTERM SIGINT

# Main execution
main() {
    echo "🚀 Initializing container..."
    
    # Base setup
    setup_permissions
    check_configuration
    
    # Initialize dependent services
    if [ "$DOCKER_MODE" = "true" ]; then
        init_database
    fi
    
    echo "✅ Initialization completed"
    echo "🔍 Generating web endpoints configuration..."
    
    # Generate web endpoints if not exists or if forced
    if [[ ! -f "/app/config/sources/web_endpoints.yaml" ]] || [[ "$FORCE_SCAN" == "true" ]]; then
        echo "📡 Running scan to generate web endpoints..."
        python main.py --scan || echo "⚠️ Scan failed, continuing with existing config"
    else
        echo "✅ Web endpoints configuration already exists"
    fi
    
    echo "🎯 Starting application: $*"
    echo "📊 GUI available at: http://localhost:8092"
    
    # Start main application
    exec "$@" &
    MAIN_PID=$!
    
    # Wait for main process
    wait "$MAIN_PID"
}

# Execute main function with all arguments
main "$@"