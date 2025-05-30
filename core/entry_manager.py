"""
Entry Manager - Gestione apertura posizioni iniziali (FASE 1)
Gestisce i controlli di entrata e l'apertura delle posizioni iniziali.
"""

import logging
import time
import uuid
import math
import os
from datetime import datetime, timezone
import sys
from dotenv import load_dotenv
from ccxt_api import CCXTAPI

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('entry_manager')

class EntryManager:
    def __init__(self, user_id, config, db, exchange):
        """
        Inizializza il gestore delle entrate
        
        Args:
            user_id: ID dell'utente
            config: Configurazione del bot
            db: Istanza di MongoManager
            exchange: Istanza di ExchangeManager
        """
        self.user_id = user_id
        self.config = config
        self.db = db
        self.exchange = exchange
        
        # Carica le variabili d'ambiente
        load_dotenv()
        
        logger.info(f"EntryManager inizializzato per l'utente {user_id}")
    
    def get_sol_price(self):
        """Ottiene il prezzo corrente di SOL da uno degli exchange"""
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
    
    def calculate_sol_size(self, usdt_amount):
        """
        Calcola la quantità di SOL da acquistare dato un importo in USDT
        
        Args:
            usdt_amount: Importo in USDT da investire
            
        Returns:
            dict: Risultato con il valore calcolato
        """
        half_usdt = usdt_amount / 2
        leveraged_usdt = half_usdt * 5
        sol_price = self.get_sol_price()
        
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
    
    def _bybit_internal_transfer(self, amount, from_wallet='funding', to_wallet='unified'):
        """Esegue un trasferimento interno su ByBit tra i wallet"""
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
    
    def _bitfinex_internal_transfer(self, amount, from_wallet='exchange', to_wallet='margin'):
        """Esegue un trasferimento interno su Bitfinex tra i wallet"""
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
    
    def find_solana_contract(self, api, exchange_name):
        """Trova il simbolo corretto per il contratto SOL su un exchange specifico"""
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
            for symbol in all_futures:
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
    
    def check_bitmex_balance(self, required_usdt):
        """Verifica se c'è sufficiente capitale su BitMEX"""
        try:
            api = CCXTAPI('bitmex')
            balance = api.exchange.fetch_balance()
            
            usdt_balance = balance.get('USDT', {}).get('free', 0)
            
            if usdt_balance >= required_usdt:
                logger.info(f"BitMEX: Saldo sufficiente ({usdt_balance} USDT)")
                return {
                    "success": True,
                    "available": usdt_balance,
                    "required": required_usdt,
                    "sufficient": True
                }
            else:
                logger.error(f"BitMEX: Saldo insufficiente ({usdt_balance} < {required_usdt} USDT)")
                return {
                    "success": False,
                    "available": usdt_balance,
                    "required": required_usdt,
                    "sufficient": False,
                    "error": f"Saldo insufficiente: {usdt_balance} USDT disponibili, {required_usdt} USDT richiesti"
                }
                
        except Exception as e:
            logger.error(f"Errore nel controllo saldo BitMEX: {str(e)}")
            return {
                "success": False,
                "error": f"Errore nel controllo saldo BitMEX: {str(e)}"
            }
    
    def check_bybit_balance(self, required_usdt):
        """Verifica se c'è sufficiente capitale su ByBit"""
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
            
            logger.info(f"Saldo ByBit: Unified: {unified_balance} USDT, Funding: {funding_balance} USDT")
            
            if unified_balance >= required_usdt:
                logger.info(f"ByBit: Saldo unified sufficiente ({unified_balance} USDT)")
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
                
                logger.warning(f"ByBit: Serve trasferimento da funding a unified ({transfer_amount} USDT)")
                
                if funding_balance < transfer_amount:
                    logger.error(f"Saldo funding insufficiente per il trasferimento: {funding_balance} < {transfer_amount}")
                    return {
                        "success": False,
                        "error": f"Saldo funding insufficiente: {funding_balance} USDT disponibili, {transfer_amount} USDT richiesti",
                        "funding_balance": funding_balance,
                        "transfer_amount": transfer_amount
                    }
                
                logger.info(f"Esecuzione trasferimento interno ByBit di {transfer_amount} USDT")
                
                transfer_result = self._bybit_internal_transfer(transfer_amount, 'funding', 'unified')
                
                if transfer_result['success']:
                    logger.info(f"Trasferimento completato con successo")
                    
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
                    logger.error(f"Errore trasferimento: {transfer_result['error']}")
                    return {
                        "success": False,
                        "error": transfer_result['error'],
                        "transfer_needed": True,
                        "transfer_completed": False,
                        "manual_action_required": True
                    }
            
            else:
                shortage = required_usdt - total_balance
                logger.error(f"ByBit: Saldo totale insufficiente (mancano {shortage} USDT)")
                return {
                    "success": False,
                    "unified_balance": unified_balance,
                    "funding_balance": funding_balance,
                    "total_balance": total_balance,
                    "required": required_usdt,
                    "shortage": shortage,
                    "sufficient": False,
                    "error": f"Saldo totale insufficiente: {total_balance} USDT disponibili, {required_usdt} USDT richiesti (mancano {shortage} USDT)"
                }
                
        except Exception as e:
            logger.error(f"Errore nel controllo saldo ByBit: {str(e)}")
            return {
                "success": False,
                "error": f"Errore nel controllo saldo ByBit: {str(e)}"
            }
    
    def check_bitfinex_balance(self, required_usdt):
        """Verifica se c'è sufficiente capitale su Bitfinex"""
        try:
            api = CCXTAPI('bitfinex')
            
            balance = api.exchange.fetch_balance()
            
            margin_balance = balance.get('margin', {}).get('USDT', {}).get('free', 0) or balance.get('margin', {}).get('UST', {}).get('free', 0)
            exchange_balance = balance.get('exchange', {}).get('USDT', {}).get('free', 0) or balance.get('exchange', {}).get('UST', {}).get('free', 0)
            funding_balance = balance.get('funding', {}).get('USDT', {}).get('free', 0) or balance.get('funding', {}).get('UST', {}).get('free', 0)
            
            # Gestisci il caso in cui margin/exchange non siano dizionari nidificati
            if margin_balance == 0:
                for currency in ['USDT', 'UST']:
                    if currency in balance:
                        for wallet_type in ['margin', 'exchange', 'funding']:
                            if wallet_type in balance[currency]:
                                wallet_balance = balance[currency][wallet_type].get('free', 0)
                                if wallet_type == 'margin':
                                    margin_balance = wallet_balance
                                elif wallet_type == 'exchange':
                                    exchange_balance = wallet_balance
                                elif wallet_type == 'funding':
                                    funding_balance = wallet_balance
            
            # Controlla anche eventuali wallet "swap"
            swap_balance = balance.get('swap', {}).get('USDT', {}).get('free', 0) or balance.get('swap', {}).get('UST', {}).get('free', 0)
            if swap_balance > 0:
                exchange_balance += swap_balance
            
            total_balance = margin_balance + exchange_balance + funding_balance
            
            logger.info(f"Saldo Bitfinex: Margin: {margin_balance} USDT, Exchange: {exchange_balance} USDT, Funding: {funding_balance} USDT")
            
            if margin_balance >= required_usdt:
                logger.info(f"Bitfinex: Saldo margin sufficiente ({margin_balance} USDT)")
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
            
            elif exchange_balance >= required_usdt:
                # Trasferimento da exchange a margin
                transfer_amount = required_usdt
                
                logger.warning(f"Bitfinex: Serve trasferimento da exchange a margin ({transfer_amount} USDT)")
                logger.info(f"Esecuzione trasferimento interno Bitfinex di {transfer_amount} USDT")
                
                transfer_result = self._bitfinex_internal_transfer(transfer_amount, 'exchange', 'margin')
                
                if transfer_result['success']:
                    logger.info(f"Trasferimento completato con successo")
                    
                    # Aggiorna i saldi dopo il trasferimento
                    return {
                        "success": True,
                        "margin_balance": margin_balance + transfer_amount,
                        "exchange_balance": exchange_balance - transfer_amount,
                        "funding_balance": funding_balance,
                        "total_balance": total_balance,
                        "required": required_usdt,
                        "transfer_needed": True,
                        "transfer_amount": transfer_amount,
                        "transfer_completed": True,
                        "sufficient": True,
                        "transfer_type": "exchange_to_margin"
                    }
                else:
                    logger.error(f"Errore trasferimento: {transfer_result['error']}")
                    return {
                        "success": False,
                        "error": transfer_result['error'],
                        "transfer_needed": True,
                        "transfer_completed": False,
                        "manual_action_required": True
                    }
            
            elif funding_balance >= required_usdt and exchange_balance < required_usdt and margin_balance < required_usdt:
                # In Bitfinex, non possiamo trasferire direttamente da funding a margin
                # Dobbiamo prima trasferire da funding a exchange, poi da exchange a margin
                transfer_amount = required_usdt
                
                logger.warning(f"Bitfinex: Servono due trasferimenti: funding -> exchange -> margin ({transfer_amount} USDT)")
                
                # Primo trasferimento: funding -> exchange
                funding_transfer = transfer_amount + 1  # Aggiungiamo un piccolo buffer
                logger.info(f"Trasferimento 1/2: funding → exchange ({funding_transfer} USDT)")
                
                transfer_result1 = self._bitfinex_internal_transfer(funding_transfer, 'funding', 'exchange')
                
                if not transfer_result1['success']:
                    logger.error(f"Errore primo trasferimento: {transfer_result1['error']}")
                    return {
                        "success": False,
                        "error": f"Errore nel primo trasferimento (funding -> exchange): {transfer_result1['error']}",
                        "transfer_needed": True,
                        "transfer_completed": False,
                        "manual_action_required": True,
                        "step": "funding_to_exchange"
                    }
                
                logger.info(f"Primo trasferimento completato con successo")
                
                # Attendi un breve periodo per il settlement
                logger.info("Attesa settlement (10 sec)")
                time.sleep(10)
                
                # Secondo trasferimento: exchange -> margin
                logger.info(f"Trasferimento 2/2: exchange → margin ({transfer_amount} USDT)")
                
                transfer_result2 = self._bitfinex_internal_transfer(transfer_amount, 'exchange', 'margin')
                
                if transfer_result2['success']:
                    logger.info(f"Secondo trasferimento completato con successo")
                    
                    # Aggiorna i saldi dopo i trasferimenti
                    return {
                        "success": True,
                        "margin_balance": margin_balance + transfer_amount,
                        "exchange_balance": exchange_balance + funding_transfer - transfer_amount,
                        "funding_balance": funding_balance - funding_transfer,
                        "total_balance": total_balance,
                        "required": required_usdt,
                        "transfer_needed": True,
                        "transfer_amount": transfer_amount,
                        "transfer_completed": True,
                        "sufficient": True,
                        "transfer_type": "funding_to_exchange_to_margin"
                    }
                else:
                    logger.error(f"Errore secondo trasferimento: {transfer_result2['error']}")
                    return {
                        "success": False,
                        "error": f"Errore nel secondo trasferimento (exchange -> margin): {transfer_result2['error']}",
                        "transfer_needed": True,
                        "transfer_completed": False,
                        "manual_action_required": True,
                        "step": "exchange_to_margin"
                    }
            
            elif total_balance >= required_usdt:
                # Combinazione di wallet
                pass  # Implementazione futura per gestire casi più complessi
            
            else:
                shortage = required_usdt - total_balance
                logger.error(f"Bitfinex: Saldo totale insufficiente (mancano {shortage} USDT)")
                return {
                    "success": False,
                    "margin_balance": margin_balance,
                    "exchange_balance": exchange_balance,
                    "funding_balance": funding_balance,
                    "total_balance": total_balance,
                    "required": required_usdt,
                    "shortage": shortage,
                    "sufficient": False,
                    "error": f"Saldo totale insufficiente: {total_balance} USDT disponibili, {required_usdt} USDT richiesti (mancano {shortage} USDT)"
                }
                
        except Exception as e:
            logger.error(f"Errore nel controllo saldo Bitfinex: {str(e)}")
            return {
                "success": False,
                "error": f"Errore nel controllo saldo Bitfinex: {str(e)}"
            }
    
    def check_capital_requirements(self, exchange_long, exchange_short, required_usdt_per_position):
        """
        Verifica che ci sia capitale sufficiente su entrambi gli exchange.
        
        Args:
            exchange_long: Exchange per la posizione long
            exchange_short: Exchange per la posizione short
            required_usdt_per_position: USDT richiesti per ciascuna posizione
            
        Returns:
            dict: Risultato delle verifiche
        """
        try:
            logger.info(f"Verifica capitale: {required_usdt_per_position} USDT per posizione")
            
            # Verifica capitale per long position
            long_check = {"success": False, "error": "Controllo non implementato"}
            
            if exchange_long.lower() == "bitmex":
                long_check = self.check_bitmex_balance(required_usdt_per_position)
            elif exchange_long.lower() == "bybit":
                long_check = self.check_bybit_balance(required_usdt_per_position)
            elif exchange_long.lower() == "bitfinex":
                long_check = self.check_bitfinex_balance(required_usdt_per_position)
            else:
                logger.warning(f"Controllo capitale per {exchange_long} non ancora implementato")
            
            # Verifica capitale per short position
            short_check = {"success": False, "error": "Controllo non implementato"}
            
            if exchange_short.lower() == "bitmex":
                short_check = self.check_bitmex_balance(required_usdt_per_position)
            elif exchange_short.lower() == "bybit":
                short_check = self.check_bybit_balance(required_usdt_per_position)
            elif exchange_short.lower() == "bitfinex":
                short_check = self.check_bitfinex_balance(required_usdt_per_position)
            else:
                logger.warning(f"Controllo capitale per {exchange_short} non ancora implementato")
            
            # Valuta risultati complessivi
            logger.info("Riepilogo Controllo Capitale")
            
            if long_check.get("success", False) and short_check.get("success", False):
                logger.info("Capitale sufficiente su entrambi gli exchange")
                return {"overall_success": True, "long_check": long_check, "short_check": short_check}
            else:
                logger.error("Capitale insufficiente o errori rilevati")
                
                if not long_check.get("success", False):
                    error_msg = long_check.get("error", "Errore sconosciuto")
                    logger.error(f"LONG ({exchange_long}): {error_msg}")
                
                if not short_check.get("success", False):
                    error_msg = short_check.get("error", "Errore sconosciuto")
                    logger.error(f"SHORT ({exchange_short}): {error_msg}")
                
                return {"overall_success": False, "long_check": long_check, "short_check": short_check}
                
        except Exception as e:
            logger.error(f"Errore nel controllo dei requisiti di capitale: {str(e)}")
            return {"overall_success": False, "error": str(e)}
    
    def open_initial_positions(self):
        """
        Apre le posizioni iniziali sugli exchange configurati.
        Esegue i controlli necessari (capitale sufficiente) e apre le posizioni.
        """
        logger.info(f"Apertura posizioni iniziali per l'utente {self.user_id}")
        
        # Estrai i parametri dalla configurazione
        symbol = self.config["parameters"]["symbol"]
        position_size = self.config["parameters"]["amount"]
        exchanges = self.config["exchanges"]
        
        # Verifica che ci siano almeno due exchange configurati
        if len(exchanges) < 2:
            logger.error("Configurazione non valida: sono necessari almeno 2 exchange")
            return {"success": False, "error": "Sono necessari almeno 2 exchange"}
        
        # Verifica se ci sono già posizioni aperte
        existing_positions = self._check_existing_positions()
        if existing_positions["has_positions"]:
            logger.info(f"Posizioni già aperte: {existing_positions['count']} trovate")
            return {"success": True, "already_open": True, "positions": existing_positions["positions"]}
        
        exchange_long = exchanges[0]
        exchange_short = exchanges[1]
        
        # Verifica API keys
        if not (os.getenv(f"{exchange_long.upper()}_API_KEY") and os.getenv(f"{exchange_long.upper()}_API_SECRET")):
            logger.error(f"API Key e Secret per {exchange_long} non configurati")
            return {"success": False, "error": f"API Key e Secret per {exchange_long} non configurati"}
        
        if not (os.getenv(f"{exchange_short.upper()}_API_KEY") and os.getenv(f"{exchange_short.upper()}_API_SECRET")):
            logger.error(f"API Key e Secret per {exchange_short} non configurati")
            return {"success": False, "error": f"API Key e Secret per {exchange_short} non configurati"}
        
        # Calcola la size SOL
        sol_info = self.calculate_sol_size(position_size)
        if not sol_info["success"]:
            logger.error(f"Errore nel calcolo della size SOL: {sol_info['error']}")
            return {"success": False, "error": sol_info["error"]}
        
        sol_size = sol_info["sol_size"]
        
        # Inizializza le API per ciascun exchange
        try:
            exchange_id_long = normalize_exchange_id(exchange_long)
            exchange_id_short = normalize_exchange_id(exchange_short)
            
            api_long = CCXTAPI(exchange_id_long)
            api_short = CCXTAPI(exchange_id_short)
            
            # Trova i simboli corretti per SOL su ciascun exchange
            symbol_long = self.find_solana_contract(api_long, exchange_long)
            symbol_short = self.find_solana_contract(api_short, exchange_short)
            
            logger.info(f"Simboli identificati: LONG={symbol_long} su {exchange_long}, SHORT={symbol_short} su {exchange_short}")
            
            # Adatta la size in base all'exchange
            if exchange_long == "BitMEX":
                adjusted_long_size = int(sol_size * 10000)
                adjusted_long_size = max(adjusted_long_size, 1000)
                adjusted_long_size = round(adjusted_long_size / 100) * 100
                logger.info(f"Conversione LONG BitMEX: {sol_size} SOL → {adjusted_long_size} contratti")
            else:
                adjusted_long_size = sol_size
            
            if exchange_short == "BitMEX":
                adjusted_short_size = -int(sol_size * 10000)
                adjusted_short_size = min(adjusted_short_size, -1000)
                adjusted_short_size = round(adjusted_short_size / 100) * 100
                logger.info(f"Conversione SHORT BitMEX: {sol_size} SOL → {abs(adjusted_short_size)} contratti")
            else:
                adjusted_short_size = -sol_size
            
            # Esegui gli ordini
            positions = []
            
            try:
                # Ordine LONG
                long_order = api_long.submit_order(
                    symbol=symbol_long,
                    amount=adjusted_long_size,
                    price=None,  # Market order
                    market=True
                )
                
                logger.info(f"Ordine LONG inviato con successo: {long_order}")
                
                # Salva informazioni posizione LONG
                long_position = {
                    "position_id": long_order.get('id', str(uuid.uuid4())),
                    "user_id": self.user_id,
                    "exchange": exchange_long,
                    "symbol": symbol_long,
                    "side": "long",
                    "size": adjusted_long_size,
                    "details": long_order
                }
                
                positions.append(long_position)
                if self.db:
                    self._save_position_to_db(long_position)
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Errore nell'invio dell'ordine LONG: {error_msg}")
                
                if exchange_long == "BitMEX" and "insufficient available balance" in error_msg.lower():
                    return {"success": False, "error": f"Saldo insufficiente su BitMEX per aprire la posizione LONG"}
                
                return {"success": False, "error": f"Errore nell'invio dell'ordine LONG: {error_msg}"}
            
            try:
                # Ordine SHORT
                short_order = api_short.submit_order(
                    symbol=symbol_short,
                    amount=adjusted_short_size,
                    price=None,  # Market order
                    market=True
                )
                
                logger.info(f"Ordine SHORT inviato con successo: {short_order}")
                
                # Salva informazioni posizione SHORT
                short_position = {
                    "position_id": short_order.get('id', str(uuid.uuid4())),
                    "user_id": self.user_id,
                    "exchange": exchange_short,
                    "symbol": symbol_short,
                    "side": "short",
                    "size": abs(adjusted_short_size),
                    "details": short_order
                }
                
                positions.append(short_position)
                if self.db:
                    self._save_position_to_db(short_position)
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Errore nell'invio dell'ordine SHORT: {error_msg}")
                
                # Se l'ordine SHORT fallisce, prova a chiudere anche la posizione LONG
                try:
                    logger.warning("Tentativo di chiusura posizione LONG dopo fallimento SHORT")
                    api_long.close_position(symbol_long)
                except Exception as close_error:
                    logger.error(f"Errore anche nella chiusura della posizione LONG: {str(close_error)}")
                
                if exchange_short == "BitMEX" and "insufficient available balance" in error_msg.lower():
                    return {"success": False, "error": f"Saldo insufficiente su BitMEX per aprire la posizione SHORT"}
                
                return {
                    "success": False, 
                    "error": f"Errore nell'invio dell'ordine SHORT: {error_msg}",
                    "note": "L'ordine LONG è stato eseguito ma si è tentato di chiuderlo"
                }
            
            # Operazione completata con successo
            return {
                "success": True,
                "positions": positions,
                "details": {
                    "sol_size": sol_size,
                    "long_exchange": exchange_long,
                    "short_exchange": exchange_short,
                    "long_symbol": symbol_long,
                    "short_symbol": symbol_short,
                    "adjusted_long_size": adjusted_long_size,
                    "adjusted_short_size": adjusted_short_size
                }
            }
            
        except Exception as e:
            logger.error(f"Errore generale nell'apertura delle posizioni: {str(e)}")
            return {"success": False, "error": f"Errore generale: {str(e)}"}
    
    def _check_existing_positions(self):
        """Verifica se ci sono già posizioni aperte per questo utente"""
        try:
            # Se abbiamo un database, verifica le posizioni lì
            if self.db:
                positions = self.db.get_user_positions(self.user_id)
                if positions:
                    return {
                        "has_positions": True, 
                        "count": len(positions),
                        "positions": positions
                    }
            
            # Altrimenti verifica posizioni direttamente sugli exchange
            positions = []
            exchanges = self.config["exchanges"]
            
            for exchange_name in exchanges:
                try:
                    exchange_id = normalize_exchange_id(exchange_name)
                    api = CCXTAPI(exchange_id)
                    exchange_positions = api.get_open_positions()
                    
                    if exchange_positions and len(exchange_positions) > 0:
                        for pos in exchange_positions:
                            # Aggiungi informazioni sull'exchange
                            pos["exchange"] = exchange_name
                            positions.append(pos)
                except Exception as e:
                    logger.warning(f"Impossibile recuperare posizioni da {exchange_name}: {str(e)}")
            
            if positions:
                return {
                    "has_positions": True,
                    "count": len(positions),
                    "positions": positions
                }
            
            return {"has_positions": False, "count": 0, "positions": []}
            
        except Exception as e:
            logger.error(f"Errore nel controllo delle posizioni esistenti: {str(e)}")
            return {"has_positions": False, "count": 0, "positions": []}
    
    def _save_position_to_db(self, position_data):
        """Salva una posizione nel database"""
        try:
            if not self.db:
                logger.warning("Database non disponibile, impossibile salvare la posizione")
                return False
                
            position_doc = {
                "position_id": position_data["position_id"],
                "user_id": self.user_id,
                "exchange": position_data["exchange"],
                "symbol": position_data["symbol"],
                "side": position_data["side"],
                "size": position_data["size"],
                "entry_price": position_data.get("details", {}).get("entryPrice", 0),
                "leverage": position_data.get("details", {}).get("leverage", 5),
                "margin_used": position_data.get("details", {}).get("positionMargin", 0),
                "current_price": position_data.get("details", {}).get("markPrice", 0),
                "timestamp": datetime.now(timezone.utc).timestamp(),
                "status": "open"
            }
            
            self.db.save_position(position_doc)
            logger.info(f"Posizione salvata nel database: {position_data['position_id']}")
            return True
            
        except Exception as e:
            logger.error(f"Errore nel salvataggio della posizione: {str(e)}")
            return False

# Funzione di utilità per normalizzare ID exchange
def normalize_exchange_id(exchange_name):
    """Converte il nome dell'exchange nel formato CCXT corrispondente"""
    if exchange_name == "BitMEX":
        return "bitmex"
    else:
        return exchange_name.lower() 