#!/bin/bash
# SolarEdge Service Status Script

echo "=== Solaredge_ScanWriter Status ==="
echo ""

# Service status (only if service is loaded)
echo "🔧 Service Status:"
if systemctl is-enabled solaredge-scanwriter >/dev/null 2>&1; then
    systemctl status solaredge-scanwriter --no-pager 2>/dev/null || echo "  Service not started yet"
else
    echo "  Service created but not enabled yet"
    echo "  Run: systemctl enable --now solaredge-scanwriter"
fi
echo ""

# Process information
echo "🔍 Process Information:"
if pgrep -f "solaredge" >/dev/null; then
    echo "✅ SolarEdge processes running:"
    ps aux | grep -E "(solaredge|main\.py)" | grep -v grep | head -5
else
    echo "❌ No SolarEdge processes found"
fi
echo ""

# System Python check
echo "🐍 System Python:"
if command -v python3 &> /dev/null; then
    echo "✅ System Python available"
    echo "  Python: $(python3 --version)"
else
    echo "❌ System Python not found"
fi
echo ""

# Recent logs
echo "📋 Recent Logs (last 15 lines):"
journalctl -u solaredge-scanwriter --lines=15 --no-pager
echo ""

# Log files
echo "📁 Log Files:"
if [[ -d /opt/Solaredge_ScanWriter/logs ]]; then
    find /opt/Solaredge_ScanWriter/logs -name "*.log" -type f 2>/dev/null | head -5 | while read file; do
        size=$(du -h "$file" 2>/dev/null | cut -f1)
        modified=$(stat -c %y "$file" 2>/dev/null | cut -d' ' -f1)
        echo "  • $(basename "$file"): $size (modified: $modified)"
    done
else
    echo "  ❌ Log directory not found"
fi
