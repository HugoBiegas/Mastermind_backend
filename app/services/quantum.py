"""
Service quantique pour Quantum Mastermind
Implémentation des algorithmes quantiques avec Qiskit
"""
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
import numpy as np
import random
import math

try:
    from qiskit import QuantumCircuit, execute, Aer, transpile
    from qiskit.quantum_info import Statevector
    from qiskit.extensions import UnitaryGate
    from qiskit.circuit.library import GroverOperator

    QISKIT_AVAILABLE = True
except ImportError:
    QISKIT_AVAILABLE = False
    print("Qiskit non disponible - Utilisation du simulateur de base")

from app.core.config import quantum_config
from app.schemas.quantum import (
    QuantumCircuit as QuantumCircuitSchema,
    QuantumMeasurement, GroverSearch, QuantumSuperposition,
    QuantumEntanglement, QuantumResult, MeasurementResult,
    GroverResult, QuantumMastermindSolution, QuantumHint
)
from app.utils.exceptions import QuantumError


class QuantumService:
    """Service pour les opérations quantiques"""

    def __init__(self):
        self.backend_name = quantum_config.QISKIT_BACKEND if QISKIT_AVAILABLE else 'simulator'
        self.backend = None
        if QISKIT_AVAILABLE:
            self.backend = Aer.get_backend(self.backend_name)

        # Configuration par défaut
        self.default_shots = quantum_config.QUANTUM_SHOTS
        self.max_qubits = quantum_config.MAX_QUBITS

        # Cache des circuits pour optimisation
        self._circuit_cache = {}

    # === MÉTHODES DE CONFIGURATION ===

    def get_backend_info(self) -> Dict[str, Any]:
        """Retourne les informations du backend quantique"""
        if not QISKIT_AVAILABLE:
            return {
                'name': 'Basic Simulator',
                'available': False,
                'max_qubits': 4,
                'simulator': True,
                'error': 'Qiskit non disponible'
            }

        return {
            'name': self.backend.name(),
            'available': True,
            'max_qubits': self.backend.configuration().n_qubits,
            'simulator': self.backend.configuration().simulator,
            'basis_gates': self.backend.configuration().basis_gates,
            'coupling_map': getattr(self.backend.configuration(), 'coupling_map', None)
        }

    # === GÉNÉRATION DE SOLUTION QUANTIQUE ===

    async def generate_quantum_mastermind_solution(
            self,
            difficulty: str = 'normal',
            seed: Optional[str] = None
    ) -> QuantumMastermindSolution:
        """
        Génère une solution de Mastermind quantique

        Args:
            difficulty: Niveau de difficulté
            seed: Graine pour la reproductibilité

        Returns:
            Solution quantique complète
        """
        if seed:
            random.seed(int(seed, 16) % (2 ** 32))
            np.random.seed(int(seed, 16) % (2 ** 32))

        # Définition des couleurs selon la difficulté
        color_sets = {
            'easy': ['red', 'blue', 'green', 'yellow'],
            'normal': ['red', 'blue', 'green', 'yellow', 'orange', 'purple'],
            'hard': ['red', 'blue', 'green', 'yellow', 'orange', 'purple', 'black'],
            'expert': ['red', 'blue', 'green', 'yellow', 'orange', 'purple', 'black', 'white']
        }

        colors = color_sets.get(difficulty, color_sets['normal'])

        # Génération de la solution classique
        classical_solution = [random.choice(colors) for _ in range(4)]

        # Génération de l'encodage quantique
        quantum_encoding = await self._create_quantum_encoding(classical_solution, colors)

        # Création de la carte d'intrication
        entanglement_map = await self._create_entanglement_map(difficulty)

        # États de superposition par position
        superposition_states = await self._create_superposition_states(
            classical_solution, colors, difficulty
        )

        return QuantumMastermindSolution(
            classical_solution=classical_solution,
            quantum_encoding=quantum_encoding,
            entanglement_map=entanglement_map,
            superposition_states=superposition_states,
            generation_seed=seed or random.randint(0, 2 ** 32 - 1)
        )

    # === ALGORITHMES QUANTIQUES ===

    async def execute_grover_search(
            self,
            search_params: GroverSearch
    ) -> GroverResult:
        """
        Exécute l'algorithme de Grover pour la recherche

        Args:
            search_params: Paramètres de recherche

        Returns:
            Résultats de la recherche de Grover
        """
        start_time = time.time()

        try:
            if not QISKIT_AVAILABLE:
                return await self._simulate_grover_search(search_params)

            # Calcul du nombre optimal d'itérations
            n_items = search_params.database_size
            n_targets = len(search_params.target_items)
            optimal_iterations = int(np.pi * np.sqrt(n_items / n_targets) / 4)

            iterations = search_params.iterations or optimal_iterations
            n_qubits = int(np.log2(n_items))

            # Création du circuit de Grover
            qc = QuantumCircuit(n_qubits, n_qubits)

            # Initialisation en superposition
            qc.h(range(n_qubits))

            # Opérateur Oracle pour marquer les éléments cibles
            oracle = self._create_oracle(search_params.target_items, n_qubits)

            # Opérateur de diffusion
            diffuser = self._create_diffuser(n_qubits)

            # Itérations de Grover
            for _ in range(iterations):
                qc.append(oracle, range(n_qubits))
                qc.append(diffuser, range(n_qubits))

            # Mesure
            qc.measure_all()

            # Exécution
            job = execute(qc, self.backend, shots=self.default_shots)
            result = job.result()
            counts = result.get_counts(qc)

            # Analyse des résultats
            found_items = []
            total_success_prob = 0

            for bitstring, count in counts.items():
                item_index = int(bitstring, 2)
                probability = count / self.default_shots

                if item_index in search_params.target_items:
                    found_items.append(item_index)
                    total_success_prob += probability

            execution_time = time.time() - start_time

            return GroverResult(
                found_items=found_items,
                success_probability=total_success_prob,
                iterations_performed=iterations,
                optimal_iterations=optimal_iterations,
                amplification_factor=total_success_prob / (n_targets / n_items),
                execution_details={
                    'circuit_depth': qc.depth(),
                    'execution_time': execution_time,
                    'shots_used': self.default_shots,
                    'measurement_counts': counts
                }
            )

        except Exception as e:
            raise QuantumError(f"Erreur lors de l'exécution de Grover: {str(e)}")

    async def create_quantum_superposition(
            self,
            superposition_params: QuantumSuperposition
    ) -> QuantumResult:
        """
        Crée un état de superposition quantique

        Args:
            superposition_params: Paramètres de superposition

        Returns:
            Résultat de l'opération quantique
        """
        start_time = time.time()

        try:
            if not QISKIT_AVAILABLE:
                return await self._simulate_superposition(superposition_params)

            n_qubits = len(superposition_params.qubits)
            qc = QuantumCircuit(n_qubits, n_qubits)

            # Application des portes Hadamard pour la superposition
            for i, qubit in enumerate(superposition_params.qubits):
                qc.h(i)

            # Application des poids si spécifiés
            if superposition_params.weights:
                # Normalisation des poids en angles de rotation
                weights = superposition_params.weights
                for i, weight in enumerate(weights):
                    if weight != 0.5:  # Éviter les rotations inutiles
                        angle = 2 * np.arccos(np.sqrt(weight))
                        qc.ry(angle, i)

            # Mesure
            qc.measure_all()

            # Exécution
            job = execute(qc, self.backend, shots=self.default_shots)
            result = job.result()
            counts = result.get_counts(qc)

            # Calcul des probabilités
            probabilities = {
                state: count / self.default_shots
                for state, count in counts.items()
            }

            execution_time = time.time() - start_time

            return QuantumResult(
                operation_type='superposition',
                success=True,
                result_data={
                    'superposition_created': True,
                    'qubits_used': n_qubits,
                    'uniform_superposition': superposition_params.weights is None
                },
                measurements=counts,
                probabilities=probabilities,
                execution_time=execution_time,
                shots_used=self.default_shots
            )

        except Exception as e:
            raise QuantumError(f"Erreur lors de la création de superposition: {str(e)}")

    async def create_quantum_entanglement(
            self,
            entanglement_params: QuantumEntanglement
    ) -> QuantumResult:
        """
        Crée des états intriqués

        Args:
            entanglement_params: Paramètres d'intrication

        Returns:
            Résultat de l'opération quantique
        """
        start_time = time.time()

        try:
            if not QISKIT_AVAILABLE:
                return await self._simulate_entanglement(entanglement_params)

            # Calcul du nombre total de qubits
            all_qubits = set()
            for pair in entanglement_params.qubit_pairs:
                all_qubits.update(pair)

            n_qubits = len(all_qubits)
            qc = QuantumCircuit(n_qubits, n_qubits)

            # Création des états intriqués selon le type
            if entanglement_params.entanglement_type == 'bell':
                for pair in entanglement_params.qubit_pairs:
                    qc.h(pair[0])
                    qc.cx(pair[0], pair[1])

            elif entanglement_params.entanglement_type == 'ghz':
                # État GHZ pour plusieurs qubits
                qubits = list(all_qubits)
                qc.h(qubits[0])
                for i in range(1, len(qubits)):
                    qc.cx(qubits[0], qubits[i])

            # Mesure
            qc.measure_all()

            # Exécution
            job = execute(qc, self.backend, shots=self.default_shots)
            result = job.result()
            counts = result.get_counts(qc)

            # Analyse de l'intrication
            entanglement_fidelity = self._calculate_entanglement_fidelity(
                counts, entanglement_params.entanglement_type
            )

            execution_time = time.time() - start_time

            return QuantumResult(
                operation_type='entanglement',
                success=True,
                result_data={
                    'entanglement_type': entanglement_params.entanglement_type,
                    'qubit_pairs': entanglement_params.qubit_pairs,
                    'entanglement_fidelity': entanglement_fidelity
                },
                measurements=counts,
                probabilities={
                    state: count / self.default_shots
                    for state, count in counts.items()
                },
                execution_time=execution_time,
                shots_used=self.default_shots
            )

        except Exception as e:
            raise QuantumError(f"Erreur lors de la création d'intrication: {str(e)}")

    async def perform_quantum_measurement(
            self,
            measurement_params: QuantumMeasurement
    ) -> MeasurementResult:
        """
        Effectue une mesure quantique

        Args:
            measurement_params: Paramètres de mesure

        Returns:
            Résultat de la mesure
        """
        start_time = time.time()

        try:
            if not QISKIT_AVAILABLE:
                return await self._simulate_measurement(measurement_params)

            circuit = measurement_params.circuit
            qubit_index = measurement_params.qubit_index
            basis = measurement_params.basis

            # Conversion du schéma en circuit Qiskit
            qc = self._schema_to_qiskit_circuit(circuit)

            # Application de la base de mesure
            if basis == 'x':
                qc.h(qubit_index)
            elif basis == 'y':
                qc.sdg(qubit_index)
                qc.h(qubit_index)

            # Mesure du qubit spécifique
            qc.measure(qubit_index, qubit_index)

            # Exécution
            job = execute(qc, self.backend, shots=self.default_shots)
            result = job.result()
            counts = result.get_counts(qc)

            # Analyse des résultats
            measured_0 = counts.get('0', 0)
            measured_1 = counts.get('1', 0)

            probability_0 = measured_0 / self.default_shots
            probability_1 = measured_1 / self.default_shots

            # Détermination du résultat de mesure
            measured_value = 1 if probability_1 > probability_0 else 0
            probability = probability_1 if measured_value == 1 else probability_0

            execution_time = time.time() - start_time

            return MeasurementResult(
                measured_value=measured_value,
                probability=probability,
                measurement_basis=basis,
                collapse_occurred=True,
                state_before={'superposition': True},
                state_after={'classical': measured_value}
            )

        except Exception as e:
            raise QuantumError(f"Erreur lors de la mesure quantique: {str(e)}")

    # === MÉTHODES POUR LE MASTERMIND QUANTIQUE ===

    async def analyze_quantum_attempt(
            self,
            solution: QuantumMastermindSolution,
            attempt: List[str]
    ) -> Dict[str, Any]:
        """
        Analyse une tentative avec les données quantiques

        Args:
            solution: Solution quantique
            attempt: Tentative du joueur

        Returns:
            Analyse quantique de la tentative
        """
        try:
            # Calcul des probabilités pour chaque position
            position_probabilities = {}

            for pos in range(4):
                attempted_color = attempt[pos]
                correct_color = solution.classical_solution[pos]

                # Probabilité basée sur la superposition
                if pos in solution.superposition_states:
                    colors_in_superposition = solution.superposition_states[pos]
                    if attempted_color in colors_in_superposition:
                        prob = 1.0 / len(colors_in_superposition)
                    else:
                        prob = 0.0
                else:
                    prob = 1.0 if attempted_color == correct_color else 0.0

                position_probabilities[pos] = prob

            # Calcul de l'avantage quantique
            quantum_advantage = sum(position_probabilities.values()) / 4

            # Suggestions d'amélioration
            suggestions = []
            for pos, prob in position_probabilities.items():
                if prob < 0.5:
                    if pos in solution.superposition_states:
                        suggestions.append(
                            f"Position {pos}: Considérez les couleurs en superposition"
                        )
                    else:
                        suggestions.append(
                            f"Position {pos}: Mesure quantique recommandée"
                        )

            return {
                'position_probabilities': position_probabilities,
                'quantum_advantage': quantum_advantage,
                'suggestions': suggestions,
                'entanglement_detected': bool(solution.entanglement_map),
                'superposition_positions': list(solution.superposition_states.keys())
            }

        except Exception as e:
            raise QuantumError(f"Erreur lors de l'analyse quantique: {str(e)}")

    async def generate_quantum_hint(
            self,
            solution: QuantumMastermindSolution,
            hint_type: str,
            position: Optional[int] = None
    ) -> QuantumHint:
        """
        Génère un indice quantique

        Args:
            solution: Solution quantique
            hint_type: Type d'indice
            position: Position pour l'indice

        Returns:
            Indice quantique
        """
        try:
            if hint_type == 'grover' and position is not None:
                # Utilise Grover pour trouver la couleur
                colors = ['red', 'blue', 'green', 'yellow', 'orange', 'purple']
                target_color = solution.classical_solution[position]
                target_index = colors.index(target_color)

                grover_params = GroverSearch(
                    database_size=len(colors),
                    target_items=[target_index]
                )

                grover_result = await self.execute_grover_search(grover_params)

                confidence = grover_result.success_probability

                return QuantumHint(
                    hint_type=hint_type,
                    position=position,
                    revealed_info={'color': target_color, 'method': 'grover'},
                    confidence=confidence,
                    quantum_cost=quantum_config.GROVER_HINT_POINTS
                )

            elif hint_type == 'measurement':
                # Mesure quantique directe
                if position is None:
                    position = random.randint(0, 3)

                revealed_color = solution.classical_solution[position]
                confidence = 0.9  # Mesure directe haute confiance

                return QuantumHint(
                    hint_type=hint_type,
                    position=position,
                    revealed_info={'color': revealed_color, 'method': 'measurement'},
                    confidence=confidence,
                    quantum_cost=quantum_config.MEASUREMENT_COST
                )

            elif hint_type == 'superposition':
                # Révèle les états de superposition
                pos = position or random.choice(list(solution.superposition_states.keys()))
                superposition_colors = solution.superposition_states.get(pos, [])

                return QuantumHint(
                    hint_type=hint_type,
                    position=pos,
                    revealed_info={'possible_colors': superposition_colors},
                    confidence=0.8,
                    quantum_cost=quantum_config.SUPERPOSITION_POINTS
                )

            else:
                raise QuantumError(f"Type d'indice non supporté: {hint_type}")

        except Exception as e:
            raise QuantumError(f"Erreur lors de la génération d'indice: {str(e)}")

    # === MÉTHODES PRIVÉES ===

    async def _create_quantum_encoding(
            self,
            solution: List[str],
            available_colors: List[str]
    ) -> Dict[str, Any]:
        """Crée l'encodage quantique de la solution"""
        # Encodage des couleurs en qubits
        color_to_qubit = {color: i for i, color in enumerate(available_colors)}

        encoding = {
            'color_map': color_to_qubit,
            'position_encodings': {},
            'quantum_gates': []
        }

        for pos, color in enumerate(solution):
            qubit_value = color_to_qubit[color]
            encoding['position_encodings'][pos] = {
                'color': color,
                'qubit_representation': format(qubit_value, '03b'),
                'amplitude': 1.0
            }

        return encoding

    async def _create_entanglement_map(self, difficulty: str) -> Dict[int, List[int]]:
        """Crée la carte d'intrication selon la difficulté"""
        entanglement_map = {}

        if difficulty in ['hard', 'expert']:
            # Intrication entre positions adjacentes
            entanglement_map[0] = [1]
            entanglement_map[2] = [3]

        if difficulty == 'expert':
            # Intrication croisée
            entanglement_map[1] = [2]

        return entanglement_map

    async def _create_superposition_states(
            self,
            solution: List[str],
            available_colors: List[str],
            difficulty: str
    ) -> Dict[int, List[str]]:
        """Crée les états de superposition par position"""
        superposition_states = {}

        # Probabilité de superposition selon la difficulté
        superposition_prob = {
            'easy': 0.1,
            'normal': 0.2,
            'hard': 0.3,
            'expert': 0.4
        }.get(difficulty, 0.2)

        for pos in range(4):
            if random.random() < superposition_prob:
                # Cette position est en superposition
                n_colors = random.randint(2, min(3, len(available_colors)))
                colors_in_superposition = random.sample(available_colors, n_colors)

                # S'assurer que la vraie couleur est dans la superposition
                if solution[pos] not in colors_in_superposition:
                    colors_in_superposition[0] = solution[pos]

                superposition_states[pos] = colors_in_superposition

        return superposition_states

    def _create_oracle(self, target_items: List[int], n_qubits: int):
        """Crée l'opérateur Oracle pour Grover"""
        if not QISKIT_AVAILABLE:
            return None

        oracle_qc = QuantumCircuit(n_qubits)

        for target in target_items:
            # Marquage des états cibles
            target_binary = format(target, f'0{n_qubits}b')

            # Application de X aux qubits qui doivent être 0
            for i, bit in enumerate(target_binary):
                if bit == '0':
                    oracle_qc.x(i)

            # Application de la porte Z multi-contrôlée
            if n_qubits == 1:
                oracle_qc.z(0)
            else:
                oracle_qc.mcz(list(range(n_qubits - 1)), n_qubits - 1)

            # Restauration
            for i, bit in enumerate(target_binary):
                if bit == '0':
                    oracle_qc.x(i)

        return oracle_qc.to_gate()

    def _create_diffuser(self, n_qubits: int):
        """Crée l'opérateur de diffusion pour Grover"""
        if not QISKIT_AVAILABLE:
            return None

        diffuser_qc = QuantumCircuit(n_qubits)

        # 2|s><s| - I
        diffuser_qc.h(range(n_qubits))
        diffuser_qc.x(range(n_qubits))

        if n_qubits == 1:
            diffuser_qc.z(0)
        else:
            diffuser_qc.mcz(list(range(n_qubits - 1)), n_qubits - 1)

        diffuser_qc.x(range(n_qubits))
        diffuser_qc.h(range(n_qubits))

        return diffuser_qc.to_gate()

    def _calculate_entanglement_fidelity(
            self,
            counts: Dict[str, int],
            entanglement_type: str
    ) -> float:
        """Calcule la fidélité de l'intrication"""
        total_shots = sum(counts.values())

        if entanglement_type == 'bell':
            # Pour un état de Bell, on s'attend à voir seulement |00> et |11>
            bell_counts = counts.get('00', 0) + counts.get('11', 0)
            return bell_counts / total_shots

        return 0.5  # Valeur par défaut

    def _schema_to_qiskit_circuit(self, circuit_schema) -> 'QuantumCircuit':
        """Convertit un schéma de circuit en circuit Qiskit"""
        if not QISKIT_AVAILABLE:
            raise QuantumError("Qiskit non disponible")

        qc = QuantumCircuit(circuit_schema.num_qubits, circuit_schema.num_qubits)

        for gate in circuit_schema.gates:
            gate_type = gate['type']
            qubits = gate['qubits']

            if gate_type == 'H':
                qc.h(qubits[0])
            elif gate_type == 'X':
                qc.x(qubits[0])
            elif gate_type == 'CNOT':
                qc.cx(qubits[0], qubits[1])
            # Ajouter d'autres portes selon les besoins

        return qc

    # === MÉTHODES DE SIMULATION (FALLBACK) ===

    async def _simulate_grover_search(self, search_params: GroverSearch) -> GroverResult:
        """Simulation basique de Grover sans Qiskit"""
        # Simulation probabiliste
        target_prob = 0.8  # Probabilité de succès simulée

        return GroverResult(
            found_items=search_params.target_items,
            success_probability=target_prob,
            iterations_performed=3,
            optimal_iterations=3,
            amplification_factor=target_prob / (len(search_params.target_items) / search_params.database_size),
            execution_details={'simulated': True}
        )

    async def _simulate_superposition(self, params: QuantumSuperposition) -> QuantumResult:
        """Simulation de superposition"""
        return QuantumResult(
            operation_type='superposition',
            success=True,
            result_data={'simulated': True},
            execution_time=0.1,
            shots_used=1024
        )

    async def _simulate_entanglement(self, params: QuantumEntanglement) -> QuantumResult:
        """Simulation d'intrication"""
        return QuantumResult(
            operation_type='entanglement',
            success=True,
            result_data={'simulated': True},
            execution_time=0.1,
            shots_used=1024
        )

    async def _simulate_measurement(self, params: QuantumMeasurement) -> MeasurementResult:
        """Simulation de mesure"""
        measured_value = random.randint(0, 1)
        return MeasurementResult(
            measured_value=measured_value,
            probability=0.5,
            measurement_basis=params.basis,
            collapse_occurred=True
        )


# Instance globale du service
quantum_service = QuantumService()