"""
CCXT API Wrapper - Checkpoint Version 3.0 (Codice Pulito)
Data: 15/05/2025
"""

import ccxt
import os
from dotenv import load_dotenv
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ccxt_api')

class CCXTAPI:
    def __init__(self, exchange_id='bybit', api_key=None, api_secret=None, testnet=False):
        """
        Inizializza la connessione con l'exchange tramite CCXT.
        """
        self.exchange_id = exchange_id
        
        if api_key is None or api_secret is None:
            load_dotenv()
            api_key = os.getenv(f"{exchange_id.upper()}_API_KEY")
            api_secret = os.getenv(f"{exchange_id.upper()}_API_SECRET")
        
        options = {
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'timeout': 30000,
            'adjustForTimeDifference': True,
        }
        
        if testnet:
            if exchange_id == 'bybit':
                options['urls'] = {
                    'api': {
                        'public': 'https://api-testnet.bybit.com',
                        'private': 'https://api-testnet.bybit.com',
                    }
                }
            elif exchange_id == 'bitmex':
                options['urls'] = {
                    'api': 'https://testnet.bitmex.com',
                }
        
        if exchange_id == 'bitfinex':
            options['options'] = {
                'createMarketBuyOrderRequiresPrice': True,
            }
            
            if api_key and api_secret:
                logger.info(f"Impostazione credenziali API per {exchange_id}")
            else:
                logger.warning(f"API key o secret mancanti per {exchange_id}")
                
            options['timeout'] = 60000
            options['dns'] = ['8.8.8.8', '8.8.4.4']
        elif exchange_id == 'bitmex':
            options['options'] = {
                'defaultType': 'swap',
            }
        elif exchange_id == 'bybit':
            options['options'] = {
                'defaultType': 'swap',
            }
        
        try:
            exchange_class = getattr(ccxt, exchange_id)
            self.exchange = exchange_class(options)
            logger.info(f"Connessione a {exchange_id} inizializzata")
            
            self.load_markets()
        except Exception as e:
            logger.error(f"Errore durante l'inizializzazione dell'exchange {exchange_id}: {str(e)}")
            raise
    
    def load_markets(self, reload=False):
        """Carica i mercati disponibili sull'exchange"""
        try:
            markets = self.exchange.load_markets(reload=reload)
            logger.info(f"Mercati caricati: {len(markets)} simboli disponibili")
            return markets
        except Exception as e:
            logger.error(f"Errore nel caricamento dei mercati: {str(e)}")
            raise
    
    def get_perpetual_futures(self):
        """Ottiene la lista dei futures perpetui disponibili"""
        try:
            markets = self.exchange.markets
            perpetual_futures = []
            
            if self.exchange_id == 'bitfinex':
                for symbol, market in markets.items():
                    if 'F0:' in symbol:
                        perpetual_futures.append(symbol)
                
                has_solana = any('SOL' in s.upper() and 'F0:' in s for s in perpetual_futures)
                if not has_solana:
                    sol_formats = ["tSOLF0:USTF0", "tSOLF0:USDF0", "tSOL:USTF0", "tSOLF0:UST0"]
                    
                    for sol_format in sol_formats:
                        logger.info(f"Aggiunto simbolo SOLANA per Bitfinex: {sol_format}")
                        perpetual_futures.append(sol_format)
            elif self.exchange_id in ['bitmex', 'bybit']:
                for symbol, market in markets.items():
                    if market.get('linear') and 'USDT' in symbol:
                        perpetual_futures.append(symbol)
            else:
                for symbol, market in markets.items():
                    if market.get('swap') or (market.get('linear') and market.get('futures')):
                        perpetual_futures.append(symbol)
            
            logger.info(f"Trovati {len(perpetual_futures)} futures perpetui")
            return perpetual_futures
        except Exception as e:
            logger.error(f"Errore nel recuperare futures perpetui: {str(e)}")
            return []
    
    def get_instrument_info(self, symbol):
        """Ottiene informazioni dettagliate su uno strumento."""
        try:
            if not hasattr(self.exchange, 'markets') or not self.exchange.markets:
                self.load_markets()
            
            if symbol in self.exchange.markets:
                market = self.exchange.markets[symbol]
                
                info = {
                    'symbol': symbol,
                    'base': market.get('base'),
                    'quote': market.get('quote'),
                    'active': market.get('active', False),
                    'precision': market.get('precision'),
                    'limits': market.get('limits'),
                    'linear': market.get('linear', False),
                    'inverse': market.get('inverse', False),
                    'contractSize': market.get('contractSize', 1)
                }
                
                if self.exchange_id == 'bitmex':
                    if 'info' in market:
                        raw_info = market['info']
                        for key in ['minOrderQty', 'maxOrderQty', 'underlyingToPositionMultiplier', 'underlyingToSettleMultiplier']:
                            if key in raw_info:
                                info[key] = raw_info[key]
                
                return info
            else:
                logger.warning(f"Simbolo {symbol} non trovato")
                return None
        except Exception as e:
            logger.error(f"Errore nel recuperare informazioni strumento: {str(e)}")
            return None
    
    def submit_order(self, symbol, amount, price=None, market=True, params={}):
        """Invia un ordine di trading"""
        try:
            if not self.exchange.apiKey or not self.exchange.secret:
                logger.error(f"API key o secret non configurati per {self.exchange_id}")
                return {"error": f"API key o secret non configurati per {self.exchange_id}"}
            
            if self.exchange_id == 'bitfinex':
                if 'SOL' in symbol.upper() and not 'F0:' in symbol:
                    symbol = "tSOLF0:USTF0"
                elif not symbol.startswith('t'):
                    symbol = 't' + symbol
                
                custom_params = params.copy() if params else {}
                if 'lev' not in custom_params:
                    custom_params['lev'] = 5
                
                try:
                    side = 'buy' if amount > 0 else 'sell'
                    abs_amount = abs(amount)
                    order_type = 'market' if market else 'limit'
                    
                    if order_type == 'market':
                        if side == 'buy':
                            response = self.exchange.create_market_buy_order(symbol, abs_amount, params=custom_params)
                        else:
                            response = self.exchange.create_market_sell_order(symbol, abs_amount, params=custom_params)
                    else:
                        if side == 'buy':
                            response = self.exchange.create_limit_buy_order(symbol, abs_amount, price, params=custom_params)
                        else:
                            response = self.exchange.create_limit_sell_order(symbol, abs_amount, price, params=custom_params)
                    
                    return response
                
                except Exception as e:
                    logger.error(f"Errore CCXT: {str(e)}")
                    
                    try:
                        from bitfinex_api import BitfinexAPI
                        api_key = os.getenv("BITFINEX_API_KEY")
                        api_secret = os.getenv("BITFINEX_API_SECRET")
                        
                        if not api_key or not api_secret:
                            return {"error": "API key o secret mancanti per Bitfinex"}
                        
                        bitfinex_api = BitfinexAPI(api_key, api_secret)
                        bitfinex_amount = amount
                        
                        bitfinex_params = {"lev": 5}
                        
                        if hasattr(bitfinex_api, 'submit_order_with_params'):
                            response = bitfinex_api.submit_order_with_params(symbol, bitfinex_amount, price, market, bitfinex_params)
                        else:
                            logger.warning("API nativa senza supporto per leva, usando metodo standard")
                            response = bitfinex_api.submit_order(symbol, bitfinex_amount, price, market)
                        
                        if "error" in response:
                            return {"error": response["error"]}
                        
                        return response
                    except Exception as native_err:
                        return {"error": f"Errore con entrambe le implementazioni: {str(e)} | {str(native_err)}"}
            
            try:
                market_info = self.exchange.market(symbol)
            except Exception as e:
                return {"error": f"Simbolo non trovato: {symbol}"}
            
            order_type = 'market' if market else 'limit'
            side = 'buy' if amount > 0 else 'sell'
            abs_amount = abs(amount)
            
            custom_params = params.copy()
            
            if self.exchange_id == 'bitmex':
                if market_info.get('linear', False):
                    custom_params['reduceOnly'] = False
                
                if 'SOL' in symbol.upper():
                    if abs_amount < 1000:
                        abs_amount = 1000
                    
                    if abs_amount % 1000 != 0:
                        abs_amount = (abs_amount // 1000) * 1000
            
            # Gestione specifica per ByBit con SOLANA
            elif self.exchange_id == 'bybit':
                if 'SOL' in symbol.upper() and not 'LAYER' in symbol.upper():
                    # Verifica che si tratti effettivamente di SOLANA e non di altri token simili
                    if (symbol == "SOLUSDT" or 
                        symbol == "SOL/USDT" or 
                        symbol.upper() == "SOL" or 
                        (symbol.startswith("SOL") and not any(x in symbol.upper() for x in ["SOLO", "SOLAYER", "SOLA"]))):
                        
                        # Per sicurezza, imposta esplicitamente il simbolo corretto
                        symbol = "SOLUSDT"
                        logger.info(f"ByBit: Conversione simbolo a SOLUSDT (Solana)")
                        
                        # Nessuna forzatura della quantità minima - lasciamo che sia l'API a gestire
                        # i limiti di precisione, come indicato nella documentazione
                        logger.info(f"ByBit: Utilizzo quantità esatta per SOLANA: {abs_amount}")
            
            if order_type == 'market':
                if market_info['type'] == 'spot' and side == 'buy' and price is None:
                    orderbook = self.exchange.fetch_order_book(symbol)
                    price = orderbook['asks'][0][0] * 1.01
                
                result = self.exchange.create_order(
                    symbol=symbol,
                    type=order_type,
                    side=side,
                    amount=abs_amount,
                    price=price,
                    params=custom_params
                )
            else:
                result = self.exchange.create_order(
                    symbol=symbol,
                    type=order_type,
                    side=side,
                    amount=abs_amount,
                    price=price,
                    params=custom_params
                )
            
            return result
        except ccxt.InsufficientFunds as e:
            return {"error": f"Fondi insufficienti: {str(e)}"}
        except ccxt.InvalidOrder as e:
            return {"error": f"Ordine non valido: {str(e)}"}
        except Exception as e:
            return {"error": f"Errore nell'invio dell'ordine: {str(e)}"}
    
    def get_account_info(self):
        """Ottiene informazioni sull'account e sui saldi"""
        try:
            if not self.exchange.apiKey or not self.exchange.secret:
                return {"error": f"API key o secret non configurati per {self.exchange_id}"}
            
            max_retries = 3
            retry_delay = 2
            
            for attempt in range(max_retries):
                try:
                    balances = self.exchange.fetch_balance()
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Tentativo {attempt+1} fallito. Nuovo tentativo tra {retry_delay} secondi...")
                        time.sleep(retry_delay)
                    else:
                        return {"error": f"Errore nel recuperare informazioni account: {str(e)}"}
            
            if self.exchange_id == 'bitfinex':
                if 'total' in balances:
                    positive_balances = {asset: amount for asset, amount in balances['total'].items() if amount > 0}
                    
                    return {
                        'balances': positive_balances,
                        'detail': balances
                    }
            elif self.exchange_id == 'bitmex':
                try:
                    positions = self.exchange.fetch_positions()
                    return {
                        'balances': balances,
                        'positions': positions
                    }
                except Exception as pos_error:
                    logger.warning(f"Non è stato possibile recuperare le posizioni")
            
            if 'total' in balances:
                positive_balances = {asset: amount for asset, amount in balances['total'].items() if amount > 0}
                
                return {
                    'balances': positive_balances,
                    'detail': balances
                }
            else:
                return balances
        except Exception as e:
            return {"error": f"Errore nel recuperare informazioni account: {str(e)}"}

    def set_position_parameters(self, symbol, leverage=5, margin_mode='isolated'):
        """Imposta i parametri della posizione (leva, tipo di margine)"""
        try:
            if not self.exchange.apiKey or not self.exchange.secret:
                return {"error": f"API key o secret non configurati per {self.exchange_id}"}
            
            # Impostazione del tipo di margine (cross/isolated)
            try:
                if margin_mode in ['cross', 'isolated']:
                    self.exchange.set_margin_mode(margin_mode, symbol)
                else:
                    return {"error": f"Tipo di margine non valido: {margin_mode}. Usare 'cross' o 'isolated'"}
            except Exception as e:
                logger.warning(f"Non è stato possibile impostare il tipo di margine: {str(e)}")
            
            # Impostazione della leva
            try:
                if leverage > 0:
                    result = self.exchange.set_leverage(leverage, symbol)
                    return {"success": True, "message": f"Leva impostata a {leverage}x", "details": result}
                else:
                    return {"error": f"Valore di leva non valido: {leverage}. Deve essere positivo"}
            except Exception as e:
                logger.error(f"Errore nell'impostare la leva: {str(e)}")
                return {"error": f"Errore nell'impostare la leva: {str(e)}"}
                
        except Exception as e:
            logger.error(f"Errore nell'impostare i parametri della posizione: {str(e)}")
            return {"error": f"Errore nell'impostare i parametri della posizione: {str(e)}"}
            
    def adjust_position_margin(self, symbol, amount, params={}):
        """Aggiunge o rimuove margine da una posizione."""
        try:
            if not self.exchange.apiKey or not self.exchange.secret:
                logger.error(f"API key o secret non configurati per {self.exchange_id}")
                return {"error": f"API key o secret non configurati per {self.exchange_id}"}
            
            # Log del tentativo di modifica margine
            direction = "aggiunta" if amount > 0 else "rimozione"
            logger.info(f"Tentativo di {direction} margine per {symbol} su {self.exchange_id}, importo: {amount}")
            
            # BitMEX ha un endpoint specifico per transferMargin
            if self.exchange_id == 'bitmex':
                try:
                    # Per BitMEX usiamo la chiamata API diretta
                    api_key = self.exchange.apiKey
                    api_secret = self.exchange.secret
                    
                    # Caso speciale per BitMEX: se stiamo aggiungendo margine, dobbiamo usare la posizione SOLUSDT
                    # che accetta USDT come valuta di margine
                    if 'SOL' in symbol.upper() and amount > 0:
                        # Controlla se esiste una posizione attiva per SOLUSDT
                        try:
                            from bitmex_api import BitMEXAPI
                            bitmex_api = BitMEXAPI()
                            positions = bitmex_api.get_open_positions('SOLUSDT')
                            
                            # Se c'è una posizione attiva per SOLUSDT (currentQty != 0), usa quella
                            for pos in positions:
                                pos_symbol = pos.get('symbol', '')
                                pos_qty = pos.get('currentQty', 0)
                                pos_currency = pos.get('currency', '')
                                
                                if pos_symbol == 'SOLUSDT' and pos_qty != 0:
                                    logger.info(f"Trovata posizione attiva SOLUSDT con qty={pos_qty}, currency={pos_currency}")
                                    symbol = 'SOLUSDT'
                                    break
                        except Exception as e:
                            logger.warning(f"Errore nel controllare le posizioni SOLUSDT: {str(e)}")
                            # In caso di errore, forziamo comunque l'uso di SOLUSDT per aggiungere margine in USDT
                            if amount > 0:
                                symbol = 'SOLUSDT'
                    
                    logger.info(f"Simbolo finale utilizzato per BitMEX: {symbol}")
                    
                    # Per BitMEX: passiamo l'importo USDT direttamente al metodo _bitmex_transfer_margin_direct,
                    # che si occuperà di convertirlo in satoshi secondo le necessità dell'API
                    # Nota che questo è un cambio rispetto alla precedente implementazione dove convertivamo qui
                    result = self._bitmex_transfer_margin_direct(api_key, api_secret, symbol, amount)
                    
                    # Log del risultato
                    if "success" in result and result["success"]:
                        logger.info(f"Modifica margine BitMEX riuscita per {symbol}")
                    else:
                        logger.error(f"Errore nella modifica margine BitMEX: {result.get('error', 'Errore sconosciuto')}")
                        
                    return result
                except Exception as e:
                    logger.error(f"Errore nel trasferimento margine BitMEX: {str(e)}")
                    return {"error": f"Errore nel trasferimento margine BitMEX: {str(e)}"}
            
            # Implementa la CCXT API se disponibile per l'exchange
            if hasattr(self.exchange, 'transfer_margin'):
                try:
                    result = self.exchange.transfer_margin(symbol, amount, params)
                    return {"success": True, "data": result}
                except Exception as e:
                    logger.error(f"Errore CCXT nel trasferimento margine: {str(e)}")
                    return {"error": f"Errore CCXT nel trasferimento margine: {str(e)}"}
            
            # Per Bitfinex, usa l'API diretta
            if self.exchange_id == 'bitfinex':
                try:
                    from bitfinex_api import BitfinexAPI
                    bitfinex = BitfinexAPI()
                    
                    if 'F0:' not in symbol and not symbol.startswith('t'):
                        # Converti il simbolo al formato Bitfinex se necessario
                        if 'SOL' in symbol.upper():
                            symbol = "tSOLF0:USTF0"
                    
                    logger.info(f"Modifica margine Bitfinex: simbolo={symbol}, importo={amount}")
                    # Utilizziamo il metodo corretto che esiste nella classe BitfinexAPI
                    result = bitfinex.set_position_collateral(symbol, amount)
                    return result
                except Exception as e:
                    logger.error(f"Errore nel trasferimento margine Bitfinex: {str(e)}")
                    return {"error": f"Errore nel trasferimento margine Bitfinex: {str(e)}"}
            
            # Per ByBit, usa l'API diretta
            if self.exchange_id == 'bybit':
                try:
                    from bybit_api import ByBitAPI
                    bybit = ByBitAPI()
                    
                    # Normalizza il simbolo al formato ByBit
                    if 'SOL' in symbol.upper() and 'USDT' not in symbol:
                        symbol = 'SOLUSDT'
                    
                    logger.info(f"Modifica margine ByBit: simbolo={symbol}, importo={amount}")
                    result = bybit.adjust_position_margin(symbol, amount)
                    return result
                except Exception as e:
                    logger.error(f"Errore nel trasferimento margine ByBit: {str(e)}")
                    return {"error": f"Errore nel trasferimento margine ByBit: {str(e)}"}
            
            # Nessun metodo disponibile per l'exchange corrente
            return {"error": f"Modifica margine non supportata per {self.exchange_id}"}
        
        except Exception as e:
            logger.error(f"Errore generale nella modifica del margine: {str(e)}")
            return {"error": f"Errore generale nella modifica del margine: {str(e)}"}
            
    def close_position(self, symbol, position_size=None, params={}):
        """Chiude una posizione aperta utilizzando ccxt.
        
        Args:
            symbol (str): Simbolo della posizione da chiudere
            position_size (float, optional): Size della posizione da chiudere
            params (dict, optional): Parametri aggiuntivi specifici per exchange
            
        Returns:
            dict: Risultato dell'operazione
        """
        try:
            if not self.exchange.apiKey or not self.exchange.secret:
                logger.error(f"API key o secret non configurati per {self.exchange_id}")
                return {"error": f"API key o secret non configurati per {self.exchange_id}"}
            
            logger.info(f"Chiusura posizione su {self.exchange_id} per {symbol}")
            
            # BitMEX: usiamo il metodo closePosition di CCXT se disponibile
            if self.exchange_id == 'bitmex':
                try:
                    # Verifichiamo se CCXT supporta il metodo closePosition (disponibile in versioni recenti)
                    if hasattr(self.exchange, 'privatePostOrderClosePosition'):
                        logger.info(f"Utilizzo del metodo nativo closePosition di CCXT per BitMEX")
                        
                        # Normalizza il simbolo, se necessario
                        if 'SOL' in symbol.upper() and '/' in symbol:
                            # Rimuovi la barra e il suffisso USDT
                            symbol_parts = symbol.split('/')
                            base = symbol_parts[0]
                            normalized_symbol = f"{base}USDT"
                            logger.info(f"Simbolo normalizzato per closePosition: {symbol} -> {normalized_symbol}")
                            symbol = normalized_symbol
                        
                        # Chiudi la posizione usando il metodo nativo CCXT
                        result = self.exchange.privatePostOrderClosePosition({
                            'symbol': symbol
                        })
                        
                        logger.info(f"Risultato closePosition CCXT: {result}")
                        return {"success": True, "result": result, "method": "ccxt_closePosition"}
                except Exception as e:
                    logger.error(f"Errore con il metodo closePosition di CCXT: {str(e)}")
                    # Continuiamo con gli altri metodi in caso di errore
                
                # Fallback al metodo dell'API diretta BitMEX
                try:
                    from bitmex_api import BitMEXAPI
                    bitmex = BitMEXAPI()
                    
                    # Normalizza il simbolo
                    symbol_normalized = symbol
                    if 'SOL' in symbol.upper():
                        if '/' in symbol:
                            symbol_normalized = "SOLUSDT"
                        elif ':' in symbol:
                            symbol_normalized = "SOLUSDT"
                    
                    logger.info(f"Fallback a BitMEXAPI per chiudere posizione: {symbol_normalized}")
                    result = bitmex.close_position(symbol_normalized)
                    
                    if isinstance(result, dict) and "error" in result:
                        # Prova anche con SOLUSD come ulteriore fallback
                        if 'SOL' in symbol.upper():
                            try:
                                logger.info("Tentativo con simbolo SOLUSD come fallback")
                                result_alt = bitmex.close_position("SOLUSD")
                                if "error" not in result_alt:
                                    return {"success": True, "result": result_alt, "method": "bitmex_api_solusd"}
                            except Exception as alt_err:
                                logger.error(f"Errore anche con SOLUSD: {str(alt_err)}")
                                
                        return {"error": result["error"]}
                    
                    return {"success": True, "result": result, "method": "bitmex_api"}
                except Exception as e:
                    logger.error(f"Errore con BitMEXAPI: {str(e)}")
            
            # Per ByBit, implementazione migliorata
            if self.exchange_id == 'bybit':
                try:
                    # Prima tentiamo di usare l'API CCXT per ByBit
                    logger.info(f"Tentativo di chiusura posizione ByBit per {symbol} con CCXT")
                    # Normalizza il simbolo per gestire formato SOLUSDTPerp
                    normalized_symbol = symbol
                    
                    # Elimina il suffisso "Perp" se presente nel simbolo passato
                    if "Perp" in symbol:
                        normalized_symbol = symbol.replace("Perp", "")
                        logger.info(f"Simbolo normalizzato da {symbol} a {normalized_symbol}")
                    
                    # Gestione dei simboli con "/" (es. SOL/USDT)
                    if "/" in normalized_symbol:
                        base, quote = normalized_symbol.split("/")
                        normalized_symbol = f"{base}{quote}"
                        logger.info(f"Simbolo normalizzato da formato con barra a {normalized_symbol}")
                    
                    # Recupera prima i dettagli della posizione
                    positions_result = self.get_open_positions()
                    
                    if not positions_result or not positions_result.get("positions"):
                        return {"error": f"Nessuna posizione aperta trovata su ByBit"}
                    
                    # Cerca la posizione in modo flessibile
                    position = None
                    # Lista di formati possibili per il simbolo SOL
                    possible_symbols = [
                        normalized_symbol,        # SOLUSDt
                        symbol,                   # Simbolo originale 
                        normalized_symbol+"Perp", # SOLUSDTPerp
                        "SOL/USDT",               # SOL/USDT
                        "SOLUSDT",                # SOLUSDT
                        "SOLUSDTPerp",            # SOLUSDTPerp
                        "SOL/USDT:USDT"           # Nuovo formato rilevato nel debug
                    ]
                    
                    
                    # Cerca la posizione con qualsiasi dei simboli possibili
                    for pos in positions_result.get("positions", []):
                        pos_symbol = pos.get('symbol', '')
                        logger.info(f"Confronto posizione: {pos_symbol}")
                        
                        # Controllo base sul simbolo della posizione
                        if pos_symbol in possible_symbols:
                            position = pos
                            logger.info(f"Posizione trovata con simbolo {pos_symbol}")
                            break
                        
                        # Controllo più flessibile - verifica se il simbolo contiene 'SOL' per SOLANA
                        if 'SOL' in symbol.upper() and 'SOL' in pos_symbol.upper():
                            # Verifica che non sia un altro token simile come SOLANA, SOLO, ecc.
                            if not any(x in pos_symbol.upper() for x in ["SOLO", "SOLAYER", "SOLA"]):
                                position = pos
                                logger.info(f"Posizione trovata con simbolo simile {pos_symbol}")
                                break
                    
                    if not position:
                        # Se position è ancora None, logga tutte le posizioni per debug
                        logger.error(f"Posizione non trovata. Posizioni disponibili:")
                        for pos in positions_result.get("positions", []):
                            pos_sym = pos.get('symbol', '')
                            logger.error(f"  - {pos_sym}")
                        return {"error": f"Posizione {symbol} non trovata su ByBit"}
                    
                    # Usa il simbolo effettivo della posizione trovata
                    actual_symbol = position.get('symbol')
                    logger.info(f"Usando simbolo effettivo: {actual_symbol}")
                    
                    # Gestione speciale per il formato SOL/USDT:USDT
                    if actual_symbol == "SOL/USDT:USDT":
                        # Per l'ordine di chiusura potremmo dover usare un formato diverso
                        # Proviamo prima con il formato originale
                        order_symbol = actual_symbol
                        # Se necessario, proveremo anche questi formati come fallback
                        alternative_symbols = ["SOL/USDT", "SOLUSDT"]
                    else:
                        order_symbol = actual_symbol
                        alternative_symbols = []
                    
                    # Determina il lato opposto per la chiusura
                    side = position.get('side')
                    close_side = 'sell' if side == 'long' else 'buy'
                    
                    # Ottieni la size corretta
                    size = abs(float(position.get('contracts', 0) or 0))
                    if size <= 0:
                        return {"error": f"Dimensione della posizione non valida: {size}"}
                    
                    # Se è stato specificato position_size, usa quello invece della size completa
                    if position_size is not None:
                        original_size = size
                        size = min(abs(float(position_size)), size)
                        logger.info(f"Utilizzo dimensione specificata: {size}")
                    
                    logger.info(f"Chiusura posizione ByBit: {actual_symbol}, {side}, size: {size}, close_side: {close_side}")
                    
                    # Parametri specifici per ByBit
                    custom_params = {
                        'reduceOnly': True,
                        'closeOnTrigger': True  # Parametro specifico ByBit per garantire la chiusura
                    }
                    
                    # Aggiungi eventuali parametri extra passati
                    if params:
                        custom_params.update(params)
                    
                    # Ottieni il ticker per ottenere l'ultimo prezzo (per ordini limit in caso di fallback)
                    ticker = None
                    try:
                        ticker = self.exchange.fetch_ticker(actual_symbol)
                    except Exception as e:
                        logger.warning(f"Impossibile ottenere ticker per {actual_symbol}: {str(e)}")
                    
                    # Invia l'ordine di mercato per chiudere la posizione
                    try:
                        try:
                            order = self.exchange.create_market_order(
                                symbol=actual_symbol,
                                side=close_side,
                                amount=size,
                                params=custom_params
                            )
                            
                            logger.info(f"Posizione ByBit chiusa con successo (mercato): {order}")
                            return {"success": True, "order": order, "method": "ccxt_market_order"}
                        except Exception as primary_error:
                            # Se l'ordine fallisce con il simbolo primario e abbiamo alternative, proviamo con quelle
                            if alternative_symbols:
                                for alt_symbol in alternative_symbols:
                                    try:
                                        order = self.exchange.create_market_order(
                                            symbol=alt_symbol,
                                            side=close_side,
                                            amount=size,
                                            params=custom_params
                                        )
                                        
                                        logger.info(f"Posizione ByBit chiusa con successo (mercato) con simbolo alternativo {alt_symbol}: {order}")
                                        return {"success": True, "order": order, "method": "ccxt_market_order_alternative"}
                                    except Exception as alt_error:
                                        continue
                                
                                # Se arriviamo qui, tutti i simboli alternativi hanno fallito
                                # Continuiamo con il fallback agli ordini limit
                            else:
                                # Nessuna alternativa, risolleva l'errore originale
                                raise primary_error
                    except Exception as market_error:
                        logger.warning(f"Errore con ordine a mercato: {str(market_error)}, tentativo con limit")
                        
                        # Fallback a ordine limit se l'ordine di mercato fallisce
                        if ticker:
                            # Calcola un prezzo leggermente svantaggioso per garantire l'esecuzione
                            last_price = ticker['last']
                            # Se compriamo (per chiudere uno short), prezzo leggermente più alto
                            # Se vendiamo (per chiudere un long), prezzo leggermente più basso
                            price_modifier = 1.005 if close_side == 'buy' else 0.995
                            limit_price = last_price * price_modifier
                            
                            try:
                                try:
                                    order = self.exchange.create_limit_order(
                                        symbol=actual_symbol,
                                        side=close_side,
                                        amount=size,
                                        price=limit_price,
                                        params=custom_params
                                    )
                                    
                                    logger.info(f"Posizione ByBit chiusa con successo (limit): {order}")
                                    return {"success": True, "order": order, "method": "ccxt_limit_order"}
                                except Exception as primary_limit_error:
                                    # Se l'ordine limit fallisce con il simbolo primario e abbiamo alternative, proviamo con quelle
                                    if alternative_symbols:
                                        for alt_symbol in alternative_symbols:
                                            try:
                                                order = self.exchange.create_limit_order(
                                                    symbol=alt_symbol,
                                                    side=close_side,
                                                    amount=size,
                                                    price=limit_price,
                                                    params=custom_params
                                                )
                                                
                                                logger.info(f"Posizione ByBit chiusa con successo (limit) con simbolo alternativo {alt_symbol}: {order}")
                                                return {"success": True, "order": order, "method": "ccxt_limit_order_alternative"}
                                            except Exception as alt_limit_error:
                                                continue
                                        
                                        # Se arriviamo qui, tutti i simboli alternativi hanno fallito
                                        raise Exception(f"Errore con tutti i tentativi di ordine limit: {str(primary_limit_error)}")
                                    else:
                                        # Nessuna alternativa, risolleva l'errore originale
                                        raise primary_limit_error
                            except Exception as limit_error:
                                raise Exception(f"Errore sia con ordine mercato che limit: {str(market_error)} | {str(limit_error)}")
                        else:
                            raise market_error
                except Exception as e:
                    logger.error(f"Errore nella chiusura posizione ByBit con CCXT: {str(e)}")
                    
                    # Fallback alla API nativa di ByBit
                    try:
                        from bybit_api import ByBitAPI
                        bybit = ByBitAPI()
                        logger.info(f"Tentativo chiusura con API nativa ByBit per {symbol}")
                        
                        if position:
                            # Se abbiamo informazioni sulla posizione, usiamole per l'API nativa
                            pos_symbol = position.get('symbol')
                            pos_side = position.get('side')
                            pos_size = abs(float(position.get('contracts', 0) or 0))
                            
                            
                            # Per SOL/USDT:USDT proviamo anche con altre forme
                            symbols_to_try = [pos_symbol]
                            if pos_symbol == "SOL/USDT:USDT":
                                symbols_to_try.extend(["SOL/USDT", "SOLUSDT"])
                            
                            exception = None
                            for sym in symbols_to_try:
                                try:
                                    result = bybit.close_position(sym)
                                    if isinstance(result, dict) and "error" in result:
                                        exception = Exception(result["error"])
                                        continue
                                    
                                    return {"success": True, "result": result, "method": f"bybit_api_sym_{sym}"}
                                except Exception as e:
                                    exception = e
                                    continue
                            
                            # Se tutti i simboli falliscono, prova il metodo diretto create_order
                            try:
                                opposite_side = "Sell" if pos_side == "long" else "Buy"
                                order_result = bybit.create_order(
                                    symbol=pos_symbol,
                                    side=opposite_side, 
                                    order_type="Market",
                                    qty=pos_size,
                                    reduce_only=True
                                )
                                return {"success": True, "result": order_result, "method": "bybit_api_direct_order"}
                            except Exception as direct_e:
                                if exception:
                                    raise exception
                                else:
                                    raise direct_e
                        else:
                            # Nessuna informazione sulla posizione, usa il metodo standard
                            result = bybit.close_position(symbol)
                            return {"success": True, "result": result, "method": "bybit_api"}
                    except Exception as native_err:
                        logger.error(f"Errore anche con API nativa ByBit: {str(native_err)}")
                        return {"error": f"Impossibile chiudere la posizione su ByBit: {str(native_err)}"}
            
            # Per Bitfinex, utilizziamo la sua API diretta
            if self.exchange_id == 'bitfinex':
                try:
                    from bitfinex_api import BitfinexAPI
                    bitfinex = BitfinexAPI()
                    
                    # Converti il simbolo al formato Bitfinex se necessario
                    if 'F0:' not in symbol and not symbol.startswith('t'):
                        if 'SOL' in symbol.upper():
                            symbol = "tSOLF0:USTF0"
                    
                    result = bitfinex.close_position(symbol)
                    return {"success": True, "result": result, "method": "bitfinex_api"}
                except Exception as e:
                    logger.error(f"Errore nella chiusura posizione Bitfinex: {str(e)}")
                    # Continuiamo con CCXT in caso di errore
            
            # Recupera le posizioni aperte per ottenere i dettagli
            positions = self.get_open_positions(symbol)
            if not positions or "positions" not in positions or not positions["positions"]:
                return {"error": f"Nessuna posizione aperta trovata per {symbol}"}
            
            # Trova la posizione specifica
            position = None
            for pos in positions["positions"]:
                if pos.get('symbol') == symbol:
                    position = pos
                    break
            
            if not position:
                return {"error": f"Posizione {symbol} non trovata"}
            
            # Determina il lato e la quantità per la chiusura
            side = position.get('side')
            close_side = 'sell' if side == 'long' else 'buy'
            
            # Usa la dimensione specificata o la dimensione completa della posizione
            size = abs(float(position_size)) if position_size is not None else abs(float(position.get('contracts', 0)))
            
            if size <= 0:
                return {"error": f"Dimensione della posizione non valida: {size}"}
            
            # Assicurati che reduceOnly sia impostato
            custom_params = params.copy() if params else {}
            if 'reduceOnly' not in custom_params and 'reduce_only' not in custom_params:
                if self.exchange_id in ['bitmex', 'bybit']:
                    custom_params['reduceOnly'] = True
                else:
                    custom_params['reduce_only'] = True
            
            # Invia l'ordine di mercato per chiudere la posizione
            order = self.exchange.create_market_order(
                symbol=symbol,
                side=close_side,
                amount=size,
                params=custom_params
            )
            
            return {"success": True, "order": order, "method": "ccxt_market_order"}
        except Exception as e:
            error_message = str(e)
            logger.error(f"Errore nella chiusura posizione: {error_message}")
            
            # Metodi alternativi di fallback per exchange specifici
            try:
                if self.exchange_id == 'bitmex':
                    from bitmex_api import BitMEXAPI
                    bitmex = BitMEXAPI()
                    
                    if 'SOL' in symbol.upper():
                        # Tenta con SOLUSDT
                        try:
                            result = bitmex.close_position("SOLUSDT")
                            if not isinstance(result, dict) or "error" not in result:
                                return {"success": True, "result": result, "method": "bitmex_api_fallback_solusdt"}
                        except:
                            # Se fallisce, tenta con SOLUSD
                            try:
                                result = bitmex.close_position("SOLUSD")
                                return {"success": True, "result": result, "method": "bitmex_api_fallback_solusd"}
                            except:
                                pass
                    else:
                        result = bitmex.close_position(symbol)
                        return {"success": True, "result": result, "method": "bitmex_api_fallback"}
                elif self.exchange_id == 'bybit':
                    from bybit_api import ByBitAPI
                    bybit = ByBitAPI()
                    
                    # Normalizza il simbolo se necessario
                    normalized_symbol = symbol
                    if '/' in symbol:
                        parts = symbol.split('/')
                        normalized_symbol = parts[0] + parts[1]
                    
                    # Gestisci formato con "Perp"
                    original_normalized = normalized_symbol
                    if "Perp" in normalized_symbol:
                        normalized_symbol = normalized_symbol.replace("Perp", "")
                    
                    logger.info(f"Tentativo fallback con ByBitAPI per {normalized_symbol}")
                    
                    # Prova prima con il simbolo normalizzato
                    result = bybit.close_position(normalized_symbol)
                    
                    # Se fallisce, prova con diverse varianti del simbolo
                    if isinstance(result, dict) and "error" in result:
                        error_msg = result.get("error", "")
                        
                        # Prova con il formato originale se la normalizzazione è fallita
                        if "position not found" in error_msg.lower() or "size" in error_msg.lower():
                            logger.info(f"Tentativo con formato originale: {original_normalized}")
                            result_original = bybit.close_position(original_normalized)
                            
                            # Se anche questo fallisce e abbiamo "Perp", prova con il formato con "Perp"
                            if isinstance(result_original, dict) and "error" in result_original:
                                if "Perp" not in original_normalized and "position not found" in result_original.get("error", "").lower():
                                    perp_symbol = normalized_symbol + "Perp"
                                    logger.info(f"Tentativo con formato Perp esplicito: {perp_symbol}")
                                    result_perp = bybit.close_position(perp_symbol)
                                    
                                    if not isinstance(result_perp, dict) or "error" not in result_perp:
                                        return {"success": True, "result": result_perp, "method": "bybit_api_perp"}
                            else:
                                # Il formato originale ha funzionato
                                return {"success": True, "result": result_original, "method": "bybit_api_original"}
                        
                        # Caso speciale: cerca tutte le posizioni aperte e trova quella che corrisponde approssimativamente
                        if "position not found" in error_msg.lower():
                            logger.info("Tentativo di recupero posizioni con API nativa ByBit")
                            positions = bybit.get_open_positions()
                            
                            # Cerca posizioni che corrispondono approssimativamente al simbolo (es. SOL in SOLUSDT)
                            matching_position = None
                            if 'SOL' in symbol.upper():
                                for pos in positions:
                                    pos_symbol = pos.get('symbol', '')
                                    if 'SOL' in pos_symbol.upper() and not any(x in pos_symbol.upper() for x in ["SOLO", "SOLAYER", "SOLA"]):
                                        matching_position = pos
                                        logger.info(f"Trovata posizione SOL: {pos_symbol}")
                                        break
                            
                            if matching_position:
                                pos_symbol = matching_position.get('symbol', '')
                                size = float(matching_position.get('size', 0))
                                pos_side = matching_position.get('side', '')
                                
                                if size > 0:
                                    # Usa la dimensione corretta e il lato opposto
                                    close_side = 'Sell' if pos_side == 'Buy' else 'Buy'
                                    logger.info(f"Tentativo con simbolo esatto: {pos_symbol}, dimensione: {size}, lato: {close_side}")
                                    
                                    result = bybit.close_position(pos_symbol)
                                    if not isinstance(result, dict) or "error" not in result:
                                        return {"success": True, "result": result, "method": "bybit_api_exact_symbol"}
                                    
                                    # Se anche questo fallisce, prova con un ordine diretto
                                    logger.info(f"Tentativo con ordine diretto")
                                    order_result = bybit.create_order(
                                        symbol=pos_symbol,
                                        side=close_side,
                                        order_type="Market",
                                        qty=size,
                                        reduce_only=True
                                    )
                                    return {"success": True, "result": order_result, "method": "bybit_api_direct_order"}
                        
                        if "size" in error_msg.lower():
                            # Prova a ottenere le posizioni aperte direttamente dalla API nativa
                            logger.info("Tentativo di recupero posizioni con API nativa ByBit")
                            positions = bybit.get_open_positions(normalized_symbol)
                            
                            if positions and len(positions) > 0:
                                position = positions[0]
                                size = float(position.get('size', 0))
                                pos_side = position.get('side', '')
                                
                                if size > 0:
                                    # Usa la dimensione corretta e il lato opposto
                                    close_side = 'Sell' if pos_side == 'Buy' else 'Buy'
                                    logger.info(f"Nuovo tentativo con dimensione {size} e lato {close_side}")
                                    
                                    result = bybit.create_order(
                                        symbol=normalized_symbol,
                                        side=close_side,
                                        order_type="Market",
                                        qty=size,
                                        reduce_only=True
                                    )
                                    return {"success": True, "result": result, "method": "bybit_api_direct_order"}
                        
                        return {"error": f"Fallback ByBit fallito: {error_msg}"}
                    
                    return {"success": True, "result": result, "method": "bybit_api_fallback"}
                elif self.exchange_id == 'bitfinex':
                    from bitfinex_api import BitfinexAPI
                    bitfinex = BitfinexAPI()
                    result = bitfinex.close_position(symbol)
                    return {"success": True, "result": result, "method": "bitfinex_api_fallback"}
            except Exception as fallback_error:
                logger.error(f"Anche il metodo di fallback ha fallito: {str(fallback_error)}")
            
            # Ultimo tentativo con approccio generico se tutto il resto fallisce
            try:
                # Ottieni ticker per sapere il prezzo corrente
                ticker = self.exchange.fetch_ticker(symbol)
                last_price = ticker['last']
                
                # Recupera la posizione aperta
                positions = self.get_open_positions(symbol)
                if positions and positions.get("positions"):
                    for pos in positions.get("positions"):
                        if pos.get('symbol') == symbol:
                            side = pos.get('side')
                            size = abs(float(pos.get('contracts', 0) or 0))
                            
                            if size > 0:
                                close_side = 'sell' if side == 'long' else 'buy'
                                logger.info(f"Ultimo tentativo di chiusura: {symbol}, {side}, size: {size}")
                                
                                # Parametri con reduceOnly
                                params = {'reduceOnly': True}
                                
                                # Prova con ordine limit con prezzo molto aggressivo
                                price_modifier = 1.01 if close_side == 'buy' else 0.99
                                limit_price = last_price * price_modifier
                                
                                order = self.exchange.create_limit_order(
                                    symbol=symbol,
                                    side=close_side,
                                    amount=size,
                                    price=limit_price,
                                    params=params
                                )
                                
                                return {"success": True, "order": order, "method": "ccxt_limit_order_final_fallback"}
            except Exception as final_error:
                logger.error(f"Fallimento finale: {str(final_error)}")
            
            return {"error": f"Errore nella chiusura posizione: {error_message}"}

    def _bitmex_transfer_margin_direct(self, api_key, api_secret, symbol, amount):
        """
        Esegue direttamente una richiesta HTTP all'API di BitMEX per trasferire margine
        
        Args:
            api_key (str): API Key di BitMEX
            api_secret (str): API Secret di BitMEX
            symbol (str): Simbolo della posizione nel formato BitMEX (es. SOLUSDT)
            amount (int): Importo di margine da trasferire in USDT
            
        Returns:
            dict: Risultato dell'operazione con chiavi "success", "data"/"error", ecc.
        """
        import requests
        import time
        import hmac
        import hashlib
        import urllib.parse
        import json
        
        try:
            # Normalizza il simbolo per BitMEX
            normalized_symbol = symbol
            
            # Gestione del formato con barra (ad es. SOL/USDT)
            if '/' in symbol:
                base, quote = symbol.split('/')
                
                # Converti BTC a XBT se necessario (BitMEX usa XBT invece di BTC)
                if base.upper() == 'BTC':
                    base = 'XBT'
                    
                normalized_symbol = f"{base.upper()}{quote.upper()}"
            
            # Caso speciale per SOL: dobbiamo scegliere tra SOLUSDT e SOLUSD in base alla posizione attiva
            if 'SOL' in normalized_symbol.upper():
                # Verifica quale posizione SOL è attiva
                try:
                    # Import the BitMEXAPI class
                    from bitmex_api import BitMEXAPI
                    bitmex_api = BitMEXAPI()
                    positions = bitmex_api.get_open_positions()
                    
                    # Cerca posizioni attive (currentQty != 0) per entrambi i simboli
                    solusdt_position = None
                    solusd_position = None
                    
                    for pos in positions:
                        pos_symbol = pos.get('symbol', '')
                        pos_qty = pos.get('currentQty', 0)
                        pos_currency = pos.get('currency', '')
                        
                        if pos_symbol == 'SOLUSDT' and pos_qty != 0:
                            solusdt_position = pos
                            logger.info(f"Trovata posizione attiva SOLUSDT con qty={pos_qty}, currency={pos_currency}")
                        elif pos_symbol == 'SOLUSD' and pos_qty != 0:
                            solusd_position = pos
                            logger.info(f"Trovata posizione attiva SOLUSD con qty={pos_qty}, currency={pos_currency}")
                    
                    # Se l'utente sta aggiungendo USDT (amount positivo) e c'è una posizione SOLUSDT attiva
                    # O se l'utente sta aggiungendo valore, dovremmo usare SOLUSDT che usa USDt
                    if amount > 0 and solusdt_position:
                        normalized_symbol = 'SOLUSDT'
                        logger.info(f"Utilizzo simbolo SOLUSDT per aggiunta di margine in USDT")
                    # Se c'è solo una posizione SOLUSD attiva, usa quella
                    elif solusd_position and not solusdt_position:
                        normalized_symbol = 'SOLUSD'
                        logger.info(f"Utilizzo simbolo SOLUSD per modifica margine (richiede XBt)")
                    # Se non ci sono posizioni attive o ci sono entrambe, preferisci SOLUSDT per USDT
                    elif amount > 0:
                        normalized_symbol = 'SOLUSDT'
                        logger.info(f"Nessuna posizione attiva, utilizzo simbolo SOLUSDT per aggiunta di margine in USDT")
                    else:
                        # Se l'amount è negativo (rimozione margine), preferisci SOLUSDT per default
                        normalized_symbol = 'SOLUSDT'
                        logger.info(f"Utilizzo SOLUSDT per rimozione margine")
                except Exception as e:
                    logger.warning(f"Errore nel controllare le posizioni attive: {str(e)}")
                    # Se c'è un errore, utilizziamo comunque SOLUSDT che è più probabile che funzioni con USDT
                    normalized_symbol = 'SOLUSDT'
                    logger.info(f"Errore nel controllare posizioni, uso SOLUSDT per default")
            
            # Log del simbolo finale che verrà utilizzato
            logger.info(f"Simbolo finale da utilizzare per modifica margine: {normalized_symbol}")
            
            # Fattore di conversione corretto, verificato manualmente: 
            # 10000000 nell'API = 10 USDT, quindi 1 USDT = 1000000 unità
            margin_units = int(amount * 1000000)
            logger.info(f"Conversione USDT in unità API: {amount} USDT -> {margin_units} unità")
            
            # BitMEX API endpoint per il trasferimento di margine
            base_url = 'https://www.bitmex.com'
            endpoint = '/api/v1/position/transferMargin'
            
            # Dati della richiesta - usiamo il fattore di conversione corretto
            data = {
                'symbol': normalized_symbol,
                'amount': margin_units
            }
            
            # Converti i dati in JSON
            data_json = json.dumps(data)
            
            # Genera timestamp per la firma
            expires = int(time.time() + 10) * 1000  # 10 secondi di scadenza
            
            # Genera la firma
            # BitMEX richiede: verb + path + expires + data
            request_path = endpoint
            message = 'POST' + request_path + str(expires) + data_json
            
            signature = hmac.new(
                bytes(api_secret, 'utf8'),
                bytes(message, 'utf8'),
                digestmod=hashlib.sha256
            ).hexdigest()
            
            # Headers per l'autenticazione
            headers = {
                'content-type': 'application/json',
                'accept': 'application/json',
                'api-expires': str(expires),
                'api-key': api_key,
                'api-signature': signature
            }
            
            # Log per debug
            logger.info(f"Invio richiesta diretta a BitMEX: POST {base_url + endpoint}")
            logger.info(f"Dati inviati: {data}")
            
            # Invio della richiesta HTTP
            response = requests.post(
                base_url + endpoint,
                data=data_json,
                headers=headers
            )
            
            # Controllo della risposta
            if response.status_code == 200:
                response_data = response.json()
                logger.info(f"Risposta BitMEX: {response_data}")
                return {
                    "success": True, 
                    "data": response_data, 
                    "message": "Trasferimento margine riuscito"
                }
            else:
                error_message = f"Errore BitMEX: Status {response.status_code}"
                logger.error(f"{error_message}, Risposta: {response.text}")
                
                # Se il codice è 400, prova a parsare il messaggio di errore per info aggiuntive
                if response.status_code == 400:
                    try:
                        error_json = response.json()
                        error_msg = error_json.get('error', {}).get('message', '')
                        if error_msg:
                            error_message = f"Errore BitMEX: {error_msg}"
                        logger.error(f"Messaggio errore BitMEX: {error_msg}")
                        
                        # Secondo tentativo con simbolo diverso se l'errore è "Cannot find instrument"
                        if "Cannot find instrument" in error_msg and normalized_symbol == "SOLUSD":
                            logger.info("Tentativo fallito con SOLUSD, provo con SOLUSDT")
                            # Dati della richiesta con simbolo alternativo
                            data['symbol'] = 'SOLUSDT'
                            
                            # Ricostruisci il JSON e la firma
                            data_json = json.dumps(data)
                            expires = int(time.time() + 10) * 1000
                            message = 'POST' + request_path + str(expires) + data_json
                            
                            signature = hmac.new(
                                bytes(api_secret, 'utf8'),
                                bytes(message, 'utf8'),
                                digestmod=hashlib.sha256
                            ).hexdigest()
                            
                            headers['api-expires'] = str(expires)
                            headers['api-signature'] = signature
                            
                            logger.info(f"Secondo tentativo con dati: {data}")
                            
                            # Secondo tentativo di richiesta
                            second_response = requests.post(
                                base_url + endpoint,
                                data=data_json,
                                headers=headers
                            )
                            
                            if second_response.status_code == 200:
                                second_response_data = second_response.json()
                                logger.info(f"Risposta secondo tentativo: {second_response_data}")
                                return {
                                    "success": True, 
                                    "data": second_response_data, 
                                    "message": "Trasferimento margine riuscito (secondo tentativo)"
                                }
                            else:
                                logger.error(f"Anche il secondo tentativo è fallito: {second_response.text}")
                                
                                # Prova il terzo tentativo con una conversione della valuta
                                if "Account has zero XBt margin balance" in second_response.text and amount > 0:
                                    logger.info("Errore di XBt balance, provo a convertire USDT in XBt")
                                    
                                    # Errore di XBt balance, tentativo di conversione USDT -> XBt
                                    try:
                                        # Possiamo provare con la posizione SOLUSDT che usa USDt
                                        data['symbol'] = 'SOLUSDT'
                                        
                                        # Ricostruisci il JSON e la firma
                                        data_json = json.dumps(data)
                                        expires = int(time.time() + 10) * 1000
                                        message = 'POST' + request_path + str(expires) + data_json
                                        
                                        signature = hmac.new(
                                            bytes(api_secret, 'utf8'),
                                            bytes(message, 'utf8'),
                                            digestmod=hashlib.sha256
                                        ).hexdigest()
                                        
                                        headers['api-expires'] = str(expires)
                                        headers['api-signature'] = signature
                                        
                                        logger.info(f"Terzo tentativo con SOLUSDT: {data}")
                                        
                                        # Terzo tentativo di richiesta
                                        third_response = requests.post(
                                            base_url + endpoint,
                                            data=data_json,
                                            headers=headers
                                        )
                                        
                                        if third_response.status_code == 200:
                                            third_response_data = third_response.json()
                                            logger.info(f"Risposta terzo tentativo: {third_response_data}")
                                            return {
                                                "success": True, 
                                                "data": third_response_data, 
                                                "message": "Trasferimento margine riuscito (terzo tentativo)"
                                            }
                                        else:
                                            logger.error(f"Tutti i tentativi falliti: {third_response.text}")
                                    except Exception as e:
                                        logger.error(f"Errore durante il terzo tentativo: {str(e)}")
                    except Exception as retry_error:
                        logger.error(f"Errore durante il secondo tentativo: {str(retry_error)}")
                
                return {"error": error_message, "raw_response": response.text}
                
        except Exception as e:
            logger.error(f"Errore durante la chiamata diretta all'API BitMEX: {str(e)}")
            return {"error": f"Errore durante la chiamata diretta all'API BitMEX: {str(e)}"}
            
    def get_open_positions(self, symbol=None):
        """
        Ottiene le posizioni aperte
        
        Args:
            symbol (str, optional): Simbolo specifico da filtrare
            
        Returns:
            dict: Risultato dell'operazione con formato standardizzato
        """
        try:
            if not self.exchange.apiKey or not self.exchange.secret:
                logger.warning(f"API key o secret non configurati per {self.exchange_id}")
                return {"success": True, "positions": [], "warning": "API credentials non configurate"}
            
            # Per BitMEX, proviamo prima con CCXT direttamente
            if self.exchange_id == 'bitmex':
                try:
                    logger.info(f"Tentativo recupero posizioni BitMEX con CCXT...")
                    
                    # Filtra per simbolo se specificato
                    params = {}
                    if symbol:
                        params['symbol'] = symbol
                    
                    # Usa CCXT per recuperare le posizioni
                    raw_positions = self.exchange.fetch_positions(params=params)
                    
                    # Se non ci sono posizioni, restituisce una lista vuota
                    if not raw_positions:
                        logger.info(f"Nessuna posizione aperta su BitMEX")
                        return {
                            "success": True,
                            "positions": []
                        }
                    
                    logger.info(f"Recuperate {len(raw_positions)} posizioni da BitMEX con CCXT")
                    
                    # Formatta le posizioni
                    positions = []
                    for pos in raw_positions:
                        # Controlla se la posizione è vuota (size/contracts = 0)
                        contracts = pos.get('contracts', 0)
                        notional = pos.get('notional', 0)
                        
                        if (contracts and contracts != 0) or (notional and notional != 0):
                            positions.append(pos)
                    
                    return {
                        "success": True,
                        "positions": positions
                    }
                    
                except Exception as e:
                    logger.error(f"Errore nel recuperare posizioni BitMEX con CCXT: {str(e)}")
                    logger.info("Fallback all'API nativa BitMEX...")
                    
                    # Fallback alla nostra API nativa
                    try:
                        from bitmex_api import BitMEXAPI
                        bitmex_api = BitMEXAPI()
                        
                        # Otteniamo le posizioni tramite l'API nativa
                        positions = bitmex_api.get_open_positions(symbol)
                        
                        # Se non ci sono posizioni, restituisci una lista vuota
                        if not positions:
                            logger.info("Nessuna posizione aperta su BitMEX")
                            return {
                                "success": True,
                                "positions": []
                            }
                        
                        # Formattiamo i dati nel formato standard
                        formatted_positions = []
                        for pos in positions:
                            # Calcoliamo il contratto con il segno
                            contract_qty = pos.get('currentQty', 0)
                            side = 'long' if contract_qty > 0 else 'short'
                            
                            # BitMEX usa satoshi (1 BTC = 100,000,000 satoshi) per alcuni valori
                            entry_price = pos.get('avgEntryPrice', 0)
                            mark_price = pos.get('markPrice', 0) 
                            liquidation_price = pos.get('liquidationPrice', 0)
                            leverage = pos.get('leverage', 0)
                            
                            # Informazioni sulla posizione
                            position = {
                                'symbol': pos.get('symbol', ''),
                                'side': side,
                                'contracts': abs(contract_qty),
                                'contractSize': pos.get('contractSize', 1),
                                'entryPrice': entry_price,
                                'markPrice': mark_price,
                                'unrealizedPnl': pos.get('unrealisedPnl', 0) / 100000000 if pos.get('unrealisedPnl') else 0,
                                'liquidationPrice': liquidation_price,
                                'margin': pos.get('posMargin', 0) / 100000000 if pos.get('posMargin') else 0,
                                'leverage': leverage,
                                'marginMode': pos.get('crossMargin', False) and 'cross' or 'isolated',
                                'info': pos
                            }
                            
                            formatted_positions.append(position)
                        
                        return {
                            "success": True,
                            "positions": formatted_positions
                        }
                    except Exception as e:
                        logger.error(f"Errore nel recuperare posizioni BitMEX anche con API nativa: {str(e)}")
                        # Se entrambi i metodi falliscono, restituisci lista vuota
                        return {"success": True, "positions": []}
            
            # Per Bitfinex, usiamo l'API nativa
            elif self.exchange_id == 'bitfinex':
                try:
                    from bitfinex_api import BitfinexAPI
                    bitfinex_api = BitfinexAPI()
                    
                    # Otteniamo le posizioni tramite l'API nativa
                    result = bitfinex_api.get_open_positions()
                    
                    if "error" in result:
                        logger.error(f"Errore nel recuperare posizioni Bitfinex: {result['error']}")
                        logger.info("Fallback al metodo CCXT standard per Bitfinex")
                        # Continua con il metodo CCXT standard
                    else:
                        if "success" in result and result["success"]:
                            return {
                                "success": True,
                                "positions": result.get("positions", [])
                            }
                except Exception as e:
                    logger.error(f"Errore nel recuperare posizioni Bitfinex: {str(e)}")
                    logger.info("Fallback al metodo CCXT standard per Bitfinex")
                    # Continua con il metodo CCXT standard
            
            # Caso speciale per ByBit: usa fetchPosition (singolare) invece di fetchPositions
            elif self.exchange_id == 'bybit':
                try:
                    positions = []
                    
                    # Se symbol è specificato, usiamo fetchPosition direttamente
                    if symbol:
                        logger.info(f"Recupero posizione Bybit per simbolo specifico: {symbol}")
                        
                        # Normalizza il simbolo se necessario
                        bybit_symbol = symbol
                        if '/' in symbol:
                            parts = symbol.split('/')
                            bybit_symbol = parts[0] + parts[1]
                        
                        # Lista di simboli possibili da provare
                        symbols_to_try = [
                            bybit_symbol,                 # formato normale (es. BTCUSDT)
                            bybit_symbol + "Perp",        # con suffisso Perp (es. BTCUSDTPerp)
                            bybit_symbol.replace("Perp", ""), # senza suffisso Perp se presente
                            "SOL/USDT:USDT"               # formato con doppio USDT (rilevato nel debug)
                        ]
                        
                        # Rimuovi duplicati
                        symbols_to_try = list(set(symbols_to_try))
                        
                        # Tenta con diversi formati del simbolo
                        position_found = False
                        for sym in symbols_to_try:
                            try:
                                logger.info(f"Tentativo con simbolo: {sym}")
                                # Usa fetchPosition per Bybit
                                position = self.exchange.fetchPosition(sym)
                                
                                if position and position.get('contracts', 0) != 0:
                                    logger.info(f"Posizione trovata per {sym}: {position}")
                                    positions.append(position)
                                    position_found = True
                                    break
                                else:
                                    logger.info(f"Posizione vuota per {sym}")
                            except Exception as e:
                                logger.warning(f"Errore nel recuperare posizione per {sym}: {str(e)}")
                                continue
                        
                        if not position_found:
                            logger.info(f"Nessuna posizione trovata per {symbol} su Bybit")
                            
                            # Fallback a fetch_positions
                            try:
                                logger.info("Fallback a fetch_positions per Bybit")
                                raw_positions = self.exchange.fetch_positions()
                                
                                # Filtra per le posizioni non vuote
                                for pos in raw_positions:
                                    # Controlla se la posizione è vuota (size/contracts = 0)
                                    contracts = pos.get('contracts', 0)
                                    notional = pos.get('notional', 0)
                                    pos_symbol = pos.get('symbol', '')
                                    
                                    if (contracts and contracts != 0) or (notional and notional != 0):
                                        positions.append(pos)
                            except Exception as e:
                                logger.error(f"Anche il fallback a fetch_positions è fallito: {str(e)}")
                    else:
                        # Se symbol non è specificato, utilizziamo fetch_positions
                        logger.info("Recupero tutte le posizioni su Bybit con fetch_positions")
                        raw_positions = self.exchange.fetch_positions()
                        
                        # Filtra per le posizioni non vuote
                        for pos in raw_positions:
                            # Controlla se la posizione è vuota (size/contracts = 0)
                            contracts = pos.get('contracts', 0)
                            notional = pos.get('notional', 0)
                            pos_symbol = pos.get('symbol', '')
                            
                            if (contracts and contracts != 0) or (notional and notional != 0):
                                positions.append(pos)
                    
                    # Se non abbiamo trovato posizioni, fallback all'API nativa
                    if not positions:
                        try:
                            from bybit_api import ByBitAPI
                            bybit_api = ByBitAPI()
                            
                            # Normalizza il simbolo se specificato
                            normalized_symbol = None
                            if symbol:
                                normalized_symbol = symbol
                                if '/' in normalized_symbol:
                                    parts = normalized_symbol.split('/')
                                    normalized_symbol = parts[0] + parts[1]
                            
                            logger.info(f"Tentativo con API nativa ByBit")
                            native_positions = bybit_api.get_open_positions(normalized_symbol)
                            
                            if native_positions and len(native_positions) > 0:
                                logger.info(f"Trovate {len(native_positions)} posizioni con API nativa")
                                
                                # Converti al formato CCXT
                                for pos in native_positions:
                                    # Determina il lato
                                    side = pos.get('side', '')
                                    is_long = side == 'Buy'
                                    pos_symbol = pos.get('symbol', '')
                                    pos_size = pos.get('size', 0)
                                    
                                    formatted_pos = {
                                        'symbol': pos_symbol,
                                        'side': 'long' if is_long else 'short',
                                        'contracts': float(pos_size),
                                        'contractSize': 1,
                                        'entryPrice': float(pos.get('entry_price', 0)),
                                        'markPrice': float(pos.get('mark_price', 0)),
                                        'unrealizedPnl': float(pos.get('unrealised_pnl', 0)),
                                        'leverage': float(pos.get('leverage', 1)),
                                        'marginMode': pos.get('margin_mode', 'isolated'),
                                        'info': pos
                                    }
                                    positions.append(formatted_pos)
                        except Exception as native_err:
                            logger.error(f"Errore con API nativa: {str(native_err)}")
                    
                    if positions:
                        for pos in positions:
                            pos_symbol = pos.get('symbol', '')
                            pos_side = pos.get('side', '')
                            pos_size = pos.get('contracts', 0)
                    
                    return {
                        "success": True,
                        "positions": positions
                    }
                    
                except Exception as e:
                    logger.error(f"Errore generale nel recuperare posizioni Bybit: {str(e)}")
                    # Continua con il metodo CCXT standard come fallback
            
            # Per gli altri exchange o come fallback, usiamo CCXT standard
            try:
                # Carica le posizioni attraverso CCXT
                positions = []
                
                # Filtra per simbolo se specificato
                params = {}
                if symbol:
                    # Se stiamo cercando un simbolo specifico con Bybit, aggiungiamo il formato con Perp
                    # come possibile candidato
                    if self.exchange_id == 'bybit' and symbol and "Perp" not in symbol:
                        logger.info(f"Verifica anche per formati alternativi di {symbol} su Bybit")
                        
                        # Prova prima con il simbolo originale
                        try:
                            raw_positions_original = self.exchange.fetch_positions(params=params)
                            
                            if not raw_positions_original or len(raw_positions_original) == 0:
                                # Se non trova nulla, prova con il simbolo + Perp
                                normalized_symbol = symbol
                                if '/' in normalized_symbol:
                                    parts = normalized_symbol.split('/')
                                    normalized_symbol = parts[0] + parts[1]
                                
                                perp_symbol = normalized_symbol + "Perp"
                                logger.info(f"Tentativo con simbolo {perp_symbol}")
                                params = {'symbol': perp_symbol}
                        except Exception as e:
                            logger.warning(f"Errore nella ricerca con simbolo originale: {str(e)}")
                
                logger.info(f"Recupero posizioni per {self.exchange_id} tramite CCXT")
                raw_positions = self.exchange.fetch_positions(params=params)
                
                # Se non ci sono posizioni, restituisce una lista vuota
                if not raw_positions:
                    logger.info(f"Nessuna posizione aperta su {self.exchange_id}")
                    
                    # Per Bybit, ultimo tentativo con API nativa
                    if self.exchange_id == 'bybit' and symbol:
                        try:
                            from bybit_api import ByBitAPI
                            bybit_api = ByBitAPI()
                            
                            # Normalizza il simbolo
                            normalized_symbol = symbol
                            if '/' in normalized_symbol:
                                parts = normalized_symbol.split('/')
                                normalized_symbol = parts[0] + parts[1]
                            
                            # Tenta di recuperare posizioni con l'API nativa
                            logger.info(f"Tentativo di recupero posizioni con ByBitAPI")
                            bybit_positions = bybit_api.get_open_positions(normalized_symbol)
                            
                            if bybit_positions and len(bybit_positions) > 0:
                                logger.info(f"Trovate {len(bybit_positions)} posizioni tramite API nativa")
                                
                                # Converti al formato CCXT
                                formatted_positions = []
                                for pos in bybit_positions:
                                    # Determina il lato
                                    side = pos.get('side', '')
                                    is_long = side == 'Buy'
                                    
                                    # Formatta la posizione
                                    formatted_pos = {
                                        'symbol': pos.get('symbol', ''),
                                        'side': 'long' if is_long else 'short',
                                        'contracts': float(pos.get('size', 0)),
                                        'contractSize': 1,
                                        'entryPrice': float(pos.get('entry_price', 0)),
                                        'markPrice': float(pos.get('mark_price', 0)),
                                        'unrealizedPnl': float(pos.get('unrealised_pnl', 0)),
                                        'leverage': float(pos.get('leverage', 1)),
                                        'marginMode': pos.get('margin_mode', 'isolated'),
                                        'info': pos
                                    }
                                    
                                    formatted_positions.append(formatted_pos)
                                
                                return {
                                    "success": True,
                                    "positions": formatted_positions
                                }
                        except Exception as e:
                            logger.error(f"Errore nel recupero posizioni con API nativa Bybit: {str(e)}")
                    
                    return {
                        "success": True,
                        "positions": []
                    }
            except Exception as e:
                logger.error(f"Errore generale nel recuperare posizioni: {str(e)}")
                return {"success": True, "positions": []}
        except Exception as e:
            logger.error(f"Errore generale nel recuperare posizioni: {str(e)}")
            return {"success": True, "positions": []}