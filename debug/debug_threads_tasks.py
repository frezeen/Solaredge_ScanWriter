#!/usr/bin/env python3
"""Script per monitorare thread attivi e asyncio tasks"""

import sys
import time
import threading
import asyncio
import psutil
import os

def monitor_threads():
    """Monitora thread attivi"""
    print("\n" + "=" * 80)
    print("🧵 THREAD ATTIVI")
    print("=" * 80)
    
    for thread in threading.enumerate():
        print(f"  - {thread.name} (daemon={thread.daemon}, alive={thread.is_alive()})")
    
    print(f"\nTotale thread: {threading.active_count()}")

def monitor_process():
    """Monitora utilizzo risorse del processo corrente"""
    process = psutil.Process(os.getpid())
    
    print("\n" + "=" * 80)
    print("💻 UTILIZZO RISORSE PROCESSO")
    print("=" * 80)
    
    cpu_percent = process.cpu_percent(interval=1.0)
    memory_info = process.memory_info()
    
    print(f"  CPU: {cpu_percent:.1f}%")
    print(f"  Memoria RSS: {memory_info.rss / 1024 / 1024:.1f} MB")
    print(f"  Memoria VMS: {memory_info.vms / 1024 / 1024:.1f} MB")
    print(f"  Thread count: {process.num_threads()}")
    print(f"  File descriptors aperti: {process.num_fds() if hasattr(process, 'num_fds') else 'N/A'}")
    
    # Connessioni di rete
    try:
        connections = process.connections()
        print(f"  Connessioni di rete: {len(connections)}")
        if connections:
            print("\n  Connessioni attive:")
            for conn in connections[:10]:  # Mostra solo prime 10
                print(f"    - {conn.status}: {conn.laddr} -> {conn.raddr if conn.raddr else 'N/A'}")
    except (psutil.AccessDenied, AttributeError):
        print("  Connessioni di rete: N/A (permessi insufficienti)")

async def monitor_asyncio_tasks():
    """Monitora asyncio tasks attivi"""
    print("\n" + "=" * 80)
    print("⚡ ASYNCIO TASKS ATTIVI")
    print("=" * 80)
    
    try:
        tasks = asyncio.all_tasks()
        print(f"\nTotale tasks: {len(tasks)}")
        
        for i, task in enumerate(tasks, 1):
            coro = task.get_coro()
            print(f"\n  Task {i}:")
            print(f"    - Nome: {task.get_name()}")
            print(f"    - Coroutine: {coro.__qualname__ if hasattr(coro, '__qualname__') else str(coro)}")
            print(f"    - Done: {task.done()}")
            print(f"    - Cancelled: {task.cancelled()}")
            
            # Stack trace se disponibile
            try:
                stack = task.get_stack()
                if stack:
                    print(f"    - Stack frames: {len(stack)}")
            except:
                pass
    except RuntimeError:
        print("  Nessun event loop attivo")

def continuous_monitor(interval=5, duration=60):
    """Monitora continuamente per un certo periodo"""
    print(f"\n🔄 Monitoraggio continuo per {duration} secondi (intervallo {interval}s)")
    print("Premi Ctrl+C per interrompere\n")
    
    start_time = time.time()
    iteration = 0
    
    try:
        while time.time() - start_time < duration:
            iteration += 1
            print(f"\n{'=' * 80}")
            print(f"ITERAZIONE {iteration} - Tempo: {time.time() - start_time:.1f}s")
            print(f"{'=' * 80}")
            
            monitor_process()
            monitor_threads()
            
            # Prova a monitorare asyncio tasks se c'è un loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Non possiamo chiamare direttamente await qui
                    print("\n⚡ Event loop attivo (usa debug_asyncio_live.py per dettagli tasks)")
            except RuntimeError:
                print("\n⚡ Nessun event loop asyncio attivo")
            
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Monitoraggio interrotto")
    
    print(f"\n✅ Monitoraggio completato dopo {time.time() - start_time:.1f} secondi")

if __name__ == '__main__':
    print("🔍 DEBUG THREAD E TASKS - SolarEdge Collector")
    print("=" * 80)
    
    if len(sys.argv) > 1 and sys.argv[1] == '--continuous':
        continuous_monitor()
    else:
        monitor_process()
        monitor_threads()
        
        print("\n💡 Suggerimento: usa --continuous per monitoraggio continuo")
        print("   Esempio: python debug_threads_tasks.py --continuous")
