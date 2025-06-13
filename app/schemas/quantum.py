"""
Schémas Pydantic pour les opérations quantiques
Validation et sérialisation des données quantiques
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
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

    model_config = {"arbitrary_types_allowed": True}

    @field_validator('amplitudes')
    @classmethod
    def validate_amplitudes(cls, v, info):
        """Valide les amplitudes quantiques"""
        data = info.data
        num_qubits = data.get('num_qubits', 1)
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

    @field_validator('gates')
    @classmethod
    def validate_gates(cls, v, info):
        """Valide les portes quantiques"""
        data = info.data
        num_qubits = data.get('num_qubits', 1)
        valid_gates = {'H', 'X', 'Y', 'Z', 'CNOT', 'CZ', 'RX', 'RY', 'RZ', 'T', 'S'}

        for gate in v:
            if 'type' not in gate:
                raise ValueError("Chaque porte doit avoir un type")

            gate_type = gate['type']
            if gate_type not in valid_gates:
                raise ValueError(f"Type de porte invalide: {gate_type}")

            # Validation des qubits cibles
            if 'target' in gate:
                target = gate['target']
                if isinstance(target, int):
                    if target < 0 or target >= num_qubits:
                        raise ValueError(f"Qubit cible invalide: {target}")
                elif isinstance(target, list):
                    for t in target:
                        if t < 0 or t >= num_qubits:
                            raise ValueError(f"Qubit cible invalide: {t}")

            # Validation des paramètres pour les portes paramétrées
            if gate_type in ['RX', 'RY', 'RZ']:
                if 'angle' not in gate:
                    raise ValueError(f"Angle requis pour la porte {gate_type}")
                angle = gate['angle']
                if not isinstance(angle, (int, float)):
                    raise ValueError(f"Angle invalide pour {gate_type}: {angle}")

        return v

    @field_validator('measurements')
    @classmethod
    def validate_measurements(cls, v, info):
        """Valide les qubits à mesurer"""
        data = info.data
        num_qubits = data.get('num_qubits', 1)

        for qubit in v:
            if qubit < 0 or qubit >= num_qubits:
                raise ValueError(f"Qubit de mesure invalide: {qubit}")

        return v


class QuantumGate(BaseModel):
    """Porte quantique individuelle"""
    type: str = Field(
        ...,
        pattern=r'^(H|X|Y|Z|CNOT|CZ|RX|RY|RZ|T|S|SWAP|CCX)$',
        description="Type de porte quantique"
    )
    target: Union[int, List[int]] = Field(
        ...,
        description="Qubit(s) cible(s)"
    )
    control: Optional[Union[int, List[int]]] = Field(
        None,
        description="Qubit(s) de contrôle pour les portes contrôlées"
    )
    angle: Optional[float] = Field(
        None,
        description="Angle pour les portes de rotation"
    )
    label: Optional[str] = Field(
        None,
        max_length=50,
        description="Label personnalisé"
    )

    @field_validator('angle')
    @classmethod
    def validate_angle(cls, v, info):
        """Valide l'angle pour les portes de rotation"""
        data = info.data
        gate_type = data.get('type')

        if gate_type in ['RX', 'RY', 'RZ']:
            if v is None:
                raise ValueError(f"Angle requis pour la porte {gate_type}")
            if not isinstance(v, (int, float)):
                raise ValueError("L'angle doit être un nombre")

        return v


class QuantumMeasurement(BaseModel):
    """Mesure quantique"""
    qubits: List[int] = Field(
        ...,
        min_length=1,
        description="Qubits à mesurer"
    )
    basis: str = Field(
        "computational",
        pattern=r'^(computational|hadamard|bell)$',
        description="Base de mesure"
    )
    shots: int = Field(
        1024,
        ge=1,
        le=10000,
        description="Nombre de mesures"
    )


class QuantumResult(BaseModel):
    """Résultat d'une opération quantique"""
    success: bool
    result_type: str = Field(
        ...,
        pattern=r'^(measurement|state|circuit_execution|algorithm)$',
        description="Type de résultat"
    )
    data: Dict[str, Any] = Field(
        ...,
        description="Données du résultat"
    )
    execution_time: float = Field(
        ...,
        ge=0,
        description="Temps d'exécution en secondes"
    )
    backend_info: Dict[str, str] = Field(
        {},
        description="Informations sur le backend utilisé"
    )
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# === ALGORITHMES QUANTIQUES SPÉCIALISÉS ===
class GroverAlgorithm(BaseModel):
    """Algorithme de Grover pour la recherche quantique"""
    search_space_size: int = Field(
        ...,
        ge=2,
        le=1024,
        description="Taille de l'espace de recherche"
    )
    target_items: List[int] = Field(
        ...,
        min_length=1,
        description="Items à rechercher"
    )
    oracle_type: str = Field(
        "boolean",
        pattern=r'^(boolean|phase)$',
        description="Type d'oracle"
    )
    iterations: Optional[int] = Field(
        None,
        ge=1,
        description="Nombre d'itérations (auto si None)"
    )

    @field_validator('target_items')
    @classmethod
    def validate_target_items(cls, v, info):
        """Valide les items cibles"""
        data = info.data
        search_space_size = data.get('search_space_size', 2)

        for item in v:
            if item < 0 or item >= search_space_size:
                raise ValueError(f"Item cible {item} hors de l'espace de recherche [0, {search_space_size-1}]")

        # Vérifier qu'il n'y a pas de doublons
        if len(v) != len(set(v)):
            raise ValueError("Items cibles dupliqués détectés")

        return v


class ShorAlgorithm(BaseModel):
    """Algorithme de Shor pour la factorisation"""
    number_to_factor: int = Field(
        ...,
        ge=15,
        le=2047,
        description="Nombre à factoriser"
    )
    use_classical_preprocessing: bool = Field(
        True,
        description="Utiliser le préprocessing classique"
    )
    max_attempts: int = Field(
        10,
        ge=1,
        le=100,
        description="Nombre maximum de tentatives"
    )

    @field_validator('number_to_factor')
    @classmethod
    def validate_number(cls, v):
        """Valide le nombre à factoriser"""
        if v < 15:
            raise ValueError("Le nombre doit être >= 15 pour Shor")

        # Vérifier que ce n'est pas une puissance de 2
        if v & (v - 1) == 0:
            raise ValueError("L'algorithme de Shor ne s'applique pas aux puissances de 2")

        return v


class QuantumSupremacyBenchmark(BaseModel):
    """Benchmark de suprématie quantique"""
    circuit_depth: int = Field(
        ...,
        ge=10,
        le=100,
        description="Profondeur du circuit"
    )
    num_qubits: int = Field(
        ...,
        ge=5,
        le=20,
        description="Nombre de qubits"
    )
    gate_set: List[str] = Field(
        ["H", "CZ", "RX"],
        description="Ensemble de portes à utiliser"
    )
    randomization_seed: Optional[int] = Field(
        None,
        description="Graine pour la génération aléatoire"
    )


# === SCHÉMAS DE SIMULATION ===
class QuantumSimulationConfig(BaseModel):
    """Configuration de simulation quantique"""
    backend_type: str = Field(
        "aer_simulator",
        pattern=r'^(aer_simulator|qasm_simulator|statevector_simulator)$',
        description="Type de simulateur"
    )
    shots: int = Field(
        1024,
        ge=1,
        le=100000,
        description="Nombre de tirs"
    )
    noise_model: Optional[str] = Field(
        None,
        pattern=r'^(ibmq_|fake_|custom_).*$',
        description="Modèle de bruit"
    )
    optimization_level: int = Field(
        1,
        ge=0,
        le=3,
        description="Niveau d'optimisation"
    )
    memory_efficient: bool = Field(
        False,
        description="Mode économe en mémoire"
    )


class QuantumNoiseModel(BaseModel):
    """Modèle de bruit quantique"""
    name: str = Field(..., max_length=100)
    gate_errors: Dict[str, float] = Field(
        {},
        description="Erreurs par porte"
    )
    measurement_error: float = Field(
        0.01,
        ge=0.0,
        le=1.0,
        description="Erreur de mesure"
    )
    decoherence_time: Optional[float] = Field(
        None,
        gt=0,
        description="Temps de décohérence en µs"
    )
    cross_talk_matrix: Optional[List[List[float]]] = Field(
        None,
        description="Matrice de diaphonie"
    )


# === SCHÉMAS D'ÉDUCATION QUANTIQUE ===
class QuantumTutorial(BaseModel):
    """Tutoriel quantique interactif"""
    id: UUID
    title: str = Field(..., max_length=200)
    description: str = Field(..., max_length=1000)
    difficulty_level: str = Field(
        ...,
        pattern=r'^(beginner|intermediate|advanced|expert)$'
    )
    prerequisites: List[str] = Field([], description="Prérequis")
    learning_objectives: List[str] = Field(..., min_length=1)
    estimated_duration: int = Field(..., gt=0, description="Durée estimée en minutes")
    interactive_elements: List[Dict[str, Any]] = Field([], description="Éléments interactifs")
    completion_criteria: Dict[str, Any] = Field(..., description="Critères de réussite")

    model_config = {"from_attributes": True}


class QuantumExercise(BaseModel):
    """Exercice quantique"""
    id: UUID
    tutorial_id: UUID
    type: str = Field(
        ...,
        pattern=r'^(circuit_building|state_preparation|measurement|algorithm)$'
    )
    instructions: str = Field(..., max_length=2000)
    starting_circuit: Optional[QuantumCircuit] = None
    expected_result: Dict[str, Any] = Field(..., description="Résultat attendu")
    hints: List[str] = Field([], description="Indices disponibles")
    max_attempts: int = Field(5, ge=1, le=20)
    scoring_criteria: Dict[str, Any] = Field(..., description="Critères de notation")

    model_config = {"from_attributes": True}


# === SCHÉMAS DE MASTERMIND QUANTIQUE ===
class QuantumMastermindHint(BaseModel):
    """Indice quantique pour le Mastermind"""
    hint_type: str = Field(
        ...,
        pattern=r'^(quantum_measurement|superposition_analysis|entanglement_check)$',
        description="Type d'indice quantique"
    )
    position: Optional[int] = Field(
        None,
        ge=0,
        le=3,
        description="Position analysée (si applicable)"
    )
    confidence_level: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Niveau de confiance [0-1]"
    )
    quantum_advantage: bool = Field(
        False,
        description="Indique si l'avantage quantique est exploité"
    )
    cost: int = Field(
        ...,
        ge=0,
        description="Coût en points quantiques"
    )
    result_data: Dict[str, Any] = Field(
        {},
        description="Données détaillées du résultat"
    )


class QuantumMastermindState(BaseModel):
    """État quantique du jeu Mastermind"""
    game_id: UUID
    superposition_active: bool = Field(
        False,
        description="Superposition quantique active"
    )
    entangled_positions: List[List[int]] = Field(
        [],
        description="Positions intriquées"
    )
    quantum_measurements_used: int = Field(
        0,
        ge=0,
        description="Nombre de mesures quantiques utilisées"
    )
    quantum_score_multiplier: float = Field(
        1.0,
        ge=1.0,
        le=5.0,
        description="Multiplicateur de score quantique"
    )
    available_quantum_operations: List[str] = Field(
        [],
        description="Opérations quantiques disponibles"
    )


# === SCHÉMAS DE PERFORMANCE QUANTIQUE ===
class QuantumPerformanceMetrics(BaseModel):
    """Métriques de performance quantique"""
    user_id: UUID
    quantum_circuits_executed: int = 0
    total_quantum_operations: int = 0
    quantum_advantage_exploited: int = 0
    average_circuit_depth: float = 0.0
    success_rate_quantum_algorithms: float = 0.0
    quantum_complexity_score: int = 0
    preferred_quantum_gates: List[str] = []
    quantum_learning_progress: Dict[str, float] = {}

    model_config = {"from_attributes": True}


# === SCHÉMAS DE VALIDATION AVANCÉE ===
class QuantumCircuitValidation(BaseModel):
    """Validation avancée de circuit quantique"""
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    optimization_suggestions: List[str] = []
    estimated_execution_time: Optional[float] = None
    resource_requirements: Dict[str, Any] = {}
    complexity_score: int = Field(0, ge=0, le=100)


class QuantumAlgorithmAnalysis(BaseModel):
    """Analyse d'algorithme quantique"""
    algorithm_type: str
    theoretical_speedup: Optional[str] = None
    actual_performance: Dict[str, float] = {}
    resource_usage: Dict[str, Any] = {}
    scalability_analysis: Dict[str, str] = {}
    comparison_classical: Dict[str, Any] = {}
    recommendations: List[str] = []