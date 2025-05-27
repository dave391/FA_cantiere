"""
MongoDB Manager - Gestione database per trading platform
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, DuplicateKeyError
from dotenv import load_dotenv

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('mongo_manager')

class MongoManager:
    def __init__(self):
        """Inizializza la connessione MongoDB"""
        load_dotenv()
        
        self.uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
        self.database_name = os.getenv('MONGODB_DATABASE', 'trading_platform')
        
        try:
            self.client = MongoClient(self.uri)
            self.db = self.client[self.database_name]
            
            # Test connessione
            self.client.admin.command('ping')
            logger.info(f"Connessione MongoDB riuscita - Database: {self.database_name}")
            
            # Inizializza le collections con indici
            self._setup_collections()
            
        except ConnectionFailure as e:
            logger.error(f"Errore connessione MongoDB: {e}")
            raise
    
    def _setup_collections(self):
        """Crea le collections e gli indici necessari"""
        try:
            # Collection: users
            self.users = self.db.users
            self.users.create_index("user_id", unique=True)
            self.users.create_index("email", unique=True)
            
            # Collection: bot_configs
            self.bot_configs = self.db.bot_configs
            self.bot_configs.create_index([("user_id", ASCENDING), ("config_name", ASCENDING)], unique=True)
            
            # Collection: bot_status
            self.bot_status = self.db.bot_status
            self.bot_status.create_index("user_id")
            self.bot_status.create_index("bot_id", unique=True)
            
            # Collection: active_positions
            self.active_positions = self.db.active_positions
            self.active_positions.create_index([("user_id", ASCENDING), ("exchange", ASCENDING), ("symbol", ASCENDING)])
            self.active_positions.create_index("position_id", unique=True)
            
            # Collection: trade_history
            self.trade_history = self.db.trade_history
            self.trade_history.create_index([("user_id", ASCENDING), ("timestamp", DESCENDING)])
            self.trade_history.create_index("trade_id", unique=True)
            
            # Collection: risk_events
            self.risk_events = self.db.risk_events
            self.risk_events.create_index([("user_id", ASCENDING), ("timestamp", DESCENDING)])
            self.risk_events.create_index("severity")
            
            # Collection: margin_balance_logs
            self.margin_balance_logs = self.db.margin_balance_logs
            self.margin_balance_logs.create_index([("user_id", ASCENDING), ("timestamp", DESCENDING)])
            self.margin_balance_logs.create_index("exchange")
            
            logger.info("Collections e indici creati con successo")
            
        except Exception as e:
            logger.error(f"Errore nella configurazione collections: {e}")
            raise
    
    # =================== USER MANAGEMENT ===================
    
    def create_user(self, user_data: Dict) -> bool:
        """Crea un nuovo utente"""
        try:
            user_doc = {
                "user_id": user_data["user_id"],
                "email": user_data["email"],
                "name": user_data.get("name", ""),
                "exchange_credentials": {},
                "risk_settings": {
                    "max_daily_loss": 1000,
                    "max_position_size": 5000,
                    "stop_loss_percentage": 5.0
                },
                "created_at": datetime.now(timezone.utc),
                "is_active": True
            }
            
            self.users.insert_one(user_doc)
            logger.info(f"Utente creato: {user_data['user_id']}")
            return True
            
        except DuplicateKeyError:
            logger.warning(f"Utente già esistente: {user_data['user_id']}")
            return False
        except Exception as e:
            logger.error(f"Errore creazione utente: {e}")
            return False
    
    def get_user(self, user_id: str) -> Optional[Dict]:
        """Recupera un utente"""
        return self.users.find_one({"user_id": user_id})
    
    def update_user_credentials(self, user_id: str, exchange: str, credentials: Dict) -> bool:
        """Aggiorna le credenziali exchange di un utente"""
        try:
            result = self.users.update_one(
                {"user_id": user_id},
                {"$set": {f"exchange_credentials.{exchange}": credentials}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Errore aggiornamento credenziali: {e}")
            return False
    
    # =================== BOT CONFIGURATION ===================
    
    def save_bot_config(self, user_id: str, config_name: str, config_data: Dict) -> bool:
        """Salva configurazione bot"""
        try:
            config_doc = {
                "user_id": user_id,
                "config_name": config_name,
                "strategy_type": config_data.get("strategy_type", "funding_arbitrage"),
                "parameters": config_data.get("parameters", {}),
                "exchanges": config_data.get("exchanges", []),
                "risk_limits": config_data.get("risk_limits", {}),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "is_active": True
            }
            
            # Upsert: aggiorna se esiste, crea se non esiste
            self.bot_configs.replace_one(
                {"user_id": user_id, "config_name": config_name},
                config_doc,
                upsert=True
            )
            
            logger.info(f"Configurazione salvata: {user_id}/{config_name}")
            return True
            
        except Exception as e:
            logger.error(f"Errore salvataggio configurazione: {e}")
            return False
    
    def get_bot_configs(self, user_id: str) -> List[Dict]:
        """Recupera tutte le configurazioni di un utente"""
        return list(self.bot_configs.find({"user_id": user_id, "is_active": True}))
    
    # =================== BOT STATUS ===================
    
    def start_bot(self, user_id: str, bot_id: str, config_name: str) -> bool:
        """Registra l'avvio di un bot"""
        try:
            status_doc = {
                "bot_id": bot_id,
                "user_id": user_id,
                "config_name": config_name,
                "status": "running",
                "started_at": datetime.now(timezone.utc),
                "last_activity": datetime.now(timezone.utc),
                "positions_count": 0,
                "total_pnl": 0.0
            }
            
            self.bot_status.replace_one(
                {"bot_id": bot_id},
                status_doc,
                upsert=True
            )
            
            logger.info(f"Bot avviato: {bot_id}")
            return True
            
        except Exception as e:
            logger.error(f"Errore avvio bot: {e}")
            return False
    
    def stop_bot(self, bot_id: str) -> bool:
        """Ferma un bot"""
        try:
            result = self.bot_status.update_one(
                {"bot_id": bot_id},
                {
                    "$set": {
                        "status": "stopped",
                        "stopped_at": datetime.now(timezone.utc)
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Errore stop bot: {e}")
            return False
    
    def get_active_bots(self, user_id: str) -> List[Dict]:
        """Recupera i bot attivi di un utente"""
        return list(self.bot_status.find({"user_id": user_id, "status": "running"}))
    
    # =================== POSITIONS ===================
    
    def save_position(self, position_data: Dict) -> bool:
        """Salva una posizione attiva"""
        try:
            position_doc = {
                "position_id": position_data["position_id"],
                "user_id": position_data["user_id"],
                "bot_id": position_data["bot_id"],
                "exchange": position_data["exchange"],
                "symbol": position_data["symbol"],
                "side": position_data["side"],
                "size": position_data["size"],
                "entry_price": position_data["entry_price"],
                "current_price": position_data.get("current_price", position_data["entry_price"]),
                "unrealized_pnl": position_data.get("unrealized_pnl", 0.0),
                "margin_used": position_data.get("margin_used", 0.0),
                "leverage": position_data.get("leverage", 1.0),
                "opened_at": datetime.now(timezone.utc),
                "last_updated": datetime.now(timezone.utc),
                "is_active": True
            }
            
            self.active_positions.replace_one(
                {"position_id": position_data["position_id"]},
                position_doc,
                upsert=True
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Errore salvataggio posizione: {e}")
            return False
    
    def update_position(self, position_id: str, updates: Dict) -> bool:
        """Aggiorna una posizione"""
        try:
            updates["last_updated"] = datetime.now(timezone.utc)
            
            result = self.active_positions.update_one(
                {"position_id": position_id},
                {"$set": updates}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Errore aggiornamento posizione: {e}")
            return False
    
    def close_position(self, position_id: str, exit_price: float, pnl: float) -> bool:
        """Chiude una posizione"""
        try:
            # Aggiorna la posizione
            self.active_positions.update_one(
                {"position_id": position_id},
                {
                    "$set": {
                        "is_active": False,
                        "exit_price": exit_price,
                        "realized_pnl": pnl,
                        "closed_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            # Sposta nel trade history
            position = self.active_positions.find_one({"position_id": position_id})
            if position:
                trade_doc = {
                    "trade_id": position_id,
                    "user_id": position["user_id"],
                    "bot_id": position["bot_id"],
                    "exchange": position["exchange"],
                    "symbol": position["symbol"],
                    "side": position["side"],
                    "size": position["size"],
                    "entry_price": position["entry_price"],
                    "exit_price": exit_price,
                    "realized_pnl": pnl,
                    "opened_at": position["opened_at"],
                    "closed_at": datetime.now(timezone.utc),
                    "timestamp": datetime.now(timezone.utc)
                }
                
                self.trade_history.insert_one(trade_doc)
            
            return True
            
        except Exception as e:
            logger.error(f"Errore chiusura posizione: {e}")
            return False
    
    def get_user_positions(self, user_id: str, active_only: bool = True) -> List[Dict]:
        """Recupera le posizioni di un utente"""
        filter_query = {"user_id": user_id}
        if active_only:
            filter_query["is_active"] = True
            
        return list(self.active_positions.find(filter_query))
    
    # =================== RISK EVENTS ===================
    
    def log_risk_event(self, user_id: str, event_type: str, severity: str, data: Dict) -> bool:
        """Registra un evento di rischio"""
        try:
            event_doc = {
                "user_id": user_id,
                "event_type": event_type,  # "margin_call", "stop_loss", "max_loss_reached"
                "severity": severity,      # "low", "medium", "high", "critical"
                "data": data,
                "timestamp": datetime.now(timezone.utc),
                "resolved": False
            }
            
            self.risk_events.insert_one(event_doc)
            return True
            
        except Exception as e:
            logger.error(f"Errore log evento rischio: {e}")
            return False
    
    # =================== MARGIN BALANCE LOGS ===================
    
    def log_margin_balance(self, user_id: str, exchange: str, balance_data: Dict) -> bool:
        """Registra il bilanciamento del margine"""
        try:
            log_doc = {
                "user_id": user_id,
                "exchange": exchange,
                "action": balance_data["action"],  # "add", "remove", "transfer"
                "amount": balance_data["amount"],
                "symbol": balance_data.get("symbol", ""),
                "before_balance": balance_data.get("before_balance", 0.0),
                "after_balance": balance_data.get("after_balance", 0.0),
                "timestamp": datetime.now(timezone.utc)
            }
            
            self.margin_balance_logs.insert_one(log_doc)
            return True
            
        except Exception as e:
            logger.error(f"Errore log margine: {e}")
            return False
    
    # =================== UTILITY ===================
    
    def get_stats(self, user_id: str) -> Dict:
        """Recupera statistiche utente"""
        try:
            # Posizioni attive
            active_positions = self.active_positions.count_documents({"user_id": user_id, "is_active": True})
            
            # Trade totali
            total_trades = self.trade_history.count_documents({"user_id": user_id})
            
            # PnL totale
            pipeline = [
                {"$match": {"user_id": user_id}},
                {"$group": {"_id": None, "total_pnl": {"$sum": "$realized_pnl"}}}
            ]
            pnl_result = list(self.trade_history.aggregate(pipeline))
            total_pnl = pnl_result[0]["total_pnl"] if pnl_result else 0.0
            
            # Bot attivi
            active_bots = self.bot_status.count_documents({"user_id": user_id, "status": "running"})
            
            return {
                "active_positions": active_positions,
                "total_trades": total_trades,
                "total_pnl": total_pnl,
                "active_bots": active_bots
            }
            
        except Exception as e:
            logger.error(f"Errore recupero statistiche: {e}")
            return {}
    
    def cleanup_old_data(self, days: int = 30):
        """Pulisce dati vecchi"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Rimuovi eventi di rischio vecchi risolti
            self.risk_events.delete_many({
                "timestamp": {"$lt": cutoff_date},
                "resolved": True
            })
            
            # Rimuovi log margine vecchi
            self.margin_balance_logs.delete_many({
                "timestamp": {"$lt": cutoff_date}
            })
            
            logger.info(f"Cleanup dati vecchi completato (> {days} giorni)")
            
        except Exception as e:
            logger.error(f"Errore cleanup: {e}")
    
    def close(self):
        """Chiude la connessione"""
        if hasattr(self, 'client'):
            self.client.close()
            logger.info("Connessione MongoDB chiusa")


# Test di connessione
if __name__ == "__main__":
    try:
        mongo = MongoManager()
        print("✅ MongoDB configurato correttamente!")
        
        # Test creazione utente
        test_user = {
            "user_id": "test_user_001",
            "email": "test@example.com",
            "name": "Test User"
        }
        
        if mongo.create_user(test_user):
            print("✅ Utente test creato!")
            
            # Test statistiche
            stats = mongo.get_stats("test_user_001")
            print(f"📊 Statistiche: {stats}")
        
        mongo.close()
        
    except Exception as e:
        print(f"❌ Errore: {e}")