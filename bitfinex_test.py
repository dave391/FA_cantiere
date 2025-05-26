import ccxt
import time

print(f"CCXT versione: {ccxt.__version__}")

try:
    print("Tentativo di connessione a Bitfinex...")
    
    # Configurazione più robusta dell'exchange
    exchange = ccxt.bitfinex({
        'enableRateLimit': True,
        'timeout': 60000,  # 60 secondi di timeout
        'options': {
            'adjustForTimeDifference': True
        }
    })
    
    # Prova fino a 3 volte a caricare i mercati
    max_retries = 3
    retry_delay = 2  # secondi
    
    for attempt in range(max_retries):
        try:
            print(f"Tentativo {attempt+1}...")
            markets = exchange.load_markets()
            print("Connessione a Bitfinex riuscita!")
            break
        except Exception as e:
            print(f"Tentativo {attempt+1} fallito: {str(e)}")
            if attempt < max_retries - 1:
                print(f"Riprovo tra {retry_delay} secondi...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Aumenta il ritardo ad ogni tentativo
            else:
                raise  # Rilancia l'errore all'ultimo tentativo
    
    # Mostra il numero totale di simboli
    print(f"Totale simboli trovati: {len(markets)}")
    
    # Classifica i simboli per tipo
    symbol_types = {}
    
    # Mostra i primi 20 simboli generici
    print("\nPrimi 20 simboli (generici):")
    sample_symbols = list(markets.keys())[:20]
    for symbol in sample_symbols:
        print(f"- {symbol}")
        
        # Classifica i simboli in base al loro pattern
        if ':' in symbol:
            prefix = 'con_due_punti'
        elif 'F0' in symbol:
            prefix = 'con_F0'
        elif symbol.startswith('t'):
            prefix = 'con_t_prefix'
        else:
            prefix = 'altri'
            
        if prefix not in symbol_types:
            symbol_types[prefix] = []
        symbol_types[prefix].append(symbol)
    
    # Cerca specificamente simboli che potrebbero essere futures perpetui
    print("\nCerca pattern comuni dei futures perpetui:")
    potential_futures = []
    
    # Patterns che potrebbero indicare futures perpetui
    patterns = ['F0:', 'PERP', 'SWAP', 'USDT', 'USD-PERP', 'USD-SWAP']
    
    for pattern in patterns:
        matching = [s for s in markets.keys() if pattern in s]
        print(f"Simboli con pattern '{pattern}': {len(matching)}")
        if matching:
            print(f"Esempi: {', '.join(matching[:5])}")
            potential_futures.extend(matching)
    
    # Controlla le caratteristiche di un simbolo comune come BTC/USDT per vedere come sono strutturati
    print("\nDettagli di un simbolo comune:")
    common_symbols = ['BTC/USDT', 'ETH/USDT', 'tBTCUSD', 'tBTCUST']
    for symbol in common_symbols:
        if symbol in markets:
            market_detail = markets[symbol]
            print(f"\nDettagli di {symbol}:")
            print(f"- Tipo: {market_detail.get('type', 'non specificato')}")
            print(f"- Spot: {market_detail.get('spot', False)}")
            print(f"- Future: {market_detail.get('future', False)}")
            print(f"- Swap: {market_detail.get('swap', False)}")
            
            # Stampa anche le chiavi principali disponibili
            print(f"- Chiavi disponibili: {', '.join(market_detail.keys())}")
    
    # Stampa i tipi di simboli trovati
    print("\nTipi di simboli trovati:")
    for type_name, symbols in symbol_types.items():
        print(f"- {type_name}: {len(symbols)} simboli")
        if symbols:
            print(f"  Esempi: {', '.join(symbols[:3])}")
            
except Exception as e:
    print(f"ERRORE: {str(e)}") 