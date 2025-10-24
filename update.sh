#!/bin/bash
# SolarEdge Data Collector - Smart Update System
# Sistema di aggiornamento robusto che preserva configurazioni e permessi

echo "🚀 SolarEdge Data Collector - Smart Update"
echo "=========================================="

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Verifica se l'utente ha permessi per controllare il servizio
if [[ "$(whoami)" == "solaredge" ]]; then
    if ! systemctl stop solaredge-collector 2>/dev/null; then
        echo -e "${YELLOW}⚠️  Nota: Per controllare il servizio senza sudo, installa la regola polkit:${NC}"
        echo -e "${BLUE}   sudo cp systemd/solaredge-user-service.conf /etc/polkit-1/rules.d/10-solaredge-service.rules${NC}"
        echo -e "${BLUE}   sudo systemctl restart polkit${NC}"
        echo ""
    fi
fi

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Verifica directory
if [ ! -f "main.py" ]; then
    log_error "main.py non trovato. Esegui lo script dalla directory del progetto."
    exit 1
fi

# Verifica Python
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 non trovato. Installa Python 3 per continuare."
    exit 1
fi

# Rendi eseguibile lo script smart update se necessario (ignora errori di permessi)
if [ -f "scripts/smart_update.py" ]; then
    chmod +x scripts/smart_update.py 2>/dev/null || true
fi

# Abilita exit on error dopo i check iniziali
set -e

# Controlla se ci sono aggiornamenti disponibili
log_info "Controllo aggiornamenti disponibili..."
if python3 scripts/smart_update.py --check-only; then
    log_info "Aggiornamenti disponibili, procedendo..."
else
    log_success "Nessun aggiornamento disponibile"
    exit 0
fi

# Chiedi conferma all'utente
echo ""
log_warning "Questo aggiornerà il sistema preservando le configurazioni locali."
read -p "Vuoi continuare? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Aggiornamento annullato dall'utente"
    exit 0
fi

# Esegui aggiornamento intelligente
log_info "Avvio aggiornamento..."
echo ""

if python3 scripts/smart_update.py; then
    echo ""
    log_success "🎉 Aggiornamento completato con successo!"
    echo ""
else
    echo ""
    log_error "❌ Aggiornamento fallito!"
    echo ""
    log_warning "🔧 Controlla i log e risolvi manualmente eventuali problemi"
    echo ""
    exit 1
fi

echo "=========================================="