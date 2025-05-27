"""
Cycle Manager - Gestione riapertura posizioni (FASE 4)
Si occupa di gestire la riapertura delle posizioni dopo una chiusura di emergenza.
"""

import logging
import time
from datetime import datetime, timezone

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('cycle_manager')

class CycleManager:
    def __init__(self, user_id, config, db, exchange):
        """
        Inizializza il gestore del ciclo di riapertura
        
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
        
        # Importa EntryManager per riutilizzare la logica di apertura
        from core.entry_manager import EntryManager
        self.entry_manager = EntryManager(user_id, config, db, exchange)
        
        logger.info(f"CycleManager inizializzato per l'utente {user_id}")
    
    def handle_position_cycle(self):
        """
        Gestisce il ciclo di riapertura delle posizioni dopo una chiusura.
        Verifica le condizioni e riapre le posizioni se possibile.
        
        Returns:
            dict: Risultato dell'operazione di riapertura
        """
        logger.info(f"Gestione ciclo di riapertura posizioni per l'utente {self.user_id}")
        
        # Controlla lo stato del bot
        bot_status = self._check_bot_status()
        if not bot_status["active"]:
            logger.info("Bot non attivo, ciclo di riapertura interrotto")
            return {"success": False, "error": "Bot non attivo"}
        
        # Verifica se ci sono già posizioni aperte
        positions_status = self._check_active_positions()
        if positions_status["has_positions"]:
            logger.info(f"Posizioni già aperte ({positions_status['count']}), ciclo di riapertura non necessario")
            return {"success": True, "reopen_needed": False}
        
        # Aspetta un breve periodo prima di riaprire le posizioni
        # per consentire la stabilizzazione del mercato dopo la chiusura
        cooling_period = self.config.get("parameters", {}).get("cooling_period", 5)
        logger.info(f"Attesa periodo di raffreddamento ({cooling_period} secondi) prima della riapertura")
        time.sleep(cooling_period)
        
        # Riapri le posizioni utilizzando l'EntryManager
        reopen_result = self.entry_manager.open_initial_positions()
        
        if reopen_result["success"]:
            logger.info("Posizioni riaperte con successo")
            
            # Registra l'evento di riapertura
            self._log_reopen_event(reopen_result.get("positions", []))
            
            return {
                "success": True,
                "reopen_needed": True,
                "positions": reopen_result.get("positions", [])
            }
        else:
            logger.error(f"Errore nella riapertura delle posizioni: {reopen_result.get('error', 'Errore sconosciuto')}")
            
            # Registra l'evento di fallimento
            self._log_reopen_failure(reopen_result.get("error", "Errore sconosciuto"))
            
            return {
                "success": False,
                "reopen_needed": True,
                "error": reopen_result.get("error", "Errore sconosciuto")
            }
    
    def _check_bot_status(self):
        """
        Verifica che il bot sia attivo
        
        Returns:
            dict: Stato del bot
        """
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
    
    def _check_active_positions(self):
        """
        Verifica se ci sono posizioni attive
        
        Returns:
            dict: Stato delle posizioni
        """
        try:
            # Recupera le posizioni dal database
            db_positions = self.db.get_user_positions(self.user_id)
            
            # Controlla anche direttamente sugli exchange
            exchange_positions_result = self.exchange.get_open_positions()
            exchange_positions = []
            
            if exchange_positions_result["success"]:
                exchange_positions = exchange_positions_result["positions"]
            
            # Combina i risultati
            total_positions = len(db_positions) + len(exchange_positions)
            
            return {
                "has_positions": total_positions > 0,
                "count": total_positions,
                "db_positions": db_positions,
                "exchange_positions": exchange_positions
            }
            
        except Exception as e:
            logger.error(f"Errore nel controllo delle posizioni attive: {str(e)}")
            return {"has_positions": False, "count": 0, "error": str(e)}
    
    def _log_reopen_event(self, positions):
        """
        Registra un evento di riapertura posizioni
        
        Args:
            positions: Posizioni riaperte
        """
        try:
            if not positions:
                return
            
            # Raggruppa le posizioni per exchange
            exchanges = {}
            
            for position in positions:
                exchange = position.get("exchange", "")
                if exchange not in exchanges:
                    exchanges[exchange] = []
                
                exchanges[exchange].append(position)
            
            # Crea un log per ogni exchange
            for exchange, exchange_positions in exchanges.items():
                symbols = [p.get("symbol", "") for p in exchange_positions]
                
                event_data = {
                    "exchange": exchange,
                    "positions_count": len(exchange_positions),
                    "symbols": symbols,
                    "action": "reopen",
                    "timestamp": datetime.now(timezone.utc)
                }
                
                # Registra nel database
                self.db.risk_events.insert_one({
                    "user_id": self.user_id,
                    "event_type": "position_cycle",
                    "severity": "info",
                    "data": event_data,
                    "timestamp": datetime.now(timezone.utc)
                })
                
                logger.info(
                    f"Evento riapertura: {len(exchange_positions)} posizioni su {exchange} "
                    f"(Simboli: {', '.join(set(symbols))})"
                )
                
        except Exception as e:
            logger.error(f"Errore nella registrazione dell'evento di riapertura: {str(e)}")
    
    def _log_reopen_failure(self, error_message):
        """
        Registra un evento di fallimento nella riapertura
        
        Args:
            error_message: Messaggio di errore
        """
        try:
            event_data = {
                "action": "reopen_failure",
                "error": error_message,
                "timestamp": datetime.now(timezone.utc)
            }
            
            # Registra nel database
            self.db.risk_events.insert_one({
                "user_id": self.user_id,
                "event_type": "position_cycle",
                "severity": "error",
                "data": event_data,
                "timestamp": datetime.now(timezone.utc)
            })
            
            logger.error(f"Evento fallimento riapertura: {error_message}")
                
        except Exception as e:
            logger.error(f"Errore nella registrazione del fallimento di riapertura: {str(e)}") 