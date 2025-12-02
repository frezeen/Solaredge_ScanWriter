#!/usr/bin/env python3
"""
Cache Manager - Gestore cache intelligente con TTL configurabile e compressione.

Struttura: cache/{source}/{endpoint}/{date}_{hash}.json.gz

Caratteristiche:
- Cache infinita per api_ufficiali e web
- Solo file compressi .json.gz
- Hash nei nomi file per evitare riscritture inutili
- Logging universale tramite app_logging
"""

import calendar
import gzip
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Set, Tuple

from app_logging import get_logger

# COSTANTI
HASH_LENGTH = 8
CACHE_KEY_LENGTH = 16
FILE_EXTENSION = '.json.gz'
DATE_PATTERN = '%Y-%m-%d'
ENCODING = 'utf-8'

# TTL Configuration (minuti)
TTL_CONFIG = {
    'api_ufficiali': 15,    # API ufficiali: 15 minuti, poi hash check
    'web': 15,              # Web scraping: 15 minuti, poi hash check
    'gme': 1440             # GME: 24 ore (dati giornalieri)
}


class CacheManager:
    """Gestore cache centralizzato con supporto per diversi tipi di sorgenti e compressione."""

    def __init__(self, cache_dir: str = "cache"):
        """
        Inizializza il gestore della cache.

        Args:
            cache_dir: Directory base per la cache.
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self._log = get_logger("cache_manager")
        
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'sealed_saves': 0,
            'partial_saves': 0
        }

    def get_cache_key(self, source: str, endpoint: str, date: str) -> str:
        """Genera chiave cache univoca."""
        raw_key = f"{source}_{endpoint}_{date}"
        return hashlib.md5(raw_key.encode()).hexdigest()[:CACHE_KEY_LENGTH]
    
    def get_statistics(self) -> Dict[str, int]:
        """Restituisce statistiche sull'utilizzo della cache."""
        return self.stats.copy()
    
    def reset_statistics(self) -> None:
        """Resetta i contatori delle statistiche."""
        self.stats = {k: 0 for k in self.stats}
    
    def get_data_hash(self, data: Dict[str, Any]) -> str:
        """Genera hash dei dati per rilevare cambiamenti."""
        return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()[:HASH_LENGTH]
    
    def _extract_time_from_filename(self, file_path: Path) -> Optional[datetime]:
        """
        Estrae l'orario dal nome del file cache.
        
        Format supportati:
        - YYYY-MM-DD_HH-MM.json.gz
        - YYYY-MM_HH-MM_hash.json.gz
        """
        try:
            filename = file_path.stem.replace('.json', '')
            if '_' not in filename:
                return None
            
            parts = filename.split('_')
            if len(parts) < 2:
                return None
                
            date_part = parts[0]
            time_part = parts[1]
            
            # Rimuovi hash se presente e normalizza orario
            time_str = time_part.replace('-', ':')
            
            # Gestione formato mensile (YYYY-MM) vs giornaliero (YYYY-MM-DD)
            if len(date_part) == 7:  # YYYY-MM
                date_part += '-01'
            
            datetime_str = f"{date_part} {time_str}:00"
            return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
        except (ValueError, IndexError):
            return None

    def _build_cache_path(
        self, 
        source: str, 
        endpoint: str, 
        date: str, 
        time_str: Optional[str] = None, 
        data_hash: Optional[str] = None
    ) -> Path:
        """Costruisce path cache con orario e opzionalmente hash nel nome."""
        if not time_str:
            time_str = datetime.now().strftime('%H-%M')
            
        filename = f"{date}_{time_str}"
        if data_hash:
            filename += f"_{data_hash}"
        filename += FILE_EXTENSION
            
        return self.cache_dir / source / endpoint / filename

    def _read_cache_file(self, cache_path: Path) -> Optional[Dict[str, Any]]:
        """Legge e decodifica un file cache."""
        if not cache_path.exists():
            return None
        
        try:
            with gzip.open(cache_path, 'rt', encoding=ENCODING) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            self._log.warning(f"Corrupt cache file {cache_path}: {e}")
            return None
    
    def _is_file_age_valid(self, file_path: Path, source: Optional[str] = None, target_date: Optional[str] = None) -> bool:
        """Valida età cache basata sull'orario nel nome del file."""
        file_timestamp = self._extract_time_from_filename(file_path)
        if not file_timestamp:
            return False
        
        # Per dati storici (history mode), la cache è sempre valida
        if target_date:
            try:
                # Supporta YYYY-MM-DD e YYYY-MM
                date_str = target_date + '-01' if len(target_date) == 7 else target_date
                target_dt = datetime.strptime(date_str, DATE_PATTERN).date()
                
                if target_dt < datetime.now().date():
                    return True
            except ValueError:
                pass # Fallback al controllo TTL standard
        
        # Per dati di oggi, usa il controllo TTL normale
        if source and (ttl_minutes := TTL_CONFIG.get(source)):
            cache_age = datetime.now() - file_timestamp
            return cache_age < timedelta(minutes=ttl_minutes)
        
        return True
    
    def is_cache_valid(self, cache_path: Path, source: Optional[str] = None, target_date: Optional[str] = None) -> bool:
        """Verifica validità cache usando validazione basata su nome file."""
        if not cache_path.exists():
            return False
        return self._is_file_age_valid(cache_path, source, target_date)

    def _find_latest_cache_file(self, source: str, endpoint: str, date: str) -> Optional[Path]:
        """Trova il file cache più recente per una data."""
        endpoint_dir = self.cache_dir / source / endpoint
        if not endpoint_dir.exists():
            return None
        
        # Cerca tutti i file che iniziano con la data
        pattern = f"{date}_*{FILE_EXTENSION}"
        files = list(endpoint_dir.glob(pattern))
        
        if not files:
            return None
            
        # Priorità ai file con hash (3 parti: date_time_hash) rispetto a quelli senza (2 parti)
        # Poi ordina per nome (che include il timestamp)
        return max(files, key=lambda p: (len(p.stem.split('_')), p.name))
    
    def get_cached_data(
        self, 
        source: str, 
        endpoint: str, 
        date: str, 
        time_str: Optional[str] = None, 
        ignore_ttl: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Recupera dati dalla cache se valida."""
        if time_str:
            cache_path = self._build_cache_path(source, endpoint, date, time_str)
        else:
            cache_path = self._find_latest_cache_file(source, endpoint, date)
            
        if not cache_path:
            return None
        
        # Validazione TTL (se non ignorata)
        if not ignore_ttl and not self._is_file_age_valid(cache_path, source, date):
            return None

        # Lettura dati
        if not (cache_entry := self._read_cache_file(cache_path)):
            return None
        
        self._log.info(f"✅ CACHE HIT [{source}]: {self.get_cache_key(source, endpoint, date)} ({date})")
        self.stats['cache_hits'] += 1
        return cache_entry.get('data')

    def _build_cache_entry(self, source: str, endpoint: str, date: str, data: Dict[str, Any], data_hash: str) -> Dict[str, Any]:
        """Costruisce entry cache standard."""
        return {
            'data': data,
            'source': source,
            'endpoint': endpoint,
            'date': date,
            'data_hash': data_hash
        }
    
    def _parse_date_value(self, value: Any) -> Optional[str]:
        """Estrae una data YYYY-MM-DD da vari formati."""
        try:
            if isinstance(value, str):
                # "2024-06-01..."
                if len(value) >= 10 and value[4] == '-' and value[7] == '-':
                    return value[:10]
            elif isinstance(value, (int, float)):
                # Timestamp
                ts = value / 1000 if value > 3e10 else value
                if ts > 946684800:  # > 2000-01-01
                    return datetime.fromtimestamp(ts).strftime(DATE_PATTERN)
        except (ValueError, TypeError):
            pass
        return None

    def _extract_dates_recursively(self, data: Any, target_month: str, found_days: Set[str]) -> None:
        """Attraversa ricorsivamente il JSON cercando date che matchano il mese target."""
        if isinstance(data, dict):
            for key, value in data.items():
                if key in {'date', 'time', 'timeStamp', 'timestamp', 'lastUpdated', 'date_time'}:
                    if (date_str := self._parse_date_value(value)) and date_str.startswith(target_month):
                        found_days.add(date_str)
                
                if isinstance(value, (dict, list)):
                    self._extract_dates_recursively(value, target_month, found_days)
                    
        elif isinstance(data, list):
            for item in data:
                self._extract_dates_recursively(item, target_month, found_days)

    def _has_full_month_data(self, data: Dict[str, Any], month_key: str) -> bool:
        """Verifica se i dati coprono tutti i giorni del mese."""
        try:
            year, month = map(int, month_key.split('-'))
            days_in_month = calendar.monthrange(year, month)[1]
            
            unique_days: Set[str] = set()
            self._extract_dates_recursively(data, month_key, unique_days)
            
            num_found = len(unique_days)
            
            if num_found == days_in_month:
                self._log.debug(f"✅ Dati completi per {month_key}: {num_found}/{days_in_month} giorni")
                return True
            
            self._log.debug(f"⚠️ Dati parziali per {month_key}: {num_found}/{days_in_month} giorni")
            return False
                
        except Exception as e:
            self._log.warning(f"Errore validazione completezza dati: {e}")
            return False

    def save_to_cache(
        self, 
        source: str, 
        endpoint: str, 
        date: str, 
        data: Dict[str, Any], 
        data_hash: Optional[str] = None, 
        is_metadata: bool = False
    ) -> str:
        """Salva dati in cache con orario e hash (se completo) nel nome."""
        if not (data_hash := data_hash or self.get_data_hash(data)):
            raise ValueError("Impossibile generare hash dei dati")
        
        # Verifica completezza
        is_complete = False
        if len(date) == 10:  # YYYY-MM-DD
            is_complete = True
        elif len(date) == 7:  # YYYY-MM
            is_complete = is_metadata or self._has_full_month_data(data, date)
        
        # Rimuovi vecchio file
        if old_file := self._find_latest_cache_file(source, endpoint, date):
            try:
                old_file.unlink()
            except OSError:
                pass
        
        # Prepara nuovo path
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
            
            if is_complete:
                self.stats['sealed_saves'] += 1
            else:
                self.stats['partial_saves'] += 1
                
            return data_hash

        except Exception as e:
            self._log.error(f"Cache save failed {cache_path}: {e}")
            raise RuntimeError(f"Cache save failed for {date}") from e

    def _check_hash_and_refresh(
        self, 
        source: str, 
        endpoint: str, 
        date: str, 
        fetch_func: Callable[[], Dict[str, Any]], 
        cached_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Confronta hash e aggiorna se necessario."""
        cache_key = self.get_cache_key(source, endpoint, date)
        
        try:
            self._log.info(f"🌐 API CALL (hash check) [{source}/{endpoint}]: {date}")
            fresh_data = fetch_func()
            fresh_hash = self.get_data_hash(fresh_data)
            cached_hash = self.get_data_hash(cached_data)
            
            if fresh_hash != cached_hash:
                self._log.info(f"🔄 HASH CHANGED [{source}]: {cache_key} ({date})")
                self.save_to_cache(source, endpoint, date, fresh_data, fresh_hash)
                return fresh_data
            
            self._log.info(f"✅ HASH MATCH [{source}]: {cache_key} ({date})")
            # Aggiorna solo timestamp
            self.save_to_cache(source, endpoint, date, cached_data, fresh_hash)
            return cached_data
                
        except Exception as e:
            self._log.error(f"Hash check failed {cache_key}: {e}")
            # Fallback: salva i nuovi dati se disponibili, altrimenti rilancia
            fresh_data = fetch_func()
            self.save_to_cache(source, endpoint, date, fresh_data)
            return fresh_data
    
    def get_or_fetch(
        self, 
        source: str, 
        endpoint: str, 
        date: str, 
        fetch_func: Callable[[], Dict[str, Any]], 
        is_metadata: bool = False
    ) -> Dict[str, Any]:
        """Ottieni da cache con logica intelligente per tipo sorgente."""
        
        # 1. Cerca file cache esistente
        cache_path = self._find_latest_cache_file(source, endpoint, date)
        
        if cache_path:
            # 2. Se valido (TTL o storico), ritorna
            if self._is_file_age_valid(cache_path, source, date):
                if cache_entry := self._read_cache_file(cache_path):
                    self._log.info(f"✅ CACHE HIT [{source}/{endpoint}]: {date}")
                    self.stats['cache_hits'] += 1
                    return cache_entry['data']
            
            # 3. Se scaduto ma è web/api e oggi -> Hash Check
            # (Per dati storici _is_file_age_valid ritorna True, quindi qui siamo solo per dati recenti scaduti)
            if source in {'web', 'api_ufficiali'}:
                # Safety check: se per qualche motivo siamo qui con dati storici, NON fare refresh
                # (es. se _extract_time_from_filename fallisce ma il file esiste)
                is_historical = False
                try:
                    target_dt = datetime.strptime(date + '-01' if len(date) == 7 else date, DATE_PATTERN).date()
                    if target_dt < datetime.now().date():
                        is_historical = True
                except ValueError:
                    pass

                if is_historical:
                     if cache_entry := self._read_cache_file(cache_path):
                        self._log.info(f"📚 HISTORICAL CACHE HIT (fallback) [{source}/{endpoint}]: {date}")
                        return cache_entry['data']

                if cache_entry := self._read_cache_file(cache_path):
                    self._log.info(f"⏰ CACHE EXPIRED (>15min) [{source}/{endpoint}]: {date}")
                    return self._check_hash_and_refresh(source, endpoint, date, fetch_func, cache_entry['data'])

        # 4. Cache Miss o Hash Check fallito -> Fetch & Save
        self._log.info(f"🌐 API CALL [{source}/{endpoint}]: {date}")
        self.stats['cache_misses'] += 1
        
        try:
            fresh_data = fetch_func()
            self.save_to_cache(source, endpoint, date, fresh_data, is_metadata=is_metadata)
            return fresh_data
        except Exception as e:
            self._log.error(f"Fetch failed for {source}/{endpoint}/{date}: {e}")
            raise

    def _clear_files_in_path(self, path: Path, pattern: str = f"*{FILE_EXTENSION}") -> int:
        """Helper per cancellazione file con pattern."""
        if not path.exists():
            return 0
        
        files_to_delete = list(path.rglob(pattern) if pattern.startswith('*') else path.glob(pattern))
        for file_path in files_to_delete:
            try:
                file_path.unlink()
            except OSError:
                pass
        return len(files_to_delete)
    
    def clear_cache(self, source: Optional[str] = None, endpoint: Optional[str] = None, date: Optional[str] = None) -> None:
        """Pulisce cache usando pattern intelligenti."""
        target_dir = self.cache_dir
        pattern = f"*{FILE_EXTENSION}"
        
        if source:
            target_dir /= source
            if endpoint:
                target_dir /= endpoint
                if date:
                    pattern = f"{date}_*{FILE_EXTENSION}"
        
        count = self._clear_files_in_path(target_dir, pattern)
        self._log.info(f"🗑️ CACHE CLEARED: {target_dir} ({pattern}) - {count} files")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Restituisce statistiche cache ottimizzate (senza leggere contenuto file)."""
        stats = {
            'total_files': 0,
            'total_size_mb': 0,
            'sources': {},
            'oldest_file': None,
            'newest_file': None
        }

        for file_path in self.cache_dir.rglob(f"*{FILE_EXTENSION}"):
            try:
                # Statistiche base
                file_size_mb = file_path.stat().st_size / (1024 * 1024)
                stats['total_files'] += 1
                stats['total_size_mb'] += file_size_mb

                # Aggregazione per sorgente
                parts = file_path.relative_to(self.cache_dir).parts
                if len(parts) >= 1:
                    source = parts[0]
                    src_stats = stats['sources'].setdefault(source, {'files': 0, 'size_mb': 0})
                    src_stats['files'] += 1
                    src_stats['size_mb'] += file_size_mb

                # Timestamp dal nome file (molto più veloce di leggere il JSON)
                if timestamp := self._extract_time_from_filename(file_path):
                    if not stats['oldest_file'] or timestamp < stats['oldest_file'][1]:
                        stats['oldest_file'] = (str(file_path), timestamp)
                    if not stats['newest_file'] or timestamp > stats['newest_file'][1]:
                        stats['newest_file'] = (str(file_path), timestamp)
                        
            except (OSError, ValueError):
                continue

        return stats

    def cache_exists_for_date(self, source: str, endpoint: str, date: str, ignore_ttl: bool = False) -> bool:
        """Verifica se esiste cache per una data specifica."""
        cache_path = self._find_latest_cache_file(source, endpoint, date)
        
        if not cache_path:
            return False
        
        if ignore_ttl:
            return True
            
        return self._is_file_age_valid(cache_path, source, target_date=date)

    def has_gme_day_cached(self, date_str: str) -> bool:
        """Verifica se esiste cache valida per un giorno GME."""
        return self.cache_exists_for_date('gme', 'data', date_str)
