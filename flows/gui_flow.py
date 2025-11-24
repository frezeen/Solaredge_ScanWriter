import os
import re
import time
import asyncio
import webbrowser
import subprocess
import platform
from typing import Dict, Any, Optional
from logging import Logger
from cache.cache_manager import CacheManager
from utils.process_manager import kill_process_on_port



def run_gui_mode(log: Logger, cache: CacheManager, config: Optional[Dict[str, Any]] = None) -> int:
    """Avvia GUI con loop automatico"""
    log.info("🌐 Avvio GUI Dashboard con loop automatico")
    from gui.simple_web_gui import SimpleWebGUI
    
    gui = SimpleWebGUI(cache=cache, auto_start_loop=True)
    
    async def run_gui():
        port = int(os.getenv('GUI_PORT', '8092'))
        runner = None
        
        # Prova ad avviare sulla porta 8092 (usa default host='127.0.0.1')
        try:
            runner, _ = await gui.start(port=port)
            log.info(f"✅ Server GUI avviato su porta {port}")
        except OSError as e:
            error_msg = str(e).lower()
            
            # Porta occupata - prova a killare
            if "address already in use" in error_msg:
                log.warning(f"⚠️ Porta {port} occupata, tento di liberarla...")
                if kill_process_on_port(port, log):
                    log.info("🔄 Riprovo ad avviare il server...")
                    try:
                        runner, _ = await gui.start(port=port)
                        log.info(f"✅ Server GUI avviato su porta {port}")
                    except OSError as retry_error:
                        log.error(f"❌ Porta {port} ancora occupata dopo kill: {retry_error}")
                        return 1
                    except Exception as retry_error:
                        log.error(f"❌ Errore imprevisto durante riavvio GUI: {retry_error}")
                        return 1
                else:
                    log.error(f"❌ Impossibile liberare porta {port}. Verifica manualmente: sudo ss -tlnp | grep {port}")
                    return 1
            elif "permission denied" in error_msg:
                log.error(f"❌ Permessi insufficienti per porta {port}. Usa porta > 1024 o esegui come root")
                return 1
            else:
                log.error(f"❌ Errore di rete durante avvio GUI su porta {port}: {e}")
                raise
        
        # Apri browser SUBITO dopo che il server è avviato
        url = f"http://127.0.0.1:{port}"
        log.info(f"🌐 GUI disponibile su: {url}")
        log.info(f"📡 Accesso rete locale: http://{gui.real_ip}:{port} (se firewall permette)")
        log.info("Loop avviato automaticamente - usa la GUI per controllarlo")
        log.info("Premi Ctrl+C per fermare la GUI")
        
        # Aspetta che il server sia pronto (usa delay configurabile)
        await asyncio.sleep(float(os.getenv('SCHEDULER_API_DELAY_SECONDS', '1')))
        
        try:
            webbrowser.open(url)
        except Exception:
            pass
        
        try:
            # Loop infinito con gestione interruzioni
            # Usa un intervallo configurabile per bilanciare CPU e responsività
            gui_check_interval = 5  # 5 secondi per shutdown più reattivo
            while True:
                await asyncio.sleep(gui_check_interval)
        except KeyboardInterrupt:
            log.info("🛑 Interruzione ricevuta, chiusura GUI...")
        except asyncio.CancelledError:
            log.info("🛑 Task cancellato, chiusura GUI...")
        finally:
            log.info("🔄 Chiusura server GUI...")
            try:
                await runner.cleanup()
                log.info("✅ GUI chiusa correttamente")
            except Exception as e:
                log.error(f"Errore durante chiusura GUI: {e}")
    
    try:
        # Usa ProactorEventLoop su Windows, o uvloop se disponibile
        # Questo riduce il busy-wait di epoll
        try:
            import uvloop
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            log.info("✅ Usando uvloop per migliori performance")
        except ImportError:
            # uvloop non disponibile, usa default
            pass
        
        asyncio.run(run_gui())
    except KeyboardInterrupt:
        # Questo è normale quando si preme Ctrl+C
        log.info("👋 GUI chiusa dall'utente")
        pass
    except asyncio.CancelledError:
        log.info("🛑 Task GUI cancellato")
        pass
    except ImportError as e:
        log.error(f"❌ Modulo GUI mancante: {e}. Installa: pip install aiohttp")
        return 1
    except Exception as e:
        log.error(f"❌ Errore imprevisto nella GUI: {e}")
        return 1
    
    return 0
