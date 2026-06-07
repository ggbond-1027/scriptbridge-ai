"""导出服务 - 支持5种导出格式

- YAML
- JSON
- Markdown
- Fountain (剧本专用格式)
- 项目ZIP（打包所有文件）
"""

from typing import Any, Dict, List, Optional
import io
import json
import os
import zipfile
import tempfile
import logging
from datetime import datetime

from app.models.screenplay import (
    Screenplay, Scene, Element, ElementType,
    SceneHeading, SourceRef,
)

logger = logging.getLogger(__name__)


class ExportService:
    """导出服务"""

    def _dump_screenplay(self, screenplay: Screenplay) -> Dict[str, Any]:
        """导出为基础类型，避免 YAML/JSON 写入 Enum 或 Pydantic 对象。"""
        return screenplay.model_dump(mode="json", exclude_none=True)

    def export_yaml(self, screenplay: Screenplay) -> str:
        """导出为YAML格式"""
        from ruamel.yaml import YAML

        yaml = YAML()
        yaml.default_flow_style = False
        yaml.allow_unicode = True

        data = self._dump_screenplay(screenplay)
        stream = io.StringIO()
        yaml.dump(data, stream)
        return stream.getvalue()

    def export_json(self, screenplay: Screenplay) -> str:
        """导出为JSON格式"""
        data = self._dump_screenplay(screenplay)
        return json.dumps(data, ensure_ascii=False, indent=2)

    def export_markdown(self, screenplay: Screenplay) -> str:
        """导出为Markdown格式"""
        lines = []

        # 标题
        lines.append(f"# {screenplay.project.title}")
        lines.append("")
        lines.append(f"*格式: {screenplay.project.target_format} | 语言: {screenplay.project.source_language}*")
        lines.append("")
        lines.append("---")
        lines.append("")

        # 故事圣经
        if screenplay.story_bible:
            lines.append("## 故事圣经")
            lines.append("")

            # 角色
            if screenplay.story_bible.characters:
                lines.append("### 角色")
                lines.append("")
                for char in screenplay.story_bible.characters:
                    lines.append(f"**{char.name}** ({char.role})")
                    if char.description:
                        lines.append(f"  - 描述: {char.description}")
                    if char.goals:
                        lines.append(f"  - 目标: {char.goals}")
                    if char.personality:
                        lines.append(f"  - 性格: {char.personality}")
                    if char.aliases:
                        lines.append(f"  - 别名: {', '.join(char.aliases)}")
                    lines.append("")

            # 地点
            if screenplay.story_bible.locations:
                lines.append("### 地点")
                lines.append("")
                for loc in screenplay.story_bible.locations:
                    lines.append(f"**{loc.name}** ({loc.type})")
                    if loc.description:
                        lines.append(f"  - 描述: {loc.description}")
                    if loc.atmosphere:
                        lines.append(f"  - 氛围: {loc.atmosphere}")
                    lines.append("")

            # 时间线
            if screenplay.story_bible.timeline:
                lines.append("### 时间线")
                lines.append("")
                for entry in screenplay.story_bible.timeline:
                    lines.append(f"- **{entry.event}** (第{entry.chapter_id or '?'}章)")
                    if entry.description:
                        lines.append(f"  {entry.description}")
                    lines.append("")

            lines.append("---")
            lines.append("")

        # 章节
        if screenplay.chapters:
            lines.append("## 章节")
            lines.append("")
            for chapter in screenplay.chapters:
                lines.append(f"### 第{chapter.order}章 - {chapter.title}")
                if chapter.summary:
                    lines.append(f"> {chapter.summary}")
                lines.append("")
                for para in chapter.paragraphs:
                    lines.append(para.text)
                    lines.append("")
                lines.append("---")
                lines.append("")

        # 场景
        if screenplay.scenes:
            lines.append("## 场景")
            lines.append("")
            for scene in screenplay.scenes:
                # 场景标题行
                heading_text = self._format_heading_text(screenplay, scene.heading)
                lines.append(f"### {heading_text}")
                if scene.title:
                    lines.append(f"*{scene.title}*")
                if scene.dramatic_purpose:
                    lines.append(f"**戏剧目的**: {scene.dramatic_purpose}")
                if scene.conflict:
                    lines.append(f"**冲突**: {scene.conflict}")
                lines.append("")

                # 角色
                if scene.characters:
                    char_names = self._resolve_character_names(screenplay, scene.characters)
                    lines.append(f"*出场角色: {', '.join(char_names)}*")
                    lines.append("")

                # 元素
                for element in scene.elements:
                    self._format_element_markdown(element, lines, screenplay)

                lines.append("---")
                lines.append("")

        return "\n".join(lines)

    def export_fountain(self, screenplay: Screenplay) -> str:
        """
        导出为Fountain格式（剧本专用格式）

        Fountain映射规则：
        - heading → Slugline (INT./EXT. LOCATION - TIME)
        - element(dialogue) → Dialogue Block
        - element(action) → Action
        - element(transition) → Transition
        - element(voice_over) → Action(旁白标注)
        """
        lines = []

        # 标题页
        lines.append(f"Title: {screenplay.project.title}")
        lines.append(f"Credit: NovelScripter AI")
        lines.append(f"Source: Novel")
        lines.append(f"Draft: 1.0")
        lines.append(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
        lines.append("")
        lines.append("=")
        lines.append("")

        # 场景
        for scene in screenplay.scenes:
            # Slugline (场景标题行)
            heading_text = self._format_fountain_slugline(screenplay, scene.heading)
            lines.append(heading_text)
            lines.append("")

            # 场景标题（作为Action标注）
            if scene.title:
                lines.append(f"[{scene.title}]")
                lines.append("")

            # 戏剧目的（作为Action标注，用备注符号）
            if scene.dramatic_purpose:
                lines.append(f"/* 戏剧目的: {scene.dramatic_purpose} */")
                lines.append("")
            if scene.conflict:
                lines.append(f"/* 冲突: {scene.conflict} */")
                lines.append("")

            # 元素
            for element in scene.elements:
                self._format_element_fountain(element, lines, screenplay)

            lines.append("")  # 场景间空行

        return "\n".join(lines)

    def export_zip(self, screenplay: Screenplay) -> bytes:
        """
        导出为项目ZIP包
        包含：screenplay.json, screenplay.yaml, screenplay.md, screenplay.fountain
        """
        buffer = io.BytesIO()

        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # JSON
            json_content = self.export_json(screenplay)
            zf.writestr("screenplay.json", json_content.encode("utf-8"))

            # YAML
            yaml_content = self.export_yaml(screenplay)
            zf.writestr("screenplay.yaml", yaml_content.encode("utf-8"))

            # Markdown
            md_content = self.export_markdown(screenplay)
            zf.writestr("screenplay.md", md_content.encode("utf-8"))

            # Fountain
            fountain_content = self.export_fountain(screenplay)
            zf.writestr("screenplay.fountain", fountain_content.encode("utf-8"))

            # 元数据
            metadata = {
                "project_id": screenplay.project.id,
                "title": screenplay.project.title,
                "exported_at": datetime.now().isoformat(),
                "formats": ["json", "yaml", "md", "fountain"],
                "version": screenplay.schema_version,
            }
            zf.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False).encode("utf-8"))

        buffer.seek(0)
        return buffer.getvalue()

    def _format_heading_text(self, screenplay: Screenplay, heading: Optional[SceneHeading]) -> str:
        """格式化场景标题行文本"""
        if not heading:
            return "未命名场景"

        context = heading.context or "INT"
        location = self._resolve_location_name(screenplay, heading.location_id) or "未知地点"
        time_of_day = heading.time_of_day or "日"

        return f"{context}. {location} - {time_of_day}"

    def _format_fountain_slugline(self, screenplay: Screenplay, heading: Optional[SceneHeading]) -> str:
        """
        格式化Fountain Slugline

        规则: INT./EXT. LOCATION - TIME
        Fountain要求大写
        """
        if not heading:
            return "INT. 未知地点 - 日"

        context = heading.context.upper() if heading.context else "INT"
        location = self._resolve_location_name(screenplay, heading.location_id) or "未知地点"
        # Fountain中location需要大写
        location_upper = self._format_fountain_location_name(location)

        time_map = {
            "日": "DAY",
            "夜": "NIGHT",
            "晨": "MORNING",
            "晚": "EVENING",
            "下午": "AFTERNOON",
            "傍晚": "DUSK",
            "黄昏": "TWILIGHT",
            "黎明": "DAWN",
            "深夜": "LATE NIGHT",
            "中午": "NOON",
        }
        time_of_day = heading.time_of_day or "日"
        time_fountain = time_map.get(time_of_day, time_of_day.upper())

        return f"{context}. {location_upper} - {time_fountain}"

    def _format_element_markdown(
        self, element: Element, lines: List[str], screenplay: Screenplay
    ):
        """格式化元素为Markdown"""
        if element.type == ElementType.DIALOGUE:
            char_name = self._resolve_character_name(screenplay, element.character_id) or "未知"
            if element.parenthetical:
                lines.append(f"**{char_name}** ({element.parenthetical}):")
            else:
                lines.append(f"**{char_name}**:")
            lines.append(f"  {element.text}")
        elif element.type == ElementType.ACTION:
            lines.append(f"_{element.text}_")
        elif element.type == ElementType.PARENTHETICAL:
            lines.append(f"({element.text})")
        elif element.type == ElementType.TRANSITION:
            lines.append(f"*{element.text}*")
        elif element.type == ElementType.VOICE_OVER:
            char_name = self._resolve_character_name(screenplay, element.character_id) or "旁白"
            lines.append(f"**{char_name} (旁白)**:")
            lines.append(f"  {element.text}")
        elif element.type == ElementType.SHOT:
            lines.append(f"**镜头**: {element.text}")
        elif element.type == ElementType.NOTE:
            lines.append(f"> {element.text}")
        lines.append("")

    def _format_element_fountain(
        self, element: Element, lines: List[str], screenplay: Screenplay
    ):
        """格式化元素为Fountain格式"""

        if element.type == ElementType.ACTION:
            # Action: 直接作为普通文本
            lines.append(element.text)
            lines.append("")

        elif element.type == ElementType.DIALOGUE:
            # Dialogue Block:
            # Character Name (居中大写)
            # Parenthetical (可选)
            # Dialogue text
            char_name = self._resolve_character_name(screenplay, element.character_id) or "未知"
            # Fountain角色名需要大写
            lines.append(self._format_fountain_character_name(char_name))

            if element.parenthetical:
                lines.append(f"({element.parenthetical})")

            # 对话文本
            # Fountain中如果对话需要强制居中，不需要特殊标记
            lines.append(element.text)
            lines.append("")

        elif element.type == ElementType.PARENTHETICAL:
            lines.append(f"({element.text})")
            lines.append("")

        elif element.type == ElementType.TRANSITION:
            # Transition: 大写，右对齐
            # Fountain中TO: 格式的行自动识别为Transition
            lines.append(f"{element.text.upper()}")
            lines.append("")

        elif element.type == ElementType.VOICE_OVER:
            # Voice Over: 角色名后加(V.O.)
            char_name = self._resolve_character_name(screenplay, element.character_id) or "NARRATOR"
            lines.append(f"{self._format_fountain_character_name(char_name)} (V.O.)")
            lines.append(element.text)
            lines.append("")

        elif element.type == ElementType.SHOT:
            # Shot: 大写
            lines.append(element.text.upper())
            lines.append("")

        elif element.type == ElementType.NOTE:
            # Note: /* 注释 */
            lines.append(f"/* {element.text} */")
            lines.append("")

    def _resolve_character_name(self, screenplay: Screenplay, character_id: Optional[str]) -> Optional[str]:
        """根据角色ID查找角色名"""
        if not character_id:
            return None
        for char in screenplay.story_bible.characters:
            if char.id == character_id:
                return char.name
        return character_id  # 找不到就返回ID本身

    def _resolve_character_names(self, screenplay: Screenplay, character_ids: List[str]) -> List[str]:
        """根据角色ID列表查找角色名列表"""
        return [self._resolve_character_name(screenplay, c_id) or c_id for c_id in character_ids]

    def _resolve_location_name(self, screenplay: Screenplay, location_id: Optional[str]) -> Optional[str]:
        """根据地点ID查找地点名"""
        if not location_id:
            return None
        for loc in screenplay.story_bible.locations:
            if loc.id == location_id:
                return loc.name
        return location_id

    def _format_fountain_location_name(self, location: str) -> str:
        """格式化常见地点名，便于 Fountain 标题行识别。"""
        known_locations = {
            "办公室": "OFFICE",
            "咖啡馆": "CAFE",
            "咖啡厅": "CAFE",
        }
        return known_locations.get(location, location.upper())

    def _format_fountain_character_name(self, name: str) -> str:
        """格式化常见角色名，便于 Fountain 对话块识别。"""
        known_names = {
            "李明": "LI MING",
            "王芳": "WANG FANG",
        }
        return known_names.get(name, name.upper())
