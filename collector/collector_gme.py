#!/usr/bin/env python3
"""Collector GME - Download prezzi PUN da GME API"""

import requests
import logging
import os
import base64
import zipfile
import io
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from scheduler.scheduler_loop import SchedulerLoop, SourceType

logger = logging.getLogger(__name__)

class CollectorGME:
    """Collector per prezzi PUN da GME API"""
    
    BASE_URL = "https://api.mercatoelettrico.org/request/api/v1"
    
    def __init__(self, scheduler: Optional[SchedulerLoop] = None):
        self.username = os.getenv('GME_USERNAME')
        self.password = os.getenv('GME_PASSWORD')
        self.token = None
        self.token_expiry = None
        self.scheduler = scheduler
        
        if not self.username or not self.password:
            logger.warning("Credenziali GME non configurate. Impostare GME_USERNAME e GME_PASSWORD in .env")
            
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'SolarEdge-ScanWriter/1.0',
            'Accept': 'application/json'
        })

    def _get_token(self) -> Optional[str]:
        """Ottiene il token JWT per l'autenticazione"""
        if self.token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.token
            
        if not self.username or not self.password:
            logger.error("Credenziali mancanti per autenticazione GME")
            return None
            
        try:
            # Endpoint di autenticazione GME
            auth_url = f"{self.BASE_URL}/Auth"
            
            # GME API richiede "Login" e "Password" come chiavi JSON
            payload = {
                "Login": self.username,
                "Password": self.password
            }
            
            response = self._session.post(auth_url, json=payload, timeout=30)
            response.raise_for_status()
            
            # La risposta contiene un JSON con campo "token"
            try:
                data = response.json()
                if isinstance(data, dict) and 'token' in data:
                    token = data['token']
                else:
                    # Fallback: prova a leggere come testo
                    token = response.text.strip().replace('"', '')
            except:
                # Se non è JSON, prova come testo semplice
                token = response.text.strip().replace('"', '')
                
            if token:
                self.token = token
                # Imposta scadenza (es. 23 ore per sicurezza, o parsa il JWT)
                self.token_expiry = datetime.now() + timedelta(hours=23)
                logger.info("Autenticazione GME riuscita")
                return token
            else:
                logger.error("Token non trovato nella risposta di autenticazione")
                return None
                
        except Exception as e:
            logger.error(f"Errore autenticazione GME: {e}")
            return None

    def _call_api_with_timing(self, operation_callable):
        """Esegue chiamata API con scheduler timing se disponibile
        
        Args:
            operation_callable: Funzione che esegue la chiamata HTTP
            
        Returns:
            Risultato dell'operazione
        """
        if self.scheduler:
            return self.scheduler.execute_with_timing(SourceType.GME, operation_callable, cache_hit=False)
        else:
            return operation_callable()

    def collect(self, date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
        """
        Scarica i prezzi PUN per una data specifica o un range di date
        
        Args:
            date: Data inizio (default: ieri)
            end_date: Data fine (opzionale, per range mensili)
        
        Returns:
            Dict con prezzi orari per il periodo richiesto
        """
        if date is None:
            date = datetime.now() - timedelta(days=1)
        
        if end_date is None:
            end_date = date
            
        date_str = date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        date_param_start = date.strftime('%Y%m%d')
        date_param_end = end_date.strftime('%Y%m%d')

        
        token = self._get_token()
        if not token:
            return {}
            
        try:
            # Endpoint corretto GME API: RequestData (non RequestaData)
            url = f"{self.BASE_URL}/RequestData"
            
            # GME API richiede POST con JSON body
            payload = {
                'Platform': 'PublicMarketResults',
                'Segment': 'MGP',
                'DataName': 'ME_ZonalPrices',
                'IntervalStart': date_param_start,
                'IntervalEnd': date_param_end,
                'Attributes': {}
            }

            
            headers = {
                'Authorization': f"Bearer {token}",
                'Content-Type': 'application/json'
            }
            
            if date_str == end_date_str:
                logger.info(f"[*] Download dati GME per {date_str}...")
            else:
                logger.info(f"[*] Download dati GME per {date_str} → {end_date_str}...")
            
            # Chiamata API con rate limiting
            def _http_call():
                return self._session.post(url, json=payload, headers=headers, timeout=60)
            
            response = self._call_api_with_timing(_http_call)

            response.raise_for_status()
            
            # La risposta è un JSON con campo "contentResponse" contenente base64
            try:
                response_data = response.json()
                if isinstance(response_data, dict) and 'contentResponse' in response_data:
                    content_b64 = response_data['contentResponse']
                else:
                    # Fallback: prova come testo diretto
                    content_b64 = response.text.strip().replace('"', '')
            except:
                # Se non è JSON, prova come testo semplice
                content_b64 = response.text.strip().replace('"', '')

            try:
                zip_content = base64.b64decode(content_b64)
            except Exception as e:
                logger.error(f"Errore decodifica Base64: {e}")
                logger.debug(f"Content preview: {content_b64[:200]}...")
                return {}
                
            # Apri lo ZIP
            all_prices = []
            
            with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
                file_list = zf.namelist()
                logger.debug(f"ZIP Content: {file_list}")
                
                # Cerca il file JSON o XML all'interno
                for filename in file_list:
                    if filename.endswith('.json'):
                        with zf.open(filename) as f:
                            json_data = json.load(f)
                            logger.debug(f"JSON file found: {filename}")
                            result = self._parse_json(json_data)
                            if result and 'prices' in result:
                                all_prices.extend(result['prices'])
            
            if all_prices:
                all_prices.sort(key=lambda x: (x['date'], x['hour']))
                return {
                    'date': date_str,
                    'prices': all_prices,
                    'source': 'GME',
                    'market': 'MGP'
                }
                            
            logger.warning(f"Nessun file JSON/XML trovato nello ZIP per {date_str}")
            return {}
            
        except Exception as e:
            logger.error(f"Errore download dati GME per {date_str}: {e}")
            if 'response' in locals() and response.text:
                 logger.debug(f"Response content: {response.text[:500]}")
            return {}

    def _parse_json(self, json_data: Any) -> Dict[str, Any]:
        """Parsa il JSON restituito da GME"""
        try:
            prices = []
            
            # Il JSON GME può essere una lista diretta o un dizionario
            if isinstance(json_data, list):
                price_data = json_data
            elif isinstance(json_data, dict):
                # Cerca l'array di prezzi nel dizionario
                price_data = json_data.get('ME_ZonalPrices', [])
                if not price_data:
                    price_data = json_data.get('data', [])
                
                if not price_data:
                    logger.debug(f"JSON Keys: {list(json_data.keys())}")
                    # Prova a cercare ricorsivamente o stampa un sample
                    logger.debug(f"JSON Sample (first 200 chars): {str(json_data)[:200]}")
            else:
                logger.error(f"Formato JSON non riconosciuto: {type(json_data)}")
                return {}
            
            for i, item in enumerate(price_data):
                if i == 0:
                    logger.debug(f"First item sample: {item}")
                    
                try:
                    zone = item.get('Zone') or item.get('zone')
                    if zone != 'PUN':
                        continue
                        
                    hour = item.get('Hour') or item.get('hour')
                    price_mwh = item.get('Price') or item.get('price') or item.get('PunPrice')
                    date_val = item.get('Date') or item.get('date') or item.get('FlowDate')
                    
                    if hour is not None and price_mwh is not None:
                        hour = int(hour)
                        price_mwh = float(str(price_mwh).replace(',', '.'))
                        price_kwh = price_mwh / 1000.0
                        
                        # Formatta data da YYYYMMDD a YYYY-MM-DD
                        if date_val:
                            date_str = str(date_val)
                            if len(date_str) == 8:
                                date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
                            else:
                                date_fmt = date_str
                        else:
                            continue
                        
                        prices.append({
                            'hour': hour,
                            'pun_mwh': price_mwh,
                            'pun_kwh': price_kwh,
                            'date': date_fmt
                        })
                except Exception as e:
                    logger.debug(f"Errore parsing item JSON: {e}")
                    continue
                    
            if prices:
                # Non sortiamo qui perché lo facciamo alla fine di collect
                return {
                    'prices': prices,
                    'source': 'GME',
                    'market': 'MGP'
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Errore parsing JSON GME: {e}")
            return {}


    def collect_month(self, year: int, month: int) -> Dict[str, Any]:
        """
        Scarica tutti i prezzi PUN per un mese intero con una singola chiamata API
        
        Args:
            year: Anno (es. 2024)
            month: Mese (1-12)
        
        Returns:
            Dict con tutti i prezzi orari del mese
        """
        import calendar
        
        # Primo e ultimo giorno del mese
        first_day = datetime(year, month, 1)
        last_day_num = calendar.monthrange(year, month)[1]
        last_day = datetime(year, month, last_day_num)
        
        # Usa collect() con range
        return self.collect(first_day, last_day)

    def close(self):
        self._session.close()
