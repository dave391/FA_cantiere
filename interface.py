"""
Trading Bot Interface - Interfaccia utente per la gestione dei bot automatici
"""

import streamlit as st
import time
import os
import subprocess
import pandas as pd
from datetime import datetime, timezone

# Importa le dipendenze necessarie
from database.mongo_manager import MongoManager
from core.bot_engine import BotManager

# Configurazione della pagina
st.set_page_config(
    page_title="Trading Bot Manager",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inizializza le connessioni
db = MongoManager()
bot_manager = BotManager()

def format_datetime(timestamp):
    """Formatta un timestamp in una data e ora leggibile"""
    if timestamp:
        if isinstance(timestamp, datetime):
            dt = timestamp
        else:
            dt = datetime.fromtimestamp(timestamp / 1000)  # Converti da millisecondi a secondi
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    return "N/A"

def format_duration(start_time):
    """Calcola e formatta la durata di esecuzione"""
    if not start_time:
        return "N/A"
    
    if isinstance(start_time, str):
        return start_time
    
    now = datetime.now(timezone.utc)
    if isinstance(start_time, datetime):
        duration = now - start_time
    else:
        start_dt = datetime.fromtimestamp(start_time / 1000, timezone.utc)
        duration = now - start_dt
    
    days = duration.days
    hours, remainder = divmod(duration.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if days > 0:
        return f"{days}g {hours}h {minutes}m"
    else:
        return f"{hours}h {minutes}m {seconds}s"

def start_bot_process(user_id, config_name=None):
    """Avvia un processo bot in background"""
    try:
        command = ["python", "bot_main.py", "start", user_id]
        if config_name:
            command.append(config_name)
        
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            return {"success": True, "output": result.stdout.strip()}
        else:
            return {"success": False, "error": result.stderr.strip()}
    except Exception as e:
        return {"success": False, "error": str(e)}

def stop_bot_process(bot_id):
    """Ferma un processo bot specifico"""
    try:
        result = subprocess.run(
            ["python", "bot_main.py", "stop", bot_id],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            return {"success": True, "output": result.stdout.strip()}
        else:
            return {"success": False, "error": result.stderr.strip()}
    except Exception as e:
        return {"success": False, "error": str(e)}

def check_bot_status(bot_id):
    """Verifica lo stato di un bot"""
    try:
        result = bot_manager.get_bot_status(bot_id)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}

def create_user_if_not_exists(user_id, email):
    """Crea un nuovo utente se non esiste già"""
    user = db.get_user(user_id)
    if not user:
        db.create_user({
            "user_id": user_id,
            "email": email,
            "name": user_id
        })
        return True
    return False

def create_default_config_if_not_exists(user_id):
    """Crea una configurazione predefinita se non ne esiste nessuna"""
    configs = db.get_bot_configs(user_id)
    if not configs:
        default_config = {
            "strategy_type": "funding_arbitrage",
            "parameters": {
                "symbol": "SOLUSDT",
                "amount": 1.0,
                "min_funding_diff": 0.01,
                "check_interval": 10,
                "cooling_period": 5
            },
            "exchanges": ["bybit", "bitmex"],
            "risk_limits": {
                "max_risk_level": 80,
                "liquidation_buffer": 20,
                "max_position_size": 1000
            },
            "margin_balance": {
                "threshold": 20,
                "check_times": ["12:00", "00:00"]
            }
        }
        db.save_bot_config(user_id, "default", default_config)
        return True
    return False

def bot_dashboard():
    """Dashboard principale per la gestione dei bot"""
    st.title("🤖 Trading Bot Manager")
    
    # Form per l'autenticazione/gestione utente
    with st.expander("👤 Gestione Utente", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            user_id = st.text_input("ID Utente", value="user1")
            email = st.text_input("Email", value="user@example.com")
            
            if st.button("Crea/Aggiorna Utente"):
                try:
                    create_user_if_not_exists(user_id, email)
                    create_default_config_if_not_exists(user_id)
                    st.success(f"Utente {user_id} configurato con successo!")
                except Exception as e:
                    st.error(f"Errore: {str(e)}")
        
        with col2:
            # Recupera e mostra le configurazioni dell'utente
            try:
                configs = db.get_bot_configs(user_id)
                if configs:
                    config_names = [c["config_name"] for c in configs]
                    selected_config = st.selectbox("Configurazione", config_names)
                    
                    # Mostra dettagli della configurazione selezionata
                    selected_config_data = next((c for c in configs if c["config_name"] == selected_config), None)
                    if selected_config_data:
                        st.code(str(selected_config_data["parameters"]))
                else:
                    st.warning("Nessuna configurazione trovata per questo utente")
            except Exception as e:
                st.error(f"Errore nel recupero delle configurazioni: {str(e)}")
    
    # Sezione per avviare un nuovo bot
    st.divider()
    st.subheader("▶️ Avvia Nuovo Bot")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Form per avviare un nuovo bot
        start_user_id = st.text_input("ID Utente", value=user_id, key="start_user")
        
        try:
            user_configs = db.get_bot_configs(start_user_id)
            if user_configs:
                config_options = [c["config_name"] for c in user_configs]
                start_config = st.selectbox("Configurazione", config_options)
            else:
                start_config = None
                st.warning("Nessuna configurazione trovata per questo utente")
        except Exception as e:
            start_config = None
            st.error(f"Errore nel recupero delle configurazioni: {str(e)}")
        
        # Bottone per avviare il bot
        if st.button("▶️ Avvia Bot"):
            with st.spinner("Avvio del bot in corso..."):
                result = bot_manager.start_bot(start_user_id, start_config)
                
                if result["success"]:
                    st.success(f"Bot avviato con successo! ID: {result['bot_id']}")
                else:
                    st.error(f"Errore nell'avvio del bot: {result.get('error', 'Errore sconosciuto')}")
    
    with col2:
        # Mostra un riepilogo dei bot attivi
        st.subheader("🔄 Bot Attivi")
        try:
            active_bots = []
            for user in db.users.find({}):
                user_bots = db.get_active_bots(user["user_id"])
                active_bots.extend(user_bots)
            
            if active_bots:
                st.info(f"🤖 {len(active_bots)} bot attivi")
            else:
                st.info("🔍 Nessun bot attivo")
        except Exception as e:
            st.error(f"Errore nel recupero dei bot attivi: {str(e)}")
    
    # Sezione per monitorare e gestire i bot attivi
    st.divider()
    st.subheader("📊 Monitoraggio Bot")
    
    try:
        # Recupera tutti i bot (attivi e inattivi)
        all_bots = []
        for user in db.users.find({}):
            # Recupera i bot attivi
            user_bots = list(db.bot_status.find({"user_id": user["user_id"]}))
            all_bots.extend(user_bots)
        
        if all_bots:
            # Prepara i dati per la tabella
            bot_data = []
            for bot in all_bots:
                # Recupera il numero di posizioni aperte
                positions_count = bot.get("positions_count", 0)
                
                # Calcola la durata di esecuzione
                if bot.get("status") == "running":
                    duration = format_duration(bot.get("started_at"))
                    status_icon = "✅"
                else:
                    if bot.get("stopped_at"):
                        duration = format_duration(bot.get("started_at")) + " (fermato)"
                    else:
                        duration = "N/A"
                    status_icon = "❌"
                
                # Aggiungi alla lista dei bot
                bot_data.append({
                    "ID": bot.get("bot_id", ""),
                    "Utente": bot.get("user_id", ""),
                    "Stato": f"{status_icon} {bot.get('status', '').upper()}",
                    "Configurazione": bot.get("config_name", ""),
                    "Posizioni": positions_count,
                    "PnL": f"{bot.get('total_pnl', 0):.2f} USDT",
                    "Attivo da": duration,
                    "Ultima attività": format_datetime(bot.get("last_activity"))
                })
            
            # Crea il dataframe e visualizzalo
            df = pd.DataFrame(bot_data)
            st.dataframe(df, use_container_width=True)
            
            # Sezione per fermare un bot specifico
            st.divider()
            st.subheader("⏹️ Ferma Bot")
            
            # Lista dei bot attivi
            active_bot_ids = [bot["bot_id"] for bot in all_bots if bot["status"] == "running"]
            
            if active_bot_ids:
                selected_bot_id = st.selectbox("Seleziona Bot da Fermare", active_bot_ids)
                
                if st.button("⏹️ Ferma Bot"):
                    with st.spinner("Arresto del bot in corso..."):
                        result = bot_manager.stop_bot(selected_bot_id)
                        
                        if result["success"]:
                            st.success(f"Bot {selected_bot_id} fermato con successo!")
                        else:
                            st.error(f"Errore nell'arresto del bot: {result.get('error', 'Errore sconosciuto')}")
            else:
                st.info("Nessun bot attivo da fermare")
        else:
            st.info("Nessun bot trovato nel database")
    except Exception as e:
        st.error(f"Errore nel recupero dei bot: {str(e)}")
    
    # Sezione per le statistiche
    st.divider()
    st.subheader("📈 Statistiche")
    
    try:
        # Recupera statistiche aggregate
        stats = {}
        for user in db.users.find({}):
            user_id = user["user_id"]
            user_stats = db.get_stats(user_id)
            
            # Aggiorna le statistiche totali
            for key, value in user_stats.items():
                if key in stats:
                    if isinstance(value, (int, float)):
                        stats[key] += value
                    elif isinstance(value, list):
                        stats[key].extend(value)
                else:
                    stats[key] = value
        
        # Visualizza le statistiche
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Utenti", stats.get("users_count", 0))
        
        with col2:
            st.metric("Bot Attivi", stats.get("active_bots_count", 0))
        
        with col3:
            st.metric("Posizioni Aperte", stats.get("active_positions_count", 0))
        
        with col4:
            st.metric("Eventi di Rischio (24h)", stats.get("risk_events_24h", 0))
        
    except Exception as e:
        st.error(f"Errore nel recupero delle statistiche: {str(e)}")


# Funzione principale
def main():
    # Sidebar
    with st.sidebar:
        st.title("📊 Navigazione")
        
        # Selettore di pagina
        pagina = st.radio(
            "Seleziona Vista:",
            ["🤖 Dashboard Bot", "📊 Analisi Posizioni", "⚙️ Configurazioni"]
        )
        
        # Informazioni aggiuntive
        st.divider()
        st.caption("Versione: 2.0 (Automatica)")
        st.caption("© 2025 - Tutti i diritti riservati")
    
    # Pagine
    if pagina == "🤖 Dashboard Bot":
        bot_dashboard()
    elif pagina == "📊 Analisi Posizioni":
        st.title("📊 Analisi Posizioni")
        st.info("Funzionalità in sviluppo...")
    else:
        st.title("⚙️ Configurazioni")
        st.info("Funzionalità in sviluppo...")


# Avvio dell'applicazione
if __name__ == "__main__":
    main() 