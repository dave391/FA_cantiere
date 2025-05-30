"""
Funding Arbitrage Application - App principale
Data: 15/05/2025
"""

import streamlit as st
import os
import time
from dotenv import load_dotenv
from core.entry_manager import EntryManager
from position_management import position_management_app

# Configurazione pagina Streamlit
st.set_page_config(
    page_title="Funding Arbitrage",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Carica le variabili d'ambiente
load_dotenv()

def main():
    st.title("Funding Arbitrage Strategy")
    
    # Inizializzazione variabili di sessione
    if 'arb_exchange_long' not in st.session_state:
        st.session_state.arb_exchange_long = "BitMEX"
    if 'arb_exchange_short' not in st.session_state:
        st.session_state.arb_exchange_short = "ByBit"
    if 'arb_size' not in st.session_state:
        st.session_state.arb_size = 100.0
    
    if 'exchange_long_select' not in st.session_state:
        st.session_state.exchange_long_select = st.session_state.arb_exchange_long
    if 'exchange_short_select' not in st.session_state:
        st.session_state.exchange_short_select = st.session_state.arb_exchange_short
    
    def on_long_exchange_change():
        st.session_state.arb_exchange_long = st.session_state.exchange_long_select
    
    def on_short_exchange_change():
        st.session_state.arb_exchange_short = st.session_state.exchange_short_select
    
    # Layout delle colonne per selezione exchange
    col_exchanges = st.columns(2)
    
    with col_exchanges[0]:
        st.subheader("🟢 Posizione LONG")
        exchange_long = st.selectbox(
            "Exchange per posizione LONG",
            ["BitMEX", "Bitfinex", "ByBit"],
            help="Seleziona l'exchange per l'apertura della posizione LONG",
            key="exchange_long_select",
            on_change=on_long_exchange_change
        )
    
    with col_exchanges[1]:
        st.subheader("🔴 Posizione SHORT")
        exchange_short = st.selectbox(
            "Exchange per posizione SHORT",
            ["BitMEX", "Bitfinex", "ByBit"],
            help="Seleziona l'exchange per l'apertura della posizione SHORT",
            key="exchange_short_select",
            on_change=on_short_exchange_change
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
    
    # Carica l'EntryManager
    entry_manager = EntryManager(
        user_id="default_user",  # In futuro potrebbe essere un ID utente reale
        config={
            "parameters": {
                "symbol": "SOLUSDT",  # Simbolo predefinito, verrà rilevato automaticamente
                "amount": usdt_amount  # Importo totale in USDT
            },
            "exchanges": [exchange_long, exchange_short]
        },
        db=None,  # Attualmente non utilizziamo un database
        exchange=None  # Verrà inizializzato all'interno di EntryManager
    )
    
    # Mostra calcoli size
    sol_size_info = entry_manager.calculate_sol_size(usdt_amount)
    
    if not sol_size_info["success"]:
        st.error(sol_size_info["error"])
        st.stop()
    
    sol_size = sol_size_info["sol_size"]
    calc_details = sol_size_info["details"]
    
    with st.expander("🧮 Dettagli Calcolo", expanded=True):
        st.write(f"**USDT Totale:** {calc_details['usdt_total']} USDT")
        st.write(f"**USDT per posizione:** {calc_details['usdt_per_position']} USDT")
        st.write(f"**USDT con leva 5x:** {calc_details['usdt_leveraged']} USDT")
        st.write(f"**Prezzo SOL:** {calc_details['sol_price']} USDT")
        st.write(f"**SOL calcolato:** {calc_details['sol_quantity_raw']:.4f}")
        st.write(f"**SOL finale (arrotondato):** {calc_details['sol_size_final']} SOL")
    
    # Pulsante per eseguire gli ordini
    if st.button("Esegui Ordini", type="primary", use_container_width=True):
        # Controllo delle API keys
        api_keys_missing = False
        
        st.write("### 🔐 Verifica API Keys")
        if not (os.getenv(f"{exchange_long.upper()}_API_KEY") and os.getenv(f"{exchange_long.upper()}_API_SECRET")):
            st.error(f"❌ API Key e Secret per {exchange_long} non configurati")
            api_keys_missing = True
        else:
            st.success(f"✅ API Key per {exchange_long} configurate")
        
        if not (os.getenv(f"{exchange_short.upper()}_API_KEY") and os.getenv(f"{exchange_short.upper()}_API_SECRET")):
            st.error(f"❌ API Key e Secret per {exchange_short} non configurati")
            api_keys_missing = True
        else:
            st.success(f"✅ API Key per {exchange_short} configurate")
        
        if exchange_long == exchange_short:
            st.error("❌ Non puoi usare lo stesso exchange per entrambe le posizioni")
            api_keys_missing = True
        else:
            st.success("✅ Exchange diversi selezionati")
        
        if sol_size <= 0:
            st.error("❌ La quantità di SOL calcolata non è valida")
            api_keys_missing = True
        else:
            st.success(f"✅ Quantità SOL valida: {sol_size}")
        
        if not api_keys_missing:
            # Controlla disponibilità capitale
            with st.spinner("Verifico capitale disponibile..."):
                capital_check = entry_manager.check_capital_requirements(
                    exchange_long,
                    exchange_short,
                    calc_details['usdt_per_position']
                )
                
                if capital_check["overall_success"]:
                    # Esegui gli ordini
                    with st.spinner("🔄 Apertura posizioni in corso..."):
                        result = entry_manager.open_initial_positions()
                        
                        if result["success"]:
                            if result.get("already_open", False):
                                st.warning("⚠️ Posizioni già aperte in precedenza")
                                st.write("Dettagli posizioni:")
                                for pos in result["positions"]:
                                    st.write(f"- {pos['exchange']}: {pos['side'].upper()} {pos['size']} {pos['symbol']}")
                            else:
                                st.success("🎉 **Operazione di Arbitraggio Completata con Successo**")
                                st.write("Dettagli posizioni:")
                                for pos in result["positions"]:
                                    st.write(f"- {pos['exchange']}: {pos['side'].upper()} {pos['size']} {pos['symbol']}")
                            
                            st.session_state['has_open_positions'] = True
                        else:
                            st.error(f"❌ Errore nell'apertura delle posizioni: {result['error']}")
                else:
                    st.error("❌ **Impossibile procedere: capitale insufficiente**")
    
    # Gestione posizioni esistenti
    if 'has_open_positions' in st.session_state and st.session_state['has_open_positions']:
        if st.button("Gestisci Posizioni", type="secondary", use_container_width=True):
            position_management_app()

if __name__ == "__main__":
    main() 