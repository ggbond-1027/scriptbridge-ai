from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol


class RedisLike(Protocol):
    def lpush(self, name: str, *values: str) -> int: ...
    def brpop(self, keys: str | list[str], timeout: int = 0): ...
    def llen(self, name: str) -> int: ...


@dataclass(frozen=True)
class RedisBrokerConfig:
    url: str
    queue_name: str = "scriptbridge:jobs:default"
    pop_timeout_seconds: int = 1


class RedisBroker:
    def __init__(self, config: RedisBrokerConfig, client: RedisLike | None = None):
        self.config = config
        self._client = client

    @property
    def enabled(self) -> bool:
        return bool(self.config.url)

    def push_job(self, job_id: str) -> int:
        if not self.enabled:
            raise RuntimeError("Redis broker is not configured.")
        return self.client.lpush(self.config.queue_name, job_id)

    def pop_job(self) -> str | None:
        if not self.enabled:
            return None
        result = self.client.brpop(self.config.queue_name, timeout=self.config.pop_timeout_seconds)
        if not result:
            return None
        if isinstance(result, tuple) and len(result) == 2:
            _, raw_job_id = result
        else:
            raw_job_id = result
        if isinstance(raw_job_id, bytes):
            return raw_job_id.decode("utf-8")
        return str(raw_job_id)

    def depth(self) -> int:
        if not self.enabled:
            return 0
        return int(self.client.llen(self.config.queue_name))

    @property
    def client(self) -> RedisLike:
        if self._client is None:
            try:
                import redis
            except ImportError as exc:
                raise RuntimeError("redis package is required when JOB_BROKER_URL or REDIS_URL is configured.") from exc
            self._client = redis.Redis.from_url(self.config.url, decode_responses=False)
        return self._client


def redis_broker_config() -> RedisBrokerConfig:
    raw_timeout = os.getenv("JOB_BROKER_POP_TIMEOUT_SECONDS", "1").strip()
    try:
        timeout = max(0, min(30, int(raw_timeout)))
    except ValueError:
        timeout = 1
    return RedisBrokerConfig(
        url=(os.getenv("JOB_BROKER_URL") or os.getenv("REDIS_URL") or "").strip(),
        queue_name=os.getenv("JOB_BROKER_QUEUE", "scriptbridge:jobs:default").strip() or "scriptbridge:jobs:default",
        pop_timeout_seconds=timeout,
    )


def configured_redis_broker() -> RedisBroker:
    return RedisBroker(redis_broker_config())
