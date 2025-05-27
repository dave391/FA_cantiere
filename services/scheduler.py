"""
Scheduler Service - Gestione dei job schedulati
Gestisce l'esecuzione periodica di operazioni come il bilanciamento del margine.
"""

import logging
import time
import threading
import schedule
from datetime import datetime, timezone
import sys
import os

# Aggiungi la directory radice al path per consentire import relativi
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.mongo_manager import MongoManager
from api.exchange_manager import ExchangeManager
from core.margin_balancer import MarginBalancer

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('scheduler')

class SchedulerService:
    def __init__(self):
        """Inizializza il servizio di scheduling"""
        self.running = False
        self.scheduler_thread = None
        self.db = MongoManager()
        
        logger.info("SchedulerService inizializzato")
    
    def start(self):
        """Avvia il servizio di scheduling"""
        if self.running:
            logger.warning("Scheduler già in esecuzione")
            return False
        
        self.running = True
        
        # Configura i job schedulati
        self._setup_jobs()
        
        # Avvia il thread dello scheduler
        self.scheduler_thread = threading.Thread(target=self._run_scheduler)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        
        logger.info("Scheduler avviato")
        return True
    
    def stop(self):
        """Ferma il servizio di scheduling"""
        if not self.running:
            logger.warning("Scheduler non in esecuzione")
            return False
        
        self.running = False
        
        # Cancella tutti i job schedulati
        schedule.clear()
        
        # Attendi che il thread termini
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5.0)
        
        logger.info("Scheduler fermato")
        return True
    
    def _setup_jobs(self):
        """Configura i job schedulati"""
        # Bilanciamento margine due volte al giorno (12:00 e 00:00)
        schedule.every().day.at("00:00").do(self._run_margin_balance_job)
        schedule.every().day.at("12:00").do(self._run_margin_balance_job)
        
        logger.info("Job schedulati configurati")
    
    def _run_scheduler(self):
        """Esegue il loop dello scheduler"""
        logger.info("Avvio loop dello scheduler")
        
        while self.running:
            try:
                # Esegui i job schedulati
                schedule.run_pending()
                
                # Dormi per un intervallo breve per non sovraccaricare la CPU
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Errore nel loop dello scheduler: {str(e)}")
                time.sleep(5)  # Attendi un po' prima di riprovare
    
    def _run_margin_balance_job(self):
        """Esegue il job di bilanciamento margine per tutti gli utenti attivi"""
        logger.info("Esecuzione job di bilanciamento margine")
        
        try:
            # Recupera tutti i bot attivi
            active_bots = self.db.bot_status.find({"status": "running"})
            
            for bot in active_bots:
                user_id = bot.get("user_id")
                bot_id = bot.get("bot_id")
                config_name = bot.get("config_name")
                
                logger.info(f"Bilanciamento margine per utente {user_id} (bot {bot_id})")
                
                try:
                    # Carica la configurazione del bot
                    configs = self.db.get_bot_configs(user_id)
                    config = next((c for c in configs if c.get("config_name") == config_name), None)
                    
                    if not config:
                        logger.warning(f"Configurazione {config_name} non trovata per utente {user_id}")
                        continue
                    
                    # Inizializza ExchangeManager e MarginBalancer
                    exchange = ExchangeManager(user_id)
                    balancer = MarginBalancer(user_id, config, self.db, exchange)
                    
                    # Esegui il bilanciamento
                    result = balancer.balance_margins()
                    
                    if result["success"] and result.get("balanced", False):
                        logger.info(
                            f"Bilanciamento completato per utente {user_id}: "
                            f"{result.get('amount', 0)} USDT da {result.get('source_exchange')} "
                            f"a {result.get('target_exchange')}"
                        )
                    elif result["success"]:
                        logger.info(f"Bilanciamento non necessario per utente {user_id}: {result.get('reason')}")
                    else:
                        logger.error(f"Errore nel bilanciamento per utente {user_id}: {result.get('error')}")
                
                except Exception as e:
                    logger.error(f"Errore nel bilanciamento per utente {user_id}: {str(e)}")
                    continue
            
            logger.info("Job di bilanciamento margine completato")
            
        except Exception as e:
            logger.error(f"Errore nell'esecuzione del job di bilanciamento margine: {str(e)}")
    
    def add_custom_job(self, job_func, schedule_time):
        """
        Aggiunge un job personalizzato allo scheduler
        
        Args:
            job_func: Funzione da eseguire
            schedule_time: Orario di esecuzione (formato "HH:MM")
        """
        schedule.every().day.at(schedule_time).do(job_func)
        logger.info(f"Job personalizzato aggiunto con orario {schedule_time}")


# Singleton per lo scheduler
_scheduler_instance = None

def get_scheduler():
    """Restituisce l'istanza singleton dello scheduler"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SchedulerService()
    return _scheduler_instance 