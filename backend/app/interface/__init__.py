"""Interface package - user-facing API layer.

Import directly from submodules:
    from backend.app.interface.ai_interaction import AIInteractionLayer
"""

def __getattr__(name: str):
    if name == "AIInteractionLayer":
        from backend.app.interface.ai_interaction import AIInteractionLayer
        return AIInteractionLayer
    if name == "OpenAIProvider":
        from backend.app.interface.llm_provider import OpenAIProvider
        return OpenAIProvider
    if name == "ConfiguredLLMProvider":
        from backend.app.interface.llm_provider import ConfiguredLLMProvider
        return ConfiguredLLMProvider
    if name == "HybridPlanningParser":
        from backend.app.interface.llm_provider import HybridPlanningParser
        return HybridPlanningParser
    if name == "DeterministicFallbackProvider":
        from backend.app.interface.llm_provider import DeterministicFallbackProvider
        return DeterministicFallbackProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["AIInteractionLayer", "OpenAIProvider", "ConfiguredLLMProvider", "HybridPlanningParser", "DeterministicFallbackProvider"]
