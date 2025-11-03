#!/bin/bash
set -e

# SolarEdge ScanWriter Docker Entrypoint
# Gestisce l'inizializzazione cross-platform del container

echo "🐳 Avvio SolarEdge ScanWriter Docker Container"
echo "📋 Platform: $(uname -m) - $(uname -s)"
echo "🐍 Python: $(python --version)"

# Funzione per attendere servizi dipendenti
wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    local max_attempts=30
    local attempt=1
    
    echo "⏳ Attendendo $service_name su $host:$port..."
    
    while ! nc -z "$host" "$port" 2>/dev/null; do
        if [ $attempt -eq $max_attempts ]; then
            echo "❌ Timeout: $service_name non disponibile dopo $max_attempts tentativi"
            exit 1
        fi
        
        echo "   Tentativo $attempt/$max_attempts..."
        sleep 2
        ((attempt++))
    done
    
    echo "✅ $service_name disponibile!"
}

# Verifica configurazione essenziale
check_configuration() {
    echo "🔍 Verifica configurazione..."
    
    # Verifica variabili d'ambiente essenziali
    required_vars=("SOLAREDGE_SITE_ID" "SOLAREDGE_API_KEY")
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            echo "❌ Variabile d'ambiente mancante: $var"
            echo "💡 Configura il file .env con le credenziali SolarEdge"
            exit 1
        fi
    done
    
    # Verifica file di configurazione
    if [ ! -f "/app/config/main.yaml" ]; then
        echo "❌ File di configurazione mancante: config/main.yaml"
        exit 1
    fi
    
    echo "✅ Configurazione verificata"
}

# Inizializzazione database (se in modalità Docker)
init_database() {
    if [ "$DOCKER_MODE" = "true" ] && [ -n "$INFLUXDB_URL" ]; then
        echo "🗄️ Inizializzazione database InfluxDB..."
        
        # Attendi InfluxDB
        influx_host=$(echo "$INFLUXDB_URL" | sed 's|http://||' | cut -d':' -f1)
        influx_port=$(echo "$INFLUXDB_URL" | sed 's|http://||' | cut -d':' -f2 | cut -d'/' -f1)
        
        wait_for_service "$influx_host" "$influx_port" "InfluxDB"
        
        # Verifica connessione InfluxDB
        python -c "
from storage.writer_influx import InfluxWriter
try:
    with InfluxWriter() as writer:
        print('✅ Connessione InfluxDB verificata')
except Exception as e:
    print(f'❌ Errore connessione InfluxDB: {e}')
    exit(1)
"
    fi
}

# Gestione permessi e directory
setup_permissions() {
    echo "🔐 Configurazione permessi..."
    
    # Assicurati che le directory esistano e abbiano i permessi corretti
    directories=("/app/logs" "/app/cache" "/app/cookies" "/app/config/sources" "/app/data")
    
    for dir in "${directories[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
        fi
        chmod 755 "$dir"
    done
    
    echo "✅ Permessi configurati"
}

# Gestione segnali per shutdown graceful
cleanup() {
    echo "🛑 Ricevuto segnale di terminazione..."
    
    # Termina processi Python gracefully
    if [ -n "$MAIN_PID" ]; then
        kill -TERM "$MAIN_PID" 2>/dev/null || true
        wait "$MAIN_PID" 2>/dev/null || true
    fi
    
    echo "✅ Shutdown completato"
    exit 0
}

# Registra handler per segnali
trap cleanup SIGTERM SIGINT

# Esecuzione principale
main() {
    echo "🚀 Inizializzazione container..."
    
    # Setup base
    setup_permissions
    check_configuration
    
    # Inizializzazione servizi dipendenti
    if [ "$DOCKER_MODE" = "true" ]; then
        init_database
    fi
    
    echo "✅ Inizializzazione completata"
    echo "🎯 Avvio applicazione: $*"
    echo "📊 GUI disponibile su: http://localhost:8092"
    
    # Avvia l'applicazione principale
    exec "$@" &
    MAIN_PID=$!
    
    # Attendi il processo principale
    wait "$MAIN_PID"
}

# Esegui funzione principale con tutti gli argomenti
main "$@"