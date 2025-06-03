"""
Admin Dashboard - Pannello di controllo per amministratori
"""

import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime, timedelta
import plotly.express as px
from dotenv import load_dotenv
from database.mongo_manager import MongoManager
from core.auth_manager import AuthManager

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

def check_admin():
    """Verifica che l'utente sia un amministratore"""
    if not "authenticated" in st.session_state or not st.session_state.authenticated:
        st.warning("Sessione non valida. Effettua il login.")
        st.session_state.current_page = "login"
        st.experimental_rerun()
        return False
        
    if not "is_admin" in st.session_state or not st.session_state.is_admin:
        st.error("Accesso non autorizzato. Questa pagina è riservata agli amministratori.")
        st.session_state.current_page = "app"
        st.experimental_rerun()
        return False
        
    # Verifica validità sessione
    if "session_token" in st.session_state:
        user_data = auth.validate_session(st.session_state.session_token)
        if not user_data or not user_data.get("is_admin", False):
            st.warning("La tua sessione è scaduta o non hai i permessi necessari.")
            st.session_state.current_page = "login"
            st.experimental_rerun()
            return False
    
    return True

def get_all_users():
    """Recupera tutti gli utenti dal database"""
    if not db:
        # Dati di test
        return [
            {"user_id": "user_test1", "email": "admin@example.com", "name": "Admin Test", "is_admin": True, "created_at": datetime.now()},
            {"user_id": "user_test2", "email": "user1@example.com", "name": "Utente Test 1", "is_admin": False, "created_at": datetime.now()},
            {"user_id": "user_test3", "email": "user2@example.com", "name": "Utente Test 2", "is_admin": False, "created_at": datetime.now()}
        ]
    
    try:
        # Recupera utenti dal database
        users = list(db.users.find({}, {
            "_id": 0,
            "user_id": 1,
            "email": 1,
            "name": 1,
            "is_admin": 1,
            "is_active": 1,
            "created_at": 1
        }))
        return users
    except Exception as e:
        st.error(f"Errore nel recupero degli utenti: {str(e)}")
        return []

def get_active_bots():
    """Recupera tutti i bot attivi"""
    if not db:
        # Dati di test
        return [
            {"bot_id": "bot1", "user_id": "user_test1", "status": "running", "config_name": "Funding Arb", "started_at": datetime.now()},
            {"bot_id": "bot2", "user_id": "user_test2", "status": "running", "config_name": "Funding Arb", "started_at": datetime.now() - timedelta(hours=2)},
            {"bot_id": "bot3", "user_id": "user_test3", "status": "stopped", "config_name": "Funding Arb", "started_at": datetime.now() - timedelta(days=1)}
        ]
    
    try:
        # Recupera bot dal database
        bots = list(db.bot_status.find({}, {
            "_id": 0,
            "bot_id": 1,
            "user_id": 1,
            "status": 1,
            "config_name": 1,
            "started_at": 1,
            "stopped_at": 1,
            "last_activity": 1,
            "positions_count": 1,
            "total_pnl": 1
        }))
        return bots
    except Exception as e:
        st.error(f"Errore nel recupero dei bot: {str(e)}")
        return []

def toggle_user_status(user_id, active):
    """Attiva o disattiva un utente"""
    if not db:
        st.warning("Funzionalità non disponibile in modalità test")
        return False
    
    try:
        result = db.users.update_one(
            {"user_id": user_id},
            {"$set": {"is_active": active}}
        )
        return result.modified_count > 0
    except Exception as e:
        st.error(f"Errore nell'aggiornamento dello stato utente: {str(e)}")
        return False

def toggle_admin_status(user_id, admin):
    """Rende un utente amministratore o revoca i privilegi"""
    if not db:
        st.warning("Funzionalità non disponibile in modalità test")
        return False
    
    try:
        result = db.users.update_one(
            {"user_id": user_id},
            {"$set": {"is_admin": admin}}
        )
        return result.modified_count > 0
    except Exception as e:
        st.error(f"Errore nell'aggiornamento dello stato admin: {str(e)}")
        return False

def stop_bot(bot_id):
    """Ferma un bot attivo"""
    if not db:
        st.warning("Funzionalità non disponibile in modalità test")
        return False
    
    try:
        result = db.bot_status.update_one(
            {"bot_id": bot_id},
            {
                "$set": {
                    "status": "stopped",
                    "stopped_at": datetime.now()
                }
            }
        )
        return result.modified_count > 0
    except Exception as e:
        st.error(f"Errore nell'arresto del bot: {str(e)}")
        return False

def get_system_stats():
    """Recupera statistiche globali del sistema"""
    if not db:
        # Dati di test
        return {
            "total_users": 3,
            "active_users": 3,
            "total_bots": 3,
            "active_bots": 2,
            "total_positions": 5,
            "total_pnl": 125.43
        }
    
    try:
        # Conteggio utenti
        total_users = db.users.count_documents({})
        active_users = db.users.count_documents({"is_active": True})
        
        # Conteggio bot
        total_bots = db.bot_status.count_documents({})
        active_bots = db.bot_status.count_documents({"status": "running"})
        
        # Conteggio posizioni
        total_positions = db.active_positions.count_documents({"is_active": True})
        
        # Calcolo PnL totale
        pnl_agg = list(db.active_positions.aggregate([
            {"$match": {"is_active": True}},
            {"$group": {"_id": None, "total_pnl": {"$sum": "$unrealized_pnl"}}}
        ]))
        total_pnl = pnl_agg[0]["total_pnl"] if pnl_agg else 0
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_bots": total_bots,
            "active_bots": active_bots,
            "total_positions": total_positions,
            "total_pnl": total_pnl
        }
    except Exception as e:
        st.error(f"Errore nel recupero delle statistiche: {str(e)}")
        return {
            "total_users": 0,
            "active_users": 0,
            "total_bots": 0,
            "active_bots": 0,
            "total_positions": 0,
            "total_pnl": 0
        }

def main():
    """Dashboard principale per amministratori"""
    # Verifica che l'utente sia un amministratore
    if not check_admin():
        return
    
    # Header con info utente
    st.title("👑 Dashboard Amministratore")
    
    user_id = st.session_state.user_id
    user_data = auth.validate_session(st.session_state.session_token)
    
    st.sidebar.subheader(f"👤 {user_data.get('name', 'Admin')}")
    st.sidebar.caption(f"ID: {user_id}")
    
    if st.sidebar.button("🚪 Logout", key="logout_button"):
        from login import logout_user
        logout_user()
    
    # Tempo di refresh
    refresh_interval = 60  # secondi
    
    # Aggiorna automaticamente la pagina
    if 'last_admin_refresh' not in st.session_state:
        st.session_state.last_admin_refresh = datetime.now()
    
    time_since_refresh = (datetime.now() - st.session_state.last_admin_refresh).total_seconds()
    
    refresh_progress = time_since_refresh / refresh_interval
    if refresh_progress >= 1:
        st.session_state.last_admin_refresh = datetime.now()
        st.experimental_rerun()
    
    # Mostra barra di avanzamento per il prossimo refresh
    st.sidebar.progress(min(refresh_progress, 1.0), f"Aggiornamento tra {max(0, int(refresh_interval - time_since_refresh))}s")
    
    if st.sidebar.button("🔄 Aggiorna Ora"):
        st.session_state.last_admin_refresh = datetime.now()
        st.experimental_rerun()
    
    # Tabs per diversi tipi di informazioni
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "👥 Gestione Utenti", "🤖 Monitor Bot"])
    
    with tab1:
        dashboard_overview()
    
    with tab2:
        manage_users()
    
    with tab3:
        monitor_bots()

def dashboard_overview():
    """Panoramica generale del sistema"""
    st.subheader("📊 Panoramica Sistema")
    
    # Statistiche del sistema
    stats = get_system_stats()
    
    # Metriche in evidenza
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Utenti Totali", stats["total_users"])
        st.metric("Utenti Attivi", stats["active_users"])
    
    with col2:
        st.metric("Bot Totali", stats["total_bots"])
        st.metric("Bot Attivi", stats["active_bots"])
    
    with col3:
        st.metric("Posizioni Aperte", stats["total_positions"])
    
    with col4:
        st.metric("P&L Totale", f"{stats['total_pnl']:.2f} USDT")
    
    # Grafici di riepilogo
    st.subheader("📈 Grafici Riepilogo")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Grafico utenti attivi vs inattivi
        if stats["total_users"] > 0:
            user_status = pd.DataFrame([
                {"Stato": "Attivi", "Utenti": stats["active_users"]},
                {"Stato": "Inattivi", "Utenti": stats["total_users"] - stats["active_users"]}
            ])
            
            fig = px.pie(
                user_status, 
                values='Utenti', 
                names='Stato', 
                title='Stato Utenti',
                color='Stato',
                color_discrete_map={'Attivi': '#5cb85c', 'Inattivi': '#d9534f'}
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nessun dato utente disponibile per la visualizzazione")
    
    with col2:
        # Grafico bot attivi vs inattivi
        if stats["total_bots"] > 0:
            bot_status = pd.DataFrame([
                {"Stato": "In esecuzione", "Bot": stats["active_bots"]},
                {"Stato": "Fermi", "Bot": stats["total_bots"] - stats["active_bots"]}
            ])
            
            fig = px.pie(
                bot_status, 
                values='Bot', 
                names='Stato', 
                title='Stato Bot',
                color='Stato',
                color_discrete_map={'In esecuzione': '#5cb85c', 'Fermi': '#f0ad4e'}
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nessun dato bot disponibile per la visualizzazione")

def manage_users():
    """Gestione degli utenti del sistema"""
    st.subheader("👥 Gestione Utenti")
    
    # Recupera tutti gli utenti
    users = get_all_users()
    
    if not users:
        st.info("Nessun utente nel sistema")
        return
    
    # Prepara dataframe per visualizzazione
    user_data = []
    for user in users:
        user_data.append({
            "ID": user.get("user_id", ""),
            "Nome": user.get("name", ""),
            "Email": user.get("email", ""),
            "Amministratore": "✅" if user.get("is_admin", False) else "❌",
            "Stato": "Attivo" if user.get("is_active", True) else "Disattivato",
            "Data Registrazione": user.get("created_at", "").strftime("%d/%m/%Y %H:%M") if isinstance(user.get("created_at"), datetime) else ""
        })
    
    df_users = pd.DataFrame(user_data)
    
    # Filtro di ricerca
    search_term = st.text_input("🔍 Cerca utente (nome o email)", "")
    
    if search_term:
        filtered_df = df_users[
            df_users["Nome"].str.contains(search_term, case=False) | 
            df_users["Email"].str.contains(search_term, case=False)
        ]
    else:
        filtered_df = df_users
    
    # Visualizza tabella utenti
    st.dataframe(filtered_df, use_container_width=True)
    
    # Sezione gestione utente
    st.subheader("🛠️ Modifica Utente")
    
    # Selezione utente
    selected_user_id = st.selectbox(
        "Seleziona utente da modificare",
        options=[user["user_id"] for user in users],
        format_func=lambda x: next((f"{u['name']} ({u['email']})" for u in users if u["user_id"] == x), x)
    )
    
    if selected_user_id:
        selected_user = next((u for u in users if u["user_id"] == selected_user_id), None)
        
        if selected_user:
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Nome:** {selected_user.get('name', '')}")
                st.write(f"**Email:** {selected_user.get('email', '')}")
                
                # Toggle admin status
                is_admin = selected_user.get("is_admin", False)
                if st.checkbox("Amministratore", value=is_admin, key="admin_toggle"):
                    if not is_admin:  # Solo se lo stato è cambiato
                        if st.button("✅ Conferma promozione ad amministratore"):
                            if toggle_admin_status(selected_user_id, True):
                                st.success("Utente promosso ad amministratore!")
                                time.sleep(1)
                                st.experimental_rerun()
                            else:
                                st.error("Errore nell'aggiornamento dei permessi")
                else:
                    if is_admin:  # Solo se lo stato è cambiato
                        if st.button("✅ Conferma revoca privilegi amministratore"):
                            if toggle_admin_status(selected_user_id, False):
                                st.success("Privilegi di amministratore revocati!")
                                time.sleep(1)
                                st.experimental_rerun()
                            else:
                                st.error("Errore nell'aggiornamento dei permessi")
            
            with col2:
                # Toggle user status
                is_active = selected_user.get("is_active", True)
                
                if is_active:
                    if st.button("🚫 Disattiva Account", key="deactivate_user", type="primary"):
                        if toggle_user_status(selected_user_id, False):
                            st.success("Account utente disattivato!")
                            time.sleep(1)
                            st.experimental_rerun()
                        else:
                            st.error("Errore nella disattivazione dell'account")
                else:
                    if st.button("✅ Riattiva Account", key="activate_user", type="primary"):
                        if toggle_user_status(selected_user_id, True):
                            st.success("Account utente riattivato!")
                            time.sleep(1)
                            st.experimental_rerun()
                        else:
                            st.error("Errore nella riattivazione dell'account")

def monitor_bots():
    """Monitoraggio dei bot in esecuzione"""
    st.subheader("🤖 Monitor Bot Attivi")
    
    # Recupera tutti i bot
    bots = get_active_bots()
    
    if not bots:
        st.info("Nessun bot nel sistema")
        return
    
    # Prepara dataframe per visualizzazione
    bot_data = []
    for bot in bots:
        bot_data.append({
            "ID Bot": bot.get("bot_id", ""),
            "Utente": bot.get("user_id", ""),
            "Configurazione": bot.get("config_name", ""),
            "Stato": "🟢 Attivo" if bot.get("status") == "running" else "🔴 Fermo",
            "Avviato": bot.get("started_at", "").strftime("%d/%m/%Y %H:%M") if isinstance(bot.get("started_at"), datetime) else "",
            "Ultima Attività": bot.get("last_activity", "").strftime("%d/%m/%Y %H:%M") if isinstance(bot.get("last_activity"), datetime) else "",
            "Posizioni": bot.get("positions_count", 0),
            "P&L": f"{bot.get('total_pnl', 0):.2f} USDT"
        })
    
    df_bots = pd.DataFrame(bot_data)
    
    # Filtro di stato
    status_filter = st.radio(
        "Filtra per stato",
        options=["Tutti", "Attivi", "Fermi"],
        horizontal=True
    )
    
    if status_filter == "Attivi":
        filtered_df = df_bots[df_bots["Stato"].str.contains("Attivo")]
    elif status_filter == "Fermi":
        filtered_df = df_bots[df_bots["Stato"].str.contains("Fermo")]
    else:
        filtered_df = df_bots
    
    # Visualizza tabella bot
    st.dataframe(filtered_df, use_container_width=True)
    
    # Sezione controllo bot
    st.subheader("🛑 Arresto Bot")
    
    # Filtra solo i bot attivi per la selezione
    active_bots = [bot for bot in bots if bot.get("status") == "running"]
    
    if not active_bots:
        st.info("Nessun bot attivo da fermare")
        return
    
    # Selezione bot
    selected_bot_id = st.selectbox(
        "Seleziona bot da fermare",
        options=[bot["bot_id"] for bot in active_bots],
        format_func=lambda x: next((f"{b['bot_id']} (Utente: {b['user_id']})" for b in active_bots if b["bot_id"] == x), x)
    )
    
    if selected_bot_id:
        if st.button("⛔ Ferma Bot", key="stop_bot_button", type="primary"):
            if stop_bot(selected_bot_id):
                st.success(f"Bot {selected_bot_id} fermato con successo!")
                time.sleep(1)
                st.experimental_rerun()
            else:
                st.error("Errore nell'arresto del bot")

if __name__ == "__main__":
    main() 