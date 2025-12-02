#!/usr/bin/env python3
"""Test parser web con dati dicembre"""

import gzip
import json
from config.env_loader import load_env
from config.config_manager import get_config_manager
from parser.web_parser import parse_web

load_env()

# Carica cache dicembre
cache_file = r'cache\web\SITE\2025-12_19-56.json.gz'
with gzip.open(cache_file, 'rt') as f:
    data = json.loads(f.read())

# Estrai measurements_raw
measurements_raw = data.get('data', {})

print("=" * 60)
print("TEST PARSER WEB CON DATI DICEMBRE")
print("=" * 60)
print(f"\nInput measurements_raw:")
print(f"  Items: {len(measurements_raw.get('list', []))}")

# Carica config
config_manager = get_config_manager()
config = config_manager.get_raw_config()

print(f"\nConfig caricato:")
print(f"  Sources: {list(config.get('sources', {}).keys())}")

# Prova parsing
try: