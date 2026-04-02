from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

import requests


class ModelClientError(RuntimeError):
    pass


class PlanningModel(Protocol):
    def plan_task(self, prompt: str, mode: str, tool_names: list[str]) -> dict[str, Any]:
        ...


def _extract_json_block(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0]

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ModelClientError("Model response did not contain a JSON object.")

    return json.loads(cleaned[start : end + 1])


def _planner_system_prompt(tool_names: list[str]) -> str:
    return (
        "You are the planner for a desktop computer-use agent. "
        "Return JSON only with keys summary and stepGroups. "
        "Each stepGroups item must be an array of step objects containing title, goal, toolName, toolArgs, verificationTarget, and fallbackNote. "
        f"Only use these tool names: {', '.join(tool_names)}. "
        "Never include shell commands or tools outside the whitelist."
    )


@dataclass(slots=True)
class NvidiaChatModel:
    endpoint: str
    api_key: str
    model_name: str
    max_tokens: int = 4096
    temperature: float = 0.2
    top_p: float = 0.9
    top_k: int = 50

    @classmethod
    def from_env(cls) -> "NvidiaChatModel | None":
        endpoint = os.getenv("OPEN_COLLAR_MODEL_ENDPOINT")
        api_key = os.getenv("OPEN_COLLAR_MODEL_API_KEY")
        model_name = os.getenv("OPEN_COLLAR_MODEL_NAME", "google/gemma-4-31b-it")
        if not endpoint or not api_key:
            return None
        return cls(endpoint=endpoint, api_key=api_key, model_name=model_name)

    def plan_task(self, prompt: str, mode: str, tool_names: list[str]) -> dict[str, Any]:
        response = requests.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            },
            json={
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": _planner_system_prompt(tool_names)},
                    {"role": "user", "content": f"Mode: {mode}\nTask: {prompt}"},
                ],
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "top_k": self.top_k,
                "stream": False,
                "chat_template_kwargs": {"enable_thinking": True},
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        choices = payload.get("choices") or []
        if not choices:
            raise ModelClientError("Model response contained no choices.")

        content = choices[0].get("message", {}).get("content", "")
        if not content:
            raise ModelClientError("Model response contained no message content.")

        return _extract_json_block(content)


@dataclass(slots=True)
class GeminiChatModel:
    api_key: str
    model_name: str
    base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    temperature: float = 0.2
    max_output_tokens: int = 4096

    def plan_task(self, prompt: str, mode: str, tool_names: list[str]) -> dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/models/{self.model_name}:generateContent",
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            json={
                "generationConfig": {
                    "temperature": self.temperature,
                    "maxOutputTokens": self.max_output_tokens,
                    "responseMimeType": "application/json",
                },
                "systemInstruction": {
                    "parts": [{"text": _planner_system_prompt(tool_names)}],
                },
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": f"Mode: {mode}\nTask: {prompt}"}],
                    }
                ],
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        candidates = payload.get("candidates") or []
        if not candidates:
            raise ModelClientError("Gemini response contained no candidates.")

        parts = candidates[0].get("content", {}).get("parts") or []
        text = "".join(str(part.get("text", "")) for part in parts if part.get("text"))
        if not text:
            raise ModelClientError("Gemini response contained no text content.")

        return _extract_json_block(text)


def create_model_client(model_config: dict[str, Any] | None) -> PlanningModel | None:
    config = dict(model_config or {})
    provider = str(config.get("provider") or "deterministic")

    if provider == "deterministic":
        return None

    if provider == "gemini":
        api_key = str(config.get("apiKey") or "").strip()
        model_name = str(config.get("modelName") or "").strip()
        if not api_key:
            raise ModelClientError("Gemini requires an API key entered by the user.")
        if not model_name:
            raise ModelClientError("Gemini requires a selected model name.")
        return GeminiChatModel(api_key=api_key, model_name=model_name)

    if provider == "nvidia":
        return NvidiaChatModel.from_env()

    raise ModelClientError(f"Unsupported model provider: {provider}")
