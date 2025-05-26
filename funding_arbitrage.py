"""
Funding Arbitrage Application - Checkpoint Version 3.0 (Codice Pulito)
Data: 15/05/2025
"""

import streamlit as st
import os
from dotenv import load_dotenv
from ccxt_api import CCXTAPI
import time
from position_management import position_management_app
import logging

# Configurazione logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('funding_arbitrage')

# Carica le variabili d'ambiente
load_dotenv()

def funding_arbitrage_app():
    """Applicazione per la strategia di funding arbitrage su SOLANA"""
    
    # Aggiungo un titolo semplice
    st.title("Funding Arbitrage Strategy")
    
    # Inizializza lo stato della sessione se necessario
    if 'arb_exchange_long' not in st.session_state:
        st.session_state.arb_exchange_long = "BitMEX"
    if 'arb_exchange_short' not in st.session_state:
        st.session_state.arb_exchange_short = "ByBit"
    if 'arb_size' not in st.session_state:
        st.session_state.arb_size = 5.0
    if 'arb_price_long' not in st.session_state:
        st.session_state.arb_price_long = 0.0
    if 'arb_price_short' not in st.session_state:
        st.session_state.arb_price_short = 0.0
    
    # Inizializza anche le chiavi specifiche dei SelectBox se non presenti
    if 'exchange_long_select' not in st.session_state:
        st.session_state.exchange_long_select = st.session_state.arb_exchange_long
    if 'exchange_short_select' not in st.session_state:
        st.session_state.exchange_short_select = st.session_state.arb_exchange_short
    
    # Funzioni per gestire i cambiamenti di selezione
    def on_long_exchange_change():
        st.session_state.arb_exchange_long = st.session_state.exchange_long_select
    
    def on_short_exchange_change():
        st.session_state.arb_exchange_short = st.session_state.exchange_short_select
    
    # Layout con due colonne per la selezione degli exchange
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
    
    # Avviso se gli exchange sono gli stessi
    if exchange_long == exchange_short:
        st.warning("⚠️ Per una strategia di arbitraggio ottimale, è consigliabile scegliere exchange differenti.")
    
    # Sezione parametri strategia
    st.subheader("⚙️ Parametri Strategia")
    
    # Input per la size (quantità)
    size = st.number_input(
        "Quantità di SOLANA (size)", 
        min_value=0.1, 
        value=st.session_state.arb_size if isinstance(st.session_state.arb_size, float) else 2.0,
        step=0.1,
        format="%.1f"
    )
    st.session_state.arb_size = size
    
    # Selezione del tipo di ordine
    order_type = st.radio(
        "Tipo di Ordine", 
        ["Market", "Limit"]
    )
    
    # Input per i prezzi limit, se necessario
    if order_type == "Limit":
        limit_cols = st.columns(2)
        
        with limit_cols[0]:
            price_long = st.number_input(
                "Prezzo Limit per LONG", 
                min_value=0.01,
                value=st.session_state.arb_price_long if st.session_state.arb_price_long > 0 else 100.0,
                step=0.1,
                format="%.2f"
            )
            st.session_state.arb_price_long = price_long
        
        with limit_cols[1]:
            price_short = st.number_input(
                "Prezzo Limit per SHORT", 
                min_value=0.01,
                value=st.session_state.arb_price_short if st.session_state.arb_price_short > 0 else 100.0,
                step=0.1,
                format="%.2f"
            )
            st.session_state.arb_price_short = price_short
    
    # Riepilogo strategia
    st.subheader("📊 Riepilogo Strategia")
    
    # Layout per il riepilogo
    recap_cols = st.columns(2)
    
    with recap_cols[0]:
        st.markdown(f"""
        **Operazione LONG su {exchange_long}**
        - Quantità: {size} SOLANA
        - Tipo: {order_type}
        {f"- Prezzo: {price_long}" if order_type == "Limit" else ""}
        """)
    
    with recap_cols[1]:
        st.markdown(f"""
        **Operazione SHORT su {exchange_short}**
        - Quantità: {size} SOLANA
        - Tipo: {order_type}
        {f"- Prezzo: {price_short}" if order_type == "Limit" else ""}
        """)
    
    # Pulsante per eseguire la strategia
    if st.button("Start", type="primary", use_container_width=True):
        # Verifica delle API key
        api_keys_missing = False
        
        if not (os.getenv(f"{exchange_long.upper()}_API_KEY") and os.getenv(f"{exchange_long.upper()}_API_SECRET")):
            st.error(f"API Key e Secret per {exchange_long} non configurati")
            api_keys_missing = True
        
        if not (os.getenv(f"{exchange_short.upper()}_API_KEY") and os.getenv(f"{exchange_short.upper()}_API_SECRET")):
            st.error(f"API Key e Secret per {exchange_short} non configurati")
            api_keys_missing = True
        
        # Verifica dei prezzi per ordini limit
        if order_type == "Limit" and (price_long <= 0 or price_short <= 0):
            st.error("È necessario specificare prezzi validi per entrambi gli ordini limit")
            api_keys_missing = True
        
        # Se tutto ok, procedi con gli ordini
        if not api_keys_missing:
            with st.spinner("Ricerca dei contratti SOLANA e invio ordini in corso..."):
                # Inizializza API per i due exchange
                exchange_id_long = exchange_long.lower()
                exchange_id_short = exchange_short.lower()
                
                if exchange_long == "BitMEX":
                    exchange_id_long = "bitmex"
                if exchange_short == "BitMEX":
                    exchange_id_short = "bitmex"
                
                # Creiamo le API
                api_long = CCXTAPI(exchange_id_long)
                api_short = CCXTAPI(exchange_id_short)
                
                # Funzione per trovare il contratto SOLANA su un exchange specifico
                def find_solana_contract(api, exchange_name):
                    # Ottieni tutti i futures perpetui
                    all_futures = api.get_perpetual_futures()
                    
                    # Gestisci i formati specifici per exchange
                    if exchange_name == "Bitfinex":
                        # Formati possibili per SOLANA su Bitfinex
                        possible_formats = ["tSOLF0:USTF0", "tSOLF0:USDF0", "tSOL:USTF0", "tSOLF0:UST0"]
                        
                        # Cerca prima nei formati conosciuti
                        for symbol in possible_formats:
                            if symbol in all_futures:
                                return symbol
                        
                        # Cerca per pattern parziale se non viene trovato nei formati standard
                        for symbol in all_futures:
                            if 'SOL' in symbol.upper() and 'F0:' in symbol:
                                return symbol
                        
                        # Se non viene trovato, utilizza l'API nativa di Bitfinex come fallback
                        try:
                            from bitfinex_api import BitfinexAPI
                            bitfinex_api = BitfinexAPI()
                            bitfinex_futures = bitfinex_api.get_perpetual_futures()
                            
                            # Controlla nei risultati dell'API nativa
                            for symbol in bitfinex_futures:
                                if 'SOL' in symbol.upper() and 'F0:' in symbol:
                                    return symbol
                            
                            # Se ancora non trovato, usa il formato predefinito
                            return "tSOLF0:USTF0"
                        except Exception as e:
                            # In caso di errore, usa il formato predefinito
                            return "tSOLF0:USTF0"
                    
                    elif exchange_name == "BitMEX":
                        # Per BitMEX, cerca simboli con SOL
                        for symbol in all_futures:
                            if 'SOL' in symbol.upper() and 'USDT' in symbol.upper():
                                return symbol
                        
                        # Se non trovato, usa il formato predefinito
                        return "SOLUSDT"
                    
                    elif exchange_name == "ByBit":
                        # Per ByBit, cerca esattamente SOL/USDT o SOLUSDT
                        exact_symbols = ["SOLUSDT", "SOL/USDT"]
                        
                        # Prima prova a trovare i simboli esatti
                        for symbol in exact_symbols:
                            if symbol in all_futures:
                                return symbol
                        
                        # Cerca rigorosamente il simbolo SOLUSDT, escludendo simboli simili
                        # come SOLOUSDT, SOLAYERUSDT, ecc.
                        for symbol in all_futures:
                            # Controlla se il simbolo è esattamente SOLUSDT (caso più comune)
                            if symbol == "SOLUSDT":
                                return symbol
                            # Controlla se il simbolo è in uno di questi formati: SOL-USDT, SOL_USDT
                            elif symbol in ["SOL-USDT", "SOL_USDT"]:
                                return symbol
                            # Controlla se il simbolo è SOL/USDT (formato con slash)
                            elif symbol == "SOL/USDT":
                                return symbol
                        
                        # Se non vengono trovati i simboli esatti, fai un controllo intelligente
                        # ma assicurati di escludere token simili come SOLO, SOLAYER, ecc.
                        for symbol in all_futures:
                            # Verifica che il simbolo inizi con "SOL" e che non contenga lettere
                            # tra la "L" iniziale di SOL e "USDT" alla fine
                            if (symbol.startswith("SOL") and 
                                symbol.endswith("USDT") and 
                                not any(x in symbol.upper() for x in ["SOLO", "SOLAYER", "SOLA"])):
                                return symbol
                        
                        # Se non è stato trovato nessun simbolo, usa il formato predefinito
                        logger.warning(f"Non è stato trovato alcun simbolo SOL valido su ByBit, utilizzo il formato predefinito SOLUSDT")
                        return "SOLUSDT"
                    
                    # Per altri exchange
                    else:
                        # Cerca simboli con SOL e USDT
                        for symbol in all_futures:
                            if 'SOL' in symbol.upper() and 'USDT' in symbol.upper():
                                return symbol
                        
                        # Cerca simboli generici con SOL
                        for symbol in all_futures:
                            if 'SOL' in symbol.upper():
                                return symbol
                        
                        # Se non trovato, usa un formato generico
                        return "SOL/USDT"
                
                # Trova i contratti SOLANA su entrambi gli exchange
                symbol_long = find_solana_contract(api_long, exchange_long)
                symbol_short = find_solana_contract(api_short, exchange_short)
                
                # Mostra i simboli trovati
                st.info(f"Simboli trovati: LONG = {symbol_long} su {exchange_long}, SHORT = {symbol_short} su {exchange_short}")
                
                # Invia gli ordini
                sol_amount = size
                
                # Adattamenti specifici per exchange
                # BitMEX ha moltiplicatore diverso per SOLUSDT
                if exchange_long == "BitMEX":
                    # Per BitMEX, 1 SOL = 10000 contratti
                    adjusted_long_size = int(sol_amount * 10000)
                    # Assicura che sia almeno 1000 contratti (minimo BitMEX per Solana)
                    adjusted_long_size = max(adjusted_long_size, 1000)
                    # Arrotonda a 100 per Solana
                    adjusted_long_size = round(adjusted_long_size / 100) * 100
                    logger.info(f"Conversione LONG BitMEX: {sol_amount} SOL → {adjusted_long_size} contratti (moltiplicatore: 10000)")
                else:
                    adjusted_long_size = sol_amount
                
                if exchange_short == "BitMEX":
                    # Per BitMEX, 1 SOL = 10000 contratti, e short è negativo
                    adjusted_short_size = -int(sol_amount * 10000)
                    # Assicura che sia almeno 1000 contratti in valore assoluto
                    adjusted_short_size = min(adjusted_short_size, -1000)
                    # Arrotonda a 100 per Solana (mantenendo il segno negativo)
                    adjusted_short_size = round(adjusted_short_size / 100) * 100
                    logger.info(f"Conversione SHORT BitMEX: {sol_amount} SOL → {abs(adjusted_short_size)} contratti (moltiplicatore: 10000)")
                else:
                    adjusted_short_size = -sol_amount
                
                # Invia gli ordini
                long_price = price_long if order_type == "Limit" else None
                short_price = price_short if order_type == "Limit" else None
                
                is_market = (order_type == "Market")
                
                # Esegui gli ordini in sequenza
                # Prima l'ordine LONG
                long_result = api_long.submit_order(
                    symbol=symbol_long,
                    amount=adjusted_long_size,
                    price=long_price,
                    market=is_market
                )
                
                # Poi l'ordine SHORT
                short_result = api_short.submit_order(
                    symbol=symbol_short,
                    amount=adjusted_short_size,
                    price=short_price,
                    market=is_market
                )
                
                # Visualizza i risultati
                st.success("Ordini inviati con successo!")
                
                # Mostra i dettagli degli ordini in un expander
                with st.expander("Dettagli ordini"):
                    st.subheader(f"Ordine LONG su {exchange_long}")
                    st.json(long_result)
                    
                    st.subheader(f"Ordine SHORT su {exchange_short}")
                    st.json(short_result)
                
                # Aggiungi un pulsante per gestire le posizioni
                st.session_state['has_open_positions'] = True
                
                if st.button("Gestisci Posizioni", type="secondary", use_container_width=True):
                    position_management_app()

def main():
    """Entry point principale della web app"""
    funding_arbitrage_app()

if __name__ == "__main__":
    main() 