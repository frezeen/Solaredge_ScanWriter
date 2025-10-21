#!/bin/bash
# Simple script to activate Python virtual environment

cd "$(dirname "$0")"

if [[ -f venv/bin/activate ]]; then
    echo "🐍 Activating Python virtual environment..."
    source venv/bin/activate
    echo "✅ Virtual environment activated!"
    echo "  Python: $(which python)"
    echo "  Pip: $(which pip)"
    echo ""
    echo "💡 You can now run Python commands with the correct environment"
    echo "💡 Type 'deactivate' to exit the virtual environment"
    echo ""
    
    # Start a new shell with venv activated
    exec bash
else
    echo "❌ Virtual environment not found at venv/bin/activate"
    echo "   Make sure you're in the correct directory and venv is created"
    echo "   Run: python3 -m venv venv && pip install -r requirements.txt"
    exit 1
fi