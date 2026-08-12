from __future__ import annotations

from backend.app.quantum.execution.decoder import QuantumResultDecoder
from backend.app.quantum.execution.models import QuantumExecutionRequest, QuantumExecutionResult
from backend.app.quantum.simulation.local_statevector_simulator import LocalStatevectorSimulator


class QuantumExecutionEngine:
    """Coordinate circuit execution, measurement collection, and result decoding."""

    def __init__(
        self,
        *,
        backend: LocalStatevectorSimulator | None = None,
        decoder: QuantumResultDecoder | None = None,
    ) -> None:
        self.backend = backend or LocalStatevectorSimulator()
        self.decoder = decoder or QuantumResultDecoder()

    def execute(self, request: QuantumExecutionRequest) -> QuantumExecutionResult:
        """Execute one validated request through the configured local backend."""

        if not isinstance(request, QuantumExecutionRequest):
            raise ValueError("request must be a QuantumExecutionRequest.")
        backend_result = self.backend.run(request.circuit, request.config)
        candidate = self.decoder.decode(
            request_id=request.request_id,
            measurement=backend_result.measurement,
            variable_mapping=request.variable_mapping,
            problem=request.problem,
        )
        return QuantumExecutionResult(
            request_id=request.request_id,
            backend_name=request.config.backend_name,
            measurement=backend_result.measurement,
            statevector=backend_result.statevector,
            candidate_solution=candidate,
            success=True,
            metadata={
                "backend_type": "local_simulator",
                "provider": "internal_statevector",
                "qubit_count": request.circuit.qubit_count,
                "shots": request.config.shots,
                "seed": request.config.seed,
                "deterministic": request.config.deterministic,
                "operation_count": len(request.circuit.operations),
            },
        )
