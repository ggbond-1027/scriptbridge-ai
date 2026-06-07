"""AI Pipeline API - 分析、运行状态、重试"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
import asyncio
import json

from app.core.pipeline import PipelineManager, PipelineStage, StageStatus
from app.core.model_router import ModelRouter, TaskType
from app.core.llm_provider import LLMProvider
from app.config import settings

router = APIRouter()

# 全局Pipeline管理器
_pipeline_manager = PipelineManager()


@router.post("/{project_id}/analyze", summary="启动分析Pipeline")
async def start_pipeline(
    project_id: str,
    request: Request,
    source_text: Optional[str] = None,
    stages: Optional[list] = None,
):
    """启动指定项目的AI Pipeline分析流程"""

    # 获取项目数据
    from app.routers.projects import _persist_project, _projects_store
    project = _projects_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")

    # 获取源文本
    if source_text:
        text = source_text
    elif project.get("source_text"):
        text = project["source_text"]
    else:
        # 检查导入数据
        from app.routers.import_router import _import_store
        import_data = None
        for imp in _import_store.values():
            if imp.get("project_id") == project_id:
                import_data = imp
                break

        if import_data:
            text = import_data["source_text"]
        else:
            raise HTTPException(status_code=400, detail="没有可用的源文本数据")

    # 初始化模型路由和LLM提供者
    model_router = getattr(request.app.state, 'model_router', None)
    if not model_router:
        model_router = ModelRouter(settings)

    llm_provider = LLMProvider(model_router)

    # 创建Pipeline运行
    run = _pipeline_manager.create_run(project_id, text)

    # 异步执行Pipeline
    try:
        screenplay = await _pipeline_manager.execute(
            run, model_router, llm_provider
        )

        # 保存结果到项目
        project["screenplay_data"] = screenplay.model_dump()
        project["chapter_count"] = len(screenplay.chapters)
        project["scene_count"] = len(screenplay.scenes)
        project["status"] = "completed"
        _persist_project(project)

    except Exception as e:
        project["status"] = "failed"
        _persist_project(project)
        raise HTTPException(status_code=500, detail=f"Pipeline执行失败: {str(e)}")

    return {
        "run_id": run.run_id,
        "project_id": project_id,
        "status": "completed",
        "stages": {
            stage.value: {
                "status": p.status.value,
                "progress_percent": p.progress_percent,
                "message": p.message,
            }
            for stage, p in run.stages.items()
        },
        "result_summary": {
            "chapter_count": len(screenplay.chapters),
            "scene_count": len(screenplay.scenes),
            "character_count": len(screenplay.story_bible.characters),
            "location_count": len(screenplay.story_bible.locations),
            "total_elements": sum(len(s.elements) for s in screenplay.scenes),
        },
    }


@router.get("/{project_id}/status", summary="获取Pipeline运行状态")
async def get_pipeline_status(
    project_id: str,
    run_id: Optional[str] = None,
):
    """获取指定项目Pipeline的运行状态"""

    if run_id:
        status = _pipeline_manager.get_run_status(run_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"运行 {run_id} 不存在")
        return status

    # 查找项目的最新运行
    for rid, status_data in _pipeline_manager._runs.items():
        if status_data.project_id == project_id:
            return _pipeline_manager.get_run_status(rid)

    raise HTTPException(status_code=404, detail=f"项目 {project_id} 没有Pipeline运行记录")


@router.post("/{project_id}/retry", summary="重试Pipeline阶段")
async def retry_pipeline_stage(
    project_id: str,
    run_id: str,
    stage: str,
    request: Request,
):
    """重试Pipeline中失败的阶段"""

    model_router = getattr(request.app.state, 'model_router', None)
    if not model_router:
        model_router = ModelRouter(settings)
    llm_provider = LLMProvider(model_router)

    try:
        pipeline_stage = PipelineStage(stage)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"无效的阶段名称: {stage}. 有效阶段: {[s.value for s in PipelineStage]}"
        )

    success = await _pipeline_manager.retry_stage(
        run_id, pipeline_stage, model_router, llm_provider
    )

    if not success:
        raise HTTPException(status_code=500, detail="重试失败")

    return {
        "run_id": run_id,
        "project_id": project_id,
        "stage": stage,
        "status": "retrying",
    }


@router.post("/{project_id}/run", summary="运行指定阶段的Pipeline")
async def run_specific_stages(
    project_id: str,
    request: Request,
    stages: list[str],
    source_text: Optional[str] = None,
):
    """运行Pipeline中指定的阶段（跳过之前的阶段）"""

    from app.routers.projects import _persist_project, _projects_store
    project = _projects_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")

    if source_text:
        text = source_text
    elif project.get("source_text"):
        text = project["source_text"]
    else:
        raise HTTPException(status_code=400, detail="没有可用的源文本数据")

    model_router = getattr(request.app.state, 'model_router', None)
    if not model_router:
        model_router = ModelRouter(settings)
    llm_provider = LLMProvider(model_router)

    run = _pipeline_manager.create_run(project_id, text)

    # 标记跳过的阶段
    for stage_name in stages:
        try:
            stage = PipelineStage(stage_name)
            run.stages[stage].status = StageStatus.SKIPPED
        except ValueError:
            pass

    try:
        screenplay = await _pipeline_manager.execute(run, model_router, llm_provider)
        project["screenplay_data"] = screenplay.model_dump()
        project["status"] = "completed"
        _persist_project(project)
    except Exception as e:
        project["status"] = "failed"
        _persist_project(project)
        raise HTTPException(status_code=500, detail=f"Pipeline执行失败: {str(e)}")

    return {
        "run_id": run.run_id,
        "project_id": project_id,
        "stages_run": stages,
        "status": "completed",
    }


# WebSocket路由需要放在main.py中单独处理
# 这里定义WebSocket的处理逻辑
async def handle_pipeline_websocket(websocket: WebSocket, project_id: str):
    """WebSocket处理Pipeline进度推送"""

    await websocket.accept()

    try:
        while True:
            # 接收客户端消息（如请求开始Pipeline）
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("action") == "start":
                source_text = message.get("source_text", "")

                model_router = ModelRouter(settings)
                llm_provider = LLMProvider(model_router)

                run = _pipeline_manager.create_run(project_id, source_text)

                # 定义WebSocket回调
                def ws_callback(progress_data):
                    try:
                        websocket.send_json(progress_data)
                    except Exception:
                        pass

                try:
                    screenplay = await _pipeline_manager.execute(
                        run, model_router, llm_provider,
                        websocket_callback=ws_callback,
                    )

                    # 发送最终结果
                    await websocket.send_json({
                        "type": "complete",
                        "run_id": run.run_id,
                        "result_summary": {
                            "chapter_count": len(screenplay.chapters),
                            "scene_count": len(screenplay.scenes),
                            "character_count": len(screenplay.story_bible.characters),
                            "total_elements": sum(len(s.elements) for s in screenplay.scenes),
                        },
                    })

                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "error": str(e),
                    })

            elif message.get("action") == "status":
                # 查询当前状态
                for rid, run in _pipeline_manager._runs.items():
                    if run.project_id == project_id:
                        status = _pipeline_manager.get_run_status(rid)
                        await websocket.send_json(status)
                        break

    except WebSocketDisconnect:
        pass
