"""
Schémas Pydantic pour les opérations quantiques
Validation et sérialisation des données quantiques
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, validator
import numpy as np


# === SCHÉMAS DE BASE QUANTIQUE ===
class QuantumState(BaseModel):
    """État quantique représenté"""
    amplitudes: List[complex] = Field(
        ...,
        description="Amplitudes de l'état quantique"
    )
    num_qubits: int = Field(
        ...,
        ge=1,
        le=10,
        description="Nombre de qubits"
    )
    is_normalized: bool = Field(
        True,
        description="État normalisé"
    )

    class Config:
        # Permet d'utiliser des types complexes
        arbitrary_types_allowed = True

    @validator('amplitudes')
    def validate_amplitudes(cls, v, values):
        """Valide les amplitudes quantiques"""
        num_qubits = values.get('num_qubits', 1)
        expected_length = 2 ** num_qubits

        if len(v) != expected_length:
            raise ValueError(f"Nombre d'amplitudes incorrect: attendu {expected_length}, reçu {len(v)}")

        # Vérification de la normalisation
        norm_squared = sum(abs(amp) ** 2 for amp in v)
        if abs(norm_squared - 1.0) > 1e-6:
            raise ValueError(f"État non normalisé: |ψ|² = {norm_squared}")

        return v


class QuantumCircuit(BaseModel):
    """Circuit quantique"""
    num_qubits: int = Field(
        ...,
        ge=1,
        le=10,
        description="Nombre de qubits"
    )
    gates: List[Dict[str, Any]] = Field(
        ...,
        description="Liste des portes quantiques"
    )
    measurements: List[int] = Field(
        [],
        description="Qubits à mesurer"
    )
    shots: int = Field(
        1024,
        ge=1,
        le=10000,
        description="Nombre de tirs pour la mesure"
    )

    @validator('gates')
    def validate_gates(cls, v, values):
        """Valide les portes quantiques"""
        num_qubits = values.get('num_qubits', 1)
        valid_gates = {'H', 'X', 'Y', 'Z', 'CNOT', 'CZ', 'RX', 'RY', 'RZ', 'T', 'S'}

        for gate in v:
            if 'type' not in gate:
                raise ValueError("Chaque porte doit avoir un type")

            if gate['type'] not in valid_gates:
                raise ValueError(f"Type de porte invalide: {gate['type']}")

            if 'qubits' not in gate:
                raise ValueError("Chaque porte doit spécifier les qubits")

            # Vérification des indices de qubits
            qubits = gate['qubits']
            if not isinstance(qubits, list):
                qubits = [qubits]

            for qubit in qubits:
                if not (0 <= qubit < num_qubits):
                    raise ValueError(f"Indice de qubit invalide: {qubit}")

        return v


class QuantumMeasurement(BaseModel):
    """Mesure quantique"""
    circuit: QuantumCircuit
    qubit_index: int = Field(
        ...,
        ge=0,
        description="Index du qubit à mesurer"
    )
    basis: str = Field(
        "computational",
        regex=r'^(computational|hadamard|x|y|z)$',
        description="Base de mesure"
    )

    @validator('qubit_index')
    def validate_qubit_index(cls, v, values):
        """Valide l'index du qubit"""
        circuit = values.get('circuit')
        if circuit and v >= circuit.num_qubits:
            raise ValueError(f"Index de qubit invalide: {v} >= {circuit.num_qubits}")
        return v


# === SCHÉMAS D'ALGORITHMES QUANTIQUES ===
class GroverSearch(BaseModel):
    """Paramètres pour l'algorithme de Grover"""
    database_size: int = Field(
        ...,
        ge=2,
        le=16,
        description="Taille de la base de données (2^n)"
    )
    target_items: List[int] = Field(
        ...,
        min_items=1,
        description="Éléments à rechercher"
    )
    iterations: Optional[int] = Field(
        None,
        ge=1,
        description="Nombre d'itérations (auto si None)"
    )

    @validator('database_size')
    def validate_database_size_power_of_two(cls, v):
        """Valide que la taille est une puissance de 2"""
        if v & (v - 1) != 0:
            raise ValueError("La taille de la base doit être une puissance de 2")
        return v

    @validator('target_items')
    def validate_target_items(cls, v, values):
        """Valide les éléments cibles"""
        database_size = values.get('database_size', 2)
        for item in v:
            if not (0 <= item < database_size):
                raise ValueError(f"Élément cible invalide: {item}")
        return v


class QuantumSuperposition(BaseModel):
    """Création de superposition quantique"""
    qubits: List[int] = Field(
        ...,
        min_items=1,
        max_items=4,
        description="Qubits à mettre en superposition"
    )
    weights: Optional[List[float]] = Field(
        None,
        description="Poids de la superposition (équiprobable si None)"
    )

    @validator('weights')
    def validate_weights(cls, v, values):
        """Valide les poids de superposition"""
        if v is not None:
            qubits = values.get('qubits', [])
            expected_length = 2 ** len(qubits)

            if len(v) != expected_length:
                raise ValueError(f"Nombre de poids incorrect: attendu {expected_length}")

            if abs(sum(v) - 1.0) > 1e-6:
                raise ValueError("Les poids doivent sommer à 1.0")

            if any(w < 0 for w in v):
                raise ValueError("Les poids doivent être positifs")

        return v


class QuantumEntanglement(BaseModel):
    """Création d'intrication quantique"""
    qubit_pairs: List[List[int]] = Field(
        ...,
        min_items=1,
        description="Paires de qubits à intriquer"
    )
    entanglement_type: str = Field(
        "bell",
        regex=r'^(bell|ghz|cluster)$',
        description="Type d'intrication"
    )

    @validator('qubit_pairs')
    def validate_qubit_pairs(cls, v):
        """Valide les paires de qubits"""
        for pair in v:
            if len(pair) != 2:
                raise ValueError("Chaque paire doit contenir exactement 2 qubits")
            if pair[0] == pair[1]:
                raise ValueError("Un qubit ne peut pas être intriqué avec lui-même")
        return v


# === SCHÉMAS DE RÉSULTATS ===
class QuantumResult(BaseModel):
    """Résultat d'une opération quantique"""
    operation_type: str
    success: bool
    result_data: Dict[str, Any]
    measurements: Optional[Dict[str, int]] = None
    probabilities: Optional[Dict[str, float]] = None
    execution_time: float  # en secondes
    shots_used: int
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class MeasurementResult(BaseModel):
    """Résultat d'une mesure quantique"""
    measured_value: int = Field(
        ...,
        ge=0,
        le=1,
        description="Valeur mesurée (0 ou 1)"
    )
    probability: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Probabilité de cette mesure"
    )
    state_before: Optional[Dict[str, Any]] = None
    state_after: Optional[Dict[str, Any]] = None
    measurement_basis: str
    collapse_occurred: bool = True

    class Config:
        from_attributes = True


class GroverResult(BaseModel):
    """Résultat de l'algorithme de Grover"""
    found_items: List[int]
    success_probability: float
    iterations_performed: int
    optimal_iterations: int
    amplification_factor: float
    execution_details: Dict[str, Any]

    class Config:
        from_attributes = True


# === SCHÉMAS POUR LE MASTERMIND QUANTIQUE ===
class QuantumMastermindSolution(BaseModel):
    """Solution quantique pour Mastermind"""
    classical_solution: List[str] = Field(
        ...,
        min_items=4,
        max_items=4,
        description="Solution classique (4 couleurs)"
    )
    quantum_encoding: Dict[str, Any] = Field(
        ...,
        description="Encodage quantique de la solution"
    )
    entanglement_map: Dict[int, List[int]] = Field(
        {},
        description="Carte des intrications entre positions"
    )
    superposition_states: Dict[int, List[str]] = Field(
        {},
        description="États de superposition par position"
    )
    generation_seed: str = Field(
        ...,
        description="Seed pour la reproduction"
    )

    @validator('classical_solution')
    def validate_colors(cls, v):
        """Valide les couleurs"""
        valid_colors = {'red', 'blue', 'green', 'yellow', 'orange', 'purple', 'black', 'white'}
        for color in v:
            if color not in valid_colors:
                raise ValueError(f"Couleur invalide: {color}")
        return v


class QuantumHint(BaseModel):
    """Indice quantique pour Mastermind"""
    hint_type: str = Field(
        ...,
        regex=r'^(measurement|grover|superposition|entanglement)$',
        description="Type d'indice quantique"
    )
    position: Optional[int] = Field(
        None,
        ge=0,
        le=3,
        description="Position concernée (0-3)"
    )
    revealed_info: Dict[str, Any] = Field(
        ...,
        description="Information révélée"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Niveau de confiance"
    )
    quantum_cost: int = Field(
        ...,
        ge=0,
        description="Coût en points quantiques"
    )


class QuantumAttemptAnalysis(BaseModel):
    """Analyse quantique d'une tentative"""
    attempt: List[str] = Field(
        ...,
        min_items=4,
        max_items=4,
        description="Tentative à analyser"
    )
    quantum_feedback: Dict[str, Any] = Field(
        ...,
        description="Feedback quantique"
    )
    probability_distribution: Dict[str, float] = Field(
        ...,
        description="Distribution de probabilité"
    )
    suggested_improvements: List[str] = Field(
        [],
        description="Améliorations suggérées"
    )
    quantum_advantage: float = Field(
        ...,
        ge=0.0,
        description="Avantage quantique obtenu"
    )


# === SCHÉMAS DE CONFIGURATION ===
class QuantumConfig(BaseModel):
    """Configuration pour les opérations quantiques"""
    backend: str = Field(
        "qasm_simulator",
        regex=r'^(qasm_simulator|statevector_simulator|unitary_simulator)$',
        description="Backend quantique à utiliser"
    )
    shots: int = Field(
        1024,
        ge=1,
        le=10000,
        description="Nombre de tirs par défaut"
    )
    max_qubits: int = Field(
        10,
        ge=1,
        le=30,
        description="Nombre maximum de qubits"
    )
    timeout: int = Field(
        30,
        ge=1,
        le=300,
        description="Timeout en secondes"
    )
    optimization_level: int = Field(
        1,
        ge=0,
        le=3,
        description="Niveau d'optimisation"
    )
    enable_error_mitigation: bool = Field(
        False,
        description="Activer la mitigation d'erreur"
    )


class QuantumBackendInfo(BaseModel):
    """Informations sur un backend quantique"""
    name: str
    version: str
    max_qubits: int
    max_shots: int
    simulator: bool
    supported_instructions: List[str]
    basis_gates: List[str]
    coupling_map: Optional[List[List[int]]] = None
    noise_model: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


# === SCHÉMAS D'ERREUR ET DEBUGGING ===
class QuantumError(BaseModel):
    """Erreur quantique"""
    error_type: str
    error_message: str
    error_code: Optional[str] = None
    circuit_info: Optional[Dict[str, Any]] = None
    suggested_fix: Optional[str] = None
    documentation_link: Optional[str] = None

    class Config:
        from_attributes = True


class QuantumDebugInfo(BaseModel):
    """Informations de debug quantique"""
    circuit_depth: int
    gate_count: Dict[str, int]
    qubit_usage: List[int]
    classical_bits: int
    memory_usage: float  # en MB
    compilation_time: float  # en secondes
    optimization_applied: List[str]

    class Config:
        from_attributes = True


# === SCHÉMAS DE STATISTIQUES ===
class QuantumUsageStats(BaseModel):
    """Statistiques d'utilisation quantique"""
    user_id: UUID
    total_operations: int
    grover_searches: int
    measurements: int
    entanglements: int
    superpositions: int
    total_qubits_used: int
    total_shots: int
    average_success_rate: float
    quantum_advantage_score: float
    period: str  # 'daily', 'weekly', 'monthly', 'all-time'

    class Config:
        from_attributes = True


class QuantumPerformanceMetrics(BaseModel):
    """Métriques de performance quantique"""
    operation_type: str
    average_execution_time: float
    success_rate: float
    error_rate: float
    optimization_efficiency: float
    resource_usage: Dict[str, float]
    timestamp: datetime

    class Config:
        from_attributes = True


# === SCHÉMAS D'EXPORT ET VISUALISATION ===
class QuantumCircuitExport(BaseModel):
    """Export d'un circuit quantique"""
    qasm_code: str
    circuit_diagram: Optional[str] = None
    gate_sequence: List[Dict[str, Any]]
    metadata: Dict[str, Any]

    class Config:
        from_attributes = True


class QuantumVisualization(BaseModel):
    """Données pour la visualisation quantique"""
    state_vector: Optional[List[complex]] = None
    probability_amplitudes: Dict[str, float]
    bloch_sphere_coords: Optional[List[List[float]]] = None
    histogram_data: Dict[str, int]
    phase_information: Optional[Dict[str, float]] = None

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True