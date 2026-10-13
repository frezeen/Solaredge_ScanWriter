#!/bin/bash
# SolarEdge Installation Test Script

cd /opt/Solaredge_ScanWriter

echo "=== SolarEdge Installation Test ==="
echo ""

# Test System Python
echo "🐍 System Python:"
if command -v python3 &> /dev/null; then
    echo "✅ System Python exists"
    echo "  Python path: $(which python3)"
    echo "  Python version: $(python3 --version)"
else
    echo "❌ System Python not found"
fi
echo ""

# Test installed packages
echo "📦 Installed Python packages:"
if command -v pip3 &> /dev/null; then
    pip3 list | grep -E "(aiohttp|influxdb|yaml|pymodbus|solaredge)" | head -10
else
    echo "❌ pip3 not found"
fi
echo ""

# Test services
echo "🔧 Services status:"
echo "  SolarEdge: $(systemctl is-active solaredge-scanwriter 2>/dev/null || echo 'not-found')"
echo "  InfluxDB: $(systemctl is-active influxdb 2>/dev/null || echo 'not-found')"
echo "  Grafana: $(systemctl is-active grafana-server 2>/dev/null || echo 'not-found')"
echo ""

# Test directories and permissions
echo "📁 Directory structure:"
ls -la /opt/Solaredge_ScanWriter/ | head -10
echo ""

# Test configuration
echo "⚙️ Configuration:"
if [[ -f .env ]]; then
    echo "✅ .env file exists"
    echo "  Key variables:"
    grep -E "^[A-Z].*=" .env | head -5 | sed 's/=.*/=***/' | sed 's/^/    /'
else
    echo "❌ .env file missing"
fi
echo ""

# Test main application
echo "🧪 Application test:"
if [[ -f main.py ]]; then
    echo "✅ main.py exists"
    if python3 -c "import main" 2>/dev/null; then
        echo "✅ Main module imports successfully"
    else
        echo "⚠️ Main module has import issues (check dependencies)"
    fi
else
    echo "❌ main.py not found"
fi

echo ""
echo "=== Test Complete ==="
