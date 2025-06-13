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

        # Mots de passe courants (basic check)
        common_passwords = [
            "password", "123456", "password123", "admin", "qwerty",
            "letmein", "welcome", "monkey", "dragon"
        ]
        if password.lower() in common_passwords:
            errors.append("Mot de passe trop commun")

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "strength_score": max(0, 100 - len(errors) * 20)
        }


# === GESTION JWT ===
class JWTManager:
    """Gestionnaire des tokens JWT"""

    @staticmethod
    def create_access_token(
            subject: Union[str, UUID],
            expires_delta: Optional[timedelta] = None,
            additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """Crée un token d'accès JWT"""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)

        to_encode = {
            "exp": expire,
            "iat": datetime.utcnow(),
            "sub": str(subject),
            "type": "access",
            "jti": secrets.token_urlsafe(16)  # JWT ID unique
        }

        if additional_claims:
            to_encode.update(additional_claims)

        encoded_jwt = jwt.encode(
            to_encode,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt

    @staticmethod
    def create_refresh_token(subject: Union[str, UUID]) -> str:
        """Crée un token de refresh"""
        expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)

        to_encode = {
            "exp": expire,
            "iat": datetime.utcnow(),
            "sub": str(subject),
            "type": "refresh",
            "jti": secrets.token_urlsafe(16)
        }

        encoded_jwt = jwt.encode(
            to_encode,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt

    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """Vérifie et décode un token JWT"""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )

            # Vérification du type de token
            if payload.get("type") != token_type:
                return None

            # Vérification de l'expiration
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp) < datetime.utcnow():
                return None

            return payload

        except JWTError:
            return None

    @staticmethod
    def get_subject_from_token(token: str) -> Optional[str]:
        """Extrait le subject d'un token"""
        payload = JWTManager.verify_token(token)
        if payload:
            return payload.get("sub")
        return None


# === GÉNÉRATEUR DE TOKENS ===
class TokenGenerator:
    """Générateur de tokens sécurisés pour diverses utilisations"""

    @staticmethod
    def generate_api_key(length: int = 32) -> str:
        """Génère une clé API sécurisée"""
        return secrets.token_urlsafe(length)

    @staticmethod
    def generate_room_code(length: int = 8) -> str:
        """Génère un code de room pour les parties"""
        # Utilise uniquement des caractères alphanumériques en majuscules
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def generate_game_seed() -> str:
        """Génère une seed pour la génération de solutions quantiques"""
        return secrets.token_hex(16)

    @staticmethod
    def generate_session_id() -> str:
        """Génère un ID de session WebSocket"""
        return secrets.token_urlsafe(24)


# === VALIDATION D'ENTRÉES ===
class InputValidator:
    """Validateur d'entrées pour la sécurité"""

    @staticmethod
    def validate_username(username: str) -> Dict[str, Any]:
        """Valide un nom d'utilisateur"""
        errors = []

        # Longueur
        if len(username) < 3:
            errors.append("Minimum 3 caractères")
        if len(username) > 50:
            errors.append("Maximum 50 caractères")

        # Caractères autorisés
        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            errors.append("Seuls lettres, chiffres, _ et - autorisés")

        # Mots réservés
        reserved = ["admin", "root", "system", "quantum", "mastermind", "api"]
        if username.lower() in reserved:
            errors.append("Nom d'utilisateur réservé")

        return {
            "is_valid": len(errors) == 0,
            "errors": errors
        }

    @staticmethod
    def validate_email(email: str) -> Dict[str, Any]:
        """Valide une adresse email"""
        errors = []

        # Format email
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            errors.append("Format email invalide")

        # Longueur
        if len(email) > 254:
            errors.append("Email trop long")

        return {
            "is_valid": len(errors) == 0,
            "errors": errors
        }

    @staticmethod
    def sanitize_string(input_str: str, max_length: int = 1000) -> str:
        """Nettoie une chaîne d'entrée"""
        if not input_str:
            return ""

        # Supprime les caractères de contrôle
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', input_str)

        # Limite la longueur
        return sanitized[:max_length].strip()


# === AUDIT ET LOGS SÉCURITÉ ===
class SecurityAuditor:
    """Auditeur pour les événements de sécurité"""

    @staticmethod
    def log_authentication_attempt(
            username: str,
            ip_address: str,
            user_agent: str,
            success: bool,
            failure_reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Enregistre une tentative d'authentification"""
        return {
            "event_type": "authentication_attempt",
            "username": username,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "success": success,
            "failure_reason": failure_reason,
            "timestamp": datetime.utcnow().isoformat(),
            "severity": "INFO" if success else "WARNING"
        }

    @staticmethod
    def log_suspicious_activity(
            user_id: Optional[str],
            activity_type: str,
            details: Dict[str, Any],
            ip_address: str
    ) -> Dict[str, Any]:
        """Enregistre une activité suspecte"""
        return {
            "event_type": "suspicious_activity",
            "user_id": user_id,
            "activity_type": activity_type,
            "details": details,
            "ip_address": ip_address,
            "timestamp": datetime.utcnow().isoformat(),
            "severity": "WARNING"
        }


# === INSTANCES GLOBALES ===
password_manager = PasswordManager()
jwt_manager = JWTManager()
token_generator = TokenGenerator()
input_validator = InputValidator()
security_auditor = SecurityAuditor()