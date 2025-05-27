"""
Margin Balancer - Bilanciamento margine tra exchange (FASE 5)
Si occupa di bilanciare il margine tra le posizioni aperte su exchange diversi.
Viene eseguito due volte al giorno indipendentemente dal ciclo principale.
"""

import logging
import time
from datetime import datetime, timezone
import sys
import os

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('margin_balancer')

class MarginBalancer:
    def __init__(self, user_id, config, db, exchange):
        """
        Inizializza il bilanciatore di margine
        
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
        
        # Estrai parametri di bilanciamento
        self.margin_balance_config = self.config.get("margin_balance", {})
        self.threshold = self.margin_balance_config.get("threshold", 20)  # Differenza % che attiva il bilanciamento
        
        logger.info(f"MarginBalancer inizializzato per l'utente {user_id}")
    
    def balance_margins(self):
        """
        Bilancia il margine tra le posizioni aperte su exchange diversi.
        Se la differenza di margine tra due exchange è superiore alla soglia,
        rimuove margine dall'exchange con più margine e lo aggiunge all'altro.
        
        Returns:
            dict: Risultato dell'operazione di bilanciamento
        """
        logger.info(f"Bilanciamento margine per l'utente {self.user_id}")
        
        # Verifica se il bot è attivo
        bot_status = self._check_bot_status()
        if not bot_status["active"]:
            logger.info("Bot non attivo, bilanciamento margine non necessario")
            return {"success": True, "balanced": False, "reason": "Bot non attivo"}
        
        # Recupera le posizioni aperte
        positions = self._get_positions_with_margin()
        
        if not positions["success"] or not positions["positions"]:
            logger.info("Nessuna posizione aperta da bilanciare")
            return {"success": True, "balanced": False, "reason": "Nessuna posizione aperta"}
        
        # Raggruppa le posizioni per exchange e calcola il margine totale
        exchange_margins = self._calculate_exchange_margins(positions["positions"])
        
        if len(exchange_margins) < 2:
            logger.info("Meno di 2 exchange con posizioni aperte, bilanciamento non necessario")
            return {"success": True, "balanced": False, "reason": "Meno di 2 exchange"}
        
        # Verifica se è necessario il bilanciamento
        balance_check = self._check_balance_needed(exchange_margins)
        
        if not balance_check["balance_needed"]:
            logger.info("Bilanciamento non necessario, margini già equilibrati")
            return {"success": True, "balanced": False, "reason": "Margini già equilibrati"}
        
        # Esegui il bilanciamento
        source_exchange = balance_check["source_exchange"]
        target_exchange = balance_check["target_exchange"]
        transfer_amount = balance_check["transfer_amount"]
        
        logger.info(
            f"Bilanciamento necessario: trasferimento di {transfer_amount:.2f} USDT "
            f"da {source_exchange} a {target_exchange}"
        )
        
        # Esegui il bilanciamento in tre fasi
        result = self._execute_balance(
            source_exchange, 
            target_exchange, 
            transfer_amount,
            balance_check["source_position"],
            balance_check["target_position"]
        )
        
        if result["success"]:
            logger.info("Bilanciamento margine completato con successo")
            
            # Registra l'evento di bilanciamento
            self._log_balance_event(result)
            
            return {
                "success": True,
                "balanced": True,
                "source_exchange": source_exchange,
                "target_exchange": target_exchange,
                "amount": transfer_amount,
                "details": result
            }
        else:
            logger.error(f"Errore nel bilanciamento margine: {result['error']}")
            return {
                "success": False,
                "balanced": False,
                "error": result['error']
            }
    
    def _check_bot_status(self):
        """Verifica se il bot è attivo"""
        try:
            # Recupera lo stato del bot dal database
            bot_status = self.db.bot_status.find_one({"user_id": self.user_id, "status": "running"})
            
            if bot_status:
                return {"active": True, "bot_id": bot_status.get("bot_id")}
            else:
                return {"active": False}
                
        except Exception as e:
            logger.error(f"Errore nel controllo dello stato del bot: {str(e)}")
            # In caso di errore, assumiamo che il bot sia attivo per sicurezza
            return {"active": True, "error": str(e)}
    
    def _get_positions_with_margin(self):
        """Recupera le posizioni aperte con informazioni sul margine"""
        try:
            # Recupera le posizioni dagli exchange
            positions_result = self.exchange.get_open_positions()
            
            if not positions_result["success"]:
                return {"success": False, "error": positions_result["error"]}
            
            positions = positions_result["positions"]
            
            # Filtra solo le posizioni che hanno informazioni sul margine
            positions_with_margin = []
            
            for position in positions:
                # Verifica che la posizione abbia le informazioni necessarie
                if (position.get("exchange") and 
                    position.get("symbol") and 
                    position.get("side") and 
                    (position.get("positionMargin") is not None or 
                     position.get("collateral") is not None or 
                     position.get("margin") is not None)):
                    
                    # Normalizza il campo del margine
                    margin = (position.get("positionMargin") or 
                              position.get("collateral") or 
                              position.get("margin") or 0)
                    
                    position["normalized_margin"] = float(margin)
                    positions_with_margin.append(position)
            
            return {"success": True, "positions": positions_with_margin}
            
        except Exception as e:
            logger.error(f"Errore nel recupero delle posizioni con margine: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _calculate_exchange_margins(self, positions):
        """Calcola il margine totale per ciascun exchange"""
        exchange_margins = {}
        
        for position in positions:
            exchange = position.get("exchange", "")
            margin = position.get("normalized_margin", 0)
            symbol = position.get("symbol", "")
            
            if not exchange or margin <= 0:
                continue
            
            if exchange not in exchange_margins:
                exchange_margins[exchange] = {
                    "total_margin": 0,
                    "positions": []
                }
            
            exchange_margins[exchange]["total_margin"] += margin
            exchange_margins[exchange]["positions"].append(position)
        
        return exchange_margins
    
    def _check_balance_needed(self, exchange_margins):
        """Verifica se è necessario il bilanciamento e determina i parametri"""
        if len(exchange_margins) < 2:
            return {"balance_needed": False}
        
        # Trova l'exchange con il margine più alto e quello con il margine più basso
        exchanges = list(exchange_margins.keys())
        max_margin_exchange = exchanges[0]
        min_margin_exchange = exchanges[0]
        
        for exchange in exchanges[1:]:
            if exchange_margins[exchange]["total_margin"] > exchange_margins[max_margin_exchange]["total_margin"]:
                max_margin_exchange = exchange
            
            if exchange_margins[exchange]["total_margin"] < exchange_margins[min_margin_exchange]["total_margin"]:
                min_margin_exchange = exchange
        
        # Calcola la differenza percentuale
        max_margin = exchange_margins[max_margin_exchange]["total_margin"]
        min_margin = exchange_margins[min_margin_exchange]["total_margin"]
        
        if max_margin == 0 or min_margin == 0:
            return {"balance_needed": False}
        
        difference_percent = ((max_margin - min_margin) / max_margin) * 100
        
        # Se la differenza è superiore alla soglia, è necessario il bilanciamento
        if difference_percent >= self.threshold:
            # Calcola l'importo da trasferire per bilanciare
            # L'obiettivo è avere lo stesso margine su entrambi gli exchange
            target_margin = (max_margin + min_margin) / 2
            transfer_amount = max_margin - target_margin
            
            # Trova la posizione con il margine più alto per l'exchange source
            source_position = None
            for position in exchange_margins[max_margin_exchange]["positions"]:
                if source_position is None or position["normalized_margin"] > source_position["normalized_margin"]:
                    source_position = position
            
            # Trova la posizione con il margine più basso per l'exchange target
            target_position = None
            for position in exchange_margins[min_margin_exchange]["positions"]:
                if target_position is None or position["normalized_margin"] < target_position["normalized_margin"]:
                    target_position = position
            
            return {
                "balance_needed": True,
                "source_exchange": max_margin_exchange,
                "target_exchange": min_margin_exchange,
                "source_margin": max_margin,
                "target_margin": min_margin,
                "difference_percent": difference_percent,
                "transfer_amount": transfer_amount,
                "source_position": source_position,
                "target_position": target_position
            }
        else:
            return {"balance_needed": False}
    
    def _execute_balance(self, source_exchange, target_exchange, amount, source_position, target_position):
        """Esegue il bilanciamento del margine tra gli exchange"""
        try:
            # 1. Rimuovi margine dalla posizione con più margine
            source_symbol = source_position["symbol"]
            remove_result = self.exchange.adjust_position_margin(
                source_exchange, 
                source_symbol, 
                -amount  # Negativo per rimuovere margine
            )
            
            if not remove_result["success"]:
                return {
                    "success": False, 
                    "error": f"Errore nella rimozione del margine da {source_exchange}: {remove_result['error']}"
                }
            
            logger.info(f"Margine rimosso con successo da {source_exchange} ({source_symbol}): {amount} USDT")
            
            # 2. Trasferisci i fondi all'altro exchange
            transfer_result = self.exchange.transfer_funds(
                source_exchange,
                target_exchange,
                amount
            )
            
            if not transfer_result["success"]:
                # Tenta di ripristinare il margine rimosso
                self.exchange.adjust_position_margin(source_exchange, source_symbol, amount)
                
                return {
                    "success": False, 
                    "error": f"Errore nel trasferimento dei fondi: {transfer_result['error']}"
                }
            
            logger.info(f"Fondi trasferiti con successo da {source_exchange} a {target_exchange}: {amount} USDT")
            
            # 3. Aggiungi margine alla posizione con meno margine
            target_symbol = target_position["symbol"]
            add_result = self.exchange.adjust_position_margin(
                target_exchange, 
                target_symbol, 
                amount  # Positivo per aggiungere margine
            )
            
            if not add_result["success"]:
                logger.error(f"Errore nell'aggiunta del margine a {target_exchange}: {add_result['error']}")
                # Non possiamo ripristinare completamente, i fondi sono già stati trasferiti
                
                return {
                    "success": False, 
                    "error": f"Errore nell'aggiunta del margine a {target_exchange}: {add_result['error']}"
                }
            
            logger.info(f"Margine aggiunto con successo a {target_exchange} ({target_symbol}): {amount} USDT")
            
            return {
                "success": True,
                "source_exchange": source_exchange,
                "target_exchange": target_exchange,
                "amount": amount,
                "source_symbol": source_symbol,
                "target_symbol": target_symbol
            }
            
        except Exception as e:
            logger.error(f"Errore nell'esecuzione del bilanciamento: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _log_balance_event(self, balance_result):
        """Registra un evento di bilanciamento margine"""
        try:
            event_data = {
                "source_exchange": balance_result["source_exchange"],
                "target_exchange": balance_result["target_exchange"],
                "amount": balance_result["amount"],
                "source_symbol": balance_result["source_symbol"],
                "target_symbol": balance_result["target_symbol"],
                "timestamp": datetime.now(timezone.utc)
            }
            
            # Registra nel database
            self.db.log_margin_balance(
                self.user_id,
                balance_result["source_exchange"],
                {
                    "action": "remove",
                    "amount": balance_result["amount"],
                    "symbol": balance_result["source_symbol"],
                    "target_exchange": balance_result["target_exchange"]
                }
            )
            
            self.db.log_margin_balance(
                self.user_id,
                balance_result["target_exchange"],
                {
                    "action": "add",
                    "amount": balance_result["amount"],
                    "symbol": balance_result["target_symbol"],
                    "source_exchange": balance_result["source_exchange"]
                }
            )
            
            logger.info(
                f"Evento bilanciamento margine registrato: {balance_result['amount']} USDT "
                f"da {balance_result['source_exchange']} a {balance_result['target_exchange']}"
            )
            
        except Exception as e:
            logger.error(f"Errore nella registrazione dell'evento di bilanciamento: {str(e)}") 