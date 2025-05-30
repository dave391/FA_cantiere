"""
Dashboard di controllo per Bot Semi-Automatico
Data: 30/07/2024
"""

import streamlit as st
import pandas as pd
import time
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Carica le variabili d'ambiente
load_dotenv()

# Configurazione pagina Streamlit
st.set_page_config(
    page_title="Dashboard Bot",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

def get_bot_attivi():
    """Recupera informazioni sui bot attivi dalla sessione"""
    if 'trading_system' in st.session_state and st.session_state.trading_system:
        # Recupera lo stato del bot
        status = st.session_state.trading_system.get_status()
        
        if status["success"]:
            return [{
                "id": "1",
                "user_id": status.get("user_id", "utente"),
                "running": status.get("active", False),
                "num_positions": status.get("num_positions", 0),
                "positions": status.get("positions", []),
                "pnl": sum([float(p.get("unrealizedPnl", 0)) for p in status.get("positions", [])]),
                "last_updated": status.get("last_updated", datetime.now().isoformat())
            }]
        
    return []

def ferma_bot(bot_id):
    """Ferma un bot attivo"""
    if 'trading_system' in st.session_state and st.session_state.trading_system:
        result = st.session_state.trading_system.stop_bot()
        
        if result["success"]:
            st.session_state.bot_running = False
            st.session_state.trading_system = None
            return True
    
    return False

def format_timestamp(timestamp_str):
    """Formatta il timestamp in un formato leggibile"""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime('%d/%m/%Y %H:%M:%S')
    except:
        return timestamp_str

def dashboard():
    """Dashboard principale per monitorare i bot attivi"""
    st.title("🤖 Dashboard Bot Automatici")
    
    # Recupera i bot attivi
    bot_attivi = get_bot_attivi()
    
    # Tempo di refresh
    refresh_interval = 30  # secondi
    
    # Aggiorna automaticamente la pagina
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = datetime.now()
    
    time_since_refresh = (datetime.now() - st.session_state.last_refresh).total_seconds()
    
    refresh_progress = time_since_refresh / refresh_interval
    if refresh_progress >= 1:
        st.session_state.last_refresh = datetime.now()
        st.rerun()
    
    # Mostra barra di avanzamento per il prossimo refresh
    st.progress(min(refresh_progress, 1.0), f"Prossimo aggiornamento tra {max(0, int(refresh_interval - time_since_refresh))}s")
    
    if st.button("🔄 Aggiorna Ora"):
        st.session_state.last_refresh = datetime.now()
        st.rerun()
    
    if not bot_attivi:
        st.warning("Nessun bot attivo al momento.")
        
        if st.button("🚀 Avvia Nuovo Bot", use_container_width=True):
            st.switch_page("app.py")
            
        return
    
    # Layout a tab per diversi tipi di informazioni
    tab1, tab2, tab3 = st.tabs(["📊 Panoramica", "📈 Posizioni", "⚙️ Controlli"])
    
    with tab1:
        # Panoramica
        st.subheader("Stato dei Bot")
        
        for bot in bot_attivi:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Stato", "🟢 Attivo" if bot["running"] else "🔴 Fermo")
                st.write(f"**ID Bot:** {bot['id']}")
                st.write(f"**Utente:** {bot['user_id']}")
                
            with col2:
                st.metric("Posizioni Aperte", bot["num_positions"])
                st.metric("P&L Totale", f"{bot['pnl']:.2f} USDT")
                
            with col3:
                st.write(f"**Ultimo Aggiornamento:** {format_timestamp(bot['last_updated'])}")
                
                if st.button(f"⏹️ Ferma Bot {bot['id']}", key=f"stop_bot_{bot['id']}"):
                    if ferma_bot(bot['id']):
                        st.success("Bot fermato con successo!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Errore durante l'arresto del bot")
        
        # Statistiche generali
        st.subheader("📊 Statistiche Generali")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Grafico a torta per distribuzione posizioni per exchange
            if any(bot.get("positions", []) for bot in bot_attivi):
                all_positions = []
                for bot in bot_attivi:
                    all_positions.extend(bot.get("positions", []))
                
                exchange_counts = {}
                for pos in all_positions:
                    exchange = pos.get("exchange", "Sconosciuto")
                    if exchange in exchange_counts:
                        exchange_counts[exchange] += 1
                    else:
                        exchange_counts[exchange] = 1
                
                if exchange_counts:
                    fig = px.pie(
                        names=list(exchange_counts.keys()),
                        values=list(exchange_counts.values()),
                        title="Distribuzione Posizioni per Exchange"
                    )
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Nessuna posizione attiva per mostrare statistiche")
        
        with col2:
            # Grafico a barre per P&L per posizione
            if any(bot.get("positions", []) for bot in bot_attivi):
                all_positions = []
                for bot in bot_attivi:
                    all_positions.extend(bot.get("positions", []))
                
                position_pnls = []
                for pos in all_positions:
                    position_pnls.append({
                        "Simbolo": pos.get("symbol", "Sconosciuto"),
                        "Exchange": pos.get("exchange", "Sconosciuto"),
                        "P&L": float(pos.get("unrealizedPnl", 0))
                    })
                
                if position_pnls:
                    pnl_df = pd.DataFrame(position_pnls)
                    fig = px.bar(
                        pnl_df,
                        x="Simbolo",
                        y="P&L",
                        color="Exchange",
                        title="P&L per Posizione"
                    )
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Nessuna posizione attiva per mostrare P&L")
    
    with tab2:
        # Dettagli posizioni
        st.subheader("Posizioni Aperte")
        
        all_positions = []
        for bot in bot_attivi:
            positions = bot.get("positions", [])
            for pos in positions:
                all_positions.append({
                    "Exchange": pos.get("exchange", ""),
                    "Simbolo": pos.get("symbol", ""),
                    "Lato": pos.get("side", "").upper(),
                    "Dimensione": pos.get("size", 0),
                    "Prezzo Entrata": pos.get("entryPrice", 0),
                    "Prezzo Attuale": pos.get("markPrice", 0),
                    "Prezzo Liquidazione": pos.get("liquidationPrice", 0),
                    "P&L": float(pos.get("unrealizedPnl", 0)),
                    "Leva": pos.get("leverage", 1),
                    "Margine": pos.get("positionMargin", 0) or pos.get("collateral", 0) or pos.get("margin", 0)
                })
        
        if all_positions:
            positions_df = pd.DataFrame(all_positions)
            st.dataframe(positions_df, use_container_width=True)
            
            # Visualizzazione del rischio
            st.subheader("📉 Analisi Rischio")
            
            risk_data = []
            for pos in all_positions:
                current_price = float(pos["Prezzo Attuale"])
                liquidation_price = float(pos["Prezzo Liquidazione"])
                
                if current_price > 0 and liquidation_price > 0:
                    if pos["Lato"] == "LONG":
                        distance_pct = ((current_price - liquidation_price) / current_price) * 100
                    else:  # SHORT
                        distance_pct = ((liquidation_price - current_price) / current_price) * 100
                    
                    risk_level = max(0, 100 - distance_pct)
                    
                    risk_data.append({
                        "Posizione": f"{pos['Exchange']} {pos['Simbolo']} {pos['Lato']}",
                        "Rischio (%)": risk_level,
                        "Distanza Liquidazione (%)": distance_pct
                    })
            
            if risk_data:
                risk_df = pd.DataFrame(risk_data)
                
                # Grafico a barre orizzontale per livello di rischio
                fig = px.bar(
                    risk_df,
                    y="Posizione",
                    x="Rischio (%)",
                    color="Rischio (%)",
                    color_continuous_scale="RdYlGn_r",
                    title="Livello di Rischio per Posizione",
                    orientation="h"
                )
                
                # Aggiungi linee di soglia
                fig.add_vline(x=80, line_width=2, line_dash="dash", line_color="red")
                fig.add_vline(x=50, line_width=2, line_dash="dash", line_color="orange")
                
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nessuna posizione aperta al momento")
    
    with tab3:
        # Controlli manuali
        st.subheader("⚙️ Controlli Manuali")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Gestione Bot**")
            
            if st.button("⏹️ Ferma Bot", use_container_width=True):
                if ferma_bot("1"):  # Assumiamo che ci sia solo un bot con ID "1"
                    st.success("Bot fermato con successo!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Errore durante l'arresto del bot")
            
            if st.button("🚀 Avvia Nuovo Bot", use_container_width=True):
                st.switch_page("app.py")
        
        with col2:
            st.write("**Azioni Disponibili**")
            
            if st.button("🔄 Bilancia Margine Manualmente", use_container_width=True):
                if 'trading_system' in st.session_state and st.session_state.trading_system:
                    with st.spinner("Bilanciamento margine in corso..."):
                        # Esegui il bilanciamento manualmente
                        result = st.session_state.trading_system._esegui_bilanciamento()
                        st.success("Bilanciamento completato!")
                else:
                    st.error("Nessun bot attivo per eseguire il bilanciamento")

def main():
    """Funzione principale per la dashboard"""
    dashboard()

if __name__ == "__main__":
    main() 