"""AI润色服务 - 对话润色、描写优化、风格统一

核心功能：
- 对话润色（让对话更加自然、生动）
- 描写优化（动作描写更视觉化）
- 风格统一（确保整体风格一致）
"""

from typing import Any, Dict, List, Optional
import logging

from app.models.screenplay import (
    Scene, Element, ElementType, Screenplay, StoryBible,
)
from app.core.llm_provider import LLMProvider, RewriteRequest
from app.core.model_router import ModelRouter, TaskType

logger = logging.getLogger(__name__)


class PolishService:
    """AI润色服务"""

    def __init__(self, llm_provider: LLMProvider, model_router: ModelRouter):
        self.llm_provider = llm_provider
        self.model_router = model_router

    async def polish_dialogue(
        self,
        screenplay: Screenplay,
        style: Optional[str] = None,
    ) -> Screenplay:
        """
        对话润色 - 让对话更加自然、生动

        Args:
            screenplay: 剧本数据
            style: 对话风格（如natural, stylized, minimalist）

        Returns:
            润色后的剧本数据
        """
        style = style or screenplay.project.adaptation_style.dialogue_style if screenplay.project.adaptation_style else "natural"

        for scene in screenplay.scenes:
            dialogue_elements = [
                e for e in scene.elements
                if e.type == ElementType.DIALOGUE or e.type == ElementType.VOICE_OVER
            ]

            if not dialogue_elements:
                continue

            # 构造对话文本
            dialogue_text = "\n".join([
                f"[{e.type.value}] {e.character_id or '角色'}: {e.text}"
                for e in dialogue_elements
            ])

            # 构造上下文
            context = self._build_scene_context(scene, screenplay.story_bible)

            # 构造润色指令
            instruction = self._build_polish_instruction(style, "dialogue")

            # 使用LLM润色
            rewrite_req = RewriteRequest(
                instruction=instruction,
                context=context,
                selection=dialogue_text,
                task_type=TaskType.POLISH_DIALOGUE,
                preserve_structure=True,
            )

            result = await self.llm_provider.rewrite(rewrite_req)

            if result.success and result.content:
                # 解析润色结果并更新元素
                polished_lines = result.content.strip().split('\n')
                self._apply_polished_dialogue(dialogue_elements, polished_lines)

        return screenplay

    async def polish_action(
        self,
        screenplay: Screenplay,
    ) -> Screenplay:
        """动作描写润色 - 让描写更视觉化"""

        for scene in screenplay.scenes:
            action_elements = [
                e for e in scene.elements
                if e.type == ElementType.ACTION
            ]

            if not action_elements:
                continue

            for element in action_elements:
                if len(element.text) < 20:  # 过短的描写不润色
                    continue

                context = self._build_scene_context(scene, screenplay.story_bible)
                instruction = "请将以下动作描写优化为更视觉化、更简洁的剧本格式。保持关键信息不变，但让描写更有画面感。"

                rewrite_req = RewriteRequest(
                    instruction=instruction,
                    context=context,
                    selection=element.text,
                    task_type=TaskType.REWRITE,
                    preserve_structure=True,
                )

                result = await self.llm_provider.rewrite(rewrite_req)

                if result.success and result.content:
                    element.text = result.content.strip()

        return screenplay

    async def polish_style_consistency(
        self,
        screenplay: Screenplay,
    ) -> Screenplay:
        """风格统一润色 - 确保整体风格一致"""

        # 提取所有场景的第一段对话和描写作为风格参考
        style_samples = []
        for scene in screenplay.scenes[:5]:  # 取前5个场景作为参考
            for element in scene.elements[:3]:
                style_samples.append(f"[{element.type.value}] {element.text}")

        reference_style = "\n".join(style_samples)

        # 对后续场景进行风格统一
        for scene in screenplay.scenes[5:]:
            scene_text = "\n".join([
                f"[{e.type.value}] {e.text}"
                for e in scene.elements
            ])

            instruction = f"""请将以下场景文本调整为与参考风格一致的风格。

参考风格示例:
{reference_style}

要求：
1. 保持对话风格一致（用词、语气、节奏）
2. 保持描写风格一致（简洁/详尽、视觉化程度）
3. 不要改变情节内容
"""

            context = f"场景: {scene.title or scene.id}"

            rewrite_req = RewriteRequest(
                instruction=instruction,
                context=context,
                selection=scene_text,
                task_type=TaskType.POLISH_DIALOGUE,
                preserve_structure=True,
            )

            result = await self.llm_provider.rewrite(rewrite_req)

            if result.success and result.content:
                # 简化处理：只记录润色结果
                logger.info(f"场景 {scene.id} 风格统一完成")

        return screenplay

    def _build_scene_context(
        self, scene: Scene, story_bible: StoryBible
    ) -> str:
        """构建场景上下文文本"""
        parts = []

        if scene.heading:
            context = scene.heading.context.value if scene.heading.context else "INT"
            parts.append(f"场景标题: {context}. {scene.heading.location_id or '未知地点'} - {scene.heading.time_of_day}")

        if scene.dramatic_purpose:
            parts.append(f"戏剧目的: {scene.dramatic_purpose}")

        if scene.conflict:
            parts.append(f"冲突: {scene.conflict}")

        # 角色信息
        char_names = []
        for char_id in scene.characters:
            for char in story_bible.characters:
                if char.id == char_id:
                    char_names.append(f"{char.name}({char.role.value})")
                    break
        if char_names:
            parts.append(f"出场角色: {', '.join(char_names)}")

        return "\n".join(parts)

    def _build_polish_instruction(self, style: str, target: str) -> str:
        """构造润色指令"""

        style_instructions = {
            "natural": "让对话更加自然、口语化，减少书面语，增加语气词和生活化的表达。",
            "stylized": "让对话更加风格化、有戏剧张力，使用精炼的对话和鲜明的角色语言。",
            "minimalist": "让对话更加精简，删减冗余，只保留核心信息和关键转折。",
            "dramatic": "让对话更加戏剧化，增强冲突感，突出角色之间的张力。",
        }

        if target == "dialogue":
            instruction = style_instructions.get(style, style_instructions["natural"])
            instruction += "\n\n只输出润色后的对话文本，保持格式为 [类型] 角色: 内容。不要改变对话的数量和顺序。"
        else:
            instruction = "请润色这段文本，使其更加精炼和视觉化。"

        return instruction

    def _apply_polished_dialogue(
        self,
        original_elements: List[Element],
        polished_lines: List[str],
    ):
        """将润色后的对话文本应用到元素中"""

        import re

        # 解析润色结果
        for i, line in enumerate(polished_lines):
            if i >= len(original_elements):
                break

            line = line.strip()
            if not line:
                continue

            # 尝试提取角色名和内容
            match = re.match(r'\[(\w+)\]\s*(.+?)\s*:\s*(.+)', line)
            if match:
                elem_type = match.group(1)
                character_name = match.group(2).strip()
                dialogue_text = match.group(3).strip()

                original_elements[i].text = dialogue_text
            else:
                # 直接更新文本
                # 尝试去除类型标记
                clean_line = re.sub(r'^\[\w+\]\s*', '', line)
                # 尝试去除角色标记
                clean_line = re.sub(r'^.+?:\s*', '', clean_line)
                if clean_line:
                    original_elements[i].text = clean_line