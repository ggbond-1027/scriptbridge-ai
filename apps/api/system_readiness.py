from __future__ import annotations

import os
from urllib.parse import urlparse

from .artifact_storage import configured_delivery_artifact_provider_name
from .model_profiles import environment_model_profile, resolve_model_secret
from .queue import configured_queue_mode
from .models import SystemReadinessCheck, SystemReadinessResponse, SystemReadinessStatus


def system_readiness() -> SystemReadinessResponse:
    checks = [
        _database_check(),
        _queue_check(),
        _model_secret_check(),
        _import_security_check(),
        _artifact_storage_check(),
        _auth_check(),
    ]
    blockers = [check for check in checks if check.status == "blocked"]
    warnings = [check for check in checks if check.status == "warning"]
    passed = [check for check in checks if check.status == "ready"]
    score = _score_checks(checks)
    status: SystemReadinessStatus = "ready"
    if blockers:
        status = "blocked"
    elif warnings:
        status = "warning"
    return SystemReadinessResponse(
        status=status,
        score=score,
        environment=_deployment_environment(),
        checks=checks,
        blockers=blockers,
        warnings=warnings,
        passed=passed,
        next_actions=_next_actions(blockers, warnings),
    )


def _database_check() -> SystemReadinessCheck:
    url = _database_url()
    if not url:
        return SystemReadinessCheck(
            id="database",
            label="生产数据库",
            status="blocked",
            summary="当前使用本地 SQLite 数据库，适合本机工作台，不适合企业级多人/多 worker 部署。",
            evidence={"engine": "sqlite", "configured": False},
        )
    parsed = urlparse(url)
    engine = (parsed.scheme or "").split("+", 1)[0]
    if engine in {"postgres", "postgresql"}:
        return SystemReadinessCheck(
            id="database",
            label="生产数据库",
            status="ready",
            summary="已配置 Postgres-compatible DATABASE_URL，可作为生产数据库迁移目标。",
            evidence={"engine": "postgres", "configured": True, "host_configured": bool(parsed.hostname)},
        )
    return SystemReadinessCheck(
        id="database",
        label="生产数据库",
        status="warning",
        summary=f"已配置数据库 URL，但引擎 {engine or 'unknown'} 不是当前推荐的 Postgres 生产目标。",
        evidence={"engine": engine or "unknown", "configured": True},
    )


def _queue_check() -> SystemReadinessCheck:
    mode = configured_queue_mode()
    broker = os.getenv("JOB_BROKER_URL", "").strip() or os.getenv("REDIS_URL", "").strip()
    if mode == "external" and broker:
        parsed = urlparse(broker)
        broker_engine = (parsed.scheme or "").split("+", 1)[0] or "unknown"
        broker_supported = broker_engine in {"redis", "rediss"}
        return SystemReadinessCheck(
            id="queue",
            label="生产任务队列",
            status="ready" if broker_supported else "warning",
            summary=(
                "任务已切换为 external worker 模式，已接入 Redis broker 适配层，并提供独立 worker 进程入口。"
                if broker_supported
                else f"任务已切换为 external worker 模式，但 broker 引擎 {broker_engine} 不是当前实现支持的 Redis。"
            ),
            evidence={
                "mode": mode,
                "broker": broker_engine,
                "broker_configured": True,
                "redis_adapter": broker_supported,
                "queue_name": os.getenv("JOB_BROKER_QUEUE", "scriptbridge:jobs:default").strip()
                or "scriptbridge:jobs:default",
            },
        )
    if mode == "external":
        return SystemReadinessCheck(
            id="queue",
            label="生产任务队列",
            status="warning",
            summary="任务已切换为 external worker 模式，但尚未配置 Redis broker。",
            evidence={"mode": mode, "broker_configured": False},
        )
    return SystemReadinessCheck(
        id="queue",
        label="生产任务队列",
        status="blocked",
        summary="当前任务仍由本地 inline/background 执行，不能代表生产级分布式队列。",
        evidence={"mode": mode, "broker_configured": bool(broker)},
    )


def _model_secret_check() -> SystemReadinessCheck:
    profile = environment_model_profile()
    has_plain_key = bool(os.getenv("OPENAI_API_KEY", "").strip())
    secret_ref = profile.api_key_secret_ref or os.getenv("OPENAI_API_KEY_SECRET_REF", "").strip()
    resolved_secret = resolve_model_secret(secret_ref)
    if secret_ref and resolved_secret:
        return SystemReadinessCheck(
            id="model_secrets",
            label="模型密钥治理",
            status="ready",
            summary="已配置服务端模型密钥引用，运行时可解析真实 key 且不持久化明文。",
            evidence={"provider": profile.provider, "secret_ref_configured": True, "plain_key_configured": has_plain_key},
        )
    if secret_ref:
        return SystemReadinessCheck(
            id="model_secrets",
            label="模型密钥治理",
            status="blocked",
            summary="已设置模型密钥引用，但服务端没有解析到对应密钥。",
            evidence={"provider": profile.provider, "secret_ref_configured": True, "secret_resolved": False},
        )
    if has_plain_key:
        return SystemReadinessCheck(
            id="model_secrets",
            label="模型密钥治理",
            status="warning",
            summary="检测到服务端明文 API key，可运行但不符合最终 Vault/KMS 或 secret_ref 治理标准。",
            evidence={"provider": profile.provider, "secret_ref_configured": False, "plain_key_configured": True},
        )
    return SystemReadinessCheck(
        id="model_secrets",
        label="模型密钥治理",
        status="blocked",
        summary="API 模型未配置服务端密钥引用，生产环境不能依赖浏览器临时 key。",
        evidence={"provider": profile.provider, "secret_ref_configured": False, "plain_key_configured": False},
    )


def _import_security_check() -> SystemReadinessCheck:
    scanner = os.getenv("IMPORT_SECURITY_SCANNER", "local").strip().lower() or "local"
    endpoint = os.getenv("IMPORT_SECURITY_EXTERNAL_ENDPOINT", "").strip()
    unavailable_policy = os.getenv("IMPORT_SECURITY_ON_UNAVAILABLE", "block").strip().lower() or "block"
    if scanner in {"external", "clamav"} and endpoint and unavailable_policy == "block":
        return SystemReadinessCheck(
            id="import_security",
            label="导入安全",
            status="ready",
            summary="导入链路已配置外部/ClamAV 风格扫描，并采用扫描器不可用时阻断策略。",
            evidence={"scanner": scanner, "external_endpoint_configured": True, "on_unavailable": unavailable_policy},
        )
    if scanner in {"external", "clamav"} and endpoint:
        return SystemReadinessCheck(
            id="import_security",
            label="导入安全",
            status="warning",
            summary="导入链路已配置外部扫描，但扫描器不可用时不是 fail-closed。",
            evidence={"scanner": scanner, "external_endpoint_configured": True, "on_unavailable": unavailable_policy},
        )
    return SystemReadinessCheck(
        id="import_security",
        label="导入安全",
        status="warning",
        summary="当前只有本地静态扫描，缺少生产级外部病毒扫描/隔离区接入。",
        evidence={"scanner": scanner, "external_endpoint_configured": False, "on_unavailable": unavailable_policy},
    )


def _artifact_storage_check() -> SystemReadinessCheck:
    provider = configured_delivery_artifact_provider_name()
    if provider in {"s3", "minio"}:
        missing = _missing_env(
            "DELIVERY_ARTIFACT_BUCKET",
            "DELIVERY_ARTIFACT_ACCESS_KEY_ID",
            "DELIVERY_ARTIFACT_SECRET_ACCESS_KEY",
        )
        if provider == "minio" and not os.getenv("DELIVERY_ARTIFACT_ENDPOINT", "").strip():
            missing.append("DELIVERY_ARTIFACT_ENDPOINT")
        return _remote_artifact_check(provider, missing)
    if provider == "qiniu":
        missing = _missing_env("DELIVERY_ARTIFACT_BUCKET", "DELIVERY_ARTIFACT_QINIU_DOMAIN")
        if not (
            os.getenv("DELIVERY_ARTIFACT_QINIU_ACCESS_KEY", "").strip()
            or os.getenv("DELIVERY_ARTIFACT_ACCESS_KEY_ID", "").strip()
        ):
            missing.append("DELIVERY_ARTIFACT_QINIU_ACCESS_KEY")
        if not (
            os.getenv("DELIVERY_ARTIFACT_QINIU_SECRET_KEY", "").strip()
            or os.getenv("DELIVERY_ARTIFACT_SECRET_ACCESS_KEY", "").strip()
        ):
            missing.append("DELIVERY_ARTIFACT_QINIU_SECRET_KEY")
        return _remote_artifact_check(provider, missing)
    return SystemReadinessCheck(
        id="artifact_storage",
        label="交付对象存储",
        status="warning",
        summary="当前交付包使用本地 artifact store，适合本机验证，不适合作为企业交付资产库。",
        evidence={"provider": provider, "remote_configured": False},
    )


def _auth_check() -> SystemReadinessCheck:
    auth_mode = os.getenv("AUTH_MODE", "local-session").strip().lower() or "local-session"
    signing_secret = os.getenv("DELIVERY_SIGNING_SECRET", "").strip()
    if auth_mode in {"sso", "oidc"} and signing_secret:
        return SystemReadinessCheck(
            id="auth",
            label="认证与签名",
            status="ready",
            summary="已声明 SSO/OIDC 认证模式，并配置交付签名密钥。",
            evidence={"auth_mode": auth_mode, "delivery_signing_secret_configured": True},
        )
    if signing_secret:
        return SystemReadinessCheck(
            id="auth",
            label="认证与签名",
            status="warning",
            summary="已配置交付签名密钥，但认证仍是本地项目成员会话，不是 SSO/OIDC。",
            evidence={"auth_mode": auth_mode, "delivery_signing_secret_configured": True},
        )
    return SystemReadinessCheck(
        id="auth",
        label="认证与签名",
        status="blocked",
        summary="缺少交付签名密钥，且认证仍是本地项目成员会话。",
        evidence={"auth_mode": auth_mode, "delivery_signing_secret_configured": False},
    )


def _database_url() -> str:
    return (
        os.getenv("DATABASE_URL", "").strip()
        or os.getenv("POSTGRES_DSN", "").strip()
        or os.getenv("SCRIPTBRIDGE_DATABASE_URL", "").strip()
    )


def _deployment_environment() -> str:
    return os.getenv("SCRIPTBRIDGE_ENV", "").strip() or os.getenv("APP_ENV", "").strip() or "local"


def _missing_env(*names: str) -> list[str]:
    return [name for name in names if not os.getenv(name, "").strip()]


def _remote_artifact_check(provider: str, missing: list[str]) -> SystemReadinessCheck:
    if not missing:
        return SystemReadinessCheck(
            id="artifact_storage",
            label="交付对象存储",
            status="ready",
            summary=f"交付包已配置 {provider} 远端对象存储 provider。",
            evidence={"provider": provider, "remote_configured": True},
        )
    return SystemReadinessCheck(
        id="artifact_storage",
        label="交付对象存储",
        status="blocked",
        summary=f"已选择 {provider} 交付对象存储，但缺少必要配置。",
        evidence={"provider": provider, "remote_configured": False, "missing_count": len(missing)},
    )


def _score_checks(checks: list[SystemReadinessCheck]) -> int:
    if not checks:
        return 0
    values = {"ready": 100, "warning": 55, "blocked": 0}
    return round(sum(values[check.status] for check in checks) / len(checks))


def _next_actions(
    blockers: list[SystemReadinessCheck],
    warnings: list[SystemReadinessCheck],
) -> list[str]:
    actions: list[str] = []
    for check in [*blockers, *warnings]:
        if check.id == "database":
            actions.append("配置 DATABASE_URL 指向 Postgres，并迁移 SQLite payload 表。")
        elif check.id == "queue":
            actions.append("配置 JOB_QUEUE_MODE=external 和 JOB_BROKER_URL/REDIS_URL，并接入独立 worker。")
        elif check.id == "model_secrets":
            actions.append("改用 OPENAI_API_KEY_SECRET_REF + MODEL_SECRET_<REF>，避免浏览器或明文 key 路径。")
        elif check.id == "import_security":
            actions.append("接入外部/ClamAV 扫描服务，并保持 IMPORT_SECURITY_ON_UNAVAILABLE=block。")
        elif check.id == "artifact_storage":
            actions.append("配置 s3/minio/qiniu 交付对象存储 provider，避免正式包只落本地磁盘。")
        elif check.id == "auth":
            actions.append("配置 DELIVERY_SIGNING_SECRET，并规划 AUTH_MODE=sso/oidc。")
    return list(dict.fromkeys(actions))[:6]
