"""
Entry Manager - Gestione apertura posizioni iniziali (FASE 1)
Gestisce i controlli di entrata e l'apertura delle posizioni iniziali.
"""

import logging
import time
import uuid
from datetime import datetime, timezone
import sys
import os

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('entry_manager')

class EntryManager:
    def __init__(self, user_id, config, db, exchange):
        """
        Inizializza il gestore delle entrate
        
        Args:
            user_id: ID dell'utente
            config: Configurazione del bot
            db: Istanza di MongoManager
            exchange: Istanza di ExchangeManager
        """
        self.user_id = user_id
        self.config = config
        self.db = db
        self.exchange = exchange
        
        logger.info(f"EntryManager inizializzato per l'utente {user_id}")
    
    def open_initial_positions(self):
        """
        Apre le posizioni iniziali sugli exchange configurati.
        Esegue solo i controlli necessari (capitale sufficiente) e apre immediatamente le posizioni.
        """
        logger.info(f"Apertura posizioni iniziali per l'utente {self.user_id}")
        
        # Estrai i parametri dalla configurazione
        symbol = self.config["parameters"]["symbol"]
        position_size = self.config["parameters"]["amount"]
        exchanges = self.config["exchanges"]
        
        # Verifica che ci siano almeno due exchange configurati
        if len(exchanges) < 2:
            logger.error("Configurazione non valida: sono necessari almeno 2 exchange")
            return {"success": False, "error": "Sono necessari almeno 2 exchange"}
        
        # Verifica se ci sono già posizioni aperte
        existing_positions = self._check_existing_positions()
        if existing_positions["has_positions"]:
            logger.info(f"Posizioni già aperte: {existing_positions['count']} trovate")
            return {"success": True, "already_open": True, "positions": existing_positions["positions"]}
        
        # Verifica il capitale disponibile su ciascun exchange
        capital_check = self._check_available_capital(exchanges, position_size)
        if not capital_check["success"]:
            logger.error(f"Capitale insufficiente: {capital_check['error']}")
            return {"success": False, "error": capital_check["error"]}
        
        # Apri le posizioni long e short su exchange diversi
        positions = []
        
        try:
            # Primo exchange: posizione LONG
            long_exchange = exchanges[0]
            long_result = self.exchange.open_position(
                long_exchange, 
                symbol, 
                "long", 
                position_size
            )
            
            if long_result["success"]:
                logger.info(f"Posizione LONG aperta su {long_exchange}")
                self._save_position_to_db(long_result)
                positions.append(long_result)
            else:
                logger.error(f"Errore nell'apertura della posizione LONG: {long_result['error']}")
                return {"success": False, "error": f"Errore posizione LONG: {long_result['error']}"}
            
            # Secondo exchange: posizione SHORT
            short_exchange = exchanges[1]
            short_result = self.exchange.open_position(
                short_exchange, 
                symbol, 
                "short", 
                position_size
            )
            
            if short_result["success"]:
                logger.info(f"Posizione SHORT aperta su {short_exchange}")
                self._save_position_to_db(short_result)
                positions.append(short_result)
            else:
                # Se la posizione short fallisce, chiudi anche la long per evitare sbilanciamenti
                logger.error(f"Errore nell'apertura della posizione SHORT: {short_result['error']}")
                self.exchange.close_position(long_exchange, symbol)
                return {"success": False, "error": f"Errore posizione SHORT: {short_result['error']}"}
            
            # Log di successo
            logger.info(f"Posizioni aperte con successo: LONG su {long_exchange}, SHORT su {short_exchange}")
            return {"success": True, "positions": positions}
            
        except Exception as e:
            logger.error(f"Errore nell'apertura delle posizioni iniziali: {str(e)}")
            # Tenta di chiudere eventuali posizioni aperte parzialmente
            self._close_all_positions(exchanges, symbol)
            return {"success": False, "error": str(e)}
    
    def _check_existing_positions(self):
        """Verifica se ci sono già posizioni aperte per questo utente"""
        try:
            # Recupera posizioni dal database
            positions = self.db.get_user_positions(self.user_id)
            
            # Controlla anche sugli exchange
            exchange_positions = self.exchange.get_open_positions()
            
            if positions or (exchange_positions["success"] and exchange_positions["positions"]):
                return {
                    "has_positions": True, 
                    "count": len(positions) if positions else len(exchange_positions["positions"]),
                    "positions": positions or exchange_positions["positions"]
                }
            
            return {"has_positions": False, "count": 0, "positions": []}
            
        except Exception as e:
            logger.error(f"Errore nel controllo delle posizioni esistenti: {str(e)}")
            return {"has_positions": False, "count": 0, "positions": []}
    
    def _check_available_capital(self, exchanges, position_size):
        """Verifica che ci sia capitale sufficiente su tutti gli exchange"""
        for exchange_id in exchanges:
            try:
                # Recupera il saldo
                balance = self.exchange.get_account_balance(exchange_id)
                
                if not balance["success"]:
                    return {"success": False, "error": f"Impossibile recuperare il saldo su {exchange_id}"}
                
                # Verifica che ci sia abbastanza capitale disponibile
                available_usdt = balance["balance"].get("USDT", {}).get("free", 0)
                
                # Calcola il capitale minimo richiesto (posizione * leva * margine di sicurezza)
                # In questo caso assumiamo una leva di 3x e un margine di sicurezza del 50%
                min_required = position_size * 1.5  # Considera margine di sicurezza
                
                if available_usdt < min_required:
                    return {
                        "success": False, 
                        "error": f"Capitale insufficiente su {exchange_id}: {available_usdt} USDT (richiesto: {min_required})"
                    }
                
                logger.info(f"Capitale disponibile su {exchange_id}: {available_usdt} USDT")
                
            except Exception as e:
                return {"success": False, "error": f"Errore nel controllo del capitale su {exchange_id}: {str(e)}"}
        
        return {"success": True}
    
    def _save_position_to_db(self, position_data):
        """Salva una posizione nel database"""
        try:
            position_doc = {
                "position_id": position_data["position_id"],
                "user_id": self.user_id,
                "bot_id": position_data.get("bot_id", ""),
                "exchange": position_data["exchange"],
                "symbol": position_data["symbol"],
                "side": position_data["side"],
                "size": position_data["size"],
                "entry_price": position_data.get("details", {}).get("entryPrice", 0),
                "leverage": position_data.get("details", {}).get("leverage", 3),
                "margin_used": position_data.get("details", {}).get("positionMargin", 0),
                "current_price": position_data.get("details", {}).get("markPrice", 0)
            }
            
            self.db.save_position(position_doc)
            logger.info(f"Posizione salvata nel database: {position_data['position_id']}")
            
        except Exception as e:
            logger.error(f"Errore nel salvataggio della posizione: {str(e)}")
    
    def _close_all_positions(self, exchanges, symbol):
        """Chiude tutte le posizioni in caso di errore"""
        for exchange_id in exchanges:
            try:
                self.exchange.close_position(exchange_id, symbol)
            except Exception as e:
                logger.error(f"Errore nella chiusura di emergenza della posizione su {exchange_id}: {str(e)}") 