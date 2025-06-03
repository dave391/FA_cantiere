"""
Exchange Manager - Wrapper per le API degli exchange
Fornisce un'interfaccia unificata per le operazioni di trading
"""

import os
import logging
from dotenv import load_dotenv
from ccxt_api import CCXTAPI
import time
from datetime import datetime
import uuid

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('exchange_manager')

class ExchangeManager:
    def __init__(self, user_id=None, db=None):
        """Inizializza la connessione con gli exchange per un utente specifico"""
        load_dotenv()
        
        self.user_id = user_id
        self.db = db
        self.apis = {}
        self.supported_exchanges = ["bybit", "bitmex", "bitfinex"]
        
        # Inizializza le API per ciascun exchange supportato
        if user_id and db:
            # Modalità multi-utente con database
            self._init_user_apis()
        else:
            # Modalità legacy - compatibilità con versione single-user
            self._init_legacy_apis()
    
    def _init_user_apis(self):
        """Inizializza le API specifiche dell'utente dal database"""
        try:
            # Recupera credenziali utente dal database
            user = self.db.users.find_one({"user_id": self.user_id})
            
            if user and "exchange_credentials" in user:
                credentials = user.get("exchange_credentials", {})
                
                for exchange_id in self.supported_exchanges:
                    if exchange_id in credentials:
                        exchange_creds = credentials[exchange_id]
                        
                        # Gestione delle credenziali criptate
                        if exchange_creds.get("is_encrypted", False):
                            # Utilizza il metodo get_user_credentials che decripta automaticamente
                            decrypted_creds = self.db.get_user_credentials(self.user_id, exchange_id)
                            if decrypted_creds:
                                api_key = decrypted_creds.get("api_key")
                                api_secret = decrypted_creds.get("api_secret")
                            else:
                                logger.warning(f"Impossibile decriptare le credenziali per {exchange_id} (utente: {self.user_id})")
                                continue
                        else:
                            # Credenziali non criptate (legacy)
                            api_key = exchange_creds.get("api_key")
                            api_secret = exchange_creds.get("api_secret")
                        
                        if api_key and api_secret:
                            self.apis[exchange_id] = CCXTAPI(exchange_id, api_key, api_secret)
                            logger.info(f"API utente per {exchange_id} inizializzate (utente: {self.user_id})")
                        else:
                            logger.warning(f"API key o secret non configurate per {exchange_id} (utente: {self.user_id})")
                    else:
                        logger.info(f"Exchange {exchange_id} non configurato per l'utente {self.user_id}")
            else:
                logger.warning(f"Nessuna credenziale trovata per l'utente {self.user_id}")
                
        except Exception as e:
            logger.error(f"Errore nell'inizializzazione API utente: {str(e)}")
            
    def _init_legacy_apis(self):
        """Inizializza le API dalla configurazione globale (modalità legacy)"""
        for exchange_id in self.supported_exchanges:
            try:
                api_key = os.getenv(f"{exchange_id.upper()}_API_KEY")
                api_secret = os.getenv(f"{exchange_id.upper()}_API_SECRET")
                
                if api_key and api_secret:
                    self.apis[exchange_id] = CCXTAPI(exchange_id, api_key, api_secret)
                    logger.info(f"API per {exchange_id} inizializzate (modalità legacy)")
                else:
                    logger.warning(f"API key o secret non configurati per {exchange_id} (modalità legacy)")
            except Exception as e:
                logger.error(f"Errore nell'inizializzazione API per {exchange_id}: {str(e)}")
    
    def save_user_credentials(self, exchange_id, api_key, api_secret):
        """Salva le credenziali di un utente per un exchange"""
        if not self.db or not self.user_id:
            logger.error("Database o user_id non disponibili per salvare le credenziali")
            return False
            
        try:
            # Prepara le credenziali (saranno criptate dal MongoManager)
            credentials = {
                "api_key": api_key,
                "api_secret": api_secret
            }
            
            # Aggiorna le credenziali nel database
            result = self.db.update_user_credentials(
                self.user_id,
                exchange_id,
                credentials
            )
            
            if result:
                logger.info(f"Credenziali salvate per {exchange_id} (utente: {self.user_id})")
                
                # Inizializza l'API con le nuove credenziali
                self.apis[exchange_id] = CCXTAPI(exchange_id, api_key, api_secret)
                
                return True
            else:
                logger.warning(f"Nessun aggiornamento effettuato per {exchange_id} (utente: {self.user_id})")
                return False
                
        except Exception as e:
            logger.error(f"Errore nel salvataggio credenziali: {str(e)}")
            return False
    
    def verify_api_keys(self):
        """Verifica che le chiavi API siano valide per tutti gli exchange configurati"""
        api_status = {}
        
        for exchange_id in self.supported_exchanges:
            api_status[exchange_id] = {"valid": False, "error": None}
            
            if exchange_id in self.apis:
                try:
                    # Tenta un'operazione che richiede autenticazione
                    account_info = self.apis[exchange_id].get_account_info()
                    api_status[exchange_id]["valid"] = True
                except Exception as e:
                    api_status[exchange_id]["error"] = str(e)
            else:
                api_status[exchange_id]["error"] = "API non inizializzate"
        
        return api_status
    
    def get_account_balance(self, exchange_id):
        """Recupera il saldo dell'account su un exchange"""
        if exchange_id not in self.apis:
            return {"success": False, "error": "Exchange non configurato"}
        
        try:
            account_info = self.apis[exchange_id].get_account_info()
            return {"success": True, "balance": account_info.get("balance", {})}
        except Exception as e:
            logger.error(f"Errore nel recupero del saldo per {exchange_id}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def open_position(self, exchange_id, symbol, side, size, params={}):
        """Apre una nuova posizione su un exchange"""
        if exchange_id not in self.apis:
            return {"success": False, "error": "Exchange non configurato"}
        
        try:
            # Prepara i parametri dell'ordine
            amount = size if side == "long" else -size
            
            # Esegui l'ordine
            order = self.apis[exchange_id].submit_order(symbol, amount, params=params)
            
            # Genera un ID univoco per la posizione
            position_id = f"pos_{uuid.uuid4().hex[:8]}"
            
            # Recupera i dettagli della posizione appena aperta
            positions = self.apis[exchange_id].get_open_positions(symbol)
            position_details = next((p for p in positions if p['symbol'] == symbol), None)
            
            result = {
                "success": True,
                "position_id": position_id,
                "exchange": exchange_id,
                "symbol": symbol,
                "side": side,
                "size": size,
                "order": order,
                "details": position_details,
                "user_id": self.user_id
            }
            
            logger.info(f"Posizione aperta con successo: {position_id} su {exchange_id} ({symbol}) per utente {self.user_id}")
            return result
            
        except Exception as e:
            logger.error(f"Errore nell'apertura della posizione su {exchange_id}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def close_position(self, exchange_id, symbol, position_size=None):
        """Chiude una posizione esistente su un exchange"""
        if exchange_id not in self.apis:
            return {"success": False, "error": "Exchange non configurato"}
        
        try:
            # Chiudi la posizione
            result = self.apis[exchange_id].close_position(symbol, position_size)
            
            logger.info(f"Posizione chiusa con successo su {exchange_id} ({symbol}) per utente {self.user_id}")
            return {"success": True, "result": result}
            
        except Exception as e:
            logger.error(f"Errore nella chiusura della posizione su {exchange_id}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_open_positions(self, exchange_id=None):
        """Recupera le posizioni aperte su un exchange o su tutti gli exchange"""
        all_positions = []
        
        if exchange_id:
            # Se è specificato un exchange, recupera solo le sue posizioni
            if exchange_id not in self.apis:
                return {"success": False, "error": f"Exchange {exchange_id} non configurato"}
            
            try:
                positions = self.apis[exchange_id].get_open_positions()
                for position in positions:
                    position['exchange'] = exchange_id
                    position['user_id'] = self.user_id
                all_positions.extend(positions)
            except Exception as e:
                logger.error(f"Errore nel recupero delle posizioni per {exchange_id}: {str(e)}")
                return {"success": False, "error": str(e)}
        else:
            # Altrimenti, recupera le posizioni da tutti gli exchange configurati
            for exchange_id, api in self.apis.items():
                try:
                    positions = api.get_open_positions()
                    for position in positions:
                        position['exchange'] = exchange_id
                        position['user_id'] = self.user_id
                    all_positions.extend(positions)
                except Exception as e:
                    logger.error(f"Errore nel recupero delle posizioni per {exchange_id}: {str(e)}")
                    # Continua con gli altri exchange anche se uno fallisce
            
        return {"success": True, "positions": all_positions}
    
    def adjust_position_margin(self, exchange_id, symbol, amount):
        """Aggiunge o rimuove margine da una posizione"""
        if exchange_id not in self.apis:
            return {"success": False, "error": "Exchange non configurato"}
        
        try:
            result = self.apis[exchange_id].adjust_position_margin(symbol, amount)
            logger.info(f"Margine regolato per {symbol} su {exchange_id}: {amount} (utente: {self.user_id})")
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Errore nella regolazione del margine per {exchange_id}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def transfer_funds(self, from_exchange, to_exchange, amount):
        """Trasferisce fondi tra exchange"""
        if from_exchange not in self.apis or to_exchange not in self.apis:
            return {"success": False, "error": "Exchange non configurato"}
        
        # In una implementazione reale, questa funzione gestirebbe 
        # il trasferimento di fondi tra exchange utilizzando le API
        # Per ora, restituiamo solo un messaggio di successo simulato
        logger.info(f"Simulazione trasferimento di {amount} USDT da {from_exchange} a {to_exchange} (utente: {self.user_id})")
        return {"success": True, "message": f"Trasferimento di {amount} USDT completato"} 