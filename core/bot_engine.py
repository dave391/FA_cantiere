"""
Bot Engine - Motore semplificato del sistema semi-automatico
Data: 30/07/2024
"""

import logging
import time
from datetime import datetime, timezone

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('bot_engine')

class BotEngine:
    def __init__(self, user_id, config, db, exchange):
        """
        Inizializza il motore del bot semplificato
        
        Args:
            user_id: ID dell'utente
            config: Configurazione del bot
            db: Istanza di database (può essere None)
            exchange: Istanza di exchange (può essere None)
        """
        self.user_id = user_id
        self.config = config
        self.db = db
        self.exchange = exchange
        
        # Stato del bot
        self.running = False
        self.start_time = None
        self.last_activity = None
        
        logger.info(f"BotEngine inizializzato per l'utente {user_id}")
    
    def start(self):
        """Avvia il motore del bot"""
        if self.running:
            logger.warning(f"Bot già in esecuzione per l'utente {self.user_id}")
            return False
        
        try:
            self.running = True
            self.start_time = datetime.now(timezone.utc)
            self.last_activity = self.start_time
            
            logger.info(f"Bot avviato per l'utente {self.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Errore nell'avvio del bot: {str(e)}")
            self.running = False
            return False
    
    def stop(self):
        """Ferma il motore del bot"""
        if not self.running:
            logger.warning(f"Bot non in esecuzione per l'utente {self.user_id}")
            return False
        
        try:
            self.running = False
            self.last_activity = datetime.now(timezone.utc)
            
            logger.info(f"Bot fermato per l'utente {self.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Errore nell'arresto del bot: {str(e)}")
            return False
    
    def get_status(self):
        """Restituisce lo stato attuale del bot"""
        return {
            "user_id": self.user_id,
            "running": self.running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "uptime_seconds": (datetime.now(timezone.utc) - self.start_time).total_seconds() if self.start_time else 0
        }
    
    def update_activity(self):
        """Aggiorna il timestamp dell'ultima attività"""
        self.last_activity = datetime.now(timezone.utc)
        return True 