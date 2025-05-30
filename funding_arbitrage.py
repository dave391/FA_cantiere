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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('funding_arbitrage')

load_dotenv()

def get_sol_price():
    try:
        api = CCXTAPI('bybit')
        ticker = api.exchange.fetch_ticker('SOL/USDT')
        price = ticker['last']
        logger.info(f"Prezzo SOL ottenuto da ByBit: {price} USDT")
        return float(price)
    except Exception as e:
        logger.warning(f"Errore nel recupero prezzo da ByBit: {str(e)}")
        
        try:
            api = CCXTAPI('bitmex')
            ticker = api.exchange.fetch_ticker('SOLUSDT')
            price = ticker['last']
            logger.info(f"Prezzo SOL ottenuto da BitMEX: {price} USDT")
            return float(price)
        except Exception as e:
            logger.warning(f"Errore nel recupero prezzo da BitMEX: {str(e)}")
            
            estimated_price = 100.0
            logger.warning(f"Uso prezzo stimato: {estimated_price} USDT")
            return estimated_price

def calculate_sol_size(usdt_amount):
    half_usdt = usdt_amount / 2
    leveraged_usdt = half_usdt * 5
    sol_price = get_sol_price()
    
    if sol_price <= 0:
        return {
            "success": False,
            "error": "Impossibile ottenere il prezzo di SOLANA"
        }
    
    sol_quantity = leveraged_usdt / sol_price
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
    try:
        logger.info(f"Trasferimento interno ByBit: {amount} USDT da {from_wallet} a {to_wallet}")
        
        api = CCXTAPI('bybit')
        
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
            
            try:
                transfer_id = f"bybit_transfer_{int(time.time() * 1000)}"
                
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

def _bitfinex_internal_transfer(amount, from_wallet='exchange', to_wallet='margin'):
    try:
        logger.info(f"Trasferimento interno Bitfinex: {amount} USDT da {from_wallet} a {to_wallet}")
        
        actual_currency = "USTF0" if from_wallet == "margin" else "UST"
        actual_currency_to = "USTF0" if to_wallet == "margin" else "UST"
        
        api = CCXTAPI('bitfinex')
        
        params = {
            "from": from_wallet,
            "to": to_wallet,
            "currency": actual_currency,
            "amount": str(amount)
        }
        
        if actual_currency != actual_currency_to:
            params["currency_to"] = actual_currency_to
            logger.info(f"Conversione da {actual_currency} a {actual_currency_to}")
        
        try:
            if hasattr(api.exchange, 'privatePostAuthWTransfer'):
                result = api.exchange.privatePostAuthWTransfer(params)
                
                if result and isinstance(result, list) and len(result) > 0:
                    status = result[6] if len(result) > 6 else "UNKNOWN"
                    
                    if status == "SUCCESS":
                        return {
                            "success": True,
                            "message": f"Trasferimento interno Bitfinex di {amount} USDT da {from_wallet} a {to_wallet} completato con successo",
                            "transaction_id": result[2] if len(result) > 2 else None,
                            "info": result
                        }
                    else:
                        error_msg = result[7] if len(result) > 7 else "Errore sconosciuto"
                        return {
                            "success": False,
                            "error": f"Trasferimento interno Bitfinex fallito: {status} - {error_msg}",
                            "info": result
                        }
            else:
                raise Exception("Metodo privatePostAuthWTransfer non disponibile")
                
        except Exception as ccxt_error:
            logger.warning(f"Metodo CCXT fallito: {str(ccxt_error)}")
            
            try:
                from bitfinex_api import BitfinexAPI
                bitfinex_api = BitfinexAPI()
                
                result = bitfinex_api._make_request('POST', 'auth/w/transfer', True, None, params)
                
                if result and isinstance(result, list) and len(result) > 0:
                    status = result[6] if len(result) > 6 else "UNKNOWN"
                    
                    if status == "SUCCESS":
                        return {
                            "success": True,
                            "message": f"Trasferimento interno Bitfinex di {amount} USDT da {from_wallet} a {to_wallet} completato con successo (API nativa)",
                            "transaction_id": result[2] if len(result) > 2 else None,
                            "info": result
                        }
                    else:
                        error_msg = result[7] if len(result) > 7 else "Errore sconosciuto"
                        return {
                            "success": False,
                            "error": f"Trasferimento interno Bitfinex fallito (API nativa): {status} - {error_msg}",
                            "info": result
                        }
                else:
                    return {
                        "success": False,
                        "error": "Risposta API non valida (API nativa)",
                        "info": result
                    }
            except Exception as api_error:
                return {
                    "success": False,
                    "error": f"Tutti i metodi di trasferimento falliti. CCXT: {str(ccxt_error)}, API Nativa: {str(api_error)}"
                }
                
    except Exception as e:
        logger.error(f"Errore durante il trasferimento interno Bitfinex: {str(e)}")
        return {
            "success": False,
            "error": f"Errore durante il trasferimento interno Bitfinex: {str(e)}"
        }

def check_bitmex_balance(required_usdt):
    try:
        api = CCXTAPI('bitmex')
        balance = api.exchange.fetch_balance()
        
        usdt_balance = balance.get('USDT', {}).get('free', 0)
        
        if usdt_balance >= required_usdt:
            st.success(f"✅ BitMEX: Saldo sufficiente ({usdt_balance} USDT)")
            return {
                "success": True,
                "available": usdt_balance,
                "required": required_usdt,
                "sufficient": True
            }
        else:
            st.error(f"❌ BitMEX: Saldo insufficiente ({usdt_balance} < {required_usdt} USDT)")
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
    try:
        api = CCXTAPI('bybit')
        
        balance = api.exchange.fetch_balance()
        
        unified_balance = 0
        funding_balance = 0
        
        if 'unified' in balance:
            unified_balance = balance['unified'].get('USDT', {}).get('free', 0)
        elif 'USDT' in balance:
            unified_balance = balance['USDT'].get('free', 0)
        
        try:
            funding_balance_ccxt = api.exchange.fetch_balance({'type': 'funding'})
            if 'USDT' in funding_balance_ccxt:
                funding_balance = funding_balance_ccxt['USDT'].get('free', 0)
        except Exception:
            pass
        
        if funding_balance == 0:
            try:
                funding_params = {'accountType': 'FUND'}
                funding_balance_direct = api.exchange.fetchBalance(funding_params)
                if 'USDT' in funding_balance_direct:
                    funding_balance = funding_balance_direct['USDT'].get('free', 0)
            except Exception:
                pass
        
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
                                break
            except Exception:
                pass
        
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
                            break
            except Exception:
                pass
        
        if funding_balance == 0:
            try:
                all_balances = api.exchange.private_get_v5_account_wallet_balance({})
                
                if all_balances and 'result' in all_balances:
                    for account in all_balances['result'].get('list', []):
                        account_type = account.get('accountType', '')
                        
                        for coin in account.get('coin', []):
                            coin_name = coin.get('coin', '')
                            wallet_balance = float(coin.get('walletBalance', 0))
                            
                            if coin_name == 'USDT' and wallet_balance > 0:
                                if account_type == 'FUND':
                                    funding_balance = wallet_balance
            except Exception:
                pass
        
        total_balance = unified_balance + funding_balance
        
        st.write(f"**Saldo ByBit:** Unified: {unified_balance} USDT, Funding: {funding_balance} USDT")
        
        if unified_balance >= required_usdt:
            st.success(f"✅ ByBit: Saldo unified sufficiente ({unified_balance} USDT)")
            return {
                "success": True,
                "unified_balance": unified_balance,
                "funding_balance": funding_balance,
                "total_balance": total_balance,
                "required": required_usdt,
                "transfer_needed": False,
                "sufficient": True
            }
        
        elif total_balance >= required_usdt:
            raw_transfer_amount = required_usdt - unified_balance
            
            if unified_balance < 0.01:
                transfer_amount = required_usdt
            else:
                transfer_amount = round(raw_transfer_amount, 2)
            
            st.warning(f"⚠️ ByBit: Serve trasferimento da funding a unified ({transfer_amount} USDT)")
            
            if funding_balance < transfer_amount:
                st.error(f"❌ Saldo funding insufficiente per il trasferimento: {funding_balance} < {transfer_amount}")
                return {
                    "success": False,
                    "error": f"Saldo funding insufficiente: {funding_balance} USDT disponibili, {transfer_amount} USDT richiesti",
                    "funding_balance": funding_balance,
                    "transfer_amount": transfer_amount
                }
            
            st.write(f"🔄 Esecuzione trasferimento interno ByBit di {transfer_amount} USDT")
            
            transfer_result = _bybit_internal_transfer(transfer_amount, 'funding', 'unified')
            
            if transfer_result['success']:
                st.success(f"✅ Trasferimento completato")
                
                time.sleep(3)
                new_balance = api.exchange.fetch_balance()
                new_unified = new_balance.get('USDT', {}).get('free', 0)
                if 'unified' in new_balance:
                    new_unified = new_balance['unified'].get('USDT', {}).get('free', 0)
                
                if new_unified == 0:
                    new_unified = unified_balance + transfer_amount
                
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

def check_bitfinex_balance(required_usdt):
    try:
        api = CCXTAPI('bitfinex')
        
        balance = api.exchange.fetch_balance()
        
        margin_balance = 0
        exchange_balance = 0
        funding_balance = 0
        
        if 'margin' in balance:
            margin_balance = balance['margin'].get('USTF0', {}).get('free', 0)
            if margin_balance == 0:
                margin_balance = balance['margin'].get('USDT', {}).get('free', 0)
        
        if 'exchange' in balance:
            exchange_balance = balance['exchange'].get('UST', {}).get('free', 0)
            if exchange_balance == 0:
                exchange_balance = balance['exchange'].get('USDT', {}).get('free', 0)
        
        if 'funding' in balance:
            funding_balance = balance['funding'].get('UST', {}).get('free', 0)
            if funding_balance == 0:
                funding_balance = balance['funding'].get('USDT', {}).get('free', 0)
        
        if 'info' in balance:
            for wallet_info in balance['info']:
                if len(wallet_info) >= 3:
                    wallet_type = wallet_info[0]
                    currency = wallet_info[1]
                    balance_amount = float(wallet_info[2])
                    
                    if wallet_type == 'margin' and (currency == 'USTF0' or currency == 'USDT') and balance_amount > 0:
                        margin_balance = balance_amount
                    
                    if wallet_type == 'exchange' and (currency == 'UST' or currency == 'USDT') and balance_amount > 0:
                        exchange_balance = balance_amount
                        
                    if wallet_type == 'funding' and (currency == 'UST' or currency == 'USDT') and balance_amount > 0:
                        funding_balance = balance_amount
        
        total_balance = margin_balance + exchange_balance + funding_balance
        
        st.write(f"**Saldo Bitfinex:** Margin: {margin_balance} USDT, Exchange: {exchange_balance} USDT, Funding: {funding_balance} USDT")
        
        if margin_balance >= required_usdt:
            st.success(f"✅ Bitfinex: Saldo margin sufficiente ({margin_balance} USDT)")
            return {
                "success": True,
                "margin_balance": margin_balance,
                "exchange_balance": exchange_balance,
                "funding_balance": funding_balance,
                "total_balance": total_balance,
                "required": required_usdt,
                "transfer_needed": False,
                "sufficient": True
            }
        
        elif exchange_balance >= (required_usdt - margin_balance):
            raw_transfer_amount = required_usdt - margin_balance
            
            if margin_balance < 0.01:
                transfer_amount = required_usdt
            else:
                transfer_amount = round(raw_transfer_amount, 2)
            
            st.warning(f"⚠️ Bitfinex: Serve trasferimento da exchange a margin ({transfer_amount} USDT)")
            
            st.write(f"🔄 Esecuzione trasferimento interno Bitfinex di {transfer_amount} USDT")
            
            transfer_result = _bitfinex_internal_transfer(transfer_amount, 'exchange', 'margin')
            
            if transfer_result['success']:
                st.success(f"✅ Trasferimento completato")
                
                time.sleep(3)
                new_balance = api.exchange.fetch_balance()
                
                new_margin = 0
                if 'margin' in new_balance:
                    new_margin = new_balance['margin'].get('USTF0', {}).get('free', 0)
                    if new_margin == 0:
                        new_margin = new_balance['margin'].get('USDT', {}).get('free', 0)
                
                if new_margin == 0:
                    new_margin = margin_balance + transfer_amount
                
                return {
                    "success": True,
                    "margin_balance": new_margin,
                    "exchange_balance": exchange_balance - transfer_amount,
                    "funding_balance": funding_balance,
                    "total_balance": total_balance,
                    "required": required_usdt,
                    "transfer_needed": True,
                    "transfer_amount": transfer_amount,
                    "transfer_completed": True,
                    "sufficient": True
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
        
        elif funding_balance >= (required_usdt - margin_balance) and exchange_balance + funding_balance >= (required_usdt - margin_balance):
            raw_transfer_amount = required_usdt - margin_balance
            
            if margin_balance < 0.01:
                transfer_amount = required_usdt
            else:
                transfer_amount = round(raw_transfer_amount, 2)
                
            st.warning(f"⚠️ Bitfinex: Servono due trasferimenti: funding -> exchange -> margin ({transfer_amount} USDT)")
            
            funding_transfer = min(transfer_amount, funding_balance)
            funding_transfer = round(funding_transfer, 2)
            
            st.write(f"🔄 Trasferimento 1/2: funding → exchange ({funding_transfer} USDT)")
            
            transfer_result1 = _bitfinex_internal_transfer(funding_transfer, 'funding', 'exchange')
            
            if not transfer_result1['success']:
                st.error(f"❌ {transfer_result1['error']}")
                return {
                    "success": False,
                    "error": transfer_result1['error'],
                    "step": "funding_to_exchange",
                    "transfer_needed": True,
                    "transfer_completed": False,
                    "manual_action_required": True
                }
            
            st.success(f"✅ Primo trasferimento completato")
            
            st.info("⏱️ Attesa settlement (10 sec)")
            time.sleep(10)
            
            exchange_balance += funding_transfer
            funding_balance -= funding_transfer
            
            st.write(f"🔄 Trasferimento 2/2: exchange → margin ({transfer_amount} USDT)")
            
            transfer_result2 = _bitfinex_internal_transfer(transfer_amount, 'exchange', 'margin')
            
            if transfer_result2['success']:
                st.success(f"✅ Secondo trasferimento completato")
                
                time.sleep(3)
                new_balance = api.exchange.fetch_balance()
                
                new_margin = 0
                if 'margin' in new_balance:
                    new_margin = new_balance['margin'].get('USTF0', {}).get('free', 0)
                    if new_margin == 0:
                        new_margin = new_balance['margin'].get('USDT', {}).get('free', 0)
                
                if new_margin == 0:
                    new_margin = margin_balance + transfer_amount
                
                return {
                    "success": True,
                    "margin_balance": new_margin,
                    "exchange_balance": exchange_balance - transfer_amount,
                    "funding_balance": funding_balance,
                    "total_balance": total_balance,
                    "required": required_usdt,
                    "transfer_needed": True,
                    "transfer_amount": transfer_amount,
                    "transfer_completed": True,
                    "sufficient": True
                }
            else:
                st.error(f"❌ {transfer_result2['error']}")
                return {
                    "success": False,
                    "error": transfer_result2['error'],
                    "step": "exchange_to_margin",
                    "transfer_needed": True,
                    "transfer_completed": False,
                    "manual_action_required": True
                }
        
        else:
            shortage = required_usdt - total_balance
            st.error(f"❌ Bitfinex: Saldo totale insufficiente (mancano {shortage} USDT)")
            return {
                "success": False,
                "margin_balance": margin_balance,
                "exchange_balance": exchange_balance,
                "funding_balance": funding_balance,
                "total_balance": total_balance,
                "required": required_usdt,
                "sufficient": False,
                "shortage": shortage,
                "error": f"Saldo insufficiente: {total_balance} USDT totali, {required_usdt} USDT richiesti"
           }
           
    except Exception as e:
        st.error(f"❌ Errore nel controllo saldo Bitfinex: {str(e)}")
        return {
            "success": False,
            "error": f"Errore nel controllo saldo Bitfinex: {str(e)}"
        }

def check_capital_requirements(exchange_long, exchange_short, required_usdt_per_position):
   results = {
       "long_exchange": {"name": exchange_long, "check": None},
       "short_exchange": {"name": exchange_short, "check": None},
       "overall_success": False
   }
   
   if exchange_long == "BitMEX":
       results["long_exchange"]["check"] = check_bitmex_balance(required_usdt_per_position)
   elif exchange_long == "ByBit":
       results["long_exchange"]["check"] = check_bybit_balance(required_usdt_per_position)
   elif exchange_long == "Bitfinex":
       results["long_exchange"]["check"] = check_bitfinex_balance(required_usdt_per_position)
   else:
       st.warning(f"⚠️ Controllo capitale per {exchange_long} non ancora implementato")
       results["long_exchange"]["check"] = {"success": False, "error": "Exchange non supportato"}
   
   if exchange_short == "BitMEX":
       results["short_exchange"]["check"] = check_bitmex_balance(required_usdt_per_position)
   elif exchange_short == "ByBit":
       results["short_exchange"]["check"] = check_bybit_balance(required_usdt_per_position)
   elif exchange_short == "Bitfinex":
       results["short_exchange"]["check"] = check_bitfinex_balance(required_usdt_per_position)
   else:
       st.warning(f"⚠️ Controllo capitale per {exchange_short} non ancora implementato")
       results["short_exchange"]["check"] = {"success": False, "error": "Exchange non supportato"}
   
   long_ok = results["long_exchange"]["check"].get("success", False)
   short_ok = results["short_exchange"]["check"].get("success", False)
   
   results["overall_success"] = long_ok and short_ok
   
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

def funding_arbitrage_app():
   st.title("Funding Arbitrage Strategy")
   
   if 'arb_exchange_long' not in st.session_state:
       st.session_state.arb_exchange_long = "BitMEX"
   if 'arb_exchange_short' not in st.session_state:
       st.session_state.arb_exchange_short = "ByBit"
   if 'arb_size' not in st.session_state:
       st.session_state.arb_size = 100.0
   
   if 'exchange_long_select' not in st.session_state:
       st.session_state.exchange_long_select = st.session_state.arb_exchange_long
   if 'exchange_short_select' not in st.session_state:
       st.session_state.exchange_short_select = st.session_state.arb_exchange_short
   
   def on_long_exchange_change():
       st.session_state.arb_exchange_long = st.session_state.exchange_long_select
   
   def on_short_exchange_change():
       st.session_state.arb_exchange_short = st.session_state.exchange_short_select
   
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
   
   if exchange_long == exchange_short:
       st.warning("⚠️ Per una strategia di arbitraggio ottimale, è consigliabile scegliere exchange differenti.")
   
   st.subheader("⚙️ Parametri Strategia")
   
   usdt_amount = st.number_input(
       "Importo USDT da utilizzare", 
       min_value=10.0, 
       value=st.session_state.arb_size if isinstance(st.session_state.arb_size, float) else 100.0,
       step=10.0,
       format="%.0f",
       help="Importo totale in USDT (minimo 10) che verrà diviso tra le due posizioni"
   )
   st.session_state.arb_size = usdt_amount
   
   size_calculation = calculate_sol_size(usdt_amount)

   if not size_calculation["success"]:
       st.error(size_calculation["error"])
       st.stop()

   sol_size = size_calculation["sol_size"]
   calc_details = size_calculation["details"]

   with st.expander("🧮 Dettagli Calcolo", expanded=True):
       st.write(f"**USDT Totale:** {calc_details['usdt_total']} USDT")
       st.write(f"**USDT per posizione:** {calc_details['usdt_per_position']} USDT")
       st.write(f"**USDT con leva 5x:** {calc_details['usdt_leveraged']} USDT")
       st.write(f"**Prezzo SOL:** {calc_details['sol_price']} USDT")
       st.write(f"**SOL calcolato:** {calc_details['sol_quantity_raw']:.4f}")
       st.write(f"**SOL finale (arrotondato):** {calc_details['sol_size_final']} SOL")
   
   if st.button("Esegui Ordini", type="primary", use_container_width=True):
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
       
       if not api_keys_missing:
           capital_check = check_capital_requirements(
               exchange_long, 
               exchange_short, 
               calc_details['usdt_per_position']
           )
           
           if capital_check["overall_success"]:
               with st.spinner("🔄 Connessione agli exchange e preparazione ordini..."):
                   exchange_id_long = exchange_long.lower()
                   exchange_id_short = exchange_short.lower()
                   
                   if exchange_long == "BitMEX":
                       exchange_id_long = "bitmex"
                   if exchange_short == "BitMEX":
                       exchange_id_short = "bitmex"
                   
                   try:
                       api_long = CCXTAPI(exchange_id_long)
                   except Exception as e:
                       st.error(f"❌ Errore connessione {exchange_long}: {str(e)}")
                       return
                   
                   try:
                       api_short = CCXTAPI(exchange_id_short)
                   except Exception as e:
                       st.error(f"❌ Errore connessione {exchange_short}: {str(e)}")
                       return
                   
                   st.write("### 🔍 Ricerca Simboli SOLANA")
                   symbol_long = find_solana_contract(api_long, exchange_long)
                   symbol_short = find_solana_contract(api_short, exchange_short)
                   
                   st.success(f"🎯 **Simboli identificati:**")
                   st.write(f"- LONG: `{symbol_long}` su {exchange_long}")
                   st.write(f"- SHORT: `{symbol_short}` su {exchange_short}")
                   
                   sol_amount = sol_size
                   
                   # Adattamento BitMEX per LONG
                   if exchange_long == "BitMEX":
                       adjusted_long_size = int(sol_amount * 10000)
                       adjusted_long_size = max(adjusted_long_size, 1000)
                       adjusted_long_size = round(adjusted_long_size / 100) * 100
                       logger.info(f"Conversione LONG BitMEX: {sol_amount} SOL → {adjusted_long_size} contratti (moltiplicatore: 10000)")
                   else:
                       adjusted_long_size = sol_amount
                   
                   # Adattamento BitMEX per SHORT
                   if exchange_short == "BitMEX":
                       adjusted_short_size = -int(sol_amount * 10000)
                       adjusted_short_size = min(adjusted_short_size, -1000)
                       adjusted_short_size = round(adjusted_short_size / 100) * 100
                       logger.info(f"Conversione SHORT BitMEX: {sol_amount} SOL → {abs(adjusted_short_size)} contratti (moltiplicatore: 10000)")
                   else:
                       adjusted_short_size = -sol_amount
                   
                   # Imposta il tipo di ordine (market in questo caso)
                   is_market = True
                   price_long = None
                   price_short = None
                   
                   st.write("### 🚀 Invio Ordini")
                   
                   # Logging dei parametri degli ordini
                   logger.info(f"Invio ordine LONG su {exchange_long}: symbol={symbol_long}, amount={adjusted_long_size}, price={price_long}, market={is_market}")
                   logger.info(f"Invio ordine SHORT su {exchange_short}: symbol={symbol_short}, amount={adjusted_short_size}, price={price_short}, market={is_market}")
                   
                   try:
                       # Ordine LONG - logica semplificata come in esempio.py
                       long_order = api_long.submit_order(
                           symbol=symbol_long,
                           amount=adjusted_long_size,
                           price=price_long,
                           market=is_market
                       )
                       logger.info(f"Ordine LONG inviato con successo: {long_order}")
                       st.success(f"✅ Ordine LONG inviato con successo su {exchange_long}")
                       st.write(f"Dettagli: ID={long_order.get('id', 'N/A')}, Stato={long_order.get('status', 'N/A')}")
                   except Exception as e:
                       error_msg = str(e)
                       logger.error(f"Errore nell'invio dell'ordine LONG: {error_msg}")
                       
                       # Log dettagliato per errori BitMEX
                       if exchange_long == "BitMEX":
                           logger.error(f"Dettagli errore BitMEX LONG:")
                           logger.error(f"- Simbolo: {symbol_long}")
                           logger.error(f"- Quantità: {adjusted_long_size}")
                           logger.error(f"- Tipo: {'Market' if is_market else 'Limit'}")
                           
                           if "insufficient available balance" in error_msg.lower():
                               st.error(f"❌ Saldo insufficiente su BitMEX per aprire la posizione LONG")
                           elif "invalid qty" in error_msg.lower():
                               st.error(f"❌ Quantità non valida per BitMEX: {adjusted_long_size}")
                           elif "invalid price" in error_msg.lower():
                               st.error(f"❌ Prezzo non valido per BitMEX")
                           elif "invalid symbol" in error_msg.lower():
                               st.error(f"❌ Simbolo non valido per BitMEX: {symbol_long}")
                           else:
                               st.error(f"❌ Errore nell'invio dell'ordine LONG su BitMEX: {error_msg}")
                       else:
                           st.error(f"❌ Errore nell'invio dell'ordine LONG: {error_msg}")
                       return
                   
                   try:
                       # Ordine SHORT - logica semplificata come in esempio.py
                       short_order = api_short.submit_order(
                           symbol=symbol_short,
                           amount=adjusted_short_size,
                           price=price_short,
                           market=is_market
                       )
                       logger.info(f"Ordine SHORT inviato con successo: {short_order}")
                       st.success(f"✅ Ordine SHORT inviato con successo su {exchange_short}")
                       st.write(f"Dettagli: ID={short_order.get('id', 'N/A')}, Stato={short_order.get('status', 'N/A')}")
                   except Exception as e:
                       error_msg = str(e)
                       logger.error(f"Errore nell'invio dell'ordine SHORT: {error_msg}")
                       
                       # Log dettagliato per errori BitMEX
                       if exchange_short == "BitMEX":
                           logger.error(f"Dettagli errore BitMEX SHORT:")
                           logger.error(f"- Simbolo: {symbol_short}")
                           logger.error(f"- Quantità: {adjusted_short_size}")
                           logger.error(f"- Tipo: {'Market' if is_market else 'Limit'}")
                           
                           if "insufficient available balance" in error_msg.lower():
                               st.error(f"❌ Saldo insufficiente su BitMEX per aprire la posizione SHORT")
                           elif "invalid qty" in error_msg.lower():
                               st.error(f"❌ Quantità non valida per BitMEX: {adjusted_short_size}")
                           elif "invalid price" in error_msg.lower():
                               st.error(f"❌ Prezzo non valido per BitMEX")
                           elif "invalid symbol" in error_msg.lower():
                               st.error(f"❌ Simbolo non valido per BitMEX: {symbol_short}")
                           else:
                               st.error(f"❌ Errore nell'invio dell'ordine SHORT su BitMEX: {error_msg}")
                       else:
                           st.error(f"❌ Errore nell'invio dell'ordine SHORT: {error_msg}")
                       
                       st.warning("⚠️ L'ordine LONG è stato eseguito ma l'ordine SHORT è fallito.")
                       return
                   
                   st.session_state['has_open_positions'] = True
                   st.success("🎉 **Operazione di Arbitraggio Completata con Successo**")
           else:
               st.error("❌ **Impossibile procedere: capitale insufficiente**")
   
   if 'has_open_positions' in st.session_state and st.session_state['has_open_positions']:
       if st.button("Gestisci Posizioni", type="secondary", use_container_width=True):
           position_management_app()

def main():
   funding_arbitrage_app()

if __name__ == "__main__":
   main()
