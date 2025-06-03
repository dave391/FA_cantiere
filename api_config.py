"""
API Keys Configuration - Pagina per configurare le chiavi API
"""

import streamlit as st
import os
import time
from dotenv import load_dotenv
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
    """Pagina principale per configurazione API keys"""
    # Verifica che l'utente sia autenticato
    if not check_auth():
        return
    
    # Recupera l'ID utente dalla sessione
    user_id = st.session_state.user_id
    
    # Mostra info utente nella sidebar
    st.sidebar.subheader(f"👤 Utente: {user_id}")
    
    # Pulsante per tornare alla home
    if st.sidebar.button("🏠 Torna alla Home", key="home_button"):
        st.session_state.current_page = "app"
        st.experimental_rerun()
    
    # Pulsante di logout nella sidebar
    if st.sidebar.button("🚪 Logout", key="logout_button"):
        from login import logout_user
        logout_user()
    
    # Titolo pagina
    st.title("🔑 Configurazione API Keys")
    st.subheader("Configura le tue chiavi API per gli exchange")
    
    # Recupera le API keys attuali
    current_keys = {}
    if db:
        user_data = db.get_user(user_id)
        if user_data and "exchange_credentials" in user_data:
            current_keys = user_data.get("exchange_credentials", {})
    
    # Creazione exchange manager per l'utente
    exchange_manager = ExchangeManager(user_id, db)
    
    # Tab per ogni exchange
    tabs = st.tabs(["BitMEX", "ByBit", "Bitfinex"])
    
    with tabs[0]:
        configure_exchange("bitmex", current_keys, exchange_manager)
    
    with tabs[1]:
        configure_exchange("bybit", current_keys, exchange_manager)
    
    with tabs[2]:
        configure_exchange("bitfinex", current_keys, exchange_manager)
    
    # Pulsante per tornare alla home
    if st.button("🏠 Torna alla Home", use_container_width=True):
        st.session_state.current_page = "app"
        st.experimental_rerun()

def configure_exchange(exchange_id, current_keys, exchange_manager):
    """Configura le API keys per un exchange specifico"""
    st.header(f"{exchange_id.upper()} API Keys")
    
    # Ottieni le chiavi attuali
    has_keys = exchange_id in current_keys and current_keys[exchange_id].get("api_key")
    api_key_value = current_keys.get(exchange_id, {}).get("api_key", "") if has_keys else ""
    api_secret_value = current_keys.get(exchange_id, {}).get("api_secret", "") if has_keys else ""
    
    # Mostra stato attuale
    if has_keys:
        st.success(f"✅ {exchange_id.upper()} configurato")
        # Mostra le prime/ultime 4 cifre della chiave per verifica
        masked_key = f"{api_key_value[:4]}...{api_key_value[-4:]}" if len(api_key_value) > 8 else "****"
        st.write(f"API Key attuale: `{masked_key}`")
    else:
        st.error(f"❌ {exchange_id.upper()} non configurato")
    
    # Form per aggiornare le keys
    with st.form(f"api_form_{exchange_id}", clear_on_submit=False):
        st.subheader(f"{'Aggiorna' if has_keys else 'Configura'} {exchange_id.upper()}")
        
        new_api_key = st.text_input(
            "API Key", 
            value=api_key_value,
            type="password" if has_keys else "default",
            placeholder="Inserisci la tua API Key"
        )
        
        new_api_secret = st.text_input(
            "API Secret", 
            value=api_secret_value,
            type="password",
            placeholder="Inserisci il tuo API Secret"
        )
        
        # Istruzioni per generare le chiavi
        with st.expander("ℹ️ Come generare le API Keys"):
            st.markdown(f"""
            ### Istruzioni per {exchange_id.upper()}
            
            1. Accedi al tuo account {exchange_id.upper()}
            2. Vai alla sezione API Management o Impostazioni API
            3. Genera una nuova chiave API con i seguenti permessi:
               - Lettura saldo
               - Lettura posizioni
               - Trading (apertura/chiusura posizioni)
            4. Copia le chiavi generate e incollale qui
            5. Assicurati di salvare le chiavi in un posto sicuro
            
            **IMPORTANTE**: Non condividere mai le tue chiavi API con nessuno!
            """)
        
        # Pulsante per verificare le chiavi
        submit = st.form_submit_button(f"📝 {'Aggiorna' if has_keys else 'Salva'} API Keys", use_container_width=True)
        
        if submit:
            if not new_api_key or not new_api_secret:
                st.error("Entrambi i campi sono obbligatori")
            else:
                with st.spinner("Salvataggio e verifica delle chiavi..."):
                    # Salva le nuove chiavi
                    if db:
                        result = exchange_manager.save_user_credentials(exchange_id, new_api_key, new_api_secret)
                        
                        if result:
                            st.success(f"✅ API Keys {exchange_id.upper()} salvate con successo!")
                            
                            # Verifica le chiavi
                            status = exchange_manager.verify_api_keys()
                            if exchange_id in status and status[exchange_id]["valid"]:
                                st.success(f"✅ Connessione a {exchange_id.upper()} verificata!")
                            else:
                                error_msg = status.get(exchange_id, {}).get("error", "Errore sconosciuto")
                                st.warning(f"⚠️ Le chiavi sono state salvate ma la verifica ha fallito: {error_msg}")
                        else:
                            st.error("❌ Errore nel salvataggio delle API Keys")
                    else:
                        # Modalità di test
                        st.success(f"✅ API Keys {exchange_id.upper()} salvate con successo! (modalità test)")
                        time.sleep(1)
                        st.experimental_rerun()

if __name__ == "__main__":
    main() 