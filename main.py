"""
Main Application - Checkpoint Version 1.0
Data: 15/05/2025
"""

import streamlit as st
from funding_arbitrage import funding_arbitrage_app
from position_management import position_management_app
from funding_rates import funding_rates_app
from transfer import TransferAPI
#from bitfinex_transfer import bitfinex_transfer_app
import time
from datetime import datetime

# Configurazione della pagina
st.set_page_config(
    page_title="Funding Arbitrage Platform",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

def format_datetime(timestamp):
    """Formatta un timestamp in una data e ora leggibile"""
    if timestamp:
        dt = datetime.fromtimestamp(timestamp / 1000)  # Converti da millisecondi a secondi
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    return "N/A"

def transfer_app():
    st.title("💸 Trasferimento USDT")
    
    # Inizializza l'API di trasferimento
    try:
        transfer_api = TransferAPI()
        
        # Verifica le API keys prima di procedere
        with st.expander("🔑 Stato API Keys", expanded=False):
            if st.button("Verifica API Keys"):
                with st.spinner("Verifica delle API keys in corso..."):
                    api_status = transfer_api.verify_api_keys()
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        if api_status["bybit"]["valid"]:
                            st.success("✅ ByBit: API keys valide")
                        else:
                            st.error(f"❌ ByBit: API keys non valide")
                            if api_status["bybit"]["error"]:
                                st.code(api_status["bybit"]["error"])
                    
                    with col2:
                        if api_status["bitmex"]["valid"]:
                            st.success("✅ BitMEX: API keys valide")
                        else:
                            st.error(f"❌ BitMEX: API keys non valide")
                            if api_status["bitmex"]["error"]:
                                st.code(api_status["bitmex"]["error"])
                                
                    with col3:
                        if api_status["bitfinex"]["valid"]:
                            st.success("✅ Bitfinex: API keys valide")
                        else:
                            st.error(f"❌ Bitfinex: API keys non valide")
                            if api_status["bitfinex"]["error"]:
                                st.code(api_status["bitfinex"]["error"])
    except Exception as e:
        st.error(f"Errore nell'inizializzazione: {str(e)}")
        if "Invalid API Key" in str(e):
            st.warning("Sembra che ci sia un problema con le chiavi API. Assicurati che le nuove chiavi API siano state salvate correttamente nel file .env e riavvia l'applicazione.")
        st.stop()
    
    # Form di trasferimento
    with st.form("transfer_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            source = st.selectbox(
                "Exchange di Origine",
                ["bybit", "bitmex", "bitfinex"],
                format_func=lambda x: "ByBit" if x == "bybit" else ("BitMEX" if x == "bitmex" else "Bitfinex")
            )
            
            # Rimuovo la selezione del wallet di origine per Bitfinex perché i fondi
            # saranno sempre su margin e il trasferimento interno sarà automatico
        
        with col2:
            destination = st.selectbox(
                "Exchange di Destinazione",
                ["bybit", "bitmex", "bitfinex"],
                format_func=lambda x: "ByBit" if x == "bybit" else ("BitMEX" if x == "bitmex" else "Bitfinex")
            )
            
            # Se la destinazione è Bitfinex, offri l'opzione per selezionare il wallet
            if destination == "bitfinex":
                dest_wallet = st.selectbox(
                    "Wallet di Destinazione (Bitfinex)",
                    ["margin", "exchange"],
                    format_func=lambda x: x.capitalize()
                )
        
        amount = st.number_input(
            "Quantità USDT",
            min_value=0.0,
            step=0.01,
            format="%.2f"
        )
        
        submit = st.form_submit_button("Trasferisci")
        
        if submit:
            if source == destination:
                st.error("Non puoi trasferire sullo stesso exchange")
            elif amount <= 0:
                st.error("La quantità deve essere maggiore di 0")
            else:
                try:
                    with st.spinner("Elaborazione del trasferimento in corso..."):
                        # Combinazioni con ByBit
                        if source == "bybit" and destination == "bitmex":
                            result = transfer_api.transfer_bybit_to_bitmex(amount)
                        elif source == "bybit" and destination == "bitfinex":
                            result = transfer_api.transfer_bybit_to_bitfinex(amount, dest_wallet if 'dest_wallet' in locals() else 'margin')
                        # Combinazioni con BitMEX
                        elif source == "bitmex" and destination == "bybit":
                            result = transfer_api.transfer_bitmex_to_bybit(amount)
                        elif source == "bitmex" and destination == "bitfinex":
                            result = transfer_api.transfer_bitmex_to_bitfinex(amount, dest_wallet if 'dest_wallet' in locals() else 'margin')
                        # Combinazioni con Bitfinex
                        elif source == "bitfinex" and destination == "bybit":
                            # Per Bitfinex, usiamo sempre 'margin' come wallet di origine
                            result = transfer_api.transfer_bitfinex_to_bybit(amount, 'margin')
                        elif source == "bitfinex" and destination == "bitmex":
                            # Per Bitfinex, usiamo sempre 'margin' come wallet di origine
                            result = transfer_api.transfer_bitfinex_to_bitmex(amount, 'margin')
                        else:
                            st.error("Combinazione di exchange non supportata")
                            return
                    
                    if result["success"]:
                        st.success(result["message"])
                        
                        # Salva le informazioni del prelievo in session state
                        st.session_state.last_withdrawal = {
                            "id": result.get("withdrawal_id"),
                            "exchange": result.get("exchange"),
                            "amount": result.get("amount"),
                            "fee": result.get("fee")
                        }
                    else:
                        st.error(result["error"])
                except Exception as e:
                    st.error(f"Errore durante il trasferimento: {str(e)}")
    
    # Sezione per visualizzare e aggiornare lo stato del prelievo
    st.divider()
    st.subheader("🔄 Stato del Prelievo")
    
    # Controlla se c'è un prelievo recente
    if "last_withdrawal" in st.session_state:
        withdrawal = st.session_state.last_withdrawal
        
        # Mostra le informazioni di base del prelievo
        st.info(f"Ultimo prelievo: {withdrawal.get('amount')} USDT da {withdrawal.get('exchange').upper()}")
        
        # Bottone per aggiornare lo stato
        if st.button("🔄 Aggiorna Stato"):
            with st.spinner("Recupero dello stato in corso..."):
                # Aggiungi un piccolo ritardo per evitare problemi di rate limiting
                time.sleep(1)
                
                # Recupera lo stato aggiornato
                status = transfer_api.get_withdrawal_status(
                    withdrawal.get("exchange"),
                    withdrawal.get("id")
                )
                
                # Aggiorna lo stato nel session state
                st.session_state.withdrawal_status = status
        
        # Mostra i dettagli dello stato se disponibili
        if "withdrawal_status" in st.session_state:
            status = st.session_state.withdrawal_status
            
            if status["success"]:
                # Crea un espander per i dettagli
                with st.expander("Dettagli Transazione", expanded=True):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**ID Prelievo:**", status.get("id", "N/A"))
                        st.write("**Valuta:**", status.get("currency", "USDT"))
                        st.write("**Importo:**", f"{status.get('amount', 0)} USDT")
                        
                        # Gestione della fee che può essere un oggetto o un valore semplice
                        fee = status.get('fee', 0)
                        if isinstance(fee, dict):
                            # Formato fee come oggetto (tipico di ByBit)
                            fee_display = f"{fee.get('cost', 0)} {fee.get('currency', 'USDT')}"
                        else:
                            # Formato fee come valore semplice (tipico di BitMEX)
                            fee_display = f"{fee} USDT"
                        
                        st.write("**Fee:**", fee_display)
                    
                    with col2:
                        st.write("**Stato:**", status.get("status", "sconosciuto").upper())
                        st.write("**Data:**", format_datetime(status.get("timestamp")))
                        st.write("**Indirizzo:**", status.get("address", "N/A"))
                    
                    # Se c'è un hash della transazione, mostralo in evidenza
                    if status.get("txid"):
                        st.success(f"**Hash Transazione (TX):** {status.get('txid')}")
                        
                        # Aggiungi il link alla blockchain explorer appropriato in base all'exchange
                        blockchain_explorer = "https://solscan.io/tx/"  # Default Solana
                        exchange = withdrawal.get("exchange", "").lower()
                        
                        # Determina l'explorer in base all'exchange
                        if exchange == "bitfinex":
                            blockchain_explorer = "https://tronscan.org/#/transaction/"  # Tron per Bitfinex
                        
                        st.markdown(f"[Visualizza sulla Blockchain]({blockchain_explorer}{status.get('txid')})")
                    else:
                        st.warning("Hash transazione non ancora disponibile. La transazione potrebbe essere in elaborazione.")
            else:
                st.error(f"Impossibile recuperare lo stato: {status.get('error')}")
    else:
        st.info("Nessun prelievo recente. Effettua un trasferimento per visualizzare lo stato.")

# Funzione principale che gestisce la navigazione
def main():
    # Configurazione della sidebar
    with st.sidebar:
        st.title("📊 Navigazione")
        
        # Selettore di pagina
        pagina = st.radio(
            "Seleziona Modulo:",
            ["🔄 Funding Arbitrage", "📋 Gestione Posizioni", "📊 Funding Rates", "💸 Trasferimento",]
        )
        
        # Informazioni aggiuntive nella sidebar
        st.divider()
        st.caption("Versione: 1.0")
        st.caption("© 2025 - Tutti i diritti riservati")

    # Navigazione tra le pagine
    if pagina == "🔄 Funding Arbitrage":
        funding_arbitrage_app()
    elif pagina == "📋 Gestione Posizioni":
        position_management_app()
    elif pagina == "📊 Funding Rates":
        funding_rates_app()
    elif pagina == "💱 Bitfinex Transfer":
        bitfinex_transfer_app()
    else:
        transfer_app()

# Esegui l'applicazione principale
if __name__ == "__main__":
    main() 