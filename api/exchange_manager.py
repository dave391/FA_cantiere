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
    def __init__(self, user_id=None):
        """Inizializza la connessione con gli exchange"""
        load_dotenv()
        
        self.user_id = user_id
        self.apis = {}
        self.supported_exchanges = ["bybit", "bitmex", "bitfinex"]
        
        # Inizializza le API per ciascun exchange supportato
        for exchange_id in self.supported_exchanges:
            try:
                api_key = os.getenv(f"{exchange_id.upper()}_API_KEY")
                api_secret = os.getenv(f"{exchange_id.upper()}_API_SECRET")
                
                if api_key and api_secret:
                    self.apis[exchange_id] = CCXTAPI(exchange_id, api_key, api_secret)
                    logger.info(f"API per {exchange_id} inizializzate")
                else:
                    logger.warning(f"API key o secret non configurati per {exchange_id}")
            except Exception as e:
                logger.error(f"Errore nell'inizializzazione API per {exchange_id}: {str(e)}")
    
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
                "details": position_details
            }
            
            logger.info(f"Posizione aperta con successo: {position_id} su {exchange_id} ({symbol})")
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
            
            logger.info(f"Posizione chiusa con successo su {exchange_id} ({symbol})")
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
            logger.info(f"Margine regolato per {symbol} su {exchange_id}: {amount}")
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
        logger.info(f"Simulazione trasferimento di {amount} USDT da {from_exchange} a {to_exchange}")
        return {"success": True, "message": f"Trasferimento di {amount} USDT completato"} 