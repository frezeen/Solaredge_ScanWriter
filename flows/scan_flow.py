from logging import Logger

from typing import Any, Dict

def run_scan_flow(log: Logger, cache: Any, config: Dict[str, Any]) -> int:
    """Gestisce modalità scan per scansione web tree"""
    log.info("🔍 Modalità scan: scansione web tree")
    from tools.web_tree_scanner import WebTreeScanner
    from tools.yawl_manager import YawlManager

    scanner = WebTreeScanner()
    scanner.scan()

    # Aggiorna solo il file web_endpoints.yaml
    log.info("Aggiornando file web_endpoints.yaml...")
    ym = YawlManager()
    if ym.generate_web_endpoints_only():
        log.info("✅ File web_endpoints.yaml aggiornato")
    else:
        log.error("❌ Errore aggiornamento web_endpoints.yaml")
    return 0
