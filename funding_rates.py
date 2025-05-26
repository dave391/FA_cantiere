"""
Funding Rates Module - Visualizzazione e analisi dei funding rate storici
"""

import streamlit as st
import ccxt
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import time as py_time
from datetime import time
import requests
import urllib.parse

def funding_rates_app():
    """Applicazione per visualizzare i funding rate storici"""
    
    st.title("📊 Funding Rate Storici - Futures Perpetual")

    # Selezione multipla degli exchange
    exchanges = st.multiselect(
        "Seleziona gli exchange",
        ["Bitfinex", "Bybit", "BitMEX"],
        default=["Bitfinex"]
    )

    @st.cache_resource
    def get_exchange(exchange_name):
        # Inizializzo l'exchange selezionato
        if exchange_name == "Bitfinex":
            exchange = ccxt.bitfinex()
        elif exchange_name == "Bybit":
            exchange = ccxt.bybit()
        else:  # BitMEX
            exchange = ccxt.bitmex()
        exchange.load_markets()
        return exchange

    # Funzione per normalizzare i simboli
    def normalize_symbol(symbol, exchange_name):
        try:
            if exchange_name == "Bitfinex":
                # Estraggo la base e la quote dal formato Bitfinex
                parts = symbol.split(':')
                if len(parts) == 2:
                    base = parts[0].replace('t', '').replace('F0', '')
                    quote = parts[1].replace('F0', '')
                    if quote == 'UST':
                        quote = 'USDT'
                    return f"{base}/{quote}"
            elif exchange_name == "Bybit":
                # Converto il formato Bybit in formato standard
                if 'USDT' in symbol:
                    base = symbol.replace('USDT', '')
                    return f"{base}/USDT"
                elif 'USD' in symbol:
                    base = symbol.replace('USD', '')
                    return f"{base}/USD"
                elif 'BTC' in symbol:
                    base = symbol.replace('BTC', '')
                    return f"{base}/BTC"
            else:  # BitMEX
                # Converto il formato BitMEX in formato standard
                if 'USD' in symbol:
                    base = symbol.replace('USD', '')
                    return f"{base}/USD"
                elif 'USDT' in symbol:
                    base = symbol.replace('USDT', '')
                    return f"{base}/USDT"
            return symbol
        except Exception as e:
            st.error(f"Errore nella normalizzazione del simbolo {symbol}: {str(e)}")
            return symbol

    # Funzione per ottenere il simbolo nel formato dell'exchange
    def get_exchange_symbol(symbol, exchange_name):
        if exchange_name == "Bitfinex":
            base, quote = symbol.split('/')
            if quote == 'USDT':
                quote = 'UST'
            return f"t{base}F0:{quote}F0"
        elif exchange_name == "Bybit":
            return symbol  # Usa il simbolo normalizzato per CCXT
        elif exchange_name == "BitMEX":
            return symbol  # Usa il simbolo normalizzato per CCXT (es. AVAX/USDT:USDT)

    # Costruisco la mappa simbolo -> exchange(s)
    all_symbols = {}

    for exchange_name in exchanges:
        exchange = get_exchange(exchange_name)
        for market in exchange.markets.values():
            # Considero solo perpetual swap
            if exchange_name == "Bitfinex":
                if not (market.get('type') == 'swap' or (market.get('future') and not market.get('expiry'))):
                    continue
            elif exchange_name == "Bybit":
                if not (market.get('type') == 'swap' and market.get('linear')):
                    continue
            else:  # BitMEX
                if not (market.get('type') == 'swap' or market.get('future')):
                    continue
            symbol = market['symbol']  # simbolo normalizzato CCXT, es. ETH/USDT
            if symbol not in all_symbols:
                all_symbols[symbol] = []
            all_symbols[symbol].append(exchange_name)

    # Lista ordinata dei simboli
    normalized_symbols = sorted(all_symbols.keys())

    # Selezione dello strumento con visualizzazione degli exchange disponibili
    selected_symbol = st.selectbox(
        "Seleziona lo strumento (coppia di scambio)",
        options=normalized_symbols,
        format_func=lambda x: f"{x} ({', '.join(all_symbols[x])})"
    )

    # Selezione del periodo temporale
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Data di inizio", value=date.today() - timedelta(days=7))
    with col2:
        end_date = st.date_input("Data di fine", value=date.today())

    # Validazione date
    if start_date > end_date:
        st.error("La data di inizio deve essere precedente alla data di fine.")

    # Inizializzo all_funding_data come variabile di sessione
    if 'all_funding_data' not in st.session_state:
        st.session_state.all_funding_data = {}

    # Bottone per avviare la chiamata
    if st.button("Recupera Funding Rates"):
        # Converto le date in timestamp Unix (millisecondi)
        start_ts = int(datetime.combine(start_date, time.min).timestamp() * 1000)
        end_ts = int(datetime.combine(end_date, time.max).timestamp() * 1000)
        
        st.session_state.all_funding_data = {}
        
        for exchange_name in exchanges:
            if selected_symbol in all_symbols and exchange_name in all_symbols[selected_symbol]:
                # Recupero il simbolo corretto per la chiamata API
                if exchange_name == "Bitfinex":
                    # Recupero il market Bitfinex per il simbolo normalizzato
                    market = None
                    bitfinex_exchange = get_exchange("Bitfinex")
                    for m in bitfinex_exchange.markets.values():
                        if m['symbol'] == selected_symbol:
                            market = m
                            break
                    if market and 'id' in market:
                        exchange_symbol = market['id']  # es: tETHF0:USTF0
                    else:
                        st.warning(f"La coppia {selected_symbol} non è disponibile su Bitfinex.")
                        continue
                elif exchange_name == "Bybit":
                    exchange_symbol = selected_symbol  # simbolo normalizzato per CCXT
                else:  # BitMEX
                    exchange_symbol = selected_symbol  # simbolo normalizzato per CCXT

                with st.spinner(f"Recupero dati da {exchange_name}..."):
                    try:
                        if exchange_name == "Bitfinex":
                            # Codifico il simbolo per l'URL
                            encoded_symbol = urllib.parse.quote(exchange_symbol)
                            base_url = f"https://api-pub.bitfinex.com/v2/status/deriv/{encoded_symbol}/hist"
                            
                            all_data = []
                            days_diff = (end_date - start_date).days + 1
                            
                            if days_diff > 3:
                                current_start = start_date
                                progress_bar = st.progress(0)
                                
                                while current_start <= end_date:
                                    current_end = min(current_start + timedelta(days=2), end_date)
                                    current_start_ts = int(datetime.combine(current_start, time.min).timestamp() * 1000)
                                    current_end_ts = int(datetime.combine(current_end, time.max).timestamp() * 1000)
                                    
                                    params = {
                                        'start': current_start_ts,
                                        'end': current_end_ts,
                                        'limit': 5000,
                                        'sort': -1
                                    }
                                    
                                    py_time.sleep(0.5)
                                    
                                    response = requests.get(base_url, params=params, headers={"accept": "application/json"})
                                    
                                    if response.status_code != 200:
                                        st.error(f"Errore nella chiamata API per il periodo {current_start} - {current_end}: {response.status_code}")
                                        st.error(f"URL utilizzato: {response.url}")
                                        current_start = current_end + timedelta(days=1)
                                        continue
                                    
                                    chunk_data = response.json()
                                    if chunk_data:
                                        all_data.extend(chunk_data)
                                    
                                    progress = min(1.0, (current_start - start_date).days / days_diff)
                                    progress_bar.progress(progress)
                                    
                                    current_start = current_end + timedelta(days=1)
                                
                                progress_bar.progress(1.0)
                            else:
                                params = {
                                    'start': start_ts,
                                    'end': end_ts,
                                    'limit': 5000,
                                    'sort': -1
                                }
                                
                                response = requests.get(base_url, params=params, headers={"accept": "application/json"})
                                
                                if response.status_code != 200:
                                    st.error(f"Errore nella chiamata API: {response.status_code}")
                                    st.error(f"URL utilizzato: {response.url}")
                                    st.error("Prova a ridurre l'intervallo di date o a selezionare un altro simbolo.")
                                    continue
                                
                                all_data = response.json()
                            
                            data = all_data
                            
                            if not data:
                                st.warning(f"Nessun dato trovato per {exchange_name}.")
                                continue
                            
                            current_rate = None
                            funding_data = []
                            current_block = []
                            previous_rate = None
                            
                            for entry in data:
                                timestamp = entry[0]
                                if start_ts <= timestamp <= end_ts:
                                    rate = entry[11]
                                    
                                    if rate != current_rate:
                                        if current_block:
                                            dt = datetime.fromtimestamp(current_block[-1][0] / 1000)
                                            rate_change = 0 if rate == previous_rate else rate
                                            
                                            funding_data.append({
                                                'timestamp': current_block[-1][0],
                                                'datetime': dt,
                                                'fundingRate': rate,
                                                'fundingRateChange': rate_change,
                                                'count': len(current_block)
                                            })
                                            
                                            previous_rate = rate
                                        
                                        current_rate = rate
                                        current_block = [entry]
                                    else:
                                        current_block.append(entry)
                            
                            if current_block:
                                dt = datetime.fromtimestamp(current_block[-1][0] / 1000)
                                rate_change = 0 if current_rate == previous_rate else current_rate
                                
                                funding_data.append({
                                    'timestamp': current_block[-1][0],
                                    'datetime': dt,
                                    'fundingRate': current_rate,
                                    'fundingRateChange': rate_change,
                                    'count': len(current_block)
                                })
                        
                        elif exchange_name == "Bybit":
                            exchange = get_exchange(exchange_name)
                            funding_data = []
                            current_start = start_date
                            
                            while current_start <= end_date:
                                current_end = min(current_start + timedelta(days=1), end_date)
                                current_start_ts = int(datetime.combine(current_start, time.min).timestamp() * 1000)
                                current_end_ts = int(datetime.combine(current_end, time.max).timestamp() * 1000)
                                
                                try:
                                    funding_history = exchange.fetch_funding_rate_history(
                                        exchange_symbol,
                                        since=current_start_ts,
                                        limit=1000
                                    )
                                    
                                    for entry in funding_history:
                                        if current_start_ts <= entry['timestamp'] <= current_end_ts:
                                            funding_data.append({
                                                'timestamp': entry['timestamp'],
                                                'datetime': datetime.fromtimestamp(entry['timestamp'] / 1000),
                                                'fundingRate': entry['fundingRate'],
                                                'fundingRateChange': entry['fundingRate'],
                                                'count': 1
                                            })
                                    
                                    py_time.sleep(0.5)
                                    current_start = current_end + timedelta(days=1)
                                    
                                except Exception as e:
                                    st.error(f"Errore nel recupero dati per il periodo {current_start} - {current_end}: {str(e)}")
                                    current_start = current_end + timedelta(days=1)
                                    continue
                        
                        else:  # BitMEX
                            exchange = get_exchange(exchange_name)
                            # Forzo il simbolo a XBTUSD per debug
                            adjusted_symbol = "XBTUSD"
                            current_start = start_date
                            funding_data = []  # Inizializzo funding_data qui
                            while current_start <= end_date:
                                current_end = min(current_start + timedelta(days=1), end_date)
                                current_start_ts = int(datetime.combine(current_start, time.min).timestamp() * 1000)
                                current_end_ts = int(datetime.combine(current_end, time.max).timestamp() * 1000)
                                try:
                                    all_entries = []
                                    start_idx = 0
                                    page_size = 100  # BitMEX ha un limite di 100 risultati per pagina
                                    while True:
                                        funding_history = exchange.fetch_funding_rate_history(
                                            adjusted_symbol,
                                            since=None,  # Non usiamo since per BitMEX
                                            limit=page_size,
                                            params={
                                                "startTime": datetime.fromtimestamp(current_start_ts/1000).isoformat() + 'Z',
                                                "endTime": datetime.fromtimestamp(current_end_ts/1000).isoformat() + 'Z',
                                                "reverse": False,
                                                "start": start_idx,
                                                "count": page_size
                                            }
                                        )
                                        if not funding_history:
                                            break
                                        all_entries.extend(funding_history)
                                        if len(funding_history) < page_size:
                                            break
                                        start_idx += page_size
                                        py_time.sleep(0.2)
                                    for entry in all_entries:
                                        if current_start_ts <= entry['timestamp'] <= current_end_ts:
                                            funding_data.append({
                                                'timestamp': entry['timestamp'],
                                                'datetime': datetime.fromtimestamp(entry['timestamp'] / 1000),
                                                'fundingRate': entry['fundingRate'],
                                                'fundingRateChange': entry['fundingRate'],
                                                'count': 1
                                            })
                                    py_time.sleep(0.5)
                                    current_start = current_end + timedelta(days=1)
                                except Exception as e:
                                    st.error(f"Errore nel recupero dati per il periodo {current_start} - {current_end}: {str(e)}")
                                    current_start = current_end + timedelta(days=1)
                                    continue
                        
                        if funding_data:
                            st.session_state.all_funding_data[exchange_name] = funding_data
                            pass  # Non mostrare più la card di successo
                        
                    except Exception as e:
                        st.error(f"Errore nel recupero dati da {exchange_name}: {str(e)}")
                        continue
        
        if not st.session_state.all_funding_data:
            st.warning("Nessun dato trovato per il periodo selezionato.")
            st.stop()
        
        # Visualizzazione dei dati per ogni exchange
        for exchange_name, funding_data in st.session_state.all_funding_data.items():
            st.subheader(f"Dati da {exchange_name}")
            
            # Costruisco DataFrame
            df = pd.DataFrame(funding_data)
            df['fundingRate_pct'] = df['fundingRate'] * 100
            df['fundingRateChange_pct'] = df['fundingRateChange'] * 100
            df['data'] = df['datetime'].dt.date
            df['ora'] = df['datetime'].dt.strftime('%H:%M:%S')
            
            # Ordino il DataFrame per data e ora
            df = df.sort_values(by='timestamp', ascending=True)

            # Statistiche chiave
            stats = {
                'Numero di record': len(df),
                'Funding Rate medio': df['fundingRate'].mean() * 100,
                'Funding Rate minimo': df['fundingRate'].min() * 100,
                'Funding Rate massimo': df['fundingRate'].max() * 100,
                'Ultimo Funding Rate': df.iloc[-1]['fundingRate'] * 100,
            }
            
            st.subheader("Statistiche chiave")
            c1, c2, c3 = st.columns(3)
            c1.metric("Record", stats['Numero di record'])
            c2.metric("Funding Rate medio", f"{stats['Funding Rate medio']:.4f}%")
            c3.metric("Ultimo Funding Rate", f"{stats['Ultimo Funding Rate']:.4f}%")

            # Tabella e grafico: logica diversa per BitMEX
            st.subheader("Dati del grafico Andamento Funding Rate")
            try:
                if exchange_name == 'BitMEX':
                    # Mostra direttamente i dati reali di BitMEX (funding ogni 8 ore)
                    display_df = df.copy()
                    display_df['datetime'] = display_df['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
                    st.dataframe(display_df.rename(
                        columns={
                            'datetime': 'Data e Ora',
                            'fundingRate_pct': 'Funding Rate (%)'
                        }
                    ))
                    st.subheader("Andamento Funding Rate")
                    fig = px.line(df, x='datetime', y='fundingRate_pct', 
                                title=f"Funding Rate - {selected_symbol} ({exchange_name})",
                                labels={'fundingRate_pct': 'Funding Rate (%)'})
                    st.plotly_chart(fig, use_container_width=True)

                    st.subheader("Somma giornaliera dei Funding Rate")
                    df['data_solo'] = df['datetime'].dt.date
                    daily_df = df.groupby('data_solo')['fundingRate_pct'].sum().reset_index()
                    daily_display_df = daily_df.copy()
                    daily_display_df['data_solo'] = daily_display_df['data_solo'].astype(str)
                    st.dataframe(daily_display_df.rename(
                        columns={
                            'data_solo': 'Data',
                            'fundingRate_pct': 'Funding Rate Giornaliero (%)'
                        }
                    ))
                    st.subheader("Grafico delle somme giornaliere")
                    fig_daily = px.bar(daily_df, x='data_solo', y='fundingRate_pct',
                                    title=f"Somma giornaliera dei Funding Rate - {selected_symbol} ({exchange_name})",
                                    labels={'fundingRate_pct': 'Funding Rate Giornaliero (%)', 'data_solo': 'Data'})
                    st.plotly_chart(fig_daily, use_container_width=True)
                else:
                    # --- LOGICA ATTUALE PER GLI ALTRI EXCHANGE ---
                    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
                    complete_datetimes = []
                    for single_date in date_range:
                        for hour in ['02', '10', '18']:
                            complete_datetimes.append(pd.Timestamp(
                                year=single_date.year,
                                month=single_date.month,
                                day=single_date.day,
                                hour=int(hour),
                                minute=0,
                                second=0
                            ))
                    complete_df = pd.DataFrame({
                        'datetime': complete_datetimes,
                        'fundingRate_pct': [0] * len(complete_datetimes)
                    })
                    df['ora_solo'] = df['datetime'].dt.strftime('%H')
                    filtered_df = df[df['ora_solo'].isin(['02', '10', '18'])].copy()
                    filtered_df['datetime_key'] = filtered_df['datetime'].dt.floor('H')
                    complete_df['datetime_key'] = complete_df['datetime'].dt.floor('H')
                    merged_df = pd.merge(
                        complete_df,
                        filtered_df[['datetime_key', 'fundingRate_pct']],
                        on='datetime_key',
                        how='left'
                    )
                    merged_df['fundingRate_final'] = merged_df['fundingRate_pct_y'].fillna(merged_df['fundingRate_pct_x'])
                    final_df = merged_df[['datetime', 'fundingRate_final']].rename(
                        columns={
                            'fundingRate_final': 'fundingRate_pct'
                        }
                    )
                    final_df = final_df.sort_values(by='datetime')
                    display_df = final_df.copy()
                    display_df['datetime'] = display_df['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
                    st.dataframe(display_df.rename(
                        columns={
                            'datetime': 'Data e Ora',
                            'fundingRate_pct': 'Funding Rate (%)'
                        }
                    ))
                    st.subheader("Andamento Funding Rate")
                    fig = px.line(final_df, x='datetime', y='fundingRate_pct', 
                                title=f"Funding Rate - {selected_symbol} ({exchange_name})",
                                labels={'fundingRate_pct': 'Funding Rate (%)'})
                    st.plotly_chart(fig, use_container_width=True)
                    st.subheader("Somma giornaliera dei Funding Rate")
                    final_df['data_solo'] = final_df['datetime'].dt.date
                    daily_df = final_df.groupby('data_solo')['fundingRate_pct'].sum().reset_index()
                    daily_display_df = daily_df.copy()
                    daily_display_df['data_solo'] = daily_display_df['data_solo'].astype(str)
                    st.dataframe(daily_display_df.rename(
                        columns={
                            'data_solo': 'Data',
                            'fundingRate_pct': 'Funding Rate Giornaliero (%)'
                        }
                    ))
                    st.subheader("Grafico delle somme giornaliere")
                    fig_daily = px.bar(daily_df, x='data_solo', y='fundingRate_pct',
                                    title=f"Somma giornaliera dei Funding Rate - {selected_symbol} ({exchange_name})",
                                    labels={'fundingRate_pct': 'Funding Rate Giornaliero (%)', 'data_solo': 'Data'})
                    st.plotly_chart(fig_daily, use_container_width=True)
            except Exception as e:
                st.error(f"Errore nella creazione della tabella per {exchange_name}: {str(e)}")
                st.write("Dettagli dell'errore per debug:", str(e))

    # --- Simulatore posizione funding ---
    st.subheader('Simula posizione')
    col_long, col_short = st.columns(2)
    with col_long:
        exchange_long = st.selectbox('Exchange LONG', normalized_symbols and all_symbols[selected_symbol], key='long')
    with col_short:
        exchange_short = st.selectbox('Exchange SHORT', normalized_symbols and all_symbols[selected_symbol], key='short')

    # Aggiungo campi per capitale e leva
    col_cap, col_lev = st.columns(2)
    with col_cap:
        capitale = st.number_input('Capitale (USDT)', min_value=0.0, value=1000.0, step=100.0)
    with col_lev:
        leva = st.selectbox('Leva', options=[1, 2, 3, 4, 5])

    def fetch_funding_for_simulation(exchange_name, selected_symbol, start_date, end_date):
        # Recupera funding rate per la simulazione, solo se non già presenti
        funding_data = []
        start_ts = int(datetime.combine(start_date, time.min).timestamp() * 1000)
        end_ts = int(datetime.combine(end_date, time.max).timestamp() * 1000)
        
        if exchange_name == "Bitfinex":
            # Recupero il market Bitfinex per il simbolo normalizzato
            market = None
            bitfinex_exchange = get_exchange("Bitfinex")
            for m in bitfinex_exchange.markets.values():
                if m['symbol'] == selected_symbol:
                    market = m
                    break
            if market and 'id' in market:
                exchange_symbol = market['id']  # es: tETHF0:USTF0
            else:
                return []
            encoded_symbol = urllib.parse.quote(exchange_symbol)
            base_url = f"https://api-pub.bitfinex.com/v2/status/deriv/{encoded_symbol}/hist"
            all_data = []
            days_diff = (end_date - start_date).days + 1
            if days_diff > 3:
                current_start = start_date
                while current_start <= end_date:
                    current_end = min(current_start + timedelta(days=2), end_date)
                    current_start_ts = int(datetime.combine(current_start, time.min).timestamp() * 1000)
                    current_end_ts = int(datetime.combine(current_end, time.max).timestamp() * 1000)
                    params = {
                        'start': current_start_ts,
                        'end': current_end_ts,
                        'limit': 5000,
                        'sort': -1
                    }
                    py_time.sleep(0.5)
                    response = requests.get(base_url, params=params, headers={"accept": "application/json"})
                    if response.status_code != 200:
                        current_start = current_end + timedelta(days=1)
                        continue
                    chunk_data = response.json()
                    if chunk_data:
                        all_data.extend(chunk_data)
                    current_start = current_end + timedelta(days=1)
            else:
                params = {
                    'start': start_ts,
                    'end': end_ts,
                    'limit': 5000,
                    'sort': -1
                }
                response = requests.get(base_url, params=params, headers={"accept": "application/json"})
                if response.status_code != 200:
                    return []
                all_data = response.json()
            data = all_data
            current_rate = None
            current_block = []
            previous_rate = None
            for entry in data:
                timestamp = entry[0]
                if start_ts <= timestamp <= end_ts:
                    rate = entry[11]
                    if rate != current_rate:
                        if current_block:
                            dt = datetime.fromtimestamp(current_block[-1][0] / 1000)
                            rate_change = 0 if rate == previous_rate else rate
                            funding_data.append({
                                'timestamp': current_block[-1][0],
                                'datetime': dt,
                                'fundingRate': rate,
                                'fundingRateChange': rate_change,
                                'count': len(current_block)
                            })
                            previous_rate = rate
                        current_rate = rate
                        current_block = [entry]
                    else:
                        current_block.append(entry)
            if current_block:
                dt = datetime.fromtimestamp(current_block[-1][0] / 1000)
                rate_change = 0 if current_rate == previous_rate else current_rate
                funding_data.append({
                    'timestamp': current_block[-1][0],
                    'datetime': dt,
                    'fundingRate': current_rate,
                    'fundingRateChange': rate_change,
                    'count': len(current_block)
                })
        elif exchange_name == "Bybit":
            exchange = get_exchange(exchange_name)
            exchange_symbol = get_exchange_symbol(selected_symbol, exchange_name)
            current_start = start_date
            
            while current_start <= end_date:
                current_end = min(current_start + timedelta(days=1), end_date)
                current_start_ts = int(datetime.combine(current_start, time.min).timestamp() * 1000)
                current_end_ts = int(datetime.combine(current_end, time.max).timestamp() * 1000)
                
                try:
                    funding_history = exchange.fetch_funding_rate_history(
                        exchange_symbol,
                        since=current_start_ts,
                        limit=1000
                    )
                    
                    for entry in funding_history:
                        if current_start_ts <= entry['timestamp'] <= current_end_ts:
                            funding_data.append({
                                'timestamp': entry['timestamp'],
                                'datetime': datetime.fromtimestamp(entry['timestamp'] / 1000),
                                'fundingRate': entry['fundingRate'],
                                'fundingRateChange': entry['fundingRate'],
                                'count': 1
                            })
                    
                    py_time.sleep(0.5)
                    current_start = current_end + timedelta(days=1)
                    
                except Exception as e:
                    st.error(f"Errore nel recupero dati per il periodo {current_start} - {current_end}: {str(e)}")
                    current_start = current_end + timedelta(days=1)
                    continue
        else:  # BitMEX
            exchange = get_exchange(exchange_name)
            # Controllo se la coppia esiste tra i mercati dell'exchange
            if selected_symbol not in exchange.markets:
                st.warning(f"La coppia {selected_symbol} non è disponibile su {exchange_name}.")
                return []
            exchange_symbol = get_exchange_symbol(selected_symbol, exchange_name)
            current_start = start_date
            while current_start <= end_date:
                current_end = min(current_start + timedelta(days=1), end_date)
                current_start_ts = int(datetime.combine(current_start, time.min).timestamp() * 1000)
                current_end_ts = int(datetime.combine(current_end, time.max).timestamp() * 1000)
                try:
                    # Per BitMEX, adattiamo il simbolo se necessario
                    if 'SOL' in selected_symbol.upper():
                        # Per BitMEX, 1 SOL = 10000 contratti
                        adjusted_symbol = "SOLUSDT"
                    else:
                        adjusted_symbol = exchange_symbol

                    all_entries = []
                    start_idx = 0
                    page_size = 100  # BitMEX ha un limite di 100 risultati per pagina
                    while True:
                        funding_history = exchange.fetch_funding_rate_history(
                            adjusted_symbol,
                            since=None,  # Non usiamo since per BitMEX
                            limit=page_size,
                            params={
                                "startTime": datetime.fromtimestamp(current_start_ts/1000).isoformat() + 'Z',
                                "endTime": datetime.fromtimestamp(current_end_ts/1000).isoformat() + 'Z',
                                "reverse": False,
                                "start": start_idx,
                                "count": page_size
                            }
                        )
                        if not funding_history:
                            break
                        all_entries.extend(funding_history)
                        if len(funding_history) < page_size:
                            break
                        start_idx += page_size
                        py_time.sleep(0.2)
                    for entry in all_entries:
                        if current_start_ts <= entry['timestamp'] <= current_end_ts:
                            funding_data.append({
                                'timestamp': entry['timestamp'],
                                'datetime': datetime.fromtimestamp(entry['timestamp'] / 1000),
                                'fundingRate': entry['fundingRate'],
                                'fundingRateChange': entry['fundingRate'],
                                'count': 1
                            })
                    py_time.sleep(0.5)
                    current_start = current_end + timedelta(days=1)
                except Exception as e:
                    st.error(f"Errore nel recupero dati per il periodo {current_start} - {current_end}: {str(e)}")
                    current_start = current_end + timedelta(days=1)
                    continue
        
        return funding_data

    if st.button('Simula posizione'):
        # Recupero funding se mancano
        for exch in [exchange_long, exchange_short]:
            if exch not in st.session_state.all_funding_data:
                funding = fetch_funding_for_simulation(exch, selected_symbol, start_date, end_date)
                if funding:
                    st.session_state.all_funding_data[exch] = funding
        # Procedo solo se almeno uno dei due ha dati
        if not st.session_state.all_funding_data or (exchange_long not in st.session_state.all_funding_data and exchange_short not in st.session_state.all_funding_data):
            st.warning("Impossibile recuperare i funding rate per almeno uno degli exchange selezionati.")
        else:
            daily_funding = {}
            for side, exch in [('long', exchange_long), ('short', exchange_short)]:
                funding_data = None
                if exch in st.session_state.all_funding_data:
                    df = pd.DataFrame(st.session_state.all_funding_data[exch])
                    df['fundingRate_pct'] = df['fundingRate'] * 100
                    df['datetime'] = pd.to_datetime(df['datetime'])
                    df['data'] = df['datetime'].dt.date
                    daily_df = df.groupby('data')['fundingRate_pct'].sum().reset_index()
                    daily_funding[side] = daily_df.set_index('data')['fundingRate_pct']
                else:
                    daily_funding[side] = pd.Series(dtype=float)
            all_dates = sorted(set(daily_funding['long'].index).union(set(daily_funding['short'].index)))
            result_rows = []
            for d in all_dates:
                f_long = daily_funding['long'].get(d, 0)
                f_short = daily_funding['short'].get(d, 0)
                totale = f_short - f_long
                result_rows.append({'Data': d, 'Funding Long': f_long, 'Funding Short': f_short, 'Totale giornaliero': totale})
            result_df = pd.DataFrame(result_rows)
            
            # Aggiungo la colonna Equity (somma cumulativa)
            result_df['Equity'] = result_df['Totale giornaliero'].cumsum()
            
            st.subheader('Tabella simulazione')
            st.dataframe(result_df)
            
            # Calcolo profitti, ROI e APR
            somma_totale = result_df['Totale giornaliero'].sum()
            profitti = capitale * leva * (somma_totale / 100)  # divido per 100 perché somma_totale è in percentuale
            roi = (profitti / capitale) * 100
            
            # Calcolo numero di giorni
            giorni = (end_date - start_date).days + 1
            apr = (roi / giorni) * 365
            
            # Mostro i risultati
            st.subheader('Risultati simulazione')
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Profitti", f"{profitti:.2f} $")
            col2.metric("ROI", f"{roi:.2f}%")
            col3.metric("APR", f"{apr:.2f}%")
            col4.metric("Giorni", f"{giorni}")
            
            st.success(f"Somma totale funding: {somma_totale:.4f} %")
            
            # Aggiungo il grafico dell'equity
            st.subheader('Andamento Equity')
            fig_equity = px.line(result_df, x='Data', y='Equity',
                            title='Andamento Equity (somma cumulativa dei totali giornalieri)',
                            labels={'Equity': 'Equity (%)', 'Data': 'Data'})
            st.plotly_chart(fig_equity, use_container_width=True) 