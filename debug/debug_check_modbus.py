#!/usr/bin/env python3
"""Verifica se il polling Modbus ogni 5 secondi causa l'alto utilizzo CPU"""

import time
import psutil
import os
from datetime import datetime

def monitor_cpu_with_timestamps(duration=60):
    """Monitora CPU con timestamp per correlare con operazioni"""
    print(f"🔍 Monitoraggio CPU per {duration} secondi")
    print("Cerca pattern di picchi ogni 5 secondi (realtime) o 15 minuti (api/web)\n")
    
    process = psutil.Process(os.getpid())
    samples = []
    
    start_time = time.time()
    
    try:
        while time.time() - start_time < duration:
            timestamp = datetime.now().strftime('%H:%M:%S')
            cpu = process.cpu_percent(interval=0.5)
            
            samples.append((timestamp, cpu))
            
            # Stampa in tempo reale
            indicator = "🔴" if cpu > 5 else "🟢"
            print(f"{indicator} {timestamp} - CPU: {cpu:5.1f}%")
            
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\n⏹️  Monitoraggio interrotto")
    
    # Analisi
    print("\n" + "=" * 80)
    print("📊 ANALISI")
    print("=" * 80)
    
    if samples:
        cpu_values = [s[1] for s in samples]
        avg_cpu = sum(cpu_values) / len(cpu_values)
        max_cpu = max(cpu_values)
        min_cpu = min(cpu_values)
        
        print(f"CPU Media: {avg_cpu:.1f}%")
        print(f"CPU Max: {max_cpu:.1f}%")
        print(f"CPU Min: {min_cpu:.1f}%")
        
        # Conta picchi
        high_cpu_count = sum(1 for cpu in cpu_values if cpu > 5)
        print(f"\nCampioni con CPU > 5%: {high_cpu_count}/{len(cpu_values)} ({high_cpu_count/len(cpu_values)*100:.1f}%)")
        
        # Cerca pattern periodici
        print("\n🔍 Cerca pattern periodici:")
        print("Se vedi picchi regolari ogni ~5 secondi → problema realtime polling")
        print("Se vedi picchi ogni ~15 minuti → problema api/web collection")
        print("Se CPU costantemente alta → problema busy-wait o loop")

if __name__ == '__main__':
    print("🔍 DEBUG MODBUS POLLING - SolarEdge Collector")
    print("=" * 80)
    print("\n⚠️  IMPORTANTE: Avvia questo script DOPO aver avviato main.py")
    print("   Questo script monitora il processo CORRENTE, non main.py\n")
    
    input("Premi INVIO per iniziare il monitoraggio...")
    
    monitor_cpu_with_timestamps(duration=60)
