#!/usr/bin/env python3
"""
Loop Orchestrator - Gestione pipeline con dependency injection
"""

import asyncio
from datetime import datetime, timedelta
from typing import Protocol, Dict, Any
from dataclasses import dataclass, field
from app_logging.universal_logger import get_logger


class DataCollector(Protocol):
    """Interface per collectors"""
    async def collect(self) -> Dict[str, Any]:
        ...


class StatsTracker(Protocol):
    """Interface per tracking statistiche"""
    def update_stats(self, collector_type: str, success: bool):
        ...


@dataclass
class LoopConfig:
    """Configurazione immutabile del loop"""
    api_interval_minutes: int = 15
    web_interval_minutes: int = 15
    realtime_interval_seconds: int = 5


@dataclass
class LoopStats:
    """Statistiche del loop"""
    api_stats: Dict[str, int] = field(default_factory=lambda: {'executed': 0, 'success': 0, 'failed': 0})
    web_stats: Dict[str, int] = field(default_factory=lambda: {'executed': 0, 'success': 0, 'failed': 0})
    realtime_stats: Dict[str, int] = field(default_factory=lambda: {'executed': 0, 'success': 0, 'failed': 0})
    start_time: datetime = field(default_factory=datetime.now)
    status: str = 'stopped'


class LoopOrchestrator:
    """Orchestratore del loop - Dependency Injection"""
    
    def __init__(
        self,
        api_collector: DataCollector,
        web_collector: DataCollector,
        realtime_collector: DataCollector,
        config: LoopConfig,
        stats_tracker: StatsTracker
    ):
        self.api_collector = api_collector
        self.web_collector = web_collector
        self.realtime_collector = realtime_collector
        self.config = config
        self.stats_tracker = stats_tracker
        self.logger = get_logger("LoopOrchestrator")
        
        self.running = False
        self.stop_requested = False
        self.stats = LoopStats()

    async def start(self):
        """Avvia loop con pattern pipeline"""
        if self.running:
            self.logger.warning("Loop già in esecuzione")
            return

        self.running = True
        self.stop_requested = False
        self.stats.status = 'running'
        self.stats.start_time = datetime.now()
        
        self.logger.info("🚀 Loop orchestrator avviato")
        
        try:
            await self._run_loop()
        except Exception as e:
            self.logger.error(f"Errore nel loop: {e}")
        finally:
            self.running = False
            self.stats.status = 'stopped'

    async def _run_loop(self):
        """Loop principale con gestione intervalli"""
        last_api_web_run = datetime.min
        last_realtime_run = datetime.min
        
        api_web_interval = timedelta(minutes=max(self.config.api_interval_minutes, self.config.web_interval_minutes))
        realtime_interval = timedelta(seconds=self.config.realtime_interval_seconds)
        
        while self.running and not self.stop_requested:
            current_time = datetime.now()
            
            # Calcola tempo fino alla prossima operazione
            time_until_api_web = (last_api_web_run + api_web_interval - current_time).total_seconds()
            time_until_realtime = (last_realtime_run + realtime_interval - current_time).total_seconds()
            
            # Esegui API/Web collectors
            if time_until_api_web <= 0:
                await self._execute_collectors(['api', 'web'])
                last_api_web_run = current_time
                # Ricalcola tempi dopo l'esecuzione
                time_until_api_web = api_web_interval.total_seconds()
                time_until_realtime = (last_realtime_run + realtime_interval - datetime.now()).total_seconds()
            
            # Esegui Realtime collector
            if time_until_realtime <= 0:
                await self._execute_collectors(['realtime'])
                last_realtime_run = datetime.now()
                # Ricalcola tempo dopo l'esecuzione
                time_until_realtime = realtime_interval.total_seconds()
            
            # Sleep intelligente: dormi fino alla prossima operazione (max 5 secondi per responsività)
            # Questo riduce drasticamente l'utilizzo CPU quando non ci sono operazioni da fare
            next_wake = min(max(time_until_api_web, 0), max(time_until_realtime, 0), 5.0)
            if next_wake > 0:
                await asyncio.sleep(next_wake)
            else:
                # Pausa minima per evitare busy-wait
                await asyncio.sleep(0.1)

    async def _execute_collectors(self, collector_types: list[str]):
        """Esegue collectors specificati"""
        collectors = {
            'api': self.api_collector,
            'web': self.web_collector,
            'realtime': self.realtime_collector
        }
        
        for collector_type in collector_types:
            if collector_type in collectors:
                await self._execute_single_collector(collector_type, collectors[collector_type])

    async def _execute_single_collector(self, collector_type: str, collector: DataCollector):
        """Esegue singolo collector con error handling"""
        try:
            self.stats_tracker.update_stats(collector_type, True)  # executed++
            await collector.collect()
            self.stats_tracker.update_stats(collector_type, True)  # success++
            self.logger.debug(f"✅ {collector_type} collector completato")
        except Exception as e:
            self.stats_tracker.update_stats(collector_type, False)  # failed++
            self.logger.error(f"❌ Errore {collector_type} collector: {e}")

    def stop(self):
        """Ferma loop"""
        self.stop_requested = True
        self.logger.info("🛑 Stop richiesto per loop orchestrator")
