#!/bin/bash
# Script per sincronizzare .env con .env.example mantenendo i valori esistenti

set -e

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo -e "${CYAN}🔄 Sincronizzazione .env con .env.example${NC}"
echo "==========================================="
echo ""

# Verifica file esistenti
if [[ ! -f ".env.example" ]]; then
    log_error "❌ File .env.example non trovato!"
    exit 1
fi

# Backup .env esistente se presente
if [[ -f ".env" ]]; then
    log_info "📋 Backup .env esistente..."
    cp .env .env.backup
    log_success "✅ Backup salvato in .env.backup"
fi

# Crea nuovo .env temporaneo
log_info "🔄 Creazione nuovo .env completo..."
temp_env=$(mktemp)

# Copia tutte le righe da .env.example
while IFS= read -r line; do
    if [[ "$line" =~ ^[A-Z_]+=.* ]]; then
        # È una variabile
        var_name=$(echo "$line" | cut -d'=' -f1)
        var_value=$(echo "$line" | cut -d'=' -f2-)
        
        # Controlla se esiste già in .env
        if [[ -f ".env" ]] && grep -q "^$var_name=" .env; then
            # Usa il valore esistente
            existing_value=$(grep "^$var_name=" .env | cut -d'=' -f2-)
            echo "$var_name=$existing_value" >> "$temp_env"
            log_info "✅ Mantenuto valore esistente per $var_name"
        else
            # Usa il valore di default da .env.example
            echo "$line" >> "$temp_env"
            log_warning "➕ Aggiunta nuova variabile: $var_name"
        fi
    else
        # È un commento o riga vuota, copia così com'è
        echo "$line" >> "$temp_env"
    fi
done < .env.example

# Sostituisci .env con la versione sincronizzata
mv "$temp_env" .env

log_success "✅ Sincronizzazione completata!"
echo ""

# Mostra statistiche
total_vars=$(grep -c "^[A-Z_]*=" .env.example)
if [[ -f ".env.backup" ]]; then
    existing_vars=$(grep -c "^[A-Z_]*=" .env.backup 2>/dev/null || echo "0")
    new_vars=$((total_vars - existing_vars))
    
    log_info "📊 Statistiche sincronizzazione:"
    echo -e "   Variabili totali: ${CYAN}$total_vars${NC}"
    echo -e "   Variabili esistenti mantenute: ${GREEN}$existing_vars${NC}"
    echo -e "   Nuove variabili aggiunte: ${YELLOW}$new_vars${NC}"
else
    log_info "📊 Nuovo file .env creato con $total_vars variabili"
fi

echo ""
log_info "🔍 Verifica configurazione obbligatoria..."

# Variabili che devono essere configurate
required_config=(
    "SOLAREDGE_SITE_ID"
    "SOLAREDGE_API_KEY"
    "SOLAREDGE_USERNAME"
    "SOLAREDGE_PASSWORD"
)

needs_config=false
for var in "${required_config[@]}"; do
    value=$(grep "^$var=" .env | cut -d'=' -f2-)
    if [[ "$value" == *"YOUR_"* ]] || [[ "$value" == *"your."* ]] || [[ "$value" == "123456" ]]; then
        log_warning "⚠️  $var deve essere configurato: $value"
        needs_config=true
    fi
done

if [[ "$needs_config" == "true" ]]; then
    echo ""
    log_warning "📝 Alcune variabili richiedono configurazione manuale"
    read -p "Vuoi aprire nano per configurarle ora? [y/N]: " open_editor
    if [[ "$open_editor" =~ ^[Yy]$ ]]; then
        nano .env
        log_success "✅ Configurazione completata"
    fi
else
    log_success "✅ Tutte le variabili obbligatorie sono configurate"
fi

echo ""
log_success "🎯 File .env sincronizzato e pronto per l'uso!"
echo ""
log_info "📋 File disponibili:"
echo -e "   ${CYAN}.env${NC} - File di configurazione aggiornato"
if [[ -f ".env.backup" ]]; then
    echo -e "   ${YELLOW}.env.backup${NC} - Backup della configurazione precedente"
fi