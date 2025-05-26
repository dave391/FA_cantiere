"""
ByBit API Wrapper - Checkpoint Version 3.0 (Codice Pulito)
Data: 15/05/2025
"""

import time
import hmac
import hashlib
import requests
import json
import os
import urllib.parse
from dotenv import load_dotenv
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('bybit_api')

class ByBitAPI:
    def __init__(self, testnet=False):
        load_dotenv()
        self.API_KEY = os.getenv('BYBIT_API_KEY')
        self.API_SECRET = os.getenv('BYBIT_API_SECRET')
        
        if testnet:
            self.API_URL = 'https://api-testnet.bybit.com'
        else:
            self.API_URL = 'https://api.bybit.com'
    
    def _generate_signature(self, params):
        """Genera una firma per l'autenticazione delle richieste a ByBit"""
        # Ordina i parametri per chiave in ordine alfabetico
        sorted_params = sorted(params.items())
        
        # Costruisci la stringa dei parametri
        param_str = '&'.join([f"{key}={value}" for key, value in sorted_params])
        
        # Genera la firma HMAC SHA256
        signature = hmac.new(
            bytes(self.API_SECRET, 'utf-8'),
            bytes(param_str, 'utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _request(self, endpoint, method='GET', params=None, data=None):
        """Esegue una richiesta all'API di ByBit con autenticazione"""
        url = f"{self.API_URL}{endpoint}"
        
        # Parametri comuni per tutte le richieste
        if params is None:
            params = {}
        
        # Aggiunge il timestamp per l'autenticazione
        params['api_key'] = self.API_KEY
        params['timestamp'] = str(int(time.time() * 1000))
        
        # Genera la firma e aggiungila ai parametri
        params['sign'] = self._generate_signature(params)
        
        # Headers
        headers = {
            'Content-Type': 'application/json'
        }
        
        try:
            if method == 'GET':
                response = requests.get(url, params=params, headers=headers)
            elif method == 'POST':
                response = requests.post(url, params=params, json=data, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, params=params, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, params=params, json=data, headers=headers)
            else:
                return {"error": f"Metodo HTTP non supportato: {method}"}
            
            # Verifica se la risposta è valida
            if response.status_code == 200:
                try:
                    result = response.json()
                    return result
                except ValueError:
                    return {"error": "Risposta non valida", "text": response.text}
            else:
                return {"error": f"Errore API: {response.status_code}", "details": response.text}
            
        except Exception as e:
            return {"error": f"Errore di connessione: {str(e)}"}
    
    def get_perpetual_futures(self):
        """Ottiene la lista di futures perpetui disponibili su ByBit"""
        try:
            endpoint = '/v2/public/symbols'
            response = self._request(endpoint, method='GET')
            
            if 'result' in response and isinstance(response['result'], list):
                # Filtra solo i futures perpetui
                perpetual_pairs = [
                    item['name'] for item in response['result']
                    if item.get('name', '').endswith('USDT')
                ]
                
                logger.info(f"Trovati {len(perpetual_pairs)} futures perpetui su ByBit")
                return perpetual_pairs
            else:
                logger.error(f"Errore nel recuperare futures perpetui: {response}")
                return []
        
        except Exception as e:
            logger.error(f"Eccezione durante il recupero dei futures: {str(e)}")
            return []
    
    def get_instrument_info(self, symbol=None):
        """Ottiene informazioni su uno strumento finanziario specifico"""
        endpoint = '/v2/public/symbols'
        response = self._request(endpoint, method='GET')
        
        if 'result' in response and isinstance(response['result'], list):
            if symbol:
                # Se è specificato un simbolo, restituisci solo quello
                for item in response['result']:
                    if item.get('name') == symbol:
                        return item
                
                logger.warning(f"Simbolo {symbol} non trovato")
                return None
            else:
                # Altrimenti, restituisci tutti gli strumenti
                return response['result']
        else:
            logger.error(f"Errore nel recuperare informazioni strumenti: {response}")
            return None
    
    def normalize_symbol(self, symbol):
        """Normalizza il nome del simbolo per compatibilità con ByBit"""
        # Se simbolo contiene SOLANA, converti al formato ByBit
        if 'SOL' in symbol.upper() and 'USDT' not in symbol.upper():
            # Verifica che sia effettivamente il token SOL (Solana) e non altri token come SOLO
            if symbol.upper() == "SOL" or symbol.upper() == "SOLANA":
                return 'SOLUSDT'
            
            # In caso di dubbio, controlla se il simbolo inizia con SOL e non contiene altri identificatori
            if symbol.upper().startswith("SOL") and not any(x in symbol.upper() for x in ["SOLO", "SOLAYER", "SOLA/"]):
                return 'SOLUSDT'
        
        # Gestione specifica per il token SOL nei vari formati
        if symbol.upper() in ["SOL/USDT", "SOL-USDT", "SOL_USDT"]:
            return 'SOLUSDT'
        
        # Rimuovi prefissi come 't' (formato Bitfinex)
        if symbol.startswith('t'):
            symbol = symbol[1:]
        
        # Rimuovi separatori e parti non necessarie
        if '/' in symbol:
            base, quote = symbol.split('/')
            symbol = base + quote
        
        if ':' in symbol:
            symbol = symbol.split(':')[0]
        
        return symbol
    
    def submit_order(self, symbol, amount, price=None, market=True):
        """Invia un ordine a ByBit"""
        try:
            symbol = self.normalize_symbol(symbol)
            
            # Converti la quantity in formato ByBit (quantità positiva)
            abs_amount = abs(float(amount))
            
            # Imposta side (buy/sell) in base al segno di amount
            side = 'Buy' if amount > 0 else 'Sell'
            
            # Prepara i parametri per l'ordine
            params = {
                'symbol': symbol,
                'side': side,
                'qty': abs_amount,
                'time_in_force': 'GoodTillCancel'
            }
            
            # Imposta tipo ordine (market o limit)
            if market:
                params['order_type'] = 'Market'
            else:
                params['order_type'] = 'Limit'
                params['price'] = price
            
            # Invia l'ordine
            endpoint = '/private/linear/order/create'
            
            logger.info(f"Invio ordine a ByBit: symbol={symbol}, side={side}, qty={abs_amount}, " +
                      f"type={'Market' if market else 'Limit'}" +
                      (f", price={price}" if not market else ""))
            
            response = self._request(endpoint, method='POST', params=params)
            
            if 'ret_code' in response and response['ret_code'] == 0:
                logger.info(f"Ordine inviato con successo: {response['result']}")
                return response['result']
            else:
                logger.error(f"Errore nell'invio dell'ordine: {response}")
                return {"error": response.get('ret_msg', 'Errore sconosciuto')}
        
        except Exception as e:
            logger.error(f"Eccezione durante l'invio dell'ordine: {str(e)}")
            return {"error": str(e)}
    
    def get_account_info(self):
        """Ottiene informazioni sull'account"""
        try:
            # Ottieni il bilancio dell'account
            wallet_endpoint = '/v2/private/wallet/balance'
            wallet_response = self._request(wallet_endpoint, method='GET')
            
            # Ottieni informazioni sul margine
            position_endpoint = '/private/linear/position/list'
            position_response = self._request(position_endpoint, method='GET')
            
            return {
                'wallet': wallet_response.get('result', {}),
                'positions': position_response.get('result', [])
            }
        
        except Exception as e:
            logger.error(f"Errore nel recuperare informazioni account: {str(e)}")
            return {"error": str(e)}
    
    def get_usdt_balance(self):
        """Ottiene il saldo USDT dell'account"""
        try:
            endpoint = '/v2/private/wallet/balance'
            response = self._request(endpoint, method='GET')
            
            if 'result' in response and 'USDT' in response['result']:
                usdt_info = response['result']['USDT']
                
                # Bilancio disponibile in USDT
                available_balance = float(usdt_info.get('available_balance', 0))
                
                logger.info(f"Saldo USDT disponibile: {available_balance}")
                return available_balance
            else:
                logger.error(f"Errore nel recuperare saldo USDT o saldo non disponibile: {response}")
                return 0
        
        except Exception as e:
            logger.error(f"Errore nel recuperare saldo USDT: {str(e)}")
            return 0
    
    def get_open_positions(self, symbol=None):
        """Ottiene le posizioni aperte"""
        try:
            endpoint = '/private/linear/position/list'
            params = {}
            
            if symbol:
                params['symbol'] = self.normalize_symbol(symbol)
            
            response = self._request(endpoint, method='GET', params=params)
            
            if 'result' in response:
                positions = response['result']
                
                # Filtra solo le posizioni con size non zero
                if isinstance(positions, list):
                    active_positions = [
                        pos for pos in positions
                        if float(pos.get('size', 0)) > 0
                    ]
                    return active_positions
                else:
                    # Se result è un oggetto, verifica se contiene una sola posizione
                    if isinstance(positions, dict) and float(positions.get('size', 0)) > 0:
                        return [positions]
                
                return []
            else:
                logger.error(f"Errore nel recuperare posizioni: {response}")
                return []
        
        except Exception as e:
            logger.error(f"Eccezione durante il recupero delle posizioni: {str(e)}")
            return []
    
    def close_position(self, symbol, reduce_only=True):
        """Chiude una posizione specifica"""
        try:
            symbol = self.normalize_symbol(symbol)
            
            # Ottieni la posizione corrente
            positions = self.get_open_positions(symbol)
            
            if not positions:
                return {"error": f"Nessuna posizione attiva trovata per {symbol}"}
            
            position = positions[0]
            current_size = float(position.get('size', 0))
            position_side = position.get('side', '')
            
            if current_size == 0:
                return {"error": f"Posizione per {symbol} ha size 0"}
            
            # Crea un ordine di segno opposto
            close_side = 'Sell' if position_side == 'Buy' else 'Buy'
            
            # Parametri dell'ordine
            params = {
                'symbol': symbol,
                'side': close_side,
                'qty': current_size,
                'order_type': 'Market',
                'time_in_force': 'GoodTillCancel',
                'reduce_only': True if reduce_only else False
            }
            
            # Invia l'ordine
            endpoint = '/private/linear/order/create'
            
            logger.info(f"Chiusura posizione {symbol}: side={close_side}, qty={current_size}")
            
            response = self._request(endpoint, method='POST', params=params)
            
            if 'ret_code' in response and response['ret_code'] == 0:
                logger.info(f"Posizione chiusa con successo: {response['result']}")
                return response['result']
            else:
                logger.error(f"Errore nella chiusura della posizione: {response}")
                return {"error": response.get('ret_msg', 'Errore sconosciuto')}
        
        except Exception as e:
            logger.error(f"Errore nel chiudere la posizione: {str(e)}")
            return {"error": str(e)}
    
    def adjust_position_margin(self, symbol, amount):
        """
        Aggiunge o rimuove margine da una posizione aperta
        
        Args:
            symbol (str): Simbolo della posizione
            amount (float): Importo di margine da aggiungere (positivo) o rimuovere (negativo) in USDT
            
        Returns:
            dict: Risultato dell'operazione
        """
        try:
            # Normalizza il simbolo
            symbol = self.normalize_symbol(symbol)
            logger.info(f"Modifica margine per simbolo normalizzato: {symbol}, importo: {amount}")
            
            # Per l'API v5, dobbiamo formattare l'importo come stringa
            # Per rimuovere margine, l'API v5 usa il segno negativo
            amount_str = str(amount)
            
            # Timestamp per la firma
            timestamp = str(int(time.time() * 1000))
            
            # Parametri per la firma
            params = {
                'api_key': self.API_KEY,
                'timestamp': timestamp,
                'recv_window': '5000'
            }
            
            # Dati del corpo della richiesta
            data = {
                'category': 'linear',
                'symbol': symbol,
                'margin': amount_str,
                'positionIdx': 0  # 0 per position_mode=BOTH (default su ByBit)
            }
            
            # Prepara il percorso per la firma
            endpoint = '/v5/position/add-margin'
            url = f"{self.API_URL}{endpoint}"
            
            # Concatena i parametri query string per la firma
            query_string = '&'.join([f"{key}={params[key]}" for key in sorted(params.keys())])
            
            # Genera la stringa da firmare: timestamp + api_key + recv_window + corpo_json
            data_json = json.dumps(data)
            sign_str = f"{timestamp}{self.API_KEY}5000{data_json}"
            
            # Genera la firma HMAC
            signature = hmac.new(
                bytes(self.API_SECRET, 'utf-8'),
                bytes(sign_str, 'utf-8'),
                digestmod=hashlib.sha256
            ).hexdigest()
            
            # Aggiungi la firma ai parametri
            params['sign'] = signature
            
            # Query string completa
            query_string = '&'.join([f"{key}={params[key]}" for key in sorted(params.keys())])
            
            # URL completo
            full_url = f"{url}?{query_string}"
            
            logger.info(f"Invio richiesta di modifica margine a {url}")
            logger.info(f"Query string: {query_string}")
            logger.info(f"Body: {data_json}")
            
            # Headers
            headers = {
                'Content-Type': 'application/json',
                'X-BAPI-API-KEY': self.API_KEY,
                'X-BAPI-SIGN': signature,
                'X-BAPI-TIMESTAMP': timestamp,
                'X-BAPI-RECV-WINDOW': '5000'
            }
            
            # Esegui la richiesta
            response = requests.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                
                # Verifica il risultato
                if 'retCode' in result and result['retCode'] == 0:
                    operation = "aggiunto" if float(amount) > 0 else "rimosso"
                    logger.info(f"Margine {operation} con successo: {abs(float(amount))} USDT")
                    return {"success": True, "data": result.get('result', {})}
                else:
                    logger.error(f"Errore ByBit nella modifica del margine: {result}")
                    return {"error": result.get('retMsg', 'Errore sconosciuto')}
            else:
                logger.error(f"Errore HTTP {response.status_code}: {response.text}")
                return {"error": f"Errore HTTP {response.status_code}: {response.text}"}
            
        except Exception as e:
            logger.error(f"Errore nell'aggiustare il margine: {str(e)}")
            return {"error": str(e)}
    
    def get_funding_history(self, symbol, start_time=None, end_time=None, count=50):
        """
        Ottiene la cronologia dei funding rate per un simbolo specifico
        
        Args:
            symbol (str): Simbolo per cui ottenere la cronologia dei funding rate
            start_time (str, optional): Timestamp di inizio in formato ISO 8601
            end_time (str, optional): Timestamp di fine in formato ISO 8601
            count (int, optional): Numero massimo di record da recuperare (default: 50)
            
        Returns:
            dict: Risultato dell'operazione con i dati dei funding rate
        """
        try:
            # Normalizza il simbolo per ByBit
            symbol = self.normalize_symbol(symbol)
            logger.info(f"Richiesta funding history per {symbol}")
            
            # Costruisci i parametri della richiesta
            params = {'category': 'linear', 'symbol': symbol, 'limit': count}
            
            # Aggiungi parametri opzionali se forniti
            if start_time:
                # Converti il formato ISO 8601 a timestamp in millisecondi
                try:
                    dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    start_ms = int(dt.timestamp() * 1000)
                    params['startTime'] = start_ms
                except:
                    logger.warning(f"Impossibile convertire start_time: {start_time}")
            
            if end_time:
                try:
                    dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                    end_ms = int(dt.timestamp() * 1000)
                    params['endTime'] = end_ms
                except:
                    logger.warning(f"Impossibile convertire end_time: {end_time}")
            
            # Endpoint v5 per funding history
            endpoint = '/v5/market/funding/history'
            
            # Esegui la richiesta
            response = requests.get(f"{self.API_URL}{endpoint}", params=params)
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    
                    if result.get('retCode') == 0 and 'result' in result and 'list' in result['result']:
                        funding_data = result['result']['list']
                        
                        # Formatta i risultati come per BitMEX
                        formatted_funding = []
                        for item in funding_data:
                            # Converti da timestamp a ISO 8601
                            ts = item.get('fundingRateTimestamp')
                            if ts:
                                dt = datetime.fromtimestamp(int(ts) / 1000)
                                timestamp = dt.isoformat()
                            else:
                                timestamp = None
                                
                            funding_rate = None
                            try:
                                funding_rate = float(item.get('fundingRate', '0'))
                            except:
                                funding_rate = 0
                                
                            formatted_item = {
                                'timestamp': timestamp,
                                'symbol': item.get('symbol'),
                                'fundingRate': funding_rate,
                                'fundingRateDaily': funding_rate * 3 * 100 if funding_rate else None,  # Tasso giornaliero in percentuale
                                'fundingInterval': None  # ByBit non fornisce questo campo
                            }
                            formatted_funding.append(formatted_item)
                            
                        logger.info(f"Recuperati {len(formatted_funding)} funding rate per {symbol}")
                        return {"success": True, "funding_history": formatted_funding}
                    else:
                        error_msg = result.get('retMsg', 'Unknown error')
                        logger.error(f"Errore nell'API ByBit: {error_msg}")
                        return {"error": error_msg}
                except Exception as e:
                    logger.error(f"Errore nel parsing della risposta: {str(e)}")
                    return {"error": f"Errore nel parsing della risposta: {str(e)}"}
            else:
                logger.error(f"Errore nella richiesta HTTP: {response.status_code} - {response.text}")
                return {"error": f"Errore nella richiesta HTTP: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Errore nel recuperare funding history: {str(e)}")
            return {"error": str(e)} 