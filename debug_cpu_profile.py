#!/usr/bin/env python3
"""Script per profilare l'utilizzo CPU del main.py"""

import cProfile
import pstats
import io
import sys
import os

# Imposta le variabili d'ambiente necessarie
from config.env_loader import load_env
load_env()

def profile_main():
    """Profila l'esecuzione del main per 60 secondi"""
    print("🔍 Avvio profiling CPU per 60 secondi...")
    print("Premi Ctrl+C dopo ~60 secondi per vedere i risultati\n")
    
    profiler = cProfile.Profile()
    profiler.enable()
    
    try:
        # Importa e avvia main
        from main import main
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Profiling interrotto, generazione report...\n")
    finally:
        profiler.disable()
        
        # Genera report
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s)
        
        # Ordina per tempo cumulativo
        ps.sort_stats('cumulative')
        
        print("=" * 80)
        print("TOP 30 FUNZIONI PER TEMPO CUMULATIVO")
        print("=" * 80)
        ps.print_stats(30)
        
        # Ordina per tempo totale (time)
        ps.sort_stats('time')
        print("\n" + "=" * 80)
        print("TOP 30 FUNZIONI PER TEMPO TOTALE")
        print("=" * 80)
        ps.print_stats(30)
        
        # Salva report completo su file
        with open('logs/cpu_profile_report.txt', 'w') as f:
            ps = pstats.Stats(profiler, stream=f)
            ps.sort_stats('cumulative')
            ps.print_stats()
        
        print(f"\n✅ Report completo salvato in: logs/cpu_profile_report.txt")

if __name__ == '__main__':
    profile_main()
