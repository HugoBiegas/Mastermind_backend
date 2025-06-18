import math
import secrets
from typing import Any, Dict, List, Tuple
import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator


class QuantumService:
    """Service quantique optimisé pour Mastermind"""

    def __init__(self):
        try:
            self.backend = AerSimulator()
        except Exception:
            self.backend = None

        self.default_shots = 1024  # Bon compromis précision/performance
        self.max_qubits = 8

    async def generate_quantum_solution(
        self,
        combination_length: int = 4,
        available_colors: int = 6,
        shots: int = None
    ) -> List[int]:
        """Génère une solution quantique avec superposition"""
        if not self.backend:
            return [secrets.randbelow(available_colors) + 1 for _ in range(combination_length)]

        shots = shots or self.default_shots
        solution = []

        try:
            qubits_per_color = math.ceil(math.log2(available_colors))

            for _ in range(combination_length):
                circuit = QuantumCircuit(qubits_per_color, qubits_per_color)

                # Superposition
                for qubit in range(qubits_per_color):
                    circuit.h(qubit)

                circuit.measure_all()

                job = self.backend.run(circuit, shots=shots)
                result = job.result()
                counts = result.get_counts()

                # Résultat le plus fréquent
                max_count = max(counts.values())
                most_frequent = [state for state, count in counts.items() if count == max_count]
                chosen_state = secrets.choice(most_frequent)

                color_value = int(chosen_state, 2) % available_colors + 1
                solution.append(color_value)

        except Exception:
            return [secrets.randbelow(available_colors) + 1 for _ in range(combination_length)]

        return solution

    async def calculate_quantum_hints_with_probabilities(
        self,
        solution: List[int],
        attempt: List[int],
        shots: int = None
    ) -> Dict[str, Any]:
        """Calcule les indices avec probabilités quantiques détaillées"""
        if not self.backend or len(solution) != len(attempt):
            return self._classical_fallback(solution, attempt)

        shots = shots or self.default_shots

        try:
            position_probabilities = await self._analyze_position_probabilities(solution, attempt, shots)
            exact_matches = sum(1 for pos in position_probabilities if pos["exact_match_probability"] > 0.5)
            wrong_position = self._calculate_wrong_position(solution, attempt, exact_matches)

            return {
                "exact_matches": exact_matches,
                "wrong_position": wrong_position,
                "position_probabilities": position_probabilities,
                "quantum_calculated": True,
                "shots_used": shots
            }

        except Exception:
            return self._classical_fallback(solution, attempt)

    async def _analyze_position_probabilities(
        self,
        solution: List[int],
        attempt: List[int],
        shots: int
    ) -> List[Dict[str, Any]]:
        """Analyse les probabilités quantiques par position"""
        if len(solution) > self.max_qubits or not self.backend:
            return self._classical_position_probabilities(solution, attempt)

        try:
            n_positions = len(solution)
            circuit = QuantumCircuit(n_positions, n_positions)

            # Encoder chaque position selon la correspondance
            for i, (sol_color, att_color) in enumerate(zip(solution, attempt)):
                if sol_color == att_color:
                    angle = 7 * np.pi / 8  # ~97% probabilité
                elif att_color in solution:
                    angle = np.pi / 3      # ~75% probabilité
                else:
                    angle = np.pi / 16     # ~6% probabilité

                circuit.ry(angle, i)
                circuit.measure(i, i)

            job = self.backend.run(circuit, shots=shots)
            result = job.result()
            counts = result.get_counts()

            position_probabilities = []
            for position in range(n_positions):
                prob_data = self._extract_position_probability(position, counts, shots, solution, attempt)
                # Sécurité : ne pas exposer la solution
                prob_data_safe = {k: v for k, v in prob_data.items() if k != "solution_color"}
                position_probabilities.append(prob_data_safe)

            return position_probabilities

        except Exception:
            return self._classical_position_probabilities(solution, attempt)

    def _extract_position_probability(
        self,
        position: int,
        counts: Dict[str, int],
        shots: int,
        solution: List[int],
        attempt: List[int]
    ) -> Dict[str, Any]:
        """Extrait la probabilité quantique pour une position"""
        total_ones = 0
        total_measurements = 0

        if not counts:
            quantum_probability = 0.0
            total_measurements = shots
        else:
            for state, count in counts.items():
                if len(state) > position:
                    bit_at_position = state[-(position + 1)]
                    if bit_at_position == '1':
                        total_ones += count
                    total_measurements += count

            quantum_probability = total_ones / total_measurements if total_measurements > 0 else 0

        # Classification
        sol_color = solution[position]
        att_color = attempt[position]

        if sol_color == att_color:
            match_type = "exact_match"
            confidence = "high" if quantum_probability > 0.8 else "medium"
        elif att_color in solution:
            match_type = "color_present"
            confidence = "medium" if quantum_probability > 0.5 else "low"
        else:
            match_type = "no_match"
            confidence = "high" if quantum_probability < 0.2 else "uncertain"

        return {
            "position": position,
            "exact_match_probability": round(quantum_probability, 3),
            "match_type": match_type,
            "confidence": confidence,
            "solution_color": sol_color,
            "attempt_color": att_color,
            "quantum_measurements": total_ones,
            "total_shots": total_measurements
        }

    def _calculate_wrong_position(self, solution: List[int], attempt: List[int], exact_matches: int) -> int:
        """Calcule les mal placés (hybride classique-quantique)"""
        solution_counts = {}
        attempt_counts = {}

        for color in solution:
            solution_counts[color] = solution_counts.get(color, 0) + 1
        for color in attempt:
            attempt_counts[color] = attempt_counts.get(color, 0) + 1

        total_matches = 0
        for color in solution_counts:
            if color in attempt_counts:
                total_matches += min(solution_counts[color], attempt_counts[color])

        return max(0, total_matches - exact_matches)

    def _classical_fallback(self, solution: List[int], attempt: List[int]) -> Dict[str, Any]:
        """Fallback classique si quantique indisponible"""
        if len(solution) != len(attempt):
            return {"exact_matches": 0, "wrong_position": 0, "quantum_calculated": False}

        exact_matches = sum(1 for s, a in zip(solution, attempt) if s == a)
        wrong_position = self._calculate_wrong_position(solution, attempt, exact_matches)

        return {
            "exact_matches": exact_matches,
            "wrong_position": wrong_position,
            "position_probabilities": self._classical_position_probabilities(solution, attempt),
            "quantum_calculated": False
        }

    def _classical_position_probabilities(self, solution: List[int], attempt: List[int]) -> List[Dict[str, Any]]:
        """Probabilités déterministes classiques"""
        position_probabilities = []
        for i, (sol_color, att_color) in enumerate(zip(solution, attempt)):
            prob = 1.0 if sol_color == att_color else 0.0
            match_type = "exact_match" if sol_color == att_color else ("color_present" if att_color in solution else "no_match")

            position_probabilities.append({
                "position": i,
                "exact_match_probability": prob,
                "match_type": match_type,
                "confidence": "high",
                "attempt_color": att_color
            })
        return position_probabilities

    # Méthode legacy pour compatibilité
    async def calculate_quantum_hints(self, solution: List[int], attempt: List[int], shots: int = None) -> Tuple[int, int]:
        """Compatibilité avec l'ancien code"""
        result = await self.calculate_quantum_hints_with_probabilities(solution, attempt, shots)
        return result["exact_matches"], result["wrong_position"]

    def get_quantum_info(self) -> Dict[str, Any]:
        """Infos sur les capacités quantiques"""
        return {
            "backend": "AerSimulator" if self.backend else "None",
            "max_qubits": self.max_qubits,
            "default_shots": self.default_shots,
            "status": "available" if self.backend else "unavailable"
        }

    # ========================================
    # DIAGNOSTIC ET TESTS
    # ========================================

    async def test_quantum_backend(self) -> Dict[str, Any]:
        """Teste le backend quantique"""
        try:
            if not self.backend:
                return {
                    "status": "error",
                    "error": "Backend non initialisé",
                    "backend": "none"
                }

            # Circuit de test simple
            qc = QuantumCircuit(2, 2)
            qc.h(0)
            qc.cx(0, 1)
            qc.measure_all()

            job = self.backend.run(qc, shots=100)
            result = job.result()
            counts = result.get_counts()

            return {
                "status": "healthy",
                "backend": "AerSimulator",
                "test_results": counts,
                "qiskit_version": "2.0.2",
                "aer_version": "0.17.1"
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "backend": "AerSimulator"
            }

# Instance globale
quantum_service = QuantumService()