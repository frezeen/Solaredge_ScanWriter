import calendar
from datetime import datetime, timedelta
from collector.collector_api import CollectorAPI
from utils.color_logger import color

class HistoryManager:
    """Gestisce il download dello storico completo con suddivisione mensile"""
    
    def __init__(self, log, cache, config):
        """Inizializza HistoryManager
        
        Args:
            log: Logger instance
            cache: Cache manager instance  
            config: Configuration dictionary
        """
        self.log = log
        self.cache = cache
        self.config = config
        self.collector = None
    
    def run(self) -> int:
        """Esegue modalità history: scarica storico completo con suddivisione mensile"""
        self.log.info(color.bold("📜 Avvio modalità History - Scaricamento storico completo"))
        self.log.info(color.success("✅ ABILITANDO CACHE per history mode - skip mesi già scaricati"))
        
        # Inizializza collector CON cache per evitare chiamate API duplicate
        self.collector = CollectorAPI(cache=self.cache, scheduler=None)
        
        # Inizializza variabili per gestione return
        interrupted = False
        failed_count = 0
        
        try:
            # 1. Recupera range temporale dall'API
            date_range_result = self._get_date_range_from_api()
            if not date_range_result:
                return 1
            start_date, end_date = date_range_result
            
            # 2. Genera lista di mesi da processare
            months = self._generate_months_list(start_date, end_date)
            
            # 3. Processa tutti i mesi
            success_count, failed_count, web_success, web_failed, interrupted, web_executed, gme_success, gme_failed = \
                self._process_months(months, end_date)
            
            # 4. Stampa statistiche finali
            self._print_final_statistics(success_count, failed_count, web_success, web_failed,
                                       interrupted, web_executed, len(months), gme_success, gme_failed)
            
        finally:
            # Chiudi sessione HTTP per liberare risorse
            if self.collector:
                self.collector.close()
        
        # Ritorna 0 se interrotto pulitamente o completato con successo
        if interrupted:
            return 0  # Uscita pulita per interruzione
        else:
            return 0 if failed_count == 0 else 1
    
    def _get_date_range_from_api(self):
        """Recupera range temporale dall'API dataPeriod"""
        self.log.info(color.info("🔍 Recupero range temporale da API dataPeriod..."))
        date_range = self.collector.get_production_date_range()
        
        if not date_range:
            self.log.error(color.error("❌ Impossibile recuperare range temporale"))
            return None
        
        start_date = date_range['start']
        end_date = date_range['end']
        self.log.info(color.highlight(f"📅 Range temporale: {start_date} → {end_date}"))
        
        return start_date, end_date
    
    def _generate_months_list(self, start_date: str, end_date: str):
        """Genera lista di mesi da processare"""
        months = []
        current = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        while current <= end:
            year = current.year
            month = current.month
            
            # Primo giorno del mese
            first_day = datetime(year, month, 1)
            
            # Ultimo giorno del mese
            last_day_num = calendar.monthrange(year, month)[1]
            last_day = datetime(year, month, last_day_num)
            
            # Non superare end_date
            if last_day > end:
                last_day = end
            
            months.append({
                'start': first_day.strftime('%Y-%m-%d'),
                'end': last_day.strftime('%Y-%m-%d'),
                'label': first_day.strftime('%Y-%m')
            })
            
            # Passa al mese successivo
            if month == 12:
                current = datetime(year + 1, 1, 1)
            else:
                current = datetime(year, month + 1, 1)
        
        self.log.info(color.highlight(f"📊 Totale mesi da processare: {len(months)}"))
        return months
    
    def _process_months(self, months, end_date: str):
        """Processa tutti i mesi con gestione interruzioni"""
        from flows.api_flow import run_api_flow
        from flows.web_flow import run_web_flow
        
        success_count = 0
        failed_count = 0
        web_success = False
        web_failed = False
        interrupted = False
        web_executed = False
        gme_success_count = 0
        gme_failed_count = 0
        
        try:
            # Processa tutti i mesi
            for idx, month_data in enumerate(months, 1):
                self.log.info(color.info(f"🔄 [{idx}/{len(months)}] Processando {month_data['label']}: {month_data['start']} → {month_data['end']}"))
                
                try:
                    # 1. API Flow con date personalizzate (sempre) - CON CACHE
                    self.log.info(color.dim(f"   🔄 API flow per {month_data['label']} (CON CACHE)"))
                    api_result = run_api_flow(self.log, self.cache, self.config, 
                                             start_date=month_data['start'], 
                                             end_date=month_data['end'])
                    
                    # 1b. GME Flow (Nuovo) - Eseguito in parallelo logico
                    try:
                        year_str, month_str = month_data['label'].split('-')
                        year, month = int(year_str), int(month_str)
                        
                        # Import locale per evitare cicli
                        from flows.gme_flow import run_gme_month_flow
                        
                        # Esegui flow GME (gestisce internamente cache check)
                        gme_result = run_gme_month_flow(self.log, self.cache, self.config, year, month)
                        
                        if gme_result == 0:
                            gme_success_count += 1
                        else:
                            gme_failed_count += 1
                        
                    except Exception as e:
                        self.log.warning(color.warning(f"   ⚠️ GME {month_data['label']} errore: {e}"))
                        gme_failed_count += 1

                    
                    # 2. Web Flow solo per gli ultimi 7 giorni (alla fine)
                    web_result = 0
                    if idx == len(months) and not web_executed:
                        # Calcola gli ultimi 7 giorni dalla data di fine
                        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                        start_dt = end_dt - timedelta(days=6)  # 7 giorni totali (incluso end_date)
                        
                        web_start = start_dt.strftime('%Y-%m-%d')
                        web_end = end_dt.strftime('%Y-%m-%d')
                        
                        self.log.info(color.dim(f"   🔄 Web flow per ultimi 7 giorni: {web_start} → {web_end}"))
                        try:
                            web_result = run_web_flow(self.log, self.cache, self.config, start_date=web_start, end_date=web_end)
                            web_executed = True
                            if web_result == 0:
                                web_success = True
                            else:
                                web_failed = True
                        except Exception as web_error:
                            self.log.error(color.error(f"   ❌ Web flow fallito: {web_error}"))
                            web_executed = True
                            web_failed = True
                            web_result = 1
                    
                    # Considera successo se API è ok (web è opzionale)
                    if api_result == 0:
                        success_count += 1
                        if web_executed and web_result == 0:
                            self.log.info(color.success(f"   ✅ {month_data['label']} completato (API + Web)"))
                        elif web_executed:
                            self.log.info(color.warning(f"   ✅ {month_data['label']} completato (API ok, Web warning)"))
                        else:
                            self.log.info(color.success(f"   ✅ {month_data['label']} completato (API)"))
                    else:
                        failed_count += 1
                        self.log.error(color.error(f"   ❌ {month_data['label']} fallito (API: {api_result})"))
                        
                except KeyboardInterrupt:
                    # Propaga l'interruzione al livello superiore
                    raise
                except Exception as e:
                    failed_count += 1
                    self.log.error(color.error(f"   ❌ Errore processando {month_data['label']}: {e}"))
                    
        except KeyboardInterrupt:
            interrupted = True
            self.log.info(color.warning("🛑 Interruzione richiesta dall'utente (Ctrl+C)"))
            self.log.info(color.dim(f"📊 Processati {success_count + failed_count}/{len(months)} mesi prima dell'interruzione"))
        
        return success_count, failed_count, web_success, web_failed, interrupted, web_executed, gme_success_count, gme_failed_count
    
    def _print_final_statistics(self, success_count, failed_count, web_success, web_failed, 
                               interrupted, web_executed, total_months, gme_success=0, gme_failed=0):
        """Stampa statistiche finali del history mode"""
        self.log.info(color.bold("=" * 60))
        if interrupted:
            self.log.info(color.warning("📈 History Mode Interrotto"))
        else:
            self.log.info(color.success("📈 History Mode Completato"))
            
        # API Stats
        self.log.info(color.success(f"✅ API: {success_count}/{total_months} mesi"))
        if failed_count > 0:
            self.log.info(color.error(f"❌ Fallimenti API: {failed_count}/{total_months}"))
            
        # GME Stats
        self.log.info(color.success(f"✅ GME: {gme_success}/{total_months} mesi"))
        if gme_failed > 0:
            self.log.info(color.error(f"❌ Fallimenti GME: {gme_failed}/{total_months}"))
            
        # Web Stats
        if web_executed:
            if web_success:
                self.log.info(color.success(f"✅ Web: 7/7 giorni"))
            elif web_failed:
                self.log.info(color.error(f"❌ Web: 0/7 giorni (fallito)"))
        
        if interrupted:
            self.log.info(color.dim(f"⏸️ Rimanenti: {total_months - success_count - failed_count}/{total_months}"))
            self.log.info(color.highlight("💡 Riavvia con --history per continuare dal punto di interruzione"))
            
        self.log.info(color.bold("=" * 60))

def run_history_flow(log, cache, config) -> int:
    """Wrapper per eseguire HistoryManager come flow standard"""
    return HistoryManager(log, cache, config).run()
