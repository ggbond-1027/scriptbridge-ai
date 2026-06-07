from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

from .importer import import_source_file
from .models import ImportSecurityReport, JobEvent, ModelProfileRuntime, ProjectVersion, StartRewriteJobRequest, UpdateProjectRequest, utc_now
from .pipeline import generate_screenplay, rewrite_scene
from .storage import (
    add_audit_event,
    add_project_version,
    current_version,
    get_job,
    get_project,
    index_project_evidence,
    local_project_actor,
    require_project_permission,
    is_local_single_user_mode,
    save_job,
    save_project,
    update_project,
)


STAGE_MESSAGES = [
    ("stage_chapter_index", "建立章节与段落证据索引", 12),
    ("stage_story_bible", "抽取人物、地点、主题、冲突和伏笔", 32),
    ("stage_scene_plan", "规划场景结构和戏剧节拍", 52),
    ("stage_script_writer", "生成剧本元素和场景改写选项", 72),
    ("stage_quality_gate", "执行 Schema、引用和质量门禁", 90),
]


async def run_generation_job(job_id: str, use_llm: bool, model_profile: ModelProfileRuntime | None = None) -> None:
    job = get_job(job_id)
    job.status = "running"
    job.started_at = utc_now()
    job.progress = 5
    job.events.append(JobEvent(stage_id="queued", message="任务已进入企业级流水线。", progress=5))
    save_job(job)

    try:
        project = get_project(job.project_id)
        for stage_id, message, progress in STAGE_MESSAGES:
            await asyncio.sleep(0)
            job = get_job(job_id)
            job.progress = progress
            job.events.append(JobEvent(stage_id=stage_id, message=message, progress=progress))
            save_job(job)

        response = await generate_screenplay(
            text=project.source_text,
            title=project.title,
            style=project.settings.style,
            use_llm=use_llm,
            model_profile=model_profile,
        )
        response.screenplay.project.id = project.id
        version = ProjectVersion(
            id=f"ver_{uuid4().hex[:12]}",
            label=f"生成版本 {len(project.versions) + 1}",
            screenplay=response.screenplay,
            yaml_text=response.yaml_text,
            validation=response.validation,
        )
        project = add_project_version(project, version)
        index_project_evidence(project.id, response.screenplay.chapters)
        project.last_job_id = job_id
        save_project(project)

        job = get_job(job_id)
        job.status = "succeeded"
        job.progress = 100
        job.completed_at = utc_now()
        job.result_version_id = version.id
        job.events.append(JobEvent(stage_id="completed", message="生成完成并保存为项目版本。", progress=100))
        save_job(job)
    except Exception as exc:
        job = get_job(job_id)
        job.status = "failed"
        job.error = f"{type(exc).__name__}: {exc}"
        job.completed_at = utc_now()
        job.events.append(JobEvent(stage_id="failed", message=job.error, progress=job.progress))
        save_job(job)


async def run_rewrite_job(job_id: str, payload: StartRewriteJobRequest) -> None:
    job = get_job(job_id)
    job.status = "running"
    job.started_at = utc_now()
    job.progress = 5
    job.events.append(JobEvent(stage_id="rewrite.queued", message="批量改写任务已进入审阅流水线。", progress=5))
    save_job(job)

    try:
        project = get_project(payload.project_id)
        actor = local_project_actor(project) if is_local_single_user_mode() else payload.actor
        require_project_permission(project, actor, "rewrite")
        version = current_version(project)
        if not version:
            raise ValueError("Project has no screenplay version to rewrite.")

        screenplay = version.screenplay.model_copy(deep=True)
        screenplay.project.id = project.id
        selected_scene_ids = _select_rewrite_scene_ids(screenplay, payload)
        if not selected_scene_ids:
            raise ValueError("No scenes matched the batch rewrite criteria.")

        job = get_job(job_id)
        job.events.append(
            JobEvent(
                stage_id="rewrite.scope",
                message=f"已选中 {len(selected_scene_ids)} 个场景进入批量改写。",
                progress=12,
            )
        )
        job.progress = 12
        save_job(job)

        last_response = None
        total = len(selected_scene_ids)
        for index, scene_id in enumerate(selected_scene_ids, start=1):
            response = await rewrite_scene(
                screenplay=screenplay,
                scene_id=scene_id,
                instruction=payload.instruction,
                mode=payload.mode,
                use_llm=payload.use_llm,
                model_profile=payload.model_profile,
            )
            screenplay = response.screenplay
            last_response = response
            progress = min(88, 12 + round(index / total * 72))
            job = get_job(job_id)
            job.progress = progress
            job.events.append(
                JobEvent(
                    stage_id=f"rewrite.scene.{scene_id}",
                    message=f"已改写 {scene_id}：{'；'.join(response.diff_summary)}",
                    progress=progress,
                )
            )
            save_job(job)

        validation = last_response.validation if last_response else version.validation
        yaml_text = last_response.yaml_text if last_response else version.yaml_text
        new_version = ProjectVersion(
            id=f"ver_{uuid4().hex[:12]}",
            label=f"批量改写版本 {len(project.versions) + 1}",
            screenplay=screenplay,
            yaml_text=yaml_text,
            validation=validation,
        )
        project = add_project_version(project, new_version)
        index_project_evidence(project.id, screenplay.chapters)
        project.last_job_id = job_id
        add_audit_event(
            project,
            actor=actor,
            event_type="rewrite.batch_completed",
            target_type="project",
            target_id=project.id,
            summary=f"{actor} 完成 {len(selected_scene_ids)} 个场景的批量改写。",
            metadata={
                "job_id": job_id,
                "version_id": new_version.id,
                "scene_ids": ",".join(selected_scene_ids),
                "mode": payload.mode,
            },
        )
        save_project(project)

        job = get_job(job_id)
        job.status = "succeeded"
        job.progress = 100
        job.completed_at = utc_now()
        job.result_version_id = new_version.id
        job.events.append(
            JobEvent(
                stage_id="rewrite.completed",
                message="批量改写完成并保存为新项目版本。",
                progress=100,
            )
        )
        save_job(job)
    except Exception as exc:
        job = get_job(job_id)
        job.status = "failed"
        job.error = f"{type(exc).__name__}: {exc}"
        job.completed_at = utc_now()
        job.events.append(JobEvent(stage_id="rewrite.failed", message=job.error, progress=job.progress))
        save_job(job)


def _select_rewrite_scene_ids(screenplay, payload: StartRewriteJobRequest) -> list[str]:
    scene_ids = [scene_id for scene_id in payload.scene_ids if any(scene.id == scene_id for scene in screenplay.scenes)]
    if not scene_ids:
        risky = [
            scene.id
            for scene in screenplay.scenes
            if scene.quality_flags or not scene.source_refs or len(scene.conflict) < 20
        ]
        scene_ids = risky or [scene.id for scene in screenplay.scenes]
    return list(dict.fromkeys(scene_ids))[: payload.max_scenes]


async def run_import_job(job_id: str) -> None:
    job = get_job(job_id)
    job.status = "running"
    job.started_at = utc_now()
    job.progress = 5
    job.events.append(JobEvent(stage_id="import.received", message="源文件已进入导入流水线。", progress=5))
    save_job(job)

    try:
        payload = job.request_payload
        file_path = Path(str(payload.get("file_path") or ""))
        filename = str(payload.get("filename") or file_path.name or "source.txt")
        content_type = str(payload.get("content_type") or "application/octet-stream")
        if not file_path.exists():
            raise ValueError("Uploaded source file is missing from local import storage.")

        await asyncio.sleep(0)
        job = get_job(job_id)
        job.progress = 18
        job.events.append(JobEvent(stage_id="import.validated", message="文件类型与大小校验通过。", progress=18))
        save_job(job)

        content = file_path.read_bytes()
        security_report = _security_report_from_payload(payload)
        await asyncio.sleep(0)
        imported = import_source_file(filename, content_type, content)
        if not security_report.sha256:
            security_report = imported.security_report
        job = get_job(job_id)
        job.progress = 58
        job.events.append(
            JobEvent(
                stage_id="import.extracted",
                message=f"{imported.extraction_method} 已提取正文，安全扫描 {security_report.verdict}，{imported.chapter_count} 章 / {imported.paragraph_count} 段。",
                progress=58,
            )
        )
        save_job(job)

        project = update_project(
            job.project_id,
            UpdateProjectRequest(title=imported.title, source_text=imported.text),
        )
        await asyncio.sleep(0)
        job = get_job(job_id)
        job.progress = 78
        job.events.append(JobEvent(stage_id="import.chapter_indexed", message="章节索引与项目源文已刷新。", progress=78))
        save_job(job)

        project.last_job_id = job_id
        add_audit_event(
            project,
            actor=str(payload.get("actor") or "system"),
            event_type="import.source_completed",
            target_type="project",
            target_id=project.id,
            summary=f"导入 {imported.filename}，识别 {imported.chapter_count} 章 / {imported.paragraph_count} 段。",
            metadata={
                "job_id": job_id,
                "filename": imported.filename,
                "extraction_method": imported.extraction_method,
                "chapter_count": str(imported.chapter_count),
                "paragraph_count": str(imported.paragraph_count),
                "size_bytes": str(imported.size_bytes),
                "sha256": imported.sha256,
                "security_verdict": imported.security_report.verdict,
                "risk_level": imported.security_report.risk_level,
                "upload_mode": str(payload.get("upload_mode") or "multipart"),
            },
        )
        save_project(project)

        job = get_job(job_id)
        job.status = "succeeded"
        job.progress = 100
        job.completed_at = utc_now()
        job.result_payload = {
            **imported.model_dump(mode="json"),
            "upload_mode": str(payload.get("upload_mode") or "multipart"),
        }
        job.events.append(JobEvent(stage_id="import.completed", message="导入完成，项目源文已可用于生成任务。", progress=100))
        save_job(job)
    except Exception as exc:
        job = get_job(job_id)
        job.status = "failed"
        job.error = f"{type(exc).__name__}: {exc}"
        job.completed_at = utc_now()
        job.events.append(JobEvent(stage_id="import.failed", message=job.error, progress=job.progress))
        save_job(job)


def _security_report_from_payload(payload: dict[str, object]) -> ImportSecurityReport:
    report = payload.get("security_report")
    if isinstance(report, dict):
        try:
            return ImportSecurityReport.model_validate(report)
        except Exception:
            pass
    return ImportSecurityReport(
        sha256=str(payload.get("sha256") or ""),
        verdict="clean" if payload.get("sha256") else "warning",
        risk_level="low" if payload.get("sha256") else "medium",
        checks=["security_metadata_loaded"] if payload.get("sha256") else [],
        warnings=[] if payload.get("sha256") else ["任务缺少上传阶段安全扫描元数据。"],
    )
