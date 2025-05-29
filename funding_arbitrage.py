"""
Funding Arbitrage Application - Checkpoint Version 3.0 (Codice Pulito)
Data: 15/05/2025
"""

import streamlit as st
import os
import math
import time
from dotenv import load_dotenv
from ccxt_api import CCXTAPI
from position_management import position_management_app
import logging

# Configurazione logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('funding_arbitrage')

# Carica le variabili d'ambiente
load_dotenv()

def get_sol_price():
    """
    Ottiene il prezzo attuale di SOLANA in USDT
    
    Returns:
        float: Prezzo di SOL in USDT, 0 se errore
    """
    try:
        # Prova con ByBit prima
        api = CCXTAPI('bybit')
        ticker = api.exchange.fetch_ticker('SOL/USDT')
        price = ticker['last']
        logger.info(f"Prezzo SOL ottenuto da ByBit: {price} USDT")
        return float(price)
    except Exception as e:
        logger.warning(f"Errore nel recupero prezzo da ByBit: {str(e)}")
        
        try:
            # Fallback a BitMEX
            api = CCXTAPI('bitmex')
            ticker = api.exchange.fetch_ticker('SOLUSDT')
            price = ticker['last']
            logger.info(f"Prezzo SOL ottenuto da BitMEX: {price} USDT")
            return float(price)
        except Exception as e:
            logger.warning(f"Errore nel recupero prezzo da BitMEX: {str(e)}")
            
            # Fallback finale a prezzo fisso stimato
            estimated_price = 100.0
            logger.warning(f"Uso prezzo stimato: {estimated_price} USDT")
            return estimated_price

def calculate_sol_size(usdt_amount):
    """
    Calcola la quantità di SOL da utilizzare per ciascuna posizione
    
    Args:
        usdt_amount: Importo totale in USDT
        
    Returns:
        dict: Contiene sol_size e dettagli del calcolo
    """
    # Passo 1: Dividi per 2
    half_usdt = usdt_amount / 2
    
    # Passo 2: Moltiplica per 5 (leva)
    leveraged_usdt = half_usdt * 5
    
    # Passo 3: Ottieni prezzo SOL
    sol_price = get_sol_price()
    
    if sol_price <= 0:
        return {
            "success": False,
            "error": "Impossibile ottenere il prezzo di SOLANA"
        }
    
    # Passo 4: Converti in quantità SOL
    sol_quantity = leveraged_usdt / sol_price
    
    # Passo 5: Arrotonda per difetto con step 0.1
    sol_size = math.floor(sol_quantity * 10) / 10
    
    return {
        "success": True,
        "sol_size": sol_size,
        "details": {
            "usdt_total": usdt_amount,
            "usdt_per_position": half_usdt,
            "usdt_leveraged": leveraged_usdt,
            "sol_price": sol_price,
            "sol_quantity_raw": sol_quantity,
            "sol_size_final": sol_size
        }
    }

def _bybit_internal_transfer(amount, from_wallet='funding', to_wallet='unified'):
    """
    Esegue un trasferimento interno su ByBit tra wallet
    
    Args:
        amount (float): Quantità di USDT da trasferire
        from_wallet (str): Wallet di origine (default: funding)
        to_wallet (str): Wallet di destinazione (default: unified)
        
    Returns:
        dict: Risultato dell'operazione
    """
    try:
        logger.info(f"Trasferimento interno ByBit: {amount} USDT da {from_wallet} a {to_wallet}")
        
        api = CCXTAPI('bybit')
        
        # Metodo 1: Usa CCXT transfer (più affidabile)
        try:
            result = api.exchange.transfer(
                code='USDT',
                amount=amount,
                fromAccount=from_wallet,
                toAccount=to_wallet
            )
            
            if result:
                return {
                    "success": True,
                    "message": f"Trasferimento interno ByBit di {amount} USDT da {from_wallet} a {to_wallet} completato con successo",
                    "transaction_id": result.get('id'),
                    "method": "CCXT",
                    "info": result
                }
            else:
                return {
                    "success": False,
                    "error": "Trasferimento CCXT restituito None"
                }
                
        except Exception as ccxt_error:
            logger.warning(f"Metodo CCXT fallito: {str(ccxt_error)}")
            
            # Metodo 2: Fallback con API v5 diretta
            try:
                transfer_id = f"bybit_transfer_{int(time.time() * 1000)}"
                
                # Mappa i nomi dei wallet al formato ByBit
                wallet_mapping = {
                    'funding': 'FUND',
                    'unified': 'UNIFIED',
                    'spot': 'SPOT',
                    'derivative': 'CONTRACT'
                }
                
                from_account_type = wallet_mapping.get(from_wallet, from_wallet.upper())
                to_account_type = wallet_mapping.get(to_wallet, to_wallet.upper())
                
                params = {
                    'transferId': transfer_id,
                    'coin': 'USDT',
                    'amount': str(amount),
                    'fromAccountType': from_account_type,
                    'toAccountType': to_account_type
                }
                
                logger.info(f"Tentativo API v5 con parametri: {params}")
                result = api.exchange.private_post_v5_asset_transfer_inter_transfer(params)
                
                if result and result.get('retCode') == 0:
                    return {
                        "success": True,
                        "message": f"Trasferimento interno ByBit di {amount} USDT da {from_wallet} a {to_wallet} completato con successo",
                        "transaction_id": result.get('result', {}).get('transferId', transfer_id),
                        "method": "API_v5",
                        "info": result
                    }
                else:
                    error_msg = result.get('retMsg', 'Errore sconosciuto') if result else 'Nessuna risposta'
                    return {
                        "success": False,
                        "error": f"Trasferimento API v5 fallito: {error_msg}",
                        "method": "API_v5",
                        "info": result
                    }
                    
            except Exception as api_error:
                logger.error(f"Anche il metodo API v5 è fallito: {str(api_error)}")
                return {
                    "success": False,
                    "error": f"Tutti i metodi di trasferimento falliti. CCXT: {str(ccxt_error)}, API v5: {str(api_error)}"
                }
                
    except Exception as e:
        logger.error(f"Errore durante il trasferimento interno ByBit: {str(e)}")
        return {
            "success": False,
            "error": f"Errore durante il trasferimento interno ByBit: {str(e)}"
        }

def check_bitmex_balance(required_usdt):
    """
    Controlla il saldo disponibile su BitMEX
    
    Args:
        required_usdt: USDT richiesti per la posizione
        
    Returns:
        dict: Risultato del controllo
    """
    try:
        st.write(f"🔍 **Controllo saldo BitMEX** (richiesto: {required_usdt} USDT)")
        
        api = CCXTAPI('bitmex')
        balance = api.exchange.fetch_balance()
        
        # Per BitMEX, il saldo è in XBt (satoshi) per Bitcoin e USDT per altri
        usdt_balance = balance.get('USDT', {}).get('free', 0)
        
        st.write(f"💰 Saldo disponibile BitMEX: {usdt_balance} USDT")
        
        if usdt_balance >= required_usdt:
            st.success(f"✅ BitMEX: Saldo sufficiente ({usdt_balance} >= {required_usdt})")
            return {
                "success": True,
                "available": usdt_balance,
                "required": required_usdt,
                "sufficient": True
            }
        else:
            st.error(f"❌ BitMEX: Saldo insufficiente ({usdt_balance} < {required_usdt})")
            return {
                "success": False,
                "available": usdt_balance,
                "required": required_usdt,
                "sufficient": False,
                "error": f"Saldo insufficiente: {usdt_balance} USDT disponibili, {required_usdt} USDT richiesti"
            }
            
    except Exception as e:
        st.error(f"❌ Errore nel controllo saldo BitMEX: {str(e)}")
        return {
            "success": False,
            "error": f"Errore nel controllo saldo BitMEX: {str(e)}"
        }

def check_bybit_balance(required_usdt):
    """
    Controlla il saldo disponibile su ByBit e gestisce i trasferimenti tra wallet
    
    Args:
        required_usdt: USDT richiesti per la posizione
        
    Returns:
        dict: Risultato del controllo e eventuale trasferimento
    """
    try:
        st.write(f"🔍 **Controllo saldo ByBit** (richiesto: {required_usdt} USDT)")
        
        api = CCXTAPI('bybit')
        
        # Metodo 1: fetch_balance standard
        balance = api.exchange.fetch_balance()
        
        # Inizializza i saldi
        unified_balance = 0
        funding_balance = 0
        
        # Recupera saldo unified
        if 'unified' in balance:
            unified_balance = balance['unified'].get('USDT', {}).get('free', 0)
        elif 'USDT' in balance:
            unified_balance = balance['USDT'].get('free', 0)
        
        st.write(f"💰 Saldo Unified (metodo 1): {unified_balance} USDT")
        
        # Metodo 2: Prova con fetch_balance e parametri specifici per funding
        try:
            funding_balance_ccxt = api.exchange.fetch_balance({'type': 'funding'})
            if 'USDT' in funding_balance_ccxt:
                funding_balance = funding_balance_ccxt['USDT'].get('free', 0)
                st.write(f"💰 Saldo Funding (metodo CCXT type): {funding_balance} USDT")
        except Exception as e:
            st.write(f"⚠️ Metodo CCXT type fallito: {str(e)}")
        
        # Metodo 3: Prova con fetchBalance e wallet specifico
        if funding_balance == 0:
            try:
                funding_params = {'accountType': 'FUND'}
                funding_balance_direct = api.exchange.fetchBalance(funding_params)
                if 'USDT' in funding_balance_direct:
                    funding_balance = funding_balance_direct['USDT'].get('free', 0)
                    st.write(f"💰 Saldo Funding (metodo fetchBalance): {funding_balance} USDT")
            except Exception as e:
                st.write(f"⚠️ Metodo fetchBalance fallito: {str(e)}")
        
        # Metodo 4: API diretta v5 per wallet balance
        if funding_balance == 0:
            try:
                wallet_response = api.exchange.private_get_v5_account_wallet_balance({
                    'accountType': 'FUND'
                })
                
                if wallet_response and 'result' in wallet_response:
                    for account in wallet_response['result'].get('list', []):
                        for coin in account.get('coin', []):
                            if coin.get('coin') == 'USDT':
                                funding_balance = float(coin.get('walletBalance', 0))
                                st.write(f"💰 Saldo Funding (metodo API v5): {funding_balance} USDT")
                                break
            except Exception as e:
                st.write(f"⚠️ Metodo API v5 fallito: {str(e)}")
        
        # Metodo 5: Prova con private_get_v5_asset_transfer_query_account_coins_balance
        if funding_balance == 0:
            try:
                coins_balance = api.exchange.private_get_v5_asset_transfer_query_account_coins_balance({
                    'accountType': 'FUND',
                    'coin': 'USDT'
                })
                
                if coins_balance and 'result' in coins_balance:
                    balance_info = coins_balance['result'].get('balance', [])
                    for coin_info in balance_info:
                        if coin_info.get('coin') == 'USDT':
                            funding_balance = float(coin_info.get('walletBalance', 0))
                            st.write(f"💰 Saldo Funding (metodo coins balance): {funding_balance} USDT")
                            break
            except Exception as e:
                st.write(f"⚠️ Metodo coins balance fallito: {str(e)}")
        
        # Metodo 6: Ricerca completa in tutti i wallet disponibili
        if funding_balance == 0:
            try:
                all_balances = api.exchange.private_get_v5_account_wallet_balance({})
                
                if all_balances and 'result' in all_balances:
                    st.write("🔍 Ricerca in tutti i wallet disponibili...")
                    
                    for account in all_balances['result'].get('list', []):
                        account_type = account.get('accountType', '')
                        st.write(f"📁 Wallet trovato: {account_type}")
                        
                        for coin in account.get('coin', []):
                            coin_name = coin.get('coin', '')
                            wallet_balance = float(coin.get('walletBalance', 0))
                            
                            if coin_name == 'USDT' and wallet_balance > 0:
                                st.write(f"💰 {account_type}: {wallet_balance} USDT")
                                
                                if account_type == 'FUND':
                                    funding_balance = wallet_balance
            except Exception as e:
                st.write(f"⚠️ Ricerca completa wallet fallita: {str(e)}")
        
        total_balance = unified_balance + funding_balance
        
        st.write(f"💰 **Saldo ByBit finale:**")
        st.write(f"  - Unified: {unified_balance} USDT")
        st.write(f"  - Funding: {funding_balance} USDT")
        st.write(f"  - Totale: {total_balance} USDT")
        
        # Controllo 1: Unified è già sufficiente
        if unified_balance >= required_usdt:
            st.success(f"✅ ByBit: Saldo unified sufficiente ({unified_balance} >= {required_usdt})")
            return {
                "success": True,
                "unified_balance": unified_balance,
                "funding_balance": funding_balance,
                "total_balance": total_balance,
                "required": required_usdt,
                "transfer_needed": False,
                "sufficient": True
            }
        
        # Controllo 2: Totale è sufficiente ma serve trasferimento
        elif total_balance >= required_usdt:
            transfer_amount = required_usdt - unified_balance
            st.warning(f"⚠️ ByBit: Serve trasferimento da funding a unified ({transfer_amount} USDT)")
            
            # Prima verifica che ci sia abbastanza nel funding wallet
            if funding_balance < transfer_amount:
                st.error(f"❌ Saldo funding insufficiente per il trasferimento: {funding_balance} < {transfer_amount}")
                return {
                    "success": False,
                    "error": f"Saldo funding insufficiente: {funding_balance} USDT disponibili, {transfer_amount} USDT richiesti",
                    "funding_balance": funding_balance,
                    "transfer_amount": transfer_amount
                }
            
            # Esegui il trasferimento usando la funzione dedicata
            st.write(f"🔄 **Esecuzione trasferimento ByBit:**")
            st.write(f"  - Da: Funding wallet ({funding_balance} USDT)")
            st.write(f"  - A: Unified wallet ({unified_balance} USDT)")
            st.write(f"  - Importo: {transfer_amount} USDT")
            
            # Usa la funzione di trasferimento interno
            transfer_result = _bybit_internal_transfer(transfer_amount, 'funding', 'unified')
            
            if transfer_result['success']:
                st.success(f"✅ {transfer_result['message']}")
                
                # Verifica il nuovo saldo dopo breve attesa
                time.sleep(3)
                new_balance = api.exchange.fetch_balance()
                new_unified = new_balance.get('USDT', {}).get('free', 0)
                if 'unified' in new_balance:
                    new_unified = new_balance['unified'].get('USDT', {}).get('free', 0)
                
                return {
                    "success": True,
                    "unified_balance": new_unified,
                    "funding_balance": funding_balance - transfer_amount,
                    "total_balance": total_balance,
                    "required": required_usdt,
                    "transfer_needed": True,
                    "transfer_amount": transfer_amount,
                    "transfer_completed": True,
                    "sufficient": True,
                    "transfer_method": transfer_result.get('method', 'Unknown')
                }
            else:
                st.error(f"❌ {transfer_result['error']}")
                return {
                    "success": False,
                    "error": transfer_result['error'],
                    "transfer_needed": True,
                    "transfer_completed": False,
                    "manual_action_required": True
                }
        
        # Controllo 3: Totale insufficiente
        else:
            shortage = required_usdt - total_balance
            st.error(f"❌ ByBit: Saldo totale insufficiente (mancano {shortage} USDT)")
            return {
                "success": False,
                "unified_balance": unified_balance,
                "funding_balance": funding_balance,
                "total_balance": total_balance,
                "required": required_usdt,
                "sufficient": False,
                "shortage": shortage,
                "error": f"Saldo insufficiente: {total_balance} USDT totali, {required_usdt} USDT richiesti"
            }
            
    except Exception as e:
        st.error(f"❌ Errore nel controllo saldo ByBit: {str(e)}")
        return {
            "success": False,
            "error": f"Errore nel controllo saldo ByBit: {str(e)}"
        }

def check_capital_requirements(exchange_long, exchange_short, required_usdt_per_position):
    """
    Controlla i requisiti di capitale per entrambi gli exchange
    
    Args:
        exchange_long: Nome dell'exchange per posizione long
        exchange_short: Nome dell'exchange per posizione short
        required_usdt_per_position: USDT richiesti per ciascuna posizione
        
    Returns:
        dict: Risultato completo del controllo capitale
    """
    st.write("## 💰 Controllo Requisiti Capitale")
    
    results = {
        "long_exchange": {"name": exchange_long, "check": None},
        "short_exchange": {"name": exchange_short, "check": None},
        "overall_success": False
    }
    
    # Controllo exchange LONG
    if exchange_long == "BitMEX":
        results["long_exchange"]["check"] = check_bitmex_balance(required_usdt_per_position)
    elif exchange_long == "ByBit":
        results["long_exchange"]["check"] = check_bybit_balance(required_usdt_per_position)
    else:
        st.warning(f"⚠️ Controllo capitale per {exchange_long} non ancora implementato")
        results["long_exchange"]["check"] = {"success": False, "error": "Exchange non supportato"}
    
    # Controllo exchange SHORT
    if exchange_short == "BitMEX":
        results["short_exchange"]["check"] = check_bitmex_balance(required_usdt_per_position)
    elif exchange_short == "ByBit":
        results["short_exchange"]["check"] = check_bybit_balance(required_usdt_per_position)
    else:
        st.warning(f"⚠️ Controllo capitale per {exchange_short} non ancora implementato")
        results["short_exchange"]["check"] = {"success": False, "error": "Exchange non supportato"}
    
    # Verifica risultato complessivo
    long_ok = results["long_exchange"]["check"].get("success", False)
    short_ok = results["short_exchange"]["check"].get("success", False)
    
    results["overall_success"] = long_ok and short_ok
    
    # Riepilogo finale
    st.write("### 📊 Riepilogo Controllo Capitale")
    if results["overall_success"]:
        st.success("✅ **Capitale sufficiente su entrambi gli exchange**")
    else:
        st.error("❌ **Capitale insufficiente o errori rilevati**")
        
        if not long_ok:
            error_msg = results["long_exchange"]["check"].get("error", "Errore sconosciuto")
            st.error(f"• LONG ({exchange_long}): {error_msg}")
            
        if not short_ok:
            error_msg = results["short_exchange"]["check"].get("error", "Errore sconosciuto")
            st.error(f"• SHORT ({exchange_short}): {error_msg}")
    
    return results

def find_solana_contract(api, exchange_name):
    """Trova il contratto SOLANA su un exchange specifico"""
    st.write(f"🔍 Ricerca contratto SOLANA su {exchange_name}...")
    
    # Ottieni tutti i futures perpetui
    all_futures = api.get_perpetual_futures()
    st.write(f"📋 Trovati {len(all_futures)} futures perpetui su {exchange_name}")
    
    # Gestisci i formati specifici per exchange
    if exchange_name == "Bitfinex":
        st.write("🔧 Logica specifica per Bitfinex...")
        # Formati possibili per SOLANA su Bitfinex
        possible_formats = ["tSOLF0:USTF0", "tSOLF0:USDF0", "tSOL:USTF0", "tSOLF0:UST0"]
        st.write(f"🎯 Formati da testare: {possible_formats}")
        
        # Cerca prima nei formati conosciuti
        for symbol in possible_formats:
            if symbol in all_futures:
                st.success(f"✅ Simbolo trovato nei formati standard: {symbol}")
                return symbol
        
        # Cerca per pattern parziale se non viene trovato nei formati standard
        for symbol in all_futures:
            if 'SOL' in symbol.upper() and 'F0:' in symbol:
                st.success(f"✅ Simbolo trovato per pattern: {symbol}")
                return symbol
        
        # Se non viene trovato, utilizza l'API nativa di Bitfinex come fallback
        st.warning("⚠️ Tentativo con API nativa Bitfinex...")
        try:
            from bitfinex_api import BitfinexAPI
            bitfinex_api = BitfinexAPI()
            bitfinex_futures = bitfinex_api.get_perpetual_futures()
            st.write(f"📋 API nativa: {len(bitfinex_futures)} simboli trovati")
            
            # Controlla nei risultati dell'API nativa
            for symbol in bitfinex_futures:
                if 'SOL' in symbol.upper() and 'F0:' in symbol:
                    st.success(f"✅ Simbolo trovato con API nativa: {symbol}")
                    return symbol
            
            # Se ancora non trovato, usa il formato predefinito
            st.warning("⚠️ Uso formato predefinito: tSOLF0:USTF0")
            return "tSOLF0:USTF0"
        except Exception as e:
            st.error(f"❌ Errore API nativa: {str(e)}")
            st.warning("⚠️ Uso formato predefinito: tSOLF0:USTF0")
            return "tSOLF0:USTF0"
    
    elif exchange_name == "BitMEX":
        st.write("🔧 Logica specifica per BitMEX...")
        # Per BitMEX, cerca simboli con SOL
        for symbol in all_futures:
            if 'SOL' in symbol.upper() and 'USDT' in symbol.upper():
                st.success(f"✅ Simbolo BitMEX trovato: {symbol}")
                return symbol
        
        # Se non trovato, usa il formato predefinito
        st.warning("⚠️ Uso formato predefinito BitMEX: SOLUSDT")
        return "SOLUSDT"
    
    elif exchange_name == "ByBit":
        st.write("🔧 Logica specifica per ByBit...")
        # Per ByBit, cerca esattamente SOL/USDT o SOLUSDT
        exact_symbols = ["SOLUSDT", "SOL/USDT"]
        st.write(f"🎯 Simboli esatti da testare: {exact_symbols}")
        
        # Prima prova a trovare i simboli esatti
        for symbol in exact_symbols:
            if symbol in all_futures:
                st.success(f"✅ Simbolo esatto trovato: {symbol}")
                return symbol
        
        # Cerca rigorosamente il simbolo SOLUSDT, escludendo simboli simili
        st.write("🔍 Ricerca pattern intelligente...")
        for symbol in all_futures:
            # Controlla se il simbolo è esattamente SOLUSDT (caso più comune)
            if symbol == "SOLUSDT":
                st.success(f"✅ SOLUSDT trovato: {symbol}")
                return symbol
            # Controlla se il simbolo è in uno di questi formati: SOL-USDT, SOL_USDT
            elif symbol in ["SOL-USDT", "SOL_USDT"]:
                st.success(f"✅ Formato alternativo trovato: {symbol}")
                return symbol
            # Controlla se il simbolo è SOL/USDT (formato con slash)
            elif symbol == "SOL/USDT":
                st.success(f"✅ Formato slash trovato: {symbol}")
                return symbol
        
        # Se non vengono trovati i simboli esatti, fai un controllo intelligente
        st.write("🔍 Controllo intelligente anti-collisione...")
        for symbol in all_futures:
            # Verifica che il simbolo inizi con "SOL" e che non contenga lettere
            # tra la "L" iniziale di SOL e "USDT" alla fine
            if (symbol.startswith("SOL") and 
                symbol.endswith("USDT") and 
                not any(x in symbol.upper() for x in ["SOLO", "SOLAYER", "SOLA"])):
                st.success(f"✅ Simbolo valido trovato (controllo intelligente): {symbol}")
                return symbol
        
        # Se non è stato trovato nessun simbolo, usa il formato predefinito
        st.warning("⚠️ Nessun simbolo SOL valido trovato, uso SOLUSDT predefinito")
        return "SOLUSDT"
    
    # Per altri exchange
    else:
        st.write("🔧 Logica generica...")
        # Cerca simboli con SOL e USDT
        for symbol in all_futures:
            if 'SOL' in symbol.upper() and 'USDT' in symbol.upper():
                st.success(f"✅ Simbolo generico trovato: {symbol}")
                return symbol
        
        # Cerca simboli generici con SOL
        for symbol in all_futures:
            if 'SOL' in symbol.upper():
                st.success(f"✅ Simbolo SOL generico: {symbol}")
                return symbol
        
        # Se non trovato, usa un formato generico
        st.warning("⚠️ Uso formato generico: SOL/USDT")
        return "SOL/USDT"

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
        st.session_state.arb_size = 100.0
    
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
    
    # Input per la size in USDT con minimo 100
    usdt_amount = st.number_input(
        "Importo USDT da utilizzare", 
        min_value=10.0, 
        value=st.session_state.arb_size if isinstance(st.session_state.arb_size, float) else 100.0,
        step=10.0,
        format="%.0f",
        help="Importo totale in USDT (minimo 10) che verrà diviso tra le due posizioni"
    )
    st.session_state.arb_size = usdt_amount
    
    # Calcola la size di SOL
    size_calculation = calculate_sol_size(usdt_amount)

    if not size_calculation["success"]:
        st.error(size_calculation["error"])
        st.stop()

    sol_size = size_calculation["sol_size"]
    calc_details = size_calculation["details"]

    # Riepilogo strategia
    st.subheader("📊 Riepilogo Strategia")

    # Mostra i calcoli
    with st.expander("🧮 Dettagli Calcolo", expanded=True):
        st.write(f"**USDT Totale:** {calc_details['usdt_total']} USDT")
        st.write(f"**USDT per posizione:** {calc_details['usdt_per_position']} USDT")
        st.write(f"**USDT con leva 5x:** {calc_details['usdt_leveraged']} USDT")
        st.write(f"**Prezzo SOL:** {calc_details['sol_price']} USDT")
        st.write(f"**SOL calcolato:** {calc_details['sol_quantity_raw']:.4f}")
        st.write(f"**SOL finale (arrotondato):** {calc_details['sol_size_final']} SOL")

    # Layout per il riepilogo
    recap_cols = st.columns(2)

    with recap_cols[0]:
        st.markdown(f"""
        **Operazione LONG su {exchange_long}**
        - Quantità: {sol_size} SOL
        - Valore: {calc_details['usdt_leveraged']:.2f} USDT (5x)
        - Capitale richiesto: {calc_details['usdt_per_position']:.2f} USDT
        - Tipo: Market
        """)

    with recap_cols[1]:
        st.markdown(f"""
        **Operazione SHORT su {exchange_short}**
        - Quantità: {sol_size} SOL  
        - Valore: {calc_details['usdt_leveraged']:.2f} USDT (5x)
        - Capitale richiesto: {calc_details['usdt_per_position']:.2f} USDT
        - Tipo: Market
        """)
    
    # Pulsante per eseguire la strategia (DEBUG MODE)
    if st.button("Start (DEBUG MODE)", type="primary", use_container_width=True):
        st.info("🔍 **MODALITÀ DEBUG ATTIVA** - Nessun ordine reale verrà inviato")
        
        # Verifica delle API key
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
        
        # Se le API key sono ok, procedi con il controllo capitale
        if not api_keys_missing:
            # Controllo capitale
            capital_check = check_capital_requirements(
                exchange_long, 
                exchange_short, 
                calc_details['usdt_per_position']
            )
            
            # Se il capitale è sufficiente, procedi con il resto dei test
            if capital_check["overall_success"]:
                st.write("### 📊 Dettagli Calcolo Size")
                st.json({
                    "step_1_divisione": f"{usdt_amount} USDT / 2 = {calc_details['usdt_per_position']} USDT",
                    "step_2_leva": f"{calc_details['usdt_per_position']} USDT * 5 = {calc_details['usdt_leveraged']} USDT",
                    "step_3_prezzo_sol": f"Prezzo SOL: {calc_details['sol_price']} USDT",
                    "step_4_conversione": f"{calc_details['usdt_leveraged']} USDT / {calc_details['sol_price']} = {calc_details['sol_quantity_raw']:.6f} SOL",
                    "step_5_arrotondamento": f"floor({calc_details['sol_quantity_raw']:.6f} * 10) / 10 = {calc_details['sol_size_final']} SOL"
                })
                
                with st.spinner("🔍 Test connessioni exchange e ricerca simboli..."):
                    # Inizializza API per i due exchange
                    exchange_id_long = exchange_long.lower()
                    exchange_id_short = exchange_short.lower()
                    
                    if exchange_long == "BitMEX":
                        exchange_id_long = "bitmex"
                    if exchange_short == "BitMEX":
                        exchange_id_short = "bitmex"
                    
                    st.write(f"### 🔗 Connessione Exchange")
                    st.write(f"- Exchange LONG: {exchange_long} (ID: {exchange_id_long})")
                    st.write(f"- Exchange SHORT: {exchange_short} (ID: {exchange_id_short})")
                    
                    # Creiamo le API
                    try:
                        api_long = CCXTAPI(exchange_id_long)
                        st.success(f"✅ Connessione a {exchange_long} riuscita")
                    except Exception as e:
                        st.error(f"❌ Errore connessione {exchange_long}: {str(e)}")
                        return
                    
                    try:
                        api_short = CCXTAPI(exchange_id_short)
                        st.success(f"✅ Connessione a {exchange_short} riuscita")
                    except Exception as e:
                        st.error(f"❌ Errore connessione {exchange_short}: {str(e)}")
                        return
                    
                    # Trova i contratti SOLANA su entrambi gli exchange
                    st.write("### 🔍 Ricerca Simboli SOLANA")
                    symbol_long = find_solana_contract(api_long, exchange_long)
                    symbol_short = find_solana_contract(api_short, exchange_short)
                    
                    # Mostra i simboli trovati
                    st.success(f"🎯 **Simboli identificati:**")
                    st.write(f"- LONG: `{symbol_long}` su {exchange_long}")
                    st.write(f"- SHORT: `{symbol_short}` su {exchange_short}")
                    
                    # Usa la size calcolata
                    sol_amount = sol_size
                    
                    st.write("### ⚙️ Adattamenti Exchange-Specifici")
                    
                    # Adattamenti specifici per exchange
                    # BitMEX ha moltiplicatore diverso per SOLUSDT
                    if exchange_long == "BitMEX":
                        st.write(f"🔧 **Adattamento BitMEX LONG:**")
                        st.write(f"- SOL originale: {sol_amount}")
                        # Per BitMEX, 1 SOL = 10000 contratti
                        adjusted_long_size = int(sol_amount * 10000)
                        st.write(f"- Moltiplicazione x10000: {adjusted_long_size}")
                        # Assicura che sia almeno 1000 contratti (minimo BitMEX per Solana)
                        adjusted_long_size = max(adjusted_long_size, 1000)
                        st.write(f"- Minimo 1000 applicato: {adjusted_long_size}")
                        # Arrotonda a 100 per Solana
                        adjusted_long_size = round(adjusted_long_size / 100) * 100
                        st.write(f"- Arrotondamento a 100: {adjusted_long_size}")
                        st.success(f"✅ LONG BitMEX finale: {adjusted_long_size} contratti")
                    else:
                        adjusted_long_size = sol_amount
                        st.write(f"✅ LONG {exchange_long}: {adjusted_long_size} SOL (nessun adattamento)")
                    
                    if exchange_short == "BitMEX":
                        st.write(f"🔧 **Adattamento BitMEX SHORT:**")
                        st.write(f"- SOL originale: {sol_amount}")
                        # Per BitMEX, 1 SOL = 10000 contratti, e short è negativo
                        adjusted_short_size = -int(sol_amount * 10000)
                        st.write(f"- Moltiplicazione x10000 + negativo: {adjusted_short_size}")
                        # Assicura che sia almeno 1000 contratti in valore assoluto
                        adjusted_short_size = min(adjusted_short_size, -1000)
                        st.write(f"- Minimo 1000 applicato: {adjusted_short_size}")
                        # Arrotonda a 100 per Solana (mantenendo il segno negativo)
                        adjusted_short_size = round(adjusted_short_size / 100) * 100
                        st.write(f"- Arrotondamento a 100: {adjusted_short_size}")
                        st.success(f"✅ SHORT BitMEX finale: {adjusted_short_size} contratti")
                    else:
                        adjusted_short_size = -sol_amount
                        st.write(f"✅ SHORT {exchange_short}: {adjusted_short_size} SOL (nessun adattamento)")
                    
                    # Parametri finali per gli ordini
                    st.write("### 📋 Parametri Ordini Finali")
                    order_params = {
                        "LONG": {
                            "exchange": exchange_long,
                            "symbol": symbol_long,
                            "amount": adjusted_long_size,
                            "type": "market"
                        },
                        "SHORT": {
                            "exchange": exchange_short,
                            "symbol": symbol_short,
                            "amount": adjusted_short_size,
                            "type": "market"
                        }
                    }
                    
                    st.json(order_params)
                    
                    # Simulazione invio ordini
                    st.write("### 🚀 Simulazione Invio Ordini")
                    st.info("🔍 **MODALITÀ DEBUG** - Ordini NON inviati realmente")
                    
                    st.write("**Ordine LONG:**")
                    st.code(f"api_long.submit_order(symbol='{symbol_long}', amount={adjusted_long_size}, market=True)")
                    
                    st.write("**Ordine SHORT:**")
                    st.code(f"api_short.submit_order(symbol='{symbol_short}', amount={adjusted_short_size}, market=True)")
                    
                    st.success("🎉 **CAPITALE VERIFICATO E DEBUG COMPLETATO**")
            else:
                st.error("❌ **Impossibile procedere: capitale insufficiente**")
    
    # Pulsante per gestire le posizioni (se esistono)
    if 'has_open_positions' in st.session_state and st.session_state['has_open_positions']:
        if st.button("Gestisci Posizioni", type="secondary", use_container_width=True):
            position_management_app()

def main():
    """Entry point principale della web app"""
    funding_arbitrage_app()

if __name__ == "__main__":
    main()