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
from database.mongo_manager import MongoManager
from core.auth_manager import AuthManager
from api.exchange_manager import ExchangeManager

# Carica le variabili d'ambiente
load_dotenv()

# Inizializzazione componenti
try:
    db = MongoManager()
    auth = AuthManager(db)
except Exception as e:
    st.error(f"Errore di connessione al database: {str(e)}")
    db = None
    auth = AuthManager(None)  # Modalità di test

def check_auth():
    """Verifica che l'utente sia autenticato"""
    if not "authenticated" in st.session_state or not st.session_state.authenticated:
        st.warning("Sessione non valida. Effettua il login.")
        st.session_state.current_page = "login"
        st.experimental_rerun()
        return False
        
    # Verifica validità sessione
    if "session_token" in st.session_state:
        user_data = auth.validate_session(st.session_state.session_token)
        if not user_data:
            st.warning("La tua sessione è scaduta. Effettua nuovamente il login.")
            st.session_state.current_page = "login"
            st.experimental_rerun()
            return False
    
    return True

def main():
    # Verifica che l'utente sia autenticato
    if not check_auth():
        return
    
    # Recupera l'ID utente dalla sessione
    user_id = st.session_state.user_id
    
    # Recupera i dati dell'utente
    user_data = None
    if db:
        user_data = db.get_user(user_id)
    
    st.title("🚀 Avvia Bot Semi-Automatico")
    st.subheader("Configura e avvia il tuo bot di Funding Arbitrage")
    
    # Mostra info utente nella sidebar
    st.sidebar.subheader(f"👤 {user_data.get('name') if user_data else 'Utente'}")
    st.sidebar.caption(f"ID: {user_id}")
    
    # Pulsante di logout nella sidebar
    if st.sidebar.button("🚪 Logout", key="logout_button"):
        from login import logout_user
        logout_user()
    
    # Verifica se l'utente è un amministratore
    is_admin = st.session_state.is_admin if "is_admin" in st.session_state else False
    if is_admin:
        if st.sidebar.button("👑 Admin Dashboard", key="admin_button"):
            st.session_state.current_page = "admin"
            st.experimental_rerun()
    
    # Visualizza le API keys configurate
    if user_data and "exchange_credentials" in user_data:
        st.sidebar.subheader("🔑 API Keys Configurate")
        
        credentials = user_data.get("exchange_credentials", {})
        for exchange in ["bitmex", "bybit", "bitfinex"]:
            if exchange in credentials and credentials[exchange].get("api_key"):
                st.sidebar.success(f"✅ {exchange.upper()}")
            else:
                st.sidebar.error(f"❌ {exchange.upper()}")
        
        # Pulsante per configurare API keys
        if st.sidebar.button("⚙️ Configura API Keys", key="config_api_keys"):
            st.session_state.current_page = "api_config"
            st.experimental_rerun()
    
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
            st.session_state.current_page = "interface"
            st.experimental_rerun()
            
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
            # Verifica le API keys per questo utente
            api_keys_missing = False
            
            if user_data and "exchange_credentials" in user_data:
                # Modalità multi-utente: verifica le API keys nel database
                credentials = user_data.get("exchange_credentials", {})
                
                exchange_long_lower = exchange_long.lower()
                if exchange_long_lower not in credentials or not credentials[exchange_long_lower].get("api_key"):
                    st.error(f"❌ API Key e Secret per {exchange_long} non configurati")
                    api_keys_missing = True
                
                exchange_short_lower = exchange_short.lower()
                if exchange_short_lower not in credentials or not credentials[exchange_short_lower].get("api_key"):
                    st.error(f"❌ API Key e Secret per {exchange_short} non configurati")
                    api_keys_missing = True
            else:
                # Modalità legacy: verifica le API keys nelle variabili d'ambiente
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
                
                # Inizializza il database per il sistema di trading
                if db:
                    trading_system.db = db
                
                # Avvia il bot
                result = trading_system.start_bot(config)
                
                if result["success"]:
                    st.session_state.bot_running = True
                    st.session_state.trading_system = trading_system
                    
                    st.success("✅ Bot avviato con successo! Ora lavora automaticamente.")
                    st.balloons()
                    
                    # Mostra dettagli delle posizioni aperte
                    if "positions" in result and result["positions"]:
                        st.subheader("Posizioni Aperte")
                        for pos in result["positions"]:
                            st.write(f"- {pos['exchange']}: {pos['side'].upper()} {pos['size']} {pos['symbol']}")
                    
                    # Pulsante per andare alla dashboard
                    if st.button("📊 Vai alla Dashboard", use_container_width=True):
                        st.session_state.current_page = "interface"
                        st.experimental_rerun()
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
                st.experimental_rerun()
            else:
                st.error(f"Errore nell'arresto del bot: {result.get('error', 'Errore sconosciuto')}")
    else:
        st.warning("Nessun bot attivo da fermare")

if __name__ == "__main__":
    main() 