"""env_loader.py
Caricamento semplice file .env senza dipendenze esterne.
Ignora linee vuote o che iniziano con '#'. SOVRASCRIVE sempre le variabili esistenti per garantire pulizia.
"""
from __future__ import annotations
import os
from pathlib import Path

def load_env(path: str = ".env") -> int:
    p = Path(path)
    if not p.exists():
        return 0
    loaded = 0
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().replace('\r', '').replace('\n', '').replace('\t', '')  # Rimuovi tutti i caratteri di controllo
        if k:
            # PULISCI SEMPRE le variabili esistenti, anche se già presenti
            old_value = os.environ.get(k, '')
            if old_value != v:
                os.environ[k] = v
                loaded += 1
    return loaded

__all__ = ["load_env"]
