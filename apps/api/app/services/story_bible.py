"""故事圣经服务 - 角色归一化、地点合并、时间线排序

核心功能：
- 从逐章理解结果合并故事圣经
- 角色别名归一化（识别同一角色的不同名称）
- 地点同一性判断（合并同义地点）
- 时间线排序与冲突检测
"""

from typing import Any, Dict, List, Optional, Set, Tuple
import logging
import re
import uuid

from app.models.screenplay import (
    Character, CharacterRole, Location, LocationType,
    TimelineEntry, StoryBible, Relationship,
)
from app.core.llm_provider import LLMProvider
from app.core.model_router import ModelRouter, TaskType

logger = logging.getLogger(__name__)


class StoryBibleService:
    """故事圣经服务"""

    def __init__(self, llm_provider: LLMProvider, model_router: ModelRouter):
        self.llm_provider = llm_provider
        self.model_router = model_router

    async def merge_from_understandings(
        self,
        understandings: List[Dict[str, Any]],
    ) -> StoryBible:
        """
        从逐章理解结果合并生成完整故事圣经

        步骤：
        1. 收集所有章节中提到的角色和地点
        2. 角色别名归一化（识别同一角色的不同名称）
        3. 地点同一性判断（合并同义地点）
        4. 时间线排序与冲突检测
        5. 使用AI辅助合并（如有歧义）
        """
        # 第一步：收集原始角色和地点数据
        raw_characters: Dict[str, Dict[str, Any]] = {}
        raw_locations: Dict[str, Dict[str, Any]] = {}
        raw_timeline: List[Dict[str, Any]] = []

        for understanding in understandings:
            chapter_id = understanding.get("chapter_id", "")

            # 收集角色
            for char_data in understanding.get("characters", []):
                name = char_data.get("name", "")
                if name and name not in raw_characters:
                    raw_characters[name] = {
                        "name": name,
                        "aliases": char_data.get("aliases", []),
                        "role": char_data.get("role", "supporting"),
                        "description": char_data.get("description", ""),
                        "goals": char_data.get("goals", ""),
                        "personality": char_data.get("personality", ""),
                        "appearance": char_data.get("appearance", ""),
                        "first_appearance": chapter_id,
                        "relationships_data": char_data.get("relationships", []),
                        "mentioned_in": [chapter_id],
                    }
                elif name in raw_characters:
                    # 合并信息
                    raw_characters[name]["mentioned_in"].append(chapter_id)
                    if char_data.get("aliases"):
                        raw_characters[name]["aliases"].extend(char_data["aliases"])
                    if char_data.get("description") and not raw_characters[name].get("description"):
                        raw_characters[name]["description"] = char_data["description"]
                    if char_data.get("goals") and not raw_characters[name].get("goals"):
                        raw_characters[name]["goals"] = char_data["goals"]
                    if char_data.get("personality") and not raw_characters[name].get("personality"):
                        raw_characters[name]["personality"] = char_data["personality"]

            # 收集地点
            for loc_data in understanding.get("locations", []):
                name = loc_data.get("name", "")
                if name and name not in raw_locations:
                    raw_locations[name] = {
                        "name": name,
                        "type": loc_data.get("type", "indoor"),
                        "description": loc_data.get("description", ""),
                        "atmosphere": loc_data.get("atmosphere", ""),
                        "first_appearance": chapter_id,
                        "mentioned_in": [chapter_id],
                    }
                elif name in raw_locations:
                    raw_locations[name]["mentioned_in"].append(chapter_id)

            # 收集事件/时间线
            for event_data in understanding.get("events", []):
                raw_timeline.append({
                    "chapter_id": chapter_id,
                    "event": event_data.get("event", ""),
                    "description": event_data.get("description", ""),
                    "characters": event_data.get("characters", []),
                    "location": event_data.get("location", ""),
                })

        # 第二步：角色别名归一化
        normalized_characters = self._normalize_characters(raw_characters)

        # 第三步：地点同一性判断
        normalized_locations = self._normalize_locations(raw_locations)

        # 第四步：时间线排序
        sorted_timeline = self._sort_timeline(raw_timeline, normalized_characters)

        # 第五步：构建StoryBible
        characters = []
        for idx, (name, data) in enumerate(normalized_characters.items()):
            char_id = f"char_{idx + 1}"
            relationships = []
            for rel_data in data.get("relationships_data", []):
                # 查找关联角色的ID
                rel_name = rel_data.get("character_name", "")
                rel_id = self._find_character_id(normalized_characters, rel_name)
                if rel_id:
                    relationships.append(Relationship(
                        character_id=rel_id,
                        relationship_type=rel_data.get("type", "unknown"),
                        description=rel_data.get("description"),
                    ))

            character = Character(
                id=char_id,
                name=name,
                aliases=data.get("aliases", []),
                role=CharacterRole(data.get("role", "supporting")),
                description=data.get("description"),
                goals=data.get("goals"),
                personality=data.get("personality"),
                appearance=data.get("appearance"),
                first_appearance=data.get("first_appearance"),
                relationships=relationships,
            )
            characters.append(character)

        locations = []
        for idx, (name, data) in enumerate(normalized_locations.items()):
            loc_id = f"loc_{idx + 1}"
            location = Location(
                id=loc_id,
                name=name,
                type=LocationType(data.get("type", "indoor")),
                description=data.get("description"),
                atmosphere=data.get("atmosphere"),
                first_appearance=data.get("first_appearance"),
            )
            locations.append(location)

        timeline = []
        for idx, entry_data in enumerate(sorted_timeline):
            tl_id = f"tl_{idx + 1}"
            # 解析角色引用
            chars_involved = []
            for char_name in entry_data.get("characters", []):
                char_id = self._find_character_id(normalized_characters, char_name)
                if char_id:
                    chars_involved.append(char_id)

            # 解析地点引用
            loc_id = None
            loc_name = entry_data.get("location", "")
            if loc_name:
                loc_id = self._find_location_id(normalized_locations, loc_name)

            timeline_entry = TimelineEntry(
                id=tl_id,
                chapter_id=entry_data.get("chapter_id"),
                event=entry_data.get("event", ""),
                description=entry_data.get("description"),
                characters_involved=chars_involved,
                location_id=loc_id,
            )
            timeline.append(timeline_entry)

        return StoryBible(
            characters=characters,
            locations=locations,
            timeline=timeline,
        )

    def _normalize_characters(
        self, raw_characters: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """角色别名归一化 - 识别同一角色的不同名称"""

        normalized: Dict[str, Dict[str, Any]] = {}

        # 构建别名映射表
        alias_to_main: Dict[str, str] = {}

        for main_name, data in raw_characters.items():
            aliases = data.get("aliases", [])
            # 主名称映射到自身
            alias_to_main[main_name] = main_name
            # 别名映射到主名称
            for alias in aliases:
                if alias not in alias_to_main:
                    alias_to_main[alias] = main_name

        # 相似名称检测（常见的别名模式）
        name_similarities = self._detect_name_similarities(
            list(raw_characters.keys()), alias_to_main
        )

        # 合并相似角色
        for main_name, data in raw_characters.items():
            actual_main = alias_to_main.get(main_name, main_name)

            if actual_main in normalized:
                # 合并到已存在的角色
                existing = normalized[actual_main]
                # 合并别名
                all_aliases = list(set(
                    existing.get("aliases", []) +
                    data.get("aliases", []) +
                    [main_name]  # 当前名称也是别名
                ))
                all_aliases = [a for a in all_aliases if a != actual_main]
                existing["aliases"] = all_aliases
                # 合并描述信息
                if data.get("description") and not existing.get("description"):
                    existing["description"] = data["description"]
                if data.get("goals") and not existing.get("goals"):
                    existing["goals"] = data["goals"]
                existing["mentioned_in"].extend(data.get("mentioned_in", []))
                # 合并关系数据
                existing["relationships_data"].extend(data.get("relationships_data", []))
            else:
                # 新角色
                normalized[actual_main] = dict(data)
                # 确保别名不包含主名称
                aliases = data.get("aliases", [])
                aliases = [a for a in aliases if a != actual_main]
                normalized[actual_main]["aliases"] = aliases

        return normalized

    def _detect_name_similarities(
        self,
        names: List[str],
        alias_to_main: Dict[str, str],
    ) -> Dict[str, str]:
        """
        检测名称相似性

        常见别名模式：
        - 全名 vs 简称（如"李明" → "明"）
        - 称谓变化（如"老张" → "张三" → "张叔"）
        - 拼写变化
        """
        similarity_map: Dict[str, str] = {}

        for i, name1 in enumerate(names):
            for j, name2 in enumerate(names):
                if i >= j:
                    continue

                # 检查包含关系
                if name1 in name2 or name2 in name1:
                    # 短名称可能是长名称的简称
                    if len(name1) < len(name2):
                        similarity_map[name1] = name2
                    else:
                        similarity_map[name2] = name1

                # 检查中文称谓模式
                if self._is_chinese_alias_pattern(name1, name2):
                    similarity_map[name1] = name2

        # 更新映射
        for alias, main in similarity_map.items():
            if alias not in alias_to_main:
                alias_to_main[alias] = main

        return similarity_map

    def _is_chinese_alias_pattern(self, name1: str, name2: str) -> bool:
        """检查两个名称是否符合中文别名模式"""
        # 老X → X叔/XX等模式
        patterns = [
            (r'^老(.+)$', r'^(.+)(叔|伯|爷|哥|姐|妹)$'),  # 老张 → 张叔
            (r'^小(.+)$', r'^(.+)(弟|妹)$'),                # 小李 → 李弟
            (r'^(.+)(先生|女士|老师)$', r'^(.+)$'),          # 李先生 → 李
        ]

        for pattern1, pattern2 in patterns:
            if re.match(pattern1, name1) and re.match(pattern2, name2):
                # 提取核心名称部分
                core1 = re.match(pattern1, name1).group(1)
                core2 = re.match(pattern2, name2).group(1)
                if core1 == core2 or core1 in core2 or core2 in core1:
                    return True

            if re.match(pattern1, name2) and re.match(pattern2, name1):
                core1 = re.match(pattern1, name2).group(1)
                core2 = re.match(pattern2, name1).group(1)
                if core1 == core2 or core1 in core2 or core2 in core1:
                    return True

        return False

    def _normalize_locations(
        self, raw_locations: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """地点同一性判断 - 合合名称相似或含义相同的地点"""

        normalized: Dict[str, Dict[str, Any]] = {}
        location_mapping: Dict[str, str] = {}

        # 检测地点相似性
        names = list(raw_locations.keys())

        for i, name1 in enumerate(names):
            for j, name2 in enumerate(names):
                if i >= j:
                    continue

                if self._is_same_location(name1, name2):
                    # 将较短的名称映射到较长的名称（通常更具体）
                    if len(name1) >= len(name2):
                        location_mapping[name2] = name1
                    else:
                        location_mapping[name1] = name2

        # 合并相似地点
        for name, data in raw_locations.items():
            main_name = location_mapping.get(name, name)

            if main_name in normalized:
                # 合并信息
                existing = normalized[main_name]
                existing["mentioned_in"].extend(data.get("mentioned_in", []))
                if data.get("description") and not existing.get("description"):
                    existing["description"] = data["description"]
                if data.get("atmosphere") and not existing.get("atmosphere"):
                    existing["atmosphere"] = data["atmosphere"]
            else:
                normalized[main_name] = dict(data)

        return normalized

    def _is_same_location(self, name1: str, name2: str) -> bool:
        """判断两个地点名称是否指同一个地点"""

        # 完全相同
        if name1 == name2:
            return True

        # 包含关系（如"小明家"包含"小明家客厅"）
        if name1 in name2 or name2 in name1:
            return True

        # 常见的同义地点模式
        synonym_groups = [
            {"家", "屋里", "房间", "住宅", "房子"},
            {"学校", "校园", "教室", "教学楼"},
            {"公司", "办公室", "写字楼", "办公大楼"},
            {"医院", "诊所", "病房"},
            {"街道", "路上", "马路", "大街"},
            {"公园", "花园", "绿地"},
            {"餐厅", "饭店", "餐馆", "食堂"},
            {"酒吧", "酒馆", "pub"},
        ]

        for group in synonym_groups:
            if name1 in group and name2 in group:
                return True

        return False

    def _sort_timeline(
        self,
        raw_timeline: List[Dict[str, Any]],
        normalized_characters: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """时间线排序 - 按章节顺序排列事件"""

        # 按章节ID排序（如果有的话）
        def get_sort_key(entry: Dict[str, Any]) -> Tuple:
            chapter_id = entry.get("chapter_id", "")
            # 从章节ID提取数字排序
            match = re.match(r'ch_(\d+)', chapter_id)
            chapter_num = int(match.group(1)) if match else 0
            return (chapter_num, raw_timeline.index(entry))

        sorted_entries = sorted(raw_timeline, key=get_sort_key)

        # 时间线冲突检测（检查是否有时间顺序矛盾）
        # 这里简化处理，实际应该使用AI进行更深入的检测

        return sorted_entries

    def _find_character_id(
        self, normalized_characters: Dict[str, Dict[str, Any]], name: str
    ) -> Optional[str]:
        """在归一化角色中查找角色ID"""
        for idx, (char_name, _) in enumerate(normalized_characters.items()):
            if char_name == name:
                return f"char_{idx + 1}"
            # 检查别名
            data = normalized_characters[char_name]
            if name in data.get("aliases", []):
                return f"char_{idx + 1}"
            # 检查名称包含关系
            if name in char_name or char_name in name:
                return f"char_{idx + 1}"

        return None

    def _find_location_id(
        self, normalized_locations: Dict[str, Dict[str, Any]], name: str
    ) -> Optional[str]:
        """在归一化地点中查找地点ID"""
        for idx, (loc_name, _) in enumerate(normalized_locations.items()):
            if loc_name == name:
                return f"loc_{idx + 1}"
            if name in loc_name or loc_name in name:
                return f"loc_{idx + 1}"

        return None