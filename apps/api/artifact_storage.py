from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from typing import Protocol
from urllib.parse import quote

try:
    from botocore.config import Config
except ImportError:  # pragma: no cover - exercised through factory error handling.
    Config = None


class ArtifactStorageError(RuntimeError):
    """Raised when the configured artifact storage provider cannot serve a request."""


class ArtifactStorageProvider(Protocol):
    name: str

    def write(self, storage_key: str, content: bytes) -> None:
        ...

    def read(self, storage_key: str) -> bytes:
        ...


def _default_s3_client_factory(**kwargs: Any):
    try:
        import boto3
    except ImportError as exc:
        raise ArtifactStorageError(
            "Delivery artifact S3/MinIO provider requires boto3. "
            "Install apps/api/requirements.txt before using this provider."
        ) from exc
    return boto3.client("s3", **kwargs)


S3_CLIENT_FACTORY: Callable[..., Any] = _default_s3_client_factory


@dataclass(frozen=True)
class _QiniuSdkClient:
    auth: Any
    put_data_fn: Callable[..., Any]

    def upload_token(self, bucket: str, key: str, expires: int) -> str:
        return self.auth.upload_token(bucket, key, expires=expires)

    def put_data(self, upload_token: str, key: str, content: bytes):
        return self.put_data_fn(upload_token, key, content)

    def private_download_url(self, base_url: str, expires: int) -> str:
        return self.auth.private_download_url(base_url, expires=expires)


def _default_qiniu_client_factory(access_key: str, secret_key: str):
    try:
        from qiniu import Auth, put_data
    except ImportError as exc:
        raise ArtifactStorageError(
            "Delivery artifact Qiniu provider requires qiniu. "
            "Install apps/api/requirements.txt before using this provider."
        ) from exc
    return _QiniuSdkClient(auth=Auth(access_key, secret_key), put_data_fn=put_data)


def _default_qiniu_http_get(url: str):
    import httpx

    return httpx.get(url, timeout=30.0)


QINIU_CLIENT_FACTORY: Callable[[str, str], Any] = _default_qiniu_client_factory
QINIU_HTTP_GET: Callable[[str], Any] = _default_qiniu_http_get


@dataclass(frozen=True)
class _S3PathStyleConfig:
    s3: dict[str, str]


@dataclass(frozen=True)
class LocalArtifactStorageProvider:
    root: Path
    name: str = "local"

    def write(self, storage_key: str, content: bytes) -> None:
        path = self._path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def read(self, storage_key: str) -> bytes:
        path = self._path(storage_key)
        if not path.exists():
            raise KeyError(storage_key)
        return path.read_bytes()

    def _path(self, storage_key: str) -> Path:
        root = self.root.resolve()
        path = (root / storage_key).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError("Invalid artifact storage key.")
        return path


@dataclass(frozen=True)
class S3ArtifactStorageProvider:
    name: str
    client: Any
    bucket: str
    key_prefix: str = ""

    def write(self, storage_key: str, content: bytes) -> None:
        key = self._object_key(storage_key)
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=content)
        except Exception as exc:
            raise ArtifactStorageError(f"Failed to write delivery artifact to {self.name}: {exc}") from exc

    def read(self, storage_key: str) -> bytes:
        key = self._object_key(storage_key)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            body = response.get("Body")
            if body is None or not hasattr(body, "read"):
                raise ArtifactStorageError(f"Delivery artifact object body is invalid for key '{key}'.")
            return body.read()
        except KeyError as exc:
            raise KeyError(storage_key) from exc
        except Exception as exc:
            if _is_missing_s3_key_error(exc):
                raise KeyError(storage_key) from exc
            raise ArtifactStorageError(f"Failed to read delivery artifact from {self.name}: {exc}") from exc

    def _object_key(self, storage_key: str) -> str:
        safe_key = _safe_remote_storage_key(storage_key)
        prefix = self.key_prefix.strip().strip("/")
        return f"{prefix}/{safe_key}" if prefix else safe_key


@dataclass(frozen=True)
class QiniuArtifactStorageProvider:
    name: str
    client: Any
    bucket: str
    domain: str
    key_prefix: str = ""
    upload_token_expires: int = 3600
    download_url_expires: int = 3600
    http_get: Callable[[str], Any] = QINIU_HTTP_GET

    def write(self, storage_key: str, content: bytes) -> None:
        key = self._object_key(storage_key)
        try:
            upload_token = self.client.upload_token(self.bucket, key, self.upload_token_expires)
            _, info = self.client.put_data(upload_token, key, content)
            if not _qiniu_upload_succeeded(info):
                raise ArtifactStorageError(f"Qiniu upload failed for key '{key}': {_qiniu_info_message(info)}")
        except ArtifactStorageError:
            raise
        except Exception as exc:
            raise ArtifactStorageError(f"Failed to write delivery artifact to {self.name}: {exc}") from exc

    def read(self, storage_key: str) -> bytes:
        key = self._object_key(storage_key)
        try:
            signed_url = self.client.private_download_url(
                _qiniu_resource_url(self.domain, key),
                self.download_url_expires,
            )
            response = self.http_get(signed_url)
            status_code = int(getattr(response, "status_code", 0) or 0)
            if status_code == 404:
                raise KeyError(storage_key)
            if status_code < 200 or status_code >= 300:
                raise ArtifactStorageError(
                    f"Qiniu download failed for key '{key}' with HTTP {status_code}: "
                    f"{getattr(response, 'text', '')}"
                )
            content = getattr(response, "content", None)
            if not isinstance(content, bytes):
                raise ArtifactStorageError(f"Qiniu download body is invalid for key '{key}'.")
            return content
        except KeyError:
            raise
        except ArtifactStorageError:
            raise
        except Exception as exc:
            raise ArtifactStorageError(f"Failed to read delivery artifact from {self.name}: {exc}") from exc

    def _object_key(self, storage_key: str) -> str:
        safe_key = _safe_remote_storage_key(storage_key)
        prefix = self.key_prefix.strip().strip("/")
        return f"{prefix}/{safe_key}" if prefix else safe_key


@dataclass(frozen=True)
class DeferredRemoteArtifactStorageProvider:
    name: str
    endpoint: str = ""
    bucket: str = ""

    def write(self, storage_key: str, content: bytes) -> None:
        self._raise_unconfigured("write")

    def read(self, storage_key: str) -> bytes:
        self._raise_unconfigured("read")

    def _raise_unconfigured(self, action: str) -> None:
        raise ArtifactStorageError(
            f"Delivery artifact provider '{self.name}' is selected for {action}, "
            "but the production object-storage adapter is not configured yet. "
            "Use DELIVERY_ARTIFACT_PROVIDER=local, or wire this provider to a real SDK/client."
        )


def delivery_artifact_provider(data_dir: Path, provider_name: str | None = None) -> ArtifactStorageProvider:
    provider_name = (provider_name or os.getenv("DELIVERY_ARTIFACT_PROVIDER", "local")).strip().lower() or "local"
    if provider_name == "local":
        configured_root = os.getenv("DELIVERY_ARTIFACT_LOCAL_DIR", "").strip()
        root = Path(configured_root) if configured_root else data_dir / "delivery-artifacts"
        return LocalArtifactStorageProvider(root=root)
    if provider_name in {"s3", "minio"}:
        return _s3_compatible_provider(provider_name)
    if provider_name == "qiniu":
        return _qiniu_provider()
    raise ArtifactStorageError(
        f"Unsupported delivery artifact provider '{provider_name}'. "
        "Supported providers: local, s3, minio, qiniu."
    )


def configured_delivery_artifact_provider_name() -> str:
    return os.getenv("DELIVERY_ARTIFACT_PROVIDER", "local").strip().lower() or "local"


def _s3_compatible_provider(provider_name: str) -> S3ArtifactStorageProvider:
    endpoint_url = os.getenv("DELIVERY_ARTIFACT_ENDPOINT", "").strip() or None
    bucket = os.getenv("DELIVERY_ARTIFACT_BUCKET", "").strip()
    access_key_id = os.getenv("DELIVERY_ARTIFACT_ACCESS_KEY_ID", "").strip()
    secret_access_key = os.getenv("DELIVERY_ARTIFACT_SECRET_ACCESS_KEY", "").strip()
    region = os.getenv("DELIVERY_ARTIFACT_REGION", "").strip() or "us-east-1"
    key_prefix = os.getenv("DELIVERY_ARTIFACT_PREFIX", "").strip()
    force_path_style = _env_bool("DELIVERY_ARTIFACT_FORCE_PATH_STYLE", provider_name == "minio")

    missing = []
    if not bucket:
        missing.append("DELIVERY_ARTIFACT_BUCKET")
    if not access_key_id:
        missing.append("DELIVERY_ARTIFACT_ACCESS_KEY_ID")
    if not secret_access_key:
        missing.append("DELIVERY_ARTIFACT_SECRET_ACCESS_KEY")
    if provider_name == "minio" and not endpoint_url:
        missing.append("DELIVERY_ARTIFACT_ENDPOINT")
    if missing:
        raise ArtifactStorageError(
            f"Delivery artifact provider '{provider_name}' is missing required configuration: "
            + ", ".join(missing)
        )

    client_config = None
    if force_path_style:
        client_config = Config(s3={"addressing_style": "path"}) if Config else _S3PathStyleConfig(
            s3={"addressing_style": "path"}
        )

    client_kwargs: dict[str, Any] = {
        "region_name": region,
        "aws_access_key_id": access_key_id,
        "aws_secret_access_key": secret_access_key,
    }
    if endpoint_url:
        client_kwargs["endpoint_url"] = endpoint_url
    if client_config is not None:
        client_kwargs["config"] = client_config

    client = S3_CLIENT_FACTORY(**client_kwargs)
    return S3ArtifactStorageProvider(
        name=provider_name,
        client=client,
        bucket=bucket,
        key_prefix=key_prefix,
    )


def _qiniu_provider() -> QiniuArtifactStorageProvider:
    bucket = os.getenv("DELIVERY_ARTIFACT_BUCKET", "").strip()
    access_key = os.getenv("DELIVERY_ARTIFACT_QINIU_ACCESS_KEY", "").strip() or os.getenv(
        "DELIVERY_ARTIFACT_ACCESS_KEY_ID", ""
    ).strip()
    secret_key = os.getenv("DELIVERY_ARTIFACT_QINIU_SECRET_KEY", "").strip() or os.getenv(
        "DELIVERY_ARTIFACT_SECRET_ACCESS_KEY", ""
    ).strip()
    domain = (
        os.getenv("DELIVERY_ARTIFACT_QINIU_DOMAIN", "").strip()
        or os.getenv("DELIVERY_ARTIFACT_DOMAIN", "").strip()
        or os.getenv("DELIVERY_ARTIFACT_ENDPOINT", "").strip()
    )
    key_prefix = os.getenv("DELIVERY_ARTIFACT_PREFIX", "").strip()
    upload_token_expires = _env_positive_int("DELIVERY_ARTIFACT_QINIU_UPLOAD_TOKEN_EXPIRES", 3600)
    download_url_expires = _env_positive_int("DELIVERY_ARTIFACT_QINIU_DOWNLOAD_URL_EXPIRES", 3600)

    missing = []
    if not bucket:
        missing.append("DELIVERY_ARTIFACT_BUCKET")
    if not access_key:
        missing.append("DELIVERY_ARTIFACT_QINIU_ACCESS_KEY or DELIVERY_ARTIFACT_ACCESS_KEY_ID")
    if not secret_key:
        missing.append("DELIVERY_ARTIFACT_QINIU_SECRET_KEY or DELIVERY_ARTIFACT_SECRET_ACCESS_KEY")
    if not domain:
        missing.append("DELIVERY_ARTIFACT_QINIU_DOMAIN or DELIVERY_ARTIFACT_DOMAIN")
    if missing:
        raise ArtifactStorageError(
            "Delivery artifact provider 'qiniu' is missing required configuration: " + ", ".join(missing)
        )

    client = QINIU_CLIENT_FACTORY(access_key, secret_key)
    return QiniuArtifactStorageProvider(
        name="qiniu",
        client=client,
        bucket=bucket,
        domain=domain,
        key_prefix=key_prefix,
        upload_token_expires=upload_token_expires,
        download_url_expires=download_url_expires,
        http_get=QINIU_HTTP_GET,
    )


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _env_positive_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ArtifactStorageError(f"{name} must be a positive integer.") from exc
    if parsed <= 0:
        raise ArtifactStorageError(f"{name} must be a positive integer.")
    return parsed


def _safe_remote_storage_key(storage_key: str) -> str:
    cleaned = storage_key.strip().replace("\\", "/")
    parts = [part for part in cleaned.split("/") if part]
    if not cleaned or cleaned.startswith("/") or any(part == ".." or ":" in part for part in parts):
        raise ValueError("Invalid artifact storage key.")
    if len(parts) != len(cleaned.split("/")):
        raise ValueError("Invalid artifact storage key.")
    return "/".join(parts)


def _qiniu_resource_url(domain: str, key: str) -> str:
    normalized_domain = domain.strip().rstrip("/")
    if not normalized_domain.startswith(("http://", "https://")):
        normalized_domain = f"https://{normalized_domain}"
    return f"{normalized_domain}/{quote(key, safe='/')}"


def _qiniu_upload_succeeded(info: Any) -> bool:
    status_code = getattr(info, "status_code", None)
    if status_code is None:
        return False
    return 200 <= int(status_code) < 300


def _qiniu_info_message(info: Any) -> str:
    for attribute in ("text_body", "error", "exception"):
        value = getattr(info, attribute, None)
        if value:
            return str(value)
    return str(info)


def _is_missing_s3_key_error(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        error = response.get("Error") or {}
        code = str(error.get("Code", "")).lower()
        status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code in {"nosuchkey", "notfound", "404"} or status == 404:
            return True
    message = str(exc).lower()
    return "nosuchkey" in message or "not found" in message
