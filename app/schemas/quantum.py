"""
Schémas Pydantic pour les fonctionnalités quantiques
Validation et sérialisation des données quantiques
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, field_validator, ConfigDict


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

    @field_validator('amplitudes')
    @classmethod
    def validate_amplitudes(cls, v: List[complex]) -> List[complex]:
        """Valide que les amplitudes forment un état quantique valide"""
        if not v:
            raise ValueError("Au moins une amplitude requise")

        # Vérifier la normalisation (optionnel pour la flexibilité)
        total_prob = sum(abs(amp)**2 for amp in v)
        if abs(total_prob - 1.0) > 1e-6:
            # Logger un avertissement mais ne pas rejeter
            pass

        return v


class QuantumGate(BaseModel):
    """Porte quantique"""
    model_config = ConfigDict(from_attributes=True)

    gate_type: QuantumGateType = Field(..., description="Type de porte")
    qubits: List[int] = Field(..., description="Qubits cibles")
    parameters: Optional[List[float]] = Field(None, description="Paramètres de la porte")
    description: Optional[str] = Field(None, description="Description de la porte")

    @field_validator('qubits')
    @classmethod
    def validate_qubits(cls, v: List[int]) -> List[int]:
        """Valide les indices de qubits"""
        if not v:
            raise ValueError("Au moins un qubit requis")

        for qubit in v:
            if qubit < 0:
                raise ValueError("Les indices de qubits doivent être positifs")

        return v


class QuantumCircuit(BaseModel):
    """Circuit quantique"""
    model_config = ConfigDict(from_attributes=True)

    n_qubits: int = Field(..., ge=1, le=20, description="Nombre de qubits")
    gates: List[QuantumGate] = Field(..., description="Portes du circuit")
    name: Optional[str] = Field(None, description="Nom du circuit")
    description: Optional[str] = Field(None, description="Description du circuit")
    classical_bits: int = Field(default=0, description="Nombre de bits classiques")

    @field_validator('gates')
    @classmethod
    def validate_gates(cls, v: List[QuantumGate]) -> List[QuantumGate]:
        """Valide la liste des portes"""
        if not v:
            raise ValueError("Au moins une porte requise")
        return v


class QuantumMeasurement(BaseModel):
    """Mesure quantique"""
    model_config = ConfigDict(from_attributes=True)

    qubits: List[int] = Field(..., description="Qubits à mesurer")
    classical_bits: List[int] = Field(..., description="Bits classiques de sortie")
    shots: int = Field(default=1024, ge=1, le=10000, description="Nombre de mesures")


class QuantumJob(BaseModel):
    """Job quantique"""
    model_config = ConfigDict(from_attributes=True)

    circuit: QuantumCircuit = Field(..., description="Circuit à exécuter")
    measurements: List[QuantumMeasurement] = Field(..., description="Mesures à effectuer")
    backend: str = Field(default="qasm_simulator", description="Backend quantique")
    shots: int = Field(default=1024, ge=1, le=10000, description="Nombre total de shots")
    optimization_level: int = Field(default=1, ge=0, le=3, description="Niveau d'optimisation")


# === SCHÉMAS DE RÉSULTATS ===

class QuantumResult(BaseModel):
    """Résultat d'exécution quantique"""
    model_config = ConfigDict(from_attributes=True)

    counts: Dict[str, int] = Field(..., description="Comptages des mesures")
    shots: int = Field(..., description="Nombre de shots")
    success: bool = Field(..., description="Exécution réussie")
    execution_time: float = Field(..., description="Temps d'exécution en secondes")
    backend_used: str = Field(..., description="Backend utilisé")
    job_id: Optional[str] = Field(None, description="ID du job")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Métadonnées")


class QuantumProbabilities(BaseModel):
    """Probabilités quantiques"""
    model_config = ConfigDict(from_attributes=True)

    probabilities: Dict[str, float] = Field(..., description="Probabilités par état")
    entropy: float = Field(..., description="Entropie de l'état")
    purity: float = Field(..., description="Pureté de l'état")

    @field_validator('probabilities')
    @classmethod
    def validate_probabilities(cls, v: Dict[str, float]) -> Dict[str, float]:
        """Valide que les probabilités somment à 1"""
        total = sum(v.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Les probabilités doivent sommer à 1, somme actuelle: {total}")
        return v


# === SCHÉMAS DE HINTS QUANTIQUES ===

class QuantumHint(BaseModel):
    """Indice quantique pour le jeu"""
    model_config = ConfigDict(from_attributes=True)

    hint_type: QuantumHintType = Field(..., description="Type d'indice")
    message: str = Field(..., description="Message de l'indice")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confiance de l'indice")
    cost: int = Field(default=0, description="Coût en points")

    # Données techniques
    algorithm_used: Optional[QuantumAlgorithm] = Field(None, description="Algorithme utilisé")
    circuit_depth: Optional[int] = Field(None, description="Profondeur du circuit")
    qubits_used: Optional[int] = Field(None, description="Nombre de qubits utilisés")
    execution_time: Optional[float] = Field(None, description="Temps d'exécution")

    # Données de jeu
    affected_positions: Optional[List[int]] = Field(None, description="Positions affectées")
    excluded_colors: Optional[List[int]] = Field(None, description="Couleurs exclues")
    suggested_colors: Optional[List[int]] = Field(None, description="Couleurs suggérées")

    # Métadonnées
    created_at: datetime = Field(default_factory=datetime.now, description="Date de création")
    expires_at: Optional[datetime] = Field(None, description="Date d'expiration")


class QuantumHintRequest(BaseModel):
    """Requête d'indice quantique"""
    model_config = ConfigDict(from_attributes=True)

    game_id: UUID = Field(..., description="ID de la partie")
    hint_type: QuantumHintType = Field(..., description="Type d'indice demandé")
    current_attempts: List[List[int]] = Field(..., description="Tentatives actuelles")
    max_cost: Optional[int] = Field(None, description="Coût maximum acceptable")
    prefer_speed: bool = Field(default=False, description="Préférer la vitesse à la précision")


class QuantumHintResponse(BaseModel):
    """Réponse d'indice quantique"""
    model_config = ConfigDict(from_attributes=True)

    hint: QuantumHint = Field(..., description="Indice généré")
    success: bool = Field(..., description="Génération réussie")
    error_message: Optional[str] = Field(None, description="Message d'erreur si échec")
    alternative_hints: Optional[List[QuantumHint]] = Field(None, description="Indices alternatifs")


# === SCHÉMAS D'ALGORITHMES ===

class GroverSearchRequest(BaseModel):
    """Requête de recherche Grover"""
    model_config = ConfigDict(from_attributes=True)

    search_space: List[List[int]] = Field(..., description="Espace de recherche")
    target_properties: Dict[str, Any] = Field(..., description="Propriétés cibles")
    iterations: Optional[int] = Field(None, description="Nombre d'itérations")
    optimization: bool = Field(default=True, description="Optimisation activée")


class GroverSearchResult(BaseModel):
    """Résultat de recherche Grover"""
    model_config = ConfigDict(from_attributes=True)

    found_items: List[List[int]] = Field(..., description="Éléments trouvés")
    probabilities: Dict[str, float] = Field(..., description="Probabilités")
    iterations_used: int = Field(..., description="Itérations utilisées")
    success_probability: float = Field(..., description="Probabilité de succès")
    quantum_advantage: float = Field(..., description="Avantage quantique calculé")


class SuperpositionAnalysis(BaseModel):
    """Analyse de superposition"""
    model_config = ConfigDict(from_attributes=True)

    state_vector: List[complex] = Field(..., description="Vecteur d'état")
    basis_states: List[str] = Field(..., description="États de base")
    superposition_degree: float = Field(..., description="Degré de superposition")
    coherence_measure: float = Field(..., description="Mesure de cohérence")
    entanglement_present: bool = Field(..., description="Intrication présente")


class EntanglementAnalysis(BaseModel):
    """Analyse d'intrication"""
    model_config = ConfigDict(from_attributes=True)

    entangled_qubits: List[List[int]] = Field(..., description="Qubits intriqués")
    entanglement_measure: float = Field(..., description="Mesure d'intrication")
    schmidt_coefficients: List[float] = Field(..., description="Coefficients de Schmidt")
    bipartite_cuts: List[Dict[str, Any]] = Field(..., description="Coupures biparties")


# === SCHÉMAS DE CONFIGURATION ===

class QuantumBackendConfig(BaseModel):
    """Configuration d'un backend quantique"""
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Nom du backend")
    provider: str = Field(..., description="Fournisseur")
    max_qubits: int = Field(..., description="Nombre maximum de qubits")
    max_shots: int = Field(..., description="Nombre maximum de shots")
    quantum_volume: Optional[int] = Field(None, description="Volume quantique")
    gate_time: Optional[float] = Field(None, description="Temps de porte en ns")
    readout_error: Optional[float] = Field(None, description="Erreur de lecture")
    gate_error: Optional[float] = Field(None, description="Erreur de porte")
    connectivity: Optional[List[List[int]]] = Field(None, description="Connectivité des qubits")
    available: bool = Field(default=True, description="Backend disponible")


class QuantumExperiment(BaseModel):
    """Expérience quantique complète"""
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Nom de l'expérience")
    description: str = Field(..., description="Description")
    circuits: List[QuantumCircuit] = Field(..., description="Circuits de l'expérience")
    measurements: List[QuantumMeasurement] = Field(..., description="Mesures")
    parameters: Dict[str, Any] = Field(..., description="Paramètres")
    expected_results: Optional[Dict[str, Any]] = Field(None, description="Résultats attendus")

    created_at: datetime = Field(default_factory=datetime.now, description="Date de création")
    created_by: UUID = Field(..., description="Créateur")
    tags: List[str] = Field(default_factory=list, description="Tags")


class QuantumExperimentResult(BaseModel):
    """Résultat d'expérience quantique"""
    model_config = ConfigDict(from_attributes=True)

    experiment_id: UUID = Field(..., description="ID de l'expérience")
    results: List[QuantumResult] = Field(..., description="Résultats des circuits")
    analysis: Dict[str, Any] = Field(..., description="Analyse des résultats")
    success: bool = Field(..., description="Expérience réussie")
    total_time: float = Field(..., description="Temps total d'exécution")

    executed_at: datetime = Field(default_factory=datetime.now, description="Date d'exécution")
    backend_used: str = Field(..., description="Backend utilisé")
    error_messages: List[str] = Field(default_factory=list, description="Messages d'erreur")


# === SCHÉMAS DE VALIDATION ===

class QuantumValidation(BaseModel):
    """Validation de données quantiques"""
    model_config = ConfigDict(from_attributes=True)

    is_valid: bool = Field(..., description="Données valides")
    errors: List[str] = Field(default_factory=list, description="Erreurs détectées")
    warnings: List[str] = Field(default_factory=list, description="Avertissements")
    suggestions: List[str] = Field(default_factory=list, description="Suggestions")
    quantum_properties: Dict[str, Any] = Field(default_factory=dict, description="Propriétés quantiques")


class CircuitOptimization(BaseModel):
    """Optimisation de circuit"""
    model_config = ConfigDict(from_attributes=True)

    original_circuit: QuantumCircuit = Field(..., description="Circuit original")
    optimized_circuit: QuantumCircuit = Field(..., description="Circuit optimisé")
    optimization_level: int = Field(..., description="Niveau d'optimisation")
    gate_count_reduction: int = Field(..., description="Réduction du nombre de portes")
    depth_reduction: int = Field(..., description="Réduction de profondeur")
    fidelity: float = Field(..., description="Fidélité de l'optimisation")


# === EXPORTS ===

__all__ = [
    # Énumérations
    "QuantumHintType", "QuantumAlgorithm", "QuantumGateType",

    # Structures de base
    "QuantumState", "QuantumGate", "QuantumCircuit", "QuantumMeasurement", "QuantumJob",

    # Résultats
    "QuantumResult", "QuantumProbabilities",

    # Hints de jeu
    "QuantumHint", "QuantumHintRequest", "QuantumHintResponse",

    # Algorithmes
    "GroverSearchRequest", "GroverSearchResult", "SuperpositionAnalysis", "EntanglementAnalysis",

    # Configuration et expériences
    "QuantumBackendConfig", "QuantumExperiment", "QuantumExperimentResult",

    # Validation et optimisation
    "QuantumValidation", "CircuitOptimization"
]