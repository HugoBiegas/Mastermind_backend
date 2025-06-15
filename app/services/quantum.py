"""
Service quantique pour Quantum Mastermind
Implémentation des algorithmes quantiques avec Qiskit 2.0.2
"""
import json
import math
import random
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

# Imports Qiskit 2.0.2 compatibles
from qiskit import QuantumCircuit, transpile
from qiskit_aer import Aer
from qiskit.primitives import Sampler
from qiskit.quantum_info import Statevector
import numpy as np

from app.core.config import settings, quantum_config
from app.models.game import Game, GameParticipation
from app.models.user import User
from app.schemas.quantum import QuantumHint, QuantumHintType
from app.utils.exceptions import (
    EntityNotFoundError, GameError, QuantumError,
    ValidationError
)


class QuantumService:
    """Service pour les opérations quantiques"""

    def __init__(self):
        # Configuration du backend quantique
        self.backend = Aer.get_backend(settings.QISKIT_BACKEND)
        self.sampler = Sampler()

        # Paramètres par défaut
        self.default_shots = quantum_config.DEFAULT_SHOTS
        self.max_qubits = quantum_config.MAX_QUBITS_PER_CIRCUIT

    # === GÉNÉRATION DE HINTS QUANTIQUES ===

    async def generate_quantum_hint(
        self,
        db: AsyncSession,
        game_id: UUID,
        player_id: UUID,
        hint_type: str = "grover"
    ) -> QuantumHint:
        """
        Génère un hint quantique pour aider le joueur

        Args:
            db: Session de base de données
            game_id: ID de la partie
            player_id: ID du joueur
            hint_type: Type de hint quantique

        Returns:
            Hint quantique généré

        Raises:
            EntityNotFoundError: Si la partie ou le joueur n'existe pas
            GameError: Si le hint ne peut pas être généré
        """
        # Vérifications préliminaires
        game, participation = await self._validate_quantum_request(
            db, game_id, player_id
        )

        # Vérifier que les hints quantiques sont activés
        if not game.get_setting("quantum_enabled", True):
            raise GameError("Les fonctionnalités quantiques sont désactivées pour cette partie")

        # Calculer le coût
        hint_cost = self._calculate_hint_cost(hint_type, game.difficulty)

        # Vérifier si le joueur a assez de points (si applicable)
        # Pour l'instant, on autorise toujours

        try:
            # Générer le hint selon le type
            if hint_type == "grover":
                hint_data = await self._generate_grover_hint(game, participation)
            elif hint_type == "superposition":
                hint_data = await self._generate_superposition_hint(game, participation)
            elif hint_type == "entanglement":
                hint_data = await self._generate_entanglement_hint(game, participation)
            elif hint_type == "interference":
                hint_data = await self._generate_interference_hint(game, participation)
            else:
                raise ValidationError(f"Type de hint non supporté: {hint_type}")

            # Mettre à jour les statistiques
            participation.quantum_hints_used += 1
            await db.commit()

            return QuantumHint(
                hint_type=QuantumHintType(hint_type),
                hint_data=hint_data,
                cost_points=hint_cost,
                confidence=hint_data.get("confidence", 0.8),
                quantum_state=hint_data.get("quantum_state"),
                measurement_results=hint_data.get("measurements", []),
                description=hint_data.get("description", "Hint quantique généré")
            )

        except Exception as e:
            raise QuantumError(f"Erreur lors de la génération du hint quantique: {str(e)}")

    # === ALGORITHMES QUANTIQUES SPÉCIFIQUES ===

    async def _generate_grover_hint(
        self,
        game: Game,
        participation: GameParticipation
    ) -> Dict[str, Any]:
        """
        Génère un hint basé sur l'algorithme de Grover

        L'algorithme de Grover permet de rechercher efficacement dans un espace
        de solutions non structuré. Ici, on l'utilise pour donner des indices
        sur les couleurs les plus probables.
        """
        try:
            solution = json.loads(game.classical_solution)
            combination_length = game.combination_length
            color_count = game.color_count

            # Créer un circuit quantique pour Grover
            n_qubits = math.ceil(math.log2(color_count))
            if n_qubits > self.max_qubits:
                n_qubits = min(4, self.max_qubits)  # Limitation

            qc = QuantumCircuit(n_qubits, n_qubits)

            # Initialisation en superposition
            for i in range(n_qubits):
                qc.h(i)

            # Oracle de Grover (simplifié pour la démonstration)
            # En réalité, on marquerait les états correspondant aux bonnes couleurs
            target_color = random.choice(solution)  # Hint sur une couleur aléatoire

            # Simulation d'une rotation oracle
            qc.barrier()
            if target_color % 2 == 0:  # Condition arbitraire pour la démonstration
                qc.z(0)

            # Diffuseur (amplification d'amplitude)
            for i in range(n_qubits):
                qc.h(i)
                qc.z(i)

            # Rotation collective
            qc.h(n_qubits - 1)
            if n_qubits > 1:
                qc.cx(range(n_qubits - 1), n_qubits - 1)
            qc.h(n_qubits - 1)

            for i in range(n_qubits):
                qc.z(i)
                qc.h(i)

            # Mesure
            qc.measure_all()

            # Exécution sur le simulateur
            transpiled_qc = transpile(qc, self.backend)
            job = self.backend.run(transpiled_qc, shots=self.default_shots)
            result = job.result()
            counts = result.get_counts()

            # Analyser les résultats
            most_probable_states = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:3]

            # Convertir en conseils de couleurs
            suggested_colors = []
            for state, count in most_probable_states:
                color_value = int(state, 2) % color_count
                probability = count / self.default_shots
                suggested_colors.append({
                    "color": color_value,
                    "probability": probability,
                    "quantum_state": state
                })

            hint_message = f"L'algorithme de Grover suggère ces couleurs : {[c['color'] for c in suggested_colors[:2]]}"

            return {
                "type": "grover_search",
                "suggested_colors": suggested_colors,
                "description": hint_message,
                "confidence": 0.75,
                "quantum_state": str(qc),
                "measurements": counts,
                "algorithm_info": {
                    "name": "Algorithme de Grover",
                    "description": "Recherche quantique dans l'espace des solutions",
                    "iterations": 1,
                    "qubits_used": n_qubits
                }
            }

        except Exception as e:
            raise QuantumError(f"Erreur dans l'algorithme de Grover: {str(e)}")

    async def _generate_superposition_hint(
        self,
        game: Game,
        participation: GameParticipation
    ) -> Dict[str, Any]:
        """
        Génère un hint basé sur la superposition quantique

        Utilise la superposition pour explorer plusieurs possibilités simultanément
        """
        try:
            solution = json.loads(game.classical_solution)
            combination_length = game.combination_length

            # Créer un circuit en superposition
            n_qubits = min(combination_length, self.max_qubits)
            qc = QuantumCircuit(n_qubits, n_qubits)

            # Mettre tous les qubits en superposition
            for i in range(n_qubits):
                qc.h(i)

            # Ajouter des rotations basées sur la solution (sans la révéler complètement)
            for i, color in enumerate(solution[:n_qubits]):
                # Rotation conditionnelle qui encode subtilement l'information
                angle = (color / game.color_count) * np.pi / 2
                qc.ry(angle, i)

            # Mesure
            qc.measure_all()

            # Exécution
            transpiled_qc = transpile(qc, self.backend)
            job = self.backend.run(transpiled_qc, shots=self.default_shots // 2)
            result = job.result()
            counts = result.get_counts()

            # Analyser la distribution des états
            position_hints = []
            for i in range(n_qubits):
                zeros = sum(count for state, count in counts.items() if state[-(i+1)] == '0')
                ones = sum(count for state, count in counts.items() if state[-(i+1)] == '1')
                total = zeros + ones

                if total > 0:
                    probability_one = ones / total
                    if probability_one > 0.6:
                        hint = "Cette position tend vers les couleurs paires"
                    elif probability_one < 0.4:
                        hint = "Cette position tend vers les couleurs impaires"
                    else:
                        hint = "Cette position est en superposition équilibrée"

                    position_hints.append({
                        "position": i,
                        "hint": hint,
                        "probability_distribution": {"0": zeros/total, "1": ones/total}
                    })

            return {
                "type": "superposition",
                "position_hints": position_hints,
                "description": "Analyse par superposition quantique des positions",
                "confidence": 0.65,
                "quantum_state": str(qc),
                "measurements": counts,
                "algorithm_info": {
                    "name": "Superposition Quantique",
                    "description": "Exploration simultanée de multiples états",
                    "qubits_used": n_qubits
                }
            }

        except Exception as e:
            raise QuantumError(f"Erreur dans l'algorithme de superposition: {str(e)}")

    async def _generate_entanglement_hint(
        self,
        game: Game,
        participation: GameParticipation
    ) -> Dict[str, Any]:
        """
        Génère un hint basé sur l'intrication quantique

        Utilise l'intrication pour révéler des corrélations entre positions
        """
        try:
            solution = json.loads(game.classical_solution)
            combination_length = min(game.combination_length, self.max_qubits // 2)

            if combination_length < 2:
                raise QuantumError("L'intrication nécessite au moins 2 positions")

            # Créer un circuit avec intrication
            qc = QuantumCircuit(combination_length * 2, combination_length * 2)

            # Créer des paires intriquées
            for i in range(combination_length):
                qubit1 = i * 2
                qubit2 = i * 2 + 1

                # État de Bell
                qc.h(qubit1)
                qc.cx(qubit1, qubit2)

                # Rotation basée sur la solution
                if i < len(solution):
                    color = solution[i]
                    angle = (color / game.color_count) * np.pi
                    qc.rz(angle, qubit1)

            # Mesure
            qc.measure_all()

            # Exécution
            transpiled_qc = transpile(qc, self.backend)
            job = self.backend.run(transpiled_qc, shots=self.default_shots // 3)
            result = job.result()
            counts = result.get_counts()

            # Analyser les corrélations
            correlations = []
            for i in range(combination_length):
                qubit1_pos = i * 2
                qubit2_pos = i * 2 + 1

                same_state_count = 0
                total_count = 0

                for state, count in counts.items():
                    if len(state) > max(qubit1_pos, qubit2_pos):
                        bit1 = state[-(qubit1_pos+1)]
                        bit2 = state[-(qubit2_pos+1)]
                        total_count += count
                        if bit1 == bit2:
                            same_state_count += count

                if total_count > 0:
                    correlation = same_state_count / total_count
                    if correlation > 0.7:
                        hint = "Ces positions sont fortement corrélées (couleurs similaires)"
                    elif correlation < 0.3:
                        hint = "Ces positions sont anti-corrélées (couleurs opposées)"
                    else:
                        hint = "Corrélation faible entre ces positions"

                    correlations.append({
                        "position": i,
                        "correlation_strength": correlation,
                        "hint": hint
                    })

            return {
                "type": "entanglement",
                "correlations": correlations,
                "description": "Analyse des corrélations par intrication quantique",
                "confidence": 0.70,
                "quantum_state": str(qc),
                "measurements": counts,
                "algorithm_info": {
                    "name": "Intrication Quantique",
                    "description": "Révélation de corrélations cachées entre positions",
                    "entangled_pairs": combination_length
                }
            }

        except Exception as e:
            raise QuantumError(f"Erreur dans l'algorithme d'intrication: {str(e)}")

    async def _generate_interference_hint(
        self,
        game: Game,
        participation: GameParticipation
    ) -> Dict[str, Any]:
        """
        Génère un hint basé sur l'interférence quantique

        Utilise les interférences pour amplifier les bonnes réponses
        """
        try:
            solution = json.loads(game.classical_solution)

            # Circuit d'interférence simple
            n_qubits = min(3, self.max_qubits)  # Limiter pour la démonstration
            qc = QuantumCircuit(n_qubits, n_qubits)

            # Superposition initiale
            for i in range(n_qubits):
                qc.h(i)

            # Interférence basée sur la solution
            for i, color in enumerate(solution[:n_qubits]):
                # Phase qui dépend de la couleur
                phase = (color / game.color_count) * 2 * np.pi
                qc.p(phase, i)

            # Interférence entre qubits
            for i in range(n_qubits - 1):
                qc.cx(i, i + 1)
                qc.h(i)

            # Mesure
            qc.measure_all()

            # Exécution
            transpiled_qc = transpile(qc, self.backend)
            job = self.backend.run(transpiled_qc, shots=self.default_shots)
            result = job.result()
            counts = result.get_counts()

            # Analyser les patterns d'interférence
            interference_patterns = []
            most_common = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:3]

            for state, count in most_common:
                probability = count / self.default_shots
                pattern_info = {
                    "quantum_state": state,
                    "probability": probability,
                    "interpretation": self._interpret_interference_pattern(state, game.color_count)
                }
                interference_patterns.append(pattern_info)

            hint_message = "Les interférences quantiques révèlent des patterns dans la solution"

            return {
                "type": "interference",
                "patterns": interference_patterns,
                "description": hint_message,
                "confidence": 0.60,
                "quantum_state": str(qc),
                "measurements": counts,
                "algorithm_info": {
                    "name": "Interférence Quantique",
                    "description": "Amplification des bonnes réponses par interférence",
                    "qubits_used": n_qubits
                }
            }

        except Exception as e:
            raise QuantumError(f"Erreur dans l'algorithme d'interférence: {str(e)}")

    # === MÉTHODES UTILITAIRES ===

    def _interpret_interference_pattern(self, state: str, color_count: int) -> str:
        """Interprète un pattern d'interférence"""
        # Conversion basique du state binaire en suggestion
        binary_value = int(state, 2)
        suggested_color = binary_value % color_count

        patterns = [
            f"Pattern suggère la couleur {suggested_color}",
            f"Interférence constructive autour de la couleur {suggested_color}",
            f"Amplitude maximale pour la couleur {suggested_color}"
        ]

        return random.choice(patterns)

    def _calculate_hint_cost(self, hint_type: str, difficulty) -> int:
        """Calcule le coût en points d'un hint"""
        base_costs = {
            "grover": 50,
            "superposition": 25,
            "entanglement": 35,
            "interference": 30
        }

        base_cost = base_costs.get(hint_type, 25)

        # Multiplicateur selon la difficulté
        difficulty_multipliers = {
            "easy": 0.5,
            "normal": 1.0,
            "hard": 1.5,
            "expert": 2.0
        }

        multiplier = difficulty_multipliers.get(str(difficulty), 1.0)
        return int(base_cost * multiplier)

    async def _validate_quantum_request(
        self,
        db: AsyncSession,
        game_id: UUID,
        player_id: UUID
    ) -> Tuple[Game, GameParticipation]:
        """Valide une requête quantique"""

        # Récupérer la partie
        from app.services.game import game_service
        game = await game_service._get_game_with_participations(db, game_id)
        if not game:
            raise EntityNotFoundError("Partie non trouvée", "Game", game_id)

        # Vérifier que la partie est active
        if not game.is_active:
            raise GameError("La partie n'est pas active")

        # Récupérer la participation
        participation = await game_service._get_participation(db, game_id, player_id)
        if not participation:
            raise EntityNotFoundError("Participation non trouvée")

        return game, participation

    # === MÉTHODES DE DIAGNOSTIC ===

    async def test_quantum_backend(self) -> Dict[str, Any]:
        """Teste le backend quantique"""
        try:
            # Circuit de test simple
            qc = QuantumCircuit(2, 2)
            qc.h(0)
            qc.cx(0, 1)
            qc.measure_all()

            # Exécution
            transpiled_qc = transpile(qc, self.backend)
            job = self.backend.run(transpiled_qc, shots=100)
            result = job.result()
            counts = result.get_counts()

            return {
                "status": "healthy",
                "backend": str(self.backend),
                "test_results": counts,
                "qiskit_version": "2.0.2",
                "available_algorithms": ["grover", "superposition", "entanglement", "interference"]
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "backend": str(self.backend)
            }

    def get_quantum_info(self) -> Dict[str, Any]:
        """Retourne les informations sur les capacités quantiques"""
        return {
            "backend": settings.QISKIT_BACKEND,
            "max_qubits": self.max_qubits,
            "default_shots": self.default_shots,
            "supported_hints": [
                {
                    "type": "grover",
                    "name": "Algorithme de Grover",
                    "description": "Recherche quantique optimisée",
                    "cost": 50
                },
                {
                    "type": "superposition",
                    "name": "Superposition Quantique",
                    "description": "Exploration d'états multiples",
                    "cost": 25
                },
                {
                    "type": "entanglement",
                    "name": "Intrication Quantique",
                    "description": "Révélation de corrélations",
                    "cost": 35
                },
                {
                    "type": "interference",
                    "name": "Interférence Quantique",
                    "description": "Amplification de patterns",
                    "cost": 30
                }
            ]
        }


# Instance globale du service quantique
quantum_service = QuantumService()