from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Callable

import requests


OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
SERVICE_NAME = "FixMate-AI"
KEY_NAME = "openrouter_api_key"
MODEL_KEY_NAME = "openrouter_model"
DEFAULT_MODEL = "openrouter/free"


class OpenRouterCancelled(RuntimeError):
    """Raised when an in-flight OpenRouter request is cancelled by the user."""


class OpenRouterConfigError(RuntimeError):
    """Raised when OpenRouter credentials/configuration are missing."""


@dataclass(frozen=True)
class OpenRouterConfig:
    api_key: str
    model: str = DEFAULT_MODEL
    base_url: str = OPENROUTER_ENDPOINT
    app_name: str = SERVICE_NAME


def get_saved_api_key() -> str:
    """Read the API key from an environment variable or Windows keyring."""
    env_key = os.getenv("FIXMATE_OPENROUTER_API_KEY", "").strip()
    if env_key:
        return env_key

    try:
        import keyring

        return (keyring.get_password(SERVICE_NAME, KEY_NAME) or "").strip()
    except Exception:
        return ""


def save_api_key(api_key: str) -> None:
    """Store or clear an API key. Empty input is a valid "no AI" configuration."""
    api_key = api_key.strip()
    if not api_key:
        delete_saved_api_key()
        return

    try:
        import keyring

        keyring.set_password(SERVICE_NAME, KEY_NAME, api_key)
    except Exception as exc:
        raise OpenRouterConfigError(
            "Could not save the API key to Windows Credential Manager. "
            f"{exc}"
        ) from exc


def delete_saved_api_key() -> None:
    """Remove the stored key from the OS credential store."""
    try:
        import keyring

        try:
            keyring.delete_password(SERVICE_NAME, KEY_NAME)
        except keyring.errors.PasswordDeleteError:
            pass
    except ModuleNotFoundError:
        # keyring is optional for using FixMate-AI without OpenRouter.
        return
    except Exception as exc:
        raise OpenRouterConfigError(
            f"Could not remove the saved API key. {exc}"
        ) from exc


def get_saved_model() -> str:
    env_model = os.getenv("FIXMATE_OPENROUTER_MODEL", "").strip()
    if env_model:
        return env_model
    try:
        import keyring

        return (keyring.get_password(SERVICE_NAME, MODEL_KEY_NAME) or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    except Exception:
        return DEFAULT_MODEL


def save_model(model: str) -> None:
    model = model.strip()
    if not model:
        raise OpenRouterConfigError("Model name cannot be empty.")
    try:
        import keyring

        keyring.set_password(SERVICE_NAME, MODEL_KEY_NAME, model)
    except Exception as exc:
        raise OpenRouterConfigError(
            f"Could not save the AI model setting. {exc}"
        ) from exc


class OpenRouterClient:
    """Synchronous OpenRouter client intended to run inside a QThread."""

    def __init__(self, config: OpenRouterConfig | None = None) -> None:
        self.config = config or self._load_config()

    @staticmethod
    def _load_config() -> OpenRouterConfig:
        api_key = get_saved_api_key()
        if not api_key:
            raise OpenRouterConfigError(
                "OpenRouter API key is not configured. Open Settings → AI Settings "
                "and save your key first."
            )
        return OpenRouterConfig(
            api_key=api_key,
            model=get_saved_model(),
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "X-Title": self.config.app_name,
            "HTTP-Referer": "https://fixmate-ai.local",
        }

    @staticmethod
    def _error_detail(response: requests.Response) -> str:
        try:
            data = response.json()
            error = data.get("error") if isinstance(data, dict) else None
            if isinstance(error, dict):
                message = error.get("message") or error.get("code")
                if message:
                    return str(message)
        except ValueError:
            pass
        text = response.text.strip()
        return text[:900] if text else "No error details were returned."

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1800,
        timeout: int = 75,
    ) -> str:
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = requests.post(
                    self.config.base_url,
                    headers=self._headers(),
                    json=payload,
                    timeout=timeout,
                )
                if response.ok:
                    break

                detail = self._error_detail(response)
                status = response.status_code
                if status in {429, 500, 502, 503, 504} and attempt == 0:
                    time.sleep(1.5)
                    continue
                raise RuntimeError(
                    f"OpenRouter request failed ({status}): {detail}"
                )
            except requests.Timeout as exc:
                last_error = RuntimeError(
                    "OpenRouter timed out. Check your internet connection and try again."
                )
                if attempt == 0:
                    continue
                raise last_error from exc
            except requests.RequestException as exc:
                last_error = RuntimeError(
                    "Could not reach OpenRouter. Check your internet connection and try again."
                )
                if attempt == 0:
                    time.sleep(1.0)
                    continue
                raise last_error from exc
        else:
            raise last_error or RuntimeError("OpenRouter request failed.")

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError("OpenRouter returned invalid JSON.") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("OpenRouter returned an unexpected response.") from exc

        if isinstance(content, list):
            content = "\n".join(
                str(part.get("text", ""))
                for part in content
                if isinstance(part, dict)
            )

        content = str(content).strip()
        if not content:
            raise RuntimeError("OpenRouter returned an empty answer.")
        return content

    def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1800,
        timeout: int = 75,
        cancel_event=None,
        on_response: Callable | None = None,
        on_chunk: Callable[[str], None] | None = None,
    ) -> str:
        """Stream an OpenRouter answer and allow the UI to cancel it."""
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        last_error: Exception | None = None
        for attempt in range(2):
            response = None
            try:
                response = requests.post(
                    self.config.base_url,
                    headers=self._headers(),
                    json=payload,
                    timeout=(10, timeout),
                    stream=True,
                )
                if on_response:
                    on_response(response)

                if not response.ok:
                    detail = self._error_detail(response)
                    status = response.status_code
                    response.close()
                    if status in {429, 500, 502, 503, 504} and attempt == 0:
                        time.sleep(1.0)
                        continue
                    raise RuntimeError(f"OpenRouter request failed ({status}): {detail}")

                parts: list[str] = []
                for raw_line in response.iter_lines(decode_unicode=True):
                    if cancel_event is not None and cancel_event.is_set():
                        response.close()
                        raise OpenRouterCancelled("AI analysis cancelled by user.")
                    if not raw_line:
                        continue
                    line = raw_line.strip()
                    if not line.startswith("data:"):
                        continue
                    data_text = line[5:].strip()
                    if data_text == "[DONE]":
                        break
                    try:
                        data = json.loads(data_text)
                    except Exception:
                        continue
                    choices = data.get("choices") if isinstance(data, dict) else None
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {}) if isinstance(choices[0], dict) else {}
                    content = delta.get("content") if isinstance(delta, dict) else None
                    if not content:
                        continue
                    text = str(content)
                    parts.append(text)
                    if on_chunk:
                        on_chunk(text)

                answer = "".join(parts).strip()
                if not answer:
                    raise RuntimeError("OpenRouter returned an empty answer.")
                return answer
            except OpenRouterCancelled:
                raise
            except requests.Timeout as exc:
                if cancel_event is not None and cancel_event.is_set():
                    raise OpenRouterCancelled("AI analysis cancelled by user.") from exc
                last_error = RuntimeError(
                    "OpenRouter timed out. Check your internet connection and try again."
                )
                if attempt == 0:
                    continue
                raise last_error from exc
            except requests.RequestException as exc:
                if cancel_event is not None and cancel_event.is_set():
                    raise OpenRouterCancelled("AI analysis cancelled by user.") from exc
                last_error = RuntimeError(
                    "Could not reach OpenRouter. Check your internet connection and try again."
                )
                if attempt == 0:
                    time.sleep(1.0)
                    continue
                raise last_error from exc
            finally:
                if response is not None:
                    response.close()
                if on_response:
                    on_response(None)

        raise last_error or RuntimeError("OpenRouter request failed.")

    def test_connection(self, timeout: int = 25) -> str:
        """Make a minimal completion request to verify credentials/model access."""
        return self.chat(
            [
                {
                    "role": "system",
                    "content": "Reply with exactly: FixMate AI connection OK",
                },
                {"role": "user", "content": "Connection test."},
            ],
            temperature=0,
            max_tokens=20,
            timeout=timeout,
        )
