"""scheduler_loop.py
Modulo scheduler per gestione timing centralizzata delle chiamate.
Gestisce pause tra chiamate API, Web e Realtime con supporto cache hit.
"""

import time
import logging
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum


class SourceType(Enum):
    """Tipi di sorgenti dati supportate."""
    API = "api"
    WEB = "web"
    REALTIME = "realtime"


@dataclass(frozen=True)
class SchedulerConfig:
    """Configurazione timing per lo scheduler."""
    api_delay_seconds: float
    web_delay_seconds: float
    realtime_delay_seconds: float
    skip_delay_on_cache_hit: bool

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'SchedulerConfig':
        """Crea configurazione da dizionario config."""
        scheduler_config = config.get('scheduler', {})
        return cls(
            api_delay_seconds=float(scheduler_config.get('api_delay_seconds', 1.0)),
            web_delay_seconds=float(scheduler_config.get('web_delay_seconds', 2.0)),
            realtime_delay_seconds=float(scheduler_config.get('realtime_delay_seconds', 0.0)),
            skip_delay_on_cache_hit=bool(scheduler_config.get('skip_delay_on_cache_hit', True))
        )


class SchedulerLoop:
    """Scheduler centralizzato per gestione timing chiamate."""
    
    def __init__(self, config: SchedulerConfig):
        """Inizializza scheduler con configurazione.
        
        Args:
            config: Configurazione timing scheduler
        """
        self._config = config
        self._log = logging.getLogger(__name__)
        self._last_call_time: Dict[SourceType, float] = {}
        
        self._log.info(f"Scheduler inizializzato - API: {config.api_delay_seconds}s, "
                      f"Web: {config.web_delay_seconds}s, Realtime: {config.realtime_delay_seconds}s")
    
    def execute_with_timing(self, 
                           source_type: SourceType, 
                           operation: Callable[[], Any],
                           cache_hit: bool = False) -> Any:
        """Esegue operazione rispettando timing per il tipo di sorgente.
        
        Args:
            source_type: Tipo di sorgente (API, WEB, REALTIME)
            operation: Funzione da eseguire
            cache_hit: Se True e configurato, salta la pausa
            
        Returns:
            Risultato dell'operazione
        """
        # Calcola pausa necessaria
        delay_needed = self._calculate_delay(source_type, cache_hit)
        
        # Applica pausa se necessaria (interrompibile)
        if delay_needed > 0:
            self._log.debug(f"Pausa {delay_needed:.2f}s per {source_type.value}")
            # Sleep interrompibile per Ctrl+C più responsivo
            try:
                time.sleep(delay_needed)
            except KeyboardInterrupt:
                self._log.info("⚠️ Interruzione richiesta durante pausa scheduler")
                raise
        
        # Registra tempo chiamata
        self._last_call_time[source_type] = time.time()
        
        # Esegue operazione
        try:
            result = operation()
            self._log.debug(f"Operazione {source_type.value} completata")
            return result
        except Exception as e:
            self._log.error(f"Errore operazione {source_type.value}: {e}")
            raise
    
    def _calculate_delay(self, source_type: SourceType, cache_hit: bool) -> float:
        """Calcola pausa necessaria per il tipo di sorgente.
        
        Args:
            source_type: Tipo di sorgente
            cache_hit: Se è un cache hit
            
        Returns:
            Secondi di pausa necessari
        """
        # Se cache hit e configurato per saltare, nessuna pausa
        if cache_hit and self._config.skip_delay_on_cache_hit:
            return 0.0
        
        # Ottieni delay configurato per il tipo
        delay_config = {
            SourceType.API: self._config.api_delay_seconds,
            SourceType.WEB: self._config.web_delay_seconds,
            SourceType.REALTIME: self._config.realtime_delay_seconds
        }
        
        required_delay = delay_config.get(source_type, 0.0)
        
        # Se nessuna pausa configurata
        if required_delay <= 0:
            return 0.0
        
        # Calcola tempo trascorso dall'ultima chiamata
        last_call = self._last_call_time.get(source_type, 0)
        elapsed = time.time() - last_call
        
        # Calcola pausa rimanente
        remaining_delay = max(0.0, required_delay - elapsed)
        
        return remaining_delay
    
    def reset_timing(self, source_type: Optional[SourceType] = None) -> None:
        """Reset timing per tipo sorgente o tutti.
        
        Args:
            source_type: Tipo specifico da resettare, None per tutti
        """
        if source_type:
            self._last_call_time.pop(source_type, None)
            self._log.debug(f"Reset timing per {source_type.value}")
        else:
            self._last_call_time.clear()
            self._log.debug("Reset timing per tutte le sorgenti")
    
    def get_next_allowed_time(self, source_type: SourceType) -> float:
        """Ottiene timestamp della prossima chiamata consentita.
        
        Args:
            source_type: Tipo di sorgente
            
        Returns:
            Timestamp Unix della prossima chiamata consentita
        """
        delay_config = {
            SourceType.API: self._config.api_delay_seconds,
            SourceType.WEB: self._config.web_delay_seconds,
            SourceType.REALTIME: self._config.realtime_delay_seconds
        }
        
        required_delay = delay_config.get(source_type, 0.0)
        last_call = self._last_call_time.get(source_type, 0)
        
        return last_call + required_delay
    
    def run_forever(self):
        """Modalità loop continuo - da implementare in futuro."""
        raise NotImplementedError("Modalità loop continuo non ancora implementata")


__all__ = ["SchedulerLoop", "SchedulerConfig", "SourceType"]
