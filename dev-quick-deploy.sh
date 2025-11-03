#!/bin/bash
# Script rapido per deploy su Debian (senza pulizia completa)
# Uso: ./dev-quick-deploy.sh

set -e

# Colori
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }

echo -e "${CYAN}SolarEdge Quick Deploy${NC}"
echo "====================="

# Aggiornamento Git rapido
log_info "🔄 Pull ultime modifiche..."
if git pull origin $(git branch --show-current) 2>/dev/null; then
    log_success "✅ Codice aggiornato"
else
    log_info "⚠️  Continuando con codice locale"
fi

# Rebuild solo l'immagine principale
log_info "🏗️ Rebuild immagine SolarEdge..."
if ! docker build -t solaredge-scanwriter:latest .; then
    log_error "❌ Errore nel build dell'immagine"
    exit 1
fi

# Restart solo il container principale
log_info "🔄 Restart container SolarEdge..."
docker compose up -d --force-recreate solaredge

# Status rapido
log_info "📊 Status servizi:"
docker compose ps

log_success "✅ Quick deploy completato!"
echo ""
echo -e "${CYAN}GUI: http://localhost:8092${NC}"