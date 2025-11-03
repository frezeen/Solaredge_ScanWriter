#!/usr/bin/env python3
"""
Platform-specific fixes for Docker cross-platform compatibility
Risolve i problemi di compatibilità identificati nell'analisi del main.py
"""

import os
import platform
import shutil
from pathlib import Path

def fix_kill_process_function():
    """
    Sostituisce la funzione kill_process_on_port con versione cross-platform
    """
    main_py_path = Path("/app/main.py")
    
    if not main_py_path.exists():
        print("❌ main.py non trovato, skip fix")
        return
    
    # Leggi il file
    with open(main_py_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Sostituisci la funzione problematica con versione Docker-friendly
    old_function = '''def kill_process_on_port(port: int, log) -> bool:
    """Killa il processo che occupa una porta specifica (Debian/Linux)"""
    import subprocess
    
    try:
        # Trova il PID del processo sulla porta usando ss (sostituto moderno di netstat)
        result = subprocess.run(
            ['ss', '-tlnp', f'sport = :{port}'],
            capture_output=True,
            text=True,
            timeout=int(os.getenv('GLOBAL_TIMEOUT_SECONDS', '30'))
        )'''
    
    new_function = '''def kill_process_on_port(port: int, log) -> bool:
    """Killa il processo che occupa una porta specifica (Cross-Platform Docker)"""
    import subprocess
    import psutil
    
    try:
        # Usa psutil per compatibilità cross-platform
        for proc in psutil.process_iter(['pid', 'name', 'connections']):
            try:
                for conn in proc.info['connections'] or []:
                    if conn.laddr.port == port and conn.status == 'LISTEN':
                        log.info(f"🔍 Trovato processo PID {proc.info['pid']} sulla porta {port}")
                        proc.terminate()
                        proc.wait(timeout=5)
                        log.info(f"✅ Processo PID {proc.info['pid']} terminato")
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        log.info(f"ℹ️ Nessun processo trovato sulla porta {port}")
        return False'''
    
    # Sostituisci solo se la funzione vecchia esiste
    if old_function[:50] in content:
        content = content.replace(old_function, new_function)
        
        # Scrivi il file modificato
        with open(main_py_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Funzione kill_process_on_port aggiornata per cross-platform")
    else:
        print("ℹ️ Funzione kill_process_on_port già aggiornata o non trovata")

def fix_import_duplicates():
    """
    Rimuove import duplicati identificati nell'analisi
    """
    main_py_path = Path("/app/main.py")
    
    if not main_py_path.exists():
        return
    
    with open(main_py_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Rimuovi import 're' duplicato dentro le funzioni
    fixed_lines = []
    in_function = False
    
    for line in lines:
        # Rileva se siamo dentro una funzione
        if line.strip().startswith('def '):
            in_function = True
        elif line.strip() == '' and in_function:
            in_function = False
        
        # Skip import 're' duplicato dentro funzioni
        if in_function and line.strip() == 'import re':
            print("✅ Rimosso import 're' duplicato")
            continue
        
        fixed_lines.append(line)
    
    # Scrivi il file corretto
    with open(main_py_path, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)

def fix_return_statement():
    """
    Corregge il return statement incompleto per scan mode
    """
    main_py_path = Path("/app/main.py")
    
    if not main_py_path.exists():
        return
    
    with open(main_py_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Correggi return incompleto
    old_return = "elif args.scan:\n            return"
    new_return = "elif args.scan:\n            return handle_scan_mode(log)"
    
    if old_return in content:
        content = content.replace(old_return, new_return)
        
        with open(main_py_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Corretto return statement per scan mode")

def setup_docker_environment():
    """
    Configura l'ambiente Docker con le ottimizzazioni necessarie
    """
    # Crea directory necessarie
    dirs = ['/app/logs', '/app/cache', '/app/cookies', '/app/config/sources', '/app/data']
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    # Imposta variabili d'ambiente Docker-specific
    os.environ['DOCKER_MODE'] = 'true'
    os.environ['PYTHONPATH'] = '/app'
    
    print(f"✅ Ambiente Docker configurato per {platform.machine()} ({platform.system()})")

def main():
    """
    Applica tutti i fix per la compatibilità cross-platform
    """
    print("🔧 Applicando fix cross-platform per Docker...")
    
    try:
        setup_docker_environment()
        fix_return_statement()
        fix_import_duplicates()
        fix_kill_process_function()
        
        print("✅ Tutti i fix applicati con successo!")
        
    except Exception as e:
        print(f"❌ Errore durante l'applicazione dei fix: {e}")
        exit(1)

if __name__ == "__main__":
    main()