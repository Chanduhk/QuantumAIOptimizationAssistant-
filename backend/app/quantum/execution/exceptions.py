"""Execution-layer exceptions for quantum simulation boundaries."""


class QuantumExecutionError(ValueError):
    """Base error for invalid quantum execution requests or results."""


class QuantumCircuitError(QuantumExecutionError):
    """Raised when a circuit or operation is malformed or unsupported."""


class QuantumBackendError(QuantumExecutionError):
    """Raised when a backend cannot execute a valid request."""


class QuantumDecodingError(QuantumExecutionError):
    """Raised when measurement data cannot be decoded safely."""


class QuantumSimulationLimitError(QuantumExecutionError):
    """Raised when a simulation request exceeds configured safety bounds."""
