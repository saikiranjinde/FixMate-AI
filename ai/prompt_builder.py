from __future__ import annotations

import json
from typing import Any


SYSTEM_PROMPT = """You are FixMate-AI, a concise Windows PC diagnostic assistant.
Use ONLY the supplied diagnostic evidence. Never invent faults, causes, temperatures, or fixes.
Answer in simple language for a normal PC user. Keep responses brief and practical.
Do not treat unknown/elevation-related Windows checks as corruption.
Problem Code 0 is not proof of hardware failure.
Never suggest dangerous registry edits, deleting system files, or disabling security software.
"""


# Keep only high-value evidence to reduce token usage.
IMPORTANT_KEYS = {
    "system", "hardware", "diagnostics", "top_cpu", "top_memory", "gpu",
    "thermal", "storage", "battery", "drivers", "network", "windows_health",
    "startup", "faults", "severity", "recommendations", "diagnosis_report",
}


def _compact(value: Any, depth: int = 0) -> Any:
    if depth > 3:
        return "[truncated]"
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key_s = str(key)
            if key_s.lower() in {"serial", "serial_number", "device_id", "raw_output", "stdout", "stderr"}:
                continue
            result[key_s] = _compact(item, depth + 1)
        return result
    if isinstance(value, list):
        return [_compact(item, depth + 1) for item in value[:15]]
    if isinstance(value, str):
        return value if len(value) <= 700 else value[:700] + "..."
    return value


def build_diagnostic_evidence(result: dict[str, Any]) -> dict[str, Any]:
    selected = {}
    for key in IMPORTANT_KEYS:
        if key in result:
            selected[key] = result[key]

    # Faults + severity + recommendations are the most important AI inputs.
    return _compact(selected)


def build_diagnostic_prompt(result: dict[str, Any]) -> str:
    evidence = build_diagnostic_evidence(result)
    encoded = json.dumps(evidence, separators=(",", ":"), ensure_ascii=False, default=str)
    # Hard cap so a large scan never creates a huge prompt.
    if len(encoded) > 12000:
        encoded = encoded[:12000] + "...[truncated]"

    return f"""Give a SIMPLE, SHORT diagnosis for this Windows PC.

Use exactly these sections:
1. Result - 1 or 2 sentences
2. Problems - only real actionable problems; write "None" when there are none
3. Fix - numbered steps, maximum 4 steps per problem
4. Check - one short sentence explaining how to verify the fix

Rules:
- Mention only evidence-backed issues.
- If the PC is healthy, say so clearly.
- Do not repeat all hardware specifications.
- Do not explain technical details unless they help the user fix something.
- Keep the complete answer under 250 words.

Diagnostic evidence:
{encoded}"""


def build_chat_messages(
    result: dict[str, Any],
    conversation: list[dict[str, str]],
    user_message: str,
) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.append({"role": "user", "content": build_diagnostic_prompt(result)})
    for message in conversation[-4:]:
        if message.get("role") in {"user", "assistant"}:
            messages.append({
                "role": message["role"],
                "content": str(message.get("content", ""))[:1800],
            })
    messages.append({"role": "user", "content": user_message[:1800]})
    return messages
