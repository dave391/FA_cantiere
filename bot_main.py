"""
Bot Main - Entry point dell'applicazione di trading automatizzata
Gestisce l'avvio e l'arresto del bot e dello scheduler
"""

import logging
import time
import signal
import sys
from datetime import datetime, timezone

from core.bot_engine import BotManager
from services.scheduler import get_scheduler

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('bot_main')

class BotApplication:
    def __init__(self):
        """Inizializza l'applicazione del bot"""
        self.bot_manager = BotManager()
        self.scheduler = get_scheduler()
        self.running = False
        
        # Configura i gestori di segnali per un arresto pulito
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        
        logger.info("Applicazione bot inizializzata")
    
    def start(self):
        """Avvia l'applicazione del bot"""
        logger.info("Avvio dell'applicazione bot")
        self.running = True
        
        try:
            # Avvia lo scheduler per il bilanciamento del margine
            self.scheduler.start()
            
            # Carica i bot già attivi dal database
            self.bot_manager.load_active_bots()
            
            # Loop principale dell'applicazione
            while self.running:
                # Tieni vivo il thread principale
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"Errore nell'esecuzione dell'applicazione: {str(e)}")
            self.shutdown()
    
    def shutdown(self):
        """Arresta l'applicazione in modo pulito"""
        logger.info("Arresto dell'applicazione bot in corso...")
        
        # Imposta il flag di esecuzione a False
        self.running = False
        
        try:
            # Ferma tutti i bot attivi
            stop_result = self.bot_manager.stop_all_bots()
            logger.info(f"Bot fermati: {stop_result.get('stopped_count', 0)}")
            
            # Ferma lo scheduler
            self.scheduler.stop()
            logger.info("Scheduler fermato")
            
        except Exception as e:
            logger.error(f"Errore durante l'arresto: {str(e)}")
        
        logger.info("Applicazione bot arrestata")
    
    def handle_shutdown(self, signum, frame):
        """Gestisce i segnali di arresto"""
        logger.info(f"Segnale di arresto ricevuto: {signum}")
        self.shutdown()
        sys.exit(0)
    
    def start_bot_for_user(self, user_id, config_name=None):
        """Avvia un bot per un utente specifico"""
        result = self.bot_manager.start_bot(user_id, config_name)
        
        if result["success"]:
            logger.info(f"Bot avviato con successo per l'utente {user_id}")
            return {"success": True, "bot_id": result["bot_id"]}
        else:
            logger.error(f"Errore nell'avvio del bot per l'utente {user_id}: {result.get('error')}")
            return {"success": False, "error": result.get("error")}
    
    def stop_bot_for_user(self, bot_id):
        """Ferma un bot specifico"""
        result = self.bot_manager.stop_bot(bot_id)
        
        if result["success"]:
            logger.info(f"Bot {bot_id} fermato con successo")
            return {"success": True}
        else:
            logger.error(f"Errore nell'arresto del bot {bot_id}: {result.get('error')}")
            return {"success": False, "error": result.get("error")}


# Entry point dell'applicazione
if __name__ == "__main__":
    app = BotApplication()
    
    # Se vengono passati parametri da riga di comando
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "start":
            # Avvia un bot specifico se specificato l'utente
            if len(sys.argv) > 2:
                user_id = sys.argv[2]
                config_name = sys.argv[3] if len(sys.argv) > 3 else None
                
                result = app.start_bot_for_user(user_id, config_name)
                if result["success"]:
                    print(f"Bot avviato per l'utente {user_id}: {result['bot_id']}")
                else:
                    print(f"Errore: {result['error']}")
                
                # Non avviare il loop dell'applicazione
                sys.exit(0)
            
        elif command == "stop":
            # Ferma un bot specifico
            if len(sys.argv) > 2:
                bot_id = sys.argv[2]
                
                result = app.stop_bot_for_user(bot_id)
                if result["success"]:
                    print(f"Bot {bot_id} fermato con successo")
                else:
                    print(f"Errore: {result['error']}")
                
                # Non avviare il loop dell'applicazione
                sys.exit(0)
    
    # Avvia l'applicazione nel loop principale
    app.start() 