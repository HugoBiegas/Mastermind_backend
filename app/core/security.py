"""
Module de sécurité pour Quantum Mastermind
Gestion JWT, hachage des mots de passe, validation sécurisée
"""
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.hash import bcrypt
import secrets
import re
from uuid import UUID

from .config import settings, security_config

# === CONTEXT DE HACHAGE ===
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # Plus sécurisé que le défaut
)


# === GESTION DES MOTS DE PASSE ===
class PasswordManager:
    """Gestionnaire sécurisé des mots de passe"""

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Vérifie un mot de passe contre son hash"""
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            return False

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash un mot de passe de manière sécurisée"""
        return pwd_context.hash(password)

    @staticmethod
    def validate_password_strength(password: str) -> Dict[str, Any]:
        """Valide la complexité d'un mot de passe"""
        errors = []

        # Longueur minimum
        if len(password) < security_config.PASSWORD_MIN_LENGTH:
            errors.append(f"Minimum {security_config.PASSWORD_MIN_LENGTH} caractères requis")

        # Majuscules
        if security_config.PASSWORD_REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
            errors.append("Au moins une majuscule requise")

        # Minuscules
        if security_config.PASSWORD_REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
            errors.append("Au moins une minuscule requise")

        # Chiffres
        if security_config.PASSWORD_REQUIRE_DIGITS and not re.search(r'\d', password):
            errors.append("Au moins un chiffre requis")

        # Caractères spéciaux
        if security_config.PASSWORD_REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Au moins un caractère spécial requis")

        # Mots de passe communs (blacklist basique)
        common_passwords = [
            "password", "123456", "password123", "admin", "qwerty",
            "letmein", "welcome", "monkey", "dragon", "master"
        ]
        if password.lower() in common_passwords:
            errors.append("Mot de passe trop commun")

        # Calcul du score de force
        score = 0
        if len(password) >= 8:
            score += 1
        if len(password) >= 12:
            score += 1
        if re.search(r'[A-Z]', password):
            score += 1
        if re.search(r'[a-z]', password):
            score += 1
        if re.search(r'\d', password):
            score += 1
        if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            score += 1
        if len(password) >= 16:
            score += 1

        # Évaluation de la force
        if score <= 2:
            strength = "très faible"
        elif score <= 3:
            strength = "faible"
        elif score <= 4:
            strength = "moyen"
        elif score <= 5:
            strength = "fort"
        else:
            strength = "très fort"

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "strength": strength,
            "score": score,
            "max_score": 7
        }

    @staticmethod
    def generate_secure_password(length: int = 16) -> str:
        """Génère un mot de passe sécurisé aléatoire"""
        import string

        # Assurer au moins un caractère de chaque type
        chars = []
        chars.append(secrets.choice(string.ascii_uppercase))
        chars.append(secrets.choice(string.ascii_lowercase))
        chars.append(secrets.choice(string.digits))
        chars.append(secrets.choice("!@#$%^&*()"))

        # Remplir le reste
        all_chars = string.ascii_letters + string.digits + "!@#$%^&*()"
        for _ in range(length - 4):
            chars.append(secrets.choice(all_chars))

        # Mélanger
        secrets.SystemRandom().shuffle(chars)
        return ''.join(chars)


# === GESTION JWT ===
class JWTManager:
    """Gestionnaire des tokens JWT"""

    @staticmethod
    def create_access_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Crée un token d'accès JWT

        Args:
            data: Données à encoder dans le token
            expires_delta: Durée d'expiration personnalisée

        Returns:
            Token JWT signé
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })

        encoded_jwt = jwt.encode(
            to_encode,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt

    @staticmethod
    def create_refresh_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Crée un token de rafraîchissement JWT

        Args:
            data: Données à encoder dans le token
            expires_delta: Durée d'expiration personnalisée

        Returns:
            Token de rafraîchissement JWT signé
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })

        encoded_jwt = jwt.encode(
            to_encode,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt

    @staticmethod
    def verify_token(token: str) -> Dict[str, Any]:
        """
        Vérifie et décode un token JWT

        Args:
            token: Token JWT à vérifier

        Returns:
            Payload décodé du token

        Raises:
            JWTError: Si le token est invalide
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            return payload
        except JWTError as e:
            raise JWTError(f"Token invalide: {str(e)}")

    @staticmethod
    def get_token_payload(token: str) -> Optional[Dict[str, Any]]:
        """
        Récupère le payload d'un token sans vérification complète

        Args:
            token: Token JWT

        Returns:
            Payload ou None si invalide
        """
        try:
            return JWTManager.verify_token(token)
        except:
            return None

    @staticmethod
    def is_token_expired(token: str) -> bool:
        """
        Vérifie si un token est expiré

        Args:
            token: Token JWT

        Returns:
            True si expiré
        """
        try:
            payload = JWTManager.get_token_payload(token)
            if not payload:
                return True

            exp = payload.get("exp")
            if not exp:
                return True

            return datetime.utcnow().timestamp() > exp
        except:
            return True

    @staticmethod
    def extract_user_id(token: str) -> Optional[UUID]:
        """
        Extrait l'ID utilisateur d'un token

        Args:
            token: Token JWT

        Returns:
            UUID de l'utilisateur ou None
        """
        try:
            payload = JWTManager.verify_token(token)
            user_id_str = payload.get("sub")
            if user_id_str:
                return UUID(user_id_str)
            return None
        except:
            return None


# === VALIDATION DES ENTRÉES ===
class InputValidator:
    """Validateur sécurisé des entrées utilisateur"""

    @staticmethod
    def sanitize_string(value: str, max_length: int = 255) -> str:
        """Nettoie et limite une chaîne de caractères"""
        if not isinstance(value, str):
            return ""

        # Supprimer les caractères de contrôle
        cleaned = ''.join(char for char in value if ord(char) >= 32)

        # Limiter la longueur
        return cleaned[:max_length].strip()

    @staticmethod
    def validate_email(email: str) -> bool:
        """Valide un format d'email"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_pattern, email)) and len(email) <= 254

    @staticmethod
    def validate_username(username: str) -> Dict[str, Any]:
        """Valide un nom d'utilisateur"""
        errors = []

        if not username:
            errors.append("Nom d'utilisateur requis")
            return {"is_valid": False, "errors": errors}

        if len(username) < 3:
            errors.append("Minimum 3 caractères")

        if len(username) > 50:
            errors.append("Maximum 50 caractères")

        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            errors.append("Seuls les lettres, chiffres, _ et - sont autorisés")

        if username.lower() in ["admin", "root", "user", "test", "quantum", "mastermind"]:
            errors.append("Nom d'utilisateur réservé")

        return {
            "is_valid": len(errors) == 0,
            "errors": errors
        }

    @staticmethod
    def validate_uuid(uuid_str: str) -> bool:
        """Valide un format UUID"""
        try:
            UUID(uuid_str)
            return True
        except ValueError:
            return False

    @staticmethod
    def sanitize_json_input(data: Dict[str, Any]) -> Dict[str, Any]:
        """Nettoie les entrées JSON récursivements"""
        if isinstance(data, dict):
            return {
                key: InputValidator.sanitize_json_input(value)
                for key, value in data.items()
                if key not in ["__class__", "__module__"]  # Sécurité
            }
        elif isinstance(data, list):
            return [
                InputValidator.sanitize_json_input(item)
                for item in data
            ]
        elif isinstance(data, str):
            return InputValidator.sanitize_string(data)
        else:
            return data


# === AUDIT DE SÉCURITÉ ===
class SecurityAuditor:
    """Auditeur de sécurité pour les actions sensibles"""

    @staticmethod
    def log_security_event(
        event_type: str,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log un événement de sécurité

        Args:
            event_type: Type d'événement
            user_id: ID de l'utilisateur concerné
            ip_address: Adresse IP
            details: Détails supplémentaires
        """
        # TODO: Implémenter le logging sécurisé
        # Pour l'instant, print simple
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": str(user_id) if user_id else None,
            "ip_address": ip_address,
            "details": details or {}
        }
        print(f"🔒 Security Event: {log_entry}")

    @staticmethod
    def check_suspicious_activity(
        user_id: UUID,
        action: str,
        ip_address: str
    ) -> bool:
        """
        Vérifie une activité suspecte

        Args:
            user_id: ID de l'utilisateur
            action: Action effectuée
            ip_address: Adresse IP

        Returns:
            True si activité suspecte détectée
        """
        # TODO: Implémenter la détection d'activité suspecte
        # - Nombreuses tentatives de connexion
        # - Changements d'IP fréquents
        # - Actions automatisées détectées
        return False

    @staticmethod
    def rate_limit_check(
        identifier: str,
        action: str,
        limit: int = 10,
        window: int = 60
    ) -> bool:
        """
        Vérifie le rate limiting

        Args:
            identifier: Identifiant (IP, user_id, etc.)
            action: Action limitée
            limit: Nombre maximum d'actions
            window: Fenêtre de temps en secondes

        Returns:
            True si limite atteinte
        """
        # TODO: Implémenter avec Redis
        return False


# === GÉNÉRATEURS SÉCURISÉS ===
class SecureGenerator:
    """Générateur de valeurs sécurisées"""

    @staticmethod
    def generate_api_key(length: int = 64) -> str:
        """Génère une clé API sécurisée"""
        return secrets.token_urlsafe(length)

    @staticmethod
    def generate_session_id() -> str:
        """Génère un ID de session sécurisé"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def generate_verification_code(digits: int = 6) -> str:
        """Génère un code de vérification numérique"""
        return ''.join([str(secrets.randbelow(10)) for _ in range(digits)])

    @staticmethod
    def generate_reset_token() -> str:
        """Génère un token de réinitialisation"""
        return secrets.token_urlsafe(48)

    @staticmethod
    def generate_room_code(length: int = 6) -> str:
        """Génère un code de room de jeu"""
        import string
        alphabet = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))


# === CHIFFREMENT AVANCÉ ===
class CryptoManager:
    """Gestionnaire de chiffrement avancé"""

    @staticmethod
    def encrypt_sensitive_data(data: str, key: Optional[str] = None) -> str:
        """
        Chiffre des données sensibles

        Args:
            data: Données à chiffrer
            key: Clé de chiffrement (optionnelle)

        Returns:
            Données chiffrées en base64
        """
        from cryptography.fernet import Fernet
        import base64

        if not key:
            key = settings.SECRET_KEY

        # Créer une clé Fernet depuis la clé fournie
        key_bytes = base64.urlsafe_b64encode(key.encode()[:32].ljust(32, b'\0'))
        fernet = Fernet(key_bytes)

        encrypted = fernet.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    @staticmethod
    def decrypt_sensitive_data(encrypted_data: str, key: Optional[str] = None) -> str:
        """
        Déchiffre des données sensibles

        Args:
            encrypted_data: Données chiffrées
            key: Clé de déchiffrement (optionnelle)

        Returns:
            Données déchiffrées
        """
        from cryptography.fernet import Fernet
        import base64

        if not key:
            key = settings.SECRET_KEY

        try:
            # Créer une clé Fernet depuis la clé fournie
            key_bytes = base64.urlsafe_b64encode(key.encode()[:32].ljust(32, b'\0'))
            fernet = Fernet(key_bytes)

            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = fernet.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception:
            raise ValueError("Impossible de déchiffrer les données")


# === INSTANCES GLOBALES ===
password_manager = PasswordManager()
jwt_manager = JWTManager()
input_validator = InputValidator()
security_auditor = SecurityAuditor()
secure_generator = SecureGenerator()
crypto_manager = CryptoManager()


# === DÉCORATEURS DE SÉCURITÉ ===
def require_permissions(*permissions):
    """Décorateur pour vérifier les permissions"""
    def decorator(func):
        from functools import wraps

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # TODO: Implémenter la vérification des permissions
            return await func(*args, **kwargs)

        return wrapper
    return decorator


def audit_action(action_type: str):
    """Décorateur pour auditer les actions"""
    def decorator(func):
        from functools import wraps

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # TODO: Implémenter l'audit des actions
            result = await func(*args, **kwargs)
            security_auditor.log_security_event(action_type)
            return result

        return wrapper
    return decorator


def rate_limit(limit: int = 10, window: int = 60):
    """Décorateur pour le rate limiting"""
    def decorator(func):
        from functools import wraps

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # TODO: Implémenter le rate limiting
            return await func(*args, **kwargs)

        return wrapper
    return decorator


# === HELPERS DE SÉCURITÉ ===
def verify_csrf_token(token: str, session_token: str) -> bool:
    """Vérifie un token CSRF"""
    # TODO: Implémenter la vérification CSRF
    return True


def generate_csrf_token() -> str:
    """Génère un token CSRF"""
    return secure_generator.generate_session_id()


def hash_file_content(content: bytes) -> str:
    """Hash le contenu d'un fichier"""
    import hashlib
    return hashlib.sha256(content).hexdigest()


def is_safe_redirect_url(url: str, allowed_hosts: List[str]) -> bool:
    """Vérifie si une URL de redirection est sûre"""
    from urllib.parse import urlparse

    parsed = urlparse(url)

    # URL relative acceptable
    if not parsed.netloc:
        return True

    # Vérifier les hosts autorisés
    return parsed.netloc in allowed_hosts


# === EXPORT ===
__all__ = [
    "password_manager",
    "jwt_manager",
    "input_validator",
    "security_auditor",
    "secure_generator",
    "crypto_manager",
    "require_permissions",
    "audit_action",
    "rate_limit",
    "verify_csrf_token",
    "generate_csrf_token",
    "hash_file_content",
    "is_safe_redirect_url"
]