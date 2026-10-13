#!/bin/bash
# Manual run script for testing SolarEdge application

cd /opt/Solaredge_ScanWriter

echo "🚀 SolarEdge Manual Run Script"
echo "============================="
echo ""

# Show Python info
echo "🐍 Python Environment:"
echo "  Python: $(which python3)"
echo "  Version: $(python3 --version)"
echo ""

# Show available options
echo "📋 Available run modes:"
echo "  1. GUI mode (default): python3 main.py"
echo "  2. API test: python3 main.py --api"
echo "  3. Web test: python3 main.py --web"
echo "  4. Realtime test: python3 main.py --realtime"
echo "  5. History mode: python3 main.py --history"
echo ""

# Ask user what to run
read -p "Enter mode number (1-5) or press Enter for GUI mode: " choice

case $choice in
    2)
        echo "🔄 Running API test..."
        python3 main.py --api
        python main.py --api
        ;;
    3)
        echo "🔄 Running Web test..."
        python main.py --web
        ;;
    4)
        python3 main.py --api
        ;;
    3)
        echo "🔄 Running Web test..."
        python3 main.py --web
        ;;
    4)
        echo "🔄 Running Realtime test..."
        python3 main.py --realtime
        ;;
    5)
        echo "🔄 Running History mode..."
        python3 main.py --history
        ;;
    *)
        echo "🔄 Running GUI mode..."
        echo "   Access GUI at: http://$(hostname -I | awk '{print $1}'):8092"
        echo "   Press Ctrl+C to stop"
        echo ""
        python3 main.py
        ;;
esac
