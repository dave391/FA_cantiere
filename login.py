"""
Login e Registrazione - Pagina di autenticazione
"""

import streamlit as st
import os
import time
import sys
from dotenv import load_dotenv
from database.mongo_manager import MongoManager
from core.auth_manager import AuthManager

# Carica le variabili d'ambiente
load_dotenv()

# Configurazione pagina Streamlit
st.set_page_config(
    page_title="Trading Bot Platform",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inizializzazione componenti
try:
    db = MongoManager()
    auth = AuthManager(db)
except Exception as e:
    st.error(f"Errore di connessione al database: {str(e)}")
    db = None
    auth = AuthManager(None)  # Modalità di test

def main():
    """Pagina principale dell'applicazione"""
    
    # Inizializza la pagina corrente se non esiste
    if "current_page" not in st.session_state:
        st.session_state.current_page = "login"
    
    # Controlla l'autenticazione
    if st.session_state.current_page != "login" and st.session_state.current_page != "register":
        if not "authenticated" in st.session_state or not st.session_state.authenticated:
            st.session_state.current_page = "login"
    
    # Mostra la pagina corrente
    if st.session_state.current_page == "login":
        show_login_page()
    elif st.session_state.current_page == "app":
        show_app_page()
    elif st.session_state.current_page == "admin":
        show_admin_page()
    elif st.session_state.current_page == "api_config":
        show_api_config_page()
    elif st.session_state.current_page == "interface":
        show_interface_page()

def show_login_page():
    """Mostra la pagina di login/registrazione"""
    st.title("🔐 Accesso alla Piattaforma")
    
    # Titolo con logo
    col1, col2 = st.columns([1, 4])
    with col1:
        st.image("https://img.icons8.com/color/96/000000/robot.png", width=80)
    with col2:
        st.title("Trading Bot Platform")
    
    # Tabs per login e registrazione
    tab_login, tab_register = st.tabs(["🔑 Login", "📝 Registrazione"])
    
    with tab_login:
        login_form()
    
    with tab_register:
        registration_form()
    
    # Visualizza messaggio di logout se necessario
    if "logout_success" in st.session_state and st.session_state.logout_success:
        st.success("Logout effettuato con successo!")
        # Rimuovi il flag dopo averlo mostrato
        st.session_state.logout_success = False

def login_form():
    """Form di login"""
    with st.form("login_form", clear_on_submit=False):
        st.subheader("Accedi al tuo account")
        
        email = st.text_input("Email", placeholder="Inserisci la tua email")
        password = st.text_input("Password", type="password", placeholder="Inserisci la tua password")
        
        submit_login = st.form_submit_button("🔑 Login", use_container_width=True)
        
        if submit_login:
            if not email or not password:
                st.error("Inserisci email e password")
                return
            
            # Tentativo di autenticazione
            with st.spinner("Autenticazione in corso..."):
                user_id = auth.authenticate_user(email, password)
                
                if user_id:
                    # Autenticazione riuscita
                    session_token = auth.create_user_session(user_id)
                    
                    if session_token:
                        # Salva i dati di sessione
                        st.session_state.user_id = user_id
                        st.session_state.session_token = session_token
                        st.session_state.authenticated = True
                        
                        # Verifica se l'utente è admin
                        is_admin = auth.is_admin(user_id)
                        st.session_state.is_admin = is_admin
                        
                        st.success("Login effettuato con successo!")
                        
                        # Reindirizza alla pagina appropriata
                        if is_admin:
                            st.session_state.current_page = "admin"
                        else:
                            st.session_state.current_page = "app"
                        
                        st.experimental_rerun()
                    else:
                        st.error("Errore nella creazione della sessione")
                else:
                    st.error("Email o password non validi")

def registration_form():
    """Form di registrazione"""
    with st.form("registration_form", clear_on_submit=True):
        st.subheader("Crea un nuovo account")
        
        name = st.text_input("Nome", placeholder="Inserisci il tuo nome")
        email = st.text_input("Email", placeholder="Inserisci la tua email")
        password = st.text_input("Password", type="password", placeholder="Inserisci una password")
        password_confirm = st.text_input("Conferma Password", type="password", placeholder="Conferma la password")
        
        submit_registration = st.form_submit_button("📝 Registrati", use_container_width=True)
        
        if submit_registration:
            if not name or not email or not password:
                st.error("Tutti i campi sono obbligatori")
                return
                
            if password != password_confirm:
                st.error("Le password non coincidono")
                return
                
            if len(password) < 8:
                st.error("La password deve contenere almeno 8 caratteri")
                return
                
            # Tentativo di registrazione
            with st.spinner("Registrazione in corso..."):
                user_id = auth.register_user(email, password, name)
                
                if user_id:
                    # Registrazione riuscita
                    session_token = auth.create_user_session(user_id)
                    
                    if session_token:
                        # Salva i dati di sessione
                        st.session_state.user_id = user_id
                        st.session_state.session_token = session_token
                        st.session_state.authenticated = True
                        st.session_state.is_admin = False
                        
                        st.success("Registrazione completata con successo! Accesso in corso...")
                        
                        # Reindirizza alla pagina principale
                        st.session_state.current_page = "app"
                        st.experimental_rerun()
                    else:
                        st.error("Errore nella creazione della sessione")
                else:
                    st.error("Errore nella registrazione. L'email potrebbe essere già in uso.")

def show_app_page():
    """Mostra la pagina principale dell'applicazione"""
    import app
    app.main()

def show_admin_page():
    """Mostra la pagina di amministrazione"""
    import admin
    admin.main()

def show_api_config_page():
    """Mostra la pagina di configurazione API"""
    import api_config
    api_config.main()

def show_interface_page():
    """Mostra l'interfaccia di monitoraggio"""
    import interface
    interface.main()

def logout_user():
    """Effettua il logout dell'utente"""
    if "session_token" in st.session_state:
        # Invalida la sessione nel database
        auth.invalidate_session(st.session_state.session_token)
        
        # Rimuovi i dati di sessione
        if "user_id" in st.session_state:
            del st.session_state.user_id
        if "session_token" in st.session_state:
            del st.session_state.session_token
        if "authenticated" in st.session_state:
            del st.session_state.authenticated
        if "is_admin" in st.session_state:
            del st.session_state.is_admin
            
        # Imposta flag di logout
        st.session_state.logout_success = True
        
        # Torna alla pagina di login
        st.session_state.current_page = "login"
        st.experimental_rerun()

if __name__ == "__main__":
    main() 