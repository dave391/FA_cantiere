"""
Emergency Closer - Chiusura posizioni a rischio (FASE 3)
Gestisce la chiusura delle posizioni quando raggiungono un livello di rischio elevato.
"""

import logging
import time
from datetime import datetime, timezone

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('emergency_closer')

class EmergencyCloser:
    def __init__(self, user_id, config, db, exchange):
        """
        Inizializza il gestore di chiusura di emergenza
        
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
        
        logger.info(f"EmergencyCloser inizializzato per l'utente {user_id}")
    
    def close_risky_positions(self, risky_positions):
        """
        Chiude le posizioni che hanno raggiunto un livello di rischio elevato.
        
        Args:
            risky_positions: Lista di posizioni con rischio elevato
        
        Returns:
            dict: Risultato dell'operazione di chiusura
        """
        if not risky_positions:
            logger.info("Nessuna posizione a rischio da chiudere")
            return {"success": True, "closed_count": 0}
        
        logger.warning(f"Chiusura di emergenza di {len(risky_positions)} posizioni a rischio")
        
        closed_positions = []
        failed_positions = []
        
        try:
            # Per ogni posizione a rischio, chiudi sia long che short
            exchange_positions = {}
            
            # Raggruppa le posizioni per exchange e symbol per chiuderle insieme
            for risky_item in risky_positions:
                position = risky_item["position"]
                exchange = position.get("exchange", "")
                symbol = position.get("symbol", "")
                
                if exchange not in exchange_positions:
                    exchange_positions[exchange] = {}
                
                if symbol not in exchange_positions[exchange]:
                    exchange_positions[exchange][symbol] = []
                
                exchange_positions[exchange][symbol].append(position)
            
            # Chiudi tutte le posizioni raggruppate per exchange e symbol
            for exchange, symbols in exchange_positions.items():
                for symbol, positions in symbols.items():
                    # Chiudi la posizione
                    close_result = self.exchange.close_position(exchange, symbol)
                    
                    if close_result["success"]:
                        logger.info(f"Posizione chiusa con successo: {symbol} su {exchange}")
                        
                        # Aggiorna lo stato nel database
                        for position in positions:
                            self._update_position_status(position, "closed", close_result)
                            closed_positions.append(position)
                    else:
                        logger.error(f"Errore nella chiusura della posizione {symbol} su {exchange}: {close_result['error']}")
                        for position in positions:
                            failed_positions.append({
                                "position": position,
                                "error": close_result['error']
                            })
            
            # Registra l'evento di chiusura di emergenza
            self._log_emergency_close_event(closed_positions)
            
            return {
                "success": len(failed_positions) == 0,
                "closed_count": len(closed_positions),
                "failed_count": len(failed_positions),
                "closed_positions": closed_positions,
                "failed_positions": failed_positions
            }
            
        except Exception as e:
            logger.error(f"Errore nella chiusura di emergenza delle posizioni: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "closed_count": len(closed_positions),
                "failed_count": len(failed_positions)
            }
    
    def _update_position_status(self, position, status, close_result):
        """
        Aggiorna lo stato della posizione nel database
        
        Args:
            position: Dati della posizione
            status: Nuovo stato della posizione
            close_result: Risultato dell'operazione di chiusura
        """
        try:
            position_id = position.get("position_id")
            
            if not position_id:
                logger.warning("Impossibile aggiornare la posizione: ID mancante")
                return
            
            # Recupera il prezzo di uscita se disponibile
            exit_price = close_result.get("result", {}).get("price", 0)
            if not exit_price:
                exit_price = position.get("markPrice", 0)
            
            # Calcola il PnL se possibile
            entry_price = position.get("entryPrice", 0)
            pnl = 0
            
            if entry_price and exit_price:
                size = position.get("size", 0)
                side = position.get("side", "").lower()
                
                if side == "long":
                    pnl = (exit_price - entry_price) * size
                else:  # short
                    pnl = (entry_price - exit_price) * size
            
            # Aggiorna il database
            self.db.close_position(position_id, exit_price, pnl)
            
            logger.info(f"Posizione {position_id} chiusa e aggiornata nel database")
            
        except Exception as e:
            logger.error(f"Errore nell'aggiornamento dello stato della posizione: {str(e)}")
    
    def _log_emergency_close_event(self, closed_positions):
        """
        Registra un evento di chiusura di emergenza
        
        Args:
            closed_positions: Lista delle posizioni chiuse
        """
        try:
            if not closed_positions:
                return
            
            # Crea un log per ciascun exchange coinvolto
            exchanges = set(p.get("exchange", "") for p in closed_positions)
            
            for exchange in exchanges:
                # Filtra le posizioni per questo exchange
                exchange_positions = [p for p in closed_positions if p.get("exchange") == exchange]
                
                if not exchange_positions:
                    continue
                
                # Crea i dati dell'evento
                symbols = [p.get("symbol", "") for p in exchange_positions]
                risk_levels = [p.get("risk_level", 0) for p in exchange_positions]
                
                event_data = {
                    "exchange": exchange,
                    "positions_count": len(exchange_positions),
                    "symbols": symbols,
                    "avg_risk_level": sum(risk_levels) / len(risk_levels) if risk_levels else 0,
                    "reason": "liquidation_risk",
                    "action": "emergency_close"
                }
                
                # Registra l'evento
                self.db.log_risk_event(
                    self.user_id,
                    "emergency_close",
                    "high",
                    event_data
                )
                
                logger.warning(
                    f"Evento chiusura emergenza: {len(exchange_positions)} posizioni su {exchange} "
                    f"(Simboli: {', '.join(set(symbols))}, "
                    f"Rischio medio: {event_data['avg_risk_level']:.1f}%)"
                )
                
        except Exception as e:
            logger.error(f"Errore nella registrazione dell'evento di chiusura: {str(e)}") 