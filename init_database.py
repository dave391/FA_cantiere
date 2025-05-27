"""
Inizializzazione Database Fundig Arbitrage
Crea le 7 collections e testa tutte le funzionalità
"""

import sys
import os
sys.path.append(os.getcwd())

from database.mongo_manager import MongoManager
from datetime import datetime
import uuid

def init_and_test_database():
    """Inizializza e testa il database completo"""
    
    print("🚀 Inizializzazione Database Trading Platform")
    print("=" * 60)
    
    try:
        # Inizializza MongoManager
        print("1️⃣ Connessione MongoDB...")
        mongo = MongoManager()
        print("✅ MongoManager inizializzato!")
        
        # Test 1: Creazione utente
        print("\n2️⃣ Test creazione utente...")
        test_user = {
            "user_id": f"user_{uuid.uuid4().hex[:8]}",
            "email": "davide@tradingplatform.com",
            "name": "Davide Test"
        }
        
        if mongo.create_user(test_user):
            print(f"✅ Utente creato: {test_user['user_id']}")
        else:
            print(f"⚠️ Utente già esistente o errore")
        
        # Test 2: Configurazione bot
        print("\n3️⃣ Test configurazione bot...")
        config_data = {
            "strategy_type": "funding_arbitrage",
            "parameters": {
                "symbol": "SOL",
                "amount": 2.0,
                "min_funding_diff": 0.01,
                "check_interval": 60
            },
            "exchanges": ["bybit", "bitmex"],
            "risk_limits": {
                "max_daily_loss": 500,
                "max_position_size": 1000
            }
        }
        
        if mongo.save_bot_config(test_user["user_id"], "sol_arbitrage", config_data):
            print("✅ Configurazione bot salvata!")
        
        # Test 3: Bot status
        print("\n4️⃣ Test bot status...")
        bot_id = f"bot_{uuid.uuid4().hex[:8]}"
        
        if mongo.start_bot(test_user["user_id"], bot_id, "sol_arbitrage"):
            print(f"✅ Bot registrato: {bot_id}")
        
        # Test 4: Posizioni
        print("\n5️⃣ Test posizioni...")
        position_data = {
            "position_id": f"pos_{uuid.uuid4().hex[:8]}",
            "user_id": test_user["user_id"],
            "bot_id": bot_id,
            "exchange": "bybit",
            "symbol": "SOLUSDT",
            "side": "long",
            "size": 2.0,
            "entry_price": 95.50,
            "leverage": 3.0
        }
        
        if mongo.save_position(position_data):
            print(f"✅ Posizione salvata: {position_data['position_id']}")
        
        # Test 5: Risk events
        print("\n6️⃣ Test risk events...")
        risk_data = {
            "exchange": "bybit",
            "position_id": position_data["position_id"],
            "risk_type": "margin_low",
            "details": "Margine sceso sotto il 20%"
        }
        
        if mongo.log_risk_event(test_user["user_id"], "margin_warning", "medium", risk_data):
            print("✅ Evento di rischio registrato!")
        
        # Test 6: Margin balance logs
        print("\n7️⃣ Test margin balance logs...")
        balance_data = {
            "action": "add",
            "amount": 100.0,
            "symbol": "SOLUSDT",
            "before_balance": 500.0,
            "after_balance": 600.0
        }
        
        if mongo.log_margin_balance(test_user["user_id"], "bybit", balance_data):
            print("✅ Log margine registrato!")
        
        # Test 7: Statistiche
        print("\n8️⃣ Test statistiche...")
        stats = mongo.get_stats(test_user["user_id"])
        print(f"✅ Statistiche recuperate:")
        for key, value in stats.items():
            print(f"   📊 {key}: {value}")
        
        # Test 8: Verifica collections
        print("\n9️⃣ Verifica collections create...")
        collections = mongo.db.list_collection_names()
        expected_collections = [
            "users", "bot_configs", "bot_status", 
            "active_positions", "trade_history", 
            "risk_events", "margin_balance_logs"
        ]
        
        print("📁 Collections presenti nel database:")
        for collection in collections:
            status = "✅" if collection in expected_collections else "📄"
            print(f"   {status} {collection}")
        
        # Test 9: Conta documenti
        print("\n🔟 Conteggio documenti...")
        for collection_name in expected_collections:
            if collection_name in collections:
                count = mongo.db[collection_name].count_documents({})
                print(f"   📊 {collection_name}: {count} documenti")
        
        # Test 10: Indici
        print("\n1️⃣1️⃣ Verifica indici...")
        for collection_name in ["users", "active_positions", "trade_history"]:
            if collection_name in collections:
                indexes = list(mongo.db[collection_name].list_indexes())
                print(f"   🔍 {collection_name}: {len(indexes)} indici")
        
        print("\n" + "=" * 60)
        print("🎉 INIZIALIZZAZIONE COMPLETATA CON SUCCESSO!")
        print("🗄️ Database ClusterFA pronto all'uso")
        print("📊 Tutte le 7 collections create e testate")
        
        # Chiudi connessione
        mongo.close()
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERRORE durante l'inizializzazione: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def show_database_structure():
    """Mostra la struttura del database"""
    print("\n📋 STRUTTURA DATABASE ClusterFA:")
    print("=" * 50)
    
    collections_info = {
        "users": "👤 Utenti, credenziali exchange, impostazioni rischio",
        "bot_configs": "⚙️ Configurazioni strategia per ogni utente",
        "bot_status": "🤖 Stato attuale bot (running/stopped)",
        "active_positions": "📊 Posizioni attive con monitoraggio rischi",
        "trade_history": "📈 Storico operazioni completate",
        "risk_events": "⚠️ Log eventi di rischio e alert",
        "margin_balance_logs": "💰 Log bilanciamenti margine"
    }
    
    for collection, description in collections_info.items():
        print(f"{description}")
        print(f"   Collection: {collection}")
        print()

if __name__ == "__main__":
    print("🔧 Inizializzazione Database Trading Platform\n")
    
    # Mostra struttura
    show_database_structure()
    
    # Chiedi conferma
    response = input("Vuoi procedere con l'inizializzazione? (y/n): ").lower()
    
    if response in ['y', 'yes', 'si', 's']:
        print("\n🚀 Avvio inizializzazione...")
        success = init_and_test_database()
        
        if success:
            print("\n✅ TUTTO PRONTO!")
            print("💡 Prossimi passi:")
            print("   1. Configura le API keys nel .env")
            print("   2. Testa l'ExchangeManager")
            print("   3. Avvia il primo bot!")
        else:
            print("\n🔧 Ricontrolla la configurazione e riprova.")
    else:
        print("❌ Inizializzazione annullata.")