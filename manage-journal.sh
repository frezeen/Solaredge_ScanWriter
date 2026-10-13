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
