#!/bin/bash
# Quick CPU check per identificare il problema

echo "🔍 QUICK CPU CHECK"
echo "=================="
echo ""

# Trova il PID di Python
PID=$(pgrep -f "python.*main.py" | head -1)

if [ -z "$PID" ]; then
    echo "❌ Processo Python non trovato"
    exit 1
fi

echo "✅ Processo trovato: PID $PID"
echo ""

# CPU usage
echo "📊 CPU USAGE:"
top -b -n 1 -p $PID | tail -2
echo ""

# Thread count
echo "🧵 THREAD COUNT:"
ps -o nlwp -p $PID | tail -1 | awk '{print "  Thread attivi: " $1}'
echo ""

# Connessioni di rete
echo "🌐 CONNESSIONI DI RETE:"
netstat -anp 2>/dev/null | grep $PID | wc -l | awk '{print "  Connessioni attive: " $1}'
echo ""

# File aperti
echo "📁 FILE APERTI:"
lsof -p $PID 2>/dev/null | wc -l | awk '{print "  File aperti: " $1}'
echo ""

# Strace per 5 secondi (mostra cosa sta facendo)
echo "🔬 SYSTEM CALLS (5 secondi):"
echo "  Analizzando..."
timeout 5 strace -c -p $PID 2>&1 | tail -20
echo ""

echo "✅ Check completato!"
echo ""
echo "💡 INTERPRETAZIONE:"
echo "  - Se vedi molte chiamate 'futex' o 'poll' → problema di threading/asyncio"
echo "  - Se vedi molte 'read'/'write' → problema I/O"
echo "  - Se vedi molte 'epoll_wait' → server web in attesa (normale)"
