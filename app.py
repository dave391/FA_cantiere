"""
Funding Arbitrage Application - App principale per avvio del bot semi-automatico
Data: 30/07/2024
"""

import streamlit as st
import os
import time
from dotenv import load_dotenv
import uuid
from bot_main import TradingSystem

# Configurazione pagina Streamlit
st.set_page_config(
    page_title="Funding Arbitrage Bot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Carica le variabili d'ambiente
load_dotenv()

def main():
    st.title("🚀 Avvia Bot Semi-Automatico")
    st.subheader("Configura e avvia il tuo bot di Funding Arbitrage")
    
    # Inizializzazione variabili di sessione
    if 'arb_exchange_long' not in st.session_state:
        st.session_state.arb_exchange_long = "BitMEX"
    if 'arb_exchange_short' not in st.session_state:
        st.session_state.arb_exchange_short = "ByBit"
    if 'arb_size' not in st.session_state:
        st.session_state.arb_size = 100.0
    if 'bot_running' not in st.session_state:
        st.session_state.bot_running = False
    if 'trading_system' not in st.session_state:
        st.session_state.trading_system = None
    
    # Impedisce di mostrare il form se il bot è già in esecuzione
    if st.session_state.bot_running:
        st.success("✅ Bot già avviato e operativo!")
        
        if st.button("📊 Vai alla Dashboard", type="primary", use_container_width=True):
            st.switch_page("interface.py")
            
        if st.button("⏹️ Ferma Bot", type="secondary", use_container_width=True):
            stop_bot()
            
        return
    
    # Layout delle colonne per selezione exchange
    col_exchanges = st.columns(2)
    
    with col_exchanges[0]:
        st.subheader("🟢 Posizione LONG")
        exchange_long = st.selectbox(
            "Exchange per posizione LONG",
            ["BitMEX", "Bitfinex", "ByBit"],
            key="exchange_long_select",
            help="Seleziona l'exchange per l'apertura della posizione LONG"
        )
    
    with col_exchanges[1]:
        st.subheader("🔴 Posizione SHORT")
        exchange_short = st.selectbox(
            "Exchange per posizione SHORT",
            ["BitMEX", "Bitfinex", "ByBit"],
            key="exchange_short_select",
            help="Seleziona l'exchange per l'apertura della posizione SHORT"
        )
    
    if exchange_long == exchange_short:
        st.warning("⚠️ Per una strategia di arbitraggio ottimale, è consigliabile scegliere exchange differenti.")
    
    # Parametri strategia
    st.subheader("⚙️ Parametri Strategia")
    
    usdt_amount = st.number_input(
        "Importo USDT da utilizzare", 
        min_value=10.0, 
        value=st.session_state.arb_size if isinstance(st.session_state.arb_size, float) else 100.0,
        step=10.0,
        format="%.0f",
        help="Importo totale in USDT (minimo 10) che verrà diviso tra le due posizioni"
    )
    st.session_state.arb_size = usdt_amount
    
    # Parametri avanzati
    with st.expander("🔧 Parametri Avanzati", expanded=False):
        risk_level = st.slider(
            "Livello di Rischio Massimo (%)", 
            min_value=50, 
            max_value=95, 
            value=80,
            help="Livello di rischio (in percentuale) che attiva la chiusura automatica delle posizioni"
        )
        
        balance_threshold = st.slider(
            "Soglia Bilanciamento Margine (%)", 
            min_value=5, 
            max_value=50, 
            value=20,
            help="Differenza percentuale di margine che attiva il bilanciamento automatico"
        )
    
    # Pulsante per avviare il bot
    if st.button("🚀 START BOT", type="primary", use_container_width=True):
        with st.spinner("Avvio del bot in corso..."):
            # Controllo delle API keys
            api_keys_missing = False
            
            if not (os.getenv(f"{exchange_long.upper()}_API_KEY") and os.getenv(f"{exchange_long.upper()}_API_SECRET")):
                st.error(f"❌ API Key e Secret per {exchange_long} non configurati")
                api_keys_missing = True
            
            if not (os.getenv(f"{exchange_short.upper()}_API_KEY") and os.getenv(f"{exchange_short.upper()}_API_SECRET")):
                st.error(f"❌ API Key e Secret per {exchange_short} non configurati")
                api_keys_missing = True
            
            if exchange_long == exchange_short:
                st.error("❌ Non puoi usare lo stesso exchange per entrambe le posizioni")
                api_keys_missing = True
            
            if not api_keys_missing:
                # Crea configurazione utente
                user_id = f"user_{uuid.uuid4().hex[:8]}"
                
                config = {
                    "user_id": user_id,
                    "exchange_long": exchange_long,
                    "exchange_short": exchange_short,
                    "importo": usdt_amount,
                    "parameters": {
                        "symbol": "SOLUSDT",
                        "amount": usdt_amount
                    },
                    "exchanges": [exchange_long, exchange_short],
                    "risk_limits": {
                        "max_risk_level": risk_level,
                        "liquidation_buffer": 100 - risk_level
                    },
                    "margin_balance": {
                        "threshold": balance_threshold
                    }
                }
                
                # Avvia il sistema di trading
                trading_system = TradingSystem()
                result = trading_system.start_bot(config)
                
                if result["success"]:
                    st.session_state.bot_running = True
                    st.session_state.trading_system = trading_system
                    st.session_state.user_id = user_id
                    
                    st.success("✅ Bot avviato con successo! Ora lavora automaticamente.")
                    st.balloons()
                    
                    # Mostra dettagli delle posizioni aperte
                    if "positions" in result and result["positions"]:
                        st.subheader("Posizioni Aperte")
                        for pos in result["positions"]:
                            st.write(f"- {pos['exchange']}: {pos['side'].upper()} {pos['size']} {pos['symbol']}")
                    
                    # Pulsante per andare alla dashboard
                    if st.button("📊 Vai alla Dashboard", use_container_width=True):
                        st.switch_page("interface.py")
                else:
                    st.error(f"❌ Errore nell'avvio del bot: {result.get('error', 'Errore sconosciuto')}")

def stop_bot():
    """Ferma il bot attualmente in esecuzione"""
    if st.session_state.trading_system:
        with st.spinner("Arresto del bot in corso..."):
            result = st.session_state.trading_system.stop_bot()
            
            if result["success"]:
                st.session_state.bot_running = False
                st.session_state.trading_system = None
                st.success("Bot arrestato con successo")
                st.rerun()
            else:
                st.error(f"Errore nell'arresto del bot: {result.get('error', 'Errore sconosciuto')}")
    else:
        st.warning("Nessun bot attivo da fermare")

if __name__ == "__main__":
    main() 