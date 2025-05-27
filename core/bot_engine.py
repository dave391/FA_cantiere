"""
Bot Engine - Motore principale del bot di trading automatico
Gestisce l'orchestrazione di tutte le fasi del ciclo di trading
"""

import logging
import time
import threading
import uuid
from datetime import datetime, timezone
import sys
import os

# Aggiungi la directory radice al path per consentire import relativi
sys.path.append(os.getcwd())

from database.mongo_manager import MongoManager
from api.exchange_manager import ExchangeManager
from core.entry_manager import EntryManager
from core.risk_monitor import RiskMonitor
from core.emergency_closer import EmergencyCloser
from core.cycle_manager import CycleManager

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('bot_engine')

class TradingBot:
    def __init__(self, user_id, config_name=None, bot_id=None):
        """
        Inizializza il bot di trading con i parametri dell'utente
        
        Args:
            user_id: ID dell'utente proprietario del bot
            config_name: Nome della configurazione da utilizzare
            bot_id: ID del bot (generato automaticamente se non fornito)
        """
        self.user_id = user_id
        self.config_name = config_name
        self.bot_id = bot_id or f"bot_{uuid.uuid4().hex[:8]}"
        
        # Flag per controllare il ciclo di esecuzione
        self.running = False
        self.monitor_thread = None
        
        # Inizializza connessioni alle API e al database
        self.db = MongoManager()
        self.exchange = ExchangeManager(user_id)
        
        # Carica la configurazione dal database
        self.load_config()
        
        # Inizializza i moduli del bot
        self.entry_manager = EntryManager(self.user_id, self.config, self.db, self.exchange)
        self.risk_monitor = RiskMonitor(self.user_id, self.config, self.db, self.exchange)
        self.emergency_closer = EmergencyCloser(self.user_id, self.config, self.db, self.exchange)
        self.cycle_manager = CycleManager(self.user_id, self.config, self.db, self.exchange)
        
        logger.info(f"Bot {self.bot_id} inizializzato per l'utente {user_id}")
    
    def load_config(self):
        """Carica la configurazione del bot dal database"""
        if self.config_name:
            # Carica la configurazione specifica
            configs = self.db.get_bot_configs(self.user_id)
            matching_configs = [c for c in configs if c['config_name'] == self.config_name]
            
            if matching_configs:
                self.config = matching_configs[0]
                logger.info(f"Configurazione '{self.config_name}' caricata per l'utente {self.user_id}")
            else:
                # Usa una configurazione predefinita
                logger.warning(f"Configurazione '{self.config_name}' non trovata, uso impostazioni predefinite")
                self.config = self._get_default_config()
        else:
            # Usa l'ultima configurazione attiva dell'utente o quella predefinita
            configs = self.db.get_bot_configs(self.user_id)
            if configs:
                self.config = configs[0]  # Usa la prima configurazione disponibile
                self.config_name = self.config['config_name']
                logger.info(f"Configurazione '{self.config_name}' caricata automaticamente")
            else:
                self.config = self._get_default_config()
                logger.info("Nessuna configurazione trovata, uso impostazioni predefinite")
    
    def _get_default_config(self):
        """Restituisce una configurazione predefinita"""
        return {
            "user_id": self.user_id,
            "config_name": "default",
            "strategy_type": "funding_arbitrage",
            "parameters": {
                "symbol": "SOLUSDT",
                "amount": 1.0,
                "min_funding_diff": 0.01,
                "check_interval": 10
            },
            "exchanges": ["bybit", "bitmex"],
            "risk_limits": {
                "max_risk_level": 80,  # Percentuale massima di rischio
                "liquidation_buffer": 20,  # Buffer di sicurezza dalla liquidazione (%)
                "max_position_size": 1000  # Dimensione massima della posizione in USDT
            },
            "margin_balance": {
                "threshold": 20,  # Differenza percentuale che attiva il bilanciamento
                "check_times": ["12:00", "00:00"]  # Orari di controllo (UTC)
            }
        }
    
    def start(self):
        """Avvia il bot di trading"""
        if self.running:
            logger.warning(f"Bot {self.bot_id} è già in esecuzione")
            return False
        
        try:
            # Registra lo stato del bot nel database
            self.db.start_bot(self.user_id, self.bot_id, self.config_name)
            
            # Imposta il flag di esecuzione
            self.running = True
            
            # Esegui le verifiche preliminari
            self._run_pre_checks()
            
            # Avvia il ciclo di monitoraggio in un thread separato
            self.monitor_thread = threading.Thread(target=self._monitoring_loop)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            
            logger.info(f"Bot {self.bot_id} avviato con successo")
            return True
            
        except Exception as e:
            logger.error(f"Errore nell'avvio del bot: {str(e)}")
            self.running = False
            return False
    
    def stop(self):
        """Ferma il bot di trading"""
        if not self.running:
            logger.warning(f"Bot {self.bot_id} non è in esecuzione")
            return False
        
        try:
            # Imposta il flag di esecuzione a False per terminare il loop
            self.running = False
            
            # Attendi che il thread di monitoraggio termini
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=5.0)
            
            # Aggiorna lo stato del bot nel database
            self.db.stop_bot(self.bot_id)
            
            logger.info(f"Bot {self.bot_id} fermato con successo")
            return True
            
        except Exception as e:
            logger.error(f"Errore nell'arresto del bot: {str(e)}")
            return False
    
    def _run_pre_checks(self):
        """Esegue i controlli preliminari prima di avviare il bot"""
        logger.info(f"Esecuzione controlli preliminari per il bot {self.bot_id}")
        
        # Verifica che le API key siano valide
        api_status = self.exchange.verify_api_keys()
        for exchange_id, status in api_status.items():
            if not status["valid"]:
                logger.warning(f"API key non valide per {exchange_id}: {status['error']}")
        
        # Verifica il capitale disponibile su ciascun exchange
        for exchange_id in self.config["exchanges"]:
            balance = self.exchange.get_account_balance(exchange_id)
            if balance["success"]:
                # Registra il saldo disponibile
                logger.info(f"Saldo su {exchange_id}: {balance['balance']}")
            else:
                logger.warning(f"Impossibile recuperare il saldo su {exchange_id}: {balance['error']}")
        
        # Apri le posizioni iniziali
        self.entry_manager.open_initial_positions()
    
    def _monitoring_loop(self):
        """Loop principale di monitoraggio continuo delle posizioni"""
        logger.info(f"Avvio loop di monitoraggio per il bot {self.bot_id}")
        
        while self.running:
            try:
                # Monitora il rischio delle posizioni aperte
                risk_status = self.risk_monitor.check_positions()
                
                # Se viene rilevato un rischio elevato, gestisci la chiusura di emergenza
                if risk_status["high_risk_detected"]:
                    logger.warning(f"Rilevato rischio elevato: {risk_status['details']}")
                    
                    # Chiudi le posizioni a rischio
                    close_result = self.emergency_closer.close_risky_positions(
                        risk_status["risky_positions"]
                    )
                    
                    if close_result["success"]:
                        logger.info("Posizioni chiuse con successo per rischio elevato")
                        
                        # Gestisci la riapertura delle posizioni
                        self.cycle_manager.handle_position_cycle()
                
                # Aggiorna lo stato del bot nel database
                self._update_bot_status()
                
                # Attendi l'intervallo configurato
                time.sleep(self.config["parameters"].get("check_interval", 10))
                
            except Exception as e:
                logger.error(f"Errore nel loop di monitoraggio: {str(e)}")
                time.sleep(5)  # Breve attesa prima di riprovare in caso di errore
    
    def _update_bot_status(self):
        """Aggiorna lo stato del bot nel database"""
        try:
            # Recupera le posizioni aperte
            positions_result = self.exchange.get_open_positions()
            
            if positions_result["success"]:
                positions = positions_result["positions"]
                
                # Calcola il PnL totale
                total_pnl = sum(float(p.get('unrealizedPnl', 0)) for p in positions)
                
                # Aggiorna il database
                self.db.bot_status.update_one(
                    {"bot_id": self.bot_id},
                    {
                        "$set": {
                            "last_activity": datetime.now(timezone.utc),
                            "positions_count": len(positions),
                            "total_pnl": total_pnl
                        }
                    }
                )
        except Exception as e:
            logger.error(f"Errore nell'aggiornamento dello stato del bot: {str(e)}")


class BotManager:
    """Classe per gestire multiple istanze di bot per diversi utenti"""
    
    def __init__(self):
        """Inizializza il manager dei bot"""
        self.bots = {}  # {bot_id: TradingBot}
        self.db = MongoManager()
        
        logger.info("BotManager inizializzato")
    
    def load_active_bots(self):
        """Carica tutti i bot attivi dal database"""
        try:
            # Recupera tutti i bot con stato "running"
            active_bots = self.db.bot_status.find({"status": "running"})
            
            count = 0
            for bot_data in active_bots:
                user_id = bot_data.get("user_id")
                bot_id = bot_data.get("bot_id")
                config_name = bot_data.get("config_name")
                
                # Crea e avvia il bot
                if bot_id not in self.bots:
                    bot = TradingBot(user_id, config_name, bot_id)
                    self.bots[bot_id] = bot
                    bot.start()
                    count += 1
            
            logger.info(f"Caricati {count} bot attivi")
            
        except Exception as e:
            logger.error(f"Errore nel caricamento dei bot attivi: {str(e)}")
    
    def start_bot(self, user_id, config_name=None):
        """Avvia un nuovo bot per un utente"""
        try:
            # Verifica se esiste già un bot attivo per questo utente
            existing_bots = self.db.get_active_bots(user_id)
            
            if existing_bots:
                logger.warning(f"Bot già attivo per l'utente {user_id}")
                return {"success": False, "error": "Bot già attivo per questo utente"}
            
            # Crea una nuova istanza del bot
            bot = TradingBot(user_id, config_name)
            bot_id = bot.bot_id
            
            # Avvia il bot
            if bot.start():
                self.bots[bot_id] = bot
                return {"success": True, "bot_id": bot_id}
            else:
                return {"success": False, "error": "Errore nell'avvio del bot"}
            
        except Exception as e:
            logger.error(f"Errore nella creazione del bot: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def stop_bot(self, bot_id):
        """Ferma un bot in esecuzione"""
        if bot_id not in self.bots:
            return {"success": False, "error": "Bot non trovato"}
        
        try:
            # Ferma il bot
            bot = self.bots[bot_id]
            if bot.stop():
                del self.bots[bot_id]
                return {"success": True}
            else:
                return {"success": False, "error": "Errore nell'arresto del bot"}
            
        except Exception as e:
            logger.error(f"Errore nell'arresto del bot {bot_id}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_bot_status(self, bot_id):
        """Recupera lo stato attuale di un bot"""
        if bot_id not in self.bots:
            return {"success": False, "error": "Bot non trovato"}
        
        try:
            bot = self.bots[bot_id]
            
            # Recupera lo stato dal database
            status = self.db.bot_status.find_one({"bot_id": bot_id})
            
            if status:
                return {"success": True, "status": status}
            else:
                return {"success": False, "error": "Stato non trovato"}
            
        except Exception as e:
            logger.error(f"Errore nel recupero dello stato del bot {bot_id}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def stop_all_bots(self):
        """Ferma tutti i bot attivi"""
        try:
            bot_ids = list(self.bots.keys())
            stopped_count = 0
            
            for bot_id in bot_ids:
                result = self.stop_bot(bot_id)
                if result["success"]:
                    stopped_count += 1
            
            logger.info(f"Fermati {stopped_count} bot su {len(bot_ids)}")
            return {"success": True, "stopped_count": stopped_count}
            
        except Exception as e:
            logger.error(f"Errore nell'arresto di tutti i bot: {str(e)}")
            return {"success": False, "error": str(e)} 