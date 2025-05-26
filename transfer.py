"""
Transfer API - Gestione trasferimenti tra exchange usando CCXT
Data: 15/05/2025
"""

import os
from dotenv import load_dotenv
import logging
import requests
from ccxt_api import CCXTAPI

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('transfer_api')

class TransferAPI:
    def __init__(self):
        # Forza il ricaricamento delle variabili d'ambiente
        load_dotenv(override=True)
        
        # Verifica che le API keys siano state caricate correttamente
        bybit_key = os.getenv('BYBIT_API_KEY')
        bybit_secret = os.getenv('BYBIT_API_SECRET')
        bitmex_key = os.getenv('BITMEX_API_KEY')
        bitmex_secret = os.getenv('BITMEX_API_SECRET')
        bitfinex_key = os.getenv('BITFINEX_API_KEY')
        bitfinex_secret = os.getenv('BITFINEX_API_SECRET')
        
        logger.info(f"API keys caricate: ByBit {'OK' if bybit_key and bybit_secret else 'MANCANTI'}, BitMEX {'OK' if bitmex_key and bitmex_secret else 'MANCANTI'}, Bitfinex {'OK' if bitfinex_key and bitfinex_secret else 'MANCANTI'}")
        
        self.bybit = CCXTAPI('bybit')
        self.bitmex = CCXTAPI('bitmex')
        self.bitfinex = CCXTAPI('bitfinex')
        
        # Carica gli indirizzi di deposito dal file .env
        self.bitmex_deposit_address = os.getenv('BITMEX_DEPOSIT_ADDRESS')
        self.bybit_deposit_address = os.getenv('BYBIT_DEPOSIT_ADDRESS')
        self.bitfinex_deposit_address = os.getenv('BITFINEX_DEPOSIT_ADDRESS')
        
        if not self.bitmex_deposit_address or not self.bybit_deposit_address or not self.bitfinex_deposit_address:
            logger.error("Indirizzi di deposito non configurati nel file .env")
            raise ValueError("Indirizzi di deposito non configurati")
    
    def verify_api_keys(self):
        """
        Verifica che le API keys siano valide testando una chiamata semplice
        
        Returns:
            dict: Stato delle API keys per ogni exchange
        """
        results = {
            "bybit": {"valid": False, "error": None},
            "bitmex": {"valid": False, "error": None},
            "bitfinex": {"valid": False, "error": None}
        }
        
        # Verifica ByBit
        try:
            self.bybit.exchange.verbose = True  # Abilita il logging dettagliato
            balance = self.bybit.exchange.fetch_balance()
            results["bybit"]["valid"] = True
            self.bybit.exchange.verbose = False  # Disabilita il logging dettagliato
        except Exception as e:
            logger.error(f"Errore verifica API keys ByBit: {str(e)}")
            results["bybit"]["error"] = str(e)
        
        # Verifica BitMEX
        try:
            self.bitmex.exchange.verbose = True  # Abilita il logging dettagliato
            balance = self.bitmex.exchange.fetch_balance()
            results["bitmex"]["valid"] = True
            self.bitmex.exchange.verbose = False  # Disabilita il logging dettagliato
        except Exception as e:
            logger.error(f"Errore verifica API keys BitMEX: {str(e)}")
            results["bitmex"]["error"] = str(e)
            
        # Verifica Bitfinex
        try:
            self.bitfinex.exchange.verbose = True  # Abilita il logging dettagliato
            balance = self.bitfinex.exchange.fetch_balance()
            results["bitfinex"]["valid"] = True
            self.bitfinex.exchange.verbose = False  # Disabilita il logging dettagliato
        except Exception as e:
            logger.error(f"Errore verifica API keys Bitfinex: {str(e)}")
            results["bitfinex"]["error"] = str(e)
        
        return results
    
    def get_public_ip(self):
        """
        Ottiene l'IP pubblico da cui vengono effettuate le chiamate
        
        Returns:
            str: IP pubblico
        """
        try:
            response = requests.get('https://api.ipify.org?format=json')
            if response.status_code == 200:
                ip = response.json()['ip']
                logger.info(f"IP pubblico: {ip}")
                return ip
            else:
                logger.error(f"Errore nel recupero dell'IP: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Errore nel recupero dell'IP: {str(e)}")
            return None
    
    def get_bitfinex_withdrawal_methods(self):
        """
        Ottiene i metodi di prelievo supportati da Bitfinex
        
        Returns:
            dict: Dizionario con i metodi disponibili per ogni valuta
        """
        try:
            # Endpoint pubblico per ottenere i metodi di prelievo
            response = requests.get('https://api-pub.bitfinex.com/v2/conf/pub:map:tx:method')
            
            if response.status_code == 200:
                methods = response.json()
                logger.info("Metodi di prelievo Bitfinex ottenuti con successo")
                return methods
            else:
                logger.warning(f"Impossibile ottenere i metodi di prelievo: {response.status_code}")
                return self._get_default_withdrawal_methods()
                
        except Exception as e:
            logger.warning(f"Errore nel recupero dei metodi di prelievo: {str(e)}")
            return self._get_default_withdrawal_methods()

    def _get_default_withdrawal_methods(self):
        """
        Ritorna i metodi di prelievo di default per USDT
        
        Returns:
            dict: Metodi di default
        """
        return {
            'USDT': {
                'Ethereum': 'tetherus',
                'Tron': 'tetherux', 
                'Liquid': 'tetherusl',
                'Omni': 'tetheruso',
                'Solana': 'tetherusdtsol',
                'Avalanche': 'tetherusdtavax',
                'Algorand': 'tetherusdtalg',
                'Polkadot': 'tetherusdtdot',
                'Kusama': 'tetherusdtksm',
                'EOS': 'tetheruss',
                'NEAR': 'tetherusdtnear',
                'Polygon': 'tetherusdtply',
                'Bitcoin Cash': 'tetherusdtbch',
                'Tezos': 'tetherusdtxtz',
                'KAVA': 'tetherusdtkava',
                'zkSync': 'tetherusdtzk',
                'Celo': 'tetherusdtcelo',
                'Toncoin': 'tetherusdtton'
            }
        }
    
    def get_withdrawal_status(self, exchange_id, withdrawal_id):
        """
        Verifica lo stato di un prelievo

        Args:
            exchange_id (str): ID dell'exchange ('bybit', 'bitmex' o 'bitfinex')
            withdrawal_id (str): ID del prelievo da verificare
            
        Returns:
            dict: Dettagli del prelievo
        """
        try:
            if exchange_id == 'bybit':
                exchange = self.bybit.exchange
            elif exchange_id == 'bitmex':
                # Per BitMEX, utilizziamo un approccio personalizzato invece dei metodi standard CCXT
                return self._get_bitmex_withdrawal_status(withdrawal_id)
            elif exchange_id == 'bitfinex':
                exchange = self.bitfinex.exchange
            else:
                return {
                    "success": False,
                    "error": f"Exchange non supportato: {exchange_id}"
                }
            
            # Verifica se l'exchange supporta il fetching dei prelievi
            if exchange.has['fetchWithdrawal']:
                withdrawal = exchange.fetch_withdrawal(withdrawal_id)
                
                # Formatta le informazioni
                result = {
                    "success": True,
                    "id": withdrawal.get('id'),
                    "txid": withdrawal.get('txid'),  # Hash della transazione
                    "timestamp": withdrawal.get('timestamp'),
                    "datetime": withdrawal.get('datetime'),
                    "currency": withdrawal.get('currency'),
                    "amount": withdrawal.get('amount'),
                    "address": withdrawal.get('address'),
                    "status": withdrawal.get('status'),
                    "fee": withdrawal.get('fee'),
                    "info": withdrawal.get('info')  # Informazioni grezze dall'exchange
                }
                
                return result
            else:
                # Se non è supportato direttamente, prova a usare fetchWithdrawals
                if exchange.has['fetchWithdrawals']:
                    withdrawals = exchange.fetch_withdrawals()
                    for w in withdrawals:
                        if w.get('id') == withdrawal_id:
                            return {
                                "success": True,
                                "id": w.get('id'),
                                "txid": w.get('txid'),
                                "timestamp": w.get('timestamp'),
                                "datetime": w.get('datetime'),
                                "currency": w.get('currency'),
                                "amount": w.get('amount'),
                                "address": w.get('address'),
                                "status": w.get('status'),
                                "fee": w.get('fee'),
                                "info": w.get('info')
                            }
                
                return {
                    "success": False,
                    "error": f"Prelievo non trovato o metodo non supportato da {exchange_id}"
                }
        except Exception as e:
            logger.error(f"Errore nel controllo dello stato del prelievo: {str(e)}")
            return {
                "success": False,
                "error": f"Errore nel controllo dello stato del prelievo: {str(e)}"
            }
            
    def _get_bitmex_withdrawal_status(self, withdrawal_id):
        """
        Metodo specifico per ottenere lo stato di un prelievo su BitMEX
        
        Args:
            withdrawal_id (str): ID del prelievo
            
        Returns:
            dict: Stato e dettagli del prelievo
        """
        try:
            logger.info(f"Recupero stato prelievo BitMEX: {withdrawal_id}")
            
            # Ottiene tutte le transazioni recenti (ultimi 30 giorni) per trovare il prelievo
            # /user/walletHistory è l'endpoint per ottenere la storia delle transazioni
            # Lo combiniamo con un filtro per il tipo di transazione "Withdrawal"
            params = {
                'transactType': 'Withdrawal',  # Filtra solo i prelievi
                'count': 100  # Limita a 100 risultati per evitare problemi di performance
            }
            
            # Imposta il modo verbose per il debug
            self.bitmex.exchange.verbose = True
            
            # Tenta di usare il metodo più appropriato disponibile in CCXT per BitMEX
            transactions = None
            
            # Prova prima con fetchTransactions, che è un metodo unificato CCXT
            if self.bitmex.exchange.has['fetchTransactions']:
                transactions = self.bitmex.exchange.fetch_transactions(params=params)
                logger.info(f"Recuperate {len(transactions) if transactions else 0} transazioni con fetchTransactions")
            
            # Se fetchTransactions fallisce o non trova nulla, prova con fetchMyTrades
            if not transactions and self.bitmex.exchange.has['fetchMyTrades']:
                transactions = self.bitmex.exchange.fetch_my_trades(params=params)
                logger.info(f"Recuperate {len(transactions) if transactions else 0} transazioni con fetchMyTrades")
            
            # Se anche fetchMyTrades fallisce, prova con l'API diretta
            if not transactions:
                # Utilizzo dell'endpoint diretto /wallet/history
                try:
                    # Questo è un endpoint privato, quindi richiede autenticazione
                    history = self.bitmex.exchange.privateGetUserWalletHistory(params)
                    transactions = history
                    logger.info(f"Recuperate {len(transactions) if transactions else 0} transazioni con privateGetUserWalletHistory")
                except Exception as direct_api_error:
                    logger.error(f"Errore API diretta: {str(direct_api_error)}")
                    
                    # Ultimo tentativo con un altro endpoint
                    try:
                        history = self.bitmex.exchange.privateGetUserWallet(params)
                        transactions = history
                        logger.info(f"Recuperate {len(transactions) if transactions else 0} transazioni con privateGetUserWallet")
                    except Exception as wallet_error:
                        logger.error(f"Errore anche con wallet: {str(wallet_error)}")
            
            # Disattiva il modo verbose
            self.bitmex.exchange.verbose = False
            
            # Se non abbiamo trovato transazioni, restituisci un errore
            if not transactions:
                return {
                    "success": False,
                    "error": "Impossibile recuperare transazioni da BitMEX"
                }
            
            # Cerca la transazione con l'ID specificato
            found_transaction = None
            for tx in transactions:
                # Controlla sia 'id' che 'txid' e anche 'transactID' (formato BitMEX specifico)
                tx_id = tx.get('id') or tx.get('txid') or tx.get('transactID')
                
                if str(tx_id) == str(withdrawal_id):
                    found_transaction = tx
                    logger.info(f"Transazione trovata: {tx}")
                    break
            
            # Se non abbiamo trovato la transazione, controlla anche all'interno di 'info'
            if not found_transaction:
                for tx in transactions:
                    if 'info' in tx:
                        info = tx['info']
                        tx_id = info.get('transactID')
                        if str(tx_id) == str(withdrawal_id):
                            found_transaction = tx
                            logger.info(f"Transazione trovata in info: {tx}")
                            break
            
            # Se ancora non abbiamo trovato la transazione, restituisci un errore
            if not found_transaction:
                return {
                    "success": False,
                    "error": f"Prelievo con ID {withdrawal_id} non trovato su BitMEX"
                }
            
            # Estrai i dettagli della transazione
            tx_info = found_transaction.get('info', {})
            
            # Mappatura dello stato
            status_map = {
                'Pending': 'pending',
                'Confirmed': 'ok',
                'Completed': 'ok',
                'Processing': 'pending',
                'Rejected': 'failed',
                'Canceled': 'canceled',
            }
            
            raw_status = tx_info.get('transactStatus', found_transaction.get('status', 'Unknown'))
            status = status_map.get(raw_status, raw_status.lower())
            
            # Formatta i risultati in un formato standard
            result = {
                "success": True,
                "id": tx_info.get('transactID', found_transaction.get('id')),
                "txid": tx_info.get('tx', found_transaction.get('txid')),
                "timestamp": found_transaction.get('timestamp'),
                "datetime": found_transaction.get('datetime'),
                "currency": tx_info.get('currency', found_transaction.get('currency', 'USDT')),
                "amount": tx_info.get('amount', found_transaction.get('amount', 0)),
                "address": tx_info.get('address', found_transaction.get('address', '')),
                "status": status,
                "fee": tx_info.get('fee', found_transaction.get('fee', 0)),
                "info": tx_info
            }
            
            return result
        except Exception as e:
            logger.error(f"Errore nel recupero dello stato del prelievo BitMEX: {str(e)}")
            return {
                "success": False,
                "error": f"Errore nel recupero dello stato del prelievo BitMEX: {str(e)}"
            }
    
    def get_withdrawal_fee(self, exchange, currency='USDT'):
        """
        Ottiene la fee di prelievo per l'exchange specificato
        
        Args:
            exchange (str): ID dell'exchange ('bybit', 'bitmex' o 'bitfinex')
            currency (str): Valuta per cui ottenere la fee
            
        Returns:
            float: Fee di prelievo in USDT
        """
        try:
            if exchange == 'bybit':
                # Per ByBit, otteniamo le fee dal mercato
                markets = self.bybit.exchange.fetch_markets()
                for market in markets:
                    if market['base'] == currency and market['quote'] == 'USDT':
                        if 'withdraw' in market and 'fee' in market['withdraw']:
                            return float(market['withdraw']['fee'])
                
                # Se non troviamo la fee nel mercato, proviamo a ottenere le informazioni di prelievo
                try:
                    withdrawal_info = self.bybit.exchange.fetch_deposit_withdraw_fees([currency])
                    if currency in withdrawal_info and 'withdraw' in withdrawal_info[currency]:
                        return float(withdrawal_info[currency]['withdraw']['fee'])
                except Exception as e:
                    logger.warning(f"Impossibile ottenere le fee di prelievo da ByBit: {str(e)}")
            
            elif exchange == 'bitmex':
                # Per BitMEX, otteniamo le fee dalle informazioni di prelievo
                try:
                    withdrawal_info = self.bitmex.exchange.fetch_deposit_withdraw_fees([currency])
                    if currency in withdrawal_info and 'withdraw' in withdrawal_info[currency]:
                        return float(withdrawal_info[currency]['withdraw']['fee'])
                except Exception as e:
                    logger.warning(f"Impossibile ottenere le fee di prelievo da BitMEX: {str(e)}")
                    
            elif exchange == 'bitfinex':
                # Per Bitfinex, otteniamo le fee dalle informazioni di prelievo
                try:
                    withdrawal_info = self.bitfinex.exchange.fetch_deposit_withdraw_fees([currency])
                    if currency in withdrawal_info and 'withdraw' in withdrawal_info[currency]:
                        return float(withdrawal_info[currency]['withdraw']['fee'])
                except Exception as e:
                    logger.warning(f"Impossibile ottenere le fee di prelievo da Bitfinex: {str(e)}")
            
            # Se non riusciamo a ottenere le fee, usiamo un valore di default
            logger.warning(f"Impossibile ottenere le fee di prelievo per {exchange}, uso valore di default")
            return 1.0  # Valore di default in USDT
            
        except Exception as e:
            logger.error(f"Errore nel recupero delle fee di prelievo per {exchange}: {str(e)}")
            return 1.0  # Valore di default in caso di errore
            
    def _bitfinex_internal_transfer(self, amount, from_wallet='margin', to_wallet='exchange'):
        """
        Esegue un trasferimento interno su Bitfinex tra wallet
        
        Args:
            amount (float): Quantità di USDT da trasferire
            from_wallet (str): Wallet di origine (default: margin)
            to_wallet (str): Wallet di destinazione (default: exchange)
            
        Returns:
            dict: Risultato dell'operazione
        """
        try:
            logger.info(f"Trasferimento interno Bitfinex: {amount} USDT da {from_wallet} a {to_wallet}")
            
            # Determina la valuta corretta in base al wallet di origine
            actual_currency = "USTF0" if from_wallet == "margin" else "UST"
            
            # Determina la valuta di destinazione in base al wallet di destinazione
            actual_currency_to = "USTF0" if to_wallet == "margin" else "UST"
            
            # Prepara i parametri per la richiesta API
            params = {
                "from": from_wallet,
                "to": to_wallet,
                "currency": actual_currency,
                "amount": str(amount)
            }
            
            # Se la valuta di origine e destinazione sono diverse, aggiungila ai parametri
            if actual_currency != actual_currency_to:
                params["currency_to"] = actual_currency_to
                logger.info(f"Conversione da {actual_currency} a {actual_currency_to}")
            
            # Usa il metodo privato di CCXT per accedere all'endpoint transfer
            result = self.bitfinex.exchange.private_post_auth_w_transfer(params)
            
            # Verifica la risposta
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
                return {
                    "success": False,
                    "error": "Risposta API non valida",
                    "info": result
                }
        except Exception as e:
            logger.error(f"Errore durante il trasferimento interno Bitfinex: {str(e)}")
            return {
                "success": False,
                "error": f"Errore durante il trasferimento interno Bitfinex: {str(e)}"
            }
    
    def transfer_bybit_to_bitmex(self, amount):
        """
        Trasferisce USDT da ByBit a BitMEX utilizzando la rete Solana
        
        Args:
            amount (float): Quantità di USDT da trasferire (inclusa la fee)
            
        Returns:
            dict: Risultato dell'operazione
        """
        try:
            # Ottieni la fee di prelievo
            withdrawal_fee = self.get_withdrawal_fee('bybit')
            actual_amount = amount - withdrawal_fee
            
            if actual_amount <= 0:
                return {
                    "success": False,
                    "error": f"L'importo deve essere maggiore della fee di prelievo ({withdrawal_fee} USDT)"
                }
            
            # 1. Verifica il saldo disponibile
            bybit_balance = self.bybit.exchange.fetch_balance()
            usdt_balance = bybit_balance.get('USDT', {}).get('free', 0)
            
            if usdt_balance < amount:
                return {
                    "success": False,
                    "error": f"Saldo insufficiente su ByBit. Disponibile: {usdt_balance} USDT, Richiesto: {amount} USDT (inclusa fee di {withdrawal_fee} USDT)"
                }
            
            # 2. Sposta i fondi da unified trading a funding
            try:
                # Correzione della chiamata transfer con i parametri nel formato corretto
                self.bybit.exchange.transfer(
                    code='USDT',
                    amount=str(amount),
                    fromAccount='unified',
                    toAccount='funding'
                )
            except Exception as e:
                logger.error(f"Errore nel trasferimento a funding: {str(e)}")
                return {
                    "success": False,
                    "error": f"Errore nel trasferimento a funding: {str(e)}"
                }
            
            # 3. Effettua il prelievo utilizzando la rete Solana
            try:
                withdrawal = self.bybit.exchange.withdraw(
                    'USDT',
                    str(actual_amount),  # Converti actual_amount in stringa
                    self.bitmex_deposit_address,
                    params={
                        'chain': 'SOL'  # Rete Solana per trasferimenti tra ByBit e BitMEX
                    }
                )
                
                return {
                    "success": True,
                    "message": f"Trasferimento di {actual_amount} USDT da ByBit a BitMEX completato con successo (fee di {withdrawal_fee} USDT dedotta) - Rete: Solana",
                    "withdrawal_id": withdrawal.get('id'),
                    "exchange": "bybit",
                    "amount": actual_amount,
                    "fee": withdrawal_fee,
                    "network": "Solana"
                }
                
            except Exception as e:
                logger.error(f"Errore nel prelievo: {str(e)}")
                return {
                    "success": False,
                    "error": f"Errore nel prelievo: {str(e)}"
                }
            
        except Exception as e:
            logger.error(f"Errore durante il trasferimento da ByBit a BitMEX: {str(e)}")
            return {
                "success": False,
                "error": f"Errore durante il trasferimento: {str(e)}"
            }
    
    def transfer_bitmex_to_bybit(self, amount):
        """
        Trasferisce USDT da BitMEX a ByBit utilizzando la rete Solana
        
        Args:
            amount (float): Quantità di USDT da trasferire (inclusa la fee)
            
        Returns:
            dict: Risultato dell'operazione
        """
        try:
            # Ottieni la fee di prelievo
            withdrawal_fee = self.get_withdrawal_fee('bitmex')
            actual_amount = amount - withdrawal_fee
            
            if actual_amount <= 0:
                return {
                    "success": False,
                    "error": f"L'importo deve essere maggiore della fee di prelievo ({withdrawal_fee} USDT)"
                }
            
            # 1. Verifica il saldo disponibile
            bitmex_balance = self.bitmex.exchange.fetch_balance()
            usdt_balance = bitmex_balance.get('USDT', {}).get('free', 0)
            
            if usdt_balance < amount:
                return {
                    "success": False,
                    "error": f"Saldo insufficiente su BitMEX. Disponibile: {usdt_balance} USDT, Richiesto: {amount} USDT (inclusa fee di {withdrawal_fee} USDT)"
                }
            
            # 2. Effettua il prelievo utilizzando la rete Solana
            try:
                withdrawal = self.bitmex.exchange.withdraw(
                    'USDT',
                    str(actual_amount),  # Converti actual_amount in stringa
                    self.bybit_deposit_address,
                    params={
                        'network': 'SOL'  # BitMEX richiede il parametro 'network' invece di 'chain' (rete Solana)
                    }
                )
                
                return {
                    "success": True,
                    "message": f"Trasferimento di {actual_amount} USDT da BitMEX a ByBit completato con successo (fee di {withdrawal_fee} USDT dedotta) - Rete: Solana",
                    "withdrawal_id": withdrawal.get('id'),
                    "exchange": "bitmex",
                    "amount": actual_amount,
                    "fee": withdrawal_fee,
                    "network": "Solana"
                }
                
            except Exception as e:
                logger.error(f"Errore nel prelievo: {str(e)}")
                return {
                    "success": False,
                    "error": f"Errore nel prelievo: {str(e)}"
                }
            
        except Exception as e:
            logger.error(f"Errore durante il trasferimento da BitMEX a ByBit: {str(e)}")
            return {
                "success": False,
                "error": f"Errore durante il trasferimento: {str(e)}"
            }
            
    def transfer_bitfinex_to_bybit(self, amount, from_wallet='margin'):
        """
        Trasferisce USDT da Bitfinex a ByBit utilizzando la rete Solana
        Con gestione migliorata degli errori di settlement
        
        Args:
            amount (float): Quantità di USDT da trasferire (inclusa la fee)
            from_wallet (str): Wallet di origine su Bitfinex (default: margin)
            
        Returns:
            dict: Risultato dell'operazione
        """
        try:
            # Ottieni la fee di prelievo
            withdrawal_fee = self.get_withdrawal_fee('bitfinex')
            actual_amount = amount - withdrawal_fee
            
            if actual_amount <= 0:
                return {
                    "success": False,
                    "error": f"L'importo deve essere maggiore della fee di prelievo ({withdrawal_fee} USDT)"
                }
            
            # 1. Verifica il saldo disponibile
            bitfinex_balance = self.bitfinex.exchange.fetch_balance()
            
            # In Bitfinex, USDT è denominato in modo diverso a seconda del wallet
            currency_code = "USTF0" if from_wallet == "margin" else "UST"
            
            # Cerca il saldo nel formato corretto per Bitfinex
            usdt_balance = 0
            
            # Prova prima a cercare nel formato specifico di wallet Bitfinex
            if from_wallet in bitfinex_balance:
                usdt_balance = bitfinex_balance[from_wallet].get(currency_code, {}).get('free', 0)
                if usdt_balance == 0:
                    # Prova anche con 'USDT' nel caso in cui il formato sia cambiato
                    usdt_balance = bitfinex_balance[from_wallet].get('USDT', {}).get('free', 0)
            
            # Se non trovato nel wallet specifico, cerca nella struttura generale
            if usdt_balance == 0:
                usdt_balance = bitfinex_balance.get(currency_code, {}).get('free', 0)
                if usdt_balance == 0:
                    usdt_balance = bitfinex_balance.get('USDT', {}).get('free', 0)
            
            # Se è presente 'info' invece di 'free', controlla anche lì
            if 'info' in bitfinex_balance:
                for wallet_info in bitfinex_balance['info']:
                    if len(wallet_info) >= 3:
                        wallet_type = wallet_info[0]
                        currency = wallet_info[1]
                        balance_amount = float(wallet_info[2])
                        
                        if wallet_type == from_wallet and (currency == currency_code or currency == 'USDT') and balance_amount > 0:
                            usdt_balance = balance_amount
                            break
            
            if usdt_balance < amount:
                return {
                    "success": False,
                    "error": f"Saldo insufficiente su Bitfinex nel wallet {from_wallet}. Disponibile: {usdt_balance} {currency_code}, Richiesto: {amount} USDT (inclusa fee di {withdrawal_fee} USDT)"
                }
            
            # 2. Se il wallet di origine è 'margin', effettua prima un trasferimento interno a 'exchange'
            if from_wallet == 'margin':
                transfer_result = self._bitfinex_internal_transfer(amount, from_wallet, 'exchange')
                
                if not transfer_result['success']:
                    return {
                        "success": False,
                        "error": f"Errore nel trasferimento interno da {from_wallet} a exchange: {transfer_result['error']}"
                    }
                
                logger.info(f"Trasferimento interno completato: {transfer_result['message']}")
                
                # NUOVO: Attendi che il settlement sia completato dopo il trasferimento interno
                logger.info("Attendo il completamento del settlement dopo il trasferimento interno...")
                import time
                time.sleep(10)  # Attendi 10 secondi per il settlement
            
            # 2.5. Verifica i requisiti di prelievo prima di procedere
            requirements_check = self.check_bitfinex_withdrawal_requirements(
                actual_amount, 
                self.bybit_deposit_address, 
                'SOL'
            )
            
            if not requirements_check['success']:
                return {
                    "success": False,
                    "error": f"Requisiti di prelievo non soddisfatti: {requirements_check['error']}",
                    "requirements_check": requirements_check
                }
            
            logger.info(f"Requisiti di prelievo verificati: {requirements_check['message']}")
            
            # 3. Effettua il prelievo con retry in caso di settlement in progress
            max_retries = 3
            retry_delay = 15  # secondi
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"Tentativo di prelievo {attempt + 1}/{max_retries}: {actual_amount} USDT verso {self.bybit_deposit_address}")
                    
                    withdrawal = self.bitfinex.exchange.withdraw(
                        'USDT',  # USDT è il codice valuta corretto
                        str(actual_amount),  # Converti actual_amount in stringa
                        self.bybit_deposit_address,
                        params={
                            'network': 'SOL',  # Network richiesto da CCXT
                            'method': 'tetherusdtsol'  # Metodo specifico per USDT su rete Solana
                        }
                    )
                    
                    logger.info(f"Risposta withdrawal (tentativo {attempt + 1}): {withdrawal}")
                    
                    # Verifica se è un errore di settlement
                    if withdrawal and 'info' in withdrawal:
                        info = withdrawal['info']
                        if isinstance(info, list) and len(info) > 7:
                            error_msg = info[7] if info[7] else ""
                            
                            # Se è un errore di settlement, ritenta
                            if "Settlement" in error_msg or "Transfer in progress" in error_msg:
                                if attempt < max_retries - 1:  # Non è l'ultimo tentativo
                                    logger.warning(f"Settlement in progress, attendo {retry_delay} secondi prima del prossimo tentativo...")
                                    import time
                                    time.sleep(retry_delay)
                                    continue
                                else:
                                    return {
                                        "success": False,
                                        "error": f"Impossibile completare il prelievo dopo {max_retries} tentativi. Errore: {error_msg}",
                                        "suggestion": "Riprova tra qualche minuto quando il settlement sarà completato"
                                    }
                    
                    # Verifica che il withdrawal sia stato effettivamente creato
                    if not withdrawal or not withdrawal.get('id'):
                        # Controlla se il withdrawal è effettivamente fallito o è solo un problema di ID
                        withdrawal_status = withdrawal.get('status', 'unknown') if withdrawal else 'unknown'
                        
                        if withdrawal_status == 'failed':
                            # Estrai informazioni dettagliate sull'errore
                            error_details = "Errore sconosciuto"
                            if withdrawal and 'info' in withdrawal and isinstance(withdrawal['info'], list):
                                if len(withdrawal['info']) > 7 and withdrawal['info'][7]:
                                    error_details = withdrawal['info'][7]
                            
                            return {
                                "success": False,
                                "error": f"Prelievo rifiutato da Bitfinex: {error_details}",
                                "response": withdrawal,
                                "suggestion": "Verifica che l'indirizzo sia corretto e che non ci siano restrizioni sull'account"
                            }
                        else:
                            return {
                                "success": False,
                                "error": "Il prelievo non è stato creato - nessun ID withdrawal ricevuto",
                                "response": withdrawal
                            }
                    
                    # Se arriviamo qui, il prelievo è stato creato con successo
                    withdrawal_id = withdrawal.get('id')
                    withdrawal_status = withdrawal.get('status', 'unknown')
                    withdrawal_info = withdrawal.get('info', {})
                    
                    logger.info(f"Withdrawal ID: {withdrawal_id}, Status: {withdrawal_status}")
                    logger.info(f"Dettagli completi: {withdrawal_info}")
                    
                    # Attendi qualche secondo e verifica lo stato del prelievo
                    import time
                    time.sleep(3)
                    
                    status_check = self.get_withdrawal_status('bitfinex', withdrawal_id)
                    logger.info(f"Controllo stato prelievo: {status_check}")
                    
                    return {
                        "success": True,
                        "message": f"Trasferimento di {actual_amount} USDT da Bitfinex a ByBit completato con successo (fee di {withdrawal_fee} USDT dedotta) - Rete: Solana",
                        "withdrawal_id": withdrawal_id,
                        "exchange": "bitfinex",
                        "amount": actual_amount,
                        "fee": withdrawal_fee,
                        "network": "Solana",
                        "status": withdrawal_status,
                        "status_check": status_check,
                        "raw_response": withdrawal_info,
                        "attempts": attempt + 1
                    }
                    
                except Exception as e:
                    logger.error(f"Errore nel prelievo (tentativo {attempt + 1}): {str(e)}")
                    if attempt < max_retries - 1:
                        logger.info(f"Ritento tra {retry_delay} secondi...")
                        import time
                        time.sleep(retry_delay)
                    else:
                        return {
                            "success": False,
                            "error": f"Errore nel prelievo dopo {max_retries} tentativi: {str(e)}"
                        }
            
            return {
                "success": False,
                "error": f"Impossibile completare il prelievo dopo {max_retries} tentativi"
            }
            
        except Exception as e:
            logger.error(f"Errore durante il trasferimento da Bitfinex a ByBit: {str(e)}")
            return {
                "success": False,
                "error": f"Errore durante il trasferimento: {str(e)}"
            }
            
    def transfer_bitfinex_to_bitmex(self, amount, from_wallet='margin'):
        """
        Trasferisce USDT da Bitfinex a BitMEX utilizzando la rete Solana
        Con gestione migliorata degli errori di settlement
        
        Args:
            amount (float): Quantità di USDT da trasferire (inclusa la fee)
            from_wallet (str): Wallet di origine su Bitfinex (default: margin)
            
        Returns:
            dict: Risultato dell'operazione
        """
        try:
            # Ottieni la fee di prelievo
            withdrawal_fee = self.get_withdrawal_fee('bitfinex')
            actual_amount = amount - withdrawal_fee
            
            if actual_amount <= 0:
                return {
                    "success": False,
                    "error": f"L'importo deve essere maggiore della fee di prelievo ({withdrawal_fee} USDT)"
                }
            
            # 1. Verifica il saldo disponibile
            bitfinex_balance = self.bitfinex.exchange.fetch_balance()
            
            # In Bitfinex, USDT è denominato in modo diverso a seconda del wallet
            currency_code = "USTF0" if from_wallet == "margin" else "UST"
            
            # Cerca il saldo nel formato corretto per Bitfinex
            usdt_balance = 0
            
            # Prova prima a cercare nel formato specifico di wallet Bitfinex
            if from_wallet in bitfinex_balance:
                usdt_balance = bitfinex_balance[from_wallet].get(currency_code, {}).get('free', 0)
                if usdt_balance == 0:
                    # Prova anche con 'USDT' nel caso in cui il formato sia cambiato
                    usdt_balance = bitfinex_balance[from_wallet].get('USDT', {}).get('free', 0)
            
            # Se non trovato nel wallet specifico, cerca nella struttura generale
            if usdt_balance == 0:
                usdt_balance = bitfinex_balance.get(currency_code, {}).get('free', 0)
                if usdt_balance == 0:
                    usdt_balance = bitfinex_balance.get('USDT', {}).get('free', 0)
            
            # Se è presente 'info' invece di 'free', controlla anche lì
            if 'info' in bitfinex_balance:
                for wallet_info in bitfinex_balance['info']:
                    if len(wallet_info) >= 3:
                        wallet_type = wallet_info[0]
                        currency = wallet_info[1]
                        balance_amount = float(wallet_info[2])
                        
                        if wallet_type == from_wallet and (currency == currency_code or currency == 'USDT') and balance_amount > 0:
                            usdt_balance = balance_amount
                            break
            
            if usdt_balance < amount:
                return {
                    "success": False,
                    "error": f"Saldo insufficiente su Bitfinex nel wallet {from_wallet}. Disponibile: {usdt_balance} {currency_code}, Richiesto: {amount} USDT (inclusa fee di {withdrawal_fee} USDT)"
                }
            
            # 2. Se il wallet di origine è 'margin', effettua prima un trasferimento interno a 'exchange'
            if from_wallet == 'margin':
                transfer_result = self._bitfinex_internal_transfer(amount, from_wallet, 'exchange')
                
                if not transfer_result['success']:
                    return {
                        "success": False,
                        "error": f"Errore nel trasferimento interno da {from_wallet} a exchange: {transfer_result['error']}"
                    }
                
                logger.info(f"Trasferimento interno completato: {transfer_result['message']}")
                
                # NUOVO: Attendi che il settlement sia completato dopo il trasferimento interno
                logger.info("Attendo il completamento del settlement dopo il trasferimento interno...")
                import time
                time.sleep(10)  # Attendi 10 secondi per il settlement
            
            # 2.5. Verifica i requisiti di prelievo prima di procedere
            requirements_check = self.check_bitfinex_withdrawal_requirements(
                actual_amount, 
                self.bitmex_deposit_address, 
                'SOL'
            )
            
            if not requirements_check['success']:
                return {
                    "success": False,
                    "error": f"Requisiti di prelievo non soddisfatti: {requirements_check['error']}",
                    "requirements_check": requirements_check
                }
            
            logger.info(f"Requisiti di prelievo verificati: {requirements_check['message']}")
            
            # 3. Effettua il prelievo con retry in caso di settlement in progress
            max_retries = 3
            retry_delay = 15  # secondi
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"Tentativo di prelievo {attempt + 1}/{max_retries}: {actual_amount} USDT verso {self.bitmex_deposit_address}")
                    
                    withdrawal = self.bitfinex.exchange.withdraw(
                        'USDT',  # USDT è il codice valuta corretto
                        str(actual_amount),  # Converti actual_amount in stringa
                        self.bitmex_deposit_address,
                        params={
                            'network': 'SOL',  # Network richiesto da CCXT
                            'method': 'tetherusdtsol'  # Metodo specifico per USDT su rete Solana
                        }
                    )
                    
                    logger.info(f"Risposta withdrawal (tentativo {attempt + 1}): {withdrawal}")
                    
                    # Verifica se è un errore di settlement
                    if withdrawal and 'info' in withdrawal:
                        info = withdrawal['info']
                        if isinstance(info, list) and len(info) > 7:
                            error_msg = info[7] if info[7] else ""
                            
                            # Se è un errore di settlement, ritenta
                            if "Settlement" in error_msg or "Transfer in progress" in error_msg:
                                if attempt < max_retries - 1:  # Non è l'ultimo tentativo
                                    logger.warning(f"Settlement in progress, attendo {retry_delay} secondi prima del prossimo tentativo...")
                                    import time
                                    time.sleep(retry_delay)
                                    continue
                                else:
                                    return {
                                        "success": False,
                                        "error": f"Impossibile completare il prelievo dopo {max_retries} tentativi. Errore: {error_msg}",
                                        "suggestion": "Riprova tra qualche minuto quando il settlement sarà completato"
                                    }
                    
                    # Verifica che il withdrawal sia stato effettivamente creato
                    if not withdrawal or not withdrawal.get('id'):
                        # Controlla se il withdrawal è effettivamente fallito o è solo un problema di ID
                        withdrawal_status = withdrawal.get('status', 'unknown') if withdrawal else 'unknown'
                        
                        if withdrawal_status == 'failed':
                            # Estrai informazioni dettagliate sull'errore
                            error_details = "Errore sconosciuto"
                            if withdrawal and 'info' in withdrawal and isinstance(withdrawal['info'], list):
                                if len(withdrawal['info']) > 7 and withdrawal['info'][7]:
                                    error_details = withdrawal['info'][7]
                            
                            return {
                                "success": False,
                                "error": f"Prelievo rifiutato da Bitfinex: {error_details}",
                                "response": withdrawal,
                                "suggestion": "Verifica che l'indirizzo sia corretto e che non ci siano restrizioni sull'account"
                            }
                        else:
                            return {
                                "success": False,
                                "error": "Il prelievo non è stato creato - nessun ID withdrawal ricevuto",
                                "response": withdrawal
                            }
                    
                    # Se arriviamo qui, il prelievo è stato creato con successo
                    withdrawal_id = withdrawal.get('id')
                    withdrawal_status = withdrawal.get('status', 'unknown')
                    withdrawal_info = withdrawal.get('info', {})
                    
                    logger.info(f"Withdrawal ID: {withdrawal_id}, Status: {withdrawal_status}")
                    logger.info(f"Dettagli completi: {withdrawal_info}")
                    
                    # Attendi qualche secondo e verifica lo stato del prelievo
                    import time
                    time.sleep(3)
                    
                    status_check = self.get_withdrawal_status('bitfinex', withdrawal_id)
                    logger.info(f"Controllo stato prelievo: {status_check}")
                    
                    return {
                        "success": True,
                        "message": f"Trasferimento di {actual_amount} USDT da Bitfinex a BitMEX completato con successo (fee di {withdrawal_fee} USDT dedotta) - Rete: Solana",
                        "withdrawal_id": withdrawal_id,
                        "exchange": "bitfinex",
                        "amount": actual_amount,
                        "fee": withdrawal_fee,
                        "network": "Solana",
                        "status": withdrawal_status,
                        "status_check": status_check,
                        "raw_response": withdrawal_info,
                        "attempts": attempt + 1
                    }
                    
                except Exception as e:
                    logger.error(f"Errore nel prelievo (tentativo {attempt + 1}): {str(e)}")
                    if attempt < max_retries - 1:
                        logger.info(f"Ritento tra {retry_delay} secondi...")
                        import time
                        time.sleep(retry_delay)
                    else:
                        return {
                            "success": False,
                            "error": f"Errore nel prelievo dopo {max_retries} tentativi: {str(e)}"
                        }
            
            return {
                "success": False,
                "error": f"Impossibile completare il prelievo dopo {max_retries} tentativi"
            }
            
        except Exception as e:
            logger.error(f"Errore durante il trasferimento da Bitfinex a BitMEX: {str(e)}")
            return {
                "success": False,
                "error": f"Errore durante il trasferimento: {str(e)}"
            }
            
    def transfer_bybit_to_bitfinex(self, amount, to_wallet='margin'):
        """
        Trasferisce USDT da ByBit a Bitfinex utilizzando la rete Solana
        
        Args:
            amount (float): Quantità di USDT da trasferire (inclusa la fee)
            to_wallet (str): Wallet di destinazione su Bitfinex (default: margin)
            
        Returns:
            dict: Risultato dell'operazione
        """
        try:
            # Ottieni la fee di prelievo
            withdrawal_fee = self.get_withdrawal_fee('bybit')
            actual_amount = amount - withdrawal_fee
            
            if actual_amount <= 0:
                return {
                    "success": False,
                    "error": f"L'importo deve essere maggiore della fee di prelievo ({withdrawal_fee} USDT)"
                }
            
            # 1. Verifica il saldo disponibile
            bybit_balance = self.bybit.exchange.fetch_balance()
            usdt_balance = bybit_balance.get('USDT', {}).get('free', 0)
            
            if usdt_balance < amount:
                return {
                    "success": False,
                    "error": f"Saldo insufficiente su ByBit. Disponibile: {usdt_balance} USDT, Richiesto: {amount} USDT (inclusa fee di {withdrawal_fee} USDT)"
                }
            
            # 2. Sposta i fondi da unified trading a funding
            try:
                # Correzione della chiamata transfer con i parametri nel formato corretto
                self.bybit.exchange.transfer(
                    code='USDT',
                    amount=str(amount),
                    fromAccount='unified',
                    toAccount='funding'
                )
            except Exception as e:
                logger.error(f"Errore nel trasferimento a funding: {str(e)}")
                return {
                    "success": False,
                    "error": f"Errore nel trasferimento a funding: {str(e)}"
                }
            
            # 3. Effettua il prelievo utilizzando la rete Solana
            try:
                withdrawal = self.bybit.exchange.withdraw(
                    'USDT',
                    str(actual_amount),  # Converti actual_amount in stringa
                    self.bitfinex_deposit_address,
                    params={
                        'chain': 'SOL'  # Rete Solana per Bitfinex (ByBit usa 'chain')
                    }
                )
                
                return {
                    "success": True,
                    "message": f"Trasferimento di {actual_amount} USDT da ByBit a Bitfinex completato con successo (fee di {withdrawal_fee} USDT dedotta) - Rete: Solana",
                    "withdrawal_id": withdrawal.get('id'),
                    "exchange": "bybit",
                    "amount": actual_amount,
                    "fee": withdrawal_fee,
                    "network": "Solana",
                    "note": f"I fondi arriveranno nel wallet exchange di Bitfinex. Trasferimento manuale richiesto per wallet {to_wallet} se necessario."
                }
                
            except Exception as e:
                logger.error(f"Errore nel prelievo: {str(e)}")
                return {
                    "success": False,
                    "error": f"Errore nel prelievo: {str(e)}"
                }
            
        except Exception as e:
            logger.error(f"Errore durante il trasferimento da ByBit a Bitfinex: {str(e)}")
            return {
                "success": False,
                "error": f"Errore durante il trasferimento: {str(e)}"
            }
            
    def transfer_bitmex_to_bitfinex(self, amount, to_wallet='margin'):
        """
        Trasferisce USDT da BitMEX a Bitfinex utilizzando la rete Solana
        
        Args:
            amount (float): Quantità di USDT da trasferire (inclusa la fee)
            to_wallet (str): Wallet di destinazione su Bitfinex (default: margin)
            
        Returns:
            dict: Risultato dell'operazione
        """
        try:
            # Ottieni la fee di prelievo
            withdrawal_fee = self.get_withdrawal_fee('bitmex')
            actual_amount = amount - withdrawal_fee
            
            if actual_amount <= 0:
                return {
                    "success": False,
                    "error": f"L'importo deve essere maggiore della fee di prelievo ({withdrawal_fee} USDT)"
                }
            
            # 1. Verifica il saldo disponibile
            bitmex_balance = self.bitmex.exchange.fetch_balance()
            usdt_balance = bitmex_balance.get('USDT', {}).get('free', 0)
            
            if usdt_balance < amount:
                return {
                    "success": False,
                    "error": f"Saldo insufficiente su BitMEX. Disponibile: {usdt_balance} USDT, Richiesto: {amount} USDT (inclusa fee di {withdrawal_fee} USDT)"
                }
            
            # 2. Effettua il prelievo utilizzando la rete Solana
            try:
                withdrawal = self.bitmex.exchange.withdraw(
                    'USDT',
                    str(actual_amount),  # Converti actual_amount in stringa
                    self.bitfinex_deposit_address,
                    params={
                        'network': 'SOL'  # Rete Solana per Bitfinex (BitMEX usa 'network')
                    }
                )
                
                return {
                    "success": True,
                    "message": f"Trasferimento di {actual_amount} USDT da BitMEX a Bitfinex completato con successo (fee di {withdrawal_fee} USDT dedotta) - Rete: Solana",
                    "withdrawal_id": withdrawal.get('id'),
                    "exchange": "bitmex",
                    "amount": actual_amount,
                    "fee": withdrawal_fee,
                    "network": "Solana",
                    "note": f"I fondi arriveranno nel wallet exchange di Bitfinex. Trasferimento manuale richiesto per wallet {to_wallet} se necessario."
                }
                
            except Exception as e:
                logger.error(f"Errore nel prelievo: {str(e)}")
                return {
                    "success": False,
                    "error": f"Errore nel prelievo: {str(e)}"
                }
            
        except Exception as e:
            logger.error(f"Errore durante il trasferimento da BitMEX a Bitfinex: {str(e)}")
            return {
                "success": False,
                "error": f"Errore durante il trasferimento: {str(e)}"
            }

    def check_bitfinex_withdrawal_requirements(self, amount, address, network='SOL'):
        """
        Verifica i requisiti per un prelievo da Bitfinex prima di eseguirlo
        
        Args:
            amount (float): Importo da prelevare
            address (str): Indirizzo di destinazione
            network (str): Rete da utilizzare
            
        Returns:
            dict: Risultato della verifica
        """
        try:
            # 1. Verifica che l'indirizzo sia nella whitelist (se richiesto)
            # 2. Verifica i limiti di prelievo
            # 3. Verifica lo stato dell'account
            
            # Ottieni informazioni sull'account
            account_info = self.bitfinex.exchange.fetch_balance()
            
            # Verifica se ci sono restrizioni sull'account
            if 'info' in account_info:
                logger.info("Informazioni account Bitfinex ottenute")
            
            # Verifica limiti di prelievo giornalieri/mensili
            try:
                # Prova a ottenere i limiti di prelievo
                limits = self.bitfinex.exchange.fetch_deposit_withdraw_fees(['USDT'])
                usdt_limits = limits.get('USDT', {}).get('withdraw', {})
                
                min_withdrawal = usdt_limits.get('min', 0)
                max_withdrawal = usdt_limits.get('max', float('inf'))
                
                if amount < min_withdrawal:
                    return {
                        "success": False,
                        "error": f"Importo minimo di prelievo: {min_withdrawal} USDT",
                        "min_amount": min_withdrawal
                    }
                
                if amount > max_withdrawal:
                    return {
                        "success": False,
                        "error": f"Importo massimo di prelievo: {max_withdrawal} USDT",
                        "max_amount": max_withdrawal
                    }
                
            except Exception as e:
                logger.warning(f"Impossibile verificare i limiti di prelievo: {str(e)}")
            
            # Verifica che l'indirizzo sia valido per la rete Solana
            if network == 'SOL' and address:
                # Verifica base per indirizzo Solana (lunghezza e caratteri)
                if len(address) < 32 or len(address) > 44:
                    return {
                        "success": False,
                        "error": f"Indirizzo Solana non valido: {address}",
                        "note": "Gli indirizzi Solana devono essere tra 32 e 44 caratteri"
                    }
            
            return {
                "success": True,
                "message": "Requisiti di prelievo verificati con successo",
                "limits": {
                    "min": min_withdrawal if 'min_withdrawal' in locals() else "N/A",
                    "max": max_withdrawal if 'max_withdrawal' in locals() else "N/A"
                },
                "network": network,
                "address": address[:10] + "..." + address[-10:] if len(address) > 20 else address
            }
            
        except Exception as e:
            logger.error(f"Errore nella verifica dei requisiti: {str(e)}")
            return {
                "success": False,
                "error": f"Errore nella verifica: {str(e)}"
            }

    def test_bitfinex_withdraw_params(self):
        """
        Testa i parametri di prelievo per Bitfinex per verificare che siano corretti
        
        Returns:
            dict: Risultato del test
        """
        try:
            # Prova a ottenere le informazioni sulle valute supportate
            currencies = self.bitfinex.exchange.fetch_currencies()
            
            if 'USDT' in currencies:
                usdt_info = currencies['USDT']
                networks = usdt_info.get('networks', {})
                
                logger.info(f"Reti USDT supportate da Bitfinex: {list(networks.keys())}")
                
                if 'SOL' in networks:
                    sol_info = networks['SOL']
                    logger.info(f"Informazioni rete Solana: {sol_info}")
                    
                    return {
                        "success": True,
                        "message": "Parametri Bitfinex verificati con successo",
                        "supported_networks": list(networks.keys()),
                        "solana_info": sol_info,
                        "recommended_params": {
                            "network": "SOL",
                            "method": "tetherusdtsol"
                        }
                    }
                else:
                    return {
                        "success": False,
                        "error": "Rete Solana non trovata nelle reti supportate",
                        "supported_networks": list(networks.keys())
                    }
            else:
                return {
                    "success": False,
                    "error": "USDT non trovato nelle valute supportate"
                }
                
        except Exception as e:
            logger.error(f"Errore nel test dei parametri Bitfinex: {str(e)}")
            return {
                "success": False,
                "error": f"Errore nel test: {str(e)}",
                "fallback_params": {
                    "network": "SOL",
                    "method": "tetherusdtsol"
                }
            }

    def get_available_transfer_routes(self):
        """
        Ottiene tutte le rotte di trasferimento disponibili
        
        Returns:
            dict: Dizionario con tutte le rotte disponibili e i relativi metodi
        """
        return {
            "routes": {
                "bybit_to_bitmex": {
                    "method": "transfer_bybit_to_bitmex",
                    "description": "Trasferisce USDT da ByBit a BitMEX via Solana",
                    "network": "Solana (SOL)",
                    "from_exchange": "ByBit",
                    "to_exchange": "BitMEX"
                },
                "bitmex_to_bybit": {
                    "method": "transfer_bitmex_to_bybit", 
                    "description": "Trasferisce USDT da BitMEX a ByBit via Solana",
                    "network": "Solana (SOL)",
                    "from_exchange": "BitMEX",
                    "to_exchange": "ByBit"
                },
                "bitfinex_to_bybit": {
                    "method": "transfer_bitfinex_to_bybit",
                    "description": "Trasferisce USDT da Bitfinex a ByBit via Solana",
                    "network": "Solana (SOL)",
                    "from_exchange": "Bitfinex",
                    "to_exchange": "ByBit",
                    "supports_wallets": ["margin", "exchange", "funding"]
                },
                "bitfinex_to_bitmex": {
                    "method": "transfer_bitfinex_to_bitmex",
                    "description": "Trasferisce USDT da Bitfinex a BitMEX via Solana", 
                    "network": "Solana (SOL)",
                    "from_exchange": "Bitfinex",
                    "to_exchange": "BitMEX",
                    "supports_wallets": ["margin", "exchange", "funding"]
                },
                "bybit_to_bitfinex": {
                    "method": "transfer_bybit_to_bitfinex",
                    "description": "Trasferisce USDT da ByBit a Bitfinex via Solana",
                    "network": "Solana (SOL)", 
                    "from_exchange": "ByBit",
                    "to_exchange": "Bitfinex",
                    "note": "I fondi arrivano nel wallet exchange di Bitfinex"
                },
                "bitmex_to_bitfinex": {
                    "method": "transfer_bitmex_to_bitfinex",
                    "description": "Trasferisce USDT da BitMEX a Bitfinex via Solana",
                    "network": "Solana (SOL)",
                    "from_exchange": "BitMEX", 
                    "to_exchange": "Bitfinex",
                    "note": "I fondi arrivano nel wallet exchange di Bitfinex"
                }
            },
            "supported_networks": {
                "Solana": {
                    "code": "SOL",
                    "bitfinex_method": "tetherusdtsol",
                    "bitfinex_network": "SOL",  # Anche network è richiesto
                    "bybit_param": "chain",
                    "bitmex_param": "network",
                    "fast": True,
                    "low_fees": True
                }
            },
            "exchanges": {
                "bybit": {
                    "name": "ByBit",
                    "withdrawal_param": "chain",
                    "internal_transfer_required": True,
                    "from_account": "unified",
                    "to_account": "funding"
                },
                "bitmex": {
                    "name": "BitMEX", 
                    "withdrawal_param": "network",
                    "internal_transfer_required": False
                },
                "bitfinex": {
                    "name": "Bitfinex",
                    "withdrawal_param": "method",
                    "network_param": "network",  # CCXT richiede anche questo
                    "internal_transfer_required": True,
                    "wallet_currencies": {
                        "margin": "USTF0",
                        "exchange": "UST",
                        "funding": "UST"
                    }
                }
            }
        }