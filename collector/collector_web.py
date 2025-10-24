"""collector_web.py - OPTIMIZED
Collector web con login e riuso cookie ottimizzato.
Mantiene tutte le funzionalità ma con codice più pulito e intelligente.
"""
from __future__ import annotations
from typing import Any, Dict, List, Protocol, runtime_checkable, Optional, Tuple
import os, re, time, json, hashlib
import urllib.request, urllib.error
from pathlib import Path
import requests
from datetime import datetime
from collections import defaultdict
from app_logging import get_logger
from cache.cache_manager import CacheManager
from scheduler.scheduler_loop import SchedulerLoop, SourceType
from config.config_manager import get_config_manager

# Constants
SESSION_MIN_VALIDITY = 300
SESSION_MAX_AGE = 3600 * 6
OPTIMIZER_BATCH_SIZE = 5

@runtime_checkable
class CollectorWebInterface(Protocol):
    def ensure_session(self) -> None: ...
    def fetch_tree(self) -> Dict[str, Any]: ...
    def fetch_measurements(self, device_requests: List[Dict[str, Any]]) -> Dict[str, Any]: ...

class CollectorWeb(CollectorWebInterface):
    def __init__(self, scheduler: Optional[SchedulerLoop] = None) -> None:
        self._log = get_logger("collector.web")
        self._config_manager = get_config_manager()
        self._web_config = self._config_manager.get_solaredge_web_config()
        self._global_config = self._config_manager.get_global_config()
        self._validate_environment()
        self._init_session_state()
        self.cache = None
        self.scheduler = scheduler
        self.load_cookie_if_present()
    
    def _validate_environment(self) -> None:
        """Valida e carica variabili ambiente richieste."""
        required = {
            '_base_url': 'SOLAREDGE_WEB_BASE_URL',
            '_login_url': 'SOLAREDGE_LOGIN_URL',
            '_site_id': 'SOLAREDGE_SITE_ID'
        }
        
        for attr, env_var in required.items():
            value = os.environ.get(env_var)
            if not value:
                raise RuntimeError(f"Variabile ambiente {env_var} mancante")
            setattr(self, attr, value)
        
        # Valida site_id numerico
        if not self._site_id.strip().isdigit():
            raise RuntimeError(f"SOLAREDGE_SITE_ID non numerico: {self._site_id!r}")
        
        # Credenziali da configurazione
        self._username = self._web_config.username
        self._password = self._web_config.password
        self._cookie_path = self._web_config.cookie_file
    
    def _init_session_state(self) -> None:
        """Inizializza stato sessione."""
        self._cookie = None
        self._csrf_token = None
        self._last_login_ts = None
    
    def set_cache(self, cache: CacheManager) -> None:
        """Imposta cache manager."""
        self.cache = cache
    
    def set_target_date(self, target_date: str = None) -> None:
        """Imposta data target per le richieste web.
        
        Args:
            target_date: Data in formato YYYY-MM-DD, se None usa oggi
        """
        self._target_date = target_date

    # ========== Session Management ==========
    
    def ensure_session(self) -> None:
        """Garantisce sessione valida con strategia multi-livello."""
        # Fast path: cookie valido e recente
        if self._is_session_valid():
            return
        
        # Prova candidati esistenti
        if self._restore_session():
            return
            
        # Tenta login
        if self._attempt_login():
            return
            
        # Fallback: usa cookie esistente se disponibile
        if self._cookie and '=' in self._cookie:
            self._log.warning("Uso cookie non validato")
            return
            
        raise RuntimeError("Impossibile ottenere sessione valida")
    
    def _is_session_valid(self) -> bool:
        """Verifica se sessione corrente è valida."""
        return (
            bool(self._cookie) and 
            '=' in self._cookie and
            self._last_login_ts is not None and
            (time.time() - self._last_login_ts) < SESSION_MAX_AGE
        )
    
    def _restore_session(self) -> bool:
        """Tenta ripristino sessione da sorgenti esistenti."""
        for candidate in self._gather_candidates():
            if self._validate_candidate(candidate):
                return True
        return False
    
    def _gather_candidates(self) -> List[Dict[str, Any]]:
        """Raccoglie candidati cookie da tutte le sorgenti."""
        candidates = []
        
        # 1. Memoria corrente
        if self._cookie:
            candidates.append({
                'source': 'memory',
                'cookie': self._cookie,
                'csrf_token': self._csrf_token,
                'ts': self._last_login_ts or time.time()
            })
        
        # 2. Variabile ambiente
        if inline := os.environ.get('SOLAREDGE_COOKIE_INLINE'):
            candidates.append({
                'source': 'env',
                'cookie': inline,
                'csrf_token': None,
                'ts': time.time()
            })
        
        # 3. File cookie (primario e secondario)
        for label, path in self._get_cookie_paths():
            if data := self._read_cookie_file(Path(path)):
                if cookie_data := self._parse_cookie_data(data):
                    candidates.append({
                        'source': label,
                        **cookie_data
                    })
        
        return candidates
    
    def _get_cookie_paths(self) -> List[Tuple[str, str]]:
        """Restituisce percorsi cookie da verificare."""
        paths = [('primary', self._cookie_path)]
        if Path('tools/cookies').exists():
            paths.append(('secondary', 'tools/cookies/web_cookies.json'))
        return paths
    
    def _validate_candidate(self, candidate: Dict[str, Any]) -> bool:
        """Valida e applica candidato cookie."""
        cookie = candidate.get('cookie')
        if not cookie or '=' not in cookie:
            return False
        
        # Verifica età
        age = time.time() - (candidate.get('ts') or time.time())
        if age > SESSION_MAX_AGE * 1.5:
            return False
        
        # Salva stato corrente per rollback
        old_state = (self._cookie, self._csrf_token, self._last_login_ts)
        
        # Applica candidato
        self._cookie = self._normalize_cookie(cookie)
        self._csrf_token = candidate.get('csrf_token')
        self._last_login_ts = candidate.get('ts') or time.time()
        
        # Valida
        if self._validate_session():
            self._persist_cookie()
            return True
        
        # Rollback su fallimento
        self._cookie, self._csrf_token, self._last_login_ts = old_state
        return False
    
    def _validate_session(self) -> bool:
        """Validazione leggera sessione."""
        if not self._cookie:
            return False
            
        url = f"{self._base_url}/solaredge-web/p/site/{self._site_id}/"
        req = urllib.request.Request(url, headers={
            'cookie': self._cookie,
            'accept': 'text/html,*/*'
        })
        
        try:
            with urllib.request.urlopen(req, timeout=self._global_config.api_request_timeout) as resp:
                if resp.status != 200:
                    return False
                    
                # Verifica non sia pagina login
                content_type = resp.headers.get('content-type', '')
                if 'html' in content_type.lower():
                    body = resp.read(2048).decode('utf-8', errors='ignore').lower()
                    return not any(x in body for x in ('j_username', 'j_password', 'login'))
                    
                return True
        except Exception:
            return False
    
    def _attempt_login(self) -> bool:
        """Tenta login con credenziali."""
        if not (self._username and self._password):
            return False
        
        for attempt in range(1, 3):
            try:
                self._perform_login()
                if self._validate_session():
                    return True
            except Exception as e:
                if attempt == 2:
                    self._log.warning(f"Login fallito dopo {attempt} tentativi: {e}")
                time.sleep(attempt)
        
        return False
    
    def _perform_login(self) -> None:
        """Esegue login SolarEdge."""
        self._log.info("Esecuzione login SolarEdge...")
        
        session = requests.Session()
        session.headers.update({
            "User-Agent": "se-collector/1.0",
            "Accept": "*/*"
        })
        
        resp = session.post(
            self._login_url,
            data={"j_username": self._username, "j_password": self._password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self._global_config.api_request_timeout,
            allow_redirects=True
        )
        
        if resp.status_code != 200:
            raise RuntimeError(f"Login fallito: HTTP {resp.status_code}")
        
        # Estrai cookie e CSRF
        self._extract_session_data(session, resp)
        self._persist_cookie()
        self._log.info("Login completato%s", " (con CSRF)" if self._csrf_token else "")
    
    def _extract_session_data(self, session: requests.Session, response: requests.Response) -> None:
        """Estrae cookie e CSRF dalla sessione."""
        # Cookie
        cookies = []
        for cookie in session.cookies:
            if cookie.name and cookie.value:
                cookies.append(f"{cookie.name}={cookie.value}")
                if cookie.name in ("CSRF-TOKEN", "XSRF-TOKEN"):
                    self._csrf_token = cookie.value
        
        self._cookie = "; ".join(cookies)
        self._last_login_ts = time.time()
        
        # CSRF da HTML se non già estratto
        if not self._csrf_token:
            self._extract_csrf_from_html(response.text)
    
    def _extract_csrf_from_html(self, html: str) -> None:
        """Estrae CSRF token da HTML."""
        patterns = [
            r'name=["\']csrf-token["\']\s+content=["\']([^"\']+)',
            r'csrfToken\s*=\s*"([^"]+)'
        ]
        
        for pattern in patterns:
            if match := re.search(pattern, html, re.IGNORECASE):
                self._csrf_token = match.group(1)
                break

    # ========== Cookie Management ==========
    
    def load_cookie_if_present(self) -> None:
        """Carica cookie da file se presente."""
        if data := self._read_cookie_file(Path(self._cookie_path)):
            if parsed := self._parse_cookie_data(data):
                self._cookie = parsed.get('cookie')
                self._csrf_token = parsed.get('csrf_token')
                self._last_login_ts = parsed.get('ts') or time.time()
    
    def _read_cookie_file(self, path: Path) -> Dict[str, Any] | List | None:
        """Legge file cookie."""
        if not path.exists():
            return None
            
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            return None
    
    def _parse_cookie_data(self, data: Any) -> Dict[str, Any] | None:
        """Parsa dati cookie da vari formati."""
        if isinstance(data, dict):
            # Formato standard
            if cookie := data.get('cookie'):
                return {
                    'cookie': cookie,
                    'csrf_token': data.get('csrf_token'),
                    'ts': data.get('last_login_ts')
                }
            
            # Formato con lista cookies
            if cookies := data.get('cookies'):
                if cookie_str := self._build_cookie_string(cookies):
                    return {
                        'cookie': cookie_str,
                        'csrf_token': data.get('csrf_token'),
                        'ts': data.get('last_login_ts')
                    }
        
        elif isinstance(data, list):
            # Lista pura di cookie
            if cookie_str := self._build_cookie_string(data):
                return {'cookie': cookie_str, 'csrf_token': None, 'ts': None}
        
        return None
    
    def _build_cookie_string(self, cookies: List) -> str | None:
        """Costruisce stringa cookie da lista."""
        parts = []
        for cookie in cookies:
            if isinstance(cookie, dict) and (name := cookie.get('name')) and (value := cookie.get('value')):
                parts.append(f"{name}={value}")
        return "; ".join(parts) if parts else None
    
    def _normalize_cookie(self, raw: str) -> str:
        """Normalizza stringa cookie."""
        cookies = {}
        for part in raw.split(';'):
            if '=' not in part:
                continue
            key, value = part.strip().split('=', 1)
            if key.lower() not in ('path', 'domain', 'expires', 'secure', 'httponly', 'samesite'):
                cookies[key] = value
        return '; '.join(f"{k}={cookies[k]}" for k in sorted(cookies))
    
    def _persist_cookie(self) -> None:
        """Salva cookie su file."""
        path = Path(self._cookie_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "cookie": self._cookie,
            "last_login_ts": self._last_login_ts,
            "csrf_token": self._csrf_token
        }
        
        path.write_text(json.dumps(data, indent=2), encoding='utf-8')

    # ========== Data Fetching ==========
    
    def fetch_tree(self) -> Dict[str, Any]:
        """Recupera struttura tree."""
        def _fetch():
            self.ensure_session()
            return self._make_tree_request()
        
        if self.cache:
            date = datetime.now().strftime("%Y-%m-%d")
            return self.cache.get_or_fetch("web", "tree", date, _fetch)
        return _fetch()
    
    def _make_tree_request(self) -> Dict[str, Any]:
        """Esegue richiesta tree."""
        url = f"{self._base_url}/services/charts/site/{self._site_id}/tree"
        headers = self._build_headers()
        
        req = urllib.request.Request(url, headers=headers, method="GET")
        
        try:
            with urllib.request.urlopen(req, timeout=self._global_config.api_request_timeout) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Tree status {resp.status}")
                    
                data = json.loads(resp.read().decode('utf-8'))
                if not isinstance(data, dict) or not data:
                    raise RuntimeError("Tree vuoto o invalido")
                    
                return data
                
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                self._log.warning("Sessione scaduta, re-login...")
                self._init_session_state()
                self.ensure_session()
                return self._make_tree_request()
            raise
    
    def fetch_measurements(self, device_requests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Recupera measurements."""
        if not device_requests:
            raise RuntimeError("device_requests vuoto")
        
        def _fetch():
            self.ensure_session()
            return self._fetch_all_measurements(device_requests)
        
        if self.cache:
            # Usa target_date se impostata, altrimenti oggi
            date = getattr(self, '_target_date', None) or datetime.now().strftime("%Y-%m-%d")
            key = self._generate_cache_key(device_requests, date)
            return self.cache.get_or_fetch("web", key, date, _fetch)
        return _fetch()
    
    def fetch_measurements_for_date(self, device_requests: List[Dict[str, Any]], target_date: str) -> Dict[str, Any]:
        """Recupera measurements per una data specifica.
        
        Args:
            device_requests: Lista delle richieste dispositivi
            target_date: Data in formato YYYY-MM-DD
        """
        # Imposta temporaneamente la data target
        old_date = getattr(self, '_target_date', None)
        self.set_target_date(target_date)
        
        try:
            return self.fetch_measurements(device_requests)
        finally:
            # Ripristina la data precedente
            self.set_target_date(old_date)
    
    def _fetch_all_measurements(self, requests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Recupera tutti i measurements."""
        # Raggruppa per tipo
        grouped = defaultdict(list)
        for req in requests:
            device_type = req.get('device', {}).get('itemType', 'GENERIC')
            grouped[device_type].append(req)
        
        self._log.info(f"Grouped into {len(grouped)} types: {list(grouped.keys())}")
        
        # Fetch per gruppo
        results = []
        for device_type, group in grouped.items():
            if device_type == 'OPTIMIZER' and len(group) > OPTIMIZER_BATCH_SIZE:
                results.extend(self._fetch_optimizer_batches(group))
            else:
                results.extend(self._fetch_batch(device_type, group))
        
        return {"list": results}
    
    def _fetch_optimizer_batches(self, requests: List[Dict[str, Any]]) -> List:
        """Gestisce optimizer in batch."""
        results = []
        for i in range(0, len(requests), OPTIMIZER_BATCH_SIZE):
            batch = requests[i:i + OPTIMIZER_BATCH_SIZE]
            self._log.info(f"OPTIMIZER batch {i//OPTIMIZER_BATCH_SIZE + 1}: {len(batch)} devices")
            results.extend(self._fetch_batch('OPTIMIZER', batch))
        return results
    
    def _fetch_batch(self, device_type: str, batch: List[Dict[str, Any]]) -> List:
        """Fetch singolo batch con scheduler timing."""
        self._log.info(f"Fetching {len(batch)} {device_type} devices...")
        
        def _http_call():
            url = f"{self._base_url}/services/charts/site/{self._site_id}/devices-measurements"
            params = self._get_date_params(getattr(self, '_target_date', None))
            headers = self._build_headers(json_content=True)
            
            session = self._create_session()
            
            try:
                resp = session.post(url, params=params, headers=headers, json=batch, timeout=self._global_config.batch_request_timeout)
                
                if resp.status_code != 200:
                    raise RuntimeError(f"HTTP {resp.status_code} for {device_type}")
                
                data = resp.json()
                results = data if isinstance(data, list) else data.get('list', [data])
                
                self._log.info(f"Success for {device_type}: {len(results)} items")
                return results
                
            except Exception as e:
                self._log.error(f"Failed for {device_type}: {e}")
                raise RuntimeError(f"Request failed for {device_type}") from e
        
        # Usa scheduler se disponibile, altrimenti chiamata diretta
        if self.scheduler:
            return self.scheduler.execute_with_timing(SourceType.WEB, _http_call, cache_hit=False)
        else:
            return _http_call()
    
    def _build_headers(self, json_content: bool = False) -> Dict[str, str]:
        """Costruisce headers richiesta."""
        headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (compatible; se-scanner/0.1)",
            "Cookie": self._cookie or "",
            "Referer": f"{self._base_url}/solaredge-web/p/site/{self._site_id}/",
            "Origin": self._base_url,
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.8"
        }
        
        if json_content:
            headers["Content-Type"] = "application/json;charset=UTF-8"
        
        if self._csrf_token:
            headers["X-CSRF-TOKEN"] = self._csrf_token
        
        return headers
    
    def _create_session(self) -> requests.Session:
        """Crea sessione con cookie."""
        session = requests.Session()
        
        if self._cookie:
            for part in self._cookie.split(';'):
                if '=' in part:
                    name, value = part.strip().split('=', 1)
                    session.cookies.set(name, value, domain='monitoring.solaredge.com')
        
        return session
    
    def _get_date_params(self, target_date: str = None) -> Dict[str, str]:
        """Parametri data per oggi o data specifica.
        
        Args:
            target_date: Data specifica in formato YYYY-MM-DD, se None usa oggi
        """
        if target_date:
            # Usa la data specifica fornita
            return {"start-date": target_date, "end-date": target_date}
        
        # Comportamento originale per oggi
        try:
            from zoneinfo import ZoneInfo
            tz = os.environ.get('TIMEZONE', os.environ.get('TZ', 'Europe/Rome'))
            today = datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%d")
        except Exception:
            today = datetime.now().strftime("%Y-%m-%d")
        
        return {"start-date": today, "end-date": today}
    
    def _generate_cache_key(self, requests: List[Dict[str, Any]], date: str) -> str:
        """Genera chiave cache."""
        hash_val = hashlib.md5(
            json.dumps(requests, sort_keys=True).encode()
        ).hexdigest()[:8]
        return f"measurements_{hash_val}_{date}"

    # ========== Config-based Requests ==========
    
    def build_requests_from_config(self, config_path: str = "config/main.yaml") -> List[Dict[str, Any]]:
        """Costruisce richieste da configurazione."""
        config = self._config_manager.get_raw_config()
        endpoints = (config.get('sources', {})
                          .get('web_scraping', {})
                          .get('endpoints', {}))
        
        requests = []
        for device_id, device_config in endpoints.items():
            if not self._is_device_enabled(device_config):
                continue
                
            if metrics := self._get_enabled_metrics(device_config):
                requests.append(self._build_request(device_id, device_config, metrics))
        
        return requests
    
    def _is_device_enabled(self, config: Any) -> bool:
        """Verifica se device è abilitato."""
        return isinstance(config, dict) and config.get('enabled', False)
    
    def _get_enabled_metrics(self, config: Dict[str, Any]) -> List[str]:
        """Estrae metriche abilitate."""
        metrics = []
        for name, cfg in config.get('measurements', {}).items():
            if isinstance(cfg, dict) and cfg.get('enabled', False):
                metrics.append(name)
        return metrics
    
    def _build_request(self, device_id: str, config: Dict[str, Any], metrics: List[str]) -> Dict[str, Any]:
        """Costruisce singola richiesta."""
        device_type = config.get('device_type', 'GENERIC').upper()
        
        # Device payload
        device = {"itemType": device_type}
        
        if device_type != 'WEATHER':
            real_id = config.get('device_id', device_id)
            real_id_str = str(real_id)  # Converti sempre in stringa
            device.update({
                "id": real_id,
                "originalSerial": real_id,
                "identifier": real_id_str.split("-")[0] if "-" in real_id_str else real_id_str
            })
            
            # Aggiungi inverter per STRING
            if device_type == 'STRING' and (inv := config.get('inverter')):
                device["connectedToInverter"] = inv
        
        return {
            "device": device,
            "deviceName": config.get('device_name', f'Device {device_id}'),
            "measurementTypes": metrics
        }
    
    # Alias per compatibilità
    build_requests_with_real_ids = build_requests_from_config

__all__ = ["CollectorWeb", "CollectorWebInterface"]