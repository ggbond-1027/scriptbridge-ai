"""场景拆分服务 - 将章节内容拆分为场景

核心要求：
- 每个场景必须有dramatic_purpose（戏剧目的）
- 每个场景必须有conflict（冲突描述）
- 场景拆分基于叙事视角变化、地点变化、时间变化
"""

from typing import Any, Dict, List, Optional
import logging
import uuid

from app.models.screenplay import (
    Scene, SceneHeading, SceneContext, Element, ElementType,
    SourceRef, SceneBeat, Chapter, StoryBible,
)
from app.core.llm_provider import LLMProvider
from app.core.model_router import ModelRouter, TaskType

logger = logging.getLogger(__name__)


class SceneSplitter:
    """场景拆分服务"""

    def __init__(self, llm_provider: LLMProvider, model_router: ModelRouter):
        self.llm_provider = llm_provider
        self.model_router = model_router

    async def split_from_chapters(
        self,
        chapters: List[Chapter],
        understandings: List[Dict[str, Any]],
        story_bible: StoryBible,
    ) -> List[Scene]:
        """
        从章节中拆分场景

        对于每个章节：
        1. 使用AI识别场景边界（地点变化、时间变化、叙事视角变化）
        2. 为每个场景生成dramatic_purpose和conflict
        3. 生成场景heading（INT/EXT、地点、时间）
        4. 关联出场角色
        """
        scenes: List[Scene] = []
        scene_counter = 0

        for idx, chapter in enumerate(chapters):
            chapter_text = "\n".join([p.text for p in chapter.paragraphs])

            # 使用AI进行场景拆分
            scene_data = await self._ai_split_scene(
                chapter, chapter_text, understandings[idx] if idx < len(understandings) else {},
                story_bible
            )

            for s_data in scene_data:
                scene_counter += 1

                # 解析场景heading
                heading = self._parse_heading(s_data.get("heading", {}), story_bible)

                # 解析角色
                characters = self._resolve_characters(s_data.get("characters", []), story_bible)

                # 构造SourceRef
                source_ref = SourceRef(
                    chapter_id=chapter.id,
                    paragraph_ids=[p.id for p in chapter.paragraphs],
                )

                # 构造节拍
                beats = []
                for beat_data in s_data.get("beats", []):
                    beats.append(SceneBeat(
                        description=beat_data.get("description", ""),
                        emotional_arc=beat_data.get("emotional_arc"),
                        key_action=beat_data.get("key_action"),
                    ))

                scene = Scene(
                    id=f"sc_{scene_counter}",
                    chapter_ids=[chapter.id],
                    source_refs=[source_ref],
                    heading=heading,
                    title=s_data.get("title"),
                    dramatic_purpose=s_data.get("dramatic_purpose", ""),
                    conflict=s_data.get("conflict", ""),
                    characters=characters,
                    beats=beats,
                    elements=[],  # 元素在后续阶段生成
                )
                scenes.append(scene)

        return scenes

    async def _ai_split_scene(
        self,
        chapter: Chapter,
        chapter_text: str,
        understanding: Dict[str, Any],
        story_bible: StoryBible,
    ) -> List[Dict[str, Any]]:
        """使用AI拆分场景"""

        # 加载prompt模板
        prompt_data = self._load_prompt("scene_splitting")

        # 构造角色和地点信息
        character_info = "\n".join([
            f"- {c.name} ({c.role.value}): {c.description or '无描述'}"
            for c in story_bible.characters
        ])
        location_info = "\n".join([
            f"- {l.name} ({l.type.value}): {l.description or '无描述'}"
            for l in story_bible.locations
        ])

        # 构造用户提示
        user_prompt = prompt_data["user_prompt_template"].format(
            chapter_title=chapter.title,
            chapter_text=chapter_text[:3000],  # 截断以避免超长
            character_info=character_info[:1000],
            location_info=location_info[:500],
        )

        # 使用LLM生成场景拆分结果
        result = await self.llm_provider.generate_structured(
            output_type=dict,
            task_type=TaskType.SCENE_SPLITTING,
            prompt=user_prompt,
            system_prompt=prompt_data["system_prompt"],
            temperature=prompt_data.get("temperature", 0.3),
        )

        if result.success and result.content:
            return result.content.get("scenes", [])

        # 回退：简单拆分策略（基于段落空行）
        return self._fallback_split(chapter, chapter_text, understanding)

    def _fallback_split(
        self,
        chapter: Chapter,
        chapter_text: str,
        understanding: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """回退拆分策略：当AI生成失败时使用规则拆分"""

        # 将章节文本按段落组拆分
        paragraphs = chapter_text.split('\n\n')
        if len(paragraphs) <= 3:
            # 内容较少，作为一个场景
            return [{
                "title": chapter.title,
                "dramatic_purpose": f"呈现第{chapter.order}章的核心内容",
                "conflict": understanding.get("conflict", "未识别的冲突"),
                "characters": understanding.get("characters", []),
                "heading": {
                    "context": "INT",
                    "location_name": understanding.get("primary_location", "未知地点"),
                    "time_of_day": "日",
                },
                "beats": [
                    {"description": "展示章节主要情节"},
                ],
            }]

        # 按段落组数量拆分（每3-5段一个场景）
        scene_texts = []
        current = []
        for p in paragraphs:
            current.append(p)
            if len(current) >= 4:
                scene_texts.append(current)
                current = []
        if current:
            scene_texts.append(current)

        scenes = []
        for i, text_group in enumerate(scene_texts):
            scenes.append({
                "title": f"{chapter.title} - 场景{i+1}",
                "dramatic_purpose": f"推进第{chapter.order}章的情节",
                "conflict": understanding.get("conflict", f"场景{i+1}的冲突"),
                "characters": understanding.get("characters", []),
                "heading": {
                    "context": "INT",
                    "location_name": understanding.get("primary_location", "未知地点"),
                    "time_of_day": "日",
                },
                "beats": [
                    {"description": text_group[0][:100] if text_group else ""},
                ],
            })

        return scenes

    def _parse_heading(
        self,
        heading_data: Dict[str, Any],
        story_bible: StoryBible,
    ) -> SceneHeading:
        """解析场景heading数据"""

        context_str = heading_data.get("context", "INT")
        try:
            context = SceneContext(context_str)
        except ValueError:
            context = SceneContext.INT

        # 解析地点ID
        location_name = heading_data.get("location_name", "")
        location_id = None
        for loc in story_bible.locations:
            if loc.name == location_name or location_name in loc.name:
                location_id = loc.id
                break

        time_of_day = heading_data.get("time_of_day", "日")

        return SceneHeading(
            context=context,
            location_id=location_id,
            time_of_day=time_of_day,
        )

    def _resolve_characters(
        self,
        character_names: List[Any],
        story_bible: StoryBible,
    ) -> List[str]:
        """解析角色名称到角色ID"""

        character_ids = []
        for name_data in character_names:
            # name_data可能是字符串或字典
            name = name_data if isinstance(name_data, str) else name_data.get("name", "")

            for char in story_bible.characters:
                if char.name == name or name in char.aliases:
                    character_ids.append(char.id)
                    break

        return character_ids

    def _load_prompt(self, prompt_name: str) -> Dict[str, Any]:
        """加载prompt模板"""
        import yaml
        import os

        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "prompts",
            f"{prompt_name}.yaml"
        )

        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)

        return {
            "name": prompt_name,
            "version": "1.0",
            "model_tier": "standard",
            "system_prompt": "你是一个专业的剧本创作分析师，擅长将小说文本拆分为场景。",
            "user_prompt_template": """请将以下章节文本拆分为场景。

## 章节标题: {chapter_title}

## 章节内容:
{chapter_text}

## 可用角色:
{character_info}

## 可用地点:
{location_info}

要求：
1. 每个场景必须有dramatic_purpose（戏剧目的）
2. 每个场景必须有conflict（冲突描述）
3. 场景边界基于地点变化、时间变化或叙事视角变化
4. 每个场景需要指定heading（INT/EXT、地点、时间）
5. 标注出场角色

请输出JSON格式：
{"scenes": [{"title": "...", "dramatic_purpose": "...", "conflict": "...", "characters": [...], "heading": {"context": "INT/EXT", "location_name": "...", "time_of_day": "日/夜"}, "beats": [{"description": "..."}]}]}""",
            "temperature": 0.3,
            "max_retries": 2,
        }