"""
Bot Main - Il "cervello" centrale del sistema automatizzato
Data: 30/07/2024
"""

import logging
import time
import threading
import schedule
from datetime import datetime, timezone
import os
import sys
from dotenv import load_dotenv

from core.entry_manager import EntryManager
from core.risk_monitor import RiskMonitor
from core.emergency_closer import EmergencyCloser
from core.cycle_manager import CycleManager
from core.margin_balancer import MarginBalancer
from core.bot_engine import BotEngine

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_log.txt"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('bot_main')

class TradingSystem:
    def __init__(self):
        """Inizializza il sistema di trading automatizzato"""
        self.bot_attivo = False
        self.posizioni_aperte = []
        self.config = None
        self.user_id = None
        self.threads = []
        self.stop_event = threading.Event()
        
        # Carica le variabili d'ambiente
        load_dotenv()
        
        # Inizializza database e exchange manager
        self.db = None  # In futuro qui ci sarà la connessione al database
        self.exchange = None  # In futuro qui ci sarà l'exchange manager
        
        logger.info("Sistema di Trading inizializzato")
    
    def start_bot(self, config_utente):
        """
        Riceve configurazione da app.py e avvia tutto il sistema
        
        Args:
            config_utente: Configurazione fornita dall'utente
        
        Returns:
            dict: Risultato dell'avvio del bot
        """
        try:
            # 1. Salva configurazione
            self.config = config_utente
            self.user_id = config_utente.get("user_id", "default_user")
            
            logger.info(f"Avvio bot per utente {self.user_id}")
            logger.info(f"Configurazione: {self.config}")
            
            # Imposta il bot come attivo
            self.bot_attivo = True
            
            # 2. Inizializza i componenti del sistema
            self._inizializza_componenti()
            
            # 3. Apri posizioni iniziali (UNA VOLTA)
            result = self.apri_posizioni_iniziali()
            
            if not result["success"]:
                logger.error(f"Errore nell'apertura delle posizioni iniziali: {result.get('error', 'Errore sconosciuto')}")
                return {
                    "success": False,
                    "error": f"Errore nell'apertura delle posizioni iniziali: {result.get('error', 'Errore sconosciuto')}"
                }
            
            # 4. Avvia monitoraggio continuo
            self.avvia_monitoraggio()
            
            # 5. Avvia scheduler bilanciamento
            self.avvia_scheduler()
            
            logger.info(f"Bot avviato con successo per utente {self.user_id}")
            
            return {
                "success": True,
                "message": "Bot avviato con successo",
                "user_id": self.user_id,
                "positions": self.posizioni_aperte
            }
            
        except Exception as e:
            logger.error(f"Errore nell'avvio del bot: {str(e)}")
            self.bot_attivo = False
            
            return {
                "success": False,
                "error": f"Errore nell'avvio del bot: {str(e)}"
            }
    
    def _inizializza_componenti(self):
        """Inizializza i componenti del sistema di trading"""
        try:
            # Inizializza i componenti core
            self.entry_manager = EntryManager(
                user_id=self.user_id,
                config=self.config,
                db=self.db,
                exchange=self.exchange
            )
            
            self.risk_monitor = RiskMonitor(
                user_id=self.user_id,
                config=self.config,
                db=self.db,
                exchange=self.exchange
            )
            
            self.emergency_closer = EmergencyCloser(
                user_id=self.user_id,
                config=self.config,
                db=self.db,
                exchange=self.exchange
            )
            
            self.cycle_manager = CycleManager(
                user_id=self.user_id,
                config=self.config,
                db=self.db,
                exchange=self.exchange
            )
            
            self.margin_balancer = MarginBalancer(
                user_id=self.user_id,
                config=self.config,
                db=self.db,
                exchange=self.exchange
            )
            
            self.bot_engine = BotEngine(
                user_id=self.user_id,
                config=self.config,
                db=self.db,
                exchange=self.exchange
            )
            
            logger.info("Componenti del sistema inizializzati")
            
        except Exception as e:
            logger.error(f"Errore nell'inizializzazione dei componenti: {str(e)}")
            raise
    
    def apri_posizioni_iniziali(self):
        """Apre le posizioni iniziali su entrambi gli exchange"""
        try:
            logger.info("Apertura posizioni iniziali")
            
            result = self.entry_manager.open_initial_positions()
            
            if result["success"]:
                logger.info("Posizioni iniziali aperte con successo")
                self.posizioni_aperte = result.get("positions", [])
                
                # Salva informazioni sulle posizioni per uso futuro
                for pos in self.posizioni_aperte:
                    logger.info(f"Posizione aperta: {pos['exchange']} {pos['side']} {pos['size']} {pos['symbol']}")
                
                return {
                    "success": True,
                    "positions": self.posizioni_aperte
                }
            else:
                logger.error(f"Errore nell'apertura delle posizioni iniziali: {result.get('error', 'Errore sconosciuto')}")
                return result
                
        except Exception as e:
            logger.error(f"Errore nell'apertura delle posizioni iniziali: {str(e)}")
            return {
                "success": False,
                "error": f"Errore nell'apertura delle posizioni iniziali: {str(e)}"
            }
    
    def avvia_monitoraggio(self):
        """Avvia il thread di monitoraggio delle posizioni"""
        try:
            logger.info("Avvio monitoraggio continuo")
            
            # Crea un thread per il monitoraggio continuo
            monitor_thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True
            )
            
            monitor_thread.start()
            self.threads.append(monitor_thread)
            
            logger.info("Thread di monitoraggio avviato")
            
        except Exception as e:
            logger.error(f"Errore nell'avvio del monitoraggio: {str(e)}")
            raise
    
    def _monitor_loop(self):
        """Loop di monitoraggio che controlla le posizioni ogni 10 secondi"""
        logger.info("Loop di monitoraggio avviato")
        
        while self.bot_attivo and not self.stop_event.is_set():
            try:
                # Controlla il livello di rischio delle posizioni
                risk_status = self.risk_monitor.check_positions()
                
                if risk_status["high_risk_detected"]:
                    logger.warning(f"Rilevato alto rischio: {risk_status['details']}")
                    
                    # Chiudi le posizioni a rischio
                    risky_positions = risk_status.get("risky_positions", [])
                    
                    if risky_positions:
                        logger.info(f"Chiusura di {len(risky_positions)} posizioni a rischio")
                        
                        for pos_data in risky_positions:
                            position = pos_data["position"]
                            risk_info = pos_data["risk_status"]
                            
                            logger.info(f"Chiusura posizione a rischio: {position['exchange']} {position['symbol']} "
                                       f"(Rischio: {risk_info['risk_level']:.1f}%)")
                            
                            # Chiudi la posizione
                            close_result = self.emergency_closer.close_position(position)
                            
                            if close_result["success"]:
                                logger.info(f"Posizione chiusa con successo: {position['exchange']} {position['symbol']}")
                            else:
                                logger.error(f"Errore nella chiusura della posizione: {close_result.get('error', 'Errore sconosciuto')}")
                        
                        # Riapri nuove posizioni
                        logger.info("Riapertura di nuove posizioni dopo chiusura per rischio")
                        reopen_result = self.cycle_manager.reopen_positions()
                        
                        if reopen_result["success"]:
                            logger.info("Nuove posizioni riaperte con successo")
                            self.posizioni_aperte = reopen_result.get("positions", [])
                        else:
                            logger.error(f"Errore nella riapertura delle posizioni: {reopen_result.get('error', 'Errore sconosciuto')}")
                
                # Aspetta 10 secondi prima del prossimo controllo
                time.sleep(10)
                
            except Exception as e:
                logger.error(f"Errore nel loop di monitoraggio: {str(e)}")
                time.sleep(30)  # In caso di errore, aspetta più a lungo
    
    def avvia_scheduler(self):
        """Avvia lo scheduler per il bilanciamento del margine"""
        try:
            logger.info("Avvio scheduler per bilanciamento margine")
            
            # Programma il bilanciamento del margine alle 12:00 e 00:00
            schedule.every().day.at("12:00").do(self._esegui_bilanciamento)
            schedule.every().day.at("00:00").do(self._esegui_bilanciamento)
            
            # Crea un thread per lo scheduler
            scheduler_thread = threading.Thread(
                target=self._scheduler_loop,
                daemon=True
            )
            
            scheduler_thread.start()
            self.threads.append(scheduler_thread)
            
            logger.info("Scheduler avviato")
            
        except Exception as e:
            logger.error(f"Errore nell'avvio dello scheduler: {str(e)}")
            raise
    
    def _scheduler_loop(self):
        """Loop dello scheduler che controlla e esegue i job programmati"""
        logger.info("Loop dello scheduler avviato")
        
        while self.bot_attivo and not self.stop_event.is_set():
            try:
                # Esegui i job programmati
                schedule.run_pending()
                
                # Aspetta 1 minuto prima del prossimo controllo
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Errore nel loop dello scheduler: {str(e)}")
                time.sleep(300)  # In caso di errore, aspetta 5 minuti
    
    def _esegui_bilanciamento(self):
        """Esegue il bilanciamento del margine tra gli exchange"""
        try:
            logger.info("Esecuzione bilanciamento margine programmato")
            
            if self.bot_attivo:
                result = self.margin_balancer.balance_margins()
                
                if result["success"] and result.get("balanced", False):
                    logger.info(f"Bilanciamento margine completato: {result.get('amount', 0)} USDT "
                               f"da {result.get('source_exchange', '')} a {result.get('target_exchange', '')}")
                else:
                    reason = result.get("reason", "Nessun motivo specificato")
                    logger.info(f"Bilanciamento non necessario: {reason}")
            else:
                logger.info("Bot non attivo, bilanciamento margine saltato")
            
        except Exception as e:
            logger.error(f"Errore nell'esecuzione del bilanciamento: {str(e)}")
    
    def stop_bot(self):
        """Ferma il bot e tutte le attività in background"""
        try:
            logger.info(f"Arresto bot per utente {self.user_id}")
            
            # Imposta il flag di arresto
            self.bot_attivo = False
            self.stop_event.set()
            
            # Attendi la terminazione dei thread
            for thread in self.threads:
                thread.join(timeout=5.0)
            
            logger.info("Bot arrestato con successo")
            
            return {
                "success": True,
                "message": "Bot arrestato con successo"
            }
            
        except Exception as e:
            logger.error(f"Errore nell'arresto del bot: {str(e)}")
            
            return {
                "success": False,
                "error": f"Errore nell'arresto del bot: {str(e)}"
            }
    
    def get_status(self):
        """Restituisce lo stato attuale del bot"""
        try:
            # Recupera informazioni aggiornate sulle posizioni
            positions_result = self.exchange.get_open_positions() if self.exchange else {"success": False, "positions": []}
            
            active_positions = positions_result.get("positions", []) if positions_result.get("success", False) else []
            
            return {
                "success": True,
                "active": self.bot_attivo,
                "user_id": self.user_id,
                "positions": active_positions,
                "num_positions": len(active_positions),
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Errore nel recupero dello stato del bot: {str(e)}")
            
            return {
                "success": False,
                "error": f"Errore nel recupero dello stato del bot: {str(e)}"
            }


# Entry point dell'applicazione
if __name__ == "__main__":
    app = TradingSystem()
    
    # Se vengono passati parametri da riga di comando
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "start":
            # Avvia un bot specifico se specificato l'utente
            if len(sys.argv) > 2:
                user_id = sys.argv[2]
                config_name = sys.argv[3] if len(sys.argv) > 3 else None
                
                result = app.start_bot(config_name)
                if result["success"]:
                    print(f"Bot avviato per l'utente {user_id}: {result['message']}")
                else:
                    print(f"Errore: {result['error']}")
                
                # Non avviare il loop dell'applicazione
                sys.exit(0)
            
        elif command == "stop":
            # Ferma il bot
            result = app.stop_bot()
            if result["success"]:
                print(f"Bot arrestato con successo: {result['message']}")
            else:
                print(f"Errore: {result['error']}")
            
            # Non avviare il loop dell'applicazione
            sys.exit(0)
    
    # Avvia l'applicazione nel loop principale
    app.start() 