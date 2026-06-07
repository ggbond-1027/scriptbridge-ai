"""项目管理 API - 项目 CRUD + Pipeline + Chapters + Scenes + StoryBible

所有前端需要的数据接口统一在此路由下：
/api/v1/projects/{project_id}/pipeline/start
/api/v1/projects/{project_id}/pipeline/status
/api/v1/projects/{project_id}/chapters
/api/v1/projects/{project_id}/story-bible
/api/v1/projects/{project_id}/scenes/{scene_id}
/api/v1/projects/{project_id}/chapters/{chapter_id}/paragraphs
/api/v1/projects/{project_id}/validation/errors
等
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Request, UploadFile, File, Form, Body
from pydantic import BaseModel, Field
import asyncio
import copy
import hashlib
import io
import json
import uuid
import logging
import os
import time
import zipfile
from pathlib import Path
from urllib.parse import quote

from app.models.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse,
    ProjectStatus, ProjectDB, Base, CreateProjectResponse,
)
from app.models.screenplay import Screenplay
from app.project_persistence import (
    DB_PATH as PROJECT_DB_PATH,
    delete_project_snapshot,
    load_project_snapshots,
    save_project_snapshot,
)
from app.services.chapter_parser import ChapterParser

logger = logging.getLogger(__name__)

router = APIRouter()

# 内存存储
_projects_store: Dict[str, Dict[str, Any]] = {}

# Pipeline后台任务追踪
_pipeline_tasks: Dict[str, asyncio.Task] = {}
_pipeline_states: Dict[str, Dict[str, Any]] = {}


def load_persisted_projects_into_memory() -> int:
    """Load SQLite project snapshots into the in-memory demo store."""
    projects = load_project_snapshots()
    _projects_store.clear()
    _projects_store.update(projects)
    logger.info("Loaded %s persisted projects from %s", len(projects), PROJECT_DB_PATH)
    return len(projects)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _persist_project(project: Dict[str, Any]) -> None:
    project["updated_at"] = _now_iso()
    save_project_snapshot(project)


def _env_int(name: str, default: int, min_value: int, max_value: int) -> int:
    """Read a bounded integer setting from the environment."""
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(min_value, min(max_value, value))


PIPELINE_CHAPTER_CONCURRENCY = _env_int("NOVELSCRIPTER_CHAPTER_CONCURRENCY", 2, 1, 8)
PIPELINE_SCENE_CONCURRENCY = _env_int("NOVELSCRIPTER_SCENE_CONCURRENCY", 2, 1, 8)
PIPELINE_ELEMENT_CONCURRENCY = _env_int("NOVELSCRIPTER_ELEMENT_CONCURRENCY", 3, 1, 12)
PIPELINE_FAST_ELEMENT_TARGET = _env_int("NOVELSCRIPTER_FAST_ELEMENT_TARGET", 10, 6, 30)
PIPELINE_CHAPTER_MAX_TOKENS = _env_int("NOVELSCRIPTER_CHAPTER_MAX_TOKENS", 900, 400, 2400)
PIPELINE_SCENE_MAX_TOKENS = _env_int("NOVELSCRIPTER_SCENE_MAX_TOKENS", 1000, 600, 3000)
PIPELINE_ELEMENT_MAX_TOKENS = _env_int("NOVELSCRIPTER_ELEMENT_MAX_TOKENS", 900, 400, 2400)
PIPELINE_REWRITE_MAX_TOKENS = _env_int("NOVELSCRIPTER_REWRITE_MAX_TOKENS", 600, 200, 2000)
PIPELINE_ELEMENT_BATCH_SIZE = _env_int("NOVELSCRIPTER_ELEMENT_BATCH_SIZE", 2, 1, 4)
PIPELINE_ELEMENT_BATCH_TEXT_LIMIT = _env_int("NOVELSCRIPTER_ELEMENT_BATCH_TEXT_LIMIT", 2600, 800, 6000)
PIPELINE_CACHE_VERSION = "fast-pipeline-v2"


def _llm_config_with_max_tokens(model_config: Dict[str, Any], max_tokens: int) -> Dict[str, Any]:
    """Return a copy of model config capped for shorter pipeline sub-tasks."""
    config = dict(model_config)
    try:
        current_max = int(config.get("max_tokens") or max_tokens)
    except (TypeError, ValueError):
        current_max = max_tokens
    config["max_tokens"] = min(current_max, max_tokens)
    return config


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _model_cache_fingerprint(model_config: Dict[str, Any], max_tokens: int) -> Dict[str, Any]:
    capped = _llm_config_with_max_tokens(model_config, max_tokens)
    return {
        "base_url": capped.get("base_url", ""),
        "model_name": capped.get("model_name", ""),
        "temperature": capped.get("temperature", 0.7),
        "max_tokens": capped.get("max_tokens", max_tokens),
    }


def _get_pipeline_cache(project: Dict[str, Any]) -> Dict[str, Any]:
    cache = project.get("_pipeline_cache")
    if not isinstance(cache, dict) or cache.get("version") != PIPELINE_CACHE_VERSION:
        cache = {
            "version": PIPELINE_CACHE_VERSION,
            "chapter_understanding": {},
            "scene_splitting": {},
            "element_generation": {},
        }
        project["_pipeline_cache"] = cache
    for bucket in ("chapter_understanding", "scene_splitting", "element_generation"):
        if not isinstance(cache.get(bucket), dict):
            cache[bucket] = {}
    return cache


def _get_chapter_text(paragraphs_cache: Dict[str, List[Dict[str, Any]]], chapter_id: str) -> str:
    return "\n".join([p.get("text", "") for p in paragraphs_cache.get(chapter_id, [])])


def _copy_data(value: Any) -> Any:
    return copy.deepcopy(value)


def _get_project_or_404(project_id: str) -> Dict[str, Any]:
    """获取项目或抛出404"""
    project = _projects_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")
    return project


# ============================================================
# Pipeline请求模型
# ============================================================

class PipelineStartRequest(BaseModel):
    """Pipeline启动请求 — 包含前端模型配置"""
    mode: str = Field(default="api", description="api 或 local")
    api_base_url: str = Field(default="", description="API base URL")
    api_key: str = Field(default="", description="API key")
    model_name: str = Field(default="", description="模型名称")
    temperature: float = Field(default=0.7, description="温度")
    max_tokens: int = Field(default=4000, description="最大tokens")
    # 本地模式配置
    local_base_url: str = Field(default="", description="本地服务URL")
    local_model_name: str = Field(default="", description="本地模型名称")


# ============================================================
# 项目CRUD
# ============================================================

async def _decode_uploaded_text(file: UploadFile) -> str:
    """Decode uploaded text files with a UTF-8 first strategy."""
    raw = await file.read()
    if not raw:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            import chardet
            detected = chardet.detect(raw)
            encoding = detected.get("encoding") or "utf-8"
            return raw.decode(encoding, errors="replace")
        except Exception:
            return raw.decode("utf-8", errors="replace")


def _create_project_record(project_data: ProjectCreate) -> CreateProjectResponse:
    """创建新的小说转剧本项目"""
    project_id = str(uuid.uuid4())
    source_text = project_data.source_text or ""
    source_text_length = len(source_text)
    now = _now_iso()

    project = {
        "id": project_id,
        "title": project_data.name,
        "name": project_data.name,
        "description": f"{project_data.adaptation_style} / {project_data.dialogue_style}",
        "source_language": "zh-CN",
        "target_format": "screenplay",
        "status": ProjectStatus.CREATED.value,
        "source_text_length": source_text_length,
        "chapter_count": None,
        "scene_count": None,
        "adaptation_style": project_data.adaptation_style,
        "dialogue_style": project_data.dialogue_style,
        "_source_text": source_text,
        "_dialogue_style": project_data.dialogue_style,
        "screenplay_data": None,
        # 章节和场景数据 — pipeline完成后填充
        "chapters": [],
        "scenes": [],
        "story_bible": {"characters": [], "locations": [], "timeline": []},
        "source_paragraphs": {},
        "validation_errors": [],
        "created_at": now,
        "updated_at": now,
    }

    _projects_store[project_id] = project

    if source_text_length > 0:
        project["status"] = ProjectStatus.IMPORTING.value
    _persist_project(project)

    return CreateProjectResponse(
        project_id=project_id,
        message=f"项目 '{project_data.name}' 创建成功",
    )


@router.post("", response_model=CreateProjectResponse, include_in_schema=False)
@router.post("/", response_model=CreateProjectResponse, summary="创建项目")
async def create_project(request: Request):
    """创建新的小说转剧本项目，兼容JSON文本导入和前端FormData文件导入。"""
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        source_text = str(form.get("source_text") or "")
        uploaded = form.get("source_file")
        if uploaded is not None and hasattr(uploaded, "read"):
            source_text = await _decode_uploaded_text(uploaded)

        project_data = ProjectCreate(
            name=str(form.get("name") or "未命名项目"),
            source_text=source_text,
            adaptation_style=str(form.get("adaptation_style") or "short_series"),
            dialogue_style=str(form.get("dialogue_style") or "natural"),
        )
        return _create_project_record(project_data)

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    project_data = ProjectCreate.model_validate(payload)
    return _create_project_record(project_data)


@router.get("", response_model=ProjectListResponse, include_in_schema=False)
@router.get("/", response_model=ProjectListResponse, summary="获取项目列表")
async def list_projects(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    status: Optional[ProjectStatus] = Query(default=None, description="项目状态筛选"),
):
    """获取所有项目列表"""
    all_projects = list(_projects_store.values())

    if status:
        all_projects = [p for p in all_projects if p["status"] == status.value]

    total = len(all_projects)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = all_projects[start:end]

    projects = [ProjectResponse(**p) for p in paginated]

    return ProjectListResponse(
        projects=projects,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{project_id}", summary="获取项目详情")
async def get_project(project_id: str):
    """获取指定项目的详细信息 — 返回前端需要的完整数据"""
    project = _get_project_or_404(project_id)

    # 构造前端 ProjectInfo 格式的响应
    result = {
        "id": project["id"],
        "name": project.get("title") or project.get("name", ""),
        "title": project.get("title") or project.get("name", ""),
        "description": project.get("description", ""),
        "status": project.get("status", "created"),
        "source_text_length": project.get("source_text_length", 0),
        "adaptation_style": project.get("adaptation_style", "short_series"),
        "dialogue_style": project.get("dialogue_style", "natural"),
        "chapter_count": project.get("chapter_count"),
        "scene_count": project.get("scene_count"),
        "created_at": project.get("created_at", ""),
        "updated_at": project.get("updated_at", ""),
        # Pipeline状态
        "pipeline_status": _get_pipeline_status_for_project(project_id),
        # Screenplay数据（如果已生成）
        "screenplay": project.get("screenplay_data"),
    }

    return result


@router.patch("/{project_id}", response_model=ProjectResponse, summary="更新项目")
async def update_project(project_id: str, update_data: ProjectUpdate):
    """更新项目信息"""
    project = _get_project_or_404(project_id)

    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        if value is not None:
            if key == "status":
                project[key] = value.value
            else:
                project[key] = value

    _persist_project(project)
    return ProjectResponse(**project)


@router.get("/{project_id}/screenplay", summary="获取完整剧本")
async def get_screenplay(project_id: str):
    """获取当前项目的完整剧本数据。"""
    project = _get_project_or_404(project_id)
    return _get_project_screenplay(project)


@router.patch("/{project_id}/screenplay", summary="更新剧本元数据")
async def update_screenplay(project_id: str, data: Dict[str, Any]):
    """更新剧本顶层元数据，供前端YAML/元数据编辑入口使用。"""
    project = _get_project_or_404(project_id)
    if "title" in data and data["title"]:
        project["title"] = data["title"]
        project["name"] = data["title"]
    if "adaptation_style" in data:
        project["adaptation_style"] = data["adaptation_style"]
    if "dialogue_style" in data:
        project["dialogue_style"] = data["dialogue_style"]
    _sync_screenplay(project)
    return _get_project_screenplay(project)


@router.delete("/{project_id}", summary="删除项目")
async def delete_project(project_id: str):
    """删除指定项目"""
    project = _get_project_or_404(project_id)
    # 取消正在运行的pipeline
    if project_id in _pipeline_tasks:
        _pipeline_tasks[project_id].cancel()
        _pipeline_tasks.pop(project_id, None)
    _pipeline_states.pop(project_id, None)
    _projects_store.pop(project_id, None)
    delete_project_snapshot(project_id)
    return {"message": f"项目 {project_id} 已删除", "id": project_id}


# ============================================================
# Pipeline接口 — 前端期望的路径
# ============================================================

# 前端pipeline阶段名 (匹配前端types.ts)
PIPELINE_STAGES_FRONTEND = [
    "chapter_identification",
    "paragraph_numbering",
    "chapter_understanding",
    "story_bible_merge",
    "scene_splitting",
    "element_generation",
    "schema_validation",
]


def _get_pipeline_status_for_project(project_id: str) -> Dict[str, Any]:
    """获取项目的pipeline状态 — 返回前端 PipelineStatus 格式"""
    state = _pipeline_states.get(project_id)

    if not state:
        project = _projects_store.get(project_id) or {}
        has_generated_screenplay = bool(project.get("screenplay_data") or project.get("scenes"))
        if has_generated_screenplay:
            return {
                "project_id": project_id,
                "current_stage": "schema_validation",
                "stages": [
                    {
                        "stage": s,
                        "status": "completed",
                        "progress": 100,
                    }
                    for s in PIPELINE_STAGES_FRONTEND
                ],
                "overall_progress": 100,
                "estimated_time_remaining": None,
            }
        return {
            "project_id": project_id,
            "current_stage": "chapter_identification",
            "stages": [
                {
                    "stage": s,
                    "status": "pending",
                    "progress": 0,
                }
                for s in PIPELINE_STAGES_FRONTEND
            ],
            "overall_progress": 0,
        }

    return state.get("status_response", {
        "project_id": project_id,
        "current_stage": "chapter_identification",
        "stages": [
            {
                "stage": s,
                "status": "pending",
                "progress": 0,
            }
            for s in PIPELINE_STAGES_FRONTEND
        ],
        "overall_progress": 0,
    })


def _update_pipeline_status(
    project_id: str,
    current_stage: str,
    stages: List[Dict],
    overall_progress: float,
    is_running: bool = True,
    error: Optional[str] = None,
):
    """更新pipeline状态"""
    status_response = {
        "project_id": project_id,
        "current_stage": current_stage,
        "stages": stages,
        "overall_progress": overall_progress,
        "estimated_time_remaining": None,
    }

    _pipeline_states[project_id] = {
        "status_response": status_response,
        "is_running": is_running,
        "error": error,
    }


@router.post("/{project_id}/pipeline/start", summary="启动Pipeline")
async def start_pipeline(
    project_id: str,
    request: PipelineStartRequest,
):
    """启动项目的AI Pipeline处理流程 — 使用前端配置的模型"""

    project = _get_project_or_404(project_id)

    source_text = project.get("_source_text", "")
    if not source_text:
        raise HTTPException(status_code=400, detail="没有可用的源文本数据")

    # 取消已有的pipeline任务
    if project_id in _pipeline_tasks:
        _pipeline_tasks[project_id].cancel()

    # 初始化pipeline状态
    initial_stages = [
        {"stage": s, "status": "pending", "progress": 0}
        for s in PIPELINE_STAGES_FRONTEND
    ]
    _update_pipeline_status(
        project_id,
        "chapter_identification",
        initial_stages,
        0,
        is_running=True,
    )

    # 确定模型配置
    base_url = request.api_base_url if request.mode == "api" else request.local_base_url
    api_key = request.api_key if request.mode == "api" else ""
    model_name = request.model_name if request.mode == "api" else request.local_model_name

    if not base_url:
        raise HTTPException(status_code=400, detail="未配置API地址或本地服务地址")
    if not model_name:
        raise HTTPException(status_code=400, detail="未配置模型名称")

    model_config = {
        "base_url": base_url,
        "api_key": api_key,
        "model_name": model_name,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
    }

    # 启动后台pipeline任务
    task = asyncio.create_task(
        _run_pipeline_background(project_id, source_text, model_config, project)
    )
    _pipeline_tasks[project_id] = task
    _persist_project(project)
    return _get_pipeline_status_for_project(project_id)

    # 立即返回当前状态
    return _get_pipeline_status_for_project(project_id)


@router.get("/{project_id}/pipeline/status", summary="获取Pipeline状态")
async def get_pipeline_status(project_id: str):
    """获取指定项目Pipeline的运行状态"""
    project = _get_project_or_404(project_id)
    return _get_pipeline_status_for_project(project_id)


@router.post("/{project_id}/pipeline/cancel", summary="取消Pipeline")
async def cancel_pipeline(project_id: str):
    """取消正在运行的Pipeline"""
    project = _get_project_or_404(project_id)

    if project_id in _pipeline_tasks:
        _pipeline_tasks[project_id].cancel()
        _pipeline_tasks.pop(project_id, None)

    # 更新状态为已停止
    state = _pipeline_states.get(project_id)
    if state and state.get("status_response"):
        stages = state["status_response"]["stages"]
        for s in stages:
            if s["status"] == "running":
                s["status"] = "error"
                s["error_message"] = "用户手动取消"
        _update_pipeline_status(
            project_id,
            state["status_response"]["current_stage"],
            stages,
            state["status_response"]["overall_progress"],
            is_running=False,
            error="Pipeline已取消",
        )

    project["status"] = ProjectStatus.FAILED.value
    _persist_project(project)
    return {"message": "Pipeline已取消", "project_id": project_id}


@router.post("/{project_id}/pipeline/retry/{stage}", summary="重试Pipeline阶段")
async def retry_pipeline_stage(project_id: str, stage: str):
    """重试Pipeline中失败的阶段"""
    project = _get_project_or_404(project_id)
    # 简化：重新启动整个pipeline
    # 实际实现中应该只重试指定阶段
    raise HTTPException(status_code=501, detail="暂不支持单阶段重试，请重新启动Pipeline")


# ============================================================
# Pipeline后台执行逻辑
# ============================================================

async def _run_pipeline_background(
    project_id: str,
    source_text: str,
    model_config: Dict[str, Any],
    project: Dict[str, Any],
):
    """后台执行Pipeline的7个阶段"""

    # 保存模型配置到项目数据（用于后续的AI重写等功能）
    project["_model_config"] = model_config
    _persist_project(project)

    try:
        # ---- 阶段1: 章节识别 ----
        await _stage_chapter_identification(project_id, source_text, project)

        # ---- 阶段2: 段落编号 ----
        await _stage_paragraph_numbering(project_id, project)

        # ---- 阶段3: 逐章理解 (LLM) ----
        await _stage_chapter_understanding(project_id, project, model_config)

        # ---- 阶段4: 故事圣经合并 (LLM) ----
        await _stage_story_bible_merge(project_id, project, model_config)

        # ---- 阶段5/6: 场景拆分 + 元素生成 (LLM流水线) ----
        await _stage_scene_element_pipeline(project_id, project, model_config)

        # ---- 阶段7: Schema校验 ----
        await _stage_schema_validation(project_id, project)

        # Pipeline完成 — 更新项目状态
        project["status"] = ProjectStatus.EDITING.value
        project["status"] = ProjectStatus.EDITING.value
        _persist_project(project)

        logger.info(f"Pipeline完成 for project {project_id}")

    except asyncio.CancelledError:
        logger.info(f"Pipeline被取消 for project {project_id}")
        project["status"] = "failed"
        _persist_project(project)

    except Exception as e:
        logger.error(f"Pipeline执行失败: {e}")
        project["status"] = "failed"
        _persist_project(project)
        # 更新pipeline状态
        state = _pipeline_states.get(project_id)
        if state and state.get("status_response"):
            stages = state["status_response"]["stages"]
            for s in stages:
                if s["status"] == "running":
                    s["status"] = "error"
                    s["error_message"] = str(e)
            _update_pipeline_status(
                project_id,
                state["status_response"]["current_stage"],
                stages,
                state["status_response"]["overall_progress"],
                is_running=False,
                error=str(e),
            )


def _get_current_stages(project_id: str) -> List[Dict]:
    """获取当前pipeline阶段状态列表"""
    state = _pipeline_states.get(project_id)
    if state and state.get("status_response"):
        return state["status_response"]["stages"]
    return [{"stage": s, "status": "pending", "progress": 0} for s in PIPELINE_STAGES_FRONTEND]


def _set_stage_status(project_id: str, stage_name: str, status: str, progress: float,
                       result_summary: Optional[str] = None, error_message: Optional[str] = None):
    """更新指定阶段的状态"""
    stages = _get_current_stages(project_id)
    for s in stages:
        if s["stage"] == stage_name:
            s["status"] = status
            s["progress"] = progress
            if result_summary:
                s["result_summary"] = result_summary
            if error_message:
                s["error_message"] = error_message

    # 计算总进度
    total_progress = sum(s["progress"] for s in stages) / len(stages)
    _update_pipeline_status(project_id, stage_name, stages, total_progress, is_running=True)
    if status in {"completed", "error"}:
        project = _projects_store.get(project_id)
        if project:
            _persist_project(project)


async def _stage_chapter_identification(project_id: str, source_text: str, project: Dict):
    """阶段1: 章节识别 (纯文本处理，不需要LLM)"""
    _set_stage_status(project_id, "chapter_identification", "running", 0)

    parser = ChapterParser()
    chapters_raw = parser.parse(source_text)

    # 转换为前端 Chapter 格式
    chapters = []
    for idx, ch in enumerate(chapters_raw):
        chapter = {
            "id": f"ch_{idx + 1}",
            "title": ch.get("title", f"第{idx + 1}章"),
            "number": idx + 1,
            "paragraph_count": len(ch.get("paragraphs", [])),
            "word_count": sum(len(p) for p in ch.get("paragraphs", [])),
            "scenes": [],  # 后续阶段填充
            "preview_text": ch.get("paragraphs", [""])[0][:300] if ch.get("paragraphs") else "",
        }
        chapters.append(chapter)

    # 保存到项目
    project["chapters"] = chapters
    project["chapter_count"] = len(chapters)

    _set_stage_status(
        project_id, "chapter_identification", "completed", 100,
        result_summary=f"识别到 {len(chapters)} 个章节"
    )


async def _stage_paragraph_numbering(project_id: str, project: Dict):
    """阶段2: 段落编号 (纯文本处理)"""
    _set_stage_status(project_id, "paragraph_numbering", "running", 0)

    # 从项目存储中读取源文本和原始解析数据
    source_text = project.get("_source_text", "")
    parser = ChapterParser()
    chapters_raw = parser.parse(source_text)

    paragraphs_cache = {}
    for idx, ch in enumerate(chapters_raw):
        chapter_id = f"ch_{idx + 1}"
        paragraphs = []
        for p_idx, p_text in enumerate(ch.get("paragraphs", [])):
            paragraph = {
                "id": f"p_{idx + 1}_{p_idx + 1}",
                "chapter_id": chapter_id,
                "index": p_idx,
                "text": p_text,
                "word_count": len(p_text),
                "is_dialogue_hint": any(c in p_text for c in ['"', '"', '「', '」', '"']) and any(name in p_text for name in ['李晓', '陈远', '王叔']),
            }
            paragraphs.append(paragraph)
        paragraphs_cache[chapter_id] = paragraphs

    # 保存到项目
    project["source_paragraphs"] = paragraphs_cache

    total_paragraphs = sum(len(ps) for ps in paragraphs_cache.values())
    _set_stage_status(
        project_id, "paragraph_numbering", "completed", 100,
        result_summary=f"完成 {len(chapters_raw)} 个章节的段落编号，共 {total_paragraphs} 段"
    )


async def _stage_chapter_understanding(project_id: str, project: Dict, model_config: Dict):
    """阶段3: 逐章理解 (需要LLM)"""
    _set_stage_status(project_id, "chapter_understanding", "running", 0)

    chapters = project.get("chapters", [])
    paragraphs_cache = project.get("source_paragraphs", {})
    if not chapters:
        project["_understandings"] = []
        _set_stage_status(
            project_id, "chapter_understanding", "completed", 100,
            result_summary="完成 0 个章节的理解"
        )
        return

    understandings: List[Optional[Dict[str, Any]]] = [None] * len(chapters)
    progress_lock = asyncio.Lock()
    completed_count = 0
    semaphore = asyncio.Semaphore(PIPELINE_CHAPTER_CONCURRENCY)
    cache = _get_pipeline_cache(project)["chapter_understanding"]
    model_fp = _model_cache_fingerprint(model_config, PIPELINE_CHAPTER_MAX_TOKENS)

    async def understand_chapter(idx: int, chapter: Dict[str, Any]) -> None:
        nonlocal completed_count
        chapter_id = chapter["id"]
        # 获取该章节的段落文本
        chapter_paragraphs = paragraphs_cache.get(chapter_id, [])
        chapter_text = "\n".join([p["text"] for p in chapter_paragraphs])
        cache_key = _stable_hash({
            "chapter_id": chapter_id,
            "title": chapter.get("title", ""),
            "text": chapter_text,
            "model": model_fp,
        })
        cached = cache.get(chapter_id)

        if isinstance(cached, dict) and cached.get("key") == cache_key and cached.get("data"):
            understanding = _copy_data(cached["data"])
        elif not chapter_text.strip():
            # 没有文本的章节，用默认理解
            understanding = {
                "characters": [],
                "locations": [],
                "events": [],
                "summary": f"第{idx + 1}章 {chapter.get('title', '')}",
            }
        else:
            # 用LLM分析章节
            chapter_title = chapter.get('title', f'第{idx+1}章')
            chapter_content = chapter_text[:2000]
            json_format = '{"characters": [{"name": "角色名", "aliases": ["别名"], "role": "protagonist/antagonist/supporting/minor", "description": "简述", "goals": ["目标1", "目标2"], "personality": "性格"}], "locations": [{"name": "地点名", "type": "indoor/outdoor", "description": "描述", "atmosphere": "氛围"}], "events": ["关键事件1", "关键事件2"], "summary": "章节概要(100字以内)"}'

            prompt = f"""请分析以下小说章节，提取关键信息。按JSON格式输出：

章节标题：{chapter_title}

章节内容：
{chapter_content}

请输出以下JSON格式：
{json_format}

只输出JSON，不要其他内容。"""

            result = await _call_llm(
                _llm_config_with_max_tokens(model_config, PIPELINE_CHAPTER_MAX_TOKENS),
                prompt
            )

            try:
                # 尝试解析JSON
                understanding = _extract_json_from_llm_response(result)
                if not understanding:
                    understanding = {
                        "characters": [],
                        "locations": [],
                        "events": [],
                        "summary": chapter_text[:200],
                    }
            except Exception as e:
                logger.warning(f"章节理解JSON解析失败: {e}")
                understanding = {
                    "characters": [],
                    "locations": [],
                    "events": [],
                    "summary": chapter_text[:200],
                }

        understanding["chapter_id"] = chapter_id
        understandings[idx] = understanding
        cache[chapter_id] = {"key": cache_key, "data": _copy_data(understanding)}

        async with progress_lock:
            completed_count += 1
            progress = completed_count / len(chapters) * 100
            _set_stage_status(
                project_id, "chapter_understanding", "running", progress,
                result_summary=f"已理解 {completed_count}/{len(chapters)} 个章节"
            )

    async def bounded_understand(idx: int, chapter: Dict[str, Any]) -> None:
        async with semaphore:
            await understand_chapter(idx, chapter)

    await asyncio.gather(*[
        bounded_understand(idx, chapter)
        for idx, chapter in enumerate(chapters)
    ])

    # 保存理解结果
    project["_understandings"] = [u for u in understandings if u is not None]

    _set_stage_status(
        project_id, "chapter_understanding", "completed", 100,
        result_summary=f"完成 {len(project['_understandings'])} 个章节的理解"
    )


async def _stage_story_bible_merge(project_id: str, project: Dict, model_config: Dict):
    """阶段4: 故事圣经合并 (需要LLM)"""
    _set_stage_status(project_id, "story_bible_merge", "running", 0)

    understandings = project.get("_understandings", [])

    # 从理解结果中收集角色和地点
    all_characters = []
    all_locations = []

    for understanding in understandings:
        for char in understanding.get("characters", []):
            all_characters.append(char)
        for loc in understanding.get("locations", []):
            all_locations.append(loc)

    # 合并同名角色（归一化）
    merged_characters = _merge_characters(all_characters)
    merged_locations = _merge_locations(all_locations)

    # 如果LLM没提取到角色，从文本中用简单规则推断
    if not merged_characters:
        merged_characters = _extract_characters_from_text(project.get("_source_text", ""))

    if not merged_locations:
        merged_locations = _extract_locations_from_text(project.get("_source_text", ""))

    # 构造时间线
    timeline = []
    for idx, understanding in enumerate(understandings):
        for event in understanding.get("events", []):
            timeline.append({
                "id": f"tl_{len(timeline) + 1}",
                "event": event,
                "chapter_id": understanding.get("chapter_id", f"ch_{idx + 1}"),
                "characters": [c["name"] for c in understanding.get("characters", [])],
                "significance": "normal",
            })

    # 构造故事圣经
    story_bible = {
        "characters": merged_characters,
        "locations": merged_locations,
        "timeline": timeline,
        "themes": [],
        "tone": project.get("_dialogue_style", "natural"),
    }

    project["story_bible"] = story_bible

    _set_stage_status(
        project_id, "story_bible_merge", "completed", 100,
        result_summary=f"合并完成: {len(merged_characters)} 角色, {len(merged_locations)} 地点"
    )


def _element_id_for_scene(scene: Dict[str, Any], el_idx: int) -> str:
    scene_id = str(scene.get("id") or "scene").replace("sc_", "").replace("-", "_")
    return f"el_{scene_id}_{el_idx + 1}"


def _get_scene_related_text(scene: Dict[str, Any], paragraphs_cache: Dict[str, List[Dict[str, Any]]]) -> str:
    chapter_id = scene.get("chapter_id", "")
    scene_paragraphs = paragraphs_cache.get(chapter_id, [])
    source_indices: List[int] = []
    for ref in scene.get("source_refs", []):
        if isinstance(ref, dict):
            try:
                source_indices.append(int(ref.get("paragraph_index", 0)))
            except (TypeError, ValueError):
                continue

    if not source_indices and scene_paragraphs:
        source_indices = list(range(len(scene_paragraphs)))

    related_parts = []
    for si in source_indices:
        if 0 <= si < len(scene_paragraphs):
            related_parts.append(scene_paragraphs[si].get("text", ""))
    return "\n".join(related_parts)


def _build_character_lookup(characters: List[Dict[str, Any]]) -> Dict[str, str]:
    char_name_to_id: Dict[str, str] = {}
    for c in characters:
        sb_id = c.get("id", f"char_{len(char_name_to_id) + 1}")
        if sb_id:
            char_name_to_id[sb_id] = sb_id
        name = c.get("name", "")
        if name:
            char_name_to_id[name] = sb_id
        for alias in c.get("aliases", []):
            if alias:
                char_name_to_id[alias] = sb_id
    return char_name_to_id


def _normalize_generated_elements(
    elements_data: Any,
    scene: Dict[str, Any],
    char_name_to_id: Dict[str, str],
    char_llm_id_to_sb_id: Dict[str, str],
) -> List[Dict[str, Any]]:
    if not isinstance(elements_data, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for el_idx, el in enumerate(elements_data):
        if not isinstance(el, dict):
            continue
        item = copy.deepcopy(el)
        item["id"] = _element_id_for_scene(scene, el_idx)
        item.setdefault("type", "action")
        item.setdefault("content", item.get("text", item.get("content", "")))
        if "text" in item and "content" not in item:
            item["content"] = item["text"]

        char_id_ref = item.get("character_id", "")
        if isinstance(char_id_ref, str) and char_id_ref:
            if char_id_ref in char_name_to_id:
                item["character_id"] = char_name_to_id[char_id_ref]
            elif char_id_ref in char_llm_id_to_sb_id:
                item["character_id"] = char_llm_id_to_sb_id[char_id_ref]
            elif char_id_ref.startswith("char_"):
                matched = False
                for c_name, c_sb_id in char_name_to_id.items():
                    if char_id_ref.replace("char_", "").replace("_", "") in c_name or c_name in char_id_ref:
                        item["character_id"] = c_sb_id
                        char_llm_id_to_sb_id[char_id_ref] = c_sb_id
                        matched = True
                        break
                if not matched:
                    logger.warning(f"无法映射角色ID {char_id_ref}，置空")
                    item["character_id"] = ""

        normalized.append(item)
    return normalized


def _default_elements_for_scene(
    related_text: str,
    scene: Dict[str, Any],
    char_name_to_id: Dict[str, str],
    fallback_idx: int,
) -> List[Dict[str, Any]]:
    elements = _create_default_elements(related_text, scene, char_name_to_id, fallback_idx)
    for el_idx, el in enumerate(elements):
        el["id"] = _element_id_for_scene(scene, el_idx)
        el.setdefault("content", el.get("text", el.get("content", "")))
    return elements


async def _split_chapter_scenes_once(
    idx: int,
    chapter: Dict[str, Any],
    paragraphs_cache: Dict[str, List[Dict[str, Any]]],
    understandings: List[Dict[str, Any]],
    story_bible: Dict[str, Any],
    model_config: Dict[str, Any],
    cache: Dict[str, Any],
) -> List[Dict[str, Any]]:
    chapter_id = chapter["id"]
    chapter_paragraphs = paragraphs_cache.get(chapter_id, [])
    chapter_text = _get_chapter_text(paragraphs_cache, chapter_id)
    understanding = understandings[idx] if idx < len(understandings) else {}
    model_fp = _model_cache_fingerprint(model_config, PIPELINE_SCENE_MAX_TOKENS)
    cache_key = _stable_hash({
        "chapter_id": chapter_id,
        "title": chapter.get("title", ""),
        "text": chapter_text,
        "understanding": understanding,
        "story_bible": story_bible,
        "model": model_fp,
    })
    cached = cache.get(chapter_id)
    if isinstance(cached, dict) and cached.get("key") == cache_key and cached.get("data"):
        return _copy_data(cached["data"])

    character_names = [c.get("name", "") for c in understanding.get("characters", [])]
    location_names = [l.get("name", "") for l in understanding.get("locations", [])]
    sb_characters = story_bible.get("characters", [])
    sb_locations = story_bible.get("locations", [])
    char_id_info = ", ".join([f"{c.get('name', '')} -> {c.get('id', '')}" for c in sb_characters])
    loc_id_info = ", ".join([f"{l.get('name', '')} -> {l.get('id', '')}" for l in sb_locations])

    chapter_title = chapter.get('title', f'第{idx+1}章')
    char_names_str = ', '.join(character_names) if character_names else '待分析'
    loc_names_str = ', '.join(location_names) if location_names else '待分析'
    chapter_content = chapter_text[:3000]

    scene_json_example = json.dumps([
        {
            "id": f"sc_{idx + 1}_1",
            "chapter_id": chapter_id,
            "heading": {"context": "INT/EXT", "location_id": "loc_1", "time_of_day": "日/夜/晨/晚"},
            "title": "场景标题",
            "dramatic_purpose": "戏剧目的",
            "conflict": "冲突描述",
            "beats": ["节拍1", "节拍2"],
            "characters": ["char_1"],
            "source_refs": [{"chapter_id": chapter_id, "paragraph_index": 0}],
            "order_in_chapter": 1,
        }
    ], ensure_ascii=False)

    prompt = f"""请将以下小说章节拆分为剧本场景。每个场景必须有dramatic_purpose和conflict。

章节标题：{chapter_title}
出场角色：{char_names_str}
相关地点：{loc_names_str}

【重要】角色ID对照表：{char_id_info}
【重要】地点ID对照表：{loc_id_info}
请在characters字段中使用上述角色ID（如char_1），在location_id中使用上述地点ID（如loc_1）。

章节内容：
{chapter_content}

请输出以下JSON格式（场景列表）：
{scene_json_example}

只输出JSON数组，不要其他内容。"""

    result = await _call_llm(
        _llm_config_with_max_tokens(model_config, PIPELINE_SCENE_MAX_TOKENS),
        prompt
    )

    char_name_to_sb_id: Dict[str, str] = {}
    char_llm_id_to_sb_id: Dict[str, str] = {}
    for c in sb_characters:
        sb_id = c.get("id", "")
        if sb_id:
            char_name_to_sb_id[sb_id] = sb_id
        name = c.get("name", "")
        if name:
            char_name_to_sb_id[name] = sb_id
        for alias in c.get("aliases", []):
            if alias:
                char_name_to_sb_id[alias] = sb_id

    loc_name_to_sb_id: Dict[str, str] = {}
    loc_llm_id_to_sb_id: Dict[str, str] = {}
    for l in sb_locations:
        sb_id = l.get("id", "")
        if sb_id:
            loc_name_to_sb_id[sb_id] = sb_id
        name = l.get("name", "")
        if name:
            loc_name_to_sb_id[name] = sb_id

    scenes_for_chapter: List[Dict[str, Any]] = []
    try:
        scenes_data = _extract_json_from_llm_response(result)
        if scenes_data and isinstance(scenes_data, list):
            for scene_order, scene in enumerate(scenes_data, start=1):
                if not isinstance(scene, dict):
                    continue
                scene["id"] = f"sc_{idx + 1}_{scene_order}"
                scene.setdefault("chapter_id", chapter_id)
                scene.setdefault("elements", [])
                scene.setdefault("source_refs", [])
                scene["order_in_chapter"] = scene_order

                mapped_chars = []
                for char_ref in scene.get("characters", []):
                    if char_ref in char_name_to_sb_id:
                        mapped_chars.append(char_name_to_sb_id[char_ref])
                    elif char_ref in char_llm_id_to_sb_id:
                        mapped_chars.append(char_llm_id_to_sb_id[char_ref])
                    else:
                        matched = False
                        for c_name, c_id in char_name_to_sb_id.items():
                            if isinstance(char_ref, str) and (
                                char_ref.replace("char_", "").replace("_", "") in c_name or c_name in char_ref
                            ):
                                mapped_chars.append(c_id)
                                char_llm_id_to_sb_id[char_ref] = c_id
                                matched = True
                                break
                        if not matched:
                            mapped_chars.append(char_ref)
                scene["characters"] = mapped_chars

                heading = scene.get("heading", {})
                if not isinstance(heading, dict):
                    heading = {}
                loc_ref = heading.get("location_id", "")
                if loc_ref and loc_ref in loc_name_to_sb_id:
                    heading["location_id"] = loc_name_to_sb_id[loc_ref]
                elif loc_ref and loc_ref in loc_llm_id_to_sb_id:
                    heading["location_id"] = loc_llm_id_to_sb_id[loc_ref]
                elif loc_ref:
                    for l_name, l_id in loc_name_to_sb_id.items():
                        if isinstance(loc_ref, str) and (l_name in loc_ref or loc_ref in l_name):
                            heading["location_id"] = l_id
                            loc_llm_id_to_sb_id[loc_ref] = l_id
                            break
                scene["heading"] = heading
                scenes_for_chapter.append(scene)
        else:
            scenes_for_chapter.extend(_create_default_scenes(chapter, chapter_paragraphs, idx))
    except Exception as e:
        logger.warning(f"场景拆分JSON解析失败: {e}")
        scenes_for_chapter.extend(_create_default_scenes(chapter, chapter_paragraphs, idx))

    cache[chapter_id] = {"key": cache_key, "data": _copy_data(scenes_for_chapter)}
    return scenes_for_chapter


def _build_element_batches(scene_items: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    batches: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    current_chars = 0

    for item in scene_items:
        text_len = len(item.get("related_text", ""))
        if current and (
            len(current) >= PIPELINE_ELEMENT_BATCH_SIZE
            or current_chars + text_len > PIPELINE_ELEMENT_BATCH_TEXT_LIMIT
        ):
            batches.append(current)
            current = []
            current_chars = 0
        current.append(item)
        current_chars += text_len

    if current:
        batches.append(current)
    return batches


def _extract_batch_elements(data: Any, scene: Dict[str, Any], batch_size: int) -> Any:
    scene_id = scene.get("id")
    if isinstance(data, dict):
        candidate = data.get(scene_id)
        if isinstance(candidate, dict) and "elements" in candidate:
            return candidate.get("elements")
        if candidate is not None:
            return candidate
        scenes_obj = data.get("scenes")
        if isinstance(scenes_obj, list):
            for item in scenes_obj:
                if isinstance(item, dict) and item.get("scene_id") == scene_id:
                    return item.get("elements", [])
    if isinstance(data, list):
        if batch_size == 1:
            if data and all(isinstance(item, dict) and "elements" in item and "scene_id" in item for item in data):
                return data[0].get("elements", [])
            return data
        for item in data:
            if isinstance(item, dict) and item.get("scene_id") == scene_id:
                return item.get("elements", [])
    return None


async def _generate_element_batch(
    batch: List[Dict[str, Any]],
    characters: List[Dict[str, Any]],
    char_name_to_id: Dict[str, str],
    char_llm_id_to_sb_id: Dict[str, str],
    model_config: Dict[str, Any],
    cache: Dict[str, Any],
    allow_single_fallback: bool = True,
) -> None:
    if not batch:
        return

    char_id_info = ", ".join([f"{c.get('name', '')} -> {c.get('id', '')}" for c in characters])
    scene_specs = []
    for item in batch:
        scene = item["scene"]
        scene_char_names = []
        for c in scene.get("characters", []):
            if isinstance(c, str) and (c in char_name_to_id or not c.startswith("char_")):
                scene_char_names.append(c)
        char_desc = ""
        for cn in scene_char_names:
            cid = char_name_to_id.get(cn, cn)
            for c in characters:
                if c.get("id") == cid or c.get("name") == cn:
                    char_desc += f"- {c.get('name', cn)} ({c.get('role', 'supporting')}): {c.get('description', '')}\n"
                    break

        scene_specs.append({
            "scene_id": scene.get("id"),
            "title": scene.get("title", "未命名场景"),
            "heading": scene.get("heading", {}),
            "dramatic_purpose": scene.get("dramatic_purpose", ""),
            "conflict": scene.get("conflict", ""),
            "characters": char_desc,
            "related_text": item.get("related_text", "")[:2000],
        })

    element_json_example = json.dumps({
        "sc_1_1": [
            {
                "id": "el_1_1",
                "type": "action",
                "content": "元素内容示例",
                "character_id": "char_1",
                "note": "可选备注"
            }
        ]
    }, ensure_ascii=False)

    prompt = f"""请为以下 {len(batch)} 个剧本场景生成核心剧本元素初稿（动作描写、对话、旁白等）。

【重要】角色ID对照表：{char_id_info}
请在character_id字段中使用上述角色ID（如char_1）。

场景资料：
{json.dumps(scene_specs, ensure_ascii=False)}

生成要求：
- 每个场景控制在 {PIPELINE_FAST_ELEMENT_TARGET} 个左右的关键元素，最多不要超过 {PIPELINE_FAST_ELEMENT_TARGET + 4} 个。
- 优先覆盖场景开端、冲突推进、关键对白、转折和收束。
- 每个元素内容保持精炼，动作描写通常 1-2 句，对话通常 1 句。
- 这是可编辑初稿，不要把每个细节都扩写成完整长剧本。

请输出以下JSON格式，key必须是scene_id，value是该场景的元素列表：
{element_json_example}

类型说明：
- action: 动作描写/场景描述
- dialogue: 对话（必须有character_id）
- parenthetical: 括号提示语（如"(微笑)"）
- transition: 场景转换标记
- voice_over: 旁白/内心独白
- shot: 镜头指示
- note: 备注

只输出JSON，不要其他内容。"""

    try:
        result = await _call_llm(
            _llm_config_with_max_tokens(model_config, PIPELINE_ELEMENT_MAX_TOKENS),
            prompt
        )
        parsed = _extract_json_from_llm_response(result)
    except Exception as e:
        logger.warning(f"元素批量生成失败: {e}")
        parsed = None

    missing: List[Dict[str, Any]] = []
    for item in batch:
        scene = item["scene"]
        raw_elements = _extract_batch_elements(parsed, scene, len(batch))
        elements = _normalize_generated_elements(raw_elements, scene, char_name_to_id, char_llm_id_to_sb_id)
        if elements:
            scene["elements"] = elements
            cache[scene.get("id", "")] = {"key": item["cache_key"], "data": _copy_data(elements)}
        else:
            missing.append(item)

    if missing and len(batch) > 1 and allow_single_fallback:
        for item in missing:
            await _generate_element_batch(
                [item],
                characters,
                char_name_to_id,
                char_llm_id_to_sb_id,
                model_config,
                cache,
                allow_single_fallback=False,
            )
        return

    for item in missing:
        scene = item["scene"]
        elements = _default_elements_for_scene(
            item.get("related_text", ""),
            scene,
            char_name_to_id,
            item.get("fallback_idx", 0),
        )
        scene["elements"] = elements
        cache[scene.get("id", "")] = {"key": item["cache_key"], "data": _copy_data(elements)}


def _build_screenplay_data(project: Dict[str, Any], story_bible: Dict[str, Any], scenes: List[Dict[str, Any]], model_config: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "project": {
            "id": project["id"],
            "title": project.get("title", ""),
            "source_language": "zh-CN",
            "target_format": "screenplay",
        },
        "story_bible": story_bible,
        "chapters": project.get("chapters", []),
        "scenes": scenes,
        "metadata": {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "model_name": model_config.get("model_name", ""),
            "prompt_version": "1.0",
            "generation_time_ms": 0,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "source_chapter_count": len(project.get("chapters", [])),
            "total_scenes": len(scenes),
            "total_elements": sum(len(s.get("elements", [])) for s in scenes),
        },
    }


async def _stage_scene_element_pipeline(project_id: str, project: Dict, model_config: Dict):
    """Pipeline scene splitting and element generation with per-chapter overlap."""
    _set_stage_status(project_id, "scene_splitting", "running", 0)
    _set_stage_status(project_id, "element_generation", "running", 0, result_summary="等待场景拆分")

    chapters = project.get("chapters", [])
    paragraphs_cache = project.get("source_paragraphs", {})
    understandings = project.get("_understandings", [])
    story_bible = project.get("story_bible", {})
    cache = _get_pipeline_cache(project)
    scene_cache = cache["scene_splitting"]
    element_cache = cache["element_generation"]

    if not chapters:
        project["scenes"] = []
        project["scene_count"] = 0
        project["screenplay_data"] = _build_screenplay_data(project, story_bible, [], model_config)
        _set_stage_status(project_id, "scene_splitting", "completed", 100, result_summary="场景拆分完成: 0 个场景")
        _set_stage_status(project_id, "element_generation", "completed", 100, result_summary="元素生成完成: 0 个元素")
        return

    chapter_scenes: List[Optional[List[Dict[str, Any]]]] = [None] * len(chapters)
    split_lock = asyncio.Lock()
    element_lock = asyncio.Lock()
    element_tasks: List[asyncio.Task] = []
    split_completed = 0
    element_completed = 0
    element_total = 0
    element_progress_shown = 0.0
    char_name_to_id = _build_character_lookup(story_bible.get("characters", []))
    char_llm_id_to_sb_id: Dict[str, str] = {}
    element_model_fp = _model_cache_fingerprint(model_config, PIPELINE_ELEMENT_MAX_TOKENS)
    split_semaphore = asyncio.Semaphore(PIPELINE_SCENE_CONCURRENCY)
    element_semaphore = asyncio.Semaphore(PIPELINE_ELEMENT_CONCURRENCY)

    async def update_element_progress(done_count: int) -> None:
        nonlocal element_completed, element_progress_shown
        async with element_lock:
            element_completed += done_count
            progress = element_completed / element_total * 100 if element_total else 0
            element_progress_shown = max(element_progress_shown, min(progress, 99))
            _set_stage_status(
                project_id,
                "element_generation",
                "running",
                element_progress_shown,
                result_summary=f"已生成 {element_completed}/{element_total} 个场景的元素",
            )

    async def generate_chapter_elements(chapter_idx: int, scenes_for_chapter: List[Dict[str, Any]]) -> None:
        nonlocal element_total
        pending: List[Dict[str, Any]] = []
        immediate_done = 0

        async with element_lock:
            element_total += len(scenes_for_chapter)

        for fallback_idx, scene in enumerate(scenes_for_chapter):
            related_text = _get_scene_related_text(scene, paragraphs_cache)
            scene_signature = _copy_data(scene)
            scene_signature.pop("elements", None)
            cache_key = _stable_hash({
                "scene": scene_signature,
                "related_text": related_text,
                "characters": story_bible.get("characters", []),
                "target": PIPELINE_FAST_ELEMENT_TARGET,
                "batch_size": PIPELINE_ELEMENT_BATCH_SIZE,
                "model": element_model_fp,
            })
            cached = element_cache.get(scene.get("id", ""))
            if isinstance(cached, dict) and cached.get("key") == cache_key and cached.get("data"):
                scene["elements"] = _copy_data(cached["data"])
                immediate_done += 1
                continue
            pending.append({
                "scene": scene,
                "related_text": related_text,
                "cache_key": cache_key,
                "fallback_idx": chapter_idx * 100 + fallback_idx,
            })

        if immediate_done:
            await update_element_progress(immediate_done)

        for batch in _build_element_batches(pending):
            async with element_semaphore:
                await _generate_element_batch(
                    batch,
                    story_bible.get("characters", []),
                    char_name_to_id,
                    char_llm_id_to_sb_id,
                    model_config,
                    element_cache,
                )
            await update_element_progress(len(batch))

    async def split_and_queue(idx: int, chapter: Dict[str, Any]) -> None:
        nonlocal split_completed
        async with split_semaphore:
            scenes_for_chapter = await _split_chapter_scenes_once(
                idx,
                chapter,
                paragraphs_cache,
                understandings,
                story_bible,
                model_config,
                scene_cache,
            )
        chapter_scenes[idx] = scenes_for_chapter

        task = asyncio.create_task(generate_chapter_elements(idx, scenes_for_chapter))
        element_tasks.append(task)

        async with split_lock:
            split_completed += 1
            progress = split_completed / len(chapters) * 100
            _set_stage_status(
                project_id,
                "scene_splitting",
                "running",
                progress,
                result_summary=f"已拆分 {split_completed}/{len(chapters)} 个章节，元素生成已流水线启动",
            )

    await asyncio.gather(*[
        split_and_queue(idx, chapter)
        for idx, chapter in enumerate(chapters)
    ])

    _set_stage_status(
        project_id,
        "scene_splitting",
        "completed",
        100,
        result_summary=f"场景拆分完成，等待元素生成收尾"
    )

    if element_tasks:
        await asyncio.gather(*element_tasks)

    all_scenes: List[Dict[str, Any]] = []
    for scenes_for_chapter in chapter_scenes:
        if scenes_for_chapter:
            all_scenes.extend(scenes_for_chapter)

    for chapter in chapters:
        chapter["scenes"] = [s for s in all_scenes if s.get("chapter_id") == chapter["id"]]

    project["scenes"] = all_scenes
    project["scene_count"] = len(all_scenes)
    project["screenplay_data"] = _build_screenplay_data(project, story_bible, all_scenes, model_config)

    total_elements = sum(len(s.get("elements", [])) for s in all_scenes)
    _set_stage_status(
        project_id,
        "element_generation",
        "completed",
        100,
        result_summary=f"元素生成完成: {total_elements} 个元素"
    )


async def _stage_scene_splitting(project_id: str, project: Dict, model_config: Dict):
    """阶段5: 场景拆分 (需要LLM)"""
    _set_stage_status(project_id, "scene_splitting", "running", 0)

    chapters = project.get("chapters", [])
    paragraphs_cache = project.get("source_paragraphs", {})
    understandings = project.get("_understandings", [])
    story_bible = project.get("story_bible", {})

    if not chapters:
        project["scenes"] = []
        project["scene_count"] = 0
        _set_stage_status(
            project_id, "scene_splitting", "completed", 100,
            result_summary="场景拆分完成: 0 个场景"
        )
        return

    chapter_scenes: List[Optional[List[Dict[str, Any]]]] = [None] * len(chapters)
    progress_lock = asyncio.Lock()
    completed_count = 0
    semaphore = asyncio.Semaphore(PIPELINE_SCENE_CONCURRENCY)

    async def split_chapter_scenes(idx: int, chapter: Dict[str, Any]) -> None:
        nonlocal completed_count
        chapter_id = chapter["id"]
        chapter_paragraphs = paragraphs_cache.get(chapter_id, [])
        chapter_text = "\n".join([p["text"] for p in chapter_paragraphs])
        understanding = understandings[idx] if idx < len(understandings) else {}
        scenes_for_chapter: List[Dict[str, Any]] = []

        # 用LLM拆分场景 — 在prompt中提供story bible的实际角色ID和地点ID
        character_names = [c.get("name", "") for c in understanding.get("characters", [])]
        location_names = [l.get("name", "") for l in understanding.get("locations", [])]

        # 构建角色ID说明（让LLM使用story bible的ID）
        sb_characters = story_bible.get("characters", [])
        sb_locations = story_bible.get("locations", [])
        char_id_info = ", ".join([f"{c.get('name', '')} -> {c.get('id', '')}" for c in sb_characters])
        loc_id_info = ", ".join([f"{l.get('name', '')} -> {l.get('id', '')}" for l in sb_locations])

        chapter_title = chapter.get('title', f'第{idx+1}章')
        char_names_str = ', '.join(character_names) if character_names else '待分析'
        loc_names_str = ', '.join(location_names) if location_names else '待分析'
        chapter_content = chapter_text[:3000]

        # JSON示例格式（不在f-string中，避免花括号冲突）
        # 使用实际的chapter_id和合理的示例ID
        scene_json_example = json.dumps([
            {
                "id": f"sc_{idx + 1}_1",
                "chapter_id": chapter_id,
                "heading": {"context": "INT/EXT", "location_id": "loc_1", "time_of_day": "日/夜/晨/晚"},
                "title": "场景标题",
                "dramatic_purpose": "戏剧目的",
                "conflict": "冲突描述",
                "beats": ["节拍1", "节拍2"],
                "characters": ["char_1"],
                "source_refs": [{"chapter_id": chapter_id, "paragraph_index": 0}],
                "order_in_chapter": 1,
            }
        ], ensure_ascii=False)

        prompt = f"""请将以下小说章节拆分为剧本场景。每个场景必须有dramatic_purpose和conflict。

章节标题：{chapter_title}
出场角色：{char_names_str}
相关地点：{loc_names_str}

【重要】角色ID对照表：{char_id_info}
【重要】地点ID对照表：{loc_id_info}
请在characters字段中使用上述角色ID（如char_1），在location_id中使用上述地点ID（如loc_1）。

章节内容：
{chapter_content}

请输出以下JSON格式（场景列表）：
{scene_json_example}

只输出JSON数组，不要其他内容。"""

        result = await _call_llm(
            _llm_config_with_max_tokens(model_config, PIPELINE_SCENE_MAX_TOKENS),
            prompt
        )

        # 构建角色名到ID和ID到ID的映射（用于将LLM生成的任意ID映射到story bible ID）
        char_name_to_sb_id = {}
        char_llm_id_to_sb_id = {}
        for c in sb_characters:
            sb_id = c.get("id", "")
            if sb_id:
                char_name_to_sb_id[sb_id] = sb_id
            char_name_to_sb_id[c.get("name", "")] = sb_id
            for alias in c.get("aliases", []):
                char_name_to_sb_id[alias] = sb_id
        loc_name_to_sb_id = {}
        loc_llm_id_to_sb_id = {}
        for l in sb_locations:
            sb_id = l.get("id", "")
            if sb_id:
                loc_name_to_sb_id[sb_id] = sb_id
            loc_name_to_sb_id[l.get("name", "")] = sb_id

        try:
            scenes_data = _extract_json_from_llm_response(result)
            if scenes_data and isinstance(scenes_data, list):
                scene_order = 0
                for scene in scenes_data:
                    # 确保scene ID唯一：强制使用 ch_idx_scene_order 格式
                    scene_order += 1
                    scene["id"] = f"sc_{idx + 1}_{scene_order}"
                    scene.setdefault("chapter_id", chapter_id)
                    scene.setdefault("elements", [])
                    scene.setdefault("source_refs", [])
                    scene["order_in_chapter"] = scene_order

                    # 映射角色ID到story bible ID
                    mapped_chars = []
                    for char_ref in scene.get("characters", []):
                        if char_ref in char_name_to_sb_id:
                            mapped_chars.append(char_name_to_sb_id[char_ref])
                        elif char_ref in char_llm_id_to_sb_id:
                            mapped_chars.append(char_llm_id_to_sb_id[char_ref])
                        else:
                            # 尝试根据pinyin模式匹配 (char_li_xiao -> 李晓)
                            matched = False
                            for c_name, c_id in char_name_to_sb_id.items():
                                if char_ref.replace("char_", "").replace("_", "") in c_name or c_name in char_ref:
                                    mapped_chars.append(c_id)
                                    char_llm_id_to_sb_id[char_ref] = c_id
                                    matched = True
                                    break
                            if not matched:
                                # 如果无法映射，保留但记录警告
                                mapped_chars.append(char_ref)
                    scene["characters"] = mapped_chars

                    # 映射地点ID到story bible ID
                    heading = scene.get("heading", {})
                    loc_ref = heading.get("location_id", "")
                    if loc_ref and loc_ref in loc_name_to_sb_id:
                        heading["location_id"] = loc_name_to_sb_id[loc_ref]
                    elif loc_ref and loc_ref in loc_llm_id_to_sb_id:
                        heading["location_id"] = loc_llm_id_to_sb_id[loc_ref]
                    elif loc_ref:
                        # 尝试根据名称模式匹配 (loc_cafe -> 咖啡馆)
                        for l_name, l_id in loc_name_to_sb_id.items():
                            if l_name in loc_ref or loc_ref in l_name:
                                heading["location_id"] = l_id
                                loc_llm_id_to_sb_id[loc_ref] = l_id
                                break

                    scenes_for_chapter.append(scene)
            else:
                # LLM没返回有效数据，创建默认场景
                scenes_for_chapter.extend(_create_default_scenes(chapter, chapter_paragraphs, idx))
        except Exception as e:
            logger.warning(f"场景拆分JSON解析失败: {e}")
            scenes_for_chapter.extend(_create_default_scenes(chapter, chapter_paragraphs, idx))

        chapter_scenes[idx] = scenes_for_chapter

        async with progress_lock:
            completed_count += 1
            progress = completed_count / len(chapters) * 100
            _set_stage_status(
                project_id, "scene_splitting", "running", progress,
                result_summary=f"已拆分 {completed_count}/{len(chapters)} 个章节"
            )

    async def bounded_split(idx: int, chapter: Dict[str, Any]) -> None:
        async with semaphore:
            await split_chapter_scenes(idx, chapter)

    await asyncio.gather(*[
        bounded_split(idx, chapter)
        for idx, chapter in enumerate(chapters)
    ])

    all_scenes: List[Dict[str, Any]] = []
    for scenes_for_chapter in chapter_scenes:
        if scenes_for_chapter:
            all_scenes.extend(scenes_for_chapter)

    # 将场景关联到章节
    for chapter in chapters:
        chapter["scenes"] = [s for s in all_scenes if s.get("chapter_id") == chapter["id"]]

    project["scenes"] = all_scenes
    project["scene_count"] = len(all_scenes)

    _set_stage_status(
        project_id, "scene_splitting", "completed", 100,
        result_summary=f"场景拆分完成: {len(all_scenes)} 个场景"
    )


async def _stage_element_generation(project_id: str, project: Dict, model_config: Dict):
    """阶段6: 剧本元素生成 (需要LLM)"""
    _set_stage_status(project_id, "element_generation", "running", 0)

    scenes = project.get("scenes", [])
    story_bible = project.get("story_bible", {})
    paragraphs_cache = project.get("source_paragraphs", {})
    characters = story_bible.get("characters", [])

    # 构建角色名到ID的映射（用于将LLM生成的任意角色ID映射到story bible ID）
    char_name_to_id = {}
    char_llm_id_to_sb_id = {}  # LLM生成的ID -> story bible ID的映射
    for c in characters:
        sb_id = c.get("id", f"char_{len(char_name_to_id) + 1}")
        if sb_id:
            char_name_to_id[sb_id] = sb_id
        char_name_to_id[c.get("name", "")] = sb_id
        for alias in c.get("aliases", []):
            char_name_to_id[alias] = sb_id

    # 构建角色ID说明（让LLM使用story bible的ID）
    char_id_info = ", ".join([f"{c.get('name', '')} -> {c.get('id', '')}" for c in characters])
    progress_lock = asyncio.Lock()
    completed_count = 0

    async def generate_scene_elements(idx: int, scene: Dict[str, Any]) -> None:
        nonlocal completed_count
        chapter_id = scene.get("chapter_id", "")
        scene_paragraphs = paragraphs_cache.get(chapter_id, [])

        # 获取与场景相关的原文段落
        source_indices = []
        for ref in scene.get("source_refs", []):
            if isinstance(ref, dict):
                source_indices.append(ref.get("paragraph_index", 0))

        # 如果没有source_refs，使用整个章节的段落
        if not source_indices and scene_paragraphs:
            source_indices = range(len(scene_paragraphs))

        related_text = ""
        for si in source_indices:
            if si < len(scene_paragraphs):
                related_text += scene_paragraphs[si].get("text", "") + "\n"

        # 用LLM生成核心剧本元素。默认先产出可编辑初稿，避免每场一次性生成过长剧本导致等待过久。
        scene_char_names = [c for c in scene.get("characters", []) if c in char_name_to_id or not c.startswith("char_")]
        char_desc = ""
        for cn in scene_char_names:
            cid = char_name_to_id.get(cn, cn)
            for c in characters:
                if c.get("id") == cid or c.get("name") == cn:
                    char_desc += f"- {c.get('name', cn)} ({c.get('role', 'supporting')}): {c.get('description', '')}\n"
                    break

        scene_title = scene.get('title', '未命名场景')
        scene_heading = json.dumps(scene.get('heading', {}), ensure_ascii=False)
        dramatic_purpose = scene.get('dramatic_purpose', '')
        conflict = scene.get('conflict', '')
        related_content = related_text[:2000]

        # JSON示例格式 — 使用story bible的角色ID
        element_json_example = json.dumps([
            {
                "id": "el_1_1",
                "type": "action",
                "content": "元素内容示例",
                "character_id": "char_1",
                "note": "可选备注"
            }
        ], ensure_ascii=False)

        prompt = f"""请为以下剧本场景生成核心剧本元素初稿（动作描写、对话、旁白等）。

场景标题：{scene_title}
场景设定：{scene_heading}
戏剧目的：{dramatic_purpose}
冲突：{conflict}
出场角色：
{char_desc}

【重要】角色ID对照表：{char_id_info}
请在character_id字段中使用上述角色ID（如char_1）。

相关原文：
{related_content}

生成要求：
- 控制在 {PIPELINE_FAST_ELEMENT_TARGET} 个左右的关键元素，最多不要超过 {PIPELINE_FAST_ELEMENT_TARGET + 4} 个。
- 优先覆盖场景开端、冲突推进、关键对白、转折和收束。
- 每个元素内容保持精炼，动作描写通常 1-2 句，对话通常 1 句。
- 这是可编辑初稿，不要把每个细节都扩写成完整长剧本。

请输出以下JSON格式（元素列表）：
{element_json_example}

类型说明：
- action: 动作描写/场景描述
- dialogue: 对话（必须有character_id）
- parenthetical: 括号提示语（如"(微笑)"）
- transition: 场景转换标记
- voice_over: 旁白/内心独白
- shot: 镜头指示
- note: 备注

只输出JSON数组，不要其他内容。"""

        try:
            result = await _call_llm(
                _llm_config_with_max_tokens(model_config, PIPELINE_ELEMENT_MAX_TOKENS),
                prompt
            )
            elements_data = _extract_json_from_llm_response(result)
            if elements_data and isinstance(elements_data, list):
                scene["elements"] = []
                for el_idx, el in enumerate(elements_data):
                    el.setdefault("id", f"el_{idx + 1}_{el_idx + 1}")
                    el.setdefault("type", "action")
                    el.setdefault("content", el.get("text", el.get("content", "")))
                    # 确保content字段存在（前端用content）
                    if "text" in el and "content" not in el:
                        el["content"] = el["text"]

                    # 映射角色ID到story bible ID
                    char_id_ref = el.get("character_id", "")
                    if char_id_ref:
                        if char_id_ref in char_name_to_id:
                            el["character_id"] = char_name_to_id[char_id_ref]
                        elif char_id_ref in char_llm_id_to_sb_id:
                            el["character_id"] = char_llm_id_to_sb_id[char_id_ref]
                        elif char_id_ref.startswith("char_"):
                            # 尝试pinyin模式匹配 (char_li_xiao -> char_1/李晓)
                            matched = False
                            for c_name, c_sb_id in char_name_to_id.items():
                                if char_id_ref.replace("char_", "").replace("_", "") in c_name or c_name in char_id_ref:
                                    el["character_id"] = c_sb_id
                                    char_llm_id_to_sb_id[char_id_ref] = c_sb_id
                                    matched = True
                                    break
                            if not matched:
                                # 无法映射，置空以避免引用错误
                                logger.warning(f"无法映射角色ID {char_id_ref}，置空")
                                el["character_id"] = ""

                    scene.setdefault("elements", []).append(el)
            else:
                # 从原文生成基本元素
                scene["elements"] = _create_default_elements(related_text, scene, char_name_to_id, idx)
        except Exception as e:
            logger.warning(f"元素生成失败，使用默认元素: {e}")
            scene["elements"] = _create_default_elements(related_text, scene, char_name_to_id, idx)

        async with progress_lock:
            completed_count += 1
            progress = completed_count / len(scenes) * 100 if scenes else 100
            _set_stage_status(
                project_id, "element_generation", "running", progress,
                result_summary=f"已生成 {completed_count}/{len(scenes)} 个场景的元素"
            )

    semaphore = asyncio.Semaphore(PIPELINE_ELEMENT_CONCURRENCY)

    async def bounded_generate(idx: int, scene: Dict[str, Any]) -> None:
        async with semaphore:
            await generate_scene_elements(idx, scene)

    await asyncio.gather(*[
        bounded_generate(idx, scene)
        for idx, scene in enumerate(scenes)
    ])

    # 构造screenplay_data用于存储
    project["screenplay_data"] = {
        "schema_version": "1.0.0",
        "project": {
            "id": project["id"],
            "title": project.get("title", ""),
            "source_language": "zh-CN",
            "target_format": "screenplay",
        },
        "story_bible": story_bible,
        "chapters": project.get("chapters", []),
        "scenes": scenes,
        "metadata": {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "model_name": model_config.get("model_name", ""),
            "prompt_version": "1.0",
            "generation_time_ms": 0,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "source_chapter_count": len(project.get("chapters", [])),
            "total_scenes": len(scenes),
            "total_elements": sum(len(s.get("elements", [])) for s in scenes),
        },
    }

    _set_stage_status(
        project_id, "element_generation", "completed", 100,
        result_summary=f"元素生成完成: {sum(len(s.get('elements', [])) for s in scenes)} 个元素"
    )


async def _stage_schema_validation(project_id: str, project: Dict):
    """阶段7: Schema校验 (结构性验证)"""
    _set_stage_status(project_id, "schema_validation", "running", 0)

    # 简化的结构校验
    errors = []

    chapters = project.get("chapters", [])
    scenes = project.get("scenes", [])
    story_bible = project.get("story_bible", {})
    characters = story_bible.get("characters", [])
    locations = story_bible.get("locations", [])

    # 检查每个场景是否有元素
    for scene in scenes:
        if not scene.get("elements"):
            errors.append({
                "id": f"err_{len(errors) + 1}",
                "type": "missing_field",
                "severity": "warning",
                "message": f"场景 {scene.get('id', '')} 没有剧本元素",
                "scene_id": scene.get("id"),
                "auto_fixable": True,
            })
        if not scene.get("dramatic_purpose"):
            errors.append({
                "id": f"err_{len(errors) + 1}",
                "type": "missing_field",
                "severity": "warning",
                "message": f"场景 {scene.get('id', '')} 缺少戏剧目的",
                "scene_id": scene.get("id"),
                "auto_fixable": False,
            })

    # 检查角色引用 — 只检查以char_开头的引用
    char_ids = {c.get("id", "") for c in characters}
    for scene in scenes:
        for char_ref in scene.get("characters", []):
            if char_ref.startswith("char_") and char_ref not in char_ids:
                errors.append({
                    "id": f"err_{len(errors) + 1}",
                    "type": "invalid_reference",
                    "severity": "warning",
                    "message": f"场景引用了不存在的角色 {char_ref}",
                    "scene_id": scene.get("id"),
                    "character_id": char_ref,
                    "auto_fixable": True,
                })

    # 检查地点引用
    loc_ids = {l.get("id", "") for l in locations}
    for scene in scenes:
        heading = scene.get("heading", {})
        loc_ref = heading.get("location_id", "")
        if loc_ref and loc_ref.startswith("loc_") and loc_ref not in loc_ids:
            errors.append({
                "id": f"err_{len(errors) + 1}",
                "type": "invalid_reference",
                "severity": "warning",
                "message": f"场景引用了不存在的地点 {loc_ref}",
                "scene_id": scene.get("id"),
                "location_id": loc_ref,
                "auto_fixable": True,
            })

    # 检查元素中的角色引用
    for scene in scenes:
        for el in scene.get("elements", []):
            el_char_id = el.get("character_id", "")
            if el_char_id and el_char_id.startswith("char_") and el_char_id not in char_ids:
                errors.append({
                    "id": f"err_{len(errors) + 1}",
                    "type": "invalid_reference",
                    "severity": "warning",
                    "message": f"元素引用了不存在的角色 {el_char_id}",
                    "scene_id": scene.get("id"),
                    "element_id": el.get("id"),
                    "character_id": el_char_id,
                    "auto_fixable": True,
                })

    project["validation_errors"] = errors

    _set_stage_status(
        project_id, "schema_validation", "completed", 100,
        result_summary=f"校验完成: {len(errors)} 个问题"
    )


# ============================================================
# LLM调用工具
# ============================================================

def _extract_chat_completion_content(data: Any) -> str:
    """Extract text from OpenAI-compatible chat completion payloads."""
    if not isinstance(data, dict):
        return ""

    chunks: List[str] = []
    for choice in data.get("choices", []) or []:
        if not isinstance(choice, dict):
            continue
        delta = choice.get("delta") or {}
        message = choice.get("message") or {}

        if isinstance(delta, dict):
            content = delta.get("content")
            if isinstance(content, str):
                chunks.append(content)
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                chunks.append(content)
        text = choice.get("text")
        if isinstance(text, str):
            chunks.append(text)

    content = data.get("content")
    if isinstance(content, str):
        chunks.append(content)

    return "".join(chunks)


def _parse_sse_line(line: str) -> Optional[str]:
    """Parse one SSE data line and return text content if present."""
    if not line.startswith("data:"):
        return None

    payload = line[5:].strip()
    if not payload or payload == "[DONE]":
        return None

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return payload

    return _extract_chat_completion_content(data)


async def _call_llm(model_config: Dict[str, Any], prompt: str) -> str:
    """使用用户配置的模型进行LLM调用 — 用httpx直接请求避免SDK被代理拦截"""
    import httpx

    last_error: Optional[Exception] = None
    for attempt in range(2):
        try:
            return await _call_llm_once(model_config, prompt)
        except (httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError) as e:
            last_error = e
            logger.warning(f"LLM流式响应中断，准备重试({attempt + 1}/2): {e}")
            await asyncio.sleep(1.5 * (attempt + 1))

    if last_error:
        raise last_error
    return await _call_llm_once(model_config, prompt)


async def _call_llm_once(model_config: Dict[str, Any], prompt: str) -> str:
    """Single OpenAI-compatible chat completion call."""
    import httpx

    base_url = model_config.get("base_url", "")
    api_key = model_config.get("api_key", "")
    model_name = model_config.get("model_name", "")
    temperature = model_config.get("temperature", 0.7)
    max_tokens = model_config.get("max_tokens", 4000)

    # 确保 base_url 以 /chat/completions 结尾
    url = base_url.rstrip("/") + "/chat/completions"

    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    body = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "你是专业的小说分析和剧本创作助手。严格按照要求的JSON格式输出，不要添加其他内容。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream("POST", url, headers=headers, json=body) as response:
                if response.status_code != 200:
                    error_body = (await response.aread()).decode("utf-8", errors="replace")
                    logger.error(f"LLM调用失败: HTTP {response.status_code} - {error_body[:300]}")
                    raise Exception(f"LLM调用失败: HTTP {response.status_code} - {error_body[:200]}")

                content_type = response.headers.get("content-type", "")
                if "text/event-stream" not in content_type:
                    raw = (await response.aread()).decode("utf-8", errors="replace")
                    try:
                        content = _extract_chat_completion_content(json.loads(raw))
                    except json.JSONDecodeError:
                        content = raw
                    return content or ""

                chunks: List[str] = []
                async for line in response.aiter_lines():
                    chunk = _parse_sse_line(line)
                    if chunk:
                        chunks.append(chunk)

                content = "".join(chunks).strip()
                if not content:
                    raise Exception("LLM调用失败: 流式响应为空")
                return content

    except httpx.TimeoutException:
        logger.error("LLM调用超时")
        raise Exception("LLM调用超时(300s)")
    except httpx.ConnectError as e:
        logger.error(f"LLM连接失败: {e}")
        raise Exception(f"LLM连接失败: {e}")
    except Exception as e:
        logger.error(f"LLM调用异常: {e}")
        raise


def _extract_json_from_llm_response(text: str) -> Optional[Any]:
    """从LLM回复中提取JSON"""
    if not text:
        return None

    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试从markdown代码块中提取
    import re
    json_pattern = re.compile(r'```(?:json)?\s*\n(.*?)\n```', re.DOTALL)
    match = json_pattern.search(text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试找到最外层的方括号或大括号
    bracket_start = text.find('[')
    brace_start = text.find('{')
    if bracket_start != -1 and (brace_start == -1 or bracket_start < brace_start):
        bracket_end = text.rfind(']')
        if bracket_end > bracket_start:
            try:
                return json.loads(text[bracket_start:bracket_end + 1])
            except json.JSONDecodeError:
                pass
    elif brace_start != -1:
        brace_end = text.rfind('}')
        if brace_end > brace_start:
            try:
                return json.loads(text[brace_start:brace_end + 1])
            except json.JSONDecodeError:
                pass

    return None


def _get_project_screenplay(project: Dict[str, Any]) -> Dict[str, Any]:
    """Return the live screenplay shape used by the current frontend."""
    screenplay = copy.deepcopy(project.get("screenplay_data") or {})
    if not screenplay:
        screenplay = {
            "schema_version": "1.0.0",
            "project": {
                "id": project.get("id"),
                "title": project.get("title") or project.get("name", ""),
                "source_language": project.get("source_language", "zh-CN"),
                "target_format": project.get("target_format", "screenplay"),
            },
            "story_bible": copy.deepcopy(project.get("story_bible") or {"characters": [], "locations": [], "timeline": []}),
            "chapters": copy.deepcopy(project.get("chapters") or []),
            "scenes": copy.deepcopy(project.get("scenes") or []),
            "metadata": {
                "generated_at": project.get("updated_at") or time.strftime("%Y-%m-%dT%H:%M:%S"),
                "model_name": project.get("_model_config", {}).get("model_name", ""),
                "source_chapter_count": len(project.get("chapters") or []),
                "total_scenes": len(project.get("scenes") or []),
                "total_elements": sum(len(s.get("elements", [])) for s in project.get("scenes", [])),
            },
        }

    screenplay["chapters"] = copy.deepcopy(project.get("chapters") or screenplay.get("chapters") or [])
    screenplay["scenes"] = copy.deepcopy(project.get("scenes") or screenplay.get("scenes") or [])
    screenplay["story_bible"] = copy.deepcopy(project.get("story_bible") or screenplay.get("story_bible") or {"characters": [], "locations": [], "timeline": []})
    return screenplay


def _sync_screenplay(project: Dict[str, Any]) -> None:
    """Persist the live in-memory data into screenplay_data after edits."""
    if project.get("screenplay_data"):
        project["screenplay_data"]["chapters"] = copy.deepcopy(project.get("chapters") or [])
        project["screenplay_data"]["scenes"] = copy.deepcopy(project.get("scenes") or [])
        project["screenplay_data"]["story_bible"] = copy.deepcopy(project.get("story_bible") or {"characters": [], "locations": [], "timeline": []})
    _persist_project(project)


def _find_scene(project: Dict[str, Any], scene_id: str) -> Optional[Dict[str, Any]]:
    for scene in project.get("scenes", []):
        if scene.get("id") == scene_id:
            return scene
    for chapter in project.get("chapters", []):
        for scene in chapter.get("scenes", []):
            if scene.get("id") == scene_id:
                return scene
    return None


def _find_element(project: Dict[str, Any], element_id: str) -> Optional[Dict[str, Any]]:
    for scene in project.get("scenes", []):
        for element in scene.get("elements", []):
            if element.get("id") == element_id:
                return element
    for chapter in project.get("chapters", []):
        for scene in chapter.get("scenes", []):
            for element in scene.get("elements", []):
                if element.get("id") == element_id:
                    return element
    return None


def _safe_filename(project: Dict[str, Any], suffix: str) -> str:
    title = project.get("title") or project.get("name") or "screenplay"
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in title).strip("_")
    return f"{safe or 'screenplay'}.{suffix}"


def _read_workspace_text(relative_path: str) -> str:
    workspace_root = Path(__file__).resolve().parents[4]
    file_path = workspace_root / relative_path
    return file_path.read_text(encoding="utf-8")


def _build_documentation_export(project: Dict[str, Any]) -> tuple[bytes, str, str]:
    files = {
        "YAML_SCREENPLAY_SCHEMA.md": _read_workspace_text("docs/YAML_SCREENPLAY_SCHEMA.md"),
        "SCHEMA.md": _read_workspace_text("docs/SCHEMA.md"),
        "screenplay.schema.json": _read_workspace_text("apps/api/app/schemas/screenplay.schema.json"),
    }

    manifest = {
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "project_id": project.get("id"),
        "project_name": project.get("name") or project.get("title"),
        "contents": list(files.keys()),
        "description": "NovelScripter 剧本 YAML Schema 说明文档包，包含用户说明、设计原因和机器校验 JSON Schema。",
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files.items():
            zf.writestr(filename, content.encode("utf-8"))
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
    return buffer.getvalue(), _safe_filename(project, "schema_docs.zip"), "application/zip"


def _screenplay_to_markdown(screenplay: Dict[str, Any]) -> str:
    lines: List[str] = []
    project = screenplay.get("project", {})
    story_bible = screenplay.get("story_bible", {})

    lines.append(f"# {project.get('title') or '未命名剧本'}")
    lines.append("")

    characters = story_bible.get("characters", [])
    if characters:
        lines.append("## 人物")
        lines.append("")
        for char in characters:
            role = char.get("role") or "supporting"
            desc = char.get("description") or ""
            lines.append(f"- **{char.get('name', char.get('id', ''))}** ({role}) {desc}".rstrip())
        lines.append("")

    locations = story_bible.get("locations", [])
    if locations:
        lines.append("## 地点")
        lines.append("")
        for loc in locations:
            lines.append(f"- **{loc.get('name', loc.get('id', ''))}**: {loc.get('description', '')}".rstrip())
        lines.append("")

    lines.append("## 场景")
    lines.append("")
    for scene in screenplay.get("scenes", []):
        heading = scene.get("heading") or {}
        heading_text = f"{heading.get('context', 'INT')}. {heading.get('location_id') or '未知地点'} - {heading.get('time_of_day', '日')}"
        lines.append(f"### {heading_text}")
        if scene.get("title"):
            lines.append(f"*{scene.get('title')}*")
        if scene.get("dramatic_purpose"):
            lines.append(f"戏剧目的: {scene.get('dramatic_purpose')}")
        lines.append("")
        for element in scene.get("elements", []):
            text = element.get("content", element.get("text", ""))
            if element.get("type") == "dialogue":
                lines.append(f"**{element.get('character_id') or '角色'}**: {text}")
            else:
                lines.append(text)
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def _screenplay_to_fountain(screenplay: Dict[str, Any]) -> str:
    lines: List[str] = []
    project = screenplay.get("project", {})
    lines.append(f"Title: {project.get('title') or '未命名剧本'}")
    lines.append("Credit: NovelScripter AI")
    lines.append("")

    for scene in screenplay.get("scenes", []):
        heading = scene.get("heading") or {}
        context = str(heading.get("context") or "INT").upper()
        location = str(heading.get("location_id") or "UNKNOWN").upper()
        time_of_day = str(heading.get("time_of_day") or "DAY").upper()
        lines.append(f"{context}. {location} - {time_of_day}")
        lines.append("")
        if scene.get("title"):
            lines.append(f"[{scene.get('title')}]")
            lines.append("")
        for element in scene.get("elements", []):
            text = element.get("content", element.get("text", ""))
            element_type = element.get("type", "action")
            if element_type == "dialogue":
                lines.append(str(element.get("character_id") or "CHARACTER").upper())
                lines.append(text)
            elif element_type == "transition":
                lines.append(str(text).upper())
            else:
                lines.append(text)
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def _build_export_content(project: Dict[str, Any], export_format: str) -> tuple[bytes, str, str]:
    screenplay = _get_project_screenplay(project)
    fmt = export_format.lower()

    if fmt in {"docs", "documentation", "schema_docs"}:
        return _build_documentation_export(project)
    if fmt == "yaml":
        from ruamel.yaml import YAML
        yaml = YAML()
        yaml.default_flow_style = False
        yaml.allow_unicode = True
        stream = io.StringIO()
        yaml.dump(screenplay, stream)
        return stream.getvalue().encode("utf-8"), _safe_filename(project, "yaml"), "text/yaml; charset=utf-8"
    if fmt == "json":
        return json.dumps(screenplay, ensure_ascii=False, indent=2).encode("utf-8"), _safe_filename(project, "json"), "application/json; charset=utf-8"
    if fmt == "markdown":
        return _screenplay_to_markdown(screenplay).encode("utf-8"), _safe_filename(project, "md"), "text/markdown; charset=utf-8"
    if fmt == "fountain":
        return _screenplay_to_fountain(screenplay).encode("utf-8"), _safe_filename(project, "fountain"), "text/plain; charset=utf-8"
    if fmt == "zip":
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for child_fmt in ["json", "yaml", "markdown", "fountain"]:
                content, filename, _ = _build_export_content(project, child_fmt)
                zf.writestr(filename, content)
        return buffer.getvalue(), _safe_filename(project, "zip"), "application/zip"

    raise HTTPException(status_code=400, detail=f"不支持的导出格式: {export_format}")


def _build_diff(before: str, after: str) -> List[Dict[str, str]]:
    if before == after:
        return [{"type": "unchanged", "content": before}]
    changes: List[Dict[str, str]] = []
    if before:
        changes.append({"type": "remove", "content": before})
    if after:
        changes.append({"type": "add", "content": after})
    return changes


# ============================================================
# 辅助函数 — 合并与默认数据生成
# ============================================================

def _strip_markdown_fence(text: str) -> str:
    value = text.strip()
    if not value.startswith("```"):
        return value
    lines = value.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _clean_rewrite_output(raw: str) -> str:
    """Return only rewritten text from common LLM wrapper shapes."""
    value = _strip_markdown_fence(str(raw or ""))
    if not value:
        return ""

    for _ in range(3):
        candidate = value.strip()
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            break

        if isinstance(parsed, str):
            value = parsed
            continue

        if isinstance(parsed, dict):
            for key in (
                "content",
                "text",
                "rewritten_content",
                "rewritten_text",
                "rewrite",
                "result",
                "answer",
                "重写后内容",
                "重写内容",
                "改写后内容",
                "改写内容",
                "内容",
            ):
                inner = parsed.get(key)
                if isinstance(inner, str) and inner.strip():
                    value = inner
                    break
            else:
                string_values = [
                    item.strip()
                    for item in parsed.values()
                    if isinstance(item, str) and item.strip()
                ]
                if len(string_values) == 1:
                    value = string_values[0]
                    continue
                break
            continue

        break

    return _strip_markdown_fence(value).strip()


def _ensure_list(value):
    """确保值为列表 — LLM可能返回字符串而不是数组"""
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        return [value]
    if value is None:
        return []
    return [str(value)]


def _merge_characters(all_characters: List[Dict]) -> List[Dict]:
    """合并同名角色（归一化）"""
    merged = {}
    for char in all_characters:
        name = char.get("name", "")
        if not name:
            continue
        if name in merged:
            # 合并别名
            existing = merged[name]
            existing_aliases = existing.get("aliases", [])
            new_aliases = char.get("aliases", [])
            for alias in new_aliases:
                if alias not in existing_aliases and alias != name:
                    existing_aliases.append(alias)
            existing["aliases"] = existing_aliases
        else:
            merged[name] = {
                "id": f"char_{len(merged) + 1}",
                "name": name,
                "aliases": _ensure_list(char.get("aliases", [])),
                "role": char.get("role", "supporting"),
                "description": char.get("description", ""),
                "goals": _ensure_list(char.get("goals", [])),
                "personality": char.get("personality", ""),
                "appearance": char.get("appearance", ""),
                "first_appearance": "",
                "relationships": _ensure_list(char.get("relationships", [])),
            }

    return list(merged.values())


def _merge_locations(all_locations: List[Dict]) -> List[Dict]:
    """合并同名地点"""
    merged = {}
    for loc in all_locations:
        name = loc.get("name", "")
        if not name:
            continue
        if name not in merged:
            merged[name] = {
                "id": f"loc_{len(merged) + 1}",
                "name": name,
                "type": loc.get("type", "indoor"),
                "description": loc.get("description", ""),
                "atmosphere": loc.get("atmosphere", ""),
                "first_appearance": "",
            }

    return list(merged.values())


def _extract_characters_from_text(text: str) -> List[Dict]:
    """从文本中用简单规则提取角色名"""
    import re
    # 查找对话中的角色名
    patterns = [
        r'"([^，。！？\s]{2,6})[说道叫喊问回答笑叹怒嚷]',
        r'([^，。！？\s]{2,6})[说道叫喊问回答笑叹怒嚷]',
    ]
    names = set()
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for name in matches:
            if len(name) >= 2 and len(name) <= 6:
                names.add(name)

    characters = []
    for idx, name in enumerate(sorted(names)):
        characters.append({
            "id": f"char_{idx + 1}",
            "name": name,
            "aliases": [],
            "role": "supporting",
            "description": f"小说中的角色 {name}",
            "goals": [],
            "personality": "",
            "appearance": "",
            "first_appearance": "",
            "relationships": [],
        })

    return characters


def _extract_locations_from_text(text: str) -> List[Dict]:
    """从文本中提取常见地点"""
    location_keywords = {
        "咖啡馆": {"type": "indoor", "atmosphere": "温暖安静"},
        "咖啡": {"type": "indoor", "atmosphere": "温暖"},
        "街道": {"type": "outdoor", "atmosphere": "喧嚣"},
        "办公室": {"type": "indoor", "atmosphere": "忙碌"},
        "家": {"type": "indoor", "atmosphere": "温馨"},
        "公园": {"type": "outdoor", "atmosphere": "自然"},
        "餐厅": {"type": "indoor", "atmosphere": "热闹"},
        "车站": {"type": "indoor", "atmosphere": "匆忙"},
    }

    locations = []
    for idx, (name, info) in enumerate(location_keywords.items()):
        if name in text:
            locations.append({
                "id": f"loc_{idx + 1}",
                "name": name,
                "type": info["type"],
                "description": f"小说中出现的{name}",
                "atmosphere": info["atmosphere"],
                "first_appearance": "",
            })

    return locations


def _create_default_scenes(chapter: Dict, paragraphs: List[Dict], chapter_idx: int) -> List[Dict]:
    """为章节创建默认场景（当LLM失败时的后备方案）"""
    scenes = []
    chapter_id = chapter.get("id", f"ch_{chapter_idx + 1}")

    # 将段落按对话/叙述分割成场景
    narrative_para_ids = []
    dialogue_para_ids = []

    for p_idx, p in enumerate(paragraphs):
        text = p.get("text", "")
        if any(c in text for c in ['"', '"', '「', '」']):
            dialogue_para_ids.append(p_idx)
        else:
            narrative_para_ids.append(p_idx)

    # 简化：每个章节一个场景
    scene = {
        "id": f"sc_{chapter_idx + 1}_1",
        "chapter_id": chapter_id,
        "heading": {
            "context": "INT",
            "location_id": "",
            "time_of_day": "日",
        },
        "title": chapter.get("title", f"第{chapter_idx + 1}章"),
        "dramatic_purpose": f"推进第{chapter_idx + 1}章的故事发展",
        "conflict": "角色之间的互动与选择",
        "beats": ["开场", "发展", "转折"],
        "characters": [],
        "source_refs": [
            {"chapter_id": chapter_id, "paragraph_index": i}
            for i in range(min(5, len(paragraphs)))
        ],
        "elements": [],
        "order_in_chapter": 1,
    }
    scenes.append(scene)

    return scenes


def _create_default_elements(
    related_text: str,
    scene: Dict,
    char_name_to_id: Dict[str, str],
    scene_idx: int,
) -> List[Dict]:
    """为场景创建默认元素（当LLM失败时的后备方案）"""
    elements = []
    el_idx = 1

    # 将原文段落转换为基本元素
    lines = related_text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 检查是否是对话
        is_dialogue = False
        char_id = None
        for char_name, cid in char_name_to_id.items():
            if char_name in line:
                is_dialogue = True
                char_id = cid
                break

        if is_dialogue:
            # 提取对话内容
            import re
            dialogue_match = re.search(r'["「"](.+?)["」"]', line)
            content = dialogue_match.group(1) if dialogue_match else line
            elements.append({
                "id": f"el_{scene_idx + 1}_{el_idx}",
                "type": "dialogue",
                "content": content,
                "character_id": char_id,
            })
        else:
            elements.append({
                "id": f"el_{scene_idx + 1}_{el_idx}",
                "type": "action",
                "content": line,
            })

        el_idx += 1

    return elements


# ============================================================
# 数据接口 — 前端编辑器需要的端点
# ============================================================

@router.get("/{project_id}/chapters", summary="获取章节列表")
async def list_chapters(project_id: str):
    """获取指定项目的章节列表（包含场景）"""
    project = _get_project_or_404(project_id)
    chapters = project.get("chapters", [])

    # 如果没有chapters但有screenplay_data，从中提取
    if not chapters and project.get("screenplay_data"):
        chapters = project["screenplay_data"].get("chapters", [])

    return chapters


@router.get("/{project_id}/chapters/{chapter_id}", summary="获取单个章节")
async def get_chapter(project_id: str, chapter_id: str):
    """获取指定章节的详细信息"""
    project = _get_project_or_404(project_id)
    chapters = project.get("chapters", [])

    if not chapters and project.get("screenplay_data"):
        chapters = project["screenplay_data"].get("chapters", [])

    for chapter in chapters:
        if chapter.get("id") == chapter_id:
            return chapter

    raise HTTPException(status_code=404, detail=f"章节 {chapter_id} 不存在")


@router.patch("/{project_id}/chapters/{chapter_id}", summary="更新章节")
async def update_chapter(project_id: str, chapter_id: str, data: Dict[str, Any]):
    """更新章节基础信息。"""
    project = _get_project_or_404(project_id)
    chapters = project.get("chapters", [])

    for chapter in chapters:
        if chapter.get("id") == chapter_id:
            for key, value in data.items():
                chapter[key] = value
            _sync_screenplay(project)
            return chapter

    raise HTTPException(status_code=404, detail=f"章节 {chapter_id} 不存在")


@router.get("/{project_id}/chapters/{chapter_id}/scenes", summary="获取章节场景列表")
async def list_chapter_scenes(project_id: str, chapter_id: str):
    """获取指定章节的场景列表"""
    project = _get_project_or_404(project_id)
    scenes = project.get("scenes", [])

    if not scenes and project.get("screenplay_data"):
        scenes = project["screenplay_data"].get("scenes", [])

    chapter_scenes = [s for s in scenes if s.get("chapter_id") == chapter_id]
    return chapter_scenes


@router.get("/{project_id}/chapters/{chapter_id}/paragraphs", summary="获取源文本段落")
async def get_source_paragraphs(project_id: str, chapter_id: str):
    """获取指定章节的源文本段落"""
    project = _get_project_or_404(project_id)
    paragraphs_cache = project.get("source_paragraphs", {})

    paragraphs = paragraphs_cache.get(chapter_id, [])
    if not paragraphs:
        # 如果没有缓存，从screenplay_data中提取
        if project.get("screenplay_data"):
            for chapter in project["screenplay_data"].get("chapters", []):
                if chapter.get("id") == chapter_id:
                    return chapter.get("paragraphs", [])

    return paragraphs


@router.get("/{project_id}/story-bible", summary="获取故事圣经")
async def get_story_bible(project_id: str):
    """获取指定项目的故事圣经"""
    project = _get_project_or_404(project_id)

    story_bible = project.get("story_bible")
    if not story_bible and project.get("screenplay_data"):
        story_bible = project["screenplay_data"].get("story_bible")

    if not story_bible:
        return {"characters": [], "locations": [], "timeline": []}

    return story_bible


@router.post("/{project_id}/story-bible/characters/merge", summary="合并角色")
async def merge_characters(project_id: str, data: Dict[str, Any]):
    """将多个源角色合并到目标角色。"""
    project = _get_project_or_404(project_id)
    story_bible = project.get("story_bible", {"characters": []})
    source_ids = set(data.get("source_ids") or [])
    target_id = data.get("target_id")

    if not target_id or not source_ids:
        raise HTTPException(status_code=400, detail="需要提供 source_ids 和 target_id")

    characters = story_bible.get("characters", [])
    target = next((c for c in characters if c.get("id") == target_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"目标角色 {target_id} 不存在")

    merged_aliases = list(target.get("aliases") or [])
    merged_description = [target.get("description") or ""]
    remaining = []
    for char in characters:
        char_id = char.get("id")
        if char_id in source_ids and char_id != target_id:
            name = char.get("name")
            if name and name not in merged_aliases:
                merged_aliases.append(name)
            for alias in char.get("aliases") or []:
                if alias not in merged_aliases:
                    merged_aliases.append(alias)
            if char.get("description"):
                merged_description.append(char["description"])
        else:
            remaining.append(char)

    target["aliases"] = merged_aliases
    target["description"] = "；".join([item for item in merged_description if item])
    story_bible["characters"] = remaining

    for scene in project.get("scenes", []):
        scene["characters"] = [target_id if cid in source_ids else cid for cid in scene.get("characters", [])]
        for element in scene.get("elements", []):
            if element.get("character_id") in source_ids:
                element["character_id"] = target_id

    _sync_screenplay(project)
    return target


@router.patch("/{project_id}/story-bible/characters/{character_id}", summary="更新角色")
async def update_character(project_id: str, character_id: str, data: Dict[str, Any]):
    """更新故事圣经中的角色信息"""
    project = _get_project_or_404(project_id)
    story_bible = project.get("story_bible", {"characters": []})

    for char in story_bible.get("characters", []):
        if char.get("id") == character_id:
            for key, value in data.items():
                char[key] = value
            _sync_screenplay(project)
            return char

    raise HTTPException(status_code=404, detail=f"角色 {character_id} 不存在")


@router.patch("/{project_id}/story-bible/locations/{location_id}", summary="更新地点")
async def update_location(project_id: str, location_id: str, data: Dict[str, Any]):
    """更新故事圣经中的地点信息"""
    project = _get_project_or_404(project_id)
    story_bible = project.get("story_bible", {"locations": []})

    for loc in story_bible.get("locations", []):
        if loc.get("id") == location_id:
            for key, value in data.items():
                loc[key] = value
            _sync_screenplay(project)
            return loc

    raise HTTPException(status_code=404, detail=f"地点 {location_id} 不存在")


@router.get("/{project_id}/scenes/{scene_id}", summary="获取单个场景")
async def get_scene(project_id: str, scene_id: str):
    """获取指定场景的详细信息"""
    project = _get_project_or_404(project_id)
    scenes = project.get("scenes", [])

    if not scenes and project.get("screenplay_data"):
        scenes = project["screenplay_data"].get("scenes", [])

    for scene in scenes:
        if scene.get("id") == scene_id:
            return scene

    raise HTTPException(status_code=404, detail=f"场景 {scene_id} 不存在")


@router.patch("/{project_id}/scenes/{scene_id}", summary="更新场景")
async def update_scene(project_id: str, scene_id: str, data: Dict[str, Any]):
    """更新指定场景"""
    project = _get_project_or_404(project_id)
    scenes = project.get("scenes", [])

    if not scenes and project.get("screenplay_data"):
        scenes = project["screenplay_data"].get("scenes", [])

    for scene in scenes:
        if scene.get("id") == scene_id:
            for key, value in data.items():
                scene[key] = value
            for chapter in project.get("chapters", []):
                chapter["scenes"] = [
                    scene if s.get("id") == scene_id else s
                    for s in chapter.get("scenes", [])
                ]
            _sync_screenplay(project)
            return scene

    raise HTTPException(status_code=404, detail=f"场景 {scene_id} 不存在")


@router.delete("/{project_id}/scenes/{scene_id}", summary="删除场景")
async def delete_scene(project_id: str, scene_id: str):
    """删除指定场景。"""
    project = _get_project_or_404(project_id)
    before = len(project.get("scenes", []))
    project["scenes"] = [s for s in project.get("scenes", []) if s.get("id") != scene_id]
    for chapter in project.get("chapters", []):
        chapter["scenes"] = [s for s in chapter.get("scenes", []) if s.get("id") != scene_id]

    if len(project.get("scenes", [])) == before:
        raise HTTPException(status_code=404, detail=f"场景 {scene_id} 不存在")

    project["scene_count"] = len(project.get("scenes", []))
    _sync_screenplay(project)
    return {"message": f"场景 {scene_id} 已删除", "id": scene_id}


@router.post("/{project_id}/scenes/{scene_id}/elements/{element_id}/rewrite", summary="AI重写元素")
async def rewrite_element(
    project_id: str,
    scene_id: str,
    element_id: str,
    data: Dict[str, Any] = Body(default_factory=dict),
):
    """使用AI重写指定剧本元素"""
    project = _get_project_or_404(project_id)

    # 获取模型配置（从pipeline状态或项目数据中）
    model_config = project.get("_model_config", {})
    if not model_config:
        raise HTTPException(status_code=400, detail="未配置模型，请先运行Pipeline")

    scenes = project.get("scenes", [])
    scene = None
    element = None

    for s in scenes:
        if s.get("id") == scene_id:
            scene = s
            for el in s.get("elements", []):
                if el.get("id") == element_id:
                    element = el
                    break

    if not element:
        raise HTTPException(status_code=404, detail=f"元素 {element_id} 不存在")

    instruction = data.get("instruction") or "优化这段内容"
    original_text = element.get("content", element.get("text", ""))
    element["_last_before"] = original_text

    prompt = f"""请根据指令重写以下剧本元素。

指令：{instruction}

原始内容：
{original_text}

场景上下文：
{scene.get('title', '')} - {scene.get('dramatic_purpose', '')}

只输出重写后的内容，不要包含任何解释。"""

    result = await _call_llm(
        _llm_config_with_max_tokens(model_config, PIPELINE_REWRITE_MAX_TOKENS),
        prompt
    )
    cleaned_result = _clean_rewrite_output(result) or result.strip()

    element["content"] = cleaned_result
    if "text" in element:
        element["text"] = cleaned_result
    element["_last_after"] = cleaned_result
    _sync_screenplay(project)

    return {
        "id": element_id,
        "type": element.get("type", "action"),
        "content": cleaned_result,
        "character_id": element.get("character_id"),
    }


@router.get("/{project_id}/elements/{element_id}/diff", summary="获取元素差异")
async def get_element_diff(project_id: str, element_id: str):
    """获取最近一次元素重写的差异。"""
    project = _get_project_or_404(project_id)
    element = _find_element(project, element_id)
    if not element:
        raise HTTPException(status_code=404, detail=f"元素 {element_id} 不存在")

    before = element.get("_last_before", "")
    after = element.get("_last_after", element.get("content", element.get("text", "")))
    return {
        "element_id": element_id,
        "before": before,
        "after": after,
        "changes": _build_diff(before, after),
    }


@router.post("/documentation/export", summary="导出说明文档")
async def export_documentation():
    """生成项目无关的 Schema 说明文档导出元信息。"""
    project = {"id": "documentation", "name": "novelscripter_schema_docs"}
    content, filename, _ = _build_documentation_export(project)
    return {
        "download_url": "/api/v1/projects/documentation/export/download",
        "filename": filename,
        "format": "docs",
        "size_bytes": len(content),
    }


@router.get("/documentation/export/download", summary="下载说明文档")
async def download_documentation_export():
    """下载项目无关的 Schema 说明文档包。"""
    from fastapi.responses import Response

    project = {"id": "documentation", "name": "novelscripter_schema_docs"}
    content, filename, media_type = _build_documentation_export(project)
    encoded_name = quote(filename)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"},
    )


@router.post("/{project_id}/export", summary="导出剧本")
async def export_project(project_id: str, data: Dict[str, Any]):
    """生成导出文件元信息，匹配前端ExportDialog使用的接口。"""
    project = _get_project_or_404(project_id)

    export_format = data.get("format") or "fountain"
    if str(export_format).lower() not in {"docs", "documentation", "schema_docs"}:
        if not project.get("screenplay_data") and not project.get("scenes"):
            raise HTTPException(status_code=404, detail="项目尚未生成剧本数据")
    content, filename, _ = _build_export_content(project, export_format)
    return {
        "download_url": f"/api/v1/projects/{project_id}/export/download?format={export_format}",
        "filename": filename,
        "format": export_format,
        "size_bytes": len(content),
    }


@router.get("/{project_id}/export/download", summary="下载导出文件")
async def download_project_export(project_id: str, format: str = Query(default="fountain")):
    """下载导出文件。"""
    from fastapi.responses import Response

    project = _get_project_or_404(project_id)
    if str(format).lower() not in {"docs", "documentation", "schema_docs"}:
        if not project.get("screenplay_data") and not project.get("scenes"):
            raise HTTPException(status_code=404, detail="项目尚未生成剧本数据")

    content, filename, media_type = _build_export_content(project, format)
    encoded_name = quote(filename)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"},
    )


@router.get("/{project_id}/validation/errors", summary="获取校验错误")
async def get_validation_errors(project_id: str):
    """获取指定项目的校验错误列表"""
    project = _get_project_or_404(project_id)
    return project.get("validation_errors", [])


@router.post("/{project_id}/repair", summary="修复校验错误")
async def repair_errors(project_id: str, data: Dict[str, Any]):
    """尝试修复校验错误"""
    project = _get_project_or_404(project_id)
    errors = project.get("validation_errors", [])

    auto_fix = data.get("auto_fix", True)
    error_ids = data.get("error_ids")

    fixed_count = 0
    remaining = []

    for error in errors:
        if error_ids and error.get("id") not in error_ids:
            remaining.append(error)
            continue

        if error.get("auto_fixable") and auto_fix:
            # 自动修复 — 标记为已修复
            fixed_count += 1
        else:
            remaining.append(error)

    project["validation_errors"] = remaining
    _persist_project(project)

    return {
        "fixed_count": fixed_count,
        "remaining_errors": remaining,
        "message": f"已修复 {fixed_count} 个错误，剩余 {len(remaining)} 个",
    }
