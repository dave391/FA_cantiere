# Trading Platform per Futures Perpetui

Un'applicazione sviluppata con Python e Streamlit per il trading di futures perpetui su diverse piattaforme di exchange (BitMEX, Bitfinex e ByBit) utilizzando CCXT e API native.

## Caratteristiche

### Trading Semplice
- Supporto per BitMEX, Bitfinex e ByBit
- Integrazione con CCXT o implementazioni native API
- Gestione automatica dei diversi formati di simboli per gli exchange
- Supporto per ordini market e limit
- Gestione delle specifiche di ogni exchange (dimensioni dei lotti, moltiplicatori, ecc.)

### Funding Arbitrage
- Apertura simultanea di posizioni LONG e SHORT su SOLANA su exchange differenti
- Selezione indipendente degli exchange per posizioni long e short
- Ricerca automatica dei contratti SOLANA su ogni exchange
- Supporto per ordini market e limit con prezzi differenti

## Soluzioni Implementate

### BitMEX
- Correzione dell'autenticazione API (errore 401) attraverso una corretta generazione della firma HMAC
- Gestione corretta dei contratti lineari USDT
- Implementazione di un moltiplicatore per calcolare l'esposizione reale

### ByBit
- Risoluzione dei problemi con gli ordini minimi (errore "Order does not meet minimum order value 5USDT")
- Gestione corretta delle API per i contratti lineari

### Bitfinex
- Gestione corretta del formato specifico dei simboli (tASSETF0:USTF0)
- Conversione automatica dei formati di simbolo per rendere l'esperienza utente più semplice

## Risoluzione problemi

### Bitfinex
- **Problema di connessione**: In caso di errori di connessione a Bitfinex, l'applicazione ora utilizza il DNS di Google (8.8.8.8 e 8.8.4.4) per la risoluzione dei nomi e aumenta il timeout.
- **Formato simboli**: Gestisce automaticamente il formato corretto dei simboli (es. tSOLF0:USTF0 per SOLANA).
- **Implementazione fallback**: In caso di errori con CCXT, utilizza automaticamente l'implementazione nativa di Bitfinex come fallback.

### BitMEX
- **Quantità minima**: Per SOLANA, viene applicato automaticamente un minimo di 1000 contratti per rispettare i requisiti di BitMEX.
- **Autenticazione**: Implementa header corretti per l'autenticazione.

### Suggerimenti generali
- Se riscontri problemi con un exchange, verifica che le chiavi API siano corrette e abbiano i permessi necessari.
- Controlla che la quantità specificata rispetti i requisiti minimi dell'exchange.
- Per ordini limite, assicurati che il prezzo sia realistico e all'interno dei limiti di mercato.

## Requisiti

```
streamlit==1.31.0
python-dotenv==1.0.0
requests==2.31.0
pandas==2.1.0
plotly==5.18.0
```

## Struttura del Progetto

- `main.py` - Punto di ingresso dell'applicazione, gestisce la selezione della modalità
- `app.py` - Implementazione della modalità Trading Semplice
- `funding_arbitrage.py` - Implementazione della strategia di Funding Arbitrage su SOLANA
- `ccxt_api.py` - Wrapper per la libreria CCXT per uniformare le API tra gli exchange
- `bitmex_api.py` - Implementazione nativa API BitMEX
- `bybit_api.py` - Implementazione nativa API ByBit
- `bitfinex_api.py` - Implementazione nativa API Bitfinex

## Configurazione

1. Creare un file `.env` nella directory principale con le chiavi API:

```
BITMEX_API_KEY=your_bitmex_api_key
BITMEX_API_SECRET=your_bitmex_api_secret
BYBIT_API_KEY=your_bybit_api_key
BYBIT_API_SECRET=your_bybit_api_secret
BITFINEX_API_KEY=your_bitfinex_api_key
BITFINEX_API_SECRET=your_bitfinex_api_secret
```

2. Installare le dipendenze:
```
pip install -r requirements.txt
```

3. Avviare l'applicazione:
```
streamlit run main.py
```

## Utilizzo

1. Scegliere tra modalità "Trading Semplice" o "Funding Arbitrage" dalla barra laterale
2. Per Trading Semplice:
   - Selezionare l'exchange
   - Selezionare un simbolo dalla lista dei futures disponibili
   - Impostare direzione (long/short) e parametri dell'ordine
   - Inviare l'ordine
3. Per Funding Arbitrage:
   - Selezionare gli exchange per le posizioni LONG e SHORT
   - Impostare la quantità di SOLANA e il tipo di ordine
   - Specificare i prezzi per ordini limit
   - Eseguire la strategia di arbitraggio

## 💱 Trasferimento Bitfinex

Questa funzionalità permette di trasferire fondi internamente tra i diversi wallet di Bitfinex.

### Tipi di wallet supportati:
- **Exchange**: wallet per il trading spot
- **Margin**: wallet per il trading a margine
- **Funding**: wallet per il finanziamento e lo staking

### Funzionalità principali:
- Visualizzazione dei saldi in tempo reale
- Trasferimento tra wallet
- Supporto alla conversione di valute (es. USDT → USTF0 per derivati)
- Monitoraggio delle transazioni

### Configurazione
Per utilizzare questa funzionalità, è necessario configurare le API keys di Bitfinex nel file `.env`:

```
BITFINEX_API_KEY=la_tua_api_key
BITFINEX_API_SECRET=il_tuo_api_secret
```

Le API keys devono avere i permessi di lettura dei saldi e di trasferimento fondi.

### Come utilizzare
1. Seleziona "💱 Bitfinex Transfer" dal menu di navigazione
2. Verifica lo stato delle API keys con l'apposito pulsante
3. Visualizza i saldi attuali dei wallet
4. Compila il form di trasferimento:
   - Seleziona wallet di origine e destinazione
   - Scegli la valuta da trasferire
   - Opzionalmente, scegli una valuta di destinazione per la conversione
   - Inserisci l'importo da trasferire
5. Conferma il trasferimento
6. Monitora lo stato della transazione

### Note importanti
- La conversione da USDT a USTF0 è necessaria per il trading di derivati
- Per il wallet dei derivati, utilizzare 'margin' come destinazione e 'USTF0' come valuta di destinazione
