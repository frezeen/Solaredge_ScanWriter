#!/bin/bash
# Script per configurare permessi e Git hooks automaticamente
# Esegui una volta dopo il clone: ./setup-permissions.sh

set -e

echo "🚀 Configurazione permessi e Git hooks per SolarEdge Data Collector"

# Configura Git hooks
echo "📁 Configurazione Git hooks..."
if [[ -d ".git" ]]; then
    # Copia hooks nella directory Git
    cp .githooks/* .git/hooks/ 2>/dev/null || true
    
    # Rendi eseguibili gli hooks
    chmod +x .git/hooks/post-checkout 2>/dev/null || true
    chmod +x .git/hooks/post-merge 2>/dev/null || true
    
    echo "✅ Git hooks configurati"
else
    echo "⚠️  Directory .git non trovata - hooks non configurati"
fi

# Lista dei file che devono essere eseguibili
EXECUTABLE_FILES=(
    "update.sh"
    "install.sh"
    "setup-permissions.sh"
    "scripts/smart_update.py"
    "scripts/cleanup_logs.sh"
)

echo "🔧 Applicazione permessi di esecuzione..."

# Applica permessi di esecuzione
for file in "${EXECUTABLE_FILES[@]}"; do
    if [[ -f "$file" ]]; then
        chmod +x "$file"
        echo "✅ $file"
    else
        echo "⚠️  $file non trovato"
    fi
done

# Configura permessi directory e file di configurazione
echo "🔧 Configurazione permessi directory e file di configurazione..."

# Determina l'utente corrente o usa solaredge se esiste
if id "solaredge" &>/dev/null; then
    CONFIG_USER="solaredge"
    CONFIG_GROUP="solaredge"
elif [[ "$EUID" -ne 0 ]]; then
    CONFIG_USER="$USER"
    CONFIG_GROUP="$(id -gn)"
else
    CONFIG_USER="root"
    CONFIG_GROUP="root"
fi

# Configura permessi directory
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
    if [[ -d "$dir" ]] || mkdir -p "$dir" 2>/dev/null; then
        if [[ "$EUID" -eq 0 ]] || [[ "$CONFIG_USER" = "$USER" ]]; then
            chown -R "$CONFIG_USER:$CONFIG_GROUP" "$dir" 2>/dev/null || true
        fi
        chmod -R 755 "$dir"
        echo "✅ Directory: $dir"
    else
        echo "⚠️  Directory non trovata: $dir"
    fi
done

# Configura permessi file di configurazione
CONFIG_FILES=(
    "config/main.yaml"
    "config/sources/api_endpoints.yaml"
    "config/sources/web_endpoints.yaml"
    "config/sources/modbus_endpoints.yaml"
    ".env"
)

for file in "${CONFIG_FILES[@]}"; do
    if [[ -f "$file" ]]; then
        if [[ "$EUID" -eq 0 ]] || [[ "$CONFIG_USER" = "$USER" ]]; then
            chown "$CONFIG_USER:$CONFIG_GROUP" "$file" 2>/dev/null || true
        fi
        chmod 664 "$file"
        echo "✅ File: $file"
    else
        echo "⚠️  File non trovato: $file"
    fi
done

# Configura Git per preservare permessi (se possibile)
if command -v git &> /dev/null && [[ -d ".git" ]]; then
    echo "⚙️  Configurazione Git per preservare permessi..."
    git config core.filemode true 2>/dev/null || echo "⚠️  Impossibile configurare core.filemode"
fi

echo ""
echo "🎉 Configurazione completata!"
echo ""
echo "📋 Cosa è stato fatto:"
echo "   • Permessi di esecuzione applicati a tutti gli script"
echo "   • Git hooks configurati per ripristino automatico"
echo "   • Git configurato per preservare permessi"
echo ""
echo "💡 D'ora in poi, dopo ogni 'git pull' i permessi verranno ripristinati automaticamente!"
echo ""