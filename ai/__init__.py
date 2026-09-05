"""FixMate-AI AI integration package."""

from .diagnostic_analyzer import DiagnosticAnalyzer
from .openrouter_client import (
    DEFAULT_MODEL,
    OpenRouterClient,
    OpenRouterCancelled,
    OpenRouterConfigError,
    delete_saved_api_key,
    get_saved_api_key,
    get_saved_model,
    save_model,
    save_api_key,
)

__all__ = [
    "DiagnosticAnalyzer",
    "DEFAULT_MODEL",
    "OpenRouterClient",
    "OpenRouterCancelled",
    "OpenRouterConfigError",
    "delete_saved_api_key",
    "get_saved_api_key",
    "get_saved_model",
    "save_model",
    "save_api_key",
]
