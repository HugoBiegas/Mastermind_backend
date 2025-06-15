"""
Repository de base avec pattern générique
Opérations CRUD communes et optimisations SQLAlchemy 2.0
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union, Sequence
from uuid import UUID

from sqlalchemy import and_, desc, asc, func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.exc import IntegrityError, NoResultFound

from app.core.database import Base, PaginationParams, PaginationResult
from app.utils.exceptions import (
    EntityNotFoundError,
    EntityAlreadyExistsError,
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
            raise DatabaseError(f"Erreur lors de la récupération par ID: {str(e)}")

    async def get_multi(
            self,
            db: AsyncSession,
            *,
            skip: int = 0,
            limit: int = 100,
            filters: Optional[Dict[str, Any]] = None,
            order_by: Optional[str] = None,
            order_desc: bool = True,
            with_deleted: bool = False,
            eager_load: Optional[List[str]] = None
    ) -> Sequence[ModelType]:
        """
        Récupère plusieurs entités avec filtres et pagination

        Args:
            db: Session de base de données
            skip: Nombre d'éléments à ignorer
            limit: Nombre maximum d'éléments
            filters: Filtres à appliquer
            order_by: Champ de tri
            order_desc: Tri descendant
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
                        elif isinstance(value, dict):
                            # Gestion des opérateurs spéciaux
                            for op, val in value.items():
                                if op == "eq":
                                    conditions.append(field == val)
                                elif op == "ne":
                                    conditions.append(field != val)
                                elif op == "gt":
                                    conditions.append(field > val)
                                elif op == "gte":
                                    conditions.append(field >= val)
                                elif op == "lt":
                                    conditions.append(field < val)
                                elif op == "lte":
                                    conditions.append(field <= val)
                                elif op == "like":
                                    conditions.append(field.like(f"%{val}%"))
                                elif op == "ilike":
                                    conditions.append(field.ilike(f"%{val}%"))
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

    async def get_multi_paginated(
            self,
            db: AsyncSession,
            pagination: PaginationParams,
            *,
            filters: Optional[Dict[str, Any]] = None,
            order_by: Optional[str] = None,
            order_desc: bool = True,
            with_deleted: bool = False,
            eager_load: Optional[List[str]] = None
    ) -> PaginationResult:
        """
        Récupère plusieurs entités avec pagination complète

        Args:
            db: Session de base de données
            pagination: Paramètres de pagination
            filters: Filtres à appliquer
            order_by: Champ de tri
            order_desc: Tri descendant
            with_deleted: Inclure les entités supprimées
            eager_load: Relations à charger

        Returns:
            Résultat paginé avec métadonnées
        """
        # Compter le total d'éléments
        total = await self.count(
            db,
            filters=filters,
            with_deleted=with_deleted
        )

        # Récupérer les éléments
        items = await self.get_multi(
            db,
            skip=pagination.offset,
            limit=pagination.limit,
            filters=filters,
            order_by=order_by,
            order_desc=order_desc,
            with_deleted=with_deleted,
            eager_load=eager_load
        )

        return PaginationResult(
            items=items,
            total=total,
            page=pagination.page,
            per_page=pagination.per_page
        )

    async def count(
            self,
            db: AsyncSession,
            *,
            filters: Optional[Dict[str, Any]] = None,
            with_deleted: bool = False
    ) -> int:
        """
        Compte le nombre d'entités correspondant aux critères

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
                        if isinstance(value, list):
                            conditions.append(field.in_(value))
                        else:
                            conditions.append(field == value)

                if conditions:
                    query = query.where(and_(*conditions))

            # Gestion de la suppression logique
            if hasattr(self.model, 'is_deleted') and not with_deleted:
                query = query.where(self.model.is_deleted == False)

            result = await db.execute(query)
            return result.scalar() or 0

        except Exception as e:
            raise DatabaseError(f"Erreur lors du comptage: {str(e)}")

    async def create(
            self,
            db: AsyncSession,
            *,
            obj_in: Union[CreateSchemaType, Dict[str, Any]],
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

        Raises:
            EntityAlreadyExistsError: Si l'entité existe déjà
            DatabaseError: En cas d'erreur de base de données
        """
        try:
            # Conversion du schéma Pydantic en dict
            if hasattr(obj_in, 'model_dump'):
                obj_data = obj_in.model_dump(exclude_unset=True)
            elif hasattr(obj_in, 'dict'):
                obj_data = obj_in.dict(exclude_unset=True)
            else:
                obj_data = dict(obj_in) if not isinstance(obj_in, dict) else obj_in

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
            raise EntityAlreadyExistsError(f"Entité déjà existante: {str(e)}")
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
            if hasattr(obj_in, 'model_dump'):
                update_data = obj_in.model_dump(exclude_unset=True)
            elif hasattr(obj_in, 'dict'):
                update_data = obj_in.dict(exclude_unset=True)
            else:
                update_data = dict(obj_in) if not isinstance(obj_in, dict) else obj_in

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

        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"Erreur lors de la mise à jour: {str(e)}")

    async def delete(
            self,
            db: AsyncSession,
            *,
            id: UUID,
            deleted_by: Optional[UUID] = None,
            soft_delete: bool = True,
            commit: bool = True
    ) -> bool:
        """
        Supprime une entité

        Args:
            db: Session de base de données
            id: ID de l'entité à supprimer
            deleted_by: ID de l'utilisateur supprimant
            soft_delete: Suppression logique si supportée
            commit: Effectuer le commit automatiquement

        Returns:
            True si supprimé avec succès

        Raises:
            EntityNotFoundError: Si l'entité n'existe pas
        """
        try:
            db_obj = await self.get_by_id(db, id)
            if not db_obj:
                raise EntityNotFoundError(f"Entité avec ID {id} non trouvée")

            if soft_delete and hasattr(db_obj, 'is_deleted'):
                # Suppression logique
                db_obj.is_deleted = True
                if hasattr(db_obj, 'deleted_by') and deleted_by:
                    db_obj.deleted_by = deleted_by
                if hasattr(db_obj, 'deleted_at'):
                    from datetime import datetime, timezone
                    db_obj.deleted_at = datetime.now(timezone.utc)
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

    async def restore(
            self,
            db: AsyncSession,
            *,
            id: UUID,
            restored_by: Optional[UUID] = None,
            commit: bool = True
    ) -> ModelType:
        """
        Restaure une entité supprimée logiquement

        Args:
            db: Session de base de données
            id: ID de l'entité à restaurer
            restored_by: ID de l'utilisateur restaurant
            commit: Effectuer le commit automatiquement

        Returns:
            L'entité restaurée

        Raises:
            EntityNotFoundError: Si l'entité n'existe pas
        """
        try:
            # Récupérer avec les entités supprimées
            db_obj = await self.get_by_id(db, id, with_deleted=True)
            if not db_obj:
                raise EntityNotFoundError(f"Entité avec ID {id} non trouvée")

            if not hasattr(db_obj, 'is_deleted'):
                raise DatabaseError("La suppression logique n'est pas supportée pour ce modèle")

            # Restauration
            db_obj.is_deleted = False
            if hasattr(db_obj, 'restored_by') and restored_by:
                db_obj.restored_by = restored_by
            if hasattr(db_obj, 'restored_at'):
                from datetime import datetime, timezone
                db_obj.restored_at = datetime.now(timezone.utc)

            if commit:
                await db.commit()
                await db.refresh(db_obj)

            return db_obj

        except EntityNotFoundError:
            raise
        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"Erreur lors de la restauration: {str(e)}")

    # === MÉTHODES DE RECHERCHE AVANCÉE ===

    async def search(
            self,
            db: AsyncSession,
            *,
            query: str,
            search_fields: List[str],
            pagination: PaginationParams,
            filters: Optional[Dict[str, Any]] = None,
            order_by: Optional[str] = None,
            order_desc: bool = True
    ) -> PaginationResult:
        """
        Recherche textuelle dans plusieurs champs

        Args:
            db: Session de base de données
            query: Terme de recherche
            search_fields: Champs dans lesquels chercher
            pagination: Paramètres de pagination
            filters: Filtres supplémentaires
            order_by: Champ de tri
            order_desc: Tri descendant

        Returns:
            Résultat paginé
        """
        try:
            base_query = select(self.model)

            # Conditions de recherche textuelle
            search_conditions = []
            for field_name in search_fields:
                if hasattr(self.model, field_name):
                    field = getattr(self.model, field_name)
                    search_conditions.append(field.ilike(f"%{query}%"))

            if search_conditions:
                base_query = base_query.where(or_(*search_conditions))

            # Application des filtres supplémentaires
            if filters:
                filter_conditions = []
                for field_name, value in filters.items():
                    if hasattr(self.model, field_name):
                        field = getattr(self.model, field_name)
                        filter_conditions.append(field == value)

                if filter_conditions:
                    base_query = base_query.where(and_(*filter_conditions))

            # Gestion de la suppression logique
            if hasattr(self.model, 'is_deleted'):
                base_query = base_query.where(self.model.is_deleted == False)

            # Compter le total
            count_query = select(func.count(self.model.id)).select_from(base_query.subquery())
            count_result = await db.execute(count_query)
            total = count_result.scalar() or 0

            # Tri et pagination
            if order_by and hasattr(self.model, order_by):
                order_field = getattr(self.model, order_by)
                if order_desc:
                    base_query = base_query.order_by(desc(order_field))
                else:
                    base_query = base_query.order_by(asc(order_field))

            base_query = base_query.offset(pagination.offset).limit(pagination.limit)

            # Exécution
            result = await db.execute(base_query)
            items = result.scalars().all()

            return PaginationResult(
                items=items,
                total=total,
                page=pagination.page,
                per_page=pagination.per_page
            )

        except Exception as e:
            raise DatabaseError(f"Erreur lors de la recherche: {str(e)}")

    async def bulk_create(
            self,
            db: AsyncSession,
            *,
            objs_in: List[Union[CreateSchemaType, Dict[str, Any]]],
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
                # Conversion en dict
                if hasattr(obj_in, 'model_dump'):
                    obj_data = obj_in.model_dump(exclude_unset=True)
                elif hasattr(obj_in, 'dict'):
                    obj_data = obj_in.dict(exclude_unset=True)
                else:
                    obj_data = dict(obj_in) if not isinstance(obj_in, dict) else obj_in

                # Ajout de l'audit
                if hasattr(self.model, 'created_by') and created_by:
                    obj_data['created_by'] = created_by

                db_obj = self.model(**obj_data)
                db_objs.append(db_obj)

            db.add_all(db_objs)

            if commit:
                await db.commit()
                for obj in db_objs:
                    await db.refresh(obj)

            return db_objs

        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"Erreur lors de la création en lot: {str(e)}")

    async def bulk_update(
            self,
            db: AsyncSession,
            *,
            filters: Dict[str, Any],
            update_data: Dict[str, Any],
            updated_by: Optional[UUID] = None,
            commit: bool = True
    ) -> int:
        """
        Met à jour plusieurs entités en lot

        Args:
            db: Session de base de données
            filters: Critères de sélection
            update_data: Données de mise à jour
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
                update_data['updated_by'] = updated_by

            query = query.values(**update_data)

            result = await db.execute(query)

            if commit:
                await db.commit()

            return result.rowcount

        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"Erreur lors de la mise à jour en lot: {str(e)}")


# === MIXINS POUR FONCTIONNALITÉS SPÉCIFIQUES ===

class SoftDeleteMixin:
    """Mixin pour la suppression logique"""

    async def get_deleted(
            self,
            db: AsyncSession,
            pagination: Optional[PaginationParams] = None
    ) -> Union[Sequence[ModelType], PaginationResult]:
        """Récupère les entités supprimées logiquement"""
        if not hasattr(self.model, 'is_deleted'):
            raise NotImplementedError("Le modèle ne supporte pas la suppression logique")

        filters = {"is_deleted": True}

        if pagination:
            return await self.get_multi_paginated(
                db, pagination, filters=filters, with_deleted=True
            )
        else:
            return await self.get_multi(db, filters=filters, with_deleted=True)


class TimestampMixin:
    """Mixin pour les horodatages"""

    async def get_recent(
            self,
            db: AsyncSession,
            *,
            hours: int = 24,
            pagination: Optional[PaginationParams] = None
    ) -> Union[Sequence[ModelType], PaginationResult]:
        """Récupère les entités créées récemment"""
        if not hasattr(self.model, 'created_at'):
            raise NotImplementedError("Le modèle ne supporte pas les horodatages")

        from datetime import datetime, timezone, timedelta
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        filters = {"created_at": {"gte": since}}

        if pagination:
            return await self.get_multi_paginated(db, pagination, filters=filters)
        else:
            return await self.get_multi(db, filters=filters, order_by="created_at")


# === REPOSITORY COMPLET ===

class BaseRepositoryWithMixins(
    BaseRepository[ModelType, CreateSchemaType, UpdateSchemaType],
    SoftDeleteMixin,
    TimestampMixin
):
    """Repository de base avec tous les mixins"""
    pass


# === EXPORTS ===

__all__ = [
    "BaseRepository",
    "SoftDeleteMixin",
    "TimestampMixin",
    "BaseRepositoryWithMixins"
]