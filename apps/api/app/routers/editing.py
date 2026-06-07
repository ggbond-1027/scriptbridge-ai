"""编辑 API - 故事圣经编辑、场景编辑、元素编辑、局部重写"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request

from app.models.screenplay import (
    Screenplay, Scene, Element, ElementType,
    Character, Location, StoryBible, SceneHeading,
    SourceRef, AdaptationStyle,
)
from app.core.llm_provider import LLMProvider, RewriteRequest
from app.core.model_router import ModelRouter, TaskType
from app.config import settings

router = APIRouter()


@router.get("/{project_id}/story-bible", summary="获取故事圣经")
async def get_story_bible(project_id: str):
    """获取指定项目的故事圣经数据"""

    from app.routers.projects import _persist_project, _projects_store
    project = _projects_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")

    screenplay_data = project.get("screenplay_data")
    if not screenplay_data:
        raise HTTPException(status_code=404, detail="项目尚未生成故事圣经")

    story_bible = screenplay_data.get("story_bible", {})
    return story_bible


@router.patch("/{project_id}/story-bible", summary="更新故事圣经")
async def patch_story_bible(
    project_id: str,
    characters: Optional[List[Character]] = None,
    locations: Optional[List[Location]] = None,
    timeline: Optional[List[Any]] = None,
):
    """局部更新故事圣经（角色、地点、时间线）"""

    from app.routers.projects import _projects_store
    project = _projects_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")

    screenplay_data = project.get("screenplay_data")
    if not screenplay_data:
        raise HTTPException(status_code=404, detail="项目尚未生成故事圣经")

    story_bible = screenplay_data["story_bible"]

    if characters:
        story_bible["characters"] = [c.model_dump() for c in characters]
    if locations:
        story_bible["locations"] = [l.model_dump() for l in locations]
    if timeline:
        story_bible["timeline"] = timeline

    # 更新项目数据
    project["screenplay_data"]["story_bible"] = story_bible
    _persist_project(project)

    return {
        "message": "故事圣经已更新",
        "character_count": len(story_bible["characters"]),
        "location_count": len(story_bible["locations"]),
        "timeline_count": len(story_bible.get("timeline", [])),
    }


@router.post("/{project_id}/story-bible/merge-characters", summary="合并角色")
async def merge_characters(
    project_id: str,
    character_ids: List[str],
    merged_name: str,
    merged_description: Optional[str] = None,
):
    """合并多个角色为一个（别名归一化）"""

    from app.routers.projects import _persist_project, _projects_store
    project = _projects_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")

    screenplay_data = project.get("screenplay_data")
    if not screenplay_data:
        raise HTTPException(status_code=404, detail="项目尚未生成故事圣经")

    characters = screenplay_data["story_bible"]["characters"]

    # 找到要合并的角色
    to_merge = [c for c in characters if c["id"] in character_ids]
    if len(to_merge) < 2:
        raise HTTPException(status_code=400, detail="至少需要2个角色才能合并")

    # 收集所有别名
    all_aliases = []
    for c in to_merge:
        if c.get("aliases"):
            all_aliases.extend(c["aliases"])
        if c["name"] != merged_name:
            all_aliases.append(c["name"])

    # 创建合并后的角色
    merged_character = {
        "id": to_merge[0]["id"],
        "name": merged_name,
        "aliases": all_aliases,
        "role": to_merge[0].get("role", "supporting"),
        "description": merged_description or to_merge[0].get("description", ""),
        "goals": to_merge[0].get("goals"),
        "personality": to_merge[0].get("personality"),
        "appearance": to_merge[0].get("appearance"),
        "first_appearance": to_merge[0].get("first_appearance"),
        "relationships": [],
    }

    # 合并关系
    for c in to_merge:
        if c.get("relationships"):
            merged_character["relationships"].extend(c["relationships"])

    # 移除旧角色，添加合并角色
    characters = [c for c in characters if c["id"] not in character_ids]
    characters.append(merged_character)

    # 更新场景中的角色引用（将旧ID映射到合并ID）
    merged_id = to_merge[0]["id"]
    old_ids = [c["id"] for c in to_merge if c["id"] != merged_id]

    scenes = screenplay_data.get("scenes", [])
    for scene in scenes:
        scene["characters"] = [merged_id if cid in old_ids else cid for cid in scene.get("characters", [])]
        for element in scene.get("elements", []):
            if element.get("character_id") in old_ids:
                element["character_id"] = merged_id

    # 更新项目数据
    screenplay_data["story_bible"]["characters"] = characters
    _persist_project(project)

    return {
        "message": "角色已合并",
        "merged_character": merged_character,
        "removed_ids": old_ids,
        "affected_scenes": len([s for s in scenes if any(oid in s.get("characters", []) for oid in old_ids)]),
    }


@router.patch("/{project_id}/scenes/{scene_id}", summary="更新场景")
async def patch_scene(
    project_id: str,
    scene_id: str,
    heading: Optional[SceneHeading] = None,
    title: Optional[str] = None,
    dramatic_purpose: Optional[str] = None,
    conflict: Optional[str] = None,
    characters: Optional[List[str]] = None,
    beats: Optional[List[Any]] = None,
):
    """局部更新场景属性"""

    from app.routers.projects import _persist_project, _projects_store
    project = _projects_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")

    screenplay_data = project.get("screenplay_data")
    if not screenplay_data:
        raise HTTPException(status_code=404, detail="项目尚未生成剧本数据")

    scenes = screenplay_data.get("scenes", [])
    scene = None
    for s in scenes:
        if s["id"] == scene_id:
            scene = s
            break

    if not scene:
        raise HTTPException(status_code=404, detail=f"场景 {scene_id} 不存在")

    # 更新字段
    if heading:
        scene["heading"] = heading.model_dump()
    if title:
        scene["title"] = title
    if dramatic_purpose:
        scene["dramatic_purpose"] = dramatic_purpose
    if conflict:
        scene["conflict"] = conflict
    if characters:
        scene["characters"] = characters
    if beats:
        scene["beats"] = beats

    _persist_project(project)

    return {
        "message": "场景已更新",
        "scene_id": scene_id,
    }


@router.post("/{project_id}/scenes/{scene_id}/rewrite", summary="AI重写场景")
async def rewrite_scene(
    project_id: str,
    scene_id: str,
    instruction: str,
    request: Request,
):
    """使用AI重写指定场景（基于指令进行定向改写）"""

    from app.routers.projects import _persist_project, _projects_store
    project = _projects_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")

    screenplay_data = project.get("screenplay_data")
    if not screenplay_data:
        raise HTTPException(status_code=404, detail="项目尚未生成剧本数据")

    # 找到场景
    scene_data = None
    for s in screenplay_data.get("scenes", []):
        if s["id"] == scene_id:
            scene_data = s
            break

    if not scene_data:
        raise HTTPException(status_code=404, detail=f"场景 {scene_id} 不存在")

    # 构造上下文
    context_parts = []
    if scene_data.get("heading"):
        heading = scene_data["heading"]
        context_parts.append(f"场景: {heading.get('context', 'INT')}. {heading.get('location_id', '未知')} - {heading.get('time_of_day', '日')}")
    if scene_data.get("dramatic_purpose"):
        context_parts.append(f"戏剧目的: {scene_data['dramatic_purpose']}")
    if scene_data.get("conflict"):
        context_parts.append(f"冲突: {scene_data['conflict']}")

    context = "\n".join(context_parts)

    # 构造选中文本（场景的所有元素）
    selection_parts = []
    for element in scene_data.get("elements", []):
        if element.get("type") == "dialogue":
            char_name = element.get("character_id", "角色")
            selection_parts.append(f"{char_name}: {element['text']}")
        else:
            selection_parts.append(element.get("text", ""))

    selection = "\n".join(selection_parts)

    # 使用LLM进行重写
    model_router = getattr(request.app.state, 'model_router', None)
    if not model_router:
        model_router = ModelRouter(settings)
    llm_provider = LLMProvider(model_router)

    rewrite_req = RewriteRequest(
        instruction=instruction,
        context=context,
        selection=selection,
        task_type=TaskType.REWRITE,
    )

    result = await llm_provider.rewrite(rewrite_req)

    if not result.success:
        raise HTTPException(status_code=500, detail=f"AI重写失败: {result.error}")

    return {
        "message": "场景重写完成",
        "scene_id": scene_id,
        "rewritten_text": result.content,
        "model_used": result.model_id,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
    }


@router.post("/{project_id}/elements/{element_id}/rewrite", summary="AI重写元素")
async def rewrite_element(
    project_id: str,
    element_id: str,
    instruction: str,
    request: Request,
):
    """使用AI重写指定剧本元素（如对话、动作描写等）"""

    from app.routers.projects import _projects_store
    project = _projects_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")

    screenplay_data = project.get("screenplay_data")
    if not screenplay_data:
        raise HTTPException(status_code=404, detail="项目尚未生成剧本数据")

    # 找到元素
    element_data = None
    scene_data = None
    for scene in screenplay_data.get("scenes", []):
        for element in scene.get("elements", []):
            if element["id"] == element_id:
                element_data = element
                scene_data = scene
                break

    if not element_data:
        raise HTTPException(status_code=404, detail=f"元素 {element_id} 不存在")

    # 构造上下文
    context_elements = []
    for element in scene_data.get("elements", []):
        context_elements.append(f"[{element.get('type', 'action')}] {element.get('text', '')}")

    context = "\n".join(context_elements[:5])  # 取前5个元素作为上下文
    selection = element_data.get("text", "")

    # 使用LLM进行重写
    model_router = getattr(request.app.state, 'model_router', None)
    if not model_router:
        model_router = ModelRouter(settings)
    llm_provider = LLMProvider(model_router)

    rewrite_req = RewriteRequest(
        instruction=instruction,
        context=context,
        selection=selection,
        task_type=TaskType.POLISH_DIALOGUE,
        preserve_structure=True,
    )

    result = await llm_provider.rewrite(rewrite_req)

    if not result.success:
        raise HTTPException(status_code=500, detail=f"AI重写失败: {result.error}")

    # 更新元素文本
    element_data["text"] = result.content
    _persist_project(project)

    return {
        "message": "元素重写完成",
        "element_id": element_id,
        "original_text": selection,
        "rewritten_text": result.content,
        "model_used": result.model_id,
    }
