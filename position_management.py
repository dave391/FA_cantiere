"""
Position Management - Checkpoint Version 3.0 (Codice Pulito)
Data: 15/05/2025
"""

import streamlit as st
import os
import pandas as pd
from dotenv import load_dotenv
from ccxt_api import CCXTAPI
import time
import logging

# Configurazione del logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('position_management')

# Carica le variabili d'ambiente
load_dotenv()

# Lista degli exchange supportati
SUPPORTED_EXCHANGES = ["BitMEX", "Bitfinex", "ByBit"]

def normalize_exchange_id(exchange_name):
    """Converte il nome dell'exchange nel formato CCXT corrispondente"""
    if exchange_name == "BitMEX":
        return "bitmex"
    else:
        return exchange_name.lower()

def get_exchange_api(exchange_name):
    """Crea e restituisce un'istanza CCXTAPI per l'exchange specificato"""
    exchange_id = normalize_exchange_id(exchange_name)
    
    try:
        # Verifica che le API key siano configurate
        api_key = os.getenv(f"{exchange_name.upper()}_API_KEY")
        api_secret = os.getenv(f"{exchange_name.upper()}_API_SECRET")
        
        if not api_key or not api_secret:
            st.error(f"API Key e Secret per {exchange_name} non configurati")
            return None
        
        # Crea l'istanza API
        api = CCXTAPI(exchange_id)
        return api
    except Exception as e:
        st.error(f"Errore nella creazione dell'API per {exchange_name}: {str(e)}")
        return None

def normalize_amount(amount, exchange_name, symbol):
    """Converte l'amount da contratti a SOL per BitMEX"""
    if amount is None:
        return 0.0
        
    try:
        amount_value = float(amount)
        if exchange_name == "BitMEX" and 'SOL' in symbol.upper():
            # Per BitMEX, 10000 contratti = 1 SOL
            return amount_value / 10000
        return amount_value
    except (ValueError, TypeError):
        return 0.0

def format_order_data(orders, exchange_name):
    """Formatta i dati degli ordini in un formato uniforme per la visualizzazione"""
    if not orders or len(orders) == 0:
        return pd.DataFrame(columns=["Exchange", "Symbol", "Side", "Type", "Price", "Amount", "Status", "Date", "Order ID"])
    
    formatted_orders = []
    
    for order in orders:
        # Estrai le informazioni principali dell'ordine
        symbol = order.get('symbol', 'N/A')
        order_type = order.get('type', 'N/A')
        side = order.get('side', 'N/A')
        price = order.get('price', 0)
        raw_amount = order.get('amount', 0)
        status = order.get('status', 'N/A')
        order_id = order.get('id', 'N/A')
        
        # Normalizza l'amount (converti da contratti a SOL per BitMEX)
        normalized_amount = normalize_amount(raw_amount, exchange_name, symbol)
        
        # Formatta la data
        timestamp = order.get('timestamp', 0)
        if timestamp:
            from datetime import datetime
            date = datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
        else:
            date = 'N/A'
        
        # Aggiungi alle righe formattate
        formatted_orders.append({
            "Exchange": exchange_name,
            "Symbol": symbol,
            "Side": side.upper(),
            "Type": order_type.upper(),
            "Price": f"{price:.2f}" if price else 'Market',
            "Amount": f"{normalized_amount:.6f}",
            "Status": status.upper(),
            "Date": date,
            "Order ID": order_id
        })
    
    return pd.DataFrame(formatted_orders)

def format_position_data(positions, exchange_name):
    """Formatta i dati delle posizioni in un formato uniforme per la visualizzazione"""
    # Gestisci esplicitamente il caso in cui positions è None
    if positions is None:
        logger.warning(f"format_position_data: positions è None per {exchange_name}")
        return pd.DataFrame(columns=["Exchange", "Symbol", "Side", "Size", "Entry Price", "Liquidation Price", "Profit/Loss", "Leverage", "Margin"])
    
    # Gestisci il caso in cui positions è vuoto
    if len(positions) == 0:
        logger.info(f"format_position_data: nessuna posizione aperta per {exchange_name}")
        return pd.DataFrame(columns=["Exchange", "Symbol", "Side", "Size", "Entry Price", "Liquidation Price", "Profit/Loss", "Leverage", "Margin"])
    
    formatted_positions = []
    
    for position in positions:
        try:
            # Estrai le informazioni principali della posizione
            symbol = position.get('symbol', 'N/A')
            side = "LONG" if position.get('side', '') == 'long' else "SHORT"
            
            # Per Bitfinex, usa SEMPRE il valore esatto delle posizioni
            if exchange_name == "Bitfinex":
                # APPROCCIO DIRETTO: usa esattamente il valore ricevuto dall'API
                # Prima controlla se abbiamo il valore notional (questo è il valore corretto per Bitfinex)
                notional_value = position.get('notional')
                raw_size = position.get('raw_size')
                contracts_value = position.get('contracts')
                
                # Usa notional come valore principale, se disponibile
                if notional_value is not None and notional_value != 0:
                    # Usa il valore assoluto di notional come dimensione effettiva
                    position_size = abs(notional_value)
                    # Aggiorna anche raw_size e contracts per coerenza
                    position['raw_size'] = notional_value
                    position['contracts'] = str(position_size)
                elif raw_size is not None and raw_size != 0:
                    # Fallback su raw_size se notional non è disponibile
                    position_size = abs(raw_size)
                elif contracts_value:
                    # Ultimo fallback su contracts
                    try:
                        position_size = float(contracts_value)
                    except (ValueError, TypeError):
                        position_size = 0
                else:
                    position_size = 0
                
                # Formatta il valore per la visualizzazione
                contract_display = f"{position_size:.8f}".rstrip('0').rstrip('.')
                
                # Memorizza i valori esatti per uso futuro
                if "raw_positions_data" not in st.session_state:
                    st.session_state.raw_positions_data = []
                
                # Crea un oggetto posizione completo da memorizzare in session_state
                position_data = {
                    "exchange": exchange_name,
                    "symbol": symbol,
                    "side": side,
                    "raw_size": notional_value if notional_value is not None else raw_size,
                    "contracts": contract_display,
                    "notional": notional_value,
                    "entry_price": position.get('entryPrice', 0),
                    "mark_price": position.get('markPrice', 0),
                    "unrealized_pnl": position.get('unrealizedPnl', 0),
                    "liquidation_price": position.get('liquidationPrice', 0),
                    "margin_mode": position.get('marginMode', 'N/A'),
                    "position_margin": position.get('collateral') or position.get('margin') or position.get('initial_margin', 0)
                }
                
                # Aggiungi all'elenco o aggiorna se esiste già
                updated = False
                if hasattr(st.session_state, 'raw_positions_data'):
                    for i, pos in enumerate(st.session_state.raw_positions_data):
                        if pos.get('exchange') == exchange and pos.get('symbol') == symbol:
                            st.session_state.raw_positions_data[i] = position_data
                            updated = True
                            break
                    
                    if not updated:
                        st.session_state.raw_positions_data.append(position_data)
                else:
                    st.session_state.raw_positions_data = [position_data]
                
                # Ottieni il margine della posizione
                position_margin = position.get('collateral') or position.get('margin') or position.get('initial_margin', 0)
                if position_margin is None:
                    margin_formatted = 'N/A'
                else:
                    try:
                        margin_formatted = f"{float(position_margin):.2f}"
                    except (ValueError, TypeError):
                        margin_formatted = 'N/A'
                
                # Aggiungi alla lista delle posizioni formattate
                formatted_positions.append({
                    "Exchange": exchange_name,
                    "Symbol": symbol,
                    "Side": side,
                    "Size": contract_display,
                    "Entry Price": f"{float(position.get('entryPrice', 0)):.2f}" if position.get('entryPrice') else 'N/A',
                    "Liquidation Price": f"{float(position.get('liquidationPrice', 0)):.2f}" if position.get('liquidationPrice') else 'N/A',
                    "Profit/Loss": f"{float(position.get('unrealizedPnl', 0)):.6f}" if position.get('unrealizedPnl') else 'N/A',
                    "Leverage": f"{float(position.get('leverage', 1)):.0f}x" if position.get('leverage') else '1x',
                    "Margin": margin_formatted
                })
                
                continue  # Continua con la prossima posizione
            else:
                # Per altri exchange, usa la logica esistente
                contracts = position.get('contracts', 0)
                contract_size = position.get('contractSize', 0)
                
                # Gestisci diversi formati per la size
                size = contracts if contracts else contract_size
                
                # Gestisci il caso in cui size sia None
                if size is None:
                    size = 0
                
                # Normalizza la size per BitMEX (converti da contratti a SOL)
                if exchange_name == "BitMEX" and 'SOL' in str(symbol).upper() and size:
                    try:
                        size = float(size) / 10000
                    except (ValueError, TypeError):
                        # Se non è possibile convertire, lascia il valore originale
                        pass
                
                # Converti al tipo float se possibile
                try:
                    size_value = float(size) if size is not None else 0
                    size_formatted = f"{abs(size_value):.6f}" if isinstance(size_value, (int, float)) else "0.000000"
                except (ValueError, TypeError):
                    size_value = 0
                    size_formatted = "0.000000"
            
            # Altri dettagli (gestione safe dei valori nulli)
            entry_price = position.get('entryPrice', 0)
            liquidation_price = position.get('liquidationPrice', 0)
            unrealized_pnl = position.get('unrealizedPnl', 0)
            leverage = position.get('leverage', 1)
            
            # Entry price
            try:
                entry_price_value = float(entry_price) if entry_price is not None else 0
            except (ValueError, TypeError):
                entry_price_value = 0
                
            # Liquidation price
            try:
                liquidation_price_value = float(liquidation_price) if liquidation_price is not None else 0
            except (ValueError, TypeError):
                liquidation_price_value = 0
            
            # Unrealized PnL
            if unrealized_pnl is None:
                pnl_formatted = "0.000000"
            elif isinstance(unrealized_pnl, (int, float)):
                pnl_formatted = f"{unrealized_pnl:.6f}"
            else:
                try:
                    pnl_formatted = f"{float(unrealized_pnl):.6f}"
                except (ValueError, TypeError):
                    pnl_formatted = str(unrealized_pnl)
            
            # Leverage
            if leverage is None:
                leverage_formatted = "1x"
            elif isinstance(leverage, (int, float)):
                leverage_formatted = f"{leverage}x"
            else:
                try:
                    leverage_formatted = f"{float(leverage)}x"
                except (ValueError, TypeError):
                    leverage_formatted = str(leverage)
            
            # Estrai il margine della posizione
            # Per BitMEX, usa posMargin
            position_margin = None
            if exchange_name == "BitMEX":
                position_margin = position.get('posMargin')
                # Se posMargin non è disponibile, prova con posInit
                if position_margin is None:
                    position_margin = position.get('posInit')
                
                # Se i campi nell'oggetto 'info' sono disponibili, usali
                if position_margin is None and 'info' in position:
                    info = position.get('info', {})
                    position_margin = info.get('posMargin') or info.get('posInit')
            else:
                # Per altri exchange, prova a trovare un campo di margine equivalente
                position_margin = position.get('margin') or position.get('initialMargin') or position.get('maintenanceMargin')
            
            # Formatta il valore del margine
            if position_margin is None:
                margin_formatted = "N/A"
            else:
                try:
                    margin_formatted = f"{float(position_margin):.2f}"
                except (ValueError, TypeError):
                    margin_formatted = str(position_margin)
            
            # Aggiungi alle righe formattate
            position_row = {
                "Exchange": exchange_name,
                "Symbol": symbol,
                "Side": side,
                "Size": size_formatted,
                "Entry Price": f"{entry_price_value:.2f}" if isinstance(entry_price_value, (int, float)) and entry_price_value else 'N/A',
                "Liquidation Price": f"{liquidation_price_value:.2f}" if isinstance(liquidation_price_value, (int, float)) and liquidation_price_value else 'N/A',
                "Profit/Loss": pnl_formatted,
                "Leverage": leverage_formatted,
                "Margin": margin_formatted
            }
            
            formatted_positions.append(position_row)
        except Exception as e:
            # Registra errori
            st.error(f"Errore nell'elaborazione di una posizione: {str(e)}")
            continue
    
    result_df = pd.DataFrame(formatted_positions)
    
    return result_df

def cancel_order(exchange_name, order_id, symbol):
    """Cancella un ordine specifico"""
    try:
        api = get_exchange_api(exchange_name)
        if not api:
            return {"error": f"Impossibile creare l'API per {exchange_name}"}
        
        result = api.cancel_order(order_id, symbol)
        return {"success": True, "result": result}
    except Exception as e:
        return {"error": f"Errore nella cancellazione dell'ordine: {str(e)}"}

def close_position(exchange_name, symbol, size=None, side=None):
    """Chiude una posizione specifica a mercato"""
    try:
        api = get_exchange_api(exchange_name)
        if not api:
            return {"error": f"Impossibile creare l'API per {exchange_name}"}
        
        # Supportiamo BitMEX, Bitfinex e ByBit
        if exchange_name not in ["BitMEX", "Bitfinex", "ByBit"]:
            return {"error": f"Chiusura posizioni attualmente supportata solo per BitMEX, Bitfinex e ByBit"}
        
        # Preparare i parametri per la chiusura
        params = {}
        
        # È fondamentale specificare il lato corretto dell'ordine di chiusura (opposto alla posizione)
        if side:
            # Se abbiamo il side della posizione, lo invertiamo in modo specifico
            # Se la posizione è LONG dobbiamo fare SELL, se è SHORT dobbiamo fare BUY
            if side == "LONG":
                order_side = "sell"
            elif side == "SHORT":
                order_side = "buy"
            else:
                # Se il side non è riconosciuto, potrebbe essere già l'ordine (non la posizione)
                order_side = side.lower()
        
        # Impostiamo SEMPRE reduceOnly per sicurezza, con il parametro corretto per ogni exchange
        if exchange_name == "BitMEX":
            params["reduceOnly"] = True
        elif exchange_name == "Bitfinex":
            params["reduce_only"] = True
        elif exchange_name == "ByBit":
            params["reduceOnly"] = True
            params["closeOnTrigger"] = True  # Parametro specifico per ByBit per garantire la chiusura
        
        # Adattamento del simbolo per ByBit
        if exchange_name == "ByBit":
            # Gestione speciale per il formato SOL/USDT:USDT
            if symbol == "SOL/USDT:USDT":
                # Usa diversi formati del simbolo da provare
                symbols_to_try = [
                    symbol,           # Originale SOL/USDT:USDT
                    "SOL/USDT",       # Formato standard
                    "SOLUSDT",        # Formato senza barra
                    "SOLUSDTPerp"     # Formato con Perp
                ]
                
                # Prova ciascun formato fino a successo
                last_error = None
                for sym in symbols_to_try:
                    try:
                        logger.info(f"Tentativo di chiusura {sym} su ByBit con size={size}")
                        result = api.close_position(sym, position_size=size, params=params)
                        if "success" in result and result["success"]:
                            return result
                        else:
                            last_error = result.get("error", "Errore sconosciuto")
                    except Exception as e:
                        last_error = str(e)
                        continue
                
                # Se tutte le opzioni falliscono, restituisci l'ultimo errore
                if last_error:
                    return {"error": f"Tutti i tentativi di chiusura hanno fallito: {last_error}"}
            
            # Per altri simboli ByBit, gestisci vari formati
            elif "SOL" in symbol.upper():
                # Per SOL tentativi con formati alternativi
                original_symbol = symbol
                symbols_to_try = [
                    symbol,                  # Formato originale
                    symbol.replace("/", ""), # Senza barra
                    symbol + "Perp",         # Con suffisso Perp
                ]
                
                last_error = None
                for sym in symbols_to_try:
                    try:
                        logger.info(f"Tentativo di chiusura {sym} su ByBit con size={size}")
                        result = api.close_position(sym, position_size=size, params=params)
                        if "success" in result and result["success"]:
                            return result
                        else:
                            last_error = result.get("error", "Errore sconosciuto")
                    except Exception as e:
                        last_error = str(e)
                        continue
                
                # Se tutte le opzioni falliscono, restituisci l'ultimo errore
                if last_error:
                    return {"error": f"Tutti i tentativi di chiusura hanno fallito: {last_error}"}
        
        # Per Bitfinex, potrebbe essere necessario adattare il simbolo
        if exchange_name == "Bitfinex" and not symbol.startswith('t') and 'F0:' not in symbol:
            if 'SOL' in symbol.upper():
                original_symbol = symbol
                symbol = "tSOLF0:USTF0"
                
                # Se è stato specificato un size ma è troppo piccolo per SOL, correggiamolo
                if size is not None and abs(float(size)) < 0.1:
                    original_size = size
                    # Manteniamo il segno originale ma impostiamo il valore minimo a 0.1
                    size = 0.1 if float(size) > 0 else -0.1
        
        # Chiamare l'API per chiudere la posizione
        result = api.close_position(symbol, position_size=size, params=params)
        
        # Verificare il risultato
        if "success" in result and result["success"]:
            method = result.get("method", "N/A")
            return {"success": True, "message": f"Posizione chiusa con successo (metodo: {method})"}
        else:
            # Include tutti i dettagli dell'errore nella risposta
            error_response = {"error": result.get("error", "Errore sconosciuto nella chiusura della posizione")}
            if "details" in result:
                error_response["details"] = result["details"]
            return error_response
    except Exception as e:
        import traceback
        stack_trace = traceback.format_exc()
        return {"error": f"Errore nella chiusura della posizione: {str(e)}", "details": stack_trace}

def close_all_positions(exchange_name):
    """Chiude tutte le posizioni aperte su un exchange"""
    try:
        api = get_exchange_api(exchange_name)
        if not api:
            return {"error": f"Impossibile creare l'API per {exchange_name}"}
        
        # Supportiamo BitMEX, Bitfinex e ByBit
        if exchange_name not in ["BitMEX", "Bitfinex", "ByBit"]:
            return {"error": f"Chiusura posizioni attualmente supportata solo per BitMEX, Bitfinex e ByBit"}
        
        # Recupera le posizioni aperte
        positions_result = api.get_open_positions()
        if "error" in positions_result:
            return {"error": f"Errore nel recuperare le posizioni: {positions_result['error']}"}
        
        if "success" in positions_result and positions_result["success"]:
            positions = positions_result.get("positions", [])
            
            if not positions:
                return {"success": True, "message": "Nessuna posizione aperta da chiudere"}
            
            logger.info(f"Trovate {len(positions)} posizioni da chiudere su {exchange_name}")
            for pos in positions:
                symbol = pos.get('symbol', 'Unknown')
                side = pos.get('side', 'Unknown')
                contracts = pos.get('contracts', 0)
                logger.info(f"Posizione: {symbol}, {side}, {contracts} contratti")
            
            # Caso speciale per BitMEX
            if exchange_name == "BitMEX":
                logger.info("Utilizzo metodo speciale per BitMEX")
                
                # Chiudi ogni posizione individualmente ma con verifica aggiuntiva
                results = []
                success_count = 0
                error_count = 0
                
                for position in positions:
                    symbol = position.get('symbol', '')
                    logger.info(f"Tentativo di chiusura posizione BitMEX: {symbol}")
                    
                    # Utilizziamo direttamente BitMEXAPI per maggiore affidabilità
                    try:
                        from bitmex_api import BitMEXAPI
                        bitmex_api = BitMEXAPI()
                        
                        # Tenta di chiudere la posizione
                        result = bitmex_api.close_position(symbol)
                        logger.info(f"Risultato chiusura BitMEX: {result}")
                        
                        # Verifica il risultato
                        if isinstance(result, dict) and "error" in result:
                            error_count += 1
                            results.append({
                                "symbol": symbol,
                                "success": False,
                                "error": result["error"]
                            })
                        elif isinstance(result, dict) and "warning" in result:
                            # Avviso ma continuiamo a considerarlo un successo parziale
                            results.append({
                                "symbol": symbol,
                                "success": True,
                                "warning": result["warning"]
                            })
                            success_count += 1
                        else:
                            success_count += 1
                            results.append({
                                "symbol": symbol,
                                "success": True,
                                "details": result
                            })
                        
                        # Attendiamo un attimo tra le operazioni per evitare rate limit
                        time.sleep(1)
                        
                    except Exception as e:
                        logger.error(f"Errore nella chiusura della posizione {symbol}: {str(e)}")
                        error_count += 1
                        results.append({
                            "symbol": symbol,
                            "success": False,
                            "error": str(e)
                        })
                
                # Verifica finale se ci sono ancora posizioni aperte
                try:
                    time.sleep(2)  # Attendiamo un po' per dare tempo all'exchange di elaborare
                    positions_after = api.get_open_positions()
                    remaining_positions = []
                    
                    if "success" in positions_after and positions_after["success"]:
                        remaining = positions_after.get("positions", [])
                        if remaining:
                            for pos in remaining:
                                pos_symbol = pos.get('symbol', '')
                                remaining_positions.append(pos_symbol)
                            
                            logger.warning(f"Attenzione: dopo il tentativo di chiusura, rimangono ancora {len(remaining)} posizioni aperte: {remaining_positions}")
                            
                            # Aggiungi un messaggio di warning al risultato
                            return {
                                "success": True,
                                "warning": f"Chiuse {success_count} posizioni, ma ne rimangono {len(remaining)} ancora aperte.",
                                "message": f"Chiuse {success_count} posizioni su {len(positions)}, con {error_count} errori",
                                "details": results,
                                "remaining_positions": remaining_positions
                            }
                    
                except Exception as check_e:
                    logger.error(f"Errore nella verifica finale delle posizioni: {str(check_e)}")
                
                # Risultato finale
                if error_count > 0:
                    return {
                        "success": True,
                        "warning": f"Chiuse {success_count} posizioni, ma ci sono stati {error_count} errori",
                        "message": f"Chiuse {success_count} posizioni su {len(positions)}",
                        "details": results
                    }
                else:
                    return {
                        "success": True,
                        "message": f"Chiuse con successo tutte le {len(positions)} posizioni",
                        "details": results
                    }
            
                            # Per altri exchange, utilizziamo l'approccio standard
            results = []
            for position in positions:
                symbol = position.get('symbol', '')
                side = position.get('side', '')
                contracts = float(position.get('contracts', 0) or 0)
                
                # Determina il lato dell'ordine (opposto alla posizione)
                order_side = 'sell' if side == 'long' else 'buy'
                
                # Chiudi la posizione specificando esplicitamente il lato
                params = {
                    'side': order_side,
                }
                
                # Imposta correttamente il flag reduceOnly a seconda dell'exchange
                if exchange_name == "BitMEX":
                    params['reduceOnly'] = True  # Per sicurezza
                elif exchange_name == "Bitfinex":
                    params['reduce_only'] = True  # Parametro specifico per Bitfinex
                elif exchange_name == "ByBit":
                    params['reduceOnly'] = True  # Parametro per ByBit
                    params['closeOnTrigger'] = True  # Parametro specifico ByBit per garantire la chiusura
                
                # Se la posizione è per SOL su Bitfinex, assicuriamo una dimensione minima
                if exchange_name == "Bitfinex" and 'SOL' in symbol.upper() and abs(contracts) < 0.1:
                    contracts = 0.1 if contracts > 0 else -0.1
                
                result = api.close_position(symbol, params=params)
                
                results.append({
                    "symbol": symbol,
                    "result": result
                })
            
            return {
                "success": True,
                "message": f"Chiuse {len(results)} posizioni",
                "details": results
            }
        else:
            return {"error": "Nessuna posizione trovata o errore nel recupero"}
    except Exception as e:
        return {"error": f"Errore nella chiusura delle posizioni: {str(e)}"}

def fetch_exchange_data(exchange_name, data_type="both"):
    """Recupera ordini aperti e posizioni aperte dall'exchange specificato"""
    api = get_exchange_api(exchange_name)
    
    if not api:
        return None, None
    
    orders = None
    positions = None
    
    # Recupera ordini aperti se richiesto
    if data_type in ["both", "orders"]:
        orders_result = api.get_open_orders()
        if "success" in orders_result and orders_result["success"]:
            orders = orders_result.get("orders", [])
        else:
            st.warning(f"Impossibile recuperare ordini da {exchange_name}: {orders_result.get('error', 'Errore sconosciuto')}")
    
    # Recupera posizioni aperte se richiesto
    if data_type in ["both", "positions"]:
        positions_result = api.get_open_positions()
        
        if "success" in positions_result and positions_result["success"]:
            positions = positions_result.get("positions", [])
        elif "warning" in positions_result:
            st.info(f"Informazione: {positions_result['warning']}")
        else:
            st.warning(f"Impossibile recuperare posizioni da {exchange_name}: {positions_result.get('error', 'Errore sconosciuto')}")
    
    return orders, positions

def fetch_all_exchanges_data(data_type="both"):
    """Recupera dati da tutti gli exchange supportati e li combina"""
    all_orders = []
    all_positions = []
    
    # Lista per memorizzare i dati grezzi delle posizioni
    if 'raw_positions_data' not in st.session_state:
        st.session_state.raw_positions_data = []
    
    for exchange in SUPPORTED_EXCHANGES:
        with st.spinner(f"Recupero dati da {exchange}..."):
            try:
                orders, positions = fetch_exchange_data(exchange, data_type)
                
                # Controllo che orders sia una lista valida
                if orders is not None and data_type in ["both", "orders"]:
                    orders_df = format_order_data(orders, exchange)
                    all_orders.append(orders_df)
                
                # Controllo che positions sia una lista valida
                if positions is not None and data_type in ["both", "positions"]:
                    # Salva i dati grezzi delle posizioni prima della formattazione
                    # Trova e rimuovi il vecchio dato per questo exchange, se esiste
                    st.session_state.raw_positions_data = [
                        item for item in st.session_state.raw_positions_data 
                        if item.get('exchange') != exchange
                    ]
                    
                    # Aggiungi il nuovo dato
                    st.session_state.raw_positions_data.append({
                        'exchange': exchange,
                        'positions': positions
                    })
                    
                    positions_df = format_position_data(positions, exchange)
                    all_positions.append(positions_df)
            except Exception as e:
                st.error(f"Errore durante il recupero dei dati da {exchange}: {str(e)}")
                # Log più dettagliato per il debug
                logger.error(f"Dettaglio errore per {exchange}: {type(e).__name__}: {str(e)}")
                continue
    
    # Combinazione dei risultati con gestione degli errori
    try:
        combined_orders = pd.concat(all_orders) if all_orders else pd.DataFrame()
    except Exception as e:
        st.error(f"Errore nella combinazione degli ordini: {str(e)}")
        logger.error(f"Dettaglio errore ordini: {str(e)}")
        combined_orders = pd.DataFrame()
    
    try:
        combined_positions = pd.concat(all_positions) if all_positions else pd.DataFrame()
    except Exception as e:
        st.error(f"Errore nella combinazione delle posizioni: {str(e)}")
        logger.error(f"Dettaglio errore posizioni: {str(e)}")
        combined_positions = pd.DataFrame()
    
    return combined_orders, combined_positions

def position_management_app():
    """Applicazione di gestione delle posizioni e degli ordini aperti"""
    
    st.title("Gestione Posizioni")
    
    st.write("Utilizza questa pagina per visualizzare e gestire i tuoi ordini e posizioni aperte su tutti gli exchange supportati.")
    
    if 'last_refresh_orders' not in st.session_state:
        st.session_state.last_refresh_orders = None
    
    if 'last_refresh_positions' not in st.session_state:
        st.session_state.last_refresh_positions = None
    
    # Per tenere traccia degli ordini cancellati
    if 'cancelled_orders' not in st.session_state:
        st.session_state.cancelled_orders = set()
    
    # Per tenere traccia delle posizioni chiuse
    if 'closed_positions' not in st.session_state:
        st.session_state.closed_positions = set()
    
    # Funzione per gestire la cancellazione degli ordini
    def handle_cancel_order(exchange, order_id, symbol):
        result = cancel_order(exchange, order_id, symbol)
        
        if "error" in result:
            st.error(f"Errore nella cancellazione dell'ordine: {result['error']}")
        else:
            st.success(f"Ordine {order_id} su {exchange} cancellato con successo")
            st.session_state.cancelled_orders.add(order_id)
            # Aggiorna automaticamente la lista degli ordini
            orders_df, _ = fetch_all_exchanges_data(data_type="orders")
            st.session_state.orders_df = orders_df
            st.experimental_rerun()
    
    # Funzione per gestire la chiusura delle posizioni
    def handle_close_position(exchange, symbol, size=None, side=None):
        try:
            # Per ByBit, implementiamo una logica speciale basata sui dati grezzi
            if exchange == "ByBit":
                # Ottieni raw_size dalle posizioni originali se disponibile
                raw_size = None
                notional = None
                original_position = None
                
                # Controlla se ci sono posizioni in session_state
                if hasattr(st.session_state, 'raw_positions_data'):
                    raw_positions = None
                    
                    # Cerca tra i dati originali delle posizioni in st.session_state
                    for exchange_data in st.session_state.raw_positions_data:
                        if exchange_data.get('exchange') == exchange:
                            raw_positions = exchange_data.get('positions', [])
                            break
                    
                    # Se abbiamo trovato le posizioni raw, cerchiamo quella specifica
                    if raw_positions:
                        for pos in raw_positions:
                            pos_symbol = pos.get('symbol', '')
                            
                            # Confronta direttamente o con formati speciali per ByBit
                            if pos_symbol == symbol or pos_symbol == symbol+":USDT" or pos_symbol == symbol+"Perp" or (pos_symbol == "SOL/USDT:USDT" and "SOL" in symbol.upper()):
                                original_position = pos
                                # Usa raw_size se disponibile
                                raw_size = pos.get('contracts', 0) or pos.get('size', 0) or pos.get('positionAmt', 0)
                                notional = pos.get('notional', 0)
                                pos_side = pos.get('side', '')
                                break
                
                # Se abbiamo trovato la posizione originale, usiamo i suoi dati esatti
                if original_position:
                    # Se abbiamo il raw_size, usiamo quello
                    if raw_size is not None and abs(float(raw_size)) > 0.000001:
                        contract_size = abs(float(raw_size))
                    # Se raw_size è zero o molto piccolo, ma abbiamo il notional, usiamo quello
                    elif notional is not None and abs(float(notional)) > 0.000001:
                        contract_size = abs(float(notional))
                    else:
                        # Altrimenti procedi come prima, convertendo dalla stringa visualizzata
                        try:
                            # Per altri casi, converti la formattazione numerica standard
                            raw_size = float(size.replace(',', '.'))
                            contract_size = raw_size
                        except (ValueError, AttributeError):
                            # Se la conversione fallisce, passiamo None
                            contract_size = None
                    
                    # Recupera il simbolo esatto dalla posizione originale
                    exact_symbol = original_position.get('symbol', symbol)
                    
                    # Chiama close_position con i dati esatti
                    result = close_position(exchange, exact_symbol, contract_size, side)
                else:
                    st.warning(f"Posizione originale non trovata per {symbol}. Tentativo con dati disponibili.")
                    result = close_position(exchange, symbol, size, side)
            else:
                # Per gli altri exchange, usa il metodo standard
                result = close_position(exchange, symbol, size, side)
        except Exception as e:
            st.error(f"Errore nell'elaborazione dei dati della posizione: {str(e)}")
            # Fallback al metodo standard
            result = close_position(exchange, symbol, size, side)
        
        if "error" in result:
            # Mostra dettagli completi dell'errore
            st.error(f"Errore nella chiusura della posizione: {result['error']}")
            if "details" in result:
                st.error(f"Dettagli: {result['details']}")
        else:
            st.success(f"Posizione {symbol} su {exchange} chiusa con successo")
            position_key = f"{exchange}_{symbol}"
            st.session_state.closed_positions.add(position_key)
            # Aggiorna automaticamente la lista delle posizioni
            _, positions_df = fetch_all_exchanges_data(data_type="positions")
            st.session_state.positions_df = positions_df
            st.experimental_rerun()
    
    # Funzione per gestire la chiusura di tutte le posizioni
    def handle_close_all_positions(exchange):
        result = close_all_positions(exchange)
        
        if "error" in result:
            st.error(f"Errore nella chiusura delle posizioni: {result['error']}")
        else:
            st.success(f"Tutte le posizioni su {exchange} chiuse con successo")
            # Aggiorna automaticamente la lista delle posizioni
            _, positions_df = fetch_all_exchanges_data(data_type="positions")
            st.session_state.positions_df = positions_df
            st.experimental_rerun()
    
    # Funzione per gestire la modifica del margine
    def handle_adjust_margin(exchange, symbol, amount):
        try:
            # Normalizza il formato del numero: sostituisci la virgola con il punto
            if isinstance(amount, str):
                amount = amount.replace(',', '.')
            
            # Converti in float
            amount_value = float(amount)
            
            # Chiama la funzione per modificare il margine
            result = adjust_position_margin(exchange, symbol, amount_value)
            
            # Indipendentemente dal risultato, aggiorniamo i dati delle posizioni
            # per riflettere eventuali modifiche o per mostrare lo stato più recente
            _, positions_df = fetch_all_exchanges_data(data_type="positions")
            st.session_state.positions_df = positions_df
            
            if "error" in result:
                # Mostra dettagli aggiuntivi dell'errore se disponibili
                error_message = result["error"]
                if "details" in result:
                    error_details = result["details"]
                    st.error(f"Errore nella modifica del margine: {error_message}\nDettagli: {error_details}")
                else:
                    st.error(f"Errore nella modifica del margine: {error_message}")
                    
                # Non facciamo rerun in caso di errore per permettere all'utente di vedere il messaggio
            else:
                # Mostra un messaggio più semplice e diretto
                message = f"Margine {'aggiunto' if amount_value > 0 else 'rimosso'} con successo: {abs(amount_value)} USDT"
                st.success(message)
                
                # Eseguiamo il rerun per aggiornare l'interfaccia
                st.experimental_rerun()
        except ValueError as e:
            st.error("Formato dell'importo non valido. Inserisci un numero valido (es. 0.5 o 1).")
    
    # Sezione per gli ordini aperti
    st.subheader("📋 Ordini Aperti")
    
    # Bottone per caricare gli ordini
    orders_col1, orders_col2 = st.columns([4, 1])
    
    with orders_col1:
        if st.button("Visualizza Ordini Aperti", type="primary", use_container_width=True, key="load_orders_btn"):
            # Registra l'orario dell'aggiornamento
            st.session_state.last_refresh_orders = time.time()
            
            try:
                # Recupera solo i dati degli ordini
                orders_df, _ = fetch_all_exchanges_data(data_type="orders")
                
                # Controlla che orders_df sia valido prima di salvarlo
                if orders_df is not None and isinstance(orders_df, pd.DataFrame):
                    # Salva i dati nella session state
                    st.session_state.orders_df = orders_df
                else:
                    st.error("Impossibile caricare i dati degli ordini. Risultato non valido.")
            except Exception as e:
                st.error(f"Errore durante il caricamento degli ordini: {str(e)}")
    
    with orders_col2:
        if st.button("🔄", use_container_width=True, key="refresh_orders_btn") and st.session_state.last_refresh_orders:
            # Aggiorna l'orario dell'aggiornamento
            st.session_state.last_refresh_orders = time.time()
            
            try:
                # Recupera solo i dati degli ordini
                orders_df, _ = fetch_all_exchanges_data(data_type="orders")
                
                # Controlla che orders_df sia valido prima di salvarlo
                if orders_df is not None and isinstance(orders_df, pd.DataFrame):
                    # Aggiorna i dati nella session state
                    st.session_state.orders_df = orders_df
                else:
                    st.error("Impossibile aggiornare i dati degli ordini. Risultato non valido.")
            except Exception as e:
                st.error(f"Errore durante l'aggiornamento degli ordini: {str(e)}")
    
    # Mostra l'orario dell'ultimo aggiornamento degli ordini
    if st.session_state.last_refresh_orders:
        from datetime import datetime
        last_refresh_time = datetime.fromtimestamp(st.session_state.last_refresh_orders).strftime('%H:%M:%S')
        st.info(f"Ultimo aggiornamento ordini: {last_refresh_time}")
    
    # Visualizza gli ordini se disponibili
    if 'orders_df' in st.session_state:
        orders_df = st.session_state.orders_df
        
        if not orders_df.empty:
            # Visualizza i dati in una tabella espandibile
            st.dataframe(orders_df, use_container_width=True)
            
            # Aggiungi pulsanti per cancellare gli ordini
            st.subheader("Cancella Ordini")
            
            for idx, order in orders_df.iterrows():
                exchange = order['Exchange']
                order_id = order['Order ID']
                symbol = order['Symbol']
                side = order['Side']
                amount = order['Amount']
                price = order['Price']
                
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(f"{exchange}: {symbol} {side} {amount} @ {price}")
                with col2:
                    if st.button(f"❌ Cancella", key=f"cancel_{order_id}"):
                        handle_cancel_order(exchange, order_id, symbol)
        else:
            st.info("Non ci sono ordini aperti")
    
    # Sezione per le posizioni aperte
    st.subheader("📊 Posizioni Aperte")
    
    # Bottone per caricare le posizioni
    positions_col1, positions_col2 = st.columns([4, 1])
    
    with positions_col1:
        if st.button("Visualizza Posizioni Aperte", type="primary", use_container_width=True, key="load_positions_btn"):
            # Registra l'orario dell'aggiornamento
            st.session_state.last_refresh_positions = time.time()
            
            try:
                # Recupera solo i dati delle posizioni
                _, positions_df = fetch_all_exchanges_data(data_type="positions")
                
                # Salva i dati nella session state
                if positions_df is not None:
                    st.session_state.positions_df = positions_df
                else:
                    st.error("Impossibile recuperare le posizioni: il risultato è None")
            except Exception as e:
                st.error(f"Errore durante il caricamento delle posizioni: {str(e)}")
                logger.error(f"Errore dettagliato: {type(e).__name__}: {str(e)}")
    
    with positions_col2:
        if st.button("🔄", use_container_width=True, key="refresh_positions_btn") and st.session_state.last_refresh_positions:
            # Aggiorna l'orario dell'aggiornamento
            st.session_state.last_refresh_positions = time.time()
            
            try:
                # Recupera solo i dati delle posizioni
                _, positions_df = fetch_all_exchanges_data(data_type="positions")
                
                # Salva i dati nella session state
                if positions_df is not None:
                    st.session_state.positions_df = positions_df
                else:
                    st.error("Impossibile recuperare le posizioni: il risultato è None")
            except Exception as e:
                st.error(f"Errore durante l'aggiornamento delle posizioni: {str(e)}")
                logger.error(f"Errore dettagliato: {type(e).__name__}: {str(e)}")
    
    # Mostra l'orario dell'ultimo aggiornamento delle posizioni
    if st.session_state.last_refresh_positions:
        from datetime import datetime
        last_refresh_time = datetime.fromtimestamp(st.session_state.last_refresh_positions).strftime('%H:%M:%S')
        st.info(f"Ultimo aggiornamento posizioni: {last_refresh_time}")
    
    # Visualizza le posizioni se disponibili
    if 'positions_df' in st.session_state:
        try:
            positions_df = st.session_state.positions_df
            
            if positions_df is None:
                st.warning("Nessun dato di posizioni disponibile. Prova a ricaricare.")
            elif not isinstance(positions_df, pd.DataFrame):
                st.error(f"Errore: positions_df non è un DataFrame valido ({type(positions_df)})")
            elif positions_df.empty:
                st.info("Non ci sono posizioni aperte")
            else:
                st.dataframe(positions_df, use_container_width=True)
                
                # Filtro per BitMEX, Bitfinex e ByBit
                bitmex_positions = positions_df[positions_df['Exchange'] == "BitMEX"]
                bitfinex_positions = positions_df[positions_df['Exchange'] == "Bitfinex"]
                bybit_positions = positions_df[positions_df['Exchange'] == "ByBit"]
                
                # Bottoni per chiudere tutte le posizioni
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if not bitmex_positions.empty:
                        if st.button("❌ Chiudi TUTTE le posizioni BitMEX", key="close_all_bitmex", type="primary"):
                            handle_close_all_positions("BitMEX")
                
                with col2:
                    if not bitfinex_positions.empty:
                        if st.button("❌ Chiudi TUTTE le posizioni Bitfinex", key="close_all_bitfinex", type="primary"):
                            handle_close_all_positions("Bitfinex")
                
                with col3:
                    if not bybit_positions.empty:
                        if st.button("❌ Chiudi TUTTE le posizioni ByBit", key="close_all_bybit", type="primary"):
                            handle_close_all_positions("ByBit")
                
                # Aggiungi pulsanti per chiudere le posizioni
                st.subheader("Gestione Posizioni")
                
                for idx, position in positions_df.iterrows():
                    exchange = position['Exchange']
                    symbol = position['Symbol']
                    side = position['Side']
                    size = position['Size']
                    entry_price = position['Entry Price']
                    
                    # Aggiungi bottone per chiudere la posizione per BitMEX, Bitfinex e ByBit
                    if exchange in ["BitMEX", "Bitfinex", "ByBit"]:
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.text(f"{exchange}: {symbol} {side} {size} @ {entry_price}")
                        with col2:
                            position_key = f"{exchange}_{symbol}"
                            if position_key not in st.session_state.closed_positions:
                                if st.button(f"❌ Chiudi", key=f"close_{position_key}"):
                                    handle_close_position(exchange, symbol, size, side)
                        
                        # Aggiungi interfaccia per modificare il margine (per BitMEX, ByBit e Bitfinex)
                        st.markdown("---")
                        st.markdown(f"**Modifica Margine {exchange} per {symbol}:**")
                        exchange_color = "#2196f3" if exchange == "BitMEX" else "#f44336"  # Blu per BitMEX, Rosso per ByBit
                        
                        # Mostra un'indicazione visiva dell'exchange
                        st.markdown(f"<div style='padding: 5px; background-color: {exchange_color}; color: white; border-radius: 5px; margin-bottom: 10px;'>Exchange: {exchange}</div>", unsafe_allow_html=True)
                        
                        margin_col1, margin_col2, margin_col3 = st.columns([2, 1, 1])
                        with margin_col1:
                            # Imposta valori predefiniti diversi a seconda dell'exchange
                            if exchange == "BitMEX":
                                default_value = "0.5"
                            elif exchange == "Bitfinex":
                                default_value = "0.01"
                            else:  # ByBit
                                default_value = "0.1"
                                
                            margin_amount = st.text_input("USDT", 
                                                         default_value, 
                                                         key=f"margin_{position_key}",
                                                         help="Inserisci l'importo in USDT. Usa il punto o la virgola come separatore decimale. Ad esempio: 0.5 o 0,5 per aggiungere mezzo USDT.")
                        with margin_col2:
                            button_label = f"➕ Aggiungi Margine {exchange}"
                            if st.button(button_label, key=f"add_margin_{position_key}"):
                                try:
                                    # Normalizza il formato del numero: sostituisci la virgola con il punto
                                    normalized_amount = margin_amount.replace(',', '.') if isinstance(margin_amount, str) else margin_amount
                                    amount = float(normalized_amount)
                                    if amount <= 0:
                                        st.error("L'importo deve essere positivo")
                                    else:
                                        # Mostra esplicitamente il valore che verrà utilizzato
                                        st.info(f"Aggiunta di {amount} USDT al margine su {exchange}")
                                        # Per ByBit, suggeriamo valori più piccoli se l'importo è grande
                                        if exchange == "ByBit" and amount > 5:
                                            st.warning(f"Nota: ByBit potrebbe rifiutare importi elevati. Considera di usare valori più piccoli se ricevi errori.")
                                        # Per Bitfinex, avvertiamo sul funzionamento diverso
                                        elif exchange == "Bitfinex":
                                            # Ottieni il valore attuale del collaterale
                                            current_collateral = 0
                                            for pos in st.session_state.raw_positions_data:
                                                if isinstance(pos, dict) and pos.get('exchange') == exchange and pos.get('symbol') == symbol:
                                                    current_collateral = float(pos.get('position_margin') or 0)
                                                    break
                                            
                                            # Calcola il nuovo collaterale come somma del valore attuale e del valore da aggiungere
                                            new_collateral = current_collateral + amount
                                            
                                            # Passa il nuovo valore totale del collaterale
                                            handle_adjust_margin(exchange, symbol, new_collateral)
                                        else:
                                            handle_adjust_margin(exchange, symbol, amount)
                                except ValueError:
                                    st.error("Inserisci un importo valido (es. 0.5 o 0,5)")
                        with margin_col3:
                            button_label = f"➖ Rimuovi Margine {exchange}"
                            if st.button(button_label, key=f"remove_margin_{position_key}"):
                                try:
                                    # Normalizza il formato del numero: sostituisci la virgola con il punto
                                    normalized_amount = margin_amount.replace(',', '.') if isinstance(margin_amount, str) else margin_amount
                                    amount = float(normalized_amount)
                                    if amount <= 0:
                                        st.error("L'importo deve essere positivo")
                                    else:
                                        # Mostra esplicitamente il valore che verrà utilizzato
                                        st.info(f"Rimozione di {amount} USDT dal margine su {exchange}")
                                        # Per ByBit, suggeriamo valori più piccoli se l'importo è grande
                                        if exchange == "ByBit" and amount > 5:
                                            st.warning(f"Nota: ByBit potrebbe rifiutare importi elevati. Considera di usare valori più piccoli se ricevi errori.")
                                        
                                        # Per Bitfinex, avvertiamo sul funzionamento diverso
                                        elif exchange == "Bitfinex":
                                            # Ottieni il valore attuale del collaterale
                                            current_collateral = 0
                                            for pos in st.session_state.raw_positions_data:
                                                if isinstance(pos, dict) and pos.get('exchange') == exchange and pos.get('symbol') == symbol:
                                                    current_collateral = float(pos.get('position_margin') or 0)
                                                    break
                                            
                                            # Calcola il nuovo collaterale come sottrazione del valore attuale e del valore da rimuovere
                                            new_collateral = current_collateral - amount
                                            
                                            # Passa il nuovo valore totale del collaterale
                                            handle_adjust_margin(exchange, symbol, new_collateral)
                                        else:
                                            # Per gli altri exchange, neghiamo l'importo per indicare la rimozione
                                            handle_adjust_margin(exchange, symbol, -amount)  # Neghiamo l'importo per indicare la rimozione
                                except ValueError:
                                    st.error("Inserisci un importo valido (es. 0.5 o 0,5)")
                        st.markdown("---")
        except Exception as e:
            st.error(f"Errore durante la visualizzazione delle posizioni: {str(e)}")
            logger.error(f"Errore dettagliato nella visualizzazione: {type(e).__name__}: {str(e)}")
    else:
        st.info("Nessun dato di posizioni caricato. Clicca su 'Visualizza Posizioni Aperte'.")

def adjust_position_margin(exchange_name, symbol, amount):
    """Aggiunge o rimuove margine da una posizione esistente
    
    Args:
        exchange_name (str): Nome dell'exchange
        symbol (str): Simbolo della posizione
        amount (float): Importo di margine da aggiungere (positivo) o rimuovere (negativo) in USDT
        
    Returns:
        dict: Risultato dell'operazione
    """
    try:
        api = get_exchange_api(exchange_name)
        if not api:
            return {"error": f"Impossibile creare l'API per {exchange_name}"}
        
        # Supportiamo BitMEX, ByBit e Bitfinex
        if exchange_name not in ["BitMEX", "ByBit", "Bitfinex"]:
            return {"error": f"Modifica margine attualmente supportata solo per BitMEX, ByBit e Bitfinex"}
        
        # Verifica che l'amount sia un numero
        try:
            # Se l'input è una stringa, sostituisci la virgola con il punto
            if isinstance(amount, str):
                amount = amount.replace(',', '.')
            
            amount_value = float(amount)
        except (ValueError, TypeError):
            return {"error": "L'importo del margine deve essere un numero"}
        
        # Ottieni informazioni sul saldo dell'account
        account_info = api.get_account_info()
        
        # Caso speciale per SOL su BitMEX
        # Se è Solana su BitMEX, dobbiamo recuperare esplicitamente tutte le posizioni
        position_found = False
        if exchange_name == "BitMEX" and 'SOL' in symbol.upper():
            # Recupera tutte le posizioni, non filtrando per simbolo
            # in modo da visualizzare entrambe SOLUSDT e SOLUSD
            from bitmex_api import BitMEXAPI
            bitmex_api = BitMEXAPI()
            positions = bitmex_api.get_open_positions()
            
            # Cerca qualsiasi posizione attiva di SOL, indipendentemente dal suffisso specifico
            for pos in positions:
                pos_symbol = pos.get('symbol', '')
                pos_qty = pos.get('currentQty', 0)
                pos_currency = pos.get('currency', '')
                
                # Se è una posizione SOL attiva, la usiamo
                if 'SOL' in pos_symbol.upper() and pos_qty != 0:
                    logger.info(f"Trovata posizione SOL attiva: {pos_symbol}, qty={pos_qty}, currency={pos_currency}")
                    symbol = pos_symbol  # Usa il simbolo esatto della posizione attiva
                    position_found = True
                    break
            
            # Se non abbiamo trovato posizioni SOL attive, ma stiamo aggiungendo margine,
            # usa SOLUSDT che accetta USDT
            if not position_found and amount_value > 0:
                symbol = 'SOLUSDT'
                logger.info(f"Nessuna posizione SOL attiva trovata, ma stiamo aggiungendo margine in USDT, quindi usiamo {symbol}")
                # Verifica comunque se esiste la posizione SOLUSDT
                solusdt_positions = api.get_open_positions('SOLUSDT')
                if isinstance(solusdt_positions, list) and len(solusdt_positions) > 0:
                    for pos in solusdt_positions:
                        pos_qty = pos.get('currentQty', 0)
                        if pos_qty != 0:
                            position_found = True
                            break
            
            # Se continuiamo a non trovare una posizione attiva, avvisa l'utente
            if not position_found:
                return {"error": f"Nessuna posizione aperta trovata per SOL su BitMEX"}
        else:
            # Per altri casi, verifica nel modo standard
            positions_result = api.get_open_positions(symbol)
            
            if isinstance(positions_result, dict) and "success" in positions_result and positions_result["success"]:
                positions = positions_result.get("positions", [])
                for pos in positions:
                    if pos.get('symbol', '') == symbol:
                        position_found = True
                        break
            elif isinstance(positions_result, list):
                # Se l'API ha restituito direttamente una lista di posizioni
                for pos in positions_result:
                    if pos.get('symbol', '') == symbol:
                        position_found = True
                        break
                                    
            if not position_found:
                return {"error": f"Nessuna posizione aperta trovata per {symbol}"}
        
        # Se stiamo tentando di aggiungere margine, controlla che ci sia saldo sufficiente
        if amount_value > 0:
            # Controllo saldo disponibile specificamente per USDT
            available_usdt = None
            if isinstance(account_info, dict):
                # Cerca il saldo USDT nel nuovo formato che abbiamo aggiunto
                if "usdt_balance" in account_info and account_info["usdt_balance"]:
                    available_usdt = account_info["usdt_balance"].get("available", 0)
                elif "availableUSDT" in account_info:
                    available_usdt = account_info["availableUSDT"]
                # Se non troviamo il saldo USDT, cerca altre alternative
                elif "balances" in account_info and "USDT" in account_info["balances"]:
                    available_usdt = account_info["balances"]["USDT"]
            
            if available_usdt is not None:
                # Converti il saldo in float per sicurezza
                try:
                    available_usdt_value = float(available_usdt)
                    
                    if available_usdt_value < amount_value:
                        return {"error": f"Saldo insufficiente. Disponibile: {available_usdt_value:.8f} USDT, Richiesto: {amount_value} USDT"}
                except (ValueError, TypeError) as e:
                    pass
        
        # Chiamiamo l'API per modificare il margine
        result = api.adjust_position_margin(symbol, amount_value)
        
        # Verificare il risultato
        if "success" in result and result["success"]:
            return {
                "success": True, 
                "message": f"Margine {'aggiunto' if amount_value > 0 else 'rimosso'} con successo: {abs(amount_value)} USDT",
                "amount_usdt": amount_value,
                "raw_response": result
            }
        else:
            # Aggiungere i dettagli dell'errore alla risposta
            error_response = {"error": result.get("error", "Errore sconosciuto nella modifica del margine")}
            if "details" in result:
                error_response["details"] = result["details"]
            return error_response
    except Exception as e:
        return {"error": f"Errore nella modifica del margine: {str(e)}"}

if __name__ == "__main__":
    # Configura la pagina Streamlit
    st.set_page_config(page_title="Gestione Posizioni", layout="wide")
    
    # Esegui l'app
    position_management_app() 