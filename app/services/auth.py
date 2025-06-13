"""
Service d'authentification pour Quantum Mastermind
Gestion complète de l'authentification, autorisation et sécurité
"""
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

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
    AccountLockedError, EmailNotVerifiedError
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
        ip_address = client_info.get('ip_address', 'unknown')
        user_agent = client_info.get('user_agent', 'unknown')

        try:
            # Récupération de l'utilisateur
            user = await self.user_repo.get_by_username_or_email(
                db, login_data.username_or_email
            )

            if not user:
                # Log de tentative d'authentification échouée
                self._log_failed_authentication(
                    login_data.username_or_email,
                    ip_address,
                    user_agent,
                    "Utilisateur non trouvé"
                )
                raise AuthenticationError("Identifiants invalides")

            # Vérification du compte verrouillé
            if user.is_locked:
                self._log_failed_authentication(
                    user.username,
                    ip_address,
                    user_agent,
                    "Compte verrouillé"
                )
                raise AccountLockedError(
                    f"Compte verrouillé jusqu'à {user.locked_until}"
                )

            # Vérification du compte actif
            if not user.is_active:
                self._log_failed_authentication(
                    user.username,
                    ip_address,
                    user_agent,
                    "Compte désactivé"
                )
                raise AuthenticationError("Compte désactivé")

            # Vérification du mot de passe
            if not password_manager.verify_password(
                    login_data.password, user.password_hash
            ):
                # Incrémentation des tentatives échouées
                user.increment_failed_login()
                await db.commit()

                self._log_failed_authentication(
                    user.username,
                    ip_address,
                    user_agent,
                    "Mot de passe incorrect"
                )
                raise AuthenticationError("Identifiants invalides")

            # Authentification réussie
            await self._handle_successful_login(db, user, ip_address, user_agent)

            # Génération des tokens
            access_token = jwt_manager.create_access_token(
                subject=user.id,
                additional_claims={
                    'username': user.username,
                    'email': user.email,
                    'is_verified': user.is_verified,
                    'is_superuser': user.is_superuser
                }
            )

            refresh_token = jwt_manager.create_refresh_token(user.id)

            # Log de succès
            self._log_successful_authentication(user.username, ip_address, user_agent)

            return LoginResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=settings.JWT_EXPIRE_MINUTES * 60,
                user=UserProfile.from_orm(user)
            )

        except (AuthenticationError, AccountLockedError):
            raise
        except Exception as e:
            self._log_failed_authentication(
                login_data.username_or_email,
                ip_address,
                user_agent,
                f"Erreur système: {str(e)}"
            )
            raise AuthenticationError("Erreur lors de l'authentification")

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
            register_data: Données d'inscription
            client_info: Informations client

        Returns:
            Réponse d'inscription

        Raises:
            ValidationError: Si les données sont invalides
        """
        try:
            # Validation des données
            await self._validate_registration_data(db, register_data)

            # Hachage du mot de passe
            password_hash = password_manager.get_password_hash(register_data.password)

            # Création de l'utilisateur
            user_data = {
                'username': register_data.username.strip(),
                'email': register_data.email.lower().strip(),
                'password_hash': password_hash,
                'is_active': True,
                'is_verified': False,  # Nécessite vérification email
                'last_ip_address': client_info.get('ip_address'),
                'preferences': {
                    'theme': 'dark',
                    'language': 'fr',
                    'notifications_enabled': True,
                    'sound_enabled': True
                }
            }

            user = await self.user_repo.create(db, obj_in=user_data)

            # TODO: Envoyer email de vérification
            # await self._send_verification_email(user)

            return RegisterResponse(
                message="Compte créé avec succès. Vérifiez votre email pour activer votre compte.",
                user_id=user.id,
                email_verification_required=True
            )

        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"Erreur lors de l'inscription: {str(e)}")

    async def refresh_access_token(
            self,
            db: AsyncSession,
            refresh_data: RefreshToken
    ) -> Dict[str, Any]:
        """
        Renouvelle un token d'accès à partir d'un refresh token

        Args:
            db: Session de base de données
            refresh_data: Token de refresh

        Returns:
            Nouveau token d'accès

        Raises:
            AuthenticationError: Si le refresh token est invalide
        """
        try:
            # Vérification du refresh token
            payload = jwt_manager.verify_token(
                refresh_data.refresh_token,
                token_type="refresh"
            )

            if not payload:
                raise AuthenticationError("Refresh token invalide")

            user_id = UUID(payload.get("sub"))
            user = await self.user_repo.get_by_id(db, user_id)

            if not user or not user.is_active:
                raise AuthenticationError("Utilisateur invalide")

            # Génération d'un nouveau token d'accès
            access_token = jwt_manager.create_access_token(
                subject=user.id,
                additional_claims={
                    'username': user.username,
                    'email': user.email,
                    'is_verified': user.is_verified,
                    'is_superuser': user.is_superuser
                }
            )

            return {
                'access_token': access_token,
                'token_type': 'bearer',
                'expires_in': settings.JWT_EXPIRE_MINUTES * 60
            }

        except Exception as e:
            raise AuthenticationError("Erreur lors du renouvellement du token")

    # === MÉTHODES DE GESTION DES MOTS DE PASSE ===

    async def change_password(
            self,
            db: AsyncSession,
            user_id: UUID,
            password_data: PasswordChangeRequest
    ) -> Dict[str, str]:
        """
        Change le mot de passe d'un utilisateur connecté

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur
            password_data: Données de changement de mot de passe

        Returns:
            Message de confirmation

        Raises:
            AuthenticationError: Si le mot de passe actuel est incorrect
            ValidationError: Si le nouveau mot de passe est invalide
        """
        user = await self.user_repo.get_by_id(db, user_id)
        if not user:
            raise AuthenticationError("Utilisateur non trouvé")

        # Vérification du mot de passe actuel
        if not password_manager.verify_password(
                password_data.current_password, user.password_hash
        ):
            raise AuthenticationError("Mot de passe actuel incorrect")

        # Validation du nouveau mot de passe
        validation = password_manager.validate_password_strength(
            password_data.new_password
        )
        if not validation['is_valid']:
            raise ValidationError(f"Mot de passe faible: {'; '.join(validation['errors'])}")

        # Mise à jour du mot de passe
        new_password_hash = password_manager.get_password_hash(
            password_data.new_password
        )

        await self.user_repo.update(
            db,
            db_obj=user,
            obj_in={
                'password_hash': new_password_hash,
                'password_changed_at': datetime.utcnow()
            }
        )

        return {'message': 'Mot de passe modifié avec succès'}

    async def request_password_reset(
            self,
            db: AsyncSession,
            reset_data: PasswordResetRequest
    ) -> Dict[str, str]:
        """
        Demande de réinitialisation de mot de passe

        Args:
            db: Session de base de données
            reset_data: Données de demande de reset

        Returns:
            Message de confirmation
        """
        user = await self.user_repo.get_by_email(db, reset_data.email)

        # Toujours retourner un message de succès pour éviter l'énumération
        if user and user.is_active:
            # Génération du token de reset
            reset_token = jwt_manager.create_access_token(
                subject=user.id,
                expires_delta=timedelta(hours=24),
                additional_claims={'type': 'password_reset'}
            )

            # Sauvegarde du token
            await self.user_repo.update(
                db,
                db_obj=user,
                obj_in={
                    'password_reset_token': reset_token,
                    'password_reset_expires': datetime.utcnow() + timedelta(hours=24)
                }
            )

            # TODO: Envoyer email de reset
            # await self._send_password_reset_email(user, reset_token)

        return {
            'message': 'Si cette adresse email existe, vous recevrez un email de réinitialisation'
        }

    async def confirm_password_reset(
            self,
            db: AsyncSession,
            reset_data: PasswordResetConfirm
    ) -> Dict[str, str]:
        """
        Confirme la réinitialisation de mot de passe

        Args:
            db: Session de base de données
            reset_data: Données de confirmation de reset

        Returns:
            Message de confirmation

        Raises:
            AuthenticationError: Si le token est invalide
            ValidationError: Si le nouveau mot de passe est invalide
        """
        # Vérification du token
        payload = jwt_manager.verify_token(reset_data.token)
        if not payload or payload.get('type') != 'password_reset':
            raise AuthenticationError("Token de réinitialisation invalide ou expiré")

        user_id = UUID(payload.get('sub'))
        user = await self.user_repo.get_by_id(db, user_id)

        if not user or user.password_reset_token != reset_data.token:
            raise AuthenticationError("Token de réinitialisation invalide")

        # Vérification de l'expiration
        if user.password_reset_expires and user.password_reset_expires < datetime.utcnow():
            raise AuthenticationError("Token de réinitialisation expiré")

        # Validation du nouveau mot de passe
        validation = password_manager.validate_password_strength(
            reset_data.new_password
        )
        if not validation['is_valid']:
            raise ValidationError(f"Mot de passe faible: {'; '.join(validation['errors'])}")

        # Mise à jour du mot de passe
        new_password_hash = password_manager.get_password_hash(
            reset_data.new_password
        )

        await self.user_repo.update(
            db,
            db_obj=user,
            obj_in={
                'password_hash': new_password_hash,
                'password_changed_at': datetime.utcnow(),
                'password_reset_token': None,
                'password_reset_expires': None,
                'failed_login_attempts': 0,  # Reset des tentatives échouées
                'locked_until': None  # Déverrouillage du compte
            }
        )

        return {'message': 'Mot de passe réinitialisé avec succès'}

    # === MÉTHODES D'AUTORISATION ===

    async def get_current_user(
            self,
            db: AsyncSession,
            token: str
    ) -> User:
        """
        Récupère l'utilisateur actuel à partir du token

        Args:
            db: Session de base de données
            token: Token d'accès

        Returns:
            L'utilisateur actuel

        Raises:
            AuthenticationError: Si le token est invalide
        """
        try:
            payload = jwt_manager.verify_token(token)
            if not payload:
                raise AuthenticationError("Token invalide")

            user_id = UUID(payload.get('sub'))
            user = await self.user_repo.get_by_id(db, user_id)

            if not user:
                raise AuthenticationError("Utilisateur non trouvé")

            if not user.is_active:
                raise AuthenticationError("Compte désactivé")

            return user

        except ValueError:  # UUID invalide
            raise AuthenticationError("Token malformé")
        except Exception:
            raise AuthenticationError("Erreur de vérification du token")

    async def verify_permission(
            self,
            user: User,
            required_permission: str,
            resource_id: Optional[UUID] = None
    ) -> bool:
        """
        Vérifie les permissions d'un utilisateur

        Args:
            user: Utilisateur à vérifier
            required_permission: Permission requise
            resource_id: ID de la ressource (optionnel)

        Returns:
            True si autorisé

        Raises:
            AuthorizationError: Si non autorisé
        """
        # Permissions de base
        if required_permission == 'authenticated':
            return True

        if required_permission == 'verified' and not user.is_verified:
            raise EmailNotVerifiedError("Email non vérifié")

        if required_permission == 'admin' and not user.is_superuser:
            raise AuthorizationError("Permissions administrateur requises")

        # Permissions sur les ressources
        if required_permission == 'own_resource' and resource_id:
            if user.id != resource_id and not user.is_superuser:
                raise AuthorizationError("Accès non autorisé à cette ressource")

        return True

    # === MÉTHODES PRIVÉES ===

    async def _validate_registration_data(
            self,
            db: AsyncSession,
            register_data: RegisterRequest
    ) -> None:
        """Valide les données d'inscription"""
        errors = []

        # Validation du nom d'utilisateur
        username_validation = input_validator.validate_username(register_data.username)
        if not username_validation['is_valid']:
            errors.extend(username_validation['errors'])

        # Vérification de la disponibilité du nom d'utilisateur
        username_available = await self.user_repo.is_username_available(
            db, register_data.username
        )
        if not username_available:
            errors.append("Nom d'utilisateur déjà utilisé")

        # Validation de l'email
        email_validation = input_validator.validate_email(register_data.email)
        if not email_validation['is_valid']:
            errors.extend(email_validation['errors'])

        # Vérification de la disponibilité de l'email
        email_available = await self.user_repo.is_email_available(
            db, register_data.email
        )
        if not email_available:
            errors.append("Adresse email déjà utilisée")

        if errors:
            raise ValidationError("; ".join(errors))

    async def _handle_successful_login(
            self,
            db: AsyncSession,
            user: User,
            ip_address: str,
            user_agent: str
    ) -> None:
        """Gère une connexion réussie"""
        user.record_login(ip_address)
        await db.commit()

    def _log_successful_authentication(
            self,
            username: str,
            ip_address: str,
            user_agent: str
    ) -> None:
        """Log une authentification réussie"""
        log_data = security_auditor.log_authentication_attempt(
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True
        )
        # TODO: Envoyer vers le système de logging
        print(f"[AUTH SUCCESS] {log_data}")

    def _log_failed_authentication(
            self,
            username: str,
            ip_address: str,
            user_agent: str,
            reason: str
    ) -> None:
        """Log une authentification échouée"""
        log_data = security_auditor.log_authentication_attempt(
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            failure_reason=reason
        )
        # TODO: Envoyer vers le système de logging
        print(f"[AUTH FAILURE] {log_data}")


# Instance globale du service
auth_service = AuthService()