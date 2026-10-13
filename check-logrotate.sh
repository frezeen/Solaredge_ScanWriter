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
