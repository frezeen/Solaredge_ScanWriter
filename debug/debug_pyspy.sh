#!/bin/bash
# Script per profilare con py-spy (sampling profiler)

echo "🔍 Installazione py-spy se necessario..."
pip install py-spy 2>/dev/null || echo "py-spy già installato"

echo ""
echo "📊 Trova il PID del processo Python:"
ps aux | grep python | grep -v grep

echo ""
read -p "Inserisci il PID del processo main.py: " PID

if [ -z "$PID" ]; then
    echo "❌ PID non fornito"
    exit 1
fi

echo ""
echo "🔍 Profiling per 60 secondi con py-spy..."
echo "Generazione flame graph in logs/cpu_flamegraph.svg"

py-spy record --pid $PID --duration 60 --output logs/cpu_flamegraph.svg --format speedscope

echo ""
echo "✅ Flame graph salvato in: logs/cpu_flamegraph.svg"
echo "Apri il file con un browser per visualizzare dove viene speso il tempo CPU"
