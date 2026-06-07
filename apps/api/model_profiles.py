from __future__ import annotations

import os
from time import perf_counter
from typing import Any

from .llm_provider import LLMProvider
from .models import (
    ModelProfilePublic,
    ModelProfileResponse,
    ModelProfileRuntime,
    ModelProfileTestResponse,
)


_RUNTIME_PROFILES: dict[str, ModelProfileRuntime] = {}


def environment_model_profile() -> ModelProfileRuntime:
    profile = ModelProfileRuntime(
        provider=_normalized_provider(os.getenv("LLM_PROVIDER", "api")),
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        model=os.getenv("MODEL_NAME", "gpt-5.5"),
        api_key=os.getenv("OPENAI_API_KEY") or None,
        api_key_secret_ref=os.getenv("OPENAI_API_KEY_SECRET_REF") or None,
        temperature=_env_float("MODEL_TEMPERATURE", 0.4),
    )
    return resolve_profile_secrets(profile)


def model_profile_response() -> ModelProfileResponse:
    active = environment_model_profile().to_public(source="environment")
    presets = [
        active,
        ModelProfilePublic(
            provider="local",
            base_url=os.getenv("LOCAL_OPENAI_BASE_URL", "http://127.0.0.1:11434/v1"),
            model=os.getenv("LOCAL_MODEL_NAME", "qwen2.5:14b"),
            temperature=0.4,
            has_api_key=False,
            source="environment",
        ),
        ModelProfilePublic(
            provider="fallback",
            base_url="local://deterministic-fallback",
            model="fallback",
            temperature=0,
            has_api_key=False,
            source="fallback",
        ),
    ]
    warnings = []
    if active.provider == "api" and not active.has_api_key:
        warnings.append("当前 API profile 未检测到 OPENAI_API_KEY，运行时可临时输入 key 或使用 fallback。")
    return ModelProfileResponse(active=active, presets=presets, warnings=warnings)


async def test_model_profile(profile: ModelProfileRuntime) -> ModelProfileTestResponse:
    profile = resolve_profile_secrets(profile)
    start = perf_counter()
    result = await LLMProvider(profile).test_connection()
    latency_ms = max(0, round((perf_counter() - start) * 1000))
    ok = result.status == "ok" or profile.provider == "fallback"
    message = "连接测试通过。" if result.status == "ok" else _connection_message(profile, result.warnings)
    return ModelProfileTestResponse(
        profile=profile.to_public(source="runtime"),
        ok=ok,
        status="ok" if ok else "failed",
        provider_status=result.status,
        latency_ms=latency_ms,
        message=message,
        warnings=result.warnings,
    )


def remember_runtime_profile(job_id: str, profile: ModelProfileRuntime | None) -> None:
    if profile:
        resolved = resolve_profile_secrets(profile)
        if resolved.api_key:
            _RUNTIME_PROFILES[job_id] = resolved


def resolve_runtime_profile(job_id: str, payload_profile: Any) -> ModelProfileRuntime | None:
    if job_id in _RUNTIME_PROFILES:
        return _RUNTIME_PROFILES[job_id]
    if not payload_profile:
        return None
    return resolve_profile_secrets(ModelProfileRuntime.model_validate(payload_profile))


def sanitize_payload(payload: Any) -> dict[str, object]:
    data = payload.model_dump(mode="json")
    profile = getattr(payload, "model_profile", None)
    if profile:
        data["model_profile"] = profile.to_public(source="runtime").model_dump(mode="json")
    return data


def public_profile(profile: ModelProfileRuntime | None) -> ModelProfilePublic | None:
    return profile.to_public(source="runtime") if profile else None


def resolve_profile_secrets(profile: ModelProfileRuntime | None) -> ModelProfileRuntime | None:
    if not profile or profile.api_key or not profile.api_key_secret_ref:
        return profile
    secret = resolve_model_secret(profile.api_key_secret_ref)
    if not secret:
        return profile
    return profile.model_copy(update={"api_key": secret})


def resolve_model_secret(secret_ref: str | None) -> str | None:
    ref = _normalized_secret_ref(secret_ref)
    if not ref:
        return None
    candidates = [
        f"MODEL_SECRET_{ref}",
        f"MODEL_SECRET_REF_{ref}",
        f"OPENAI_API_KEY_{ref}",
    ]
    for name in candidates:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return None


def _normalized_provider(value: str) -> str:
    provider = (value or "api").strip().lower()
    return provider if provider in {"api", "local", "fallback"} else "fallback"


def _normalized_secret_ref(value: str | None) -> str:
    raw = (value or "").strip().upper()
    normalized = "".join(ch if ch.isalnum() else "_" for ch in raw)
    normalized = "_".join(part for part in normalized.split("_") if part)
    return normalized


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _connection_message(profile: ModelProfileRuntime, warnings: list[str]) -> str:
    if profile.provider == "api" and not profile.api_key:
        if profile.api_key_secret_ref:
            return f"API profile 的密钥引用 {profile.api_key_secret_ref} 未解析到服务端密钥。"
        return "API profile 缺少 key，未发起远程模型调用。"
    return warnings[0] if warnings else "连接测试失败。"
