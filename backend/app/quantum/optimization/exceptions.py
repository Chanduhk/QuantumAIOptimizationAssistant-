"""QAOA-specific errors."""


class QAOAConfigurationError(ValueError):
    """Raised when QAOA configuration is malformed or unsafe."""


class QAOAParameterError(ValueError):
    """Raised when QAOA parameters are malformed."""


class QAOAOptimizationError(ValueError):
    """Raised when bounded parameter optimization cannot proceed safely."""


class QAOAExecutionError(ValueError):
    """Raised when QAOA execution fails."""


class QAOAResultError(ValueError):
    """Raised when QAOA result construction or validation fails."""
