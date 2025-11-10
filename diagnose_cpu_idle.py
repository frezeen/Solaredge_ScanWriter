#!/usr/bin/env python3
"""Script per diagnosticare CPU alta con loop fermo"""

import psutil
import time
import threading
import os
from datetime import datetime

def monitor_threads():
    """Monitora thread attivi"""
    print("\n" + "="*80)
    print("🧵 THREAD ATTIVI")
    print("="*80)
    
    for thread in threading.enumerate():
        print(f"  - {thread.name}")
        print(f"    Daemon: {thread.daemon}")
        print(f"    Alive: {thread.is_alive()}")
        print(f"    Ident: {thread.ident}")
        print()
    
    print(f"Totale thread: {threading.active_count()}")

def monitor_cpu_per_thread():
    """Monitora CPU per thread (se possibile)"""
    print("\n" + "="*80)
    print("💻 CPU PER THREAD")
    print("="*80)
    
    process = psutil.Process(os.getpid())
    
    try:
        # Prova a ottenere info sui thread
        threads = process.threads()
        print(f"Thread di sistema: {len(threads)}")
        for i, thread in enumerate(threads, 1):
            print(f"  Thread {i}:")
            print(f"    ID: {thread.id}")
            print(f"    User time: {thread.user_time:.2f}s")
            print(f"    System time: {thread.system_time:.2f}s")
    except Exception as e:
        print(f"Impossibile ottenere info thread: {e}")

def monitor_connections():
    """Monitora connessioni di rete"""
    print("\n" + "="*80)
    print("🌐 CONNESSIONI DI RETE")
    print("="*80)
    
    process = psutil.Process(os.getpid())
    
    try:
        connections = process.connections()
        print(f"Totale connessioni: {len(connections)}")
        
        if connections:
            for i, conn in enumerate(connections[:20], 1):  # Prime 20
                print(f"  {i}. {conn.status}: {conn.laddr} -> {conn.raddr if conn.raddr else 'N/A'}")
    except (psutil.AccessDenied, AttributeError) as e:
        print(f"Impossibile ottenere connessioni: {e}")

def monitor_files():
    """Monitora file aperti"""
    print("\n" + "="*80)
    print("📁 FILE APERTI")
    print("="*80)
    
    process = psutil.Process(os.getpid())
    
    try:
        open_files = process.open_files()
        print(f"Totale file aperti: {len(open_files)}")
        
        if open_files:
            for i, f in enumerate(open_files[:20], 1):  # Primi 20
                print(f"  {i}. {f.path} (fd: {f.fd})")
    except (psutil.AccessDenied, AttributeError) as e:
        print(f"Impossibile ottenere file aperti: {e}")

def monitor_cpu_continuous(duration=30):
    """Monitora CPU continuamente"""
    print("\n" + "="*80)
    print(f"📊 MONITORAGGIO CPU CONTINUO ({duration} secondi)")
    print("="*80)
    
    process = psutil.Process(os.getpid())
    samples = []
    
    print("\nTimestamp       CPU%    Threads  Connections  Files")
    print("-" * 60)
    
    for i in range(duration):
        timestamp = datetime.now().strftime('%H:%M:%S')
        cpu = process.cpu_percent(interval=1.0)
        num_threads = process.num_threads()
        
        try:
            num_connections = len(process.connections())
        except:
            num_connections = 0
        
        try:
            num_files = len(process.open_files())
        except:
            num_files = 0
        
        samples.append(cpu)
        
        indicator = "🔴" if cpu > 5 else "🟢"
        print(f"{indicator} {timestamp}    {cpu:5.1f}%   {num_threads:3d}      {num_connections:3d}          {num_files:3d}")
    
    # Statistiche finali
    print("\n" + "="*80)
    print("📈 STATISTICHE")
    print("="*80)
    avg_cpu = sum(samples) / len(samples)
    max_cpu = max(samples)
    min_cpu = min(samples)
    
    print(f"CPU Media: {avg_cpu:.1f}%")
    print(f"CPU Max: {max_cpu:.1f}%")
    print(f"CPU Min: {min_cpu:.1f}%")
    
    high_cpu_count = sum(1 for cpu in samples if cpu > 5)
    print(f"\nCampioni con CPU > 5%: {high_cpu_count}/{len(samples)} ({high_cpu_count/len(samples)*100:.1f}%)")

if __name__ == '__main__':
    print("🔍 DIAGNOSI CPU CON LOOP FERMO")
    print("="*80)
    print("\n⚠️  IMPORTANTE: Questo script deve essere eseguito MENTRE main.py è in esecuzione")
    print("   ma con il loop FERMO dalla GUI\n")
    
    input("Premi INVIO per iniziare la diagnosi...")
    
    # Snapshot iniziale
    monitor_threads()
    monitor_cpu_per_thread()
    monitor_connections()
    monitor_files()
    
    # Monitoraggio continuo
    monitor_cpu_continuous(duration=30)
    
    print("\n✅ Diagnosi completata!")
    print("\n💡 COSA CERCARE:")
    print("  - Thread inaspettati (dovrebbero essere pochi con loop fermo)")
    print("  - Connessioni aperte inutilmente")
    print("  - File aperti in eccesso")
    print("  - CPU costantemente alta anche con loop fermo")
