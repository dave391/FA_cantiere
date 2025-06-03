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
import uuid
from dotenv import load_dotenv

from core.entry_manager import EntryManager
from core.risk_monitor import RiskMonitor
from core.emergency_closer import EmergencyCloser
from core.cycle_manager import CycleManager
from core.margin_balancer import MarginBalancer
from core.bot_engine import BotEngine
from database.mongo_manager import MongoManager
from api.exchange_manager import ExchangeManager

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
        self.bot_id = None
        
        # Carica le variabili d'ambiente
        load_dotenv()
        
        # Inizializza database e exchange manager
        try:
            self.db = MongoManager()
            logger.info("Database inizializzato")
        except Exception as e:
            logger.error(f"Errore inizializzazione database: {e}")
            self.db = None
        
        self.exchange = None  # Sarà inizializzato in base all'utente
        
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
            
            # Genera un ID univoco per il bot
            self.bot_id = f"bot_{uuid.uuid4().hex[:8]}"
            
            logger.info(f"Avvio bot {self.bot_id} per utente {self.user_id}")
            logger.info(f"Configurazione: {self.config}")
            
            # Imposta il bot come attivo
            self.bot_attivo = True
            
            # 2. Inizializza i componenti del sistema
            self._inizializza_componenti()
            
            # 3. Registra l'avvio del bot nel database
            if self.db:
                self.db.start_bot(self.user_id, self.bot_id, config_utente.get("config_name", "funding_arbitrage"))
            
            # 4. Apri posizioni iniziali (UNA VOLTA)
            result = self.apri_posizioni_iniziali()
            
            if not result["success"]:
                logger.error(f"Errore nell'apertura delle posizioni iniziali: {result.get('error', 'Errore sconosciuto')}")
                return {
                    "success": False,
                    "error": f"Errore nell'apertura delle posizioni iniziali: {result.get('error', 'Errore sconosciuto')}"
                }
            
            # 5. Avvia monitoraggio continuo
            self.avvia_monitoraggio()
            
            # 6. Avvia scheduler bilanciamento
            self.avvia_scheduler()
            
            logger.info(f"Bot avviato con successo per utente {self.user_id}")
            
            return {
                "success": True,
                "message": "Bot avviato con successo",
                "user_id": self.user_id,
                "bot_id": self.bot_id,
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
            # Inizializza exchange per l'utente specifico
            try:
                if self.db:
                    self.exchange = ExchangeManager(self.user_id, self.db)
                    logger.info(f"Exchange manager inizializzato per utente {self.user_id}")
                else:
                    # Fallback per modalità senza database
                    self.exchange = ExchangeManager(self.user_id)
                    logger.info("Exchange manager inizializzato in modalità legacy")
            except Exception as e:
                logger.error(f"Errore inizializzazione exchange: {e}")
                self.exchange = None
                logger.warning("Usando modalità senza exchange (simulazione)")
            
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
                    
                    # Salva nel database se disponibile
                    if self.db:
                        position_data = {
                            "position_id": pos.get("position_id", f"pos_{uuid.uuid4().hex[:8]}"),
                            "user_id": self.user_id,
                            "bot_id": self.bot_id,
                            "exchange": pos["exchange"],
                            "symbol": pos["symbol"],
                            "side": pos["side"],
                            "size": pos["size"],
                            "entry_price": pos.get("entry_price", 0),
                            "unrealized_pnl": pos.get("unrealized_pnl", 0)
                        }
                        self.db.save_position(position_data)
                
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
                "error": f"Errore nell'apertura delle posizioni: {str(e)}"
            }
    
    def avvia_monitoraggio(self):
        """Avvia il thread di monitoraggio continuo"""
        try:
            # Crea un nuovo thread per il monitoraggio continuo
            monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.threads.append(monitor_thread)
            
            # Avvia il thread
            monitor_thread.start()
            
            logger.info("Thread di monitoraggio avviato")
            
        except Exception as e:
            logger.error(f"Errore nell'avvio del monitoraggio: {str(e)}")
    
    def _monitor_loop(self):
        """Loop di monitoraggio continuo in un thread separato"""
        try:
            logger.info("Loop di monitoraggio avviato")
            
            # Imposta intervallo di monitoraggio (in secondi)
            monitor_interval = 30
            
            # Loop principale
            while self.bot_attivo and not self.stop_event.is_set():
                try:
                    # 1. Controlla i rischi
                    risk_status = self.risk_monitor.check_risks()
                    
                    if risk_status.get("emergency", False):
                        logger.warning(f"Situazione di emergenza rilevata: {risk_status.get('reason', 'Rischio sconosciuto')}")
                        
                        # Chiusura di emergenza
                        emergency_result = self.emergency_closer.close_positions()
                        
                        if emergency_result.get("success", False):
                            logger.info("Posizioni chiuse con successo in emergenza")
                            
                            if self.db:
                                # Registra l'evento nel database
                                self.db.log_risk_event(
                                    self.user_id,
                                    "emergency_close",
                                    "critical",
                                    {"reason": risk_status.get("reason", ""), "result": emergency_result}
                                )
                                
                                # Aggiorna lo stato del bot
                                self.db.stop_bot(self.bot_id)
                            
                            # Ferma il bot
                            self.bot_attivo = False
                            self.stop_event.set()
                            break
                        else:
                            logger.error(f"Errore nella chiusura di emergenza: {emergency_result.get('error', 'Errore sconosciuto')}")
                    
                    # 2. Aggiorna prezzi e stato
                    if self.cycle_manager:
                        self.cycle_manager.update_positions()
                    
                    # 3. Aggiorna il database con lo stato corrente
                    if self.db and self.exchange:
                        # Recupera le posizioni aperte
                        positions_result = self.exchange.get_open_positions()
                        
                        if positions_result.get("success", False):
                            positions = positions_result.get("positions", [])
                            
                            # Aggiorna numero posizioni nel database
                            self.db.bot_status.update_one(
                                {"bot_id": self.bot_id},
                                {"$set": {
                                    "positions_count": len(positions),
                                    "last_activity": datetime.now(timezone.utc)
                                }}
                            )
                            
                            # Calcola PnL totale
                            total_pnl = sum([float(p.get("unrealizedPnl", 0)) for p in positions])
                            
                            # Aggiorna PnL nel database
                            self.db.bot_status.update_one(
                                {"bot_id": self.bot_id},
                                {"$set": {"total_pnl": total_pnl}}
                            )
                
                except Exception as e:
                    logger.error(f"Errore nel ciclo di monitoraggio: {str(e)}")
                
                # Attendi il prossimo ciclo
                time.sleep(monitor_interval)
            
            logger.info("Loop di monitoraggio terminato")
            
        except Exception as e:
            logger.error(f"Errore critico nel thread di monitoraggio: {str(e)}")
    
    def avvia_scheduler(self):
        """Avvia lo scheduler per operazioni periodiche"""
        try:
            # Pianifica operazioni periodiche
            schedule.every(4).hours.do(self._esegui_bilanciamento)
            
            # Crea un nuovo thread per lo scheduler
            scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self.threads.append(scheduler_thread)
            
            # Avvia il thread
            scheduler_thread.start()
            
            logger.info("Scheduler avviato")
            
        except Exception as e:
            logger.error(f"Errore nell'avvio dello scheduler: {str(e)}")
    
    def _scheduler_loop(self):
        """Loop per lo scheduler in un thread separato"""
        try:
            logger.info("Loop scheduler avviato")
            
            # Loop principale
            while self.bot_attivo and not self.stop_event.is_set():
                # Esegui job pianificati
                schedule.run_pending()
                
                # Attendi
                time.sleep(60)
            
            logger.info("Loop scheduler terminato")
            
        except Exception as e:
            logger.error(f"Errore critico nel thread dello scheduler: {str(e)}")
    
    def _esegui_bilanciamento(self):
        """Esegue il bilanciamento dei margini tra gli exchange"""
        try:
            logger.info("Esecuzione bilanciamento margini periodico")
            
            if self.margin_balancer:
                result = self.margin_balancer.balance_margins()
                
                if result.get("success", False):
                    logger.info(f"Bilanciamento margini completato: {result.get('message', '')}")
                    
                    # Registra nel database
                    if self.db:
                        self.db.log_margin_balance(
                            self.user_id, 
                            "all", 
                            {"action": "balance", "result": result}
                        )
                else:
                    logger.warning(f"Bilanciamento margini non riuscito: {result.get('error', 'Errore sconosciuto')}")
            
        except Exception as e:
            logger.error(f"Errore nell'esecuzione del bilanciamento: {str(e)}")
    
    def stop_bot(self):
        """Ferma il bot attualmente in esecuzione"""
        try:
            logger.info(f"Arresto bot {self.bot_id} per utente {self.user_id}")
            
            # Imposta il flag di arresto
            self.bot_attivo = False
            self.stop_event.set()
            
            # Chiudi tutte le posizioni aperte
            if self.emergency_closer:
                result = self.emergency_closer.close_positions()
                
                if not result.get("success", False):
                    logger.error(f"Errore nella chiusura delle posizioni: {result.get('error', 'Errore sconosciuto')}")
                    return {
                        "success": False,
                        "error": f"Errore nella chiusura delle posizioni: {result.get('error', 'Errore sconosciuto')}"
                    }
            
            # Attendi la terminazione di tutti i thread
            for thread in self.threads:
                if thread.is_alive():
                    thread.join(timeout=10)
            
            # Aggiorna lo stato nel database
            if self.db:
                self.db.stop_bot(self.bot_id)
            
            logger.info(f"Bot {self.bot_id} arrestato con successo")
            
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
        """Recupera lo stato attuale del bot"""
        try:
            # Stato di base
            status = {
                "success": True,
                "active": self.bot_attivo,
                "user_id": self.user_id,
                "bot_id": self.bot_id,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            
            # Recupera posizioni aperte
            if self.exchange:
                positions_result = self.exchange.get_open_positions()
                
                if positions_result.get("success", False):
                    positions = positions_result.get("positions", [])
                    status["positions"] = positions
                    status["num_positions"] = len(positions)
            
            # Se non ci sono posizioni disponibili dall'exchange, usa quelle memorizzate
            if "positions" not in status:
                status["positions"] = self.posizioni_aperte
                status["num_positions"] = len(self.posizioni_aperte)
            
            return status
            
        except Exception as e:
            logger.error(f"Errore nel recupero dello stato: {str(e)}")
            
            return {
                "success": False,
                "error": f"Errore nel recupero dello stato: {str(e)}"
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
    
    # Configurazione di default se nessun parametro specificato
    default_config = {
        "user_id": "default_user",
        "config_name": "funding_arbitrage",
        "strategy_type": "funding_arbitrage",
        "exchanges": ["bybit", "bitmex"],
        "parameters": {
            "threshold": 0.01,
            "size": 1000
        }
    }
    
    # Avvia il bot con configurazione di default
    app.start_bot(default_config) 