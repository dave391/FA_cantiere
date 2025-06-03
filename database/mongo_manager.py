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
from security.crypto_manager import CryptoManager  # Importa il CryptoManager

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
            
            # Inizializza il gestore di crittografia
            self.crypto = CryptoManager()
            
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
            
            # Collection: sessions
            self.sessions = self.db.sessions
            self.sessions.create_index("session_id", unique=True)
            self.sessions.create_index("token", unique=True)
            self.sessions.create_index("user_id")
            self.sessions.create_index("expires_at")
            
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
                "password_hash": user_data.get("password_hash", ""),
                "exchange_credentials": {},
                "risk_settings": {
                    "max_daily_loss": 1000,
                    "max_position_size": 5000,
                    "stop_loss_percentage": 5.0
                },
                "created_at": datetime.now(timezone.utc),
                "is_active": True,
                "is_admin": user_data.get("is_admin", False)
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
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Recupera un utente tramite email"""
        return self.users.find_one({"email": email})
    
    def update_user_credentials(self, user_id: str, exchange: str, credentials: Dict) -> bool:
        """Aggiorna le credenziali exchange di un utente"""
        try:
            # Cripta le credenziali prima di salvarle
            api_key = credentials.get("api_key")
            api_secret = credentials.get("api_secret")
            
            # Se le credenziali non sono già criptate, criptale
            if api_key and api_secret and not credentials.get("is_encrypted", False):
                encrypted_credentials = self.crypto.encrypt_api_credentials(api_key, api_secret)
                
                # Preserva altri campi oltre a api_key e api_secret
                for key, value in credentials.items():
                    if key not in ["api_key", "api_secret"]:
                        encrypted_credentials[key] = value
                
                credentials = encrypted_credentials
            
            result = self.users.update_one(
                {"user_id": user_id},
                {"$set": {f"exchange_credentials.{exchange}": credentials}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Errore aggiornamento credenziali: {e}")
            return False
    
    def get_user_credentials(self, user_id: str, exchange: str) -> Optional[Dict]:
        """Recupera le credenziali di un utente per un exchange specifico"""
        try:
            user = self.users.find_one(
                {"user_id": user_id},
                {f"exchange_credentials.{exchange}": 1}
            )
            
            if not user or "exchange_credentials" not in user or exchange not in user["exchange_credentials"]:
                return None
                
            credentials = user["exchange_credentials"][exchange]
            
            # Se le credenziali sono criptate, decriptale
            if credentials.get("is_encrypted", False):
                return self.crypto.decrypt_api_credentials(credentials)
            
            return credentials
        except Exception as e:
            logger.error(f"Errore recupero credenziali: {e}")
            return None
    
    def get_all_users(self, include_inactive: bool = False) -> List[Dict]:
        """Recupera tutti gli utenti"""
        query = {} if include_inactive else {"is_active": True}
        return list(self.users.find(query))
    
    def update_user(self, user_id: str, updates: Dict) -> bool:
        """Aggiorna i dati di un utente"""
        try:
            result = self.users.update_one(
                {"user_id": user_id},
                {"$set": updates}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Errore aggiornamento utente: {e}")
            return False
    
    # =================== SESSION MANAGEMENT ===================
    
    def create_session(self, session_data: Dict) -> bool:
        """Crea una nuova sessione utente"""
        try:
            self.sessions.insert_one(session_data)
            logger.info(f"Sessione creata per utente: {session_data['user_id']}")
            return True
        except Exception as e:
            logger.error(f"Errore creazione sessione: {e}")
            return False
    
    def get_session(self, token: str) -> Optional[Dict]:
        """Recupera una sessione tramite token"""
        return self.sessions.find_one({"token": token})
    
    def update_session(self, token: str, updates: Dict) -> bool:
        """Aggiorna una sessione"""
        try:
            result = self.sessions.update_one(
                {"token": token},
                {"$set": updates}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Errore aggiornamento sessione: {e}")
            return False
    
    def invalidate_session(self, token: str) -> bool:
        """Invalida una sessione (logout)"""
        try:
            result = self.sessions.update_one(
                {"token": token},
                {"$set": {"is_active": False}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Errore invalidazione sessione: {e}")
            return False
    
    def cleanup_expired_sessions(self) -> int:
        """Rimuove le sessioni scadute"""
        try:
            result = self.sessions.delete_many({
                "expires_at": {"$lt": datetime.now(timezone.utc)}
            })
            return result.deleted_count
        except Exception as e:
            logger.error(f"Errore pulizia sessioni: {e}")
            return 0
    
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
    
    def get_active_bots(self, user_id: str = None) -> List[Dict]:
        """Recupera i bot attivi di un utente o di tutti gli utenti"""
        if user_id:
            return list(self.bot_status.find({"user_id": user_id, "status": "running"}))
        else:
            return list(self.bot_status.find({"status": "running"}))
    
    def get_all_bots(self) -> List[Dict]:
        """Recupera tutti i bot nel sistema"""
        return list(self.bot_status.find())
    
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
            # Assicurati che last_updated sia sempre aggiornato
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
        """Chiude una posizione attiva e la sposta nella cronologia"""
        try:
            # Recupera la posizione
            position = self.active_positions.find_one({"position_id": position_id})
            
            if not position:
                logger.warning(f"Posizione non trovata per chiusura: {position_id}")
                return False
            
            # Aggiorna la posizione come chiusa
            result = self.active_positions.update_one(
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
            
            # Crea voce nella cronologia di trading
            trade_doc = {
                "trade_id": f"trade_{position_id}",
                "position_id": position_id,
                "user_id": position["user_id"],
                "bot_id": position["bot_id"],
                "exchange": position["exchange"],
                "symbol": position["symbol"],
                "side": position["side"],
                "size": position["size"],
                "entry_price": position["entry_price"],
                "exit_price": exit_price,
                "pnl": pnl,
                "opened_at": position["opened_at"],
                "closed_at": datetime.now(timezone.utc),
                "duration_seconds": (datetime.now(timezone.utc) - position["opened_at"]).total_seconds(),
                "timestamp": datetime.now(timezone.utc)
            }
            
            self.trade_history.insert_one(trade_doc)
            
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Errore chiusura posizione: {e}")
            return False
    
    def get_user_positions(self, user_id: str, active_only: bool = True) -> List[Dict]:
        """Recupera le posizioni di un utente"""
        query = {"user_id": user_id}
        if active_only:
            query["is_active"] = True
        
        return list(self.active_positions.find(query))
    
    def get_all_positions(self, active_only: bool = True) -> List[Dict]:
        """Recupera tutte le posizioni nel sistema"""
        query = {}
        if active_only:
            query["is_active"] = True
        
        return list(self.active_positions.find(query))
    
    # =================== RISK MONITORING ===================
    
    def log_risk_event(self, user_id: str, event_type: str, severity: str, data: Dict) -> bool:
        """Registra un evento di rischio"""
        try:
            event_doc = {
                "user_id": user_id,
                "event_type": event_type,
                "severity": severity,
                "data": data,
                "timestamp": datetime.now(timezone.utc),
                "is_resolved": False
            }
            
            self.risk_events.insert_one(event_doc)
            
            return True
        except Exception as e:
            logger.error(f"Errore nel log evento di rischio: {e}")
            return False
    
    # =================== BALANCE MONITORING ===================
    
    def log_margin_balance(self, user_id: str, exchange: str, balance_data: Dict) -> bool:
        """Registra il saldo del margine"""
        try:
            balance_doc = {
                "user_id": user_id,
                "exchange": exchange,
                "available_balance": balance_data.get("available", 0.0),
                "used_margin": balance_data.get("used", 0.0),
                "total_balance": balance_data.get("total", 0.0),
                "unrealized_pnl": balance_data.get("unrealized_pnl", 0.0),
                "timestamp": datetime.now(timezone.utc)
            }
            
            self.margin_balance_logs.insert_one(balance_doc)
            
            return True
        except Exception as e:
            logger.error(f"Errore nel log del saldo: {e}")
            return False
    
    # =================== STATISTICS ===================
    
    def get_stats(self, user_id: str) -> Dict:
        """Recupera statistiche per un utente specifico"""
        try:
            # Posizioni attive
            active_positions = self.active_positions.count_documents({
                "user_id": user_id,
                "is_active": True
            })
            
            # PnL non realizzato
            pnl_agg = list(self.active_positions.aggregate([
                {"$match": {"user_id": user_id, "is_active": True}},
                {"$group": {"_id": None, "total_pnl": {"$sum": "$unrealized_pnl"}}}
            ]))
            unrealized_pnl = pnl_agg[0]["total_pnl"] if pnl_agg else 0
            
            # PnL realizzato (ultimi 30 giorni)
            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
            realized_pnl_agg = list(self.trade_history.aggregate([
                {"$match": {"user_id": user_id, "closed_at": {"$gte": thirty_days_ago}}},
                {"$group": {"_id": None, "total_pnl": {"$sum": "$pnl"}}}
            ]))
            realized_pnl = realized_pnl_agg[0]["total_pnl"] if realized_pnl_agg else 0
            
            return {
                "active_positions": active_positions,
                "unrealized_pnl": unrealized_pnl,
                "realized_pnl_30d": realized_pnl
            }
        except Exception as e:
            logger.error(f"Errore nel recupero statistiche: {e}")
            return {
                "active_positions": 0,
                "unrealized_pnl": 0,
                "realized_pnl_30d": 0
            }
    
    def get_system_stats(self) -> Dict:
        """Recupera statistiche globali del sistema"""
        try:
            # Conteggio utenti
            total_users = self.users.count_documents({})
            active_users = self.users.count_documents({"is_active": True})
            
            # Conteggio bot
            total_bots = self.bot_status.count_documents({})
            active_bots = self.bot_status.count_documents({"status": "running"})
            
            # Conteggio posizioni
            total_positions = self.active_positions.count_documents({"is_active": True})
            
            # Calcolo PnL totale
            pnl_agg = list(self.active_positions.aggregate([
                {"$match": {"is_active": True}},
                {"$group": {"_id": None, "total_pnl": {"$sum": "$unrealized_pnl"}}}
            ]))
            total_pnl = pnl_agg[0]["total_pnl"] if pnl_agg else 0
            
            return {
                "total_users": total_users,
                "active_users": active_users,
                "total_bots": total_bots,
                "active_bots": active_bots,
                "total_positions": total_positions,
                "total_pnl": total_pnl
            }
        except Exception as e:
            logger.error(f"Errore nel recupero statistiche sistema: {e}")
            return {
                "total_users": 0,
                "active_users": 0,
                "total_bots": 0,
                "active_bots": 0,
                "total_positions": 0,
                "total_pnl": 0
            }
    
    # =================== MAINTENANCE ===================
    
    def cleanup_old_data(self, days: int = 30):
        """Elimina dati vecchi per mantenere il database snello"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Rimuovi log vecchi
            self.margin_balance_logs.delete_many({"timestamp": {"$lt": cutoff_date}})
            
            # Rimuovi eventi di rischio risolti vecchi
            self.risk_events.delete_many({"timestamp": {"$lt": cutoff_date}, "is_resolved": True})
            
            # Archivia trade history vecchia
            # In un'implementazione reale, potresti spostarla in una collection di archiviazione
            
            logger.info(f"Pulizia dati vecchi completata (più vecchi di {days} giorni)")
            
        except Exception as e:
            logger.error(f"Errore nella pulizia dati vecchi: {e}")
    
    def close(self):
        """Chiude la connessione al database"""
        if self.client:
            self.client.close()
            logger.info("Connessione al database chiusa")


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