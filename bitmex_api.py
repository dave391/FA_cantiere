"""
BitMEX API Wrapper - Checkpoint Version 3.0 (Codice Pulito)
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

# Imposta il livello di log a DEBUG per ottenere più informazioni
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('bitmex_api')

class BitMEXAPI:
    def __init__(self, testnet=False):
        # Carica le variabili d'ambiente
        load_dotenv()
        
        # Assicurati che il file .env sia stato caricato correttamente
        self.API_KEY = os.getenv('BITMEX_API_KEY')
        self.API_SECRET = os.getenv('BITMEX_API_SECRET')
        
        # Controllo delle credenziali e pulizia
        if not self.API_KEY or not self.API_SECRET:
            logger.error("Impossibile caricare le credenziali BitMEX. Verificare il file .env")
            logger.error(f"BITMEX_API_KEY trovata: {'Sì' if self.API_KEY else 'No'}")
            logger.error(f"BITMEX_API_SECRET trovata: {'Sì' if self.API_SECRET else 'No'}")
            
            # Controlla se il file .env esiste
            env_path = os.path.join(os.getcwd(), '.env')
            if os.path.exists(env_path):
                logger.debug(f".env file trovato in {env_path}")
                
                # Controlla il contenuto del file (solo per debug, in produzione non farlo per sicurezza)
                with open(env_path, 'r') as f:
                    content = f.read()
                    logger.debug(f".env contiene riferimenti a BITMEX_API_KEY: {'BITMEX_API_KEY' in content}")
                    logger.debug(f".env contiene riferimenti a BITMEX_API_SECRET: {'BITMEX_API_SECRET' in content}")
            else:
                logger.debug(f"File .env non trovato in {env_path}")
        else:
            # Pulizia avanzata delle credenziali (rimuovi spazi, newline e caratteri invisibili)
            self.API_KEY = ''.join(c for c in self.API_KEY.strip() if c.isprintable())
            self.API_SECRET = ''.join(c for c in self.API_SECRET.strip() if c.isprintable())
            
            # Log (nascosto) delle chiavi per debug
            key_masked = f"{self.API_KEY[:4]}...{self.API_KEY[-4:]}" if len(self.API_KEY) > 8 else "***"
            secret_masked = f"{self.API_SECRET[:4]}...{self.API_SECRET[-4:]}" if len(self.API_SECRET) > 8 else "***"
            logger.info(f"Credenziali BitMEX caricate. API Key: {key_masked}, Secret: {secret_masked}")
            
            # Stampa anche i formati esadecimali per verifica avanzata
            logger.debug(f"API Key hex: {' '.join(hex(ord(c))[2:] for c in self.API_KEY[:4])}...")
            logger.debug(f"API Secret hex: {' '.join(hex(ord(c))[2:] for c in self.API_SECRET[:4])}...")
            
            # Verifica se le credenziali sembrano valide nel formato
            if len(self.API_KEY) < 10:
                logger.warning(f"La BITMEX_API_KEY sembra troppo corta ({len(self.API_KEY)} caratteri). Verificare che sia corretta.")
            if len(self.API_SECRET) < 10:
                logger.warning(f"La BITMEX_API_SECRET sembra troppo corta ({len(self.API_SECRET)} caratteri). Verificare che sia corretta.")
        
        # Imposta l'URL base in base alla modalità testnet
        self.BASE_URL = 'https://testnet.bitmex.com' if testnet else 'https://www.bitmex.com'
        self.API_URL = self.BASE_URL + '/api/v1'
        logger.info(f"BitMEX API URL: {self.BASE_URL}")
        
        # Effettua una richiesta di test per verificare la connessione
        if self.API_KEY and self.API_SECRET:
            try:
                logger.info("Test di connessione BitMEX in corso...")
                self.test_connection()
            except Exception as e:
                logger.warning(f"Errore nel test di connessione BitMEX: {str(e)}")
        
    def test_connection(self):
        """Test di connessione e validità delle API key"""
        try:
            # Controlla le credenziali
            if not self.API_KEY or not self.API_SECRET:
                logger.error("Test fallito: API key o secret non configurati")
                return False
            
            logger.info("Verifica connessione BitMEX...")
            
            # Prova a recuperare informazioni sul wallet
            wallet_result = self._request('GET', '/user/wallet', params={'currency': 'XBt'})
            
            if isinstance(wallet_result, dict) and "error" in wallet_result:
                logger.error(f"Test wallet BitMEX fallito: {wallet_result['error']}")
                return False
            
            # Prova a recuperare le posizioni aperte
            positions_result = self._request('GET', '/position')
            
            if isinstance(positions_result, dict) and "error" in positions_result:
                logger.error(f"Test posizioni BitMEX fallito: {positions_result['error']}")
                return False
            
            # Se arriviamo qui, il test è riuscito
            logger.info("Test di connessione BitMEX riuscito!")
            logger.info(f"Numero di posizioni recuperate: {len(positions_result) if isinstance(positions_result, list) else 'N/A'}")
            return True
        except Exception as e:
            logger.error(f"Errore durante il test di connessione BitMEX: {str(e)}")
            return False
    
    def _generate_signature(self, verb, path, nonce, data=''):
        """Genera la firma HMAC per autenticare le richieste"""
        try:
            if not self.API_SECRET:
                logger.error("API_SECRET non configurata correttamente")
                return ""
                
            # BitMEX richiede una firma specifica nel formato: verb + path + nonce + data
            if data is None:
                data = ''
            
            # Assicuriamoci che path sia nel formato corretto
            if not path.startswith('/api/v1'):
                if not path.startswith('/'):
                    path = '/api/v1/' + path
                else:
                    path = '/api/v1' + path
            
            # Preparazione del messaggio
            message = verb + path + str(nonce) + data
            
            # Log per debug
            logger.debug(f"Dati firma: verb={verb}, path={path}, nonce={nonce}")
            logger.debug(f"Messaggio firma completo: {message}")
            
            # Genera la firma HMAC-SHA256
            signature = hmac.new(
                bytes(self.API_SECRET, 'utf8'),
                bytes(message, 'utf8'),
                digestmod=hashlib.sha256
            ).hexdigest()
            
            logger.debug(f"Firma generata: {signature[:10]}...")
            
            return signature
        except Exception as e:
            logger.error(f"Errore nella generazione della firma: {str(e)}")
            logger.error(f"Dati per firma: verb={verb}, path={path}, nonce={nonce}, data={data}")
            return ""
    
    def _request(self, verb, path, data=None, params=None):
        """Esegue una richiesta all'API di BitMEX"""
        try:
            # Gestisci i parametri e costruisci l'URL corretto
            query = ''
            if params:
                query = '?' + urllib.parse.urlencode(params)
                
            # Determina il path completo con query string per la firma
            full_path = path + query
            
            # Costruisci l'URL completo per la richiesta
            if path.startswith('/api/v1'):
                url = self.BASE_URL + path
            else:
                url = self.API_URL + path
            
            # Prepara i dati JSON
            data_str = ''
            if data is not None:
                data_str = json.dumps(data)
            
            # Verifica che le credenziali siano impostate
            if not self.API_KEY or not self.API_SECRET:
                logger.error(f"API key o secret non configurati. Chiave: {'Configurata' if self.API_KEY else 'Mancante'}, Secret: {'Configurato' if self.API_SECRET else 'Mancante'}")
                return {"error": "API key o secret non configurati"}
            
            # Headers con autenticazione
            expires = int((time.time() + 10) * 1000)  # 10 secondi di scadenza
            
            api_key_debug = f"{self.API_KEY[:4]}...{self.API_KEY[-4:]}" if len(self.API_KEY) > 8 else self.API_KEY
            logger.debug(f"Usando API Key: {api_key_debug}")
            
            # Genera la firma (usa il path completo con query per firmare)
            signature = self._generate_signature(verb, full_path, expires, data_str)
            if not signature:
                return {"error": "Impossibile generare firma valida"}
            
            headers = {
                'content-type': 'application/json',
                'accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'api-expires': str(expires),
                'api-key': self.API_KEY,
                'api-signature': signature
            }
            
            # URL completo per la richiesta
            full_url = url + query
            
            # Log dettagliato per debug
            logger.debug(f"Richiesta {verb} a {full_url}")
            logger.debug(f"Headers di autenticazione: expires={expires}, api-key={api_key_debug}, api-signature={signature[:10]}...")
            if data:
                logger.debug(f"Body della richiesta: {data_str}")
            
            # Esecuzione richiesta HTTP
            response = None
            if verb == 'GET':
                response = requests.get(full_url, headers=headers)
            elif verb == 'POST':
                response = requests.post(full_url, data=data_str, headers=headers)
            elif verb == 'DELETE':
                response = requests.delete(full_url, data=data_str, headers=headers)
            elif verb == 'PUT':
                response = requests.put(full_url, data=data_str, headers=headers)
            else:
                return {"error": f"Metodo HTTP non supportato: {verb}"}
            
            # Log della risposta
            logger.debug(f"Risposta HTTP status: {response.status_code}")
            
            # Controllo status code
            if response.status_code == 200:
                # Risposta con successo
                try:
                    resp_json = response.json()
                    logger.debug(f"Risposta parsata con successo")
                    return resp_json
                except json.JSONDecodeError as e:
                    logger.error(f"Errore nel decodificare la risposta JSON: {e}")
                    logger.error(f"Risposta text: {response.text}")
                    return {"error": f"Risposta non è un JSON valido: {response.text[:100]}..."}
            else:
                # Errore HTTP
                logger.error(f"Errore API HTTP {response.status_code}: {response.text}")
                try:
                    error_json = response.json()
                    # Verifica se è un errore di autenticazione
                    if response.status_code == 401:
                        logger.error("Errore di autenticazione! Verifica API key e secret.")
                        # Log delle prime 4 cifre dell'API key per debug
                        if self.API_KEY:
                            key_prefix = self.API_KEY[:4] if len(self.API_KEY) >= 4 else self.API_KEY
                            logger.error(f"API Key utilizzata: {key_prefix}...")
                    return {"error": f"Errore API ({response.status_code}): {error_json}"}
                except:
                    return {"error": f"Errore API ({response.status_code}): {response.text}"}
                    
        except requests.exceptions.RequestException as e:
            # Errore di rete
            logger.error(f"Errore di rete durante la richiesta: {str(e)}")
            return {"error": f"Errore di rete: {str(e)}"}
        except Exception as e:
            # Errore generico
            logger.error(f"Errore generico durante la richiesta: {str(e)}")
            return {"error": f"Errore generico: {str(e)}"}
    
    def get_perpetual_futures(self):
        """Ottiene la lista dei futures perpetui disponibili su BitMEX"""
        try:
            response = self._request('GET', '/instrument/active')
            
            if not isinstance(response, dict) or "error" not in response:
                # Log per debug
                logger.debug(f"Strumenti totali trovati: {len(response)}")
                
                # Ottieni tutti i futures perpetui
                perpetual_pairs = []
                
                for instr in response:
                    # Linear futures (quotati in USDT)
                    if instr.get('settlCurrency') == 'USDT':
                        perpetual_pairs.append(instr['symbol'])
                        logger.debug(f"Future lineare trovato: {instr['symbol']}")
                
                logger.info(f"Futures lineari trovati: {len(perpetual_pairs)}")
                return perpetual_pairs
            else:
                logger.error(f"Errore nel recuperare futures perpetui: {response}")
                return []
                
        except Exception as e:
            logger.error(f"Eccezione durante il recupero dei futures: {str(e)}")
            return []
            
    def get_instrument_info(self, symbol=None):
        """Ottiene informazioni su uno strumento finanziario specifico o tutti gli strumenti attivi"""
        path = '/instrument'
        params = None
        
        if symbol:
            params = {'symbol': symbol}
        else:
            path += '/active'
        
        response = self._request('GET', path, params=params)
        
        if not isinstance(response, dict) or "error" not in response:
            if symbol:
                # Se cerchiamo un simbolo specifico, restituisci solo quello
                for instr in response:
                    if instr['symbol'] == symbol:
                        return instr
                return None
            else:
                # Altrimenti, restituisci tutti gli strumenti
                return response
        else:
            logger.error(f"Errore nel recuperare informazioni strumenti: {response}")
            return None
    
    def normalize_symbol(self, symbol):
        """Normalizza il formato del simbolo per BitMEX"""
        try:
            # Rimuovi eventuali spazi
            symbol = symbol.strip()
            
            # Log per debug
            logger.debug(f"Normalizzazione simbolo: input={symbol}")
            
            # Se il simbolo contiene ":USDT", rimuovilo (formato errato per BitMEX)
            if ":USDT" in symbol:
                symbol = symbol.replace(":USDT", "")
                logger.debug(f"Rimosso ':USDT' dal simbolo: {symbol}")
            
            # Se il simbolo ha già il formato BitMEX, lascialo invariato
            if symbol.isupper() and not '/' in symbol:
                logger.debug(f"Simbolo già in formato BitMEX: {symbol}")
                return symbol
            
            # Mappatura speciale per alcuni asset (aggiungi qui eventuali casi speciali)
            symbol_mapping = {
                'BTC/USD': 'XBTUSD',
                'BTC/USDT': 'XBTUSDT',
                'SOL/USD': 'SOLUSD',
                'SOL/USDT': 'SOLUSDT',
                'ETH/USD': 'ETHUSD',
                'ETH/USDT': 'ETHUSDT',
                # Aggiungi altri mapping se necessario
            }
            
            # Prova con la mappatura diretta
            if symbol in symbol_mapping:
                normalized = symbol_mapping[symbol]
                logger.debug(f"Simbolo normalizzato da mappatura: {normalized}")
                return normalized
            
            # Se il simbolo contiene la barra CCXT (es. "BTC/USD")
            if '/' in symbol:
                base, quote = symbol.split('/')
                
                # Converti BTC in XBT (BitMEX usa XBT invece di BTC)
                if base.upper() == 'BTC':
                    base = 'XBT'
                
                # Formato "BTCUSD" di BitMEX
                normalized = f"{base.upper()}{quote.upper()}"
                logger.debug(f"Simbolo normalizzato da formato CCXT: {normalized}")
                return normalized
            
            # Altrimenti restituisci il simbolo originale in maiuscolo
            normalized = symbol.upper()
            logger.debug(f"Simbolo normalizzato (default): {normalized}")
            return normalized
            
        except Exception as e:
            logger.error(f"Errore nella normalizzazione del simbolo '{symbol}': {str(e)}")
            # In caso di errore, restituisci il simbolo originale
            return symbol
    
    def submit_order(self, symbol, amount, price=None, market=True):
        """Invia un ordine a BitMEX"""
        try:
            # Normalizza il simbolo
            symbol = self.normalize_symbol(symbol)
            
            # Determina tipo e lato dell'ordine
            side = 'Buy' if amount > 0 else 'Sell'
            abs_amount = abs(int(amount))  # BitMEX richiede valori interi per i contratti
            
            # Per Solana su BitMEX, ci sono 10k contratti per 1 SOL, e un minimo di 1000 contratti
            if 'SOL' in symbol:
                # Esempio: 0.5 SOL dovrebbe essere 5000 contratti
                if abs_amount < 10000:
                    abs_amount = abs_amount * 10000
                
                # BitMEX richiede minimo 1000 contratti per Solana
                if abs_amount < 1000:
                    abs_amount = 1000
                
                # Arrotonda a 100
                old_amount = abs_amount
                abs_amount = round(abs_amount / 100) * 100
                
            # Prepara i parametri dell'ordine
            order_params = {}
            
            # Se è un ordine market o limit
            if market:
                order_params['ordType'] = 'Market'
            else:
                order_params['ordType'] = 'Limit'
                order_params['price'] = price
            
            # Parametri completi dell'ordine
            order_data = {
                'symbol': symbol,
                'side': side,
                'orderQty': abs_amount,
                **order_params
            }
            
            # Invia l'ordine a BitMEX
            return self._request('POST', '/order', data=order_data)
            
        except Exception as e:
            logger.error(f"Eccezione durante l'invio dell'ordine: {str(e)}")
            return {"error": str(e)}
    
    def get_account_info(self):
        """Ottiene informazioni sull'account e sul wallet"""
        try:
            # Ottiene informazioni sul wallet
            wallet_info = self._request('GET', '/user/wallet')
            
            # Ottiene informazioni sul margine
            margin_info = self._request('GET', '/user/margin')
            
            # Ottieni il riepilogo del wallet
            wallet_summary = self._request('GET', '/user/walletSummary')
            
            # Restituisci tutte le informazioni
            return {
                'wallet': wallet_info,
                'margin': margin_info,
                'summary': wallet_summary
            }
        except Exception as e:
            logger.error(f"Errore nel recuperare informazioni account: {str(e)}")
            return {"error": str(e)}
    
    def get_usdt_balance(self):
        """Ottiene il saldo USDT dell'account"""
        try:
            wallet_info = self._request('GET', '/user/wallet')
            
            if not isinstance(wallet_info, dict) or "error" in wallet_info:
                logger.error(f"Errore nel recuperare informazioni wallet: {wallet_info}")
                return 0
            
            # BitMEX usa XBt come unità (satoshi)
            usdt_balance = wallet_info.get('amount', 0) / 100000000
            
            return usdt_balance
            
        except Exception as e:
            logger.error(f"Errore nel recuperare saldo USDT: {str(e)}")
            return 0
    
    def get_open_positions(self, symbol=None):
        """Ottiene le posizioni aperte"""
        try:
            params = {}
            if symbol:
                params['symbol'] = self.normalize_symbol(symbol)
            
            # Aggiungo log per debug
            logger.info(f"Richiesta posizioni BitMEX con parametri: {params}")
            
            response = self._request('GET', '/position', params=params)
            
            # Aggiungo log di risposta per debug
            logger.info(f"Risposta BitMEX posizioni (grezzo): {response}")
            
            if isinstance(response, dict) and "error" in response:
                logger.error(f"Errore nel recuperare posizioni: {response}")
                return []
            
            # Filtra solo le posizioni con quantità non zero
            if isinstance(response, list):
                # Log dettagliato di ogni posizione per debug
                for pos in response:
                    symbol = pos.get('symbol', 'Sconosciuto')
                    qty = pos.get('currentQty', 0)
                    logger.info(f"Posizione trovata: {symbol}, qty: {qty}")
                
                active_positions = [pos for pos in response if pos.get('currentQty', 0) != 0]
                
                logger.info(f"Posizioni attive filtrate: {len(active_positions)} su {len(response)} totali")
                return active_positions
            else:
                logger.error(f"Risposta non valida dall'API: {response}")
                return []
                
        except Exception as e:
            logger.error(f"Eccezione durante il recupero delle posizioni: {str(e)}")
            return []
    
    def close_position(self, symbol, reduce_only=True):
        """Chiude una posizione specifica"""
        try:
            symbol = self.normalize_symbol(symbol)
            
            # Aggiungi log per debug
            logger.info(f"Tentativo di chiusura posizione per il simbolo: {symbol}")
            
            # Ottieni la posizione corrente
            try:
                positions = self.get_open_positions(symbol)
                
                if positions:
                    logger.debug(f"Posizioni trovate: {len(positions)}")
                    for i, pos in enumerate(positions):
                        pos_symbol = pos.get('symbol', 'Unknown')
                        pos_qty = pos.get('currentQty', 0)
                        logger.debug(f"Posizione {i+1}: symbol={pos_symbol}, qty={pos_qty}")
                else:
                    logger.warning(f"Nessuna posizione trovata per {symbol}")
            except Exception as e:
                logger.error(f"Errore nel recuperare posizioni: {str(e)}")
                # Se non riusciamo a recuperare le posizioni, proviamo comunque a chiuderle
                positions = []
            
            # Se non ci sono posizioni, prova a usare l'endpoint diretto di BitMEX per la chiusura
            if not positions:
                logger.info(f"Nessuna posizione attiva trovata per {symbol}. Tentativo di chiusura diretta.")
                
                # Parametri dell'ordine di chiusura diretta
                order_data = {
                    'symbol': symbol,
                    'execInst': 'Close'
                }
                
                # Invia l'ordine direttamente all'endpoint closePosition
                try:
                    logger.info(f"Invio richiesta closePosition diretta: {order_data}")
                    response = self._request('POST', '/order/closePosition', data=order_data)
                    
                    if isinstance(response, dict):
                        if "error" in response:
                            logger.error(f"Errore nella risposta API BitMEX per chiusura diretta: {response['error']}")
                            return response
                        
                        logger.info(f"Risposta chiusura diretta: {response}")
                        return {"success": True, "message": f"Posizione {symbol} chiusa con successo (diretta)", "order": response}
                    else:
                        logger.warning(f"Risposta non standard dalla API: {response}")
                        return {"success": True, "message": f"Posizione chiusa (esito incerto)", "response": response}
                except Exception as direct_err:
                    logger.error(f"Errore nella chiusura diretta: {str(direct_err)}")
                    # Continuiamo con l'approccio standard
            
            # Approccio standard: recupera position e crea ordine inverso
            if positions:
                position = positions[0]
                current_qty = position.get('currentQty', 0)
                
                logger.info(f"Posizione trovata: {symbol}, currentQty={current_qty}")
                
                if current_qty == 0:
                    logger.error(f"Posizione per {symbol} ha quantità 0")
                    return {"error": f"Posizione per {symbol} ha quantità 0"}
                
                # Crea un ordine di segno opposto
                order_qty = -current_qty
                
                # Parametri dell'ordine
                order_data = {
                    'symbol': symbol,
                    'orderQty': order_qty,
                    'ordType': 'Market'
                }
                
                if reduce_only:
                    order_data['execInst'] = 'ReduceOnly'
                
                logger.info(f"Invio ordine di chiusura posizione: {order_data}")
                
                # Invia l'ordine
                response = self._request('POST', '/order', data=order_data)
                
                # Verifica il risultato
                if isinstance(response, dict):
                    if "error" in response:
                        logger.error(f"Errore nella risposta API BitMEX: {response['error']}")
                        return response
                    
                    logger.info(f"Risposta ordine di chiusura posizione: {response}")
                    
                    # Verifica che l'ordine sia stato creato correttamente
                    order_id = response.get('orderID')
                    if order_id:
                        logger.info(f"Ordine creato con successo, ID: {order_id}")
                        
                        # Verifica dopo un breve ritardo se la posizione è stata effettivamente chiusa
                        time.sleep(2)  # Attendi 2 secondi
                        positions_after = self.get_open_positions(symbol)
                        
                        if not positions_after:
                            logger.info(f"Posizione {symbol} chiusa con successo")
                            return {"success": True, "message": f"Posizione {symbol} chiusa con successo", "order": response}
                        
                        for pos in positions_after:
                            pos_symbol = pos.get('symbol', '')
                            pos_qty = pos.get('currentQty', 0)
                            
                            if pos_symbol == symbol and pos_qty != 0:
                                logger.warning(f"Posizione {symbol} ancora aperta dopo ordine di chiusura (qty={pos_qty})")
                                return {"warning": f"Ordine inviato ma posizione ancora aperta (qty={pos_qty})", "order": response}
                        
                        return {"success": True, "message": f"Posizione {symbol} chiusa con successo", "order": response}
                    else:
                        logger.warning(f"Ordine inviato ma nessun ID ordine nella risposta")
                        return {"warning": "Ordine inviato ma nessun ID ordine nella risposta", "response": response}
                else:
                    logger.error(f"Risposta non valida dall'API: {response}")
                    return {"error": f"Risposta non valida dall'API: {response}"}
            else:
                # Già provato approccio diretto, restituisci errore
                return {"error": f"Nessuna posizione attiva trovata per {symbol} e la chiusura diretta ha fallito"}
            
        except Exception as e:
            logger.error(f"Errore nel chiudere la posizione: {str(e)}")
            return {"error": str(e)}
    
    def adjust_position_margin(self, symbol, amount):
        """
        Aggiunge o rimuove margine da una posizione aperta
        
        Args:
            symbol (str): Simbolo della posizione
            amount (int): Importo di margine da aggiungere (positivo) o rimuovere (negativo) in satoshi
            
        Returns:
            dict: Risultato dell'operazione
        """
        try:
            # Normalizza il simbolo
            symbol = self.normalize_symbol(symbol)
            logger.info(f"Modifica margine per simbolo normalizzato: {symbol}, importo: {amount}")
            
            # Ottieni la posizione corrente
            positions = self.get_open_positions(symbol)
            
            if isinstance(positions, dict) and "error" in positions:
                logger.error(f"Errore nel recuperare posizione: {positions['error']}")
                return {"error": f"Errore nel recuperare posizione: {positions['error']}"}
                
            # Verifica se esiste una posizione per questo simbolo
            position_exists = False
            for pos in positions:
                if pos.get('symbol', '') == symbol:
                    position_exists = True
                    logger.info(f"Trovata posizione attiva per {symbol}")
                    break
                    
            if not position_exists:
                # Prova con SOLUSD se il simbolo era SOLUSDT
                if symbol == "SOLUSDT":
                    alternative_symbol = "SOLUSD"
                    logger.info(f"Posizione non trovata con {symbol}, tentativo con {alternative_symbol}")
                    positions = self.get_open_positions(alternative_symbol)
                    
                    if isinstance(positions, list):
                        for pos in positions:
                            if pos.get('symbol', '') == alternative_symbol:
                                position_exists = True
                                symbol = alternative_symbol
                                logger.info(f"Trovata posizione attiva per {alternative_symbol}")
                                break
            
            if not position_exists:
                logger.error(f"Nessuna posizione attiva trovata per {symbol}")
                return {"error": f"Nessuna posizione attiva trovata per {symbol}"}
            
            # Prepara la richiesta di modifica margine
            data = {
                'symbol': symbol,
                'amount': amount  # BitMEX usa valori in satoshi (1 USDT = 1,000,000 satoshi)
            }
            
            logger.info(f"Invio richiesta di trasferimento margine: {data}")
            
            # Invia la richiesta utilizzando l'endpoint corretto per transferMargin
            response = self._request('POST', '/position/transferMargin', data=data)
            
            if isinstance(response, dict) and "error" in response:
                logger.error(f"Errore BitMEX nella modifica del margine: {response['error']}")
                return {"error": response.get('error')}
            
            logger.info(f"Risposta BitMEX trasferimento margine: {response}")
            return {"success": True, "data": response}
            
        except Exception as e:
            logger.error(f"Errore nell'aggiustare il margine: {str(e)}")
            return {"error": str(e)}

    def get_funding_history(self, symbol, start_time=None, end_time=None, count=500):
        """
        Ottiene la cronologia dei funding rate per un simbolo specifico
        
        Args:
            symbol (str): Simbolo per cui ottenere la cronologia dei funding rate
            start_time (str, optional): Timestamp di inizio in formato ISO 8601
            end_time (str, optional): Timestamp di fine in formato ISO 8601
            count (int, optional): Numero massimo di record da recuperare (default: 500)
            
        Returns:
            dict: Risultato dell'operazione con i dati dei funding rate
        """
        try:
            params = {'symbol': symbol, 'count': count, 'reverse': True}
            
            if start_time:
                params['startTime'] = start_time
                
            if end_time:
                params['endTime'] = end_time
                
            # Richiedi i funding rate storici
            funding_history = self._request('GET', '/funding', params=params)
            
            if isinstance(funding_history, dict) and "error" in funding_history:
                logger.error(f"Errore nel recuperare funding history: {funding_history['error']}")
                return {"error": funding_history.get('error')}
                
            logger.info(f"Recuperati {len(funding_history)} funding rate per {symbol}")
            
            # Formatta i risultati
            formatted_funding = []
            for item in funding_history:
                formatted_item = {
                    'timestamp': item.get('timestamp'),
                    'symbol': item.get('symbol'),
                    'fundingRate': item.get('fundingRate'),
                    'fundingRateDaily': item.get('fundingRate') * 3 * 100 if item.get('fundingRate') else None,  # Tasso giornaliero in percentuale
                    'fundingInterval': item.get('fundingInterval')
                }
                formatted_funding.append(formatted_item)
                
            return {"success": True, "funding_history": formatted_funding}
            
        except Exception as e:
            logger.error(f"Errore nel recuperare funding history: {str(e)}")
            return {"error": str(e)}