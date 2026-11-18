"""Learning package - autonomous learning and adaptation.

Import directly from submodules:
    from backend.app.learning.autonomous_learning import AutonomousLearningLoop
"""

from backend.app.learning.autonomous_learning import (  # noqa: F401
    AutonomousLearningLoop,
    AutomaticLearningCoordinator,
    LearningState,
    get_learning_coordinator,
    reset_learning_coordinator,
)

__all__ = [
    "AutonomousLearningLoop",
    "AutomaticLearningCoordinator",
    "LearningState",
    "get_learning_coordinator",
    "reset_learning_coordinator",
]
