from typing import Dict, Any
from logging import Logger
from cache.cache_manager import CacheManager
from collector.collector_bolletta import CollectorBolletta
from utils.color_logger import color


def run_bolletta_flow(log: Logger, cache: CacheManager, config: Dict[str, Any]) -> int:
    """Pipeline bolletta: aggiorna bonus ARERA, indice GO e rete/oneri in InfluxDB (Bolletta)."""
    log.info("[FLOW:BOLLETTA:START]")
    log.info(color.bold('Avvio flusso bolletta (ARERA/GME)'))
    try:
        res = CollectorBolletta().collect()
        b, g, r = res['bonus'], res['go'], res['rete']
        log.info('   Bonus ARERA: %s (cambiato=%s)' % (b['values'], b['changed']))
        log.info('   Indice GO: %s EUR/kWh %s (cambiato=%s)' % (g['value'], g['month'], g['changed']))
        log.info('   Rete/oneri: net_var=%s net_fix=%s potenza=%s (cambiato=%s)'
                 % (r['net_var'], r['net_fix'], r['potenza_tariffa'], r['changed']))
        try:
            from flows import cusf_flow
            cusf_flow.ensure(log)
        except Exception as e:
            log.warning('CUsf SSP: aggiornamento saltato (%s)' % e)

        log.info('[FLOW:BOLLETTA:COMPLETION] Raccolta bolletta completata')
        return 0
    except Exception as e:
        log.error('Errore flusso bolletta: %s' % e)
        try:
            CollectorBolletta().write_stato(False, str(e))
        except Exception:
            pass
        return 1
