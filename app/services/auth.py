"""
Service d'authentification pour Quantum Mastermind
Gestion complète de l'authentification, autorisation et sécurité
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.core.security import (
    password_manager, jwt_manager, input_validator, security_auditor
)
from app.core.config import settings
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import (
    LoginRequest, LoginResponse, RegisterRequest, RegisterResponse,
    PasswordResetRequest, PasswordResetConfirm, PasswordChangeRequest,
    TokenData, RefreshToken
)
from app.schemas.user import UserProfile
from app.utils.exceptions import (
    AuthenticationError, AuthorizationError, ValidationError,
    AccountLockedError, EmailNotVerifiedError, EntityAlreadyExistsError
)


class AuthService:
    """Service d'authentification avec sécurité renforcée"""

    def __init__(self):
        self.user_repo = UserRepository()

    # === MÉTHODES D'AUTHENTIFICATION ===

    async def authenticate_user(
            self,
            db: AsyncSession,
            login_data: LoginRequest,
            client_info: Dict[str, Any]
    ) -> LoginResponse:
        """
        Authentifie un utilisateur et retourne les tokens

        Args:
            db: Session de base de données
            login_data: Données de connexion
            client_info: Informations client (IP, User-Agent, etc.)

        Returns:
            Réponse de connexion avec tokens

        Raises:
            AuthenticationError: Si l'authentification échoue
            AccountLockedError: Si le compte est verrouillé
        """
        # Validation des entrées
        username_or_email = input_validator.sanitize_string(
            login_data.username_or_email, 254
        )

        if not username_or_email or not login_data.password:
            raise AuthenticationError("Nom d'utilisateur/email et mot de passe requis")

        # Recherche de l'utilisateur
        user = await self._get_user_by_username_or_email(db, username_or_email)

        if not user:
            # Log de tentative sur utilisateur inexistant
            security_auditor.log_security_event(
                "login_attempt_invalid_user",
                ip_address=client_info.get('ip_address'),
                details={"attempted_username": username_or_email}
            )
            raise AuthenticationError("Identifiants incorrects")

        # Vérification du verrouillage du compte
        if user.is_locked:
            security_auditor.log_security_event(
                "login_attempt_locked_account",
                user_id=user.id,
                ip_address=client_info.get('ip_address')
            )
            raise AccountLockedError(
                "Compte temporairement verrouillé",
                unlock_time=user.locked_until.isoformat() if user.locked_until else None
            )

        # Vérification du mot de passe
        if not password_manager.verify_password(login_data.password, user.hashed_password):
            # Incrémenter les tentatives de connexion
            user.increment_login_attempts()
            await db.commit()

            security_auditor.log_security_event(
                "login_attempt_invalid_password",
                user_id=user.id,
                ip_address=client_info.get('ip_address'),
                details={"attempts": user.login_attempts}
            )

            if user.is_locked:
                raise AccountLockedError("Trop de tentatives incorrectes. Compte verrouillé.")

            raise AuthenticationError("Identifiants incorrects")

        # Vérification que le compte est actif
        if not user.is_active:
            security_auditor.log_security_event(
                "login_attempt_inactive_user",
                user_id=user.id,
                ip_address=client_info.get('ip_address')
            )
            raise AuthenticationError("Compte désactivé")

        # Vérification de l'email si nécessaire
        if settings.ENABLE_EMAIL_VERIFICATION and not user.is_verified:
            raise EmailNotVerifiedError(
                "Email non vérifié. Vérifiez votre boîte de réception.",
                email=user.email
            )

        # Mise à jour des informations de connexion
        user.update_last_login(client_info.get('ip_address'))
        await db.commit()

        # Génération des tokens
        token_data = {"sub": str(user.id), "username": user.username}

        access_token = jwt_manager.create_access_token(token_data)
        refresh_token = jwt_manager.create_refresh_token(token_data)

        # Log de connexion réussie
        security_auditor.log_security_event(
            "login_success",
            user_id=user.id,
            ip_address=client_info.get('ip_address'),
            details={
                "user_agent": client_info.get('user_agent'),
                "remember_me": login_data.remember_me
            }
        )

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.JWT_EXPIRE_MINUTES * 60,
            user=UserProfile.model_validate(user)
        )

    async def register_user(
            self,
            db: AsyncSession,
            register_data: RegisterRequest,
            client_info: Dict[str, Any]
    ) -> RegisterResponse:
        """
        Enregistre un nouvel utilisateur

        Args:
            db: Session de base de données
            register_data: Données d'enregistrement
            client_info: Informations client

        Returns:
            Réponse d'enregistrement

        Raises:
            ValidationError: Si les données sont invalides
            EntityAlreadyExistsError: Si l'utilisateur existe déjà
        """
        # Vérification que l'enregistrement est activé
        if not settings.ENABLE_REGISTRATION:
            raise ValidationError("Enregistrement désactivé")

        # Validation des données
        await self._validate_registration_data(db, register_data)

        # Hachage du mot de passe
        hashed_password = password_manager.get_password_hash(register_data.password)

        # Création de l'utilisateur
        user = User(
            username=register_data.username.lower().strip(),
            email=register_data.email,
            hashed_password=hashed_password,
            full_name=register_data.full_name,
            is_verified=not settings.ENABLE_EMAIL_VERIFICATION,
            is_active=True,
            is_superuser=False
        )

        # Ajout à la session et commit
        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Log de création de compte
        security_auditor.log_security_event(
            "user_registration",
            user_id=user.id,
            ip_address=client_info.get('ip_address'),
            details={
                "username": user.username,
                "email": user.email,
                "user_agent": client_info.get('user_agent')
            }
        )

        # Génération des tokens si l'email n'a pas besoin d'être vérifié
        access_token = None
        refresh_token = None

        if user.is_verified:
            token_data = {"sub": str(user.id), "username": user.username}
            access_token = jwt_manager.create_access_token(token_data)
            refresh_token = jwt_manager.create_refresh_token(token_data)

        return RegisterResponse(
            message="Compte créé avec succès",
            user=UserProfile.model_validate(user),
            access_token=access_token,
            refresh_token=refresh_token,
            requires_email_verification=not user.is_verified
        )

    async def refresh_access_token(
            self,
            db: AsyncSession,
            refresh_token: str,
            client_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Rafraîchit un token d'accès

        Args:
            db: Session de base de données
            refresh_token: Token de rafraîchissement
            client_info: Informations client

        Returns:
            Nouveaux tokens

        Raises:
            AuthenticationError: Si le token est invalide
        """
        try:
            payload = jwt_manager.verify_token(refresh_token)

            # Vérifier que c'est bien un refresh token
            if payload.get("type") != "refresh":
                raise AuthenticationError("Type de token invalide")

            user_id = UUID(payload.get("sub"))

        except Exception as e:
            raise AuthenticationError(f"Token de rafraîchissement invalide: {str(e)}")

        # Récupérer l'utilisateur
        user = await self.user_repo.get_by_id(db, user_id)
        if not user or not user.is_active:
            raise AuthenticationError("Utilisateur introuvable ou inactif")

        # Générer de nouveaux tokens
        token_data = {"sub": str(user.id), "username": user.username}
        new_access_token = jwt_manager.create_access_token(token_data)
        new_refresh_token = jwt_manager.create_refresh_token(token_data)

        # Log de rafraîchissement
        security_auditor.log_security_event(
            "token_refresh",
            user_id=user.id,
            ip_address=client_info.get('ip_address')
        )

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": settings.JWT_EXPIRE_MINUTES * 60
        }

    async def logout_user(
            self,
            db: AsyncSession,
            user_id: UUID,
            token: str,
            client_info: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Déconnecte un utilisateur

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur
            token: Token d'accès
            client_info: Informations client

        Returns:
            Message de confirmation
        """
        # TODO: Ajouter le token à une blacklist Redis

        # Log de déconnexion
        security_auditor.log_security_event(
            "user_logout",
            user_id=user_id,
            ip_address=client_info.get('ip_address')
        )

        return {"message": "Déconnexion réussie"}

    # === GESTION DES MOTS DE PASSE ===

    async def change_password(
            self,
            db: AsyncSession,
            user_id: UUID,
            password_data: PasswordChangeRequest
    ) -> Dict[str, str]:
        """
        Change le mot de passe d'un utilisateur

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur
            password_data: Données de changement de mot de passe

        Returns:
            Message de confirmation

        Raises:
            AuthenticationError: Si l'ancien mot de passe est incorrect
            ValidationError: Si le nouveau mot de passe est invalide
        """
        user = await self.user_repo.get_by_id(db, user_id)
        if not user:
            raise AuthenticationError("Utilisateur introuvable")

        # Vérification de l'ancien mot de passe
        if not password_manager.verify_password(
            password_data.current_password,
            user.hashed_password
        ):
            security_auditor.log_security_event(
                "password_change_invalid_current",
                user_id=user_id
            )
            raise AuthenticationError("Mot de passe actuel incorrect")

        # Validation du nouveau mot de passe
        validation_result = password_manager.validate_password_strength(
            password_data.new_password
        )
        if not validation_result["is_valid"]:
            raise ValidationError(
                "Mot de passe trop faible",
                field="new_password",
                validation_errors=validation_result["errors"]
            )

        # Mise à jour du mot de passe
        user.hashed_password = password_manager.get_password_hash(
            password_data.new_password
        )
        user.updated_at = datetime.now(timezone.utc)

        await db.commit()

        # Log de changement de mot de passe
        security_auditor.log_security_event(
            "password_changed",
            user_id=user_id
        )

        return {"message": "Mot de passe modifié avec succès"}

    async def reset_password_request(
            self,
            db: AsyncSession,
            reset_data: PasswordResetRequest,
            client_info: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Initie une demande de réinitialisation de mot de passe

        Args:
            db: Session de base de données
            reset_data: Données de demande de réinitialisation
            client_info: Informations client

        Returns:
            Message de confirmation
        """
        user = await self._get_user_by_username_or_email(db, reset_data.email)

        if user and user.is_active:
            # TODO: Générer un token de réinitialisation et envoyer un email
            # Pour l'instant, juste log
            security_auditor.log_security_event(
                "password_reset_requested",
                user_id=user.id,
                ip_address=client_info.get('ip_address'),
                details={"email": reset_data.email}
            )

        # Toujours retourner le même message pour éviter l'énumération
        return {"message": "Si l'adresse email existe, un lien de réinitialisation a été envoyé"}

    # === MÉTHODES UTILITAIRES ===

    async def get_current_user(self, db: AsyncSession, token: str) -> User:
        """
        Récupère l'utilisateur actuel à partir d'un token

        Args:
            db: Session de base de données
            token: Token JWT

        Returns:
            Utilisateur actuel

        Raises:
            AuthenticationError: Si le token est invalide
        """
        try:
            payload = jwt_manager.verify_token(token)
            user_id = UUID(payload.get("sub"))

        except Exception as e:
            raise AuthenticationError(f"Token invalide: {str(e)}")

        user = await self.user_repo.get_by_id(db, user_id)
        if not user:
            raise AuthenticationError("Utilisateur introuvable")

        if not user.is_active:
            raise AuthenticationError("Compte désactivé")

        return user

    async def verify_email(
            self,
            db: AsyncSession,
            verification_token: str
    ) -> Dict[str, str]:
        """
        Vérifie un email avec un token de vérification

        Args:
            db: Session de base de données
            verification_token: Token de vérification

        Returns:
            Message de confirmation
        """
        # TODO: Implémenter la vérification d'email avec token
        # Pour l'instant, placeholder
        return {"message": "Email vérifié avec succès"}

    async def _get_user_by_username_or_email(
            self,
            db: AsyncSession,
            identifier: str
    ) -> Optional[User]:
        """
        Récupère un utilisateur par nom d'utilisateur ou email

        Args:
            db: Session de base de données
            identifier: Nom d'utilisateur ou email

        Returns:
            Utilisateur trouvé ou None
        """
        # Déterminer si c'est un email ou un nom d'utilisateur
        if "@" in identifier:
            return await self.user_repo.get_by_email(db, identifier)
        else:
            return await self.user_repo.get_by_username(db, identifier)

    async def _validate_registration_data(
            self,
            db: AsyncSession,
            register_data: RegisterRequest
    ) -> None:
        """
        Valide les données d'enregistrement

        Args:
            db: Session de base de données
            register_data: Données à valider

        Raises:
            ValidationError: Si les données sont invalides
            EntityAlreadyExistsError: Si l'utilisateur existe déjà
        """
        # Validation du nom d'utilisateur
        username_validation = input_validator.validate_username(register_data.username)
        if not username_validation["is_valid"]:
            raise ValidationError(
                "Nom d'utilisateur invalide",
                field="username",
                validation_errors=username_validation["errors"]
            )

        # Validation de l'email
        if not input_validator.validate_email(register_data.email):
            raise ValidationError(
                "Format d'email invalide",
                field="email"
            )

        # Validation du mot de passe
        password_validation = password_manager.validate_password_strength(
            register_data.password
        )
        if not password_validation["is_valid"]:
            raise ValidationError(
                "Mot de passe trop faible",
                field="password",
                validation_errors=password_validation["errors"]
            )

        # Confirmation du mot de passe
        if register_data.password != register_data.password_confirm:
            raise ValidationError(
                "Les mots de passe ne correspondent pas",
                field="password_confirm"
            )

        # Vérification des conditions d'utilisation
        if not register_data.accept_terms:
            raise ValidationError(
                "Vous devez accepter les conditions d'utilisation",
                field="accept_terms"
            )

        # Vérification de l'unicité
        existing_user = await self.user_repo.get_by_username(db, register_data.username)
        if existing_user:
            raise EntityAlreadyExistsError(
                "Ce nom d'utilisateur existe déjà",
                entity_type="User",
                conflicting_field="username",
                conflicting_value=register_data.username
            )

        existing_email = await self.user_repo.get_by_email(db, register_data.email)
        if existing_email:
            raise EntityAlreadyExistsError(
                "Cette adresse email est déjà utilisée",
                entity_type="User",
                conflicting_field="email",
                conflicting_value=register_data.email
            )


# Instance globale du service d'authentification
auth_service = AuthService()