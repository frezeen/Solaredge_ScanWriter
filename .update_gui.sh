#!/bin/bash
cd /opt/Solaredge_ScanWriter
echo "=== Update avviato da GUI ===" >> /opt/Solaredge_ScanWriter/logs/update_gui.log
date >> /opt/Solaredge_ScanWriter/logs/update_gui.log

# Usa expect per rispondere automaticamente al prompt, oppure yes come fallback
if command -v expect &> /dev/null; then
    expect << 'EOF' >> /opt/Solaredge_ScanWriter/logs/update_gui.log 2>&1
spawn ./update.sh
expect "Vuoi continuare?"
send "y\r"
expect eof
EOF
else
    # Fallback: usa yes per rispondere automaticamente
    yes y | ./update.sh >> /opt/Solaredge_ScanWriter/logs/update_gui.log 2>&1
fi

echo "=== Update completato ===" >> /opt/Solaredge_ScanWriter/logs/update_gui.log
date >> /opt/Solaredge_ScanWriter/logs/update_gui.log
