"""
Risk Monitor - Monitoraggio rischio posizioni (FASE 2)
Controlla continuamente il livello di rischio delle posizioni aperte.
"""

import logging
import time
from datetime import datetime, timezone

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('risk_monitor')

class RiskMonitor:
    def __init__(self, user_id, config, db, exchange):
        """
        Inizializza il monitor del rischio
        
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
        
        # Estrai limiti di rischio dalla configurazione
        self.risk_limits = self.config.get("risk_limits", {})
        self.max_risk_level = self.risk_limits.get("max_risk_level", 80)
        self.liquidation_buffer = self.risk_limits.get("liquidation_buffer", 20)
        
        logger.info(f"RiskMonitor inizializzato per l'utente {user_id}")
    
    def check_positions(self):
        """
        Controlla il livello di rischio di tutte le posizioni aperte.
        Monitora la distanza tra prezzo attuale e prezzo di liquidazione.
        
        Returns:
            dict: Stato del rischio con rilevamento di posizioni ad alto rischio
        """
        logger.info(f"Controllo rischio posizioni per l'utente {self.user_id}")
        
        # Recupera le posizioni aperte
        positions_result = self.exchange.get_open_positions()
        
        if not positions_result["success"] or not positions_result["positions"]:
            logger.info("Nessuna posizione aperta da monitorare")
            return {"high_risk_detected": False, "positions": []}
        
        positions = positions_result["positions"]
        risky_positions = []
        
        for position in positions:
            # Calcola il livello di rischio per ciascuna posizione
            risk_status = self._calculate_risk_level(position)
            
            # Aggiorna la posizione nel database con il rischio corrente
            self._update_position_risk(position["position_id"], risk_status)
            
            # Se il rischio è elevato, aggiungi alla lista delle posizioni a rischio
            if risk_status["risk_level"] >= self.max_risk_level:
                risky_positions.append({
                    "position": position,
                    "risk_status": risk_status
                })
                
                # Registra l'evento di rischio nel database
                self._log_risk_event(position, risk_status)
        
        # Determina se c'è un alto rischio complessivo
        high_risk_detected = len(risky_positions) > 0
        
        result = {
            "high_risk_detected": high_risk_detected,
            "risky_positions": risky_positions,
            "total_positions": len(positions),
            "details": f"{len(risky_positions)} posizioni a rischio elevato" if high_risk_detected else "Nessun rischio elevato"
        }
        
        if high_risk_detected:
            logger.warning(f"Rilevato rischio elevato: {result['details']}")
        else:
            logger.info("Nessun rischio elevato rilevato")
        
        return result
    
    def _calculate_risk_level(self, position):
        """
        Calcola il livello di rischio di una posizione basato sulla distanza
        dal prezzo di liquidazione.
        
        Args:
            position: Dati della posizione
            
        Returns:
            dict: Stato del rischio con percentuale e livello
        """
        # Estrai i dati rilevanti dalla posizione
        entry_price = float(position.get("entryPrice", 0))
        current_price = float(position.get("markPrice", 0))
        liquidation_price = float(position.get("liquidationPrice", 0))
        side = position.get("side", "").lower()
        
        # Se non abbiamo un prezzo di liquidazione valido, usa un valore predefinito
        if not liquidation_price or liquidation_price == 0:
            if side == "long":
                # Per posizione long, assume liquidation a -30% dal prezzo attuale
                liquidation_price = current_price * 0.7
            else:
                # Per posizione short, assume liquidation a +30% dal prezzo attuale
                liquidation_price = current_price * 1.3
        
        # Calcola la distanza percentuale dal prezzo di liquidazione
        distance_to_liquidation = 0
        
        if side == "long":
            if current_price > liquidation_price:  # Verifica che il prezzo di liquidazione sia inferiore al prezzo attuale
                distance_to_liquidation = ((current_price - liquidation_price) / current_price) * 100
            else:
                # Situazione critica, prezzo attuale è sotto la liquidazione
                distance_to_liquidation = 0
        else:  # short
            if current_price < liquidation_price:  # Verifica che il prezzo di liquidazione sia superiore al prezzo attuale
                distance_to_liquidation = ((liquidation_price - current_price) / current_price) * 100
            else:
                # Situazione critica, prezzo attuale è sopra la liquidazione
                distance_to_liquidation = 0
        
        # Calcola il livello di rischio inverso (100% - distanza%)
        # Più vicino alla liquidazione = rischio maggiore
        risk_level = max(0, 100 - distance_to_liquidation)
        
        # Determina la severità del rischio
        if risk_level >= 90:
            risk_severity = "critical"
        elif risk_level >= 80:
            risk_severity = "high"
        elif risk_level >= 50:
            risk_severity = "medium"
        else:
            risk_severity = "low"
        
        return {
            "risk_level": risk_level,
            "distance_to_liquidation": distance_to_liquidation,
            "current_price": current_price,
            "liquidation_price": liquidation_price,
            "severity": risk_severity,
            "timestamp": datetime.now(timezone.utc)
        }
    
    def _update_position_risk(self, position_id, risk_status):
        """
        Aggiorna lo stato di rischio della posizione nel database
        
        Args:
            position_id: ID della posizione
            risk_status: Stato di rischio calcolato
        """
        try:
            self.db.active_positions.update_one(
                {"position_id": position_id},
                {
                    "$set": {
                        "risk_level": risk_status["risk_level"],
                        "current_price": risk_status["current_price"],
                        "liquidation_price": risk_status["liquidation_price"],
                        "last_updated": risk_status["timestamp"]
                    }
                }
            )
        except Exception as e:
            logger.error(f"Errore nell'aggiornamento del rischio della posizione {position_id}: {str(e)}")
    
    def _log_risk_event(self, position, risk_status):
        """
        Registra un evento di rischio nel database
        
        Args:
            position: Dati della posizione
            risk_status: Stato di rischio calcolato
        """
        try:
            event_data = {
                "exchange": position.get("exchange", ""),
                "position_id": position.get("position_id", ""),
                "symbol": position.get("symbol", ""),
                "risk_level": risk_status["risk_level"],
                "current_price": risk_status["current_price"],
                "liquidation_price": risk_status["liquidation_price"],
                "distance_percent": risk_status["distance_to_liquidation"]
            }
            
            self.db.log_risk_event(
                self.user_id,
                "liquidation_risk",
                risk_status["severity"],
                event_data
            )
            
            logger.warning(
                f"Evento rischio registrato: {position.get('symbol')} su {position.get('exchange')} "
                f"(Rischio: {risk_status['risk_level']:.1f}%, "
                f"Prezzo: {risk_status['current_price']}, "
                f"Liquidazione: {risk_status['liquidation_price']})"
            )
            
        except Exception as e:
            logger.error(f"Errore nella registrazione dell'evento di rischio: {str(e)}") 