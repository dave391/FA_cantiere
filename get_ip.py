from transfer import TransferAPI

def main():
    # Crea un'istanza di TransferAPI
    transfer_api = TransferAPI()
    
    # Ottieni l'IP pubblico
    ip = transfer_api.get_public_ip()
    
    if ip:
        print("\n=== Informazioni IP ===")
        print(f"Il tuo IP pubblico è: {ip}")
        print("\nQuesto è l'IP che devi aggiungere alla whitelist di ByBit:")
        print("1. Accedi al tuo account ByBit")
        print("2. Vai in Account -> API Management")
        print("3. Seleziona la tua API key")
        print("4. Nella sezione 'IP Restriction', aggiungi questo IP:", ip)
        print("5. Salva le modifiche")
    else:
        print("Impossibile ottenere l'IP pubblico. Verifica la tua connessione internet.")

if __name__ == "__main__":
    main() 