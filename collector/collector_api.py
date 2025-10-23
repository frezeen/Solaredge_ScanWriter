#!/usr/bin/env python3
"""Collector API - Versione Ottimizzata"""

import os
import requests
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from scheduler.scheduler_loop import SchedulerLoop, SourceType
from config.config_manager import get_config_manager

logger = logging.getLogger(__name__)

class CollectorAPI:
    """Collector minimale che segue il YAML"""
    
    # Rimossa lista hardcoded - history mode usa tutti gli endpoint abilitati nel YAML
    


    def __init__(self, config_path: str = "config/main.yaml", cache=None, scheduler: Optional[SchedulerLoop] = None):
        self.cache = cache
        self.scheduler = scheduler
        self._config_manager = get_config_manager(config_path)
        self._api_config = self._config_manager.get_solaredge_api_config()
        self._global_config = self._config_manager.get_global_config()
        
        self.api_key = self._api_config.api_key
        self.site_id = self._api_config.site_id or self._global_config.site_id
        self.base_url = self._api_config.base_url
        
        self.config = self._config_manager.get_raw_config()

    def _get_enabled_endpoints(self) -> Dict[str, Any]:
        """Ottieni endpoint abilitati dal YAML"""
        api_config = self.config.get('sources', {}).get('api_ufficiali', {})
        return {
            name: cfg for name, cfg in api_config.get('endpoints', {}).items()
            if cfg.get('enabled', False)
        }

    def _build_url(self, endpoint_config: Dict[str, Any], serial_number: str = None) -> str:
        """Costruisci URL dall'endpoint config"""
        endpoint = endpoint_config['endpoint']
        if ('changeLog' in endpoint or '/data' in endpoint or '/storageData' in endpoint) and serial_number:
            return f"{self.base_url}{endpoint}".format(siteId=self.site_id, serialNumber=serial_number)
        return f"{self.base_url}{endpoint}".format(siteId=self.site_id)

    def _build_params(self, endpoint_config: Dict[str, Any]) -> Dict[str, str]:
        """Costruisci parametri con date automatiche"""
        params = {'api_key': self.api_key}
        
        # Copia parametri dal config e sostituisci placeholder
        config_params = endpoint_config.get('parameters', {})
        today = datetime.now().strftime('%Y-%m-%d')
        current_year = datetime.now().year
        year_start = f"{current_year}-01-01"
        year_end = f"{current_year}-12-31"
        
        for key, value in config_params.items():
            if isinstance(value, str):
                # Sostituisci placeholder con valori reali
                value = value.replace('${API_START_DATE}', today)
                value = value.replace('${API_END_DATE}', today)
                value = value.replace('${API_START_TIME}', f"{today} 00:00:00")
                value = value.replace('${API_END_TIME}', f"{today} 23:59:59")
                value = value.replace('${CURRENT_YEAR_START}', year_start)
                value = value.replace('${CURRENT_YEAR_END}', year_end)
            params[key] = value
        
        # Identifica endpoint che richiedono date aggiuntive (solo se non hanno già date)
        endpoint_path = endpoint_config.get('endpoint', '')
        has_existing_dates = any(k in params for k in ['startDate', 'endDate', 'startTime', 'endTime'])
        needs_date = any(x in endpoint_path for x in ['energyDetails', 'powerDetails', 'meters']) and not has_existing_dates
        
        if needs_date:
            params.update({
                'startTime': f"{today} 00:00:00",
                'endTime': f"{today} 23:59:59"
            })
            
        return params

    def _call_api(self, url: str, params: Dict[str, str]) -> Dict[str, Any]:
        """Chiamata API con scheduler timing"""
        def _http_call():
            try:
                response = requests.get(url, params=params, timeout=self._api_config.timeout_seconds)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.HTTPError as e:
                logger.error(f"HTTP Error for {url}: {e.response.status_code}")
                raise
            except Exception as e:
                logger.error(f"Errore chiamata API {url}: {e}")
                raise
        
        # Usa scheduler se disponibile, altrimenti chiamata diretta
        if self.scheduler:
            return self.scheduler.execute_with_timing(SourceType.API, _http_call, cache_hit=False)
        else:
            return _http_call()

    def _collect_equipment_endpoint(self, endpoint_name: str, endpoint_config: Dict[str, Any]) -> Dict[str, Any]:
        """Raccolta per endpoint equipment che richiedono serial number"""
        try:
            # Ottieni serial number da equipment_list
            equipment_config = self.config.get('sources', {}).get('api_ufficiali', {}).get('endpoints', {}).get('equipment_list')
            if not equipment_config or not equipment_config.get('enabled'):
                return {}
            
            # Usa cache per equipment_list
            equipment_data = None
            if self.cache:
                today = datetime.now().strftime('%Y-%m-%d')
                equipment_data = self.cache.get_or_fetch(
                    'api_ufficiali', 'equipment_list', today,
                    lambda: self._call_api(self._build_url(equipment_config), self._build_params(equipment_config))
                )
            else:
                equipment_data = self._call_api(self._build_url(equipment_config), self._build_params(equipment_config))
            
            serial = equipment_data.get('reporters', {}).get('list', [{}])[0].get('serialNumber')
            if not serial:
                return {}
            
            # Usa cache per l'endpoint equipment specifico
            if self.cache:
                today = datetime.now().strftime('%Y-%m-%d')
                return self.cache.get_or_fetch(
                    'api_ufficiali', endpoint_name, today,
                    lambda: self._call_api(self._build_url(endpoint_config, serial), self._build_params(endpoint_config))
                )
            else:
                return self._call_api(self._build_url(endpoint_config, serial), self._build_params(endpoint_config))
        except Exception as e:
            logger.error(f"Errore raccolta equipment endpoint {endpoint_name}: {e}")
            return {}

    def collect(self) -> Dict[str, Any]:
        """Raccolta dati da endpoint abilitati"""
        results = {}
        
        for endpoint_name, endpoint_config in self._get_enabled_endpoints().items():
            try:
                if endpoint_name in ['equipment_change_log', 'equipment_data', 'site_storage_data']:
                    results[endpoint_name] = self._collect_equipment_endpoint(endpoint_name, endpoint_config)
                else:
                    url = self._build_url(endpoint_config)
                    params = self._build_params(endpoint_config)

                    if self.cache:
                        today = datetime.now().strftime('%Y-%m-%d')
                        results[endpoint_name] = self.cache.get_or_fetch(
                            'api_ufficiali', endpoint_name, today,
                            lambda: self._call_api(url, params)
                        )
                    else:
                        results[endpoint_name] = self._call_api(url, params)

            except Exception as e:
                logger.error(f"Errore raccolta {endpoint_name}: {e}")
                continue

        return results
    
    def get_production_date_range(self) -> Optional[Dict[str, str]]:
        """Ottiene range temporale di produzione dall'API dataPeriod
        
        Returns:
            Dict con 'start' e 'end' in formato YYYY-MM-DD, None se errore
        """
        try:
            url = f"{self.base_url}/site/{self.site_id}/dataPeriod"
            params = {'api_key': self.api_key}
            
            response = requests.get(url, params=params, timeout=self._api_config.timeout_seconds)
            response.raise_for_status()
            data = response.json()
            
            date_period = data.get('dataPeriod', {})
            start_date = date_period.get('startDate')
            end_date = date_period.get('endDate')
            
            if not start_date or not end_date:
                logger.error("API dataPeriod non ha restituito date valide")
                return None
            
            logger.info(f"Range produzione: {start_date} → {end_date}")
            return {'start': start_date, 'end': end_date}
            
        except Exception as e:
            logger.error(f"Errore recupero date range: {e}")
            return None
    
    def collect_with_dates(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Raccolta dati con date personalizzate (per history mode)
        
        Args:
            start_date: Data inizio in formato YYYY-MM-DD
            end_date: Data fine in formato YYYY-MM-DD
            
        Returns:
            Dizionario con dati raccolti dagli endpoint aggregati per giorno
        """
        # Validazione formato date
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError as e:
            logger.error(f"Formato date non valido: {e}")
            return {}
        
        # Formatta date per API (con orari)
        start_time = f"{start_date} 00:00:00"
        end_time = f"{end_date} 23:59:59"
        
        logger.info(f"Raccolta dati per periodo: {start_date} → {end_date}")
        
        # Risultati aggregati per tutto il periodo
        aggregated_results = {}
        

        
        # Usa tutti gli endpoint abilitati nel YAML invece di lista hardcoded
        enabled_endpoints = self._get_enabled_endpoints()
        
        for endpoint_name, endpoint_config in enabled_endpoints.items():
            
            try:
                # USA SEMPRE cache.get_or_fetch() come API mode - semplice e funziona!
                if self.cache:
                    logger.debug(f"🔄 Usando cache diretta per {endpoint_name} ({start_date})")
                    
                    if endpoint_name in ['equipment_change_log', 'equipment_data', 'site_storage_data']:
                        # Endpoint speciali - per ora usa API
                        use_cache = False
                        cached_data = None
                        logger.debug(f"⚠️ Endpoint speciale {endpoint_name} - usa API")
                    else:
                        # Endpoint normali - usa cache.get_or_fetch come API mode
                        # SEMPRE, anche per periodi multipli (history mode gestisce mese per mese)
                        url = self._build_url(endpoint_config)
                        params = self._build_params_with_dates(endpoint_config, 
                                                             f"{start_date} 00:00:00", 
                                                             f"{end_date} 23:59:59")
                        
                        cached_data = self.cache.get_or_fetch(
                            'api_ufficiali', endpoint_name, start_date,
                            lambda: self._call_api(url, params)
                        )
                        use_cache = True
                        logger.info(f"✅ Cache diretta per {endpoint_name} (come API mode)")
                else:
                    # Nessuna cache disponibile
                    use_cache = False
                    cached_data = None
                
                # Ottieni i dati (da cache o API)
                if use_cache and cached_data:
                    # Verifica qualità dati dalla cache
                    data_size = len(str(cached_data))
                    
                    # Se i dati sono troppo piccoli, probabilmente sono vuoti/corrotti
                    if data_size < 100:  # Soglia minima ragionevole
                        logger.warning(f"⚠️ Dati da cache per {endpoint_name} troppo piccoli ({data_size} caratteri), fallback API")
                        use_cache = False
                        month_data = None
                    else:
                        # Usa dati dalla cache
                        month_data = cached_data
                        logger.info(f"🔄 Cache hit per {endpoint_name}: dati ricostruiti da cache, verranno processati per DB")
                        logger.debug(f"📊 Dati da cache - Chiavi: {list(cached_data.keys()) if cached_data else 'Nessun dato'}")
                        logger.debug(f"📊 Dati da cache - Dimensione: {data_size} caratteri")
                
                # Chiamata API se necessaria (cache miss o dati corrotti)
                if not use_cache or not month_data:
                    # Chiamata API necessaria
                    logger.info(f"📞 Chiamata API per {endpoint_name}")
                    if endpoint_name == 'equipment_data':
                        month_data = self._collect_equipment_endpoint_with_dates(
                            endpoint_name, endpoint_config, start_time, end_time
                        )
                    elif endpoint_name == 'site_energy_day':
                        month_data = self._collect_site_energy_day_with_dates(
                            endpoint_name, endpoint_config, start_date, end_date
                        )
                    elif endpoint_name == 'site_timeframe_energy':
                        # Raccolta intelligente per anno con cache individuale
                        month_data = self._collect_site_timeframe_energy_smart_cache(
                            endpoint_name, endpoint_config, start_date, end_date
                        )
                    else:
                        url = self._build_url(endpoint_config)
                        params = self._build_params_with_dates(endpoint_config, start_time, end_time)
                        month_data = self._call_api(url, params)
                
                # Salva in cache solo se i dati vengono dall'API (non dalla cache)
                if month_data and not use_cache:
                    # Dati freschi dall'API - salva in cache
                    daily_data = self._split_data_by_day(endpoint_name, month_data, start_date, end_date)
                    
                    # Salva ogni giorno in cache separatamente
                    if self.cache:
                        for day, day_data in daily_data.items():
                            self.cache.save_to_cache('api_ufficiali', endpoint_name, day, day_data)
                            logger.debug(f"💾 Cache salvata: {endpoint_name} - {day}")
                
                # Aggiungi sempre i dati al risultato finale (da cache o API)
                if month_data:
                    aggregated_results[endpoint_name] = month_data
                    logger.debug(f"📋 Dati aggiunti al risultato finale per {endpoint_name}")
                    
            except Exception as e:
                logger.error(f"Errore raccolta {endpoint_name} per {start_date}: {e}")
                continue
        
        return aggregated_results
    
    def _build_params_with_dates(self, endpoint_config: Dict[str, Any], start_time: str, end_time: str) -> Dict[str, str]:
        """Costruisci parametri con date personalizzate per history mode"""
        params = {'api_key': self.api_key}
        
        # Copia parametri dal config
        config_params = endpoint_config.get('parameters', {})
        for key, value in config_params.items():
            if key not in ['startTime', 'endTime', 'startDate', 'endDate']:
                params[key] = value
        
        # Identifica endpoint che richiedono date
        endpoint_path = endpoint_config.get('endpoint', '')
        
        if any(x in endpoint_path for x in ['energyDetails', 'powerDetails', 'meters', 'energy', 'power']):
            params['startTime'] = start_time
            params['endTime'] = end_time
        elif 'data' in endpoint_path:
            # Equipment data API supporta solo 1 settimana, ma proviamo comunque
            # Se fallisce, verrà gestito dal try/except
            params['startTime'] = start_time
            params['endTime'] = end_time
            
        return params
    
    def _collect_equipment_endpoint_with_dates(self, endpoint_name: str, endpoint_config: Dict[str, Any], 
                                              start_time: str, end_time: str) -> Dict[str, Any]:
        """Raccolta per endpoint equipment con date personalizzate
        
        Nota: L'API equipment supporta solo range di 1 settimana.
        Per periodi più lunghi, suddividiamo in settimane.
        """
        try:
            # Ottieni serial number da equipment_list
            equipment_config = self.config.get('sources', {}).get('api_ufficiali', {}).get('endpoints', {}).get('equipment_list')
            if not equipment_config or not equipment_config.get('enabled'):
                logger.warning("equipment_list non abilitato, skip equipment_data")
                return {}
            
            equipment_data = self._call_api(
                self._build_url(equipment_config), 
                self._build_params(equipment_config)
            )
            
            serial = equipment_data.get('reporters', {}).get('list', [{}])[0].get('serialNumber')
            if not serial:
                logger.warning("Serial number non trovato, skip equipment_data")
                return {}
            
            # Calcola durata del periodo
            start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
            end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
            duration_days = (end_dt - start_dt).days
            
            # Se il periodo è > 7 giorni, suddividi in settimane
            if duration_days > 7:
                logger.info(f"Periodo {duration_days} giorni > 7, suddivisione in settimane per equipment_data")
                return self._collect_equipment_by_weeks(endpoint_config, serial, start_dt, end_dt)
            
            # Periodo <= 7 giorni, chiamata singola
            url = self._build_url(endpoint_config, serial)
            params = self._build_params_with_dates(endpoint_config, start_time, end_time)
            
            return self._call_api(url, params)
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                logger.warning(f"Equipment endpoint non supporta questo range temporale, skip")
            else:
                logger.error(f"HTTP Error per equipment endpoint: {e}")
            return {}
        except Exception as e:
            logger.error(f"Errore raccolta equipment endpoint {endpoint_name} con date: {e}")
            return {}
    
    def _collect_equipment_by_weeks(self, endpoint_config: Dict[str, Any], serial: str, 
                                    start_dt: datetime, end_dt: datetime) -> Dict[str, Any]:
        """Raccoglie dati equipment suddividendo in settimane"""
        all_telemetries = []
        current = start_dt
        
        while current <= end_dt:
            # Calcola fine settimana (7 giorni con sovrapposizione per recuperare giorni persi)
            week_end = min(current + timedelta(days=6), end_dt)
            
            start_time_str = current.strftime('%Y-%m-%d %H:%M:%S')
            end_time_str = week_end.strftime('%Y-%m-%d %H:%M:%S')
            
            try:
                url = self._build_url(endpoint_config, serial)
                params = self._build_params_with_dates(endpoint_config, start_time_str, end_time_str)
                
                logger.info(f"🔄 Equipment API call: {start_time_str[:10]} → {end_time_str[:10]}")
                week_data = self._call_api(url, params)
                
                if week_data and 'data' in week_data and 'telemetries' in week_data['data']:
                    telemetries_count = len(week_data['data']['telemetries'])
                    telemetries = week_data['data']['telemetries']
                    
                    all_telemetries.extend(telemetries)
                    logger.debug(f"Equipment data: {telemetries_count} telemetries per settimana {start_time_str[:10]} - {end_time_str[:10]}")
                else:
                    logger.warning(f"❌ Equipment data: Nessuna telemetria per settimana {start_time_str[:10]} - {end_time_str[:10]}")
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 400:
                    logger.warning(f"Equipment data non disponibile per settimana {start_time_str[:10]} - {end_time_str[:10]}, skip")
                else:
                    logger.error(f"HTTP Error per equipment data {start_time_str[:10]} - {end_time_str[:10]}: {e}")
            except Exception as e:
                logger.error(f"Errore raccolta equipment data {start_time_str[:10]} - {end_time_str[:10]}: {e}")
            
            # Passa alla settimana successiva con sovrapposizione (6 giorni dopo l'inizio)
            current = current + timedelta(days=6)
        
        # Restituisci formato aggregato
        if all_telemetries:
            return {
                'data': {
                    'telemetries': all_telemetries
                }
            }
        return {}
    
    def _split_data_by_day(self, endpoint_name: str, month_data: Dict[str, Any], 
                          start_date: str, end_date: str) -> Dict[str, Dict[str, Any]]:
        """Suddivide i dati mensili per giorno per il caching
        
        Args:
            endpoint_name: Nome dell'endpoint (es. 'site_power_details')
            month_data: Dati grezzi dell'intero mese dall'API
            start_date: Data inizio in formato YYYY-MM-DD
            end_date: Data fine in formato YYYY-MM-DD
            
        Returns:
            Dizionario {data: dati_giorno} dove ogni chiave è una data YYYY-MM-DD
        """
        daily_split = {}
        
        # Parsing basato sulla struttura dell'endpoint
        if endpoint_name in ['site_power_details', 'site_energy_details']:
            # Struttura: {"[measurement]": {"timeUnit": "...", "unit": "...", "meters": [...]}}
            for meter_type, meter_data in month_data.items():
                if not isinstance(meter_data, dict) or 'meters' not in meter_data:
                    continue
                
                for meter in meter_data.get('meters', []):
                    for value_entry in meter.get('values', []):
                        date_str = value_entry.get('date', '')
                        if not date_str:
                            continue
                        
                        # Estrai solo la data (YYYY-MM-DD)
                        day = date_str.split(' ')[0] if ' ' in date_str else date_str
                        
                        # Inizializza struttura per questo giorno se non esiste
                        if day not in daily_split:
                            daily_split[day] = {meter_type: {
                                'timeUnit': meter_data.get('timeUnit'),
                                'unit': meter_data.get('unit'),
                                'meters': []
                            }}
                        
                        # Aggiungi il meter se non esiste già per questo giorno
                        if meter_type not in daily_split[day]:
                            daily_split[day][meter_type] = {
                                'timeUnit': meter_data.get('timeUnit'),
                                'unit': meter_data.get('unit'),
                                'meters': []
                            }
                        
                        # Trova o crea il meter specifico
                        existing_meter = None
                        for m in daily_split[day][meter_type]['meters']:
                            if m.get('type') == meter.get('type'):
                                existing_meter = m
                                break
                        
                        if not existing_meter:
                            existing_meter = {
                                'type': meter.get('type'),
                                'values': []
                            }
                            daily_split[day][meter_type]['meters'].append(existing_meter)
                        
                        # Aggiungi il valore
                        existing_meter['values'].append(value_entry)
        
        elif endpoint_name == 'equipment_data':
            # Struttura: {"data": {"count": N, "telemetries": [{"date": "...", "...": ...}]}}
            telemetries = month_data.get('data', {}).get('telemetries', [])
            
            for telemetry in telemetries:
                date_str = telemetry.get('date', '')
                if not date_str:
                    continue
                
                # Estrai solo la data (YYYY-MM-DD)
                day = date_str.split(' ')[0] if ' ' in date_str else date_str
                
                # Inizializza struttura per questo giorno
                if day not in daily_split:
                    daily_split[day] = {'data': {'count': 0, 'telemetries': []}}
                
                # Aggiungi telemetria
                daily_split[day]['data']['telemetries'].append(telemetry)
                daily_split[day]['data']['count'] = len(daily_split[day]['data']['telemetries'])
        
        else:
            # Endpoint non supportato - restituisci tutto come un singolo giorno
            logger.warning(f"Endpoint {endpoint_name} non supporta split giornaliero, uso start_date")
            daily_split[start_date] = month_data
        
        logger.info(f"Split dati per {endpoint_name}: {len(daily_split)} giorni estratti")
        return daily_split
    
    def _split_data_by_day(self, endpoint_name: str, data: Dict[str, Any], start_date: str, end_date: str) -> Dict[str, Dict[str, Any]]:
        """Suddivide dati mensili per giorno per cache giornaliera
        
        Args:
            endpoint_name: Nome endpoint
            data: Dati mensili dall'API
            start_date: Data inizio (YYYY-MM-DD)
            end_date: Data fine (YYYY-MM-DD)
            
        Returns:
            Dizionario {data: dati_giorno}
        """
        
        daily_data = {}
        
        # Gestione per powerDetails e energyDetails
        if endpoint_name in ['site_power_details', 'site_energy_details']:
            root_field = 'powerDetails' if endpoint_name == 'site_power_details' else 'energyDetails'
            root = data.get(root_field, {})
            meters = root.get('meters', [])
            
            if not meters:
                return daily_data
            
            # Inizializza struttura per ogni giorno
            current = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            
            while current <= end:
                day_str = current.strftime('%Y-%m-%d')
                daily_data[day_str] = {
                    root_field: {
                        'timeUnit': root.get('timeUnit'),
                        'unit': root.get('unit'),
                        'meters': []
                    }
                }
                current += timedelta(days=1)
            
            # Distribuisci i valori per giorno
            for meter in meters:
                meter_type = meter.get('type')
                values = meter.get('values', [])
                
                # Raggruppa valori per giorno
                daily_values = {}
                for value in values:
                    if 'date' in value:
                        date_str = value['date'][:10]  # Prendi solo YYYY-MM-DD
                        if date_str not in daily_values:
                            daily_values[date_str] = []
                        daily_values[date_str].append(value)
                
                # Aggiungi meter a ogni giorno
                for day_str, day_values in daily_values.items():
                    if day_str in daily_data:
                        daily_data[day_str][root_field]['meters'].append({
                            'type': meter_type,
                            'values': day_values
                        })
        
        # Gestione per equipment_data
        elif endpoint_name == 'equipment_data':
            telemetries = data.get('data', {}).get('telemetries', [])
            
            if not telemetries:
                return daily_data
            
            # Raggruppa telemetrie per giorno
            for telemetry in telemetries:
                if 'date' in telemetry:
                    date_str = telemetry['date'][:10]  # Prendi solo YYYY-MM-DD
                    
                    if date_str not in daily_data:
                        daily_data[date_str] = {
                            'data': {
                                'telemetries': []
                            }
                        }
                    
                    daily_data[date_str]['data']['telemetries'].append(telemetry)
        
        logger.info(f"Suddivisi dati {endpoint_name} in {len(daily_data)} giorni")
        
        return daily_data
    

    

    
    def _collect_site_energy_day_with_dates(self, endpoint_name: str, endpoint_config: Dict[str, Any], 
                                           start_date: str, end_date: str) -> Dict[str, Any]:
        """Raccoglie site_energy_day per tutto il periodo richiesto, suddividendo in anni
        
        Limitazione API: 1 anno max per timeUnit=DAY
        Strategia: Chiamate annuali per minimizzare API calls
        """
        try:
            # Ottieni il range di vita dell'impianto
            life_range = self.get_production_date_range()
            if not life_range:
                logger.warning("Impossibile ottenere range di vita impianto per site_energy_day")
                return {}
            
            # Usa il range più restrittivo tra quello richiesto e quello di vita
            actual_start = max(start_date, life_range['start'])
            actual_end = min(end_date, life_range['end'])
            
            logger.info(f"site_energy_day: raccolta da {actual_start} a {actual_end}")
            
            all_values = []
            current_year = int(actual_start[:4])
            end_year = int(actual_end[:4])
            
            while current_year <= end_year:
                year_start = f"{current_year}-01-01"
                year_end = f"{current_year}-12-31"
                
                # Limita al range effettivo
                if year_start < actual_start:
                    year_start = actual_start
                if year_end > actual_end:
                    year_end = actual_end
                
                try:
                    url = self._build_url(endpoint_config)
                    params = self._build_params(endpoint_config)
                    params.update({
                        'startDate': year_start,
                        'endDate': year_end,
                        'timeUnit': 'DAY'
                    })
                    
                    year_data = self._call_api(url, params)
                    
                    if year_data and 'energy' in year_data:
                        energy_data = year_data['energy']
                        if 'values' in energy_data:
                            all_values.extend(energy_data['values'])
                            logger.info(f"site_energy_day: raccolti {len(energy_data['values'])} giorni per {current_year}")
                
                except Exception as e:
                    logger.error(f"Errore raccolta site_energy_day per anno {current_year}: {e}")
                
                current_year += 1
            
            # Restituisci formato aggregato
            if all_values:
                return {
                    'energy': {
                        'timeUnit': 'DAY',
                        'unit': 'Wh',
                        'values': all_values
                    }
                }
            return {}
            
        except Exception as e:
            logger.error(f"Errore raccolta site_energy_day: {e}")
            return {}
    
    def _collect_site_timeframe_energy_smart_cache(self, endpoint_name: str, endpoint_config: Dict[str, Any], 
                                                  start_date: str, end_date: str) -> Dict[str, Any]:
        """Raccoglie site_timeframe_energy con cache intelligente per singolo anno
        
        Controlla cache per ogni anno individualmente. Se manca un anno, fa solo quella chiamata API.
        Quando l'impianto invecchia (es. da 5 a 6 anni), fa solo 1 chiamata per il nuovo anno.
        """
        try:
            # Ottieni il range di vita dell'impianto
            life_range = self.get_production_date_range()
            if not life_range:
                logger.warning("Impossibile ottenere range di vita impianto per site_timeframe_energy")
                return {}
            
            life_start_year = int(life_range['start'][:4])
            life_end_year = int(life_range['end'][:4])
            
            logger.info(f"site_timeframe_energy: controllo cache per anni {life_start_year}-{life_end_year}")
            
            all_timeframes = []
            api_calls_needed = 0
            
            for current_year in range(life_start_year, life_end_year + 1):
                year_cache_key = f"year_{current_year}"
                
                # Controlla se questo anno è già in cache
                if self.cache and self.cache.cache_exists_for_date('api_ufficiali', endpoint_name, year_cache_key, ignore_ttl=True):
                    logger.info(f"site_timeframe_energy: ✅ Anno {current_year} già in cache, skip")
                    # Carica dal cache
                    try:
                        cached_data = self.cache.get_cached_data('api_ufficiali', endpoint_name, year_cache_key)
                        if cached_data and 'timeFrameEnergy' in cached_data:
                            all_timeframes.append(cached_data['timeFrameEnergy'])
                    except Exception as e:
                        logger.warning(f"Errore caricamento cache anno {current_year}: {e}")
                else:
                    # Anno non in cache, fai chiamata API
                    api_calls_needed += 1
                    logger.info(f"site_timeframe_energy: 🔄 Anno {current_year} non in cache, chiamata API necessaria")
                    
                    year_start = f"{current_year}-01-01"
                    year_end = f"{current_year}-12-31"
                    
                    # Limita al range di vita effettivo
                    if year_start < life_range['start']:
                        year_start = life_range['start']
                    if year_end > life_range['end']:
                        year_end = life_range['end']
                    
                    try:
                        url = self._build_url(endpoint_config)
                        params = self._build_params(endpoint_config)
                        params.update({
                            'startDate': year_start,
                            'endDate': year_end
                        })
                        
                        year_data = self._call_api(url, params)
                        
                        if year_data and 'timeFrameEnergy' in year_data:
                            timeframe_data = year_data['timeFrameEnergy']
                            # Aggiungi metadati
                            timeframe_with_year = dict(timeframe_data)
                            timeframe_with_year['year'] = current_year
                            timeframe_with_year['startDate'] = year_start
                            timeframe_with_year['endDate'] = year_end
                            all_timeframes.append(timeframe_with_year)
                            
                            # Salva nel cache per questo specifico anno
                            if self.cache:
                                year_cache_data = {'timeFrameEnergy': timeframe_with_year}
                                self.cache.save_to_cache('api_ufficiali', endpoint_name, year_cache_key, year_cache_data)
                            
                            logger.info(f"site_timeframe_energy: ✅ Anno {current_year} - {timeframe_data.get('energy', 0)} Wh (salvato in cache)")
                    
                    except Exception as e:
                        logger.error(f"Errore raccolta site_timeframe_energy per anno {current_year}: {e}")
            
            # Statistiche finali
            total_years = life_end_year - life_start_year + 1
            cached_years = total_years - api_calls_needed
            
            if api_calls_needed > 0:
                logger.info(f"site_timeframe_energy: 📊 {api_calls_needed} chiamate API, {cached_years} anni da cache")
            else:
                logger.info(f"site_timeframe_energy: 📊 Tutti i {total_years} anni caricati da cache, 0 chiamate API")
            
            # Restituisci formato aggregato
            if all_timeframes:
                return {
                    'timeFrameEnergy': {
                        'unit': 'Wh',
                        'years': all_timeframes
                    }
                }
            return {}
            
        except Exception as e:
            logger.error(f"Errore raccolta site_timeframe_energy smart cache: {e}")
            return {}

