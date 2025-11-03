#!/bin/bash
# Script per verificare la configurazione .env

set -e

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo -e "${BLUE}🔍 Verifica Configurazione .env${NC}"
echo "================================"
echo ""

# Verifica esistenza file .env
if [[ ! -f ".env" ]]; then
    log_error "❌ File .env non trovato!"
    log_info "Copia .env.example in .env e configuralo"
    exit 1
fi

# Carica variabili .env
source .env

# Variabili obbligatorie
required_vars=(
    "SOLAREDGE_SITE_ID"
    "SOLAREDGE_API_KEY" 
    "SOLAREDGE_USERNAME"
    "SOLAREDGE_PASSWORD"
)

# Variabili con valori di default da cambiare
default_values=(
    "YOUR_API_KEY_HERE"
    "your.email@example.com"
    "YOUR_PASSWORD_HERE"
    "123456"
)

errors=0

log_info "Controllo variabili obbligatorie..."

for var in "${required_vars[@]}"; do
    if [[ -z "${!var}" ]]; then
        log_error "❌ Variabile $var non impostata"
        ((errors++))
    elif [[ "${!var}" == *"YOUR_"* ]] || [[ "${!var}" == *"your."* ]] || [[ "${!var}" == "123456" ]]; then
        log_error "❌ Variabile $var contiene ancora il valore di esempio: ${!var}"
        ((errors++))
    else
        log_success "✅ $var configurata"
    fi
done

echo ""
log_info "Controllo configurazione Docker..."

# Verifica configurazione Docker
if [[ "$INFLUXDB_URL" == *"localhost"* ]]; then
    log_warning "⚠️  INFLUXDB_URL usa localhost, per Docker dovrebbe essere: http://influxdb:8086"
fi

if [[ "$GUI_HOST" == "127.0.0.1" ]]; then
    log_warning "⚠️  GUI_HOST è 127.0.0.1, per Docker dovrebbe essere: 0.0.0.0"
fi

if [[ "$DOCKER_MODE" != "true" ]]; then
    log_warning "⚠️  DOCKER_MODE non impostato su true"
fi

echo ""

if [[ $errors -eq 0 ]]; then
    log_success "🎉 Configurazione .env corretta!"
    echo ""
    log_info "📋 Riepilogo configurazione:"
    echo -e "   ${BLUE}Site ID:${NC} $SOLAREDGE_SITE_ID"
    echo -e "   ${BLUE}Username:${NC} $SOLAREDGE_USERNAME"
    echo -e "   ${BLUE}API Key:${NC} ${SOLAREDGE_API_KEY:0:10}..."
    echo -e "   ${BLUE}InfluxDB:${NC} $INFLUXDB_URL"
    echo -e "   ${BLUE}GUI:${NC} http://$GUI_HOST:$GUI_PORT"
    echo ""
    log_success "✅ Pronto per il deploy Docker!"
else
    log_error "❌ Trovati $errors errori nella configurazione"
    echo ""
    log_info "📝 Per correggere:"
    echo -e "   ${YELLOW}nano .env${NC}"
    echo ""
    log_info "📋 Variabili da configurare:"
    echo -e "   ${BLUE}SOLAREDGE_SITE_ID${NC}=il_tuo_site_id"
    echo -e "   ${BLUE}SOLAREDGE_API_KEY${NC}=la_tua_api_key"
    echo -e "   ${BLUE}SOLAREDGE_USERNAME${NC}=la_tua_email"
    echo -e "   ${BLUE}SOLAREDGE_PASSWORD${NC}=la_tua_password"
    exit 1
fi