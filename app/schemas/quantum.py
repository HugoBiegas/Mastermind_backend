"""
Schémas Pydantic pour les fonctionnalités quantiques
Validation et sérialisation des données quantiques
CORRECTION: Synchronisé avec le service quantum
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
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
    """Algorithmes quantiques supportés - CORRECTION: Ajout des valeurs du service"""
    GROVER = "grover"                           # Valeur retournée par le service
    GROVER_SEARCH = "grover_search"            # Nom complet
    QUANTUM = "quantum"                         # Valeur générique
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
        return v


class QuantumGate(BaseModel):
    """Porte quantique"""
    model_config = ConfigDict(from_attributes=True)

    gate_type: QuantumGateType = Field(..., description="Type de porte")
    qubits: List[int] = Field(..., description="Qubits cibles")
    parameters: Optional[List[float]] = Field(None, description="Paramètres de la porte")


class QuantumCircuit(BaseModel):
    """Circuit quantique"""
    model_config = ConfigDict(from_attributes=True)

    n_qubits: int = Field(..., description="Nombre de qubits")
    gates: List[QuantumGate] = Field(..., description="Portes du circuit")
    measurements: List[int] = Field(default_factory=list, description="Qubits mesurés")
    depth: int = Field(..., description="Profondeur du circuit")


class QuantumJob(BaseModel):
    """Job quantique"""
    model_config = ConfigDict(from_attributes=True)

    job_id: str = Field(..., description="ID du job")
    circuit: QuantumCircuit = Field(..., description="Circuit exécuté")
    backend: str = Field(..., description="Backend utilisé")
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
    """
    Indice quantique pour le jeu
    CORRECTION: Champs optionnels pour correspondre au service
    """
    model_config = ConfigDict(from_attributes=True)

    # Champs de base (du service quantum)
    message: str = Field(..., description="Message de l'indice")
    type: str = Field(..., description="Type d'indice")  # Utilise 'type' comme dans le service
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confiance de l'indice")

    # Champs techniques (optionnels)
    algorithm_used: Optional[str] = Field(None, description="Algorithme utilisé")
    qubits_used: Optional[int] = Field(None, description="Nombre de qubits utilisés")
    execution_time: Optional[float] = Field(None, description="Temps d'exécution")

    # Champs optionnels supplémentaires
    hint_type: Optional[str] = Field(None, description="Type de hint (alias)")
    cost: int = Field(default=0, description="Coût en points")
    circuit_depth: Optional[int] = Field(None, description="Profondeur du circuit")

    # Données de jeu
    affected_positions: Optional[List[int]] = Field(None, description="Positions affectées")
    excluded_colors: Optional[List[int]] = Field(None, description="Couleurs exclues")
    suggested_colors: Optional[List[int]] = Field(None, description="Couleurs suggérées")

    # Métadonnées
    created_at: Optional[datetime] = Field(None, description="Date de création")
    expires_at: Optional[datetime] = Field(None, description="Date d'expiration")
    error: Optional[str] = Field(None, description="Message d'erreur éventuel")


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


class EntanglementMeasure(BaseModel):
    """Mesure d'intrication"""
    model_config = ConfigDict(from_attributes=True)

    entanglement_entropy: float = Field(..., description="Entropie d'intrication")
    concurrence: float = Field(..., description="Concurrence")
    negativity: float = Field(..., description="Négativité")
    entangled_qubits: List[Tuple[int, int]] = Field(..., description="Paires de qubits intriqués")


# === SCHÉMAS DE VALIDATION ===

class QuantumValidation(BaseModel):
    """Validation des données quantiques"""
    model_config = ConfigDict(from_attributes=True)

    is_valid: bool = Field(..., description="Données valides")
    errors: List[str] = Field(default_factory=list, description="Erreurs détectées")
    warnings: List[str] = Field(default_factory=list, description="Avertissements")
    quantum_properties_preserved: bool = Field(..., description="Propriétés quantiques préservées")


class CircuitOptimization(BaseModel):
    """Optimisation de circuit quantique"""
    model_config = ConfigDict(from_attributes=True)

    original_depth: int = Field(..., description="Profondeur originale")
    optimized_depth: int = Field(..., description="Profondeur optimisée")
    gate_count_reduction: int = Field(..., description="Réduction du nombre de portes")
    fidelity: float = Field(..., description="Fidélité après optimisation")
    optimization_time: float = Field(..., description="Temps d'optimisation")


# === SCHÉMAS DE CONFIGURATION ===

class QuantumBackendConfig(BaseModel):
    """Configuration d'un backend quantique"""
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Nom du backend")
    max_qubits: int = Field(..., description="Nombre maximum de qubits")
    max_shots: int = Field(..., description="Nombre maximum de shots")
    coupling_map: Optional[List[List[int]]] = Field(None, description="Carte de couplage")
    gate_set: List[str] = Field(..., description="Ensemble de portes supportées")
    error_rates: Dict[str, float] = Field(default_factory=dict, description="Taux d'erreur")


class QuantumExperiment(BaseModel):
    """Expérience quantique"""
    model_config = ConfigDict(from_attributes=True)

    experiment_id: UUID = Field(..., description="ID de l'expérience")
    circuit: QuantumCircuit = Field(..., description="Circuit utilisé")
    backend_config: QuantumBackendConfig = Field(..., description="Configuration backend")
    results: Dict[str, Any] = Field(..., description="Résultats de l'expérience")
    analysis: Optional[Dict[str, Any]] = Field(None, description="Analyse des résultats")
    created_at: datetime = Field(..., description="Date de création")
    completed_at: Optional[datetime] = Field(None, description="Date de complétion")


# === EXPORTS ===

__all__ = [
    # Énumérations
    "QuantumHintType", "QuantumAlgorithm", "QuantumGateType",

    # États et circuits
    "QuantumState", "QuantumGate", "QuantumCircuit", "QuantumJob",

    # Hints
    "QuantumHint", "QuantumHintRequest", "QuantumHintResponse",

    # Algorithmes
    "GroverSearchRequest", "GroverSearchResult",
    "SuperpositionAnalysis", "EntanglementMeasure",

    # Utilitaires
    "QuantumProbabilities", "QuantumValidation", "CircuitOptimization",

    # Configuration
    "QuantumBackendConfig", "QuantumExperiment"
]