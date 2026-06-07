from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import httpx

from .models import ModelProfileRuntime


@dataclass
class ProviderResult:
    data: dict[str, Any] | None
    provider: str
    status: str
    model: str
    warnings: list[str]


class LLMProvider:
    def __init__(self, profile: ModelProfileRuntime | None = None) -> None:
        self.provider = (profile.provider if profile else os.getenv("LLM_PROVIDER", "api")).lower()
        self.base_url = (profile.base_url if profile else os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.api_key = profile.api_key if profile else os.getenv("OPENAI_API_KEY", "")
        self.model = profile.model if profile else os.getenv("MODEL_NAME", "gpt-5.5")
        self.temperature = profile.temperature if profile else _env_float("MODEL_TEMPERATURE", 0.4)

    async def generate_screenplay_object(self, prompt: str) -> ProviderResult:
        return await self._chat_json(
            prompt=prompt,
            system_prompt="你是专业小说剧本改编助手。只输出一个 JSON 对象，不要输出 Markdown。",
            max_tokens=6000,
        )

    async def rewrite_scene_object(self, prompt: str) -> ProviderResult:
        return await self._chat_json(
            prompt=prompt,
            system_prompt="你是资深剧本编辑。只输出一个 JSON 对象，严格保留原文事实、人物和证据边界。",
            max_tokens=2600,
        )

    async def test_connection(self) -> ProviderResult:
        if self.provider == "fallback":
            return ProviderResult(
                data={"status": "ok"},
                provider="fallback",
                status="fallback",
                model="fallback",
                warnings=["fallback profile 使用本地 deterministic 规则，不调用模型。"],
            )
        return await self._chat_json(
            prompt='请只输出 {"status":"ok"}，用于连接测试。',
            system_prompt="你是模型连接测试器。只输出一个 JSON 对象。",
            max_tokens=64,
            timeout_seconds=8,
        )

    async def _chat_json(
        self,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        timeout_seconds: float = 90,
    ) -> ProviderResult:
        if self.provider not in {"api", "local"}:
            return ProviderResult(
                data=None,
                provider=self.provider,
                status="fallback",
                model="fallback",
                warnings=[f"未知 LLM_PROVIDER={self.provider}，已使用 fallback。"],
            )

        if self.provider == "api" and not self.api_key:
            return ProviderResult(
                data=None,
                provider="api",
                status="fallback",
                model="fallback",
                warnings=["未配置 OPENAI_API_KEY，已使用离线 fallback 生成器。"],
            )

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
                if response.status_code == 400:
                    fallback_payload = dict(payload)
                    fallback_payload.pop("response_format", None)
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=fallback_payload,
                    )
                response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return ProviderResult(
                data=_parse_json_object(content),
                provider=self.provider,
                status="ok",
                model=self.model,
                warnings=[],
            )
        except Exception as exc:  # Provider errors should never break local demo.
            return ProviderResult(
                data=None,
                provider=self.provider,
                status="fallback",
                model="fallback",
                warnings=[f"模型调用失败，已使用 fallback：{type(exc).__name__}: {exc}"],
            )


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _parse_json_object(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))
