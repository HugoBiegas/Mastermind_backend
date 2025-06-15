"""
Schémas Pydantic pour les fonctionnalités quantiques
Validation et sérialisation des données quantiques
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, validator, ConfigDict


# === ÉNUMÉRATIONS ===

class QuantumHintType(str, Enum):
    """Types de hints quantiques disponibles"""
    GROVER = "grover"                    # Algorithme de Grover
    SUPERPOSITION = "superposition"      # États de superposition
    ENTANGLEMENT = "entanglement"       # Intrication quantique
    INTERFERENCE = "interference"       # Interférence quantique


class QuantumAlgorithm(str, Enum):
    """Algorithmes quantiques supportés"""
    GROVER_SEARCH = "grover_search"
    QUANTUM_FOURIER = "quantum_fourier"
    PHASE_ESTIMATION = "phase_estimation"
    AMPLITUDE_AMPLIFICATION = "amplitude_amplification"
    QUANTUM_WALK = "quantum_walk"


class QuantumGateType(str, Enum):
    """Types de portes quantiques"""
    HADAMARD = "h"
    PAULI_X = "x"
    PAULI_Y = "y"
    PAULI_Z = "z"
    CNOT = "cx"
    ROTATION_X = "rx"
    ROTATION_Y = "ry"
    ROTATION_Z = "rz"
    PHASE = "p"
    CONTROLLED_Z = "cz"


# === SCHÉMAS DE BASE ===

class QuantumState(BaseModel):
    """État quantique"""
    model_config = ConfigDict(from_attributes=True)

    amplitudes: List[complex] = Field(..., description="Amplitudes de l'état quantique")
    n_qubits: int = Field(..., description="Nombre de qubits")
    is_normalized: bool = Field(default=True, description="État normalisé")

    @validator('amplitudes')
    def validate_amplitudes(cls, v):
        """Valide que les amplitudes forment un état quantique valide"""
        if not v:
            raise ValueError("Au moins une amplitude requise")

        # Vérifier la normalisation (optionnel pour la flexibilité)
        total_prob = sum(abs(amp)**2 for amp in v)
        if abs(total_prob - 1.0) > 1e-6:
            # Logger un avertissement mais ne pas rejeter
            pass

        return v


class QuantumCircuit(BaseModel):
    """Circuit quantique"""
    model_config = ConfigDict(from_attributes=True)

    n_qubits: int = Field(..., ge=1, le=50, description="Nombre de qubits")
    n_classical: int = Field(..., ge=0, le=50, description="Nombre de bits classiques")
    gates: List[Dict[str, Any]] = Field(default_factory=list, description="Liste des portes")
    depth: int = Field(default=0, description="Profondeur du circuit")

    @validator('gates')
    def validate_gates(cls, v, values):
        """Valide les portes du circuit"""
        n_qubits = values.get('n_qubits', 0)

        for gate in v:
            if not isinstance(gate, dict):
                raise ValueError("Chaque porte doit être un dictionnaire")

            if 'type' not in gate:
                raise ValueError("Type de porte manquant")

            if 'qubits' in gate:
                qubits = gate['qubits']
                if isinstance(qubits, list):
                    for qubit in qubits:
                        if not (0 <= qubit < n_qubits):
                            raise ValueError(f"Qubit {qubit} hors limites (0-{n_qubits-1})")

        return v


class MeasurementResult(BaseModel):
    """Résultat de mesure quantique"""
    model_config = ConfigDict(from_attributes=True)

    counts: Dict[str, int] = Field(..., description="Comptages des états mesurés")
    shots: int = Field(..., description="Nombre de mesures effectuées")
    most_probable_state: str = Field(..., description="État le plus probable")
    probability_distribution: Dict[str, float] = Field(..., description="Distribution de probabilité")

    @validator('probability_distribution')
    def validate_probabilities(cls, v):
        """Valide que les probabilités somment à 1"""
        total = sum(v.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError("Les probabilités doivent sommer à 1")
        return v


# === SCHÉMAS DE HINTS QUANTIQUES ===

class QuantumHintRequest(BaseModel):
    """Requête de hint quantique"""
    model_config = ConfigDict(from_attributes=True)

    game_id: UUID = Field(..., description="ID de la partie")
    hint_type: QuantumHintType = Field(..., description="Type de hint demandé")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Paramètres additionnels")
    max_cost: Optional[int] = Field(None, description="Coût maximum accepté")


class QuantumHint(BaseModel):
    """Hint quantique généré"""
    model_config = ConfigDict(from_attributes=True)

    hint_type: QuantumHintType = Field(..., description="Type de hint")
    hint_data: Dict[str, Any] = Field(..., description="Données du hint")
    cost_points: int = Field(..., description="Coût en points quantiques")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Niveau de confiance")
    quantum_state: Optional[str] = Field(None, description="État quantique associé")
    measurement_results: Optional[List[Dict[str, Any]]] = Field(None, description="Résultats de mesures")
    description: str = Field(..., description="Description du hint")
    created_at: datetime = Field(default_factory=datetime.now, description="Date de création")


class QuantumHintResponse(BaseModel):
    """Réponse avec hint quantique"""
    model_config = ConfigDict(from_attributes=True)

    hint: QuantumHint = Field(..., description="Hint quantique")
    remaining_points: int = Field(..., description="Points quantiques restants")
    usage_stats: Dict[str, Any] = Field(..., description="Statistiques d'utilisation")


# === SCHÉMAS D'ALGORITHMES ===

class GroverHint(BaseModel):
    """Hint basé sur l'algorithme de Grover"""
    model_config = ConfigDict(from_attributes=True)

    suggested_colors: List[Dict[str, Any]] = Field(..., description="Couleurs suggérées")
    search_space_size: int = Field(..., description="Taille de l'espace de recherche")
    iterations: int = Field(..., description="Nombre d'itérations de Grover")
    oracle_calls: int = Field(..., description="Appels à l'oracle")
    confidence_level: float = Field(..., description="Niveau de confiance")


class SuperpositionHint(BaseModel):
    """Hint basé sur la superposition"""
    model_config = ConfigDict(from_attributes=True)

    position_hints: List[Dict[str, Any]] = Field(..., description="Hints par position")
    superposition_states: List[str] = Field(..., description="États en superposition")
    coherence_time: Optional[float] = Field(None, description="Temps de cohérence")


class EntanglementHint(BaseModel):
    """Hint basé sur l'intrication"""
    model_config = ConfigDict(from_attributes=True)

    correlations: List[Dict[str, Any]] = Field(..., description="Corrélations détectées")
    entangled_pairs: List[Tuple[int, int]] = Field(..., description="Paires intriquées")
    correlation_strength: float = Field(..., description="Force de corrélation")


class InterferenceHint(BaseModel):
    """Hint basé sur l'interférence"""
    model_config = ConfigDict(from_attributes=True)

    patterns: List[Dict[str, Any]] = Field(..., description="Patterns d'interférence")
    constructive_regions: List[str] = Field(..., description="Régions d'interférence constructive")
    destructive_regions: List[str] = Field(..., description="Régions d'interférence destructive")


# === SCHÉMAS DE SIMULATION ===

class QuantumSimulationRequest(BaseModel):
    """Requête de simulation quantique"""
    model_config = ConfigDict(from_attributes=True)

    circuit: QuantumCircuit = Field(..., description="Circuit à simuler")
    shots: int = Field(default=1024, ge=1, le=10000, description="Nombre de mesures")
    backend: str = Field(default="qasm_simulator", description="Backend de simulation")
    optimization_level: int = Field(default=1, ge=0, le=3, description="Niveau d'optimisation")


class QuantumSimulationResult(BaseModel):
    """Résultat de simulation quantique"""
    model_config = ConfigDict(from_attributes=True)

    measurement_results: MeasurementResult = Field(..., description="Résultats de mesure")
    execution_time: float = Field(..., description="Temps d'exécution en secondes")
    backend_used: str = Field(..., description="Backend utilisé")
    transpiled_circuit: Optional[Dict[str, Any]] = Field(None, description="Circuit transpilé")
    quantum_statistics: Dict[str, Any] = Field(..., description="Statistiques quantiques")


# === SCHÉMAS D'ANALYSE ===

class QuantumAdvantageAnalysis(BaseModel):
    """Analyse de l'avantage quantique"""
    model_config = ConfigDict(from_attributes=True)

    classical_complexity: str = Field(..., description="Complexité classique")
    quantum_complexity: str = Field(..., description="Complexité quantique")
    speedup_factor: Optional[float] = Field(None, description="Facteur d'accélération")
    advantage_type: str = Field(..., description="Type d'avantage (polynomial/exponentiel)")
    problem_size: int = Field(..., description="Taille du problème")


class QuantumErrorAnalysis(BaseModel):
    """Analyse des erreurs quantiques"""
    model_config = ConfigDict(from_attributes=True)

    gate_errors: Dict[str, float] = Field(..., description="Erreurs par porte")
    decoherence_time: Optional[float] = Field(None, description="Temps de décohérence")
    fidelity: float = Field(..., ge=0.0, le=1.0, description="Fidélité")
    error_correction_overhead: Optional[float] = Field(None, description="Surcharge de correction d'erreur")


# === SCHÉMAS DE CONFIGURATION ===

class QuantumBackendInfo(BaseModel):
    """Informations sur le backend quantique"""
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Nom du backend")
    provider: str = Field(..., description="Fournisseur")
    max_qubits: int = Field(..., description="Nombre maximum de qubits")
    supported_gates: List[str] = Field(..., description="Portes supportées")
    coupling_map: Optional[List[List[int]]] = Field(None, description="Carte de couplage")
    basis_gates: List[str] = Field(..., description="Portes de base")
    simulator: bool = Field(..., description="Est un simulateur")


class QuantumCapabilities(BaseModel):
    """Capacités quantiques disponibles"""
    model_config = ConfigDict(from_attributes=True)

    available_algorithms: List[QuantumAlgorithm] = Field(..., description="Algorithmes disponibles")
    max_circuit_depth: int = Field(..., description="Profondeur maximale de circuit")
    max_qubits: int = Field(..., description="Nombre maximum de qubits")
    supported_hint_types: List[QuantumHintType] = Field(..., description="Types de hints supportés")
    backend_info: QuantumBackendInfo = Field(..., description="Informations backend")


# === SCHÉMAS DE STATISTIQUES ===

class QuantumUsageStats(BaseModel):
    """Statistiques d'utilisation quantique"""
    model_config = ConfigDict(from_attributes=True)

    total_hints_used: int = Field(..., description="Total des hints utilisés")
    hints_by_type: Dict[str, int] = Field(..., description="Hints par type")
    total_points_spent: int = Field(..., description="Points totaux dépensés")
    average_confidence: float = Field(..., description="Confiance moyenne")
    success_rate: float = Field(..., description="Taux de succès")
    favorite_algorithm: Optional[str] = Field(None, description="Algorithme préféré")


class QuantumGameStats(BaseModel):
    """Statistiques quantiques d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    game_id: UUID = Field(..., description="ID de la partie")
    quantum_features_used: bool = Field(..., description="Fonctionnalités quantiques utilisées")
    total_quantum_hints: int = Field(..., description="Total des hints quantiques")
    quantum_advantage_gained: bool = Field(..., description="Avantage quantique obtenu")
    classical_equivalent_time: Optional[float] = Field(None, description="Temps équivalent classique")
    quantum_speedup: Optional[float] = Field(None, description="Accélération quantique")


# === SCHÉMAS D'ÉDUCATION ===

class QuantumConcept(BaseModel):
    """Concept quantique éducatif"""
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Nom du concept")
    description: str = Field(..., description="Description")
    mathematical_formulation: Optional[str] = Field(None, description="Formulation mathématique")
    practical_applications: List[str] = Field(default_factory=list, description="Applications pratiques")
    difficulty_level: int = Field(..., ge=1, le=5, description="Niveau de difficulté")
    prerequisites: List[str] = Field(default_factory=list, description="Prérequis")


class QuantumTutorial(BaseModel):
    """Tutoriel quantique"""
    model_config = ConfigDict(from_attributes=True)

    title: str = Field(..., description="Titre du tutoriel")
    concepts: List[QuantumConcept] = Field(..., description="Concepts couverts")
    interactive_examples: List[Dict[str, Any]] = Field(default_factory=list, description="Exemples interactifs")
    estimated_duration: int = Field(..., description="Durée estimée en minutes")
    target_audience: str = Field(..., description="Public cible")


# === SCHÉMAS DE VALIDATION ===

class QuantumCircuitValidation(BaseModel):
    """Validation de circuit quantique"""
    model_config = ConfigDict(from_attributes=True)

    is_valid: bool = Field(..., description="Circuit valide")
    errors: List[str] = Field(default_factory=list, description="Erreurs détectées")
    warnings: List[str] = Field(default_factory=list, description="Avertissements")
    suggestions: List[str] = Field(default_factory=list, description="Suggestions d'amélioration")
    estimated_execution_time: Optional[float] = Field(None, description="Temps d'exécution estimé")


class QuantumAlgorithmValidation(BaseModel):
    """Validation d'algorithme quantique"""
    model_config = ConfigDict(from_attributes=True)

    algorithm: QuantumAlgorithm = Field(..., description="Algorithme validé")
    correctness: bool = Field(..., description="Algorithme correct")
    complexity_analysis: Dict[str, str] = Field(..., description="Analyse de complexité")
    optimality: bool = Field(..., description="Algorithme optimal")
    practical_considerations: List[str] = Field(default_factory=list, description="Considérations pratiques")


# === EXPORTS ===

__all__ = [
    # Énumérations
    "QuantumHintType", "QuantumAlgorithm", "QuantumGateType",

    # Schémas de base
    "QuantumState", "QuantumCircuit", "MeasurementResult",

    # Hints quantiques
    "QuantumHintRequest", "QuantumHint", "QuantumHintResponse",

    # Algorithmes spécifiques
    "GroverHint", "SuperpositionHint", "EntanglementHint", "InterferenceHint",

    # Simulation
    "QuantumSimulationRequest", "QuantumSimulationResult",

    # Analyse
    "QuantumAdvantageAnalysis", "QuantumErrorAnalysis",

    # Configuration
    "QuantumBackendInfo", "QuantumCapabilities",

    # Statistiques
    "QuantumUsageStats", "QuantumGameStats",

    # Éducation
    "QuantumConcept", "QuantumTutorial",

    # Validation
    "QuantumCircuitValidation", "QuantumAlgorithmValidation"
]