"""Interface package - user-facing API layer.

Import directly from submodules:
    from backend.app.interface.ai_interaction import AIInteractionLayer
"""

def __getattr__(name: str):
    if name == "AIInteractionLayer":
        from backend.app.interface.ai_interaction import AIInteractionLayer
        return AIInteractionLayer
    if name == "GeminiProvider":
        from backend.app.interface.llm_provider import GeminiProvider
        return GeminiProvider
    if name == "OpenAIProvider":
        from backend.app.interface.llm_provider import OpenAIProvider
        return OpenAIProvider
    if name == "get_llm_provider":
        from backend.app.interface.llm_provider import get_llm_provider
        return get_llm_provider
    if name == "get_default_llm_provider":
        from backend.app.interface.llm_provider import get_default_llm_provider
        return get_default_llm_provider
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

__all__ = [
    "AIInteractionLayer",
    "GeminiProvider",
    "OpenAIProvider",
    "ConfiguredLLMProvider",
    "HybridPlanningParser",
    "DeterministicFallbackProvider",
    "get_llm_provider",
    "get_default_llm_provider",
]
