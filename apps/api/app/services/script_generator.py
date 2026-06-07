"""剧本元素生成服务 - 为每个场景生成剧本元素

生成元素类型：
- action（动作描写）
- dialogue（对话）
- parenthetical（括号提示语）
- transition（转场）
- voice_over（旁白/内心独白）
- shot（镜头指示）
- note（注释）
"""

from typing import Any, Dict, List, Optional
import logging
import uuid

from app.models.screenplay import (
    Scene, Element, ElementType, SceneContext,
    StoryBible, SourceRef,
)
from app.core.llm_provider import LLMProvider
from app.core.model_router import ModelRouter, TaskType

logger = logging.getLogger(__name__)


class ScriptGenerator:
    """剧本元素生成服务"""

    def __init__(self, llm_provider: LLMProvider, model_router: ModelRouter):
        self.llm_provider = llm_provider
        self.model_router = model_router

    async def generate_elements(
        self,
        scenes: List[Scene],
        story_bible: StoryBible,
    ) -> List[Scene]:
        """
        为每个场景生成剧本元素

        处理流程：
        1. 获取场景的源文本内容
        2. 使用AI将源文本转换为剧本元素
        3. 为每个元素分配ID、类型、角色引用
        4. 关联源文本引用
        """
        element_counter = 0

        for scene in scenes:
            # 获取场景的源文本
            source_text = self._get_scene_source_text(scene)

            if not source_text:
                continue

            # 构造角色映射
            character_map = self._build_character_map(scene, story_bible)

            # 使用AI生成元素
            generated_elements = await self._ai_generate_elements(
                scene, source_text, story_bible, character_map
            )

            # 如果AI生成失败，使用回退策略
            if not generated_elements:
                generated_elements = self._fallback_generate(
                    scene, source_text, character_map
                )

            # 分配ID和添加到场景
            for elem_data in generated_elements:
                element_counter += 1

                element_type = elem_data.get("type", "action")
                try:
                    elem_type = ElementType(element_type)
                except ValueError:
                    elem_type = ElementType.ACTION

                # 解析角色引用
                character_id = self._resolve_character(
                    elem_data.get("character_name"), character_map
                )

                # 构造源引用
                source_ref = None
                if scene.source_refs:
                    source_ref = SourceRef(
                        chapter_id=scene.source_refs[0].chapter_id,
                        paragraph_ids=scene.source_refs[0].paragraph_ids[:1],
                    )

                element = Element(
                    id=f"el_{element_counter}",
                    type=elem_type,
                    text=elem_data.get("text", ""),
                    character_id=character_id,
                    emotion=elem_data.get("emotion"),
                    parenthetical=elem_data.get("parenthetical"),
                    source_ref=source_ref,
                )
                scene.elements.append(element)

        return scenes

    async def _ai_generate_elements(
        self,
        scene: Scene,
        source_text: str,
        story_bible: StoryBible,
        character_map: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """使用AI生成剧本元素"""

        # 加载prompt模板
        prompt_data = self._load_prompt("element_generation")

        # 构造角色信息
        char_info = "\n".join([
            f"- {name} (ID: {id})"
            for name, id in character_map.items()
        ])

        # 构造场景信息
        scene_info = ""
        if scene.heading:
            context = scene.heading.context.value if scene.heading.context else "INT"
            scene_info += f"场景: {context}. {scene.heading.location_id or '未知地点'} - {scene.heading.time_of_day}\n"
        if scene.dramatic_purpose:
            scene_info += f"戏剧目的: {scene.dramatic_purpose}\n"
        if scene.conflict:
            scene_info += f"冲突: {scene.conflict}\n"

        # 构造用户提示
        user_prompt = prompt_data["user_prompt_template"].format(
            scene_info=scene_info,
            source_text=source_text[:3000],
            character_info=char_info[:500],
        )

        # 使用LLM生成
        result = await self.llm_provider.generate_structured(
            output_type=dict,
            task_type=TaskType.ELEMENT_GENERATION,
            prompt=user_prompt,
            system_prompt=prompt_data["system_prompt"],
            temperature=prompt_data.get("temperature", 0.5),
        )

        if result.success and result.content:
            return result.content.get("elements", [])

        return []

    def _fallback_generate(
        self,
        scene: Scene,
        source_text: str,
        character_map: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """回退策略：基于规则将源文本转换为剧本元素"""

        elements = []
        paragraphs = source_text.split('\n')

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 检测对话（引号内容）
            dialogue_match = self._detect_dialogue(para)
            if dialogue_match:
                elements.append(dialogue_match)
                continue

            # 检测旁白/内心独白
            voice_over_match = self._detect_voice_over(para)
            if voice_over_match:
                elements.append(voice_over_match)
                continue

            # 检测转场提示
            transition_match = self._detect_transition(para)
            if transition_match:
                elements.append(transition_match)
                continue

            # 默认为动作描写
            elements.append({
                "type": "action",
                "text": para,
            })

        # 在场景开头添加场景heading对应的action
        if scene.heading:
            context = scene.heading.context.value if scene.heading.context else "INT"
            heading_text = f"{context}. {scene.heading.location_id or '未知地点'} - {scene.heading.time_of_day}"
            elements.insert(0, {
                "type": "action",
                "text": heading_text,
            })

        # 在场景末尾添加转场
        if len(elements) > 0:
            elements.append({
                "type": "transition",
                "text": "切至下一场景",
            })

        return elements

    def _detect_dialogue(self, text: str) -> Optional[Dict[str, Any]]:
        """检测中文对话格式"""
        # 中文引号对话："XXX" 或 "XXX"
        import re
        patterns = [
            # 角色名+冒号+引号对话：李明："你来了。"
            re.compile(r'^([^：:""]+)\s*[：:]\s*[""「](.+)[""」]$'),
            # 纯引号对话："你来了。"
            re.compile(r'^[""「](.+)[""」]$'),
            # 角色名+冒号+无引号对话：李明：你来了。
            re.compile(r'^([^：:]{2,10})\s*[：:]\s*(.+)$'),
        ]

        for pattern in patterns:
            match = pattern.match(text)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    character_name = groups[0].strip()
                    dialogue_text = groups[1].strip()

                    return {
                        "type": "dialogue",
                        "text": dialogue_text,
                        "character_name": character_name,
                    }
                elif len(groups) >= 1:
                    return {
                        "type": "dialogue",
                        "text": groups[0].strip(),
                    }

        return None

    def _detect_voice_over(self, text: str) -> Optional[Dict[str, Any]]:
        """检测旁白/内心独白"""
        import re

        # 内心独白提示词
        inner_markers = [
            "心想", "暗想", "暗自", "心中", "内心", "暗道",
            "想着", "不禁想", "喃喃", "自言自语",
        ]

        for marker in inner_markers:
            if marker in text:
                return {
                    "type": "voice_over",
                    "text": text,
                }

        return None

    def _detect_transition(self, text: str) -> Optional[Dict[str, Any]]:
        """检测转场提示"""
        transitions = [
            "镜头转向", "切到", "切换到", "转移到",
            "画面一转", "与此同时", "此时", "另一边",
            "淡出", "淡入", "黑屏", "时间流逝",
        ]

        for trans in transitions:
            if text.startswith(trans):
                return {
                    "type": "transition",
                    "text": text,
                }

        return None

    def _get_scene_source_text(self, scene: Scene) -> str:
        """获取场景关联的源文本"""
        # 在简化模式下，从场景的beats中提取
        texts = []
        for beat in scene.beats:
            if beat.description:
                texts.append(beat.description)

        return "\n".join(texts)

    def _build_character_map(
        self, scene: Scene, story_bible: StoryBible
    ) -> Dict[str, str]:
        """构建角色名到ID的映射"""
        char_map = {}
        for char_id in scene.characters:
            for char in story_bible.characters:
                if char.id == char_id:
                    char_map[char.name] = char.id
                    for alias in char.aliases:
                        char_map[alias] = char.id
                    break
        return char_map

    def _resolve_character(
        self, character_name: Optional[str], character_map: Dict[str, str]
    ) -> Optional[str]:
        """解析角色名到ID"""
        if not character_name:
            return None

        # 直接查找
        if character_name in character_map:
            return character_map[character_name]

        # 模糊查找
        for name, id in character_map.items():
            if character_name in name or name in character_name:
                return id

        return None

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
            "model_tier": "premium",
            "system_prompt": "你是一个专业的剧本编剧，擅长将小说文本转化为剧本元素格式。",
            "user_prompt_template": """请将以下场景的源文本转化为剧本元素。

## 场景信息:
{scene_info}

## 源文本:
{source_text}

## 角色列表:
{character_info}

要求：
1. 每个元素指定类型：action, dialogue, parenthetical, transition, voice_over, shot, note
2. 对话元素必须指定角色
3. 保持叙事连贯性
4. 对话需要自然、生动
5. 动作描写需要简洁、视觉化

请输出JSON格式：
{"elements": [{"type": "action/dialogue/...", "text": "...", "character_name": "...(对话必填)", "emotion": "...(可选)", "parenthetical": "...(可选)"}]}""",
            "temperature": 0.5,
            "max_retries": 2,
        }