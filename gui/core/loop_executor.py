"""Loop Executor - Gestione esecuzione loop flows per GUI

Responsabilità:
- Esecuzione loop continuo con scheduling automatico
- Gestione intervalli da variabili d'ambiente
- Verifica enabled/disabled per ogni flow
- Aggiornamento statistiche GUI
- Integrazione con main.execute_flow()
"""

import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any

from main import execute_flow
from app_logging import get_logger
from utils.yaml_loader import load_yaml


class LoopExecutor:
    """Esecutore loop per GUI con scheduling automatico"""

    def __init__(self, state_manager, logger, cache=None):
        """Inizializza loop executor.

        Args:
            state_manager: StateManager instance per tracking stato/statistiche
            logger: Logger instance
            cache: CacheManager instance (opzionale)
        """
        self.state_manager = state_manager
        self.logger = logger
        self.cache = cache

    async def auto_start(self, load_config_callback):
        """Avvia automaticamente il loop con ricaricamento configurazione.

        Args:
            load_config_callback: Callback async per caricare config (es. self.load_config)
        """
        try:
            if self.state_manager.loop_running:
                self.logger.info("[GUI] Loop già in esecuzione")
                return

            self.logger.info("[GUI] Avvio automatico loop - ricaricamento configurazione...")

            # 1. Ricarica variabili d'ambiente dal file .env
            try:
                from config.env_loader import load_env
                load_env()
                self.logger.info("[GUI] ✅ Variabili d'ambiente ricaricate da .env")
            except Exception as e:
                self.logger.error(f"[GUI] ❌ Errore ricaricamento .env: {e}")

            # 2. Ricarica configurazione YAML principale
            try:
                await load_config_callback()
                self.logger.info("[GUI] ✅ Configurazione YAML principale ricaricata")
            except Exception as e:
                self.logger.error(f"[GUI] ❌ Errore ricaricamento config: {e}")

            # 3. Ricarica config manager globale
            try:
                from config.config_manager import get_config_manager
                config_manager = get_config_manager()
                config_manager.reload()
                self.logger.info("[GUI] ✅ Config manager globale ricaricato")
            except Exception as e:
                self.logger.error(f"[GUI] ❌ Errore ricaricamento config manager: {e}")
                config_manager = None

            # 4. Reset flag di stop e avvia il loop
            self.state_manager.stop_requested = False
            self.state_manager.loop_running = True
            self.state_manager.loop_mode = True

            # 5. Ottieni config completo
            if config_manager:
                config = config_manager.get_raw_config()
                self.logger.info("[GUI] ✅ Config completo caricato con sources da config_manager")
            else:
                config = await load_config_callback()
                self.logger.warning("[GUI] ⚠️ Usando config da load_config_callback (senza sources)")

            # 6. Verifica cache
            if not self.cache:
                from cache.cache_manager import CacheManager
                self.cache = CacheManager()
                self.logger.warning("[GUI] Cache non passato, creando nuova istanza")

            # 7. Avvia il loop asincrono
            asyncio.create_task(self.run(self.cache, config))

            self.logger.info("[GUI] 🚀 Loop avviato automaticamente con configurazione aggiornata")

        except Exception as e:
            self.logger.error(f"[GUI] Errore avvio automatico loop: {e}")

    async def run(self, cache, config):
        """Esegue loop continuo con scheduling automatico.

        Args:
            cache: CacheManager instance
            config: Configurazione completa
        """
        self.logger.info("[GUI] 🔄 Avvio loop personalizzato per GUI")

        # Aggiorna statistiche per il nuovo loop
        self.state_manager.loop_stats['start_time'] = datetime.now()
        self.state_manager.loop_stats['status'] = 'running'
        self.state_manager.loop_stats['last_api_web_run'] = datetime.min

        log = get_logger("main")

        # Timestamp per tracking esecuzioni
        last_api_web_run = datetime.min
        last_realtime_run = datetime.min
        last_gme_run = datetime.min

        # Leggi intervalli dal file .env
        api_mins = int(os.getenv('LOOP_API_INTERVAL_MINUTES', '15'))
        web_mins = int(os.getenv('LOOP_WEB_INTERVAL_MINUTES', '15'))
        realtime_secs = int(os.getenv('LOOP_REALTIME_INTERVAL_SECONDS', '5'))
        gme_mins = int(os.getenv('LOOP_GME_INTERVAL_MINUTES', '1440'))

        api_web_interval = timedelta(minutes=max(api_mins, web_mins))
        realtime_interval = timedelta(seconds=realtime_secs)
        gme_interval = timedelta(minutes=gme_mins)

        # Verifica quali flow sono abilitati
        api_enabled = self._load_source_enabled_with_check('config/sources/api_endpoints.yaml', 'api_ufficiali')
        web_enabled = self._load_source_enabled_with_check('config/sources/web_endpoints.yaml', 'web_scraping')
        modbus_enabled = self._load_source_enabled_with_check('config/sources/modbus_endpoints.yaml', 'modbus')
        gme_enabled = os.getenv('GME_ENABLED', 'false').lower() == 'true'

        # Log configurazione
        self._log_flow_configuration(api_enabled, web_enabled, modbus_enabled, gme_enabled,
                                     api_mins, web_mins, realtime_secs, gme_mins)

        try:
            while self.state_manager.loop_running and not self.state_manager.stop_requested:
                current_time = datetime.now()

                # Calcola tempo fino alla prossima operazione
                time_until_api_web = (last_api_web_run + api_web_interval - current_time).total_seconds()
                time_until_realtime = (last_realtime_run + realtime_interval - current_time).total_seconds()
                time_until_gme = (last_gme_run + gme_interval - current_time).total_seconds()

                # Debug logging per GME
                if gme_enabled and time_until_gme < 60:
                    self.logger.debug(f"[GME DEBUG] time_until_gme={time_until_gme:.1f}s, last_run={last_gme_run}, interval={gme_interval}")

                # Esegui API e Web
                if (api_enabled or web_enabled) and time_until_api_web <= 0:
                    await self._execute_api_web_flows(api_enabled, web_enabled, log, cache, config)
                    last_api_web_run = current_time
                    self.state_manager.loop_stats['last_api_web_run'] = current_time
                    self.state_manager.loop_stats['last_update'] = current_time
                    self.state_manager.loop_stats['next_api_web_run'] = current_time + api_web_interval
                    time_until_api_web = api_web_interval.total_seconds()
                    time_until_realtime = (last_realtime_run + realtime_interval - datetime.now()).total_seconds()
                elif not api_enabled and not web_enabled:
                    time_until_api_web = 999999

                # Esegui Realtime
                if modbus_enabled and time_until_realtime <= 0:
                    await self._execute_realtime_flow(log, cache, config)
                    last_realtime_run = datetime.now()
                    self.state_manager.loop_stats['last_update'] = datetime.now()
                    time_until_realtime = realtime_interval.total_seconds()
                elif not modbus_enabled:
                    time_until_realtime = 999999

                # Esegui GME
                if gme_enabled and time_until_gme <= 0:
                    await self._execute_gme_flow(log, cache, config, last_gme_run, gme_interval, time_until_gme)
                    last_gme_run = current_time
                    self.state_manager.loop_stats['last_gme_run'] = current_time
                    self.state_manager.loop_stats['last_update'] = current_time
                    self.state_manager.loop_stats['next_gme_run'] = current_time + gme_interval
                    time_until_gme = gme_interval.total_seconds()
                    time_until_api_web = (last_api_web_run + api_web_interval - datetime.now()).total_seconds()
                    self.logger.debug(f"[GUI] GME completato. Prossima esecuzione tra {time_until_gme/60:.1f} minuti")
                elif not gme_enabled:
                    time_until_gme = 999999

                # Sleep intelligente
                next_wake = min(max(time_until_api_web, 0), max(time_until_realtime, 0), max(time_until_gme, 0), 5.0)
                if next_wake > 0:
                    await asyncio.sleep(next_wake)
                else:
                    await asyncio.sleep(0.1)

        except Exception as e:
            self.logger.error(f"[GUI] Errore nel loop: {e}")
            self.state_manager.loop_running = False
        finally:
            self.state_manager.loop_stats['status'] = 'stopped'
            self.state_manager.loop_mode = False
            self.logger.info("[GUI] Loop terminato")

    def _load_source_enabled_with_check(self, file_path: str, key: str) -> bool:
        """Verifica se source è enabled e ha endpoint attivi.

        Args:
            file_path: Path del file di configurazione
            key: Chiave della sorgente nel file

        Returns:
            True se source è enabled e ha almeno un endpoint attivo
        """
        try:
            if Path(file_path).exists():
                data = load_yaml(file_path, substitute_env=True, use_cache=True)
                source_enabled = data.get(key, {}).get('enabled', False)

                if source_enabled:
                    endpoints = data.get(key, {}).get('endpoints', {})
                    has_enabled = any(
                        ep.get('enabled', False)
                        for ep in endpoints.values()
                        if isinstance(ep, dict)
                    )

                    if not has_enabled:
                        self.logger.warning(f"[GUI] ⚠️ {key} è enabled ma non ha endpoint attivi - considerato disabilitato")
                        return False

                return source_enabled
        except Exception as e:
            self.logger.error(f"[GUI] Errore caricamento {file_path}: {e}")
        return False

    def _log_flow_configuration(self, api_enabled: bool, web_enabled: bool,
                                modbus_enabled: bool, gme_enabled: bool,
                                api_mins: int, web_mins: int,
                                realtime_secs: int, gme_mins: int):
        """Log configurazione dettagliata per ogni flow."""
        status_parts = []

        if api_enabled:
            status_parts.append(f"API: {api_mins} min")
        else:
            status_parts.append("API: DISABILITATO")

        if web_enabled:
            status_parts.append(f"Web: {web_mins} min")
        else:
            status_parts.append("Web: DISABILITATO")

        if modbus_enabled:
            status_parts.append(f"Realtime: {realtime_secs} sec")
        else:
            status_parts.append("Realtime: DISABILITATO")

        if gme_enabled:
            status_parts.append(f"GME: {gme_mins} min")
        else:
            status_parts.append("GME: DISABILITATO")

        self.logger.info(f"[GUI] Intervalli configurati - {', '.join(status_parts)}")

        # Log dettagliato per flow disabilitati
        if not api_enabled:
            self.logger.info("[GUI] ℹ️ API disabilitato nella configurazione, API flow non verrà eseguito")
        if not web_enabled:
            self.logger.info("[GUI] ℹ️ Web scraping disabilitato nella configurazione, Web flow non verrà eseguito")
        if not modbus_enabled:
            self.logger.info("[GUI] ℹ️ Modbus disabilitato nella configurazione, Realtime flow non verrà eseguito")
        if not gme_enabled:
            self.logger.info("[GUI] ℹ️ GME disabilitato nella configurazione, GME flow non verrà eseguito")

    async def _execute_api_web_flows(self, api_enabled: bool, web_enabled: bool,
                                     log, cache, config):
        """Esegue API e Web flows."""
        self.logger.info("[GUI] 🌐 Esecuzione raccolta API/Web...")

        if web_enabled:
            self.state_manager.start_new_run('web')
            self.state_manager.loop_stats['web_stats']['executed'] += 1
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, execute_flow, 'web', log, cache, config
                )
                self.state_manager.loop_stats['web_stats']['success'] += 1
                log.info("[FLOW:WEB:COMPLETION]✅ Raccolta web completata")
            except Exception as e:
                self.state_manager.loop_stats['web_stats']['failed'] += 1
                self.logger.error(f"[GUI] ❌ Errore raccolta web: {e}")

        if api_enabled:
            self.state_manager.start_new_run('api')
            self.state_manager.loop_stats['api_stats']['executed'] += 1
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, execute_flow, 'api', log, cache, config
                )
                self.state_manager.loop_stats['api_stats']['success'] += 1
                log.info("[FLOW:API:COMPLETION]✅ Raccolta API completata")
            except Exception as e:
                self.state_manager.loop_stats['api_stats']['failed'] += 1
                self.logger.error(f"[GUI] ❌ Errore raccolta API: {e}")

    async def _execute_realtime_flow(self, log, cache, config):
        """Esegue Realtime flow."""
        self.state_manager.start_new_run('realtime')
        self.state_manager.loop_stats['realtime_stats']['executed'] += 1
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, execute_flow, 'realtime', log, cache, config
            )
            if result == 0:
                self.state_manager.loop_stats['realtime_stats']['success'] += 1
                log.info("[FLOW:REALTIME:COMPLETION]✅ Raccolta realtime completata")
            else:
                self.state_manager.loop_stats['realtime_stats']['failed'] += 1
        except Exception as e:
            self.state_manager.loop_stats['realtime_stats']['failed'] += 1
            self.logger.error(f"[GUI] ❌ Errore raccolta realtime: {e}")

    async def _execute_gme_flow(self, log, cache, config, last_gme_run, gme_interval, time_until_gme):
        """Esegue GME flow."""
        self.logger.info(f"[GUI] 🔋 Esecuzione raccolta GME... (last_run: {last_gme_run}, interval: {gme_interval}, time_until: {time_until_gme:.1f}s)")
        self.state_manager.start_new_run('gme')
        self.state_manager.loop_stats['gme_stats']['executed'] += 1
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, execute_flow, 'gme', log, cache, config
            )
            self.state_manager.loop_stats['gme_stats']['success'] += 1
            log.info("[FLOW:GME:COMPLETION]✅ Raccolta GME completata")
        except Exception as e:
            self.state_manager.loop_stats['gme_stats']['failed'] += 1
            self.logger.error(f"[GUI] ❌ Errore raccolta GME: {e}")


__all__ = ['LoopExecutor']
