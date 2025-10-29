#!/bin/bash
# Script per fixare i formati date di Grafana

echo "🔧 Fix formati date Grafana"
echo "=========================="
echo ""

# Verifica root
if [[ $EUID -ne 0 ]]; then
    echo "❌ Questo script deve essere eseguito come root"
    echo "Usa: sudo bash fix_grafana_dates.sh"
    exit 1
fi

GRAFANA_INI="/etc/grafana/grafana.ini"

if [[ ! -f "$GRAFANA_INI" ]]; then
    echo "❌ File $GRAFANA_INI non trovato"
    exit 1
fi

echo "📝 Backup del file originale..."
cp "$GRAFANA_INI" "${GRAFANA_INI}.backup.$(date +%Y%m%d_%H%M%S)"

# Rimuovi sezione date_formats esistente se presente
if grep -q "\[date_formats\]" "$GRAFANA_INI"; then
    echo "🗑️  Rimozione configurazione esistente..."
    # Rimuovi dalla riga [date_formats] fino alla prossima sezione o fine file
    sed -i '/^\[date_formats\]/,/^\[/{ /^\[date_formats\]/d; /^\[/!d; }' "$GRAFANA_INI"
fi

echo "✏️  Aggiunta nuova configurazione..."
cat >> "$GRAFANA_INI" << 'DATEFORMATS'

[date_formats]
# For information on what formatting patterns that are supported https://momentjs.com/docs/#/displaying/
# Default system date format used in time range picker and other places where full time is displayed
full_date = DD/MM/YYYY HH:mm:ss
# Used by graph and other places where we only show small intervals
interval_second = HH:mm:ss
interval_minute = HH:mm
interval_hour = HH:mm
interval_day = DD/MM/YYYY
interval_month = MMMM YYYY
interval_year = YYYY
DATEFORMATS

echo "🔄 Riavvio Grafana..."
systemctl restart grafana-server

echo ""
echo "✅ Configurazione completata!"
echo ""
echo "📌 Note:"
echo "  - Formato date: DD/MM/YYYY (italiano)"
echo "  - Backup salvato in: ${GRAFANA_INI}.backup.*"
echo "  - Ricarica la pagina di Grafana per vedere le modifiche"
echo ""
