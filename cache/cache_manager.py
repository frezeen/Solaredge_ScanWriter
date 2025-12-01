#!/usr/bin/env python3
"""
Cache Manager - Gestore cache intelligente con TTL configurabile e compressione
Struttura: cache/{source}/{endpoint}/{date}_{hash}.json.gz

Caratteristiche:
- Cache infinita per api_ufficiali e web
- Solo file compressi .json.gz
- Hash nei nomi file per evitare riscritture inutili
- Logging universale tramite app_logging
"""

import json
import gzip
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable
from app_logging import get_logger

# COSTANTI ESTRATTE (REGOLA #7)
HASH_LENGTH = 8
CACHE_KEY_LENGTH = 16
FILE_EXTENSION = '.json.gz'
DATE_PATTERN = '%Y-%m-%d'
ENCODING = 'utf-8'

class CacheManager:
    """Gestore cache centralizzato con supporto per diversi tipi di sorgenti e compressione."""
    
    # COSTANTI DI CLASSE (REGOLA #7) - TTL in minuti
    TTL_CONFIG = {
        'api_ufficiali': 15,    # API ufficiali: 15 minuti, poi hash check
        'web': 15,              # Web scraping: 15 minuti, poi hash check
        'gme': 1440             # GME: 24 ore (dati giornalieri)
    }

    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self._log = get_logger("cache_manager")
        # Eliminata ridondanza: solo self._log (REGOLA #0)
        
        # Statistics counters
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'sealed_saves': 0,
            'partial_saves': 0
        }

    def get_cache_key(self, source: str, endpoint: str, date: str) -> str:
        """Genera chiave cache univoca."""
        return hashlib.md5(f"{source}_{endpoint}_{date}".encode()).hexdigest()[:CACHE_KEY_LENGTH]
    
    def get_statistics(self) -> Dict[str, int]:
        """Restituisce statistiche sull'utilizzo della cache."""
        return self.stats.copy()
    
    def reset_statistics(self) -> None:
        """Resetta i contatori delle statistiche."""
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'sealed_saves': 0,
            'partial_saves': 0
        }
    
    def get_data_hash(self, data: Dict[str, Any]) -> str:
        """Genera hash dei dati per rilevare cambiamenti."""
        return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()[:HASH_LENGTH]
    
    def _extract_time_from_filename(self, file_path: Path) -> Optional[datetime]:
        """Estrae l'orario dal nome del file cache."""
        try:
            # Formato: 2025-10-03_14-32.json.gz o 2025-11_14-32_a3f5b2c8.json.gz
            filename = file_path.stem.replace('.json', '')  # Rimuove .json da .json.gz
            if '_' not in filename:
                return None
            
            parts = filename.split('_')
            date_part = parts[0]
            time_part = parts[1] if len(parts) > 1 else None
            
            if not time_part:
                return None
            
            # Rimuovi hash se presente (es. 14-32 da 14-32 o da array con hash)
            time_str = time_part.replace('-', ':')  # 14-32 → 14:32
            
            # Combina data e ora
            datetime_str = f"{date_part} {time_str}:00"  # Aggiungi secondi
            return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
        except (ValueError, AttributeError):
            return None

    def _build_cache_path(self, source: str, endpoint: str, date: str, time_str: str = None, data_hash: str = None) -> Path:
        """Costruisce path cache con orario e opzionalmente hash nel nome."""
        if time_str:
            if data_hash:
                filename = f"{date}_{time_str}_{data_hash}{FILE_EXTENSION}"
            else:
                filename = f"{date}_{time_str}{FILE_EXTENSION}"
        else:
            # Usa orario attuale se non specificato
            time_str = datetime.now().strftime('%H-%M')
            if data_hash:
                filename = f"{date}_{time_str}_{data_hash}{FILE_EXTENSION}"
            else:
                filename = f"{date}_{time_str}{FILE_EXTENSION}"
        return self.cache_dir / source / endpoint / filename
    


    def _validate_cache_file(self, cache_path: Path) -> Optional[Dict[str, Any]]:
        """Valida esistenza e lettura file cache."""
        if not cache_path.exists():
            return None
        
        try:
            with gzip.open(cache_path, 'rt', encoding=ENCODING) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, KeyError, gzip.BadGzipFile):
            return None
    
    def _validate_cache_age_from_filename(self, file_path: Path, source: str = None, target_date: str = None) -> bool:
        """Valida età cache basata sull'orario nel nome del file."""
        try:
            file_timestamp = self._extract_time_from_filename(file_path)
            if not file_timestamp:
                return False
            
            # Per dati storici (history mode), la cache è sempre valida
            if target_date:
                # Supporta sia YYYY-MM-DD che YYYY-MM
                if len(target_date) == 7 and target_date.count('-') == 1:
                    # Formato mensile: considera il primo giorno del mese
                    target_dt = datetime.strptime(target_date + '-01', '%Y-%m-%d').date()
                else:
                    target_dt = datetime.strptime(target_date, '%Y-%m-%d').date()
                    
                today = datetime.now().date()
                
                # Se stiamo richiedendo dati del passato, la cache è sempre valida
                if target_dt < today:
                    return True
            
            # Per dati di oggi, usa il controllo TTL normale
            cache_age = datetime.now() - file_timestamp
            
            # WALRUS OPERATOR per TTL configurabile (REGOLA #3)
            if source and (ttl_minutes := self.TTL_CONFIG.get(source)) is not None:
                return cache_age < timedelta(minutes=ttl_minutes)
            
            return True
        except (ValueError, AttributeError):
            return False
    
    def is_cache_valid(self, cache_path: Path, source: str = None, target_date: str = None) -> bool:
        """Verifica validità cache usando validazione basata su nome file."""
        if not cache_path.exists():
            return False
        return self._validate_cache_age_from_filename(cache_path, source, target_date)

    def _find_latest_cache_file(self, source: str, endpoint: str, date: str) -> Optional[Path]:
        """Trova il file cache per una data, prioritizzando file con hash (sigillo qualità)."""
        endpoint_dir = self.cache_dir / source / endpoint
        if not endpoint_dir.exists():
            return None
        
        # Prima cerca file CON hash (completi)
        pattern_with_hash = f"{date}_*_*{FILE_EXTENSION}"
        files_with_hash = list(endpoint_dir.glob(pattern_with_hash))
        
        if files_with_hash:
            # Trovato file con sigillo qualità - priorità massima
            return max(files_with_hash, key=lambda p: p.name)
        
        # Altrimenti cerca file SENZA hash (parziali)
        pattern_without_hash = f"{date}_*{FILE_EXTENSION}"
        files_without_hash = [f for f in endpoint_dir.glob(pattern_without_hash) 
                              if len(f.stem.split('_')) == 2]  # Solo 2 parti: date_time
        
        return max(files_without_hash, key=lambda p: p.name) if files_without_hash else None
    
    def get_cached_data(self, source: str, endpoint: str, date: str, time_str: str = None, ignore_ttl: bool = False) -> Optional[Dict[str, Any]]:
        """Recupera dati dalla cache se valida
        
        Args:
            ignore_ttl: Se True, ignora il TTL e restituisce cache anche se scaduta
        """
        # WALRUS OPERATOR per determinazione path (REGOLA #3)
        if time_str:
            cache_path = self._build_cache_path(source, endpoint, date, time_str)
        elif not (cache_path := self._find_latest_cache_file(source, endpoint, date)):
            return None
        
        # VALIDATION CHAIN riutilizzata (REGOLA #2)
        if not (cache_data := self._validate_cache_file(cache_path)):
            return None
        
        # Usa validazione basata su nome file con supporto per dati storici
        # Se ignore_ttl=True, salta il check TTL (per merge operations)
        if not ignore_ttl and not self._validate_cache_age_from_filename(cache_path, source, date):
            return None
        
        self._log.info(f"✅ CACHE HIT [{source}]: {self.get_cache_key(source, endpoint, date)} ({date})")
        self.stats['cache_hits'] += 1
        return cache_data['data']

    def _build_cache_entry(self, source: str, endpoint: str, date: str, data: Dict[str, Any], data_hash: str) -> Dict[str, Any]:
        """Costruisce entry cache semplificata (solo dati)."""
        return {
            'data': data,
            'source': source,
            'endpoint': endpoint,
            'date': date,
            'data_hash': data_hash
        }
    
    def _parse_date_value(self, value: Any) -> Optional[str]:
        """Estrae una data YYYY-MM-DD da vari formati (stringa, timestamp)."""
        try:
            if isinstance(value, str):
                # Gestione stringhe: "2024-06-01", "2024-06-01 12:00:00", ISO format
                if len(value) >= 10 and value[4] == '-' and value[7] == '-':
                    return value[:10]
            elif isinstance(value, (int, float)):
                # Gestione timestamp (secondi o millisecondi)
                # Se > 3e10 (anno 2920), probabilmente sono millisecondi
                ts = value / 1000 if value > 3e10 else value
                # Filtro timestamp non validi (es. 0 o troppo piccoli)
                if ts > 946684800:  # > 2000-01-01
                    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
        except Exception:
            pass
        return None

    def _extract_dates_recursively(self, data: Any, target_month: str, found_days: set) -> None:
        """
        Attraversa ricorsivamente il JSON cercando date che matchano il mese target.
        Popola il set found_days in-place.
        """
        if isinstance(data, dict):
            for key, value in data.items():
                # Se la chiave suggerisce una data/tempo, prova a parsare il valore
                if key in ('date', 'time', 'timeStamp', 'timestamp', 'lastUpdated', 'date_time'):
                    if date_str := self._parse_date_value(value):
                        if date_str.startswith(target_month):
                            found_days.add(date_str)
                
                # Ricorsione su dizionari e liste
                if isinstance(value, (dict, list)):
                    self._extract_dates_recursively(value, target_month, found_days)
                    
        elif isinstance(data, list):
            for item in data:
                self._extract_dates_recursively(item, target_month, found_days)

    def _has_full_month_data(self, data: Dict[str, Any], month_key: str) -> bool:
        """
        Verifica universale se i dati coprono tutti i giorni del mese.
        Usa scansione ricorsiva per trovare date.
        
        Logica Time-Series:
        - Se trova tutti i giorni del mese -> SEALED (True)
        - Se NON trova date (0 giorni) -> PARTIAL (False) (Assume dati mancanti/errore)
        - Se trova alcuni giorni ma non tutti -> PARTIAL (False)
        """
        import calendar
        try:
            year, month = map(int, month_key.split('-'))
            days_in_month = calendar.monthrange(year, month)[1]
            
            unique_days = set()
            self._extract_dates_recursively(data, month_key, unique_days)
            
            num_found = len(unique_days)
            
            # Logica di decisione
            if num_found == days_in_month:
                self._log.debug(f"✅ Dati completi per {month_key}: {num_found}/{days_in_month} giorni")
                return True
            elif num_found == 0:
                # Nessuna data trovata per time-series: probabilmente errore o dati mancanti
                # NON sigilliamo, così riproverà
                self._log.debug(f"⚠️ Nessuna data trovata per {month_key} (Time-Series) -> PARTIAL")
                return False
            else:
                self._log.debug(f"⚠️ Dati parziali per {month_key}: {num_found}/{days_in_month} giorni")
                return False
                
        except Exception as e:
            self._log.warning(f"Errore validazione completezza dati: {e}")
            return False

    def save_to_cache(self, source: str, endpoint: str, date: str, data: Dict[str, Any], data_hash: str = None, is_metadata: bool = False) -> str:
        """Salva dati in cache con orario e hash (se completo) nel nome."""
        # WALRUS OPERATOR per hash generation (REGOLA #3)
        if not (data_hash := data_hash or self.get_data_hash(data)):
            raise ValueError("Impossibile generare hash dei dati")
        
        # Verifica se i dati sono completi
        is_complete = False
        
        # Dati giornalieri (YYYY-MM-DD): sempre completi per definizione
        if len(date) == 10 and date.count('-') == 2:
            is_complete = True
            self._log.debug(f"✅ Dati giornalieri validi per {date} -> SEALED")
        # Dati mensili (YYYY-MM): verifica completezza
        elif len(date) == 7 and '-' in date:
            if is_metadata:
                is_complete = True
                self._log.debug(f"✅ Dati metadata validi per {date} -> SEALED")
            else:
                is_complete = self._has_full_month_data(data, date)
        
        # Rimuovi il vecchio file se esiste (per rinominare con nuovo orario/hash)
        old_file = self._find_latest_cache_file(source, endpoint, date)
        if old_file and old_file.exists():
            old_file.unlink()
        
        # Crea nuovo file con orario attuale e hash se completo
        current_time = datetime.now().strftime('%H-%M')
        quality_hash = data_hash if is_complete else None
        cache_path = self._build_cache_path(source, endpoint, date, current_time, quality_hash)
        
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_entry = self._build_cache_entry(source, endpoint, date, data, data_hash)

        try:
            with gzip.open(cache_path, 'wt', encoding=ENCODING) as f:
                json.dump(cache_entry, f, indent=2, ensure_ascii=False)

            seal_status = "🔒 SEALED" if is_complete else "📝 PARTIAL"
            self._log.info(f"💾 CACHE SAVED [{source}] {seal_status}: {data_hash} ({date})")
            
            # Update statistics
            if is_complete:
                self.stats['sealed_saves'] += 1
            else:
                self.stats['partial_saves'] += 1
                
            return data_hash

        except Exception as e:
            self._log.error(f"Cache save failed {cache_path}: {e}")
            raise RuntimeError(f"Cache save failed for {date}") from e

    def _update_cache_with_new_time(self, source: str, endpoint: str, date: str, data: Dict[str, Any], data_hash: str) -> None:
        """Aggiorna il file cache con nuovo orario nel nome."""
        # Rimuovi il vecchio file
        old_file = self._find_latest_cache_file(source, endpoint, date)
        if old_file and old_file.exists():
            old_file.unlink()
        
        # Salva con nuovo orario
        self.save_to_cache(source, endpoint, date, data, data_hash)
        self._log.info(f"🔄 TIMESTAMP UPDATED [{source}]: {data_hash} ({date})")

    def _check_hash_and_refresh(self, source: str, endpoint: str, date: str, fetch_func: Callable, cached_data: Dict[str, Any]) -> Dict[str, Any]:
        """Confronta hash e aggiorna se necessario."""
        cache_key = self.get_cache_key(source, endpoint, date)
        
        try:
            self._log.info(f"🌐 API CALL (hash check) [{source}/{endpoint}]: {date}")
            fresh_data = fetch_func()
            fresh_hash = self.get_data_hash(fresh_data)
            cached_hash = self.get_data_hash(cached_data)
            
            # Confronta hash dei dati
            if fresh_hash != cached_hash:
                self._log.info(f"🔄 HASH CHANGED [{source}]: {cache_key} ({date})")
                self.save_to_cache(source, endpoint, date, fresh_data, fresh_hash)
                return fresh_data
            
            self._log.info(f"✅ HASH MATCH [{source}]: {cache_key} ({date})")
            # Aggiorna l'orario nel nome del file anche se i dati non sono cambiati
            self._update_cache_with_new_time(source, endpoint, date, cached_data, fresh_hash)
            return cached_data
                
        except Exception as e:
            self._log.error(f"Hash check failed {cache_key}: {e}")
            fresh_data = fetch_func()
            self.save_to_cache(source, endpoint, date, fresh_data)
            return fresh_data
    
    def get_or_fetch(self, source: str, endpoint: str, date: str, fetch_func: Callable, is_metadata: bool = False) -> Dict[str, Any]:
        """Ottieni da cache con logica intelligente per tipo sorgente (REGOLA #4)."""
        cache_key = self.get_cache_key(source, endpoint, date)
        
        try:
            # Prima controlla se esiste un file cache (valido o scaduto)
            cache_path = self._find_latest_cache_file(source, endpoint, date)
            if cache_path and (cache_entry := self._validate_cache_file(cache_path)):
                
                # Controlla se la cache è ancora valida usando nome file + data target
                if self._validate_cache_age_from_filename(cache_path, source, date):
                    # CACHE HIT DIRETTO - nessuna chiamata API
                    self._log.info(f"✅ CACHE HIT [{source}/{endpoint}]: {date}")
                    self.stats['cache_hits'] += 1
                    return cache_entry['data']
                
                # Cache scaduto (> 15 min): hash check per web/api (solo per dati di oggi)
                elif source in ['web', 'api_ufficiali']:
                    # Supporta sia YYYY-MM-DD che YYYY-MM
                    if len(date) == 7 and date.count('-') == 1:
                        # Formato mensile: considera il primo giorno del mese
                        target_dt = datetime.strptime(date + '-01', '%Y-%m-%d').date()
                    else:
                        target_dt = datetime.strptime(date, '%Y-%m-%d').date()
                        
                    today = datetime.now().date()
                    
                    # Per dati storici, usa sempre la cache senza hash check
                    if target_dt < today:
                        self._log.info(f"📚 HISTORICAL CACHE HIT [{source}/{endpoint}]: {date}")
                        return cache_entry['data']
                    
                    # Per dati di oggi, fai hash check
                    self._log.info(f"⏰ CACHE EXPIRED (>15min) [{source}/{endpoint}]: {date}")
                    return self._check_hash_and_refresh(source, endpoint, date, fetch_func, cache_entry['data'])
            
            # Cache miss completo - nessun file trovato
            self._log.info(f"🌐 API CALL [{source}/{endpoint}]: {date}")
            self.stats['cache_misses'] += 1
            fresh_data = fetch_func()
            self.save_to_cache(source, endpoint, date, fresh_data, is_metadata=is_metadata)
            return fresh_data
            
        except Exception as e:
            self._log.error(f"Cache operation failed {cache_key}: {e}")
            raise RuntimeError(f"Cache operation failed for {cache_key}") from e

    def _clear_files_in_path(self, path: Path, pattern: str = f"*{FILE_EXTENSION}") -> int:
        """Helper per cancellazione file con pattern (REGOLA #9)."""
        if not path.exists():
            return 0
        
        # COMPREHENSION per file deletion (REGOLA #6)
        files_to_delete = list(path.rglob(pattern) if pattern.startswith('*') else path.glob(pattern))
        for file_path in files_to_delete:
            file_path.unlink()
        return len(files_to_delete)
    
    def clear_cache(self, source: str = None, endpoint: str = None, date: str = None):
        """Pulisce cache usando pattern intelligenti."""
        if source and endpoint and date:
            # Cancella file specifici per data
            endpoint_dir = self.cache_dir / source / endpoint
            count = self._clear_files_in_path(endpoint_dir, f"{date}_*{FILE_EXTENSION}")
            self._log.info(f"🗑️ CACHE CLEARED: {source}/{endpoint} ({date}) - {count} files")
        elif source and endpoint:
            # Cancella endpoint completo
            endpoint_dir = self.cache_dir / source / endpoint
            count = self._clear_files_in_path(endpoint_dir)
            self._log.info(f"🗑️ CACHE CLEARED: {source}/{endpoint} - {count} files")
        elif source:
            # Cancella sorgente completa
            source_dir = self.cache_dir / source
            count = self._clear_files_in_path(source_dir)
            self._log.info(f"🗑️ CACHE CLEARED: {source} - {count} files")
        else:
            # Cancella tutta la cache
            count = self._clear_files_in_path(self.cache_dir)
            self._log.info(f"🗑️ CACHE CLEARED: All cache - {count} files")

    def _process_cache_file_stats(self, file_path: Path, stats: Dict[str, Any]):
        """Processa statistiche per singolo file cache (REGOLA #9)."""
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        stats['total_files'] += 1
        stats['total_size_mb'] += file_size_mb

        # WALRUS OPERATOR per source extraction (REGOLA #3)
        if (parts := file_path.relative_to(self.cache_dir).parts) and len(parts) >= 2:
            source = parts[0]
            stats['sources'].setdefault(source, {'files': 0, 'size_mb': 0})
            stats['sources'][source]['files'] += 1
            stats['sources'][source]['size_mb'] += file_size_mb

        # WALRUS OPERATOR per timestamp processing (REGOLA #3)
        if (cache_data := self._validate_cache_file(file_path)) and \
           (timestamp_str := cache_data.get('timestamp')):
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
                if not stats['oldest_file'] or timestamp < stats['oldest_file'][1]:
                    stats['oldest_file'] = (str(file_path), timestamp)
                if not stats['newest_file'] or timestamp > stats['newest_file'][1]:
                    stats['newest_file'] = (str(file_path), timestamp)
            except ValueError:
                pass
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Restituisce statistiche cache usando pattern ottimizzati."""
        stats = {
            'total_files': 0,
            'total_size_mb': 0,
            'sources': {},
            'oldest_file': None,
            'newest_file': None
        }

        # COMPREHENSION per file processing (REGOLA #6)
        cache_files = list(self.cache_dir.rglob(f"*{FILE_EXTENSION}"))
        for file_path in cache_files:
            self._process_cache_file_stats(file_path, stats)

        return stats


    
    def cache_exists_for_date(self, source: str, endpoint: str, date: str, ignore_ttl: bool = False) -> bool:
        """Verifica se esiste cache per una data specifica.
        
        Args:
            source: Sorgente dati (es. 'api_ufficiali')
            endpoint: Nome endpoint
            date: Data in formato YYYY-MM-DD
            ignore_ttl: Se True, ignora il TTL e verifica solo l'esistenza del file
            
        Returns:
            True se esiste cache valida per la data
        """
        cache_path = self._find_latest_cache_file(source, endpoint, date)
        
        if not cache_path or not cache_path.exists():
            return False
        
        # Per history mode, ignora il TTL
        if ignore_ttl:
            return True
        
        # Altrimenti verifica validità con TTL
        return self.is_cache_valid(cache_path, source)

    def has_gme_day_cached(self, date_str: str) -> bool:
        """
        Verifica se esiste cache valida per un giorno GME
        
        Args:
            date_str: Data in formato YYYY-MM-DD
            
        Returns:
            True se esiste cache valida (considerando dati storici infiniti)
        """
        # Per GME usiamo source='gme' e endpoint='data'
        cache_path = self._find_latest_cache_file('gme', 'data', date_str)
        
        if not cache_path or not cache_path.exists():
            return False
            
        # Verifica validità (gestisce automaticamente storico vs recente)
        return self.is_cache_valid(cache_path, source='gme', target_date=date_str)

    def _check_database_data_exists(self, source: str, date: str) -> bool:
        """Verifica se esistono dati nel database per una data specifica.
        
        Args:
            source: Sorgente dati ('api_ufficiali', 'web', 'gme')
            date: Data in formato YYYY-MM-DD
            
        Returns:
            True se esistono dati nel database per quella data
        """
        try:
            from config.config_manager import get_config_manager
            
            config_manager = get_config_manager()
            influx_config = config_manager.get_influxdb_config()
            
            # Skip verifica se in dry mode
            if influx_config.dry_mode:
                return True
            
            # Import InfluxDB client
            try:
                from influxdb_client import InfluxDBClient
            except ImportError:
                self._log.warning("InfluxDB client non disponibile per verifica database")
                return True  # Assume che i dati ci siano se non possiamo verificare
            
            # Determina bucket e measurement basato sulla sorgente
            if source == 'web':
                bucket = influx_config.bucket
                measurement = 'web'
            elif source == 'api_ufficiali':
                bucket = influx_config.bucket
                measurement = 'api'
            else:
                return True  # Sorgente sconosciuta, assume che i dati ci siano
            
            # Query per verificare esistenza dati
            with InfluxDBClient(url=influx_config.url, token=influx_config.token, org=influx_config.org) as client:
                query_api = client.query_api()
                
                # Query per contare i record per quella data
                query = f'''
                from(bucket: "{bucket}")
                |> range(start: {date}T00:00:00Z, stop: {date}T23:59:59Z)
                |> filter(fn: (r) => r._measurement == "{measurement}")
                |> count()
                |> yield(name: "count")
                '''
                
                result = query_api.query(query)
                
                # Verifica se ci sono risultati
                for table in result:
                    for record in table.records:
                        count = record.get_value()
                        if count and count > 0:
                            self._log.debug(f"Database check: {count} record trovati per {source} {date}")
                            return True
                
                self._log.debug(f"Database check: nessun record trovato per {source} {date}")
                return False
                
        except Exception as e:
            self._log.warning(f"Errore verifica database per {source} {date}: {e}")
            return True  # In caso di errore, assume che i dati ci siano per evitare loop infiniti


