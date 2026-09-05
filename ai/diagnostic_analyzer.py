from __future__ import annotations

from typing import Any

from .openrouter_client import OpenRouterClient
from .prompt_builder import SYSTEM_PROMPT, build_chat_messages, build_diagnostic_prompt


class DiagnosticAnalyzer:
    """Compact AI interface for scan analysis and follow-up chat."""

    def __init__(self, client: OpenRouterClient | None = None) -> None:
        self.client = client or OpenRouterClient()

    def _analysis_messages(self, result: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_diagnostic_prompt(result)},
        ]

    def analyze(self, result: dict[str, Any]) -> str:
        return self.client.chat(
            self._analysis_messages(result),
            temperature=0.1,
            max_tokens=850,
        )

    def analyze_stream(self, result: dict[str, Any], **kwargs) -> str:
        return self.client.chat_stream(
            self._analysis_messages(result),
            temperature=0.1,
            max_tokens=850,
            **kwargs,
        )

    def chat_stream(
        self,
        result: dict[str, Any],
        conversation: list[dict[str, str]],
        user_message: str,
        **kwargs,
    ) -> str:
        return self.client.chat_stream(
            build_chat_messages(result, conversation, user_message),
            temperature=0.15,
            max_tokens=700,
            **kwargs,
        )

    def chat(
        self,
        result: dict[str, Any],
        conversation: list[dict[str, str]],
        user_message: str,
    ) -> str:
        return self.client.chat(
            build_chat_messages(result, conversation, user_message),
            temperature=0.15,
            max_tokens=700,
        )
