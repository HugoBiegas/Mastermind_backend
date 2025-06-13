"""
Repository de base avec pattern générique
Opérations CRUD communes et optimisations SQLAlchemy 2.0
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from uuid import UUID

from sqlalchemy import and_, desc, asc, func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.exc import IntegrityError, NoResultFound

from app.core.database import Base, PaginationHelper
from app.utils.exceptions import (
    EntityNotFoundError,
    DuplicateEntityError,
    DatabaseError
)

# Type générique pour les modèles
ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType], ABC):
    """
    Repository de base avec opérations CRUD génériques
    Implémente le pattern Repository avec SQLAlchemy 2.0 async
    """

    def __init__(self, model: Type[ModelType]):
        """
        Initialise le repository avec le modèle

        Args:
            model: Classe du modèle SQLAlchemy
        """
        self.model = model

    # === MÉTHODES CRUD DE BASE ===

    async def get_by_id(
            self,
            db: AsyncSession,
            id: UUID,
            *,
            with_deleted: bool = False,
            eager_load: Optional[List[str]] = None
    ) -> Optional[ModelType]:
        """
        Récupère une entité par son ID

        Args:
            db: Session de base de données
            id: ID de l'entité
            with_deleted: Inclure les entités supprimées logiquement
            eager_load: Relations à charger en eager loading

        Returns:
            L'entité ou None si non trouvée
        """
        try:
            query = select(self.model).where(self.model.id == id)

            # Gestion de la suppression logique
            if hasattr(self.model, 'is_deleted') and not with_deleted:
                query = query.where(self.model.is_deleted == False)

            # Eager loading des relations
            if eager_load:
                for relation in eager_load:
                    if hasattr(self.model, relation):
                        query = query.options(selectinload(getattr(self.model, relation)))

            result = await db.execute(query)
            return result.scalar_one_or_none()

        except Exception as e:
            raise DatabaseError(f"Erreur lors de la récupération de l'entité {id}: {str(e)}")

    async def get_by_field(
            self,
            db: AsyncSession,
            field_name: str,
            field_value: Any,
            *,
            with_deleted: bool = False
    ) -> Optional[ModelType]:
        """
        Récupère une entité par un champ spécifique

        Args:
            db: Session de base de données
            field_name: Nom du champ
            field_value: Valeur du champ
            with_deleted: Inclure les entités supprimées

        Returns:
            L'entité ou None si non trouvée
        """
        try:
            if not hasattr(self.model, field_name):
                raise ValueError(f"Champ '{field_name}' n'existe pas sur le modèle {self.model.__name__}")

            field = getattr(self.model, field_name)
            query = select(self.model).where(field == field_value)

            if hasattr(self.model, 'is_deleted') and not with_deleted:
                query = query.where(self.model.is_deleted == False)

            result = await db.execute(query)
            return result.scalar_one_or_none()

        except Exception as e:
            raise DatabaseError(f"Erreur lors de la récupération par {field_name}: {str(e)}")

    async def get_multi(
            self,
            db: AsyncSession,
            *,
            skip: int = 0,
            limit: int = 100,
            filters: Optional[Dict[str, Any]] = None,
            order_by: Optional[str] = None,
            order_desc: bool = False,
            with_deleted: bool = False,
            eager_load: Optional[List[str]] = None
    ) -> List[ModelType]:
        """
        Récupère plusieurs entités avec pagination et filtres

        Args:
            db: Session de base de données
            skip: Nombre d'entités à ignorer
            limit: Nombre maximum d'entités
            filters: Filtres à appliquer
            order_by: Champ de tri
            order_desc: Tri décroissant
            with_deleted: Inclure les entités supprimées
            eager_load: Relations à charger

        Returns:
            Liste des entités
        """
        try:
            query = select(self.model)

            # Application des filtres
            if filters:
                conditions = []
                for field_name, value in filters.items():
                    if hasattr(self.model, field_name):
                        field = getattr(self.model, field_name)
                        if isinstance(value, list):
                            conditions.append(field.in_(value))
                        else:
                            conditions.append(field == value)
                if conditions:
                    query = query.where(and_(*conditions))

            # Gestion de la suppression logique
            if hasattr(self.model, 'is_deleted') and not with_deleted:
                query = query.where(self.model.is_deleted == False)

            # Tri
            if order_by and hasattr(self.model, order_by):
                order_field = getattr(self.model, order_by)
                if order_desc:
                    query = query.order_by(desc(order_field))
                else:
                    query = query.order_by(asc(order_field))
            else:
                # Tri par défaut sur created_at
                if hasattr(self.model, 'created_at'):
                    query = query.order_by(desc(self.model.created_at))

            # Eager loading
            if eager_load:
                for relation in eager_load:
                    if hasattr(self.model, relation):
                        query = query.options(selectinload(getattr(self.model, relation)))

            # Pagination
            query = query.offset(skip).limit(limit)

            result = await db.execute(query)
            return result.scalars().all()

        except Exception as e:
            raise DatabaseError(f"Erreur lors de la récupération multiple: {str(e)}")

    async def create(
            self,
            db: AsyncSession,
            *,
            obj_in: CreateSchemaType,
            created_by: Optional[UUID] = None,
            commit: bool = True
    ) -> ModelType:
        """
        Crée une nouvelle entité

        Args:
            db: Session de base de données
            obj_in: Données de création
            created_by: ID de l'utilisateur créateur
            commit: Effectuer le commit automatiquement

        Returns:
            L'entité créée
        """
        try:
            # Conversion du schéma Pydantic en dict
            if hasattr(obj_in, 'dict'):
                obj_data = obj_in.dict(exclude_unset=True)
            else:
                obj_data = obj_in

            # Ajout de l'audit si disponible
            if hasattr(self.model, 'created_by') and created_by:
                obj_data['created_by'] = created_by

            # Création de l'instance
            db_obj = self.model(**obj_data)
            db.add(db_obj)

            if commit:
                await db.commit()
                await db.refresh(db_obj)

            return db_obj

        except IntegrityError as e:
            await db.rollback()
            raise DuplicateEntityError(f"Entité déjà existante: {str(e)}")
        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"Erreur lors de la création: {str(e)}")

    async def update(
            self,
            db: AsyncSession,
            *,
            db_obj: ModelType,
            obj_in: Union[UpdateSchemaType, Dict[str, Any]],
            updated_by: Optional[UUID] = None,
            commit: bool = True
    ) -> ModelType:
        """
        Met à jour une entité existante

        Args:
            db: Session de base de données
            db_obj: Entité à mettre à jour
            obj_in: Nouvelles données
            updated_by: ID de l'utilisateur modificateur
            commit: Effectuer le commit automatiquement

        Returns:
            L'entité mise à jour
        """
        try:
            # Conversion du schéma en dict
            if hasattr(obj_in, 'dict'):
                update_data = obj_in.dict(exclude_unset=True)
            else:
                update_data = obj_in

            # Ajout de l'audit si disponible
            if hasattr(db_obj, 'updated_by') and updated_by:
                update_data['updated_by'] = updated_by

            # Mise à jour des champs
            for field, value in update_data.items():
                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)

            if commit:
                await db.commit()
                await db.refresh(db_obj)

            return db_obj

        except IntegrityError as e:
            await db.rollback()
            raise DuplicateEntityError(f"Conflit lors de la mise à jour: {str(e)}")
        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"Erreur lors de la mise à jour: {str(e)}")

    async def delete(
            self,
            db: AsyncSession,
            *,
            id: UUID,
            soft_delete: bool = True,
            deleted_by: Optional[UUID] = None,
            commit: bool = True
    ) -> bool:
        """
        Supprime une entité

        Args:
            db: Session de base de données
            id: ID de l'entité à supprimer
            soft_delete: Suppression logique ou physique
            deleted_by: ID de l'utilisateur supprimant
            commit: Effectuer le commit automatiquement

        Returns:
            True si supprimé avec succès
        """
        try:
            db_obj = await self.get_by_id(db, id)
            if not db_obj:
                raise EntityNotFoundError(f"Entité {id} non trouvée")

            if soft_delete and hasattr(db_obj, 'soft_delete'):
                # Suppression logique
                db_obj.soft_delete()
                if hasattr(db_obj, 'updated_by') and deleted_by:
                    db_obj.updated_by = deleted_by
            else:
                # Suppression physique
                await db.delete(db_obj)

            if commit:
                await db.commit()

            return True

        except EntityNotFoundError:
            raise
        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"Erreur lors de la suppression: {str(e)}")

    # === MÉTHODES DE COMPTAGE ===

    async def count(
            self,
            db: AsyncSession,
            *,
            filters: Optional[Dict[str, Any]] = None,
            with_deleted: bool = False
    ) -> int:
        """
        Compte le nombre d'entités

        Args:
            db: Session de base de données
            filters: Filtres à appliquer
            with_deleted: Inclure les entités supprimées

        Returns:
            Nombre d'entités
        """
        try:
            query = select(func.count(self.model.id))

            # Application des filtres
            if filters:
                conditions = []
                for field_name, value in filters.items():
                    if hasattr(self.model, field_name):
                        field = getattr(self.model, field_name)
                        conditions.append(field == value)
                if conditions:
                    query = query.where(and_(*conditions))

            # Gestion de la suppression logique
            if hasattr(self.model, 'is_deleted') and not with_deleted:
                query = query.where(self.model.is_deleted == False)

            result = await db.execute(query)
            return result.scalar()

        except Exception as e:
            raise DatabaseError(f"Erreur lors du comptage: {str(e)}")

    async def exists(
            self,
            db: AsyncSession,
            *,
            filters: Dict[str, Any],
            with_deleted: bool = False
    ) -> bool:
        """
        Vérifie l'existence d'une entité

        Args:
            db: Session de base de données
            filters: Critères de recherche
            with_deleted: Inclure les entités supprimées

        Returns:
            True si l'entité existe
        """
        count = await self.count(db, filters=filters, with_deleted=with_deleted)
        return count > 0

    # === MÉTHODES DE PAGINATION ===

    async def get_paginated(
            self,
            db: AsyncSession,
            *,
            page: int = 1,
            page_size: int = 20,
            filters: Optional[Dict[str, Any]] = None,
            order_by: Optional[str] = None,
            order_desc: bool = False,
            with_deleted: bool = False,
            eager_load: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Récupère des entités avec pagination complète

        Args:
            db: Session de base de données
            page: Numéro de page (commence à 1)
            page_size: Taille de la page
            filters: Filtres à appliquer
            order_by: Champ de tri
            order_desc: Tri décroissant
            with_deleted: Inclure les entités supprimées
            eager_load: Relations à charger

        Returns:
            Dictionnaire avec items et métadonnées de pagination
        """
        # Validation des paramètres
        page = max(1, page)
        page_size = min(max(1, page_size), 100)  # Limite à 100 items par page

        # Calcul de l'offset
        skip = (page - 1) * page_size

        # Récupération des entités
        items = await self.get_multi(
            db,
            skip=skip,
            limit=page_size,
            filters=filters,
            order_by=order_by,
            order_desc=order_desc,
            with_deleted=with_deleted,
            eager_load=eager_load
        )

        # Comptage total
        total = await self.count(db, filters=filters, with_deleted=with_deleted)

        # Métadonnées de pagination
        return PaginationHelper.create_pagination_response(items, total, page, page_size)

    # === MÉTHODES DE BULK OPERATIONS ===

    async def bulk_create(
            self,
            db: AsyncSession,
            *,
            objs_in: List[CreateSchemaType],
            created_by: Optional[UUID] = None,
            commit: bool = True
    ) -> List[ModelType]:
        """
        Crée plusieurs entités en lot

        Args:
            db: Session de base de données
            objs_in: Liste des données de création
            created_by: ID de l'utilisateur créateur
            commit: Effectuer le commit automatiquement

        Returns:
            Liste des entités créées
        """
        try:
            db_objs = []
            for obj_in in objs_in:
                if hasattr(obj_in, 'dict'):
                    obj_data = obj_in.dict(exclude_unset=True)
                else:
                    obj_data = obj_in

                if hasattr(self.model, 'created_by') and created_by:
                    obj_data['created_by'] = created_by

                db_obj = self.model(**obj_data)
                db.add(db_obj)
                db_objs.append(db_obj)

            if commit:
                await db.commit()
                for db_obj in db_objs:
                    await db.refresh(db_obj)

            return db_objs

        except IntegrityError as e:
            await db.rollback()
            raise DuplicateEntityError(f"Erreur de contrainte lors de la création en lot: {str(e)}")
        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"Erreur lors de la création en lot: {str(e)}")

    async def bulk_update(
            self,
            db: AsyncSession,
            *,
            filters: Dict[str, Any],
            values: Dict[str, Any],
            updated_by: Optional[UUID] = None,
            commit: bool = True
    ) -> int:
        """
        Met à jour plusieurs entités en lot

        Args:
            db: Session de base de données
            filters: Critères de sélection
            values: Nouvelles valeurs
            updated_by: ID de l'utilisateur modificateur
            commit: Effectuer le commit automatiquement

        Returns:
            Nombre d'entités mises à jour
        """
        try:
            query = update(self.model)

            # Application des filtres
            conditions = []
            for field_name, value in filters.items():
                if hasattr(self.model, field_name):
                    field = getattr(self.model, field_name)
                    conditions.append(field == value)

            if conditions:
                query = query.where(and_(*conditions))

            # Ajout de l'audit
            if hasattr(self.model, 'updated_by') and updated_by:
                values['updated_by'] = updated_by

            query = query.values(**values)

            result = await db.execute(query)

            if commit:
                await db.commit()

            return result.rowcount

        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"Erreur lors de la mise à jour en lot: {str(e)}")

    # === MÉTHODES ABSTRAITES ===

    @abstractmethod
    async def get_by_unique_field(
            self,
            db: AsyncSession,
            field_value: Any
    ) -> Optional[ModelType]:
        """
        Récupère une entité par un champ unique spécifique au modèle
        À implémenter dans chaque repository enfant
        """
        pass