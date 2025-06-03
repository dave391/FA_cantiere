"""
Auth Manager - Gestione autenticazione utenti
"""

import os
import logging
from datetime import datetime, timedelta, timezone
import uuid
import hashlib
import secrets
import base64

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('auth_manager')

class AuthManager:
    def __init__(self, db=None):
        """Inizializza il gestore di autenticazione"""
        self.db = db
        logger.info("Auth Manager inizializzato")
        
        # Se non c'è database, usa una memoria temporanea (solo per test)
        if not self.db:
            logger.warning("Nessun database disponibile, usando storage in memoria (solo per test)")
            self._temp_users = {}
            self._temp_sessions = {}
    
    def authenticate_user(self, email, password):
        """
        Autentica un utente con email e password
        
        Args:
            email: Email dell'utente
            password: Password dell'utente
        
        Returns:
            str: user_id se autenticazione riuscita, None altrimenti
        """
        try:
            # Hash della password per confronto
            password_hash = self._hash_password(password)
            
            if self.db:
                # Recupera utente dal database
                user = self.db.users.find_one({"email": email})
                
                if user and user.get("password_hash") == password_hash:
                    logger.info(f"Autenticazione riuscita per: {email}")
                    return user.get("user_id")
                else:
                    logger.warning(f"Autenticazione fallita per: {email}")
                    return None
            else:
                # Versione per test senza database
                if email in self._temp_users and self._temp_users[email]["password_hash"] == password_hash:
                    logger.info(f"Autenticazione riuscita per: {email} (modalità test)")
                    return self._temp_users[email]["user_id"]
                else:
                    logger.warning(f"Autenticazione fallita per: {email} (modalità test)")
                    return None
                
        except Exception as e:
            logger.error(f"Errore durante l'autenticazione: {str(e)}")
            return None
    
    def create_user_session(self, user_id):
        """
        Crea una nuova sessione per un utente autenticato
        
        Args:
            user_id: ID dell'utente autenticato
        
        Returns:
            str: Token di sessione
        """
        try:
            # Genera un token di sessione unico
            session_token = self._generate_session_token()
            
            # Data di scadenza (7 giorni)
            expiry = datetime.now(timezone.utc) + timedelta(days=7)
            
            # Dati sessione
            session_data = {
                "session_id": f"session_{uuid.uuid4().hex[:8]}",
                "user_id": user_id,
                "token": session_token,
                "created_at": datetime.now(timezone.utc),
                "expires_at": expiry,
                "last_activity": datetime.now(timezone.utc),
                "is_active": True
            }
            
            if self.db:
                # Salva sessione nel database
                self.db.sessions.insert_one(session_data)
            else:
                # Versione per test senza database
                self._temp_sessions[session_token] = session_data
            
            logger.info(f"Nuova sessione creata per utente: {user_id}")
            return session_token
            
        except Exception as e:
            logger.error(f"Errore durante la creazione della sessione: {str(e)}")
            return None
    
    def validate_session(self, session_token):
        """
        Verifica se una sessione è valida
        
        Args:
            session_token: Token di sessione da validare
        
        Returns:
            dict: Dati dell'utente se la sessione è valida, None altrimenti
        """
        try:
            session_data = None
            
            if self.db:
                # Recupera la sessione dal database
                session_data = self.db.sessions.find_one({
                    "token": session_token,
                    "is_active": True,
                    "expires_at": {"$gt": datetime.now(timezone.utc)}
                })
            else:
                # Versione per test senza database
                if (session_token in self._temp_sessions and 
                    self._temp_sessions[session_token]["is_active"] and 
                    self._temp_sessions[session_token]["expires_at"] > datetime.now(timezone.utc)):
                    session_data = self._temp_sessions[session_token]
            
            if not session_data:
                logger.warning(f"Sessione non valida o scaduta: {session_token}")
                return None
            
            # Aggiorna l'ultima attività
            user_id = session_data["user_id"]
            
            if self.db:
                self.db.sessions.update_one(
                    {"token": session_token},
                    {"$set": {"last_activity": datetime.now(timezone.utc)}}
                )
                
                # Recupera i dati dell'utente
                user_data = self.db.users.find_one({"user_id": user_id})
            else:
                # Versione per test senza database
                self._temp_sessions[session_token]["last_activity"] = datetime.now(timezone.utc)
                user_data = self._temp_users.get(user_id)
            
            if not user_data:
                logger.warning(f"Utente non trovato per sessione: {session_token}")
                return None
                
            logger.info(f"Sessione valida per utente: {user_id}")
            return user_data
            
        except Exception as e:
            logger.error(f"Errore durante la validazione della sessione: {str(e)}")
            return None
    
    def invalidate_session(self, session_token):
        """
        Invalida una sessione (logout)
        
        Args:
            session_token: Token di sessione da invalidare
        
        Returns:
            bool: True se l'operazione è riuscita, False altrimenti
        """
        try:
            if self.db:
                # Imposta la sessione come non attiva
                result = self.db.sessions.update_one(
                    {"token": session_token},
                    {"$set": {"is_active": False}}
                )
                
                success = result.modified_count > 0
            else:
                # Versione per test senza database
                if session_token in self._temp_sessions:
                    self._temp_sessions[session_token]["is_active"] = False
                    success = True
                else:
                    success = False
            
            if success:
                logger.info(f"Sessione invalidata: {session_token}")
            else:
                logger.warning(f"Sessione non trovata per invalidazione: {session_token}")
                
            return success
            
        except Exception as e:
            logger.error(f"Errore durante l'invalidazione della sessione: {str(e)}")
            return False
    
    def register_user(self, email, password, name=""):
        """
        Registra un nuovo utente
        
        Args:
            email: Email dell'utente
            password: Password dell'utente
            name: Nome dell'utente (opzionale)
        
        Returns:
            str: user_id se registrazione riuscita, None altrimenti
        """
        try:
            # Controlla se l'utente esiste già
            user_exists = False
            
            if self.db:
                user_exists = self.db.users.find_one({"email": email}) is not None
            else:
                user_exists = email in self._temp_users
            
            if user_exists:
                logger.warning(f"Utente già esistente con email: {email}")
                return None
            
            # Genera un nuovo user_id unico
            user_id = f"user_{uuid.uuid4().hex[:8]}"
            
            # Hash della password
            password_hash = self._hash_password(password)
            
            # Dati utente
            user_data = {
                "user_id": user_id,
                "email": email,
                "name": name,
                "password_hash": password_hash,
                "exchange_credentials": {},
                "risk_settings": {
                    "max_daily_loss": 1000,
                    "max_position_size": 5000,
                    "stop_loss_percentage": 5.0
                },
                "created_at": datetime.now(timezone.utc),
                "is_active": True,
                "is_admin": False
            }
            
            if self.db:
                # Salva utente nel database
                self.db.users.insert_one(user_data)
            else:
                # Versione per test senza database
                self._temp_users[email] = user_data
            
            logger.info(f"Nuovo utente registrato: {email} ({user_id})")
            return user_id
            
        except Exception as e:
            logger.error(f"Errore durante la registrazione utente: {str(e)}")
            return None
    
    def is_admin(self, user_id):
        """
        Verifica se un utente è un amministratore
        
        Args:
            user_id: ID dell'utente
        
        Returns:
            bool: True se l'utente è admin, False altrimenti
        """
        try:
            user_data = None
            
            if self.db:
                user_data = self.db.users.find_one({"user_id": user_id})
            else:
                # Cerca per user_id tra i temp_users
                for email, data in self._temp_users.items():
                    if data.get("user_id") == user_id:
                        user_data = data
                        break
            
            if not user_data:
                logger.warning(f"Utente non trovato: {user_id}")
                return False
                
            is_admin = user_data.get("is_admin", False)
            return is_admin
            
        except Exception as e:
            logger.error(f"Errore durante la verifica admin: {str(e)}")
            return False
    
    def _hash_password(self, password):
        """
        Crea un hash sicuro della password
        
        Args:
            password: Password in chiaro
        
        Returns:
            str: Hash della password
        """
        # In produzione, usare un algoritmo più robusto come bcrypt
        hash_obj = hashlib.sha256(password.encode())
        return hash_obj.hexdigest()
    
    def _generate_session_token(self):
        """
        Genera un token di sessione sicuro
        
        Returns:
            str: Token di sessione
        """
        # Genera 32 byte casuali
        token_bytes = secrets.token_bytes(32)
        # Converti in stringa base64
        token = base64.urlsafe_b64encode(token_bytes).decode('utf-8')
        return token 