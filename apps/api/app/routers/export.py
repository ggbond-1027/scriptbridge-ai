"""导出 API - 支持5种导出格式"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from app.core.export import ExportService
from app.models.screenplay import Screenplay

router = APIRouter()


@router.get("/{project_id}/yaml", summary="导出YAML格式")
async def export_yaml(project_id: str):
    """导出指定项目的剧本为YAML格式"""

    from app.routers.projects import _projects_store
    project = _projects_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")

    screenplay_data = project.get("screenplay_data")
    if not screenplay_data:
        raise HTTPException(status_code=404, detail="项目尚未生成剧本数据")

    screenplay = Screenplay.model_validate(screenplay_data)
    export_service = ExportService()
    yaml_content = export_service.export_yaml(screenplay)

    return Response(
        content=yaml_content.encode("utf-8"),
        media_type="text/yaml",
        headers={
            "Content-Disposition": f"attachment; filename={project['title']}.yaml"
        },
    )


@router.get("/{project_id}/json", summary="导出JSON格式")
async def export_json(project_id: str):
    """导出指定项目的剧本为JSON格式"""

    from app.routers.projects import _projects_store
    project = _projects_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")

    screenplay_data = project.get("screenplay_data")
    if not screenplay_data:
        raise HTTPException(status_code=404, detail="项目尚未生成剧本数据")

    screenplay = Screenplay.model_validate(screenplay_data)
    export_service = ExportService()
    json_content = export_service.export_json(screenplay)

    return Response(
        content=json_content.encode("utf-8"),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename={project['title']}.json"
        },
    )


@router.get("/{project_id}/markdown", summary="导出Markdown格式")
async def export_markdown(project_id: str):
    """导出指定项目的剧本为Markdown格式"""

    from app.routers.projects import _projects_store
    project = _projects_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")

    screenplay_data = project.get("screenplay_data")
    if not screenplay_data:
        raise HTTPException(status_code=404, detail="项目尚未生成剧本数据")

    screenplay = Screenplay.model_validate(screenplay_data)
    export_service = ExportService()
    md_content = export_service.export_markdown(screenplay)

    return Response(
        content=md_content.encode("utf-8"),
        media_type="text/markdown",
        headers={
            "Content-Disposition": f"attachment; filename={project['title']}.md"
        },
    )


@router.get("/{project_id}/fountain", summary="导出Fountain格式")
async def export_fountain(project_id: str):
    """导出指定项目的剧本为Fountain剧本格式"""

    from app.routers.projects import _projects_store
    project = _projects_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")

    screenplay_data = project.get("screenplay_data")
    if not screenplay_data:
        raise HTTPException(status_code=404, detail="项目尚未生成剧本数据")

    screenplay = Screenplay.model_validate(screenplay_data)
    export_service = ExportService()
    fountain_content = export_service.export_fountain(screenplay)

    return Response(
        content=fountain_content.encode("utf-8"),
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename={project['title']}.fountain"
        },
    )


@router.get("/{project_id}/zip", summary="导出项目ZIP包")
async def export_zip(project_id: str):
    """导出指定项目的完整ZIP包（包含所有格式的剧本文件）"""

    from app.routers.projects import _projects_store
    project = _projects_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")

    screenplay_data = project.get("screenplay_data")
    if not screenplay_data:
        raise HTTPException(status_code=404, detail="项目尚未生成剧本数据")

    screenplay = Screenplay.model_validate(screenplay_data)
    export_service = ExportService()
    zip_bytes = export_service.export_zip(screenplay)

    return StreamingResponse(
        iter([zip_bytes]),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={project['title']}.zip"
        },
    )