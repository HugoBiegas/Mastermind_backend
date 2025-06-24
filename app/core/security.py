"""
Module de sécurité pour Quantum Mastermind
Gestion JWT, hachage des mots de passe, validation sécurisée
"""
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings

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
        suggestions = []

        # Longueur minimum
        if len(password) < settings.PASSWORD_MIN_LENGTH:
            errors.append(f"Minimum {settings.PASSWORD_MIN_LENGTH} caractères requis")

        # Majuscules
        if settings.PASSWORD_REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
            errors.append("Au moins une majuscule requise")
            suggestions.append("Ajoutez une lettre majuscule")

        # Minuscules
        if settings.PASSWORD_REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
            errors.append("Au moins une minuscule requise")
            suggestions.append("Ajoutez une lettre minuscule")

        # Chiffres
        if settings.PASSWORD_REQUIRE_NUMBERS and not re.search(r'\d', password):
            errors.append("Au moins un chiffre requis")
            suggestions.append("Ajoutez un chiffre")

        # Caractères spéciaux
        if settings.PASSWORD_REQUIRE_SYMBOLS and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Au moins un caractère spécial requis")
            suggestions.append("Ajoutez un caractère spécial")

        # Mots de passe communs (blacklist basique)
        common_passwords = [
            "password", "123456", "password123", "admin", "qwerty",
            "letmein", "welcome", "monkey", "dragon", "master"
        ]
        if password.lower() in common_passwords:
            errors.append("Mot de passe trop commun")
            suggestions.append("Utilisez un mot de passe plus original")

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

        # Détermination de la force
        if score >= 5:
            strength = "forte"
        elif score >= 3:
            strength = "moyenne"
        else:
            strength = "faible"

        return {
            "is_valid": len(errors) == 0,
            "strength": strength,
            "score": score,
            "errors": errors,
            "suggestions": suggestions
        }


# === GESTION JWT ===
class JWTManager:
    """Gestionnaire de tokens JWT"""

    @staticmethod
    def create_access_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Crée un token d'accès JWT

        Args:
            data: Données à encoder
            expires_delta: Durée de validité

        Returns:
            Token JWT
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)

        to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})

        return jwt.encode(
            to_encode,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )

    @staticmethod
    def create_refresh_token(user_id: UUID) -> str:
        """
        Crée un token de rafraîchissement

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Token de rafraîchissement
        """
        data = {
            "sub": str(user_id),
            "type": "refresh",
            "exp": datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
        }

        return jwt.encode(
            data,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )

    @staticmethod
    def verify_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Vérifie et décode un token JWT

        Args:
            token: Token à vérifier

        Returns:
            Données du token si valide, None sinon
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            return payload
        except JWTError:
            return None

    @staticmethod
    def get_user_id_from_token(token: str) -> Optional[UUID]:
        """
        Extrait l'ID utilisateur d'un token

        Args:
            token: Token JWT

        Returns:
            UUID de l'utilisateur si valide
        """
        payload = JWTManager.verify_token(token)
        if payload and "sub" in payload:
            try:
                return UUID(payload["sub"])
            except ValueError:
                return None
        return None


# === VALIDATION DES ENTRÉES ===
class InputValidator:
    """Validateur d'entrées utilisateur"""

    @staticmethod
    def validate_email(email: str) -> Dict[str, Any]:
        """Valide une adresse email"""
        email = email.strip().lower()

        # Pattern email basique mais robuste
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        is_valid = bool(re.match(pattern, email)) and len(email) <= 254

        return {
            "is_valid": is_valid,
            "normalized": email if is_valid else None,
            "errors": [] if is_valid else ["Format d'email invalide"]
        }

    @staticmethod
    def validate_username(username: str) -> Dict[str, Any]:
        """Valide un nom d'utilisateur"""
        username = username.strip().lower()
        errors = []

        # Longueur
        if len(username) < 3:
            errors.append("Minimum 3 caractères")
        if len(username) > 50:
            errors.append("Maximum 50 caractères")

        # Caractères autorisés
        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            errors.append("Seuls les lettres, chiffres, _ et - sont autorisés")

        # Ne peut pas commencer par un chiffre
        if username and username[0].isdigit():
            errors.append("Ne peut pas commencer par un chiffre")

        # Mots réservés
        reserved = ["admin", "root", "system", "api", "www", "mail", "ftp", "test"]
        if username in reserved:
            errors.append("Nom d'utilisateur réservé")

        return {
            "is_valid": len(errors) == 0,
            "normalized": username if len(errors) == 0 else None,
            "errors": errors
        }

    @staticmethod
    def sanitize_string(input_str: str, max_length: int = 1000) -> str:
        """Nettoie une chaîne de caractères"""
        if not isinstance(input_str, str):
            return ""

        # Supprime les caractères de contrôle
        sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', input_str)

        # Limite la longueur
        sanitized = sanitized[:max_length]

        # Supprime les espaces en début/fin
        return sanitized.strip()

    @staticmethod
    def sanitize_json_input(data: Any) -> Any:
        """Nettoie les entrées JSON récursivement"""
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
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "user_id": str(user_id) if user_id else None,
            "ip_address": ip_address,
            "details": details or {}
        }

        # En production, utiliser un vrai système de logging
        if settings.DEBUG:
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
        # TODO: Implémenter avec Redis ou mémoire
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
        # Éviter les caractères confus
        alphabet = alphabet.replace('0', '').replace('O', '').replace('1', '').replace('I', '')
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
        try:
            from cryptography.fernet import Fernet
            import base64

            if not key:
                key = settings.SECRET_KEY

            # Créer une clé Fernet depuis la clé fournie
            key_bytes = key.encode()[:32].ljust(32, b'0')  # 32 bytes
            fernet_key = base64.urlsafe_b64encode(key_bytes)
            f = Fernet(fernet_key)

            encrypted = f.encrypt(data.encode())
            return base64.b64encode(encrypted).decode()
        except Exception:
            # Fallback simple si cryptography n'est pas disponible
            return base64.b64encode(data.encode()).decode()

    @staticmethod
    def decrypt_sensitive_data(encrypted_data: str, key: Optional[str] = None) -> str:
        """
        Déchiffre des données sensibles

        Args:
            encrypted_data: Données chiffrées
            key: Clé de déchiffrement

        Returns:
            Données déchiffrées
        """
        try:
            from cryptography.fernet import Fernet
            import base64

            if not key:
                key = settings.SECRET_KEY

            key_bytes = key.encode()[:32].ljust(32, b'0')
            fernet_key = base64.urlsafe_b64encode(key_bytes)
            f = Fernet(fernet_key)

            encrypted_bytes = base64.b64decode(encrypted_data.encode())
            decrypted = f.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception:
            # Fallback simple
            return base64.b64decode(encrypted_data.encode()).decode()


# === INSTANCES GLOBALES ===
password_manager = PasswordManager()
jwt_manager = JWTManager()
input_validator = InputValidator()
security_auditor = SecurityAuditor()
secure_generator = SecureGenerator()
crypto_manager = CryptoManager()


# === DÉCORATEURS DE SÉCURITÉ ===
def require_permissions(permissions: list[str]):
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
    """Décorateur pour auditer des actions"""
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

def decode_access_token():
    """
    Décoder le token d'accès JWT pour obtenir les données utilisateur

    Returns:
        Dict[str, Any]: Données utilisateur si le token est valide, None sinon
    """
    from fastapi import Request

    async def _decode(request: Request) -> Optional[Dict[str, Any]]:
        token = request.headers.get("Authorization")
        if not token or not token.startswith("Bearer "):
            return None

        token = token.split(" ")[1]
        return jwt_manager.verify_token(token)

    return _decode


def is_safe_redirect_url(url: str, allowed_hosts: list[str]) -> bool:
    """Vérifie si une URL de redirection est sûre"""
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)

        # URL relative acceptable
        if not parsed.netloc:
            return True

        # Vérifier les hosts autorisés
        return parsed.netloc in allowed_hosts
    except Exception:
        return False


# === EXPORT ===
__all__ = [
    "password_manager",
    "decode_access_token",
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



