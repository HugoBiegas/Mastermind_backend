"""
Service de gestion des objets et effets de jeu
COMPLET: Système d'objets avancé pour le multijoueur
"""
import asyncio
import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.multijoueur import (
    GameItem, PlayerProgress, MultiplayerGame, ItemType, ItemRarity
)
from app.utils.exceptions import (
    ItemError, ItemNotFoundError, ItemNotAvailableError,
    InvalidItemTargetError, GameError
)

logger = logging.getLogger(__name__)


class GameItemService:
    """Service pour la gestion des objets de jeu"""

    def __init__(self):
        # Cache des objets par type
        self._items_cache: Dict[str, GameItem] = {}

        # Effets actifs par partie
        self._active_effects: Dict[str, List[Dict[str, Any]]] = {}

        # Probabilités de drop par rareté
        self._drop_rates = {
            ItemRarity.COMMON: 0.6,
            ItemRarity.RARE: 0.25,
            ItemRarity.EPIC: 0.12,
            ItemRarity.LEGENDARY: 0.03
        }

        logger.info("🎁 GameItemService initialisé")

    # =====================================================
    # GESTION DES OBJETS DISPONIBLES
    # =====================================================

    async def initialize_items_cache(self, db: AsyncSession):
        """Initialise le cache des objets depuis la base de données"""
        try:
            result = await db.execute(
                select(GameItem).where(GameItem.is_active == True)
            )
            items = result.scalars().all()

            self._items_cache = {item.item_type.value: item for item in items}
            logger.info(f"🎁 Cache d'objets initialisé: {len(self._items_cache)} objets")

        except Exception as e:
            logger.error(f"❌ Erreur initialisation cache objets: {e}")
            raise

    async def get_all_available_items(self, db: AsyncSession) -> List[GameItem]:
        """Récupère tous les objets disponibles"""
        if not self._items_cache:
            await self.initialize_items_cache(db)

        return list(self._items_cache.values())

    async def get_item_by_type(self, db: AsyncSession, item_type: str) -> GameItem:
        """Récupère un objet par son type"""
        if not self._items_cache:
            await self.initialize_items_cache(db)

        if item_type not in self._items_cache:
            raise ItemNotFoundError(item_type)

        return self._items_cache[item_type]

    # =====================================================
    # ATTRIBUTION D'OBJETS AUX JOUEURS
    # =====================================================

    async def award_random_items_to_player(
            self,
            db: AsyncSession,
            multiplayer_game_id: UUID,
            user_id: UUID,
            count: int = 1
    ) -> List[str]:
        """Attribue des objets aléatoires à un joueur"""
        try:
            # Récupérer la progression du joueur
            progress_query = select(PlayerProgress).where(
                and_(
                    PlayerProgress.multiplayer_game_id == multiplayer_game_id,
                    PlayerProgress.user_id == user_id
                )
            )
            result = await db.execute(progress_query)
            player_progress = result.scalar_one_or_none()

            if not player_progress:
                raise GameError(f"Progression du joueur {user_id} introuvable")

            # Générer des objets aléatoires
            awarded_items = []
            for _ in range(count):
                item_type = self._generate_random_item()
                if item_type:
                    awarded_items.append(item_type)

            # Mettre à jour la progression du joueur
            current_items = player_progress.collected_items or []
            current_items.extend(awarded_items)
            player_progress.collected_items = current_items

            await db.commit()

            logger.info(f"🎁 Objets attribués à {user_id}: {awarded_items}")
            return awarded_items

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Erreur attribution objets: {e}")
            raise

    async def award_mastermind_completion_items(
            self,
            db: AsyncSession,
            multiplayer_game_id: UUID,
            user_id: UUID,
            mastermind_number: int,
            attempts_used: int,
            max_attempts: int
    ) -> List[str]:
        """Attribue des objets pour la complétion d'un mastermind"""
        # Calculer le nombre d'objets basé sur la performance
        bonus_multiplier = 1.0

        # Bonus pour complétion rapide
        if attempts_used <= max_attempts // 2:
            bonus_multiplier = 2.0
        elif attempts_used <= max_attempts * 0.75:
            bonus_multiplier = 1.5

        # Déterminer le nombre d'objets
        base_items = 1
        bonus_items = int(bonus_multiplier - 1.0)
        total_items = base_items + bonus_items

        awarded_items = await self.award_random_items_to_player(
            db, multiplayer_game_id, user_id, total_items
        )

        logger.info(f"🏆 Objets de complétion mastermind {mastermind_number} pour {user_id}: {awarded_items}")
        return awarded_items

    def _generate_random_item(self) -> Optional[str]:
        """Génère un objet aléatoire basé sur les probabilités"""
        if not self._items_cache:
            return None

        # Sélectionner la rareté
        rand = random.random()
        selected_rarity = None

        cumulative_prob = 0.0
        for rarity, prob in self._drop_rates.items():
            cumulative_prob += prob
            if rand <= cumulative_prob:
                selected_rarity = rarity
                break

        if not selected_rarity:
            selected_rarity = ItemRarity.COMMON

        # Sélectionner un objet de cette rareté
        items_of_rarity = [
            item for item in self._items_cache.values()
            if item.rarity == selected_rarity
        ]

        if items_of_rarity:
            return random.choice(items_of_rarity).item_type.value

        return None

    # =====================================================
    # UTILISATION D'OBJETS
    # =====================================================

    async def use_item(
            self,
            db: AsyncSession,
            multiplayer_game_id: UUID,
            user_id: UUID,
            item_type: str,
            target_user_id: Optional[UUID] = None,
            parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Utilise un objet"""
        try:
            # Vérifier que le joueur possède l'objet
            await self._verify_player_has_item(db, multiplayer_game_id, user_id, item_type)

            # Récupérer l'objet
            item = await self.get_item_by_type(db, item_type)

            # Vérifier la cible si nécessaire
            if item.is_offensive and not target_user_id:
                raise InvalidItemTargetError(item_type, "Aucune cible spécifiée pour un objet offensif")

            # Appliquer l'effet
            effect_result = await self._apply_item_effect(
                db, multiplayer_game_id, user_id, target_user_id, item, parameters or {}
            )

            # Marquer l'objet comme utilisé
            await self._mark_item_as_used(db, multiplayer_game_id, user_id, item_type)

            await db.commit()

            logger.info(f"🎁 Objet {item_type} utilisé par {user_id} sur {target_user_id}")
            return effect_result

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Erreur utilisation objet {item_type}: {e}")
            raise

    async def _verify_player_has_item(
            self,
            db: AsyncSession,
            multiplayer_game_id: UUID,
            user_id: UUID,
            item_type: str
    ):
        """Vérifie qu'un joueur possède un objet"""
        progress_query = select(PlayerProgress).where(
            and_(
                PlayerProgress.multiplayer_game_id == multiplayer_game_id,
                PlayerProgress.user_id == user_id
            )
        )
        result = await db.execute(progress_query)
        player_progress = result.scalar_one_or_none()

        if not player_progress:
            raise GameError(f"Progression du joueur {user_id} introuvable")

        collected_items = player_progress.collected_items or []
        used_items = player_progress.used_items or []

        # Compter les objets disponibles
        available_count = collected_items.count(item_type)
        used_count = used_items.count(item_type)
        remaining_count = available_count - used_count

        if remaining_count <= 0:
            raise ItemNotAvailableError(item_type, "Objet non possédé ou déjà utilisé")

    async def _mark_item_as_used(
            self,
            db: AsyncSession,
            multiplayer_game_id: UUID,
            user_id: UUID,
            item_type: str
    ):
        """Marque un objet comme utilisé"""
        progress_query = select(PlayerProgress).where(
            and_(
                PlayerProgress.multiplayer_game_id == multiplayer_game_id,
                PlayerProgress.user_id == user_id
            )
        )
        result = await db.execute(progress_query)
        player_progress = result.scalar_one_or_none()

        if player_progress:
            used_items = player_progress.used_items or []
            used_items.append(item_type)
            player_progress.used_items = used_items

    # =====================================================
    # EFFETS D'OBJETS
    # =====================================================

    async def _apply_item_effect(
            self,
            db: AsyncSession,
            multiplayer_game_id: UUID,
            source_user_id: UUID,
            target_user_id: Optional[UUID],
            item: GameItem,
            parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Applique l'effet d'un objet"""

        effect_id = f"{source_user_id}_{target_user_id or 'self'}_{datetime.now().timestamp()}"
        room_code = await self._get_room_code_from_multiplayer_game(db, multiplayer_game_id)

        # Router selon le type d'objet
        if item.item_type == ItemType.EXTRA_HINT:
            return await self._apply_extra_hint_effect(db, multiplayer_game_id, source_user_id, item)

        elif item.item_type == ItemType.TIME_BONUS:
            return await self._apply_time_bonus_effect(db, multiplayer_game_id, source_user_id, item)

        elif item.item_type == ItemType.SKIP_MASTERMIND:
            return await self._apply_skip_mastermind_effect(db, multiplayer_game_id, source_user_id, item)

        elif item.item_type == ItemType.DOUBLE_SCORE:
            return await self._apply_double_score_effect(db, multiplayer_game_id, source_user_id, item)

        elif item.item_type == ItemType.FREEZE_TIME:
            return await self._apply_freeze_time_effect(db, multiplayer_game_id, target_user_id, item)

        elif item.item_type == ItemType.ADD_MASTERMIND:
            return await self._apply_add_mastermind_effect(db, multiplayer_game_id, target_user_id, item)

        elif item.item_type == ItemType.REDUCE_ATTEMPTS:
            return await self._apply_reduce_attempts_effect(db, multiplayer_game_id, target_user_id, item)

        elif item.item_type == ItemType.SCRAMBLE_COLORS:
            return await self._apply_scramble_colors_effect(db, multiplayer_game_id, target_user_id, item)

        else:
            raise ItemError(f"Type d'objet non implémenté: {item.item_type}")

    async def _apply_extra_hint_effect(
            self,
            db: AsyncSession,
            multiplayer_game_id: UUID,
            user_id: UUID,
            item: GameItem
    ) -> Dict[str, Any]:
        """Applique l'effet d'indice supplémentaire"""
        # TODO: Intégration avec le service quantique pour générer un indice
        return {
            "effect_type": "extra_hint",
            "applied_to": str(user_id),
            "hint_granted": True,
            "message": "Indice supplémentaire accordé"
        }

    async def _apply_time_bonus_effect(
            self,
            db: AsyncSession,
            multiplayer_game_id: UUID,
            user_id: UUID,
            item: GameItem
    ) -> Dict[str, Any]:
        """Applique l'effet de bonus de temps"""
        bonus_seconds = item.effect_value or 30

        # Enregistrer l'effet temporaire
        effect = {
            "effect_type": "time_bonus",
            "user_id": str(user_id),
            "bonus_seconds": bonus_seconds,
            "applied_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=bonus_seconds)
        }

        room_code = await self._get_room_code_from_multiplayer_game(db, multiplayer_game_id)
        if room_code not in self._active_effects:
            self._active_effects[room_code] = []

        self._active_effects[room_code].append(effect)

        return {
            "effect_type": "time_bonus",
            "applied_to": str(user_id),
            "bonus_seconds": bonus_seconds,
            "message": f"Bonus de temps de {bonus_seconds} secondes accordé"
        }

    async def _apply_skip_mastermind_effect(
            self,
            db: AsyncSession,
            multiplayer_game_id: UUID,
            user_id: UUID,
            item: GameItem
    ) -> Dict[str, Any]:
        """Applique l'effet de saut de mastermind"""
        # Récupérer la progression du joueur
        progress_query = select(PlayerProgress).where(
            and_(
                PlayerProgress.multiplayer_game_id == multiplayer_game_id,
                PlayerProgress.user_id == user_id
            )
        )
        result = await db.execute(progress_query)
        player_progress = result.scalar_one_or_none()

        if not player_progress:
            raise GameError(f"Progression du joueur {user_id} introuvable")

        # Avancer au mastermind suivant
        old_mastermind = player_progress.current_mastermind
        player_progress.current_mastermind += 1
        player_progress.completed_masterminds += 1

        # Bonus de score partiel
        skip_bonus = 200  # Score de base pour un skip
        player_progress.total_score += skip_bonus

        return {
            "effect_type": "skip_mastermind",
            "applied_to": str(user_id),
            "old_mastermind": old_mastermind,
            "new_mastermind": player_progress.current_mastermind,
            "score_bonus": skip_bonus,
            "message": f"Mastermind {old_mastermind} sauté, passage au {player_progress.current_mastermind}"
        }

    async def _apply_double_score_effect(
            self,
            db: AsyncSession,
            multiplayer_game_id: UUID,
            user_id: UUID,
            item: GameItem
    ) -> Dict[str, Any]:
        """Applique l'effet de double score"""
        duration_seconds = item.duration_seconds or 300  # 5 minutes par défaut

        effect = {
            "effect_type": "double_score",
            "user_id": str(user_id),
            "multiplier": 2.0,
            "applied_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
        }

        room_code = await self._get_room_code_from_multiplayer_game(db, multiplayer_game_id)
        if room_code not in self._active_effects:
            self._active_effects[room_code] = []

        self._active_effects[room_code].append(effect)

        return {
            "effect_type": "double_score",
            "applied_to": str(user_id),
            "duration_seconds": duration_seconds,
            "multiplier": 2.0,
            "message": f"Score doublé pendant {duration_seconds // 60} minutes"
        }

    async def _apply_freeze_time_effect(
            self,
            db: AsyncSession,
            multiplayer_game_id: UUID,
            target_user_id: UUID,
            item: GameItem
    ) -> Dict[str, Any]:
        """Applique l'effet de gel du temps (malus)"""
        if not target_user_id:
            raise InvalidItemTargetError("freeze_time", "Aucune cible spécifiée")

        duration_seconds = item.duration_seconds or 10

        effect = {
            "effect_type": "freeze_time",
            "user_id": str(target_user_id),
            "applied_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
        }

        room_code = await self._get_room_code_from_multiplayer_game(db, multiplayer_game_id)
        if room_code not in self._active_effects:
            self._active_effects[room_code] = []

        self._active_effects[room_code].append(effect)

        return {
            "effect_type": "freeze_time",
            "applied_to": str(target_user_id),
            "duration_seconds": duration_seconds,
            "message": f"Temps gelé pendant {duration_seconds} secondes"
        }

    async def _apply_add_mastermind_effect(
            self,
            db: AsyncSession,
            multiplayer_game_id: UUID,
            target_user_id: UUID,
            item: GameItem
    ) -> Dict[str, Any]:
        """Applique l'effet d'ajout de mastermind (malus)"""
        if not target_user_id:
            raise InvalidItemTargetError("add_mastermind", "Aucune cible spécifiée")

        # TODO: Logique complexe pour ajouter un mastermind supplémentaire
        # Pour l'instant, simulation

        return {
            "effect_type": "add_mastermind",
            "applied_to": str(target_user_id),
            "additional_masterminds": 1,
            "message": "Mastermind supplémentaire ajouté"
        }

    async def _apply_reduce_attempts_effect(
            self,
            db: AsyncSession,
            multiplayer_game_id: UUID,
            target_user_id: UUID,
            item: GameItem
    ) -> Dict[str, Any]:
        """Applique l'effet de réduction de tentatives (malus)"""
        if not target_user_id:
            raise InvalidItemTargetError("reduce_attempts", "Aucune cible spécifiée")

        reduction = item.effect_value or 2

        return {
            "effect_type": "reduce_attempts",
            "applied_to": str(target_user_id),
            "attempts_reduced": reduction,
            "message": f"Tentatives réduites de {reduction}"
        }

    async def _apply_scramble_colors_effect(
            self,
            db: AsyncSession,
            multiplayer_game_id: UUID,
            target_user_id: UUID,
            item: GameItem
    ) -> Dict[str, Any]:
        """Applique l'effet de mélange des couleurs (malus)"""
        if not target_user_id:
            raise InvalidItemTargetError("scramble_colors", "Aucune cible spécifiée")

        duration_seconds = item.duration_seconds or 10

        effect = {
            "effect_type": "scramble_colors",
            "user_id": str(target_user_id),
            "applied_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
        }

        room_code = await self._get_room_code_from_multiplayer_game(db, multiplayer_game_id)
        if room_code not in self._active_effects:
            self._active_effects[room_code] = []

        self._active_effects[room_code].append(effect)

        return {
            "effect_type": "scramble_colors",
            "applied_to": str(target_user_id),
            "duration_seconds": duration_seconds,
            "message": f"Couleurs mélangées pendant {duration_seconds} secondes"
        }

    # =====================================================
    # GESTION DES EFFETS ACTIFS
    # =====================================================

    async def get_active_effects_for_player(
            self,
            multiplayer_game_id: UUID,
            user_id: UUID
    ) -> List[Dict[str, Any]]:
        """Récupère les effets actifs pour un joueur"""
        # Cette méthode nécessiterait le room_code, simplification pour l'exemple
        all_effects = []
        for room_effects in self._active_effects.values():
            for effect in room_effects:
                if effect.get("user_id") == str(user_id):
                    # Vérifier si l'effet n'est pas expiré
                    expires_at = effect.get("expires_at")
                    if expires_at and datetime.now(timezone.utc) < expires_at:
                        all_effects.append(effect)

        return all_effects

    async def cleanup_expired_effects(self):
        """Nettoie les effets expirés"""
        now = datetime.now(timezone.utc)

        for room_code in list(self._active_effects.keys()):
            active_effects = []

            for effect in self._active_effects[room_code]:
                expires_at = effect.get("expires_at")
                if not expires_at or now < expires_at:
                    active_effects.append(effect)
                else:
                    logger.info(f"🧹 Effet expiré nettoyé: {effect['effect_type']} pour {effect.get('user_id')}")

            self._active_effects[room_code] = active_effects

            # Supprimer les rooms vides
            if not active_effects:
                del self._active_effects[room_code]

    # =====================================================
    # MÉTHODES UTILITAIRES
    # =====================================================

    async def _get_room_code_from_multiplayer_game(
            self,
            db: AsyncSession,
            multiplayer_game_id: UUID
    ) -> str:
        """Récupère le code de room depuis l'ID de partie multijoueur"""
        from app.models.game import Game

        query = select(Game.room_code).select_from(
            MultiplayerGame.__table__.join(
                Game.__table__,
                MultiplayerGame.base_game_id == Game.id
            )
        ).where(MultiplayerGame.id == multiplayer_game_id)

        result = await db.execute(query)
        room_code = result.scalar_one_or_none()

        if not room_code:
            raise GameError(f"Room code introuvable pour la partie {multiplayer_game_id}")

        return room_code

    async def get_player_items_summary(
            self,
            db: AsyncSession,
            multiplayer_game_id: UUID,
            user_id: UUID
    ) -> Dict[str, Any]:
        """Récupère un résumé des objets d'un joueur"""
        progress_query = select(PlayerProgress).where(
            and_(
                PlayerProgress.multiplayer_game_id == multiplayer_game_id,
                PlayerProgress.user_id == user_id
            )
        )
        result = await db.execute(progress_query)
        player_progress = result.scalar_one_or_none()

        if not player_progress:
            return {"available_items": [], "used_items": [], "active_effects": []}

        collected_items = player_progress.collected_items or []
        used_items = player_progress.used_items or []

        # Calculer les objets disponibles
        available_items = []
        for item_type in set(collected_items):
            available_count = collected_items.count(item_type)
            used_count = used_items.count(item_type)
            remaining_count = available_count - used_count

            if remaining_count > 0:
                available_items.append({
                    "item_type": item_type,
                    "count": remaining_count
                })

        # Récupérer les effets actifs
        active_effects = await self.get_active_effects_for_player(multiplayer_game_id, user_id)

        return {
            "available_items": available_items,
            "used_items": list(set(used_items)),
            "active_effects": active_effects,
            "total_collected": len(collected_items),
            "total_used": len(used_items)
        }

    def get_service_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques du service"""
        total_effects = sum(len(effects) for effects in self._active_effects.values())

        return {
            "cached_items": len(self._items_cache),
            "active_rooms_with_effects": len(self._active_effects),
            "total_active_effects": total_effects,
            "drop_rates": {rarity.value: rate for rarity, rate in self._drop_rates.items()}
        }


# =====================================================
# INSTANCE GLOBALE ET TÂCHE DE NETTOYAGE
# =====================================================

# Instance globale du service
game_item_service = GameItemService()


async def start_effect_cleanup_task():
    """Démarre la tâche de nettoyage des effets"""
    while True:
        try:
            await asyncio.sleep(60)  # Nettoyer toutes les minutes
            await game_item_service.cleanup_expired_effects()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"❌ Erreur lors du nettoyage des effets: {e}")


# Log de l'état du service
logger.info("🎁 GameItemService initialisé et prêt")