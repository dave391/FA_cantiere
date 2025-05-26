"""
Bitfinex API Wrapper - Checkpoint Version 3.0 (Codice Pulito)
Data: 15/05/2025
"""

import time
import hmac
import hashlib
import requests
import json
import os
import base64
import urllib.parse
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('bitfinex_api')

class BitfinexAPI:
    def __init__(self, testnet=False):
        load_dotenv()
        self.API_KEY = os.getenv('BITFINEX_API_KEY')
        self.API_SECRET = os.getenv('BITFINEX_API_SECRET')
        self.API_URL = 'https://api.bitfinex.com'
        self.API_VERSION = 'v2'
        self.NONCE_OFFSET = 0

    def _nonce(self):
        """Genera un nonce incrementale per le richieste API"""
        return str(int(time.time() * 1000) + self.NONCE_OFFSET)

    def _headers(self, path, nonce, body):
        """Genera gli headers per le richieste autenticate"""
        signature = f'/api/{path}{nonce}{body}'
        h = hmac.new(self.API_SECRET.encode(), signature.encode(), hashlib.sha384)
        signature = h.hexdigest()

        return {
            "bfx-nonce": nonce,
            "bfx-apikey": self.API_KEY,
            "bfx-signature": signature,
            "content-type": "application/json"
        }

    def _make_request(self, method, endpoint, auth=False, params=None, data=None):
        """Esegue una richiesta all'API di Bitfinex"""
        url = f"{self.API_URL}/{endpoint}"
        
        if auth:
            # Se è una richiesta autenticata
            if params:
                path = f"{endpoint}?{urllib.parse.urlencode(params)}"
            else:
                path = endpoint
                
            nonce = self._nonce()
            body = json.dumps(data) if data else '{}'
            headers = self._headers(path, nonce, body)
            
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    data=body if data else None
                )
            except Exception as e:
                logger.error(f"Errore di connessione a Bitfinex: {str(e)}")
                return None
        else:
            # Se è una richiesta pubblica
            try:
                if method == 'GET':
                    response = requests.get(url, params=params)
                else:
                    headers = {"content-type": "application/json"}
                    response = requests.request(
                        method=method,
                        url=url,
                        headers=headers,
                        params=params,
                        data=json.dumps(data) if data else None
                    )
            except Exception as e:
                logger.error(f"Errore di connessione a Bitfinex: {str(e)}")
                return None
                
        # Verifica la risposta
        if response.status_code == 200:
            try:
                return response.json()
            except:
                return response.text
        else:
            logger.error(f"Errore API Bitfinex ({response.status_code}): {response.text}")
            return None

    def get_perpetual_futures(self):
        """Ottiene la lista dei futures perpetui disponibili"""
        try:
            # Richiesta per ottenere tutti i simboli di trading
            response = requests.get(f"{self.API_URL}/v1/symbols")
            
            if response.status_code != 200:
                logger.error(f"Errore nel recuperare futures da Bitfinex: {response.status_code}")
                return []
                
            symbols = response.json()
            perpetual_pairs = []
            
            # Filtra i simboli per trovare i futures perpetui
            for symbol in symbols:
                if ':' in symbol or symbol.endswith('f0'):
                    perpetual_pairs.append(f"t{symbol.upper()}")
            
            # Aggiunge manualmente SOLANA se non è presente
            manual_solana = "tSOLF0:USTF0"
            if not any('SOL' in p.upper() for p in perpetual_pairs):
                logger.info(f"Aggiunto manualmente simbolo SOLANA per Bitfinex: {manual_solana}")
                perpetual_pairs.append(manual_solana)
                
            logger.info(f"Trovati {len(perpetual_pairs)} futures perpetui su Bitfinex")
            return perpetual_pairs
                
        except Exception as e:
            logger.error(f"Eccezione durante il recupero dei futures da Bitfinex: {str(e)}")
            return []

    def _convert_to_bitfinex_symbol(self, symbol, is_futures=True):
        """Converte un simbolo generico nel formato Bitfinex"""
        # Se è già nel formato Bitfinex (es. tBTCUSD)
        if symbol.startswith('t') and ':' in symbol and 'F0' in symbol.upper():
            return symbol
            
        # Caso speciale per SOLANA
        if 'SOL' in symbol.upper():
            formatted_symbol = "tSOLF0:USTF0"
            logger.info(f"Convertito simbolo {symbol} nel formato per SOLANA: {formatted_symbol}")
            return formatted_symbol
            
        # Rimuovi prefissi, suffissi e separatori
        clean_symbol = symbol.replace('t', '').replace('/', '').replace('-', '')
        
        # Per futures, aggiungi il suffisso F0:USTF0
        if is_futures:
            base = clean_symbol.replace('USDT', '').replace('USD', '')
            formatted_symbol = f"t{base}F0:USTF0"
            logger.info(f"Convertito simbolo {symbol} nel formato per futures: {formatted_symbol}")
            return formatted_symbol
            
        # Per spot, aggiungi solo il prefisso t
        return f"t{clean_symbol}"

    def submit_order(self, symbol, amount, price=None, market=True, params={}):
        """Invia un ordine di trading"""
        logger.info(f"Invio ordine con simbolo {symbol}, quantità {amount}, prezzo {price}, market {market}")
        
        # Controllo se le API key sono presenti
        if not self.API_KEY or not self.API_SECRET:
            return {"error": "API key o secret non configurati"}
            
        # Converte il simbolo nel formato Bitfinex
        formatted_symbol = self._convert_to_bitfinex_symbol(symbol, is_futures=True)
        
        # Imposta i parametri dell'ordine
        # Per Bitfinex, amount negativo = sell, amount positivo = buy
        # Non è necessario invertire il segno
        
        # Controlla se ci sono parametri aggiuntivi
        order_params = {}
        
        # Imposta il leverage se specificato
        if 'lev' in params:
            order_params['lev'] = params['lev']
        else:
            # Imposta il leverage di default a 3 per futures
            order_params['lev'] = 3
            
        # Flag per ReduceOnly (se specificate nel dizionario params)
        if 'reduce_only' in params and params['reduce_only']:
            flags = 4096  # Flag per ReduceOnly
            order_params['flags'] = flags
            logger.info(f"Attivato flag REDUCE_ONLY (flags = {flags})")
            
        # Flag per post-only (se specificato)
        if 'post_only' in params and params['post_only']:
            # Aggiunge il flag 4 (post-only)
            if 'flags' in order_params:
                order_params['flags'] |= 4
            else:
                order_params['flags'] = 4
                
        # Flag per hidden (se specificato)
        if 'hidden' in params and params['hidden']:
            # Aggiunge il flag 64 (hidden)
            if 'flags' in order_params:
                order_params['flags'] |= 64
            else:
                order_params['flags'] = 64
                
        # Se specificato, usa il leverage custom
        if 'lev' in params:
            order_params['lev'] = params['lev']
            logger.info(f"Impostata leva a {params['lev']}")
            
        # Tipo di ordine
        if market:
            order_type = "MARKET"
        else:
            order_type = "LIMIT"
            
        # Per ordini market su Bitfinex, è necessario specificare comunque un prezzo
        # per il calcolo del valore dell'ordine
        if market:
            if price is None or price == 0:
                # Prova a ottenere il prezzo corrente
                try:
                    ticker_response = requests.get(f"{self.API_URL}/v2/ticker/t{formatted_symbol}")
                    if ticker_response.status_code == 200:
                        ticker_data = ticker_response.json()
                        # Il prezzo è il primo elemento dell'array
                        est_price = ticker_data[0]
                        price = est_price
                        logger.info(f"Usando prezzo stimato per ordine market: {est_price}")
                    else:
                        # Se non è possibile ottenere il prezzo, usa un valore di default
                        price = 100
                        logger.info("Usando prezzo di default 100 per ordine market")
                except Exception as price_error:
                    # In caso di errore, usa un valore di default
                    price = 100
                    logger.error(f"Errore nel recuperare il prezzo, uso default 100: {str(price_error)}")
                    
        # Crea il payload dell'ordine
        payload = {
            "type": order_type,
            "symbol": formatted_symbol,
            "amount": str(amount),
            "price": str(price) if price is not None else "0",
            **order_params
        }
        
        # Esegui la richiesta
        path = "v2/auth/w/order/submit"
        nonce = self._nonce()
        body = json.dumps(payload)
        headers = self._headers(path, nonce, body)
        
        try:
            response = requests.post(
                url=f"{self.API_URL}/{path}",
                headers=headers,
                data=body
            )
            
            # Verifica la risposta
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    
                    # Se la risposta contiene un errore
                    if isinstance(response_data, list) and len(response_data) > 1 and response_data[0] == 'error':
                        error_details = response_data[2] if len(response_data) > 2 else "Dettagli non disponibili"
                        logger.error(f"Errore API Bitfinex: {error_details}")
                        
                        # Se l'errore è relativo al nonce, prova di nuovo con un nonce aggiornato
                        if "nonce" in str(error_details).lower():
                            logger.info("Tentativo con nuovo nonce...")
                            self.NONCE_OFFSET += 1000
                            nonce = self._nonce()
                            headers = self._headers(path, nonce, body)
                            
                            response = requests.post(
                                url=f"{self.API_URL}/{path}",
                                headers=headers,
                                data=body
                            )
                            
                            if response.status_code == 200:
                                response_data = response.json()
                                logger.info(f"Risposta API con nuovo nonce: {response.text}")
                                return {"success": True, "data": response_data}
                            
                        return {"error": error_details}
                    
                    return {"success": True, "data": response_data}
                except Exception as e:
                    logger.error(f"Eccezione durante l'invio dell'ordine a Bitfinex: {str(e)}")
                    return {"error": f"Errore nel processare la risposta: {str(e)}", "raw": response.text}
            else:
                return {"error": f"Errore API ({response.status_code}): {response.text}"}
                
        except Exception as e:
            return {"error": f"Errore di connessione: {str(e)}"}

    def get_account_info(self):
        """Ottiene informazioni sull'account"""
        if not self.API_KEY or not self.API_SECRET:
            return {"error": "API key o secret non configurati"}
            
        try:
            # Richiesta per ottenere il saldo
            path = "v2/auth/r/wallets"
            nonce = self._nonce()
            body = '{}'
            headers = self._headers(path, nonce, body)
            
            response = requests.post(
                url=f"{self.API_URL}/{path}",
                headers=headers,
                data=body
            )
            
            # Verifica la risposta
            if response.status_code == 200:
                try:
                    wallets = response.json()
                    return {"success": True, "wallets": wallets}
                except:
                    return {"error": "Errore nel processare la risposta", "raw": response.text}
            else:
                # Se c'è un errore, estrai i dettagli
                try:
                    error_data = response.json()
                    if isinstance(error_data, list) and error_data[0] == 'error':
                        error_details = error_data[2] if len(error_data) > 2 else "Dettagli non disponibili"
                        logger.error(f"Errore API Bitfinex: {error_details}")
                        return {"error": error_details}
                except:
                    pass
                    
                return {"error": f"Errore API ({response.status_code}): {response.text}"}
                
        except Exception as e:
            logger.error(f"Eccezione durante la richiesta a Bitfinex: {str(e)}")
            return {"error": f"Errore di connessione: {str(e)}"}

    def get_open_positions(self):
        """
        Recupera le posizioni aperte dall'API di Bitfinex
        
        Returns:
            dict: Risultato dell'operazione con le posizioni
        """
        if not self.API_KEY or not self.API_SECRET:
            return {"error": "API key o secret non configurati"}
        
        try:
            # Richiesta per ottenere le posizioni
            path = "v2/auth/r/positions"
            nonce = self._nonce()
            body = '{}'
            headers = self._headers(path, nonce, body)
            
            response = requests.post(
                url=f"{self.API_URL}/{path}",
                headers=headers,
                data=body
            )
            
            # Verifica la risposta
            if response.status_code == 200:
                try:
                    raw_positions = response.json()
                    logger.info(f"DEBUG - Risposta API posizioni: {raw_positions}")
                    
                    # Formatta le posizioni in un formato più utilizzabile
                    positions = []
                    
                    for pos in raw_positions:
                        if isinstance(pos, list) and len(pos) > 2:
                            # Bitfinex restituisce un array con valori in posizioni specifiche
                            position = {
                                "symbol": pos[0],  # Il simbolo è il primo elemento
                                "status": pos[1],  # Lo stato è il secondo elemento
                                "amount": float(pos[2]) if len(pos) > 2 and pos[2] is not None else 0,  # La quantità è il terzo elemento
                                "base_price": float(pos[3]) if len(pos) > 3 and pos[3] is not None else 0,
                                "funding": float(pos[4]) if len(pos) > 4 and pos[4] is not None else 0,
                                "funding_type": int(pos[5]) if len(pos) > 5 and pos[5] is not None else 0,
                                "pnl": float(pos[6]) if len(pos) > 6 and pos[6] is not None else None,
                                "pnl_perc": float(pos[7]) if len(pos) > 7 and pos[7] is not None else None,
                                "price_liq": float(pos[8]) if len(pos) > 8 and pos[8] is not None else None,
                                "leverage": float(pos[9]) if len(pos) > 9 and pos[9] is not None else None,
                                "side": "long" if float(pos[2]) > 0 else "short" if float(pos[2]) < 0 else "none",
                                # Campi aggiuntivi se disponibili
                                "position_id": int(pos[11]) if len(pos) > 11 and pos[11] is not None else None,
                                # Campi per il collaterale (aggiunti nel 2019)
                                "collateral": float(pos[17]) if len(pos) > 17 and pos[17] is not None else None,
                                "collateral_min": float(pos[18]) if len(pos) > 18 and pos[18] is not None else None
                            }
                            
                            # Aggiungo i campi nel formato CCXT per compatibilità con la funzione format_position_data
                            position['entryPrice'] = position['base_price']
                            position['liquidationPrice'] = position['price_liq']
                            position['unrealizedPnl'] = position['pnl']
                            position['contracts'] = abs(position['amount'])
                            position['raw_size'] = position['amount']
                            position['initial_margin'] = position['collateral']
                            
                            positions.append(position)
                    
                    return {"success": True, "positions": positions, "raw": raw_positions}
                except Exception as e:
                    logger.error(f"Eccezione durante l'elaborazione delle posizioni: {str(e)}")
                    return {"error": f"Errore nel processare la risposta: {str(e)}", "raw": response.text}
            else:
                # Gestione errori HTTP
                error_msg = f"Errore API ({response.status_code}): {response.text}"
                logger.error(error_msg)
                return {"error": error_msg}
                
        except Exception as e:
            logger.error(f"Eccezione durante la richiesta a Bitfinex: {str(e)}")
            return {"error": f"Errore di connessione: {str(e)}"}

    def set_position_collateral(self, symbol, collateral):
        """
        Imposta il collaterale per una posizione derivata
        
        Args:
            symbol (str): Simbolo della posizione nel formato Bitfinex (es. "tBTCF0:USTF0")
            collateral (float): Importo di collaterale da impostare
            
        Returns:
            dict: Risultato dell'operazione
        """
        logger.info(f"[DEBUG] Richiesta di impostazione collaterale - Simbolo originale: '{symbol}', Collaterale: {collateral}")
        
        # Controllo se le API key sono presenti
        if not self.API_KEY or not self.API_SECRET:
            return {"error": "API key o secret non configurati"}
        
        # Ottieni prima le posizioni aperte per verificare quali simboli esistono realmente
        logger.info("[DEBUG] Recupero posizioni aperte per verificare i simboli esistenti...")
        
        try:
            # Richiesta per ottenere le posizioni attive
            positions_path = "v2/auth/r/positions"
            positions_nonce = self._nonce()
            positions_body = '{}'
            positions_headers = self._headers(positions_path, positions_nonce, positions_body)
            
            positions_response = requests.post(
                url=f"{self.API_URL}/{positions_path}",
                headers=positions_headers,
                data=positions_body
            )
            
            if positions_response.status_code == 200:
                positions = positions_response.json()
                logger.info(f"[DEBUG] Posizioni trovate: {positions}")
                
                # Verifica se il simbolo esiste tra le posizioni
                position_symbol = None
                for pos in positions:
                    if isinstance(pos, list) and len(pos) > 0:
                        pos_symbol = pos[0]
                        logger.info(f"[DEBUG] Simbolo posizione trovata: '{pos_symbol}'")
                        
                        # Controlla corrispondenza esatta
                        if pos_symbol == symbol:
                            position_symbol = pos_symbol
                            logger.info(f"[DEBUG] Corrispondenza esatta trovata: '{position_symbol}'")
                            break
                        
                        # Controlla corrispondenza per parte del simbolo (ad es. SOL)
                        if 'SOL' in symbol.upper() and 'SOL' in pos_symbol.upper():
                            position_symbol = pos_symbol
                            logger.info(f"[DEBUG] Corrispondenza per SOL trovata: '{position_symbol}'")
                            break
                
                # Se abbiamo trovato una posizione corrispondente, usa quel simbolo
                if position_symbol:
                    logger.info(f"[DEBUG] Utilizzo il simbolo trovato: '{position_symbol}'")
                    symbol = position_symbol
            else:
                logger.warning(f"[DEBUG] Errore nel recuperare le posizioni: {positions_response.status_code} - {positions_response.text}")
        except Exception as e:
            logger.error(f"[DEBUG] Eccezione nel recuperare le posizioni: {str(e)}")
            
        # Assicurati che il simbolo sia nel formato corretto
        if not symbol.startswith('t'):
            old_symbol = symbol
            symbol = 't' + symbol
            logger.info(f"[DEBUG] Aggiunto prefisso 't' al simbolo: '{old_symbol}' -> '{symbol}'")
            
        # Assicurati che sia un derivato
        if not ':' in symbol and not 'F0' in symbol:
            old_symbol = symbol
            # Converti nel formato corretto
            symbol = self._convert_to_bitfinex_symbol(old_symbol, is_futures=True)
            logger.info(f"[DEBUG] Convertito formato simbolo: '{old_symbol}' -> '{symbol}'")
            
        # Crea il payload della richiesta
        payload = {
            "symbol": symbol,
            "collateral": float(collateral)
        }
        
        logger.info(f"[DEBUG] Payload finale: {payload}")
        
        # Esegui la richiesta
        path = "v2/auth/w/deriv/collateral/set"
        nonce = self._nonce()
        body = json.dumps(payload)
        headers = self._headers(path, nonce, body)
        
        logger.info(f"[DEBUG] Invio richiesta a {self.API_URL}/{path}")
        
        try:
            response = requests.post(
                url=f"{self.API_URL}/{path}",
                headers=headers,
                data=body
            )
            
            logger.info(f"[DEBUG] Risposta ricevuta: status={response.status_code}, corpo={response.text}")
            
            # Verifica la risposta
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    
                    # La risposta dovrebbe essere [1] se l'operazione ha avuto successo
                    if isinstance(response_data, list) and len(response_data) > 0 and response_data[0] == 1:
                        logger.info(f"[DEBUG] Collaterale impostato con successo a {collateral} per {symbol}")
                        return {"success": True, "status": "ok", "collateral": collateral, "symbol": symbol}
                    
                    # Risposta [[1]] indica successo per l'API di Bitfinex
                    if isinstance(response_data, list) and len(response_data) > 0 and isinstance(response_data[0], list) and len(response_data[0]) > 0 and response_data[0][0] == 1:
                        logger.info(f"[DEBUG] Collaterale impostato con successo a {collateral} per {symbol} (formato risposta [[1]])")
                        return {"success": True, "status": "ok", "collateral": collateral, "symbol": symbol}
                    
                    # Gestisci errori specifici
                    if isinstance(response_data, list) and len(response_data) > 0 and response_data[0] == 0:
                        logger.error(f"[DEBUG] Errore nell'impostare il collaterale: operazione non riuscita. Risposta: {response_data}")
                        return {"error": "Operazione non riuscita", "raw": response_data}
                        
                    # Errore generico
                    logger.error(f"[DEBUG] Errore nell'impostare il collaterale: risposta inattesa {response_data}")
                    return {"error": "Risposta inattesa", "raw": response_data}
                except Exception as e:
                    logger.error(f"[DEBUG] Eccezione durante l'elaborazione della risposta: {str(e)}")
                    return {"error": f"Errore nel processare la risposta: {str(e)}", "raw": response.text}
            else:
                # Gestione errori HTTP
                error_msg = f"Errore API ({response.status_code})"
                try:
                    error_data = response.json()
                    if isinstance(error_data, list) and error_data[0] == 'error':
                        error_details = error_data[2] if len(error_data) > 2 else "Dettagli non disponibili"
                        error_msg = f"{error_msg}: {error_details}"
                except:
                    error_msg = f"{error_msg}: {response.text}"
                    
                logger.error(f"[DEBUG] {error_msg}")
                return {"error": error_msg}
                
        except Exception as e:
            logger.error(f"[DEBUG] Eccezione durante la richiesta a Bitfinex: {str(e)}")
            return {"error": f"Errore di connessione: {str(e)}"}

    def get_funding_history(self, symbol, start_time=None, end_time=None, count=1000):
        """
        Ottiene la cronologia storica dei funding rate utilizzando l'endpoint di Bitfinex
        
        Args:
            symbol (str): Simbolo per cui ottenere la cronologia dei funding rate
            start_time (str, optional): Timestamp di inizio in formato ISO 8601
            end_time (str, optional): Timestamp di fine in formato ISO 8601
            count (int, optional): Numero massimo di record da recuperare (default: 1000)
            
        Returns:
            dict: Risultato dell'operazione con i dati dei funding rate
        """
        try:
            # Log del simbolo originale ricevuto
            logger.info(f"Richiesta funding rate history per simbolo originale: {symbol}")
            
            # Determina il simbolo corretto per Bitfinex basato sulla coppia
            base_currency = None
            
            # Estrai la valuta base dal simbolo
            normalized_symbol = symbol.upper().replace('/', '').replace('-', '').replace('_', '')
            if 'USDT' in normalized_symbol:
                base_currency = normalized_symbol.replace('USDT', '')
            elif 'USD' in normalized_symbol:
                base_currency = normalized_symbol.replace('USD', '')
            else:
                base_currency = normalized_symbol  # Assume che sia già la valuta base
            
            # Mappa speciale per casi particolari
            special_mapping = {
                'XBT': 'BTC',  # BitMEX usa XBT per Bitcoin
            }
            
            # Applica la mappatura speciale se necessario
            if base_currency in special_mapping:
                base_currency = special_mapping[base_currency]
            
            # Formatta nel formato di Bitfinex: tXXXF0:USTF0
            bitfinex_symbol = f"t{base_currency}F0:USTF0"
            logger.info(f"Simbolo convertito per Bitfinex: {normalized_symbol} -> {bitfinex_symbol}")
            
            # Parametri della richiesta
            params = {}
            
            # Converti timestamp in millisecondi per Bitfinex
            if start_time:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    params['start'] = int(dt.timestamp() * 1000)
                except Exception as e:
                    logger.warning(f"Impossibile convertire start_time: {start_time}. Errore: {str(e)}")
            
            if end_time:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                    params['end'] = int(dt.timestamp() * 1000)
                except Exception as e:
                    logger.warning(f"Impossibile convertire end_time: {end_time}. Errore: {str(e)}")
            
            # Imposta il limite se specificato
            if count and count > 0:
                params['limit'] = min(count, 250)  # Limita a 250 elementi
            
            # Costruisci l'URL direttamente come negli esempi della documentazione
            # Esempio: https://api-pub.bitfinex.com/v2/status/deriv/tBTCF0:USTF0/hist
            encoded_symbol = urllib.parse.quote(bitfinex_symbol)
            url = f"{self.API_URL}/v2/status/deriv/{encoded_symbol}/hist"
            
            logger.info(f"Chiamata API funding rate history: {url} con parametri: {params}")
            
            # Esegui la richiesta API
            response = requests.get(url, params=params)
            
            # Verifica la risposta HTTP
            if response.status_code != 200:
                logger.error(f"Errore API: status code {response.status_code}, response: {response.text}")
                
                # Prova con il simbolo BTC come fallback (solo se non era già BTC)
                if base_currency != 'BTC':
                    fallback_url = f"{self.API_URL}/v2/status/deriv/tBTCF0:USTF0/hist"
                    logger.info(f"Tentativo con simbolo fallback BTC: {fallback_url}")
                    
                    fallback_response = requests.get(fallback_url, params=params)
                    if fallback_response.status_code == 200:
                        result = fallback_response.json()
                        # Mantieni il simbolo originale per visualizzazione
                        logger.info(f"Fallback BTC riuscito, elaboro i dati")
                    else:
                        return {"error": f"Impossibile recuperare dati per {symbol} su Bitfinex"}
                else:
                    return {"error": f"Errore API Bitfinex: {response.status_code}, {response.text}"}
            else:
                result = response.json()
            
            # Verifica il contenuto della risposta
            if not isinstance(result, list) or len(result) == 0:
                logger.error(f"Risposta non valida o vuota: {result}")
                return {"error": f"Nessun dato di funding rate disponibile per {symbol} su Bitfinex"}
            
            # Log della risposta per debug
            logger.info(f"Risposta API: primi 2 elementi: {result[:2] if len(result) >= 2 else result}")
            
            # Processo i dati
            funding_history = []
            
            for entry in result:
                try:
                    if isinstance(entry, list):
                        # Il formato della risposta di Bitfinex è un array di array:
                        # [0] = MTS - timestamp in millisecondi
                        # [1] = FRR - funding rate in tempo reale (questo è il più affidabile!)
                        # [11] = CURRENT_FUNDING - funding applicato nel periodo corrente
                        
                        if len(entry) >= 2:  # Assicurati che ci siano almeno timestamp e FRR
                            timestamp_ms = int(entry[0])
                            
                            # Prova a leggere il funding rate nel campo più appropriato
                            funding_rate = None
                            
                            # FRR (indice 1) è il valore più affidabile per il funding rate
                            if len(entry) > 1 and entry[1] is not None:
                                funding_rate = float(entry[1])
                                logger.info(f"Usato FRR (indice 1): {funding_rate}")
                            # Se FRR non è disponibile, prova CURRENT_FUNDING (indice 11)
                            elif len(entry) > 11 and entry[11] is not None:
                                funding_rate = float(entry[11])
                                logger.info(f"Usato CURRENT_FUNDING (indice 11): {funding_rate}")
                            
                            # Procedi solo se è stato trovato un valore valido
                            if funding_rate is not None:
                                # Converti il timestamp in formato ISO
                                from datetime import datetime
                                dt = datetime.fromtimestamp(timestamp_ms / 1000)
                                iso_timestamp = dt.isoformat()
                                
                                # Normalizza il funding rate se necessario
                                # Bitfinex potrebbe fornire il tasso in percentuale (es. 0.01%)
                                # o come valore decimale (es. 0.0001)
                                if abs(funding_rate) > 1:
                                    funding_rate = funding_rate / 100
                                
                                # Calcola il tasso giornaliero (3 pagamenti al giorno)
                                funding_rate_daily = funding_rate * 3 * 100  # Converti in percentuale
                                
                                # Crea l'oggetto funding
                                funding_item = {
                                    'timestamp': iso_timestamp,
                                    'symbol': symbol,
                                    'fundingRate': funding_rate,
                                    'fundingRateDaily': funding_rate_daily,
                                    'fundingInterval': '8h'  # Bitfinex usa intervalli di 8 ore
                                }
                                
                                funding_history.append(funding_item)
                except Exception as e:
                    logger.warning(f"Errore nell'elaborazione di un record: {str(e)}")
            
            # Ordina per timestamp (più recente prima)
            funding_history.sort(key=lambda x: x['timestamp'], reverse=True)
            
            # Verifica se abbiamo ottenuto dati
            if not funding_history:
                return {"error": f"Nessun dato di funding rate disponibile per {symbol} su Bitfinex"}
            
            # Log dei risultati
            logger.info(f"Recuperati {len(funding_history)} funding rate per {symbol}")
            
            return {
                "success": True,
                "funding_history": funding_history
            }
            
        except Exception as e:
            logger.error(f"Errore nel recuperare funding history: {str(e)}", exc_info=True)
            return {"error": str(e)}