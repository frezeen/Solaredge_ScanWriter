#!/bin/bash
# Script automatico per diagnosi CPU - esegui sulla macchina Debian

set -e

REPORT_DIR="logs/cpu_diagnosis_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$REPORT_DIR"

echo "🔍 DIAGNOSI AUTOMATICA CPU - SolarEdge Collector"
echo "Report salvato in: $REPORT_DIR"
echo ""

# 1. Info sistema
echo "📊 Raccolta info sistema..."
{
    echo "=== SYSTEM INFO ==="
    uname -a
    echo ""
    echo "=== CPU INFO ==="
    lscpu | grep -E "Model name|CPU\(s\)|Thread|Core"
    echo ""
    echo "=== MEMORY INFO ==="
    free -h
    echo ""
} > "$REPORT_DIR/system_info.txt"

# 2. Trova processo Python
echo "🔍 Ricerca processo Python..."
PYTHON_PID=$(pgrep -f "python.*main.py" | head -1)

if [ -z "$PYTHON_PID" ]; then
    echo "❌ Processo main.py non trovato!"
    echo "   Avvia prima: python main.py"
    exit 1
fi

echo "✅ Processo trovato: PID $PYTHON_PID"

# 3. Snapshot iniziale CPU
echo "📸 Snapshot iniziale utilizzo CPU..."
{
    echo "=== INITIAL CPU SNAPSHOT ==="
    ps -p $PYTHON_PID -o pid,ppid,cmd,%cpu,%mem,etime
    echo ""
} > "$REPORT_DIR/cpu_snapshot.txt"

# 4. Thread count
echo "🧵 Conteggio thread..."
{
    echo "=== THREAD COUNT ==="
    ps -p $PYTHON_PID -T | wc -l
    echo ""
    echo "=== THREAD DETAILS ==="
    ps -p $PYTHON_PID -T -o pid,tid,cmd,%cpu
    echo ""
} >> "$REPORT_DIR/cpu_snapshot.txt"

# 5. Connessioni di rete
echo "🌐 Verifica connessioni di rete..."
{
    echo "=== NETWORK CONNECTIONS ==="
    lsof -p $PYTHON_PID -a -i 2>/dev/null || netstat -anp 2>/dev/null | grep $PYTHON_PID || echo "Nessuna connessione trovata"
    echo ""
} >> "$REPORT_DIR/cpu_snapshot.txt"

# 6. File descriptors aperti
echo "📁 Verifica file descriptors..."
{
    echo "=== OPEN FILE DESCRIPTORS ==="
    ls -l /proc/$PYTHON_PID/fd 2>/dev/null | wc -l
    echo ""
    echo "=== FD DETAILS (primi 20) ==="
    ls -l /proc/$PYTHON_PID/fd 2>/dev/null | head -20
    echo ""
} >> "$REPORT_DIR/cpu_snapshot.txt"

# 7. Monitoring CPU per 30 secondi
echo "⏱️  Monitoring CPU per 30 secondi (campionamento ogni secondo)..."
{
    echo "=== CPU MONITORING (30 samples) ==="
    echo "Timestamp,CPU%,MEM%"
    for i in {1..30}; do
        TIMESTAMP=$(date +%H:%M:%S)
        CPU_MEM=$(ps -p $PYTHON_PID -o %cpu,%mem --no-headers)
        echo "$TIMESTAMP,$CPU_MEM"
        sleep 1
    done
    echo ""
} > "$REPORT_DIR/cpu_monitoring.csv"

# Calcola media CPU
AVG_CPU=$(awk -F',' 'NR>1 {sum+=$2; count++} END {print sum/count}' "$REPORT_DIR/cpu_monitoring.csv")
echo "📊 CPU Media: $AVG_CPU%"

# 8. Verifica configurazione
echo "⚙️  Verifica configurazione..."
{
    echo "=== CONFIGURATION CHECK ==="
    echo ""
    echo "--- .env LOG_LEVEL ---"
    grep "^LOG_LEVEL" .env 2>/dev/null || echo "LOG_LEVEL non trovato"
    echo ""
    echo "--- .env LOOP INTERVALS ---"
    grep "^LOOP_" .env 2>/dev/null || echo "LOOP intervals non trovati"
    echo ""
    echo "--- Modbus enabled ---"
    grep -A2 "^modbus:" config/sources/modbus_endpoints.yaml 2>/dev/null || echo "Modbus config non trovato"
    echo ""
} > "$REPORT_DIR/configuration.txt"

# 9. Verifica log recenti
echo "📝 Analisi log recenti..."
{
    echo "=== RECENT LOGS (last 50 lines) ==="
    tail -50 logs/*.log 2>/dev/null | grep -E "ERROR|WARNING|realtime|modbus" || echo "Nessun log trovato"
    echo ""
} > "$REPORT_DIR/recent_logs.txt"

# 10. Strace per 10 secondi (syscalls)
echo "🔬 Strace per 10 secondi (syscalls più frequenti)..."
timeout 10 strace -c -p $PYTHON_PID 2> "$REPORT_DIR/strace_summary.txt" || true

# 11. Genera report finale
echo ""
echo "=" | tr '=' '='
echo "📋 REPORT FINALE"
echo "=" | tr '=' '='
echo ""

{
    echo "=== DIAGNOSI CPU - SUMMARY ==="
    echo ""
    echo "Data: $(date)"
    echo "PID: $PYTHON_PID"
    echo "CPU Media (30s): $AVG_CPU%"
    echo ""
    
    echo "--- Possibili Cause ---"
    
    # Analizza CPU media
    if (( $(echo "$AVG_CPU > 10" | bc -l) )); then
        echo "🔴 CPU ALTA (>10%): Problema significativo"
    elif (( $(echo "$AVG_CPU > 5" | bc -l) )); then
        echo "🟡 CPU MEDIA (5-10%): Ottimizzabile"
    else
        echo "🟢 CPU NORMALE (<5%): OK"
    fi
    
    # Verifica thread
    THREAD_COUNT=$(ps -p $PYTHON_PID -T | wc -l)
    if [ $THREAD_COUNT -gt 15 ]; then
        echo "⚠️  Troppi thread ($THREAD_COUNT): Possibile thread leak"
    fi
    
    # Verifica log level
    LOG_LEVEL=$(grep "^LOG_LEVEL" .env 2>/dev/null | cut -d'=' -f2)
    if [ "$LOG_LEVEL" = "DEBUG" ]; then
        echo "⚠️  LOG_LEVEL=DEBUG: Troppo verboso, usa INFO o WARNING"
    fi
    
    # Verifica intervallo realtime
    REALTIME_INTERVAL=$(grep "^LOOP_REALTIME_INTERVAL_SECONDS" .env 2>/dev/null | cut -d'=' -f2)
    if [ ! -z "$REALTIME_INTERVAL" ] && [ $REALTIME_INTERVAL -lt 10 ]; then
        echo "⚠️  Realtime interval troppo basso ($REALTIME_INTERVAL s): Considera 15-30s"
    fi
    
    echo ""
    echo "--- File Generati ---"
    ls -lh "$REPORT_DIR"
    
    echo ""
    echo "--- Prossimi Passi ---"
    echo "1. Leggi questo report: cat $REPORT_DIR/diagnosis_summary.txt"
    echo "2. Analizza CPU monitoring: cat $REPORT_DIR/cpu_monitoring.csv"
    echo "3. Verifica strace: cat $REPORT_DIR/strace_summary.txt"
    echo "4. Se CPU ancora alta, esegui: python debug_cpu_profile.py"
    
} | tee "$REPORT_DIR/diagnosis_summary.txt"

echo ""
echo "✅ Diagnosi completata!"
echo "📁 Report salvato in: $REPORT_DIR"
echo ""
echo "Per vedere il summary:"
echo "  cat $REPORT_DIR/diagnosis_summary.txt"
