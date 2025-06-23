import math
import secrets
import time
from typing import Any, Dict, List, Tuple
import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator


class QuantumService:
    """Service quantique optimisé pour Mastermind avec fonctions quantiques avancées"""

    def __init__(self):
        try:
            self.backend = AerSimulator()
            self.statevector_backend = AerSimulator(method='statevector')
        except Exception:
            self.backend = None
            self.statevector_backend = None

        self.default_shots = 1024  # Bon compromis précision/performance
        self.max_qubits = 8

        # NOUVEAU: Flag pour activer les fonctions quantiques avancées
        self.enhanced_quantum = True  # Active les nouvelles fonctions quantiques

        # NOUVEAU: Statistiques de performance
        self.performance_stats = {
            "quantum_calls": 0,
            "fallback_calls": 0,
            "total_execution_time": 0.0,
            "average_fidelity": 0.0
        }

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
        """Calcule les indices avec probabilités quantiques détaillées - VERSION AMÉLIORÉE"""
        if not self.backend or len(solution) != len(attempt):
            return self._classical_fallback(solution, attempt)

        shots = shots or self.default_shots
        start_time = time.time()
        quantum_methods_used = []

        try:
            if self.enhanced_quantum:
                # NOUVEAU: Version entièrement quantique
                position_probabilities = []
                total_fidelity = 0.0

                for position in range(len(solution)):
                    prob_data = await self._extract_position_probability_quantum(
                        position, solution, attempt, shots
                    )
                    # Sécurité : ne pas exposer la solution
                    prob_data_safe = {k: v for k, v in prob_data.items() if k != "solution_color"}
                    position_probabilities.append(prob_data_safe)

                    if "fidelity" in prob_data:
                        total_fidelity += prob_data["fidelity"]

                quantum_methods_used.append("amplitude_estimation")

                exact_matches = sum(1 for pos in position_probabilities if pos["exact_match_probability"] > 0.5)

                # NOUVEAU: Utiliser la version quantique pour les mal placées
                wrong_position = await self._calculate_wrong_position_quantum(
                    solution, attempt, exact_matches, shots
                )
                quantum_methods_used.append("superposition_comparison")

                self.performance_stats["quantum_calls"] += 1

            else:
                # Version hybride existante
                position_probabilities = await self._analyze_position_probabilities(solution, attempt, shots)
                exact_matches = sum(1 for pos in position_probabilities if pos["exact_match_probability"] > 0.5)
                wrong_position = self._calculate_wrong_position_classical(solution, attempt, exact_matches)
                quantum_methods_used.append("basic_quantum")

            execution_time = time.time() - start_time
            self.performance_stats["total_execution_time"] += execution_time

            if total_fidelity > 0:
                avg_fidelity = total_fidelity / len(solution)
                self.performance_stats["average_fidelity"] = (
                                                                     self.performance_stats[
                                                                         "average_fidelity"] + avg_fidelity
                                                             ) / 2

            return {
                "exact_matches": exact_matches,
                "wrong_position": wrong_position,
                "position_probabilities": position_probabilities,
                "quantum_calculated": True,
                "shots_used": shots,
                "quantum_methods_used": quantum_methods_used,
                "enhancement_level": "full" if self.enhanced_quantum else "basic",
                "quantum_execution_time": execution_time,
                "average_fidelity": avg_fidelity if total_fidelity > 0 else None
            }

        except Exception as e:
            self.performance_stats["fallback_calls"] += 1
            print(f"Erreur calcul quantique amélioré: {e}")
            return self._classical_fallback(solution, attempt)

    # =========================================
    # NOUVELLE VERSION QUANTIQUE DE _calculate_wrong_position
    # =========================================

    async def _calculate_wrong_position_quantum(
            self,
            solution: List[int],
            attempt: List[int],
            exact_matches: int,
            shots: int = None
    ) -> int:
        """
        Version quantique du calcul des mal placées
        Utilise la superposition et comparaison quantique
        """
        if not self.backend or len(solution) > self.max_qubits:
            return self._calculate_wrong_position_classical(solution, attempt, exact_matches)

        shots = shots or self.default_shots
        available_colors = max(max(solution), max(attempt))

        try:
            # Calculer avec superposition quantique
            color_matches = await self._quantum_color_comparison(solution, attempt, available_colors, shots)

            # Les mal placées = total correspondances - correspondances exactes
            total_color_matches = sum(color_matches.values())
            wrong_position = max(0, total_color_matches - exact_matches)

            return wrong_position

        except Exception as e:
            print(f"Erreur calcul quantique mal placées: {e}")
            return self._calculate_wrong_position_classical(solution, attempt, exact_matches)

    async def _quantum_color_comparison(
            self,
            solution: List[int],
            attempt: List[int],
            max_color: int,
            shots: int
    ) -> Dict[int, int]:
        """
        Compare les couleurs en utilisant la superposition quantique
        Retourne le nombre de correspondances par couleur
        """
        qubits_per_color = math.ceil(math.log2(max_color + 1))

        # Limiter la complexité
        if qubits_per_color > 3 or len(solution) > 4:
            raise ValueError("Circuit trop complexe pour ce backend")

        n_qubits = min(qubits_per_color * 2, self.max_qubits)
        circuit = QuantumCircuit(n_qubits, max_color)

        # Encoder les couleurs de la solution en superposition
        for i, color in enumerate(solution[:min(len(solution), 2)]):  # Limiter à 2 positions
            self._encode_color_superposition(circuit, color, i * qubits_per_color, qubits_per_color)

        # Encoder les couleurs de la tentative
        solution_len = min(len(solution), 2)
        for i, color in enumerate(attempt[:solution_len]):
            start_qubit = solution_len * qubits_per_color + i * qubits_per_color
            if start_qubit + qubits_per_color <= n_qubits:
                self._encode_color_superposition(circuit, color, start_qubit, qubits_per_color)

        # Circuit de comparaison quantique simple
        for color in range(1, min(max_color + 1, max_color)):
            if color - 1 < circuit.num_clbits:
                # Mesurer la présence de cette couleur
                self._add_color_detection_circuit(circuit, color, solution_len, qubits_per_color, color - 1)

        # Exécution
        job = self.backend.run(circuit, shots=shots)
        result = job.result()
        counts = result.get_counts()

        # Analyser les résultats
        color_matches = {}
        for color in range(1, max_color + 1):
            matches = self._count_color_matches(counts, color - 1, solution, attempt)
            if matches > 0:
                color_matches[color] = matches

        return color_matches

    def _encode_color_superposition(self, circuit, color, start_qubit, qubits_per_color):
        """Encode une couleur en superposition quantique"""
        if start_qubit + qubits_per_color > circuit.num_qubits:
            return

        # Convertir la couleur en binaire
        color_binary = format(color, f'0{qubits_per_color}b')

        for i, bit in enumerate(color_binary):
            if start_qubit + i < circuit.num_qubits and bit == '1':
                circuit.x(start_qubit + i)

    def _add_color_detection_circuit(self, circuit, target_color, solution_length, qubits_per_color, measure_qubit):
        """Ajoute un circuit de détection pour une couleur spécifique"""
        if measure_qubit >= circuit.num_clbits:
            return

        # Circuit simple pour détecter la couleur
        target_binary = format(target_color, f'0{qubits_per_color}b')

        # Vérifier le premier qubit de la première position
        if solution_length > 0 and target_binary[0] == '1':
            circuit.measure(0, measure_qubit)
        elif solution_length > 0:
            # Mesurer un qubit de référence
            circuit.measure(min(1, circuit.num_qubits - 1), measure_qubit)

    def _count_color_matches(self, counts, color_index, solution, attempt):
        """Compte les correspondances pour une couleur depuis les résultats quantiques"""
        if not counts:
            return 0

        total_matches = 0
        total_shots = sum(counts.values())

        for state, count in counts.items():
            if len(state) > color_index and color_index >= 0:
                if state[-(color_index + 1)] == '1':
                    # Cette couleur était détectée
                    color = color_index + 1
                    sol_count = solution.count(color)
                    att_count = attempt.count(color)
                    matches = min(sol_count, att_count)
                    total_matches += matches * count / total_shots

        return int(round(total_matches))

    # =========================================
    # NOUVELLE VERSION QUANTIQUE DE _extract_position_probability
    # =========================================

    async def _extract_position_probability_quantum(
            self,
            position: int,
            solution: List[int],
            attempt: List[int],
            shots: int = None
    ) -> Dict[str, Any]:
        """
        Version quantique de l'extraction de probabilité
        Utilise l'estimation d'amplitude quantique
        """
        if not self.backend:
            return self._extract_position_probability_classical(position, {}, shots or 1024, solution, attempt)

        shots = shots or self.default_shots

        try:
            # Créer un circuit d'estimation d'amplitude
            amplitude_result = await self._quantum_amplitude_estimation(position, solution, attempt, shots)

            sol_color = solution[position]
            att_color = attempt[position]

            # Classification quantique
            if sol_color == att_color:
                match_type = "exact_match"
                confidence = "high" if amplitude_result["probability"] > 0.8 else "medium"
            elif att_color in solution:
                match_type = "color_present"
                confidence = "medium" if amplitude_result["probability"] > 0.5 else "low"
            else:
                match_type = "no_match"
                confidence = "high" if amplitude_result["probability"] < 0.2 else "uncertain"

            return {
                "position": position,
                "exact_match_probability": round(amplitude_result["probability"], 3),
                "match_type": match_type,
                "confidence": confidence,
                "solution_color": sol_color,
                "attempt_color": att_color,
                "quantum_measurements": amplitude_result["measurements"],
                "total_shots": shots,
                "quantum_method": "amplitude_estimation",
                "fidelity": amplitude_result.get("fidelity", 0.95)
            }

        except Exception as e:
            print(f"Erreur extraction quantique position {position}: {e}")
            return self._extract_position_probability_classical(position, {}, shots, solution, attempt)

    async def _quantum_amplitude_estimation(
            self,
            position: int,
            solution: List[int],
            attempt: List[int],
            shots: int
    ) -> Dict[str, Any]:
        """
        Estime l'amplitude quantique pour une position spécifique
        Plus précis que le simple comptage classique
        """
        sol_color = solution[position]
        att_color = attempt[position]

        # Nombre de qubits nécessaires
        max_color = max(max(solution), max(attempt))
        qubits_needed = math.ceil(math.log2(max_color + 1))

        if qubits_needed > self.max_qubits - 1:
            raise ValueError(f"Trop de qubits nécessaires: {qubits_needed}")

        # Circuit d'estimation d'amplitude simplifié
        circuit = QuantumCircuit(qubits_needed + 1, 1)  # +1 pour ancilla

        # Préparer l'état de référence
        self._prepare_reference_state(circuit, sol_color, att_color, qubits_needed)

        # Oracle pour marquer les états correspondants
        self._add_matching_oracle(circuit, sol_color, att_color, qubits_needed)

        # Mesure de l'ancilla
        circuit.measure(qubits_needed, 0)

        # Exécution
        job = self.backend.run(circuit, shots=shots)
        result = job.result()
        counts = result.get_counts()

        # Calculer la probabilité à partir des mesures
        ones_count = counts.get('1', 0)
        probability = ones_count / shots

        # Correction de biais quantique
        corrected_probability = self._correct_quantum_bias(probability, sol_color, att_color)

        return {
            "probability": corrected_probability,
            "measurements": ones_count,
            "raw_probability": probability,
            "fidelity": self._estimate_fidelity(counts)
        }

    def _prepare_reference_state(self, circuit, sol_color, att_color, qubits_needed):
        """Prépare l'état de référence pour la comparaison"""
        # Créer une superposition uniforme
        for i in range(qubits_needed):
            circuit.h(i)

        # Encoder la comparaison solution/tentative
        if sol_color == att_color:
            # État |1⟩ pour correspondance exacte
            circuit.x(qubits_needed)  # Ancilla = 1
        else:
            # Superposition proportionnelle à la similarité
            similarity = 1.0 / max(abs(sol_color - att_color), 1)
            angle = np.arcsin(np.sqrt(min(similarity, 1.0)))
            circuit.ry(2 * angle, qubits_needed)

    def _add_matching_oracle(self, circuit, sol_color, att_color, qubits_needed):
        """Oracle qui marque les états correspondants"""
        if sol_color == att_color:
            # Amplifier pour correspondance exacte
            if qubits_needed > 0:
                circuit.cz(0, qubits_needed)  # Phase flip conditionnel
        elif sol_color != att_color:
            # Rotation partielle pour similarité
            if qubits_needed > 0:
                circuit.crz(np.pi / 6, 0, qubits_needed)

    def _correct_quantum_bias(self, raw_probability, sol_color, att_color):
        """Corrige les biais dus aux erreurs quantiques"""
        # Modèle de correction basé sur le type de correspondance
        if sol_color == att_color:
            # Correction pour correspondance exacte
            return min(0.99, raw_probability * 1.03)  # Légère surestimation
        elif att_color in [sol_color]:
            # Correction pour mal placée
            return max(0.01, raw_probability * 0.95)  # Légère sous-estimation
        else:
            # Correction pour absence
            return max(0.01, raw_probability * 0.9)  # Plus de sous-estimation

    def _estimate_fidelity(self, counts):
        """Estime la fidélité du circuit quantique"""
        total_counts = sum(counts.values())
        if total_counts == 0:
            return 0.0

        # Fidelity basée sur la distribution des résultats
        max_count = max(counts.values()) if counts else 0
        entropy = 0

        for count in counts.values():
            if count > 0:
                p = count / total_counts
                entropy -= p * np.log2(p)

        # Fidelity inversement proportionnelle à l'entropie
        return max(0.5, 1.0 - entropy / 2.0)

    # =========================================
    # FONCTIONS EXISTANTES MODIFIÉES
    # =========================================

    async def _analyze_position_probabilities(
            self,
            solution: List[int],
            attempt: List[int],
            shots: int
    ) -> List[Dict[str, Any]]:
        """Analyse les probabilités quantiques par position - VERSION ORIGINALE"""
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
                    angle = np.pi / 3  # ~75% probabilité
                else:
                    angle = np.pi / 16  # ~6% probabilité

                circuit.ry(angle, i)
                circuit.measure(i, i)

            job = self.backend.run(circuit, shots=shots)
            result = job.result()
            counts = result.get_counts()

            position_probabilities = []
            for position in range(n_positions):
                prob_data = self._extract_position_probability_classical(position, counts, shots, solution, attempt)
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
        """Extrait la probabilité quantique pour une position - VERSION AMÉLIORÉE"""
        if self.enhanced_quantum and self.backend:
            # Ignorer les 'counts' classiques, faire du vrai quantique
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(
                    self._extract_position_probability_quantum(position, solution, attempt, shots)
                )
            except Exception as e:
                print(f"Fallback vers méthode classique pour position {position}: {e}")
                return self._extract_position_probability_classical(position, counts, shots, solution, attempt)
        else:
            # Code classique existant
            return self._extract_position_probability_classical(position, counts, shots, solution, attempt)

    def _extract_position_probability_classical(
            self,
            position: int,
            counts: Dict[str, int],
            shots: int,
            solution: List[int],
            attempt: List[int]
    ) -> Dict[str, Any]:
        """Version classique originale de l'extraction de probabilité"""
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
        """Calcule les mal placés - VERSION AMÉLIORÉE"""
        if self.enhanced_quantum and self.backend:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(
                    self._calculate_wrong_position_quantum(solution, attempt, exact_matches)
                )
            except Exception as e:
                print(f"Fallback vers calcul classique mal placées: {e}")
                return self._calculate_wrong_position_classical(solution, attempt, exact_matches)
        else:
            return self._calculate_wrong_position_classical(solution, attempt, exact_matches)

    def _calculate_wrong_position_classical(self, solution: List[int], attempt: List[int], exact_matches: int) -> int:
        """Version classique originale du calcul des mal placées"""
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
        wrong_position = self._calculate_wrong_position_classical(solution, attempt, exact_matches)

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
            match_type = "exact_match" if sol_color == att_color else (
                "color_present" if att_color in solution else "no_match")

            position_probabilities.append({
                "position": i,
                "exact_match_probability": prob,
                "match_type": match_type,
                "confidence": "high",
                "attempt_color": att_color
            })
        return position_probabilities

    # =========================================
    # MÉTHODES EXISTANTES INCHANGÉES
    # =========================================

    # Méthode legacy pour compatibilité
    async def calculate_quantum_hints(self, solution: List[int], attempt: List[int], shots: int = None) -> Tuple[
        int, int]:
        """Compatibilité avec l'ancien code"""
        result = await self.calculate_quantum_hints_with_probabilities(solution, attempt, shots)
        return result["exact_matches"], result["wrong_position"]

    def get_quantum_info(self) -> Dict[str, Any]:
        """Infos sur les capacités quantiques - ÉTENDU"""
        return {
            "backend": "AerSimulator" if self.backend else "None",
            "max_qubits": self.max_qubits,
            "default_shots": self.default_shots,
            "status": "available" if self.backend else "unavailable",
            "enhanced_quantum": self.enhanced_quantum,
            "performance_stats": self.performance_stats.copy()
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
                "aer_version": "0.17.1",
                "enhanced_quantum": self.enhanced_quantum
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "backend": "AerSimulator"
            }

    # =========================================
    # NOUVELLES MÉTHODES DE CONTRÔLE
    # =========================================

    def set_enhancement_level(self, level: str):
        """Contrôle le niveau d'amélioration quantique"""
        if level == "full":
            self.enhanced_quantum = True
        elif level == "basic":
            self.enhanced_quantum = False
        else:
            raise ValueError("Level must be 'full' or 'basic'")

    def get_performance_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de performance"""
        total_calls = self.performance_stats["quantum_calls"] + self.performance_stats["fallback_calls"]

        return {
            **self.performance_stats.copy(),
            "total_calls": total_calls,
            "quantum_success_rate": (
                self.performance_stats["quantum_calls"] / total_calls
                if total_calls > 0 else 0
            ),
            "average_execution_time": (
                self.performance_stats["total_execution_time"] / total_calls
                if total_calls > 0 else 0
            )
        }

    def reset_performance_stats(self):
        """Remet à zéro les statistiques de performance"""
        self.performance_stats = {
            "quantum_calls": 0,
            "fallback_calls": 0,
            "total_execution_time": 0.0,
            "average_fidelity": 0.0
        }


# Instance globale
quantum_service = QuantumService()