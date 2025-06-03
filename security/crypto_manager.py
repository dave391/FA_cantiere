"""
Crypto Manager - Gestione crittografia per dati sensibili
"""

import os
import base64
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from dotenv import load_dotenv

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('crypto_manager')

class CryptoManager:
    def __init__(self):
        """Inizializza il gestore di crittografia"""
        load_dotenv()
        
        # Recupera la chiave master dall'ambiente
        self.master_key = os.getenv('MASTER_ENCRYPTION_KEY')
        if not self.master_key:
            logger.warning("MASTER_ENCRYPTION_KEY non trovata nelle variabili d'ambiente. La sicurezza dei dati sensibili è compromessa!")
            # Usa una chiave predefinita solo per sviluppo (NON USARE IN PRODUZIONE)
            self.master_key = "default_insecure_key_only_for_development"
            
        # Deriva la chiave Fernet dalla chiave master
        self.fernet_key = self._derive_key(self.master_key)
        self.cipher_suite = Fernet(self.fernet_key)
        logger.info("Crypto Manager inizializzato")
    
    def _derive_key(self, master_key, salt=b'trading_platform_salt'):
        """
        Deriva una chiave Fernet dalla chiave master
        
        Args:
            master_key: La chiave master come stringa
            salt: Salt per la derivazione della chiave
            
        Returns:
            bytes: Chiave Fernet in formato URL-safe base64
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
        return key
    
    def encrypt(self, plaintext):
        """
        Cripta un testo in chiaro
        
        Args:
            plaintext: Testo in chiaro da criptare
            
        Returns:
            str: Testo criptato in formato base64
        """
        if not plaintext:
            return None
            
        try:
            # Converti il testo in bytes se è una stringa
            if isinstance(plaintext, str):
                plaintext = plaintext.encode('utf-8')
                
            # Cripta i dati
            encrypted_data = self.cipher_suite.encrypt(plaintext)
            
            # Converti in stringa base64 per archiviazione
            return base64.urlsafe_b64encode(encrypted_data).decode('utf-8')
        except Exception as e:
            logger.error(f"Errore durante la crittografia: {str(e)}")
            return None
    
    def decrypt(self, encrypted_text):
        """
        Decripta un testo criptato
        
        Args:
            encrypted_text: Testo criptato in formato base64
            
        Returns:
            str: Testo in chiaro
        """
        if not encrypted_text:
            return None
            
        try:
            # Converti il testo criptato da base64 a bytes
            if isinstance(encrypted_text, str):
                encrypted_data = base64.urlsafe_b64decode(encrypted_text)
            else:
                encrypted_data = encrypted_text
                
            # Decripta i dati
            decrypted_data = self.cipher_suite.decrypt(encrypted_data)
            
            # Converti in stringa
            return decrypted_data.decode('utf-8')
        except Exception as e:
            logger.error(f"Errore durante la decrittografia: {str(e)}")
            return None
    
    def encrypt_api_credentials(self, api_key, api_secret):
        """
        Cripta le credenziali API
        
        Args:
            api_key: API Key in chiaro
            api_secret: API Secret in chiaro
            
        Returns:
            dict: Dizionario con credenziali criptate
        """
        encrypted_key = self.encrypt(api_key)
        encrypted_secret = self.encrypt(api_secret)
        
        return {
            "api_key_encrypted": encrypted_key,
            "api_secret_encrypted": encrypted_secret,
            "is_encrypted": True
        }
    
    def decrypt_api_credentials(self, credentials):
        """
        Decripta le credenziali API
        
        Args:
            credentials: Dizionario con credenziali criptate
            
        Returns:
            dict: Dizionario con credenziali in chiaro
        """
        if not credentials or not credentials.get("is_encrypted", False):
            return credentials
            
        api_key = self.decrypt(credentials.get("api_key_encrypted"))
        api_secret = self.decrypt(credentials.get("api_secret_encrypted"))
        
        return {
            "api_key": api_key,
            "api_secret": api_secret,
            "is_encrypted": False
        }


# Test del modulo
if __name__ == "__main__":
    crypto = CryptoManager()
    
    # Test di crittografia e decrittografia
    test_api_key = "your_api_key_12345"
    test_api_secret = "your_secret_abcdef"
    
    print("Test di crittografia e decrittografia:")
    
    # Cripta le credenziali
    encrypted = crypto.encrypt_api_credentials(test_api_key, test_api_secret)
    print(f"Credenziali criptate: {encrypted}")
    
    # Decripta le credenziali
    decrypted = crypto.decrypt_api_credentials(encrypted)
    print(f"Credenziali decriptate: {decrypted}")
    
    # Verifica
    assert decrypted["api_key"] == test_api_key
    assert decrypted["api_secret"] == test_api_secret
    print("✅ Test completato con successo!") 