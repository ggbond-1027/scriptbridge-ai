from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Awaitable, Callable

from fastapi import BackgroundTasks

from .jobs import run_generation_job, run_import_job, run_rewrite_job
from .model_profiles import resolve_runtime_profile
from .models import (
    JobQueueMode,
    JobQueueStatus,
    JobRecord,
    StartRewriteJobRequest,
    WorkerStatus,
    utc_now,
)
from .redis_broker import RedisBroker, configured_redis_broker
from .storage import (
    claim_job,
    claim_next_job,
    get_job,
    list_queued_jobs,
    list_worker_statuses,
    mark_job_dead_lettered,
    queue_counts,
    record_worker_status,
    save_job,
)


WorkerMap = dict[str, Callable[[JobRecord], Awaitable[None]]]


@dataclass(frozen=True)
class WorkerLoopResult:
    worker: WorkerStatus
    processed: int


def configured_queue_mode() -> JobQueueMode:
    raw = os.getenv("JOB_QUEUE_MODE", "background").strip().lower()
    if raw in {"inline", "background", "external"}:
        return raw  # type: ignore[return-value]
    return "background"


async def dispatch_job(
    job: JobRecord,
    *,
    background_tasks: BackgroundTasks | None = None,
) -> JobRecord:
    if job.queue_mode == "inline":
        await execute_job(job.id)
        return get_job(job.id)
    if job.queue_mode == "background":
        if background_tasks is None:
            raise RuntimeError("background queue mode requires BackgroundTasks.")
        background_tasks.add_task(execute_job, job.id)
    if job.queue_mode == "external":
        broker = configured_redis_broker()
        if broker.enabled:
            broker.push_job(job.id)
    return job


async def execute_job(job_id: str) -> JobRecord:
    job = get_job(job_id)
    if job.status != "queued":
        return job
    if job.attempts >= job.max_attempts:
        return mark_job_dead_lettered(
            job.id,
            "Job reached max attempts before execution.",
            source=job.locked_by or "queue",
        )
    job.attempts += 1
    save_job(job)
    if job.kind == "generate":
        use_llm = bool(job.request_payload.get("use_llm", True))
        model_profile = resolve_runtime_profile(job.id, job.request_payload.get("model_profile"))
        await run_generation_job(job.id, use_llm, model_profile=model_profile)
    elif job.kind == "rewrite":
        payload = StartRewriteJobRequest.model_validate(job.request_payload)
        model_profile = resolve_runtime_profile(job.id, job.request_payload.get("model_profile"))
        if model_profile:
            payload = payload.model_copy(update={"model_profile": model_profile})
        await run_rewrite_job(job.id, payload)
    elif job.kind == "import":
        await run_import_job(job.id)
    else:
        mark_job_dead_lettered(job.id, f"Unsupported job kind: {job.kind}", source=job.locked_by or "queue")
    completed = get_job(job.id)
    if completed.status == "failed" and completed.attempts >= completed.max_attempts:
        return mark_job_dead_lettered(
            completed.id,
            completed.error or "Job failed after max attempts.",
            source=completed.locked_by or "queue",
        )
    return completed


async def work_one(worker_id: str = "local-worker", broker: RedisBroker | None = None) -> JobRecord | None:
    broker = broker or configured_redis_broker()
    job = None
    if broker.enabled:
        for _ in range(5):
            job_id = broker.pop_job()
            if not job_id:
                break
            job = claim_job(job_id, worker_id, queue_mode="external")
            if job:
                break
        if not job:
            return None
    else:
        job = claim_next_job(worker_id, queue_mode="external")
    if not job:
        return None
    status = _worker_status(worker_id, status="running", current_job_id=job.id)
    record_worker_status(status)
    try:
        completed = await execute_job(job.id)
    except Exception as exc:
        status.status = "error"
        status.current_job_id = job.id
        status.last_error = str(exc)
        record_worker_status(status)
        raise
    status.status = "idle"
    status.current_job_id = None
    if completed.status == "succeeded":
        status.completed_jobs += 1
    elif completed.status in {"failed", "dead_lettered"}:
        status.failed_jobs += 1
        status.last_error = completed.error
    record_worker_status(status)
    return completed


async def run_worker_loop(
    worker_id: str = "scriptbridge-worker",
    *,
    max_jobs: int | None = None,
    idle_sleep_seconds: float | None = None,
    broker: RedisBroker | None = None,
) -> WorkerLoopResult:
    sleep_seconds = idle_sleep_seconds if idle_sleep_seconds is not None else _worker_idle_sleep_seconds()
    processed = 0
    worker = _worker_status(worker_id, status="starting")
    record_worker_status(worker)
    try:
        while max_jobs is None or processed < max_jobs:
            job = await work_one(worker_id=worker_id, broker=broker)
            if job:
                processed += 1
                worker = _merge_worker_counts(worker, list_worker_statuses(limit=50), worker_id)
                continue
            worker.status = "idle"
            worker.current_job_id = None
            record_worker_status(worker)
            if max_jobs is not None:
                break
            await asyncio.sleep(sleep_seconds)
    except asyncio.CancelledError:
        worker.status = "stopped"
        worker.current_job_id = None
        record_worker_status(worker)
        raise
    except Exception as exc:
        worker.status = "error"
        worker.last_error = str(exc)
        record_worker_status(worker)
        raise
    worker = _merge_worker_counts(worker, list_worker_statuses(limit=50), worker_id)
    worker.status = "stopped" if max_jobs is not None else worker.status
    worker.current_job_id = None
    record_worker_status(worker)
    return WorkerLoopResult(worker=worker, processed=processed)


def job_queue_status() -> JobQueueStatus:
    counts = queue_counts()
    mode = configured_queue_mode()
    broker = configured_redis_broker()
    broker_depth = 0
    broker_error = ""
    if broker.enabled:
        try:
            broker_depth = broker.depth()
        except RuntimeError as exc:
            broker_error = str(exc)
    external_waiting = len(list_queued_jobs(limit=100, queue_mode="external"))
    if mode == "external":
        if broker.enabled and not broker_error:
            hint = f"Redis broker 模式：任务写入 {broker.config.queue_name}，独立 Worker 或 /api/workers/run-once 可消费。"
        elif broker_error:
            hint = f"外部 Worker 模式已配置 broker，但当前不可用：{broker_error}"
        else:
            hint = "外部 Worker 模式：任务只入队，需要调用 /api/workers/run-once 或独立 Worker 执行。"
    elif mode == "inline":
        hint = "Inline 模式：请求内同步执行，适合测试和本地确定性验证。"
    else:
        hint = "Background 模式：FastAPI 后台任务执行，后续可替换 Redis/Celery/RQ。"
    if external_waiting:
        hint = f"{hint} 当前有 {external_waiting} 个 external 任务等待 Worker。"
    if broker_depth:
        hint = f"{hint} Redis 队列深度 {broker_depth}。"
    return JobQueueStatus(
        mode=mode,
        queued=counts.get("queued", 0),
        running=counts.get("running", 0),
        failed=counts.get("failed", 0),
        dead_lettered=counts.get("dead_lettered", 0),
        succeeded=counts.get("succeeded", 0),
        canceled=counts.get("canceled", 0),
        broker="redis" if broker.enabled else "sqlite",
        broker_queue=broker.config.queue_name if broker.enabled else "sqlite:jobs",
        broker_depth=broker_depth,
        broker_error=broker_error or None,
        workers=list_worker_statuses(limit=10),
        worker_hint=hint,
    )


def _worker_idle_sleep_seconds() -> float:
    raw = os.getenv("WORKER_IDLE_SLEEP_SECONDS", "1").strip()
    try:
        value = float(raw)
    except ValueError:
        return 1.0
    return max(0.05, min(30.0, value))


def _worker_status(
    worker_id: str,
    *,
    status: str,
    current_job_id: str | None = None,
) -> WorkerStatus:
    existing = next((item for item in list_worker_statuses(limit=50) if item.worker_id == worker_id), None)
    if existing:
        return existing.model_copy(
            update={
                "status": status,
                "last_seen_at": utc_now(),
                "current_job_id": current_job_id,
            }
        )
    now = utc_now()
    return WorkerStatus(
        worker_id=worker_id,
        status=status,  # type: ignore[arg-type]
        started_at=now,
        last_seen_at=now,
        current_job_id=current_job_id,
    )


def _merge_worker_counts(worker: WorkerStatus, workers: list[WorkerStatus], worker_id: str) -> WorkerStatus:
    existing = next((item for item in workers if item.worker_id == worker_id), None)
    return existing or worker
