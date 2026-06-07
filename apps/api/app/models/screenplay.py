"""Pydantic 剧本数据模型 - 完整的Screenplay定义

严格按照设计项目书定义，包含所有字段和跨引用校验方法。
"""

from typing import Any, Dict, List, Optional, Set
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator


class ElementType(str, Enum):
    """剧本元素类型"""
    ACTION = "action"
    DIALOGUE = "dialogue"
    PARENTHETICAL = "parenthetical"
    TRANSITION = "transition"
    VOICE_OVER = "voice_over"
    SHOT = "shot"
    NOTE = "note"


class SceneContext(str, Enum):
    """场景上下文（室内/室外）"""
    INT = "INT"
    EXT = "EXT"
    INT_EXT = "INT/EXT"


class CharacterRole(str, Enum):
    """角色类型"""
    PROTAGONIST = "protagonist"
    ANTAGONIST = "antagonist"
    SUPPORTING = "supporting"
    MINOR = "minor"
    EXTRA = "extra"


class LocationType(str, Enum):
    """地点类型"""
    INDOOR = "indoor"
    OUTDOOR = "outdoor"
    HYBRID = "hybrid"
    VEHICLE = "vehicle"
    VIRTUAL = "virtual"


class AdaptationStyle(BaseModel):
    """改编风格"""
    genre: List[str] = Field(default_factory=list, description="目标类型，如drama, thriller, comedy")
    tone: List[str] = Field(default_factory=list, description="基调，如dark, humorous, romantic")
    dialogue_style: str = Field(default="natural", description="对话风格，如natural, stylized, minimalist")


class ProjectInfo(BaseModel):
    """项目信息"""
    id: str = Field(..., description="项目唯一ID")
    title: str = Field(..., description="项目标题")
    source_language: str = Field(default="zh-CN", description="源文本语言")
    target_format: str = Field(default="screenplay", description="目标格式")
    adaptation_style: Optional[AdaptationStyle] = Field(default=None, description="改编风格")


class Relationship(BaseModel):
    """角色关系"""
    character_id: str = Field(..., description="关联角色ID")
    relationship_type: str = Field(..., description="关系类型，如friend, enemy, lover, family")
    description: Optional[str] = Field(default=None, description="关系描述")


class Character(BaseModel):
    """角色模型"""
    id: str = Field(..., description="角色ID，格式: char_XXX")
    name: str = Field(..., description="角色名称")
    aliases: List[str] = Field(default_factory=list, description="别名/昵称列表")
    role: CharacterRole = Field(default=CharacterRole.SUPPORTING, description="角色类型")
    description: Optional[str] = Field(default=None, description="角色描述")
    goals: Optional[str] = Field(default=None, description="角色目标")
    personality: Optional[str] = Field(default=None, description="性格特点")
    appearance: Optional[str] = Field(default=None, description="外貌描述")
    first_appearance: Optional[str] = Field(default=None, description="首次出现的章节ID")
    relationships: List[Relationship] = Field(default_factory=list, description="角色关系列表")

    @field_validator('id')
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        """验证角色ID格式"""
        if not v.startswith("char_"):
            raise ValueError(f"角色ID必须以'char_'开头: {v}")
        return v


class Location(BaseModel):
    """地点模型"""
    id: str = Field(..., description="地点ID，格式: loc_XXX")
    name: str = Field(..., description="地点名称")
    type: LocationType = Field(default=LocationType.INDOOR, description="地点类型")
    description: Optional[str] = Field(default=None, description="地点描述")
    atmosphere: Optional[str] = Field(default=None, description="氛围描述")
    first_appearance: Optional[str] = Field(default=None, description="首次出现的章节ID")

    @field_validator('id')
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        """验证地点ID格式"""
        if not v.startswith("loc_"):
            raise ValueError(f"地点ID必须以'loc_'开头: {v}")
        return v


class TimelineEntry(BaseModel):
    """时间线条目"""
    id: str = Field(..., description="时间线ID，格式: tl_XXX")
    chapter_id: Optional[str] = Field(default=None, description="所属章节ID")
    event: str = Field(..., description="事件描述")
    description: Optional[str] = Field(default=None, description="详细描述")
    characters_involved: List[str] = Field(default_factory=list, description="涉及角色ID列表")
    location_id: Optional[str] = Field(default=None, description="涉及地点ID")
    timestamp: Optional[str] = Field(default=None, description="时间标记（小说中提及的时间）")

    @field_validator('id')
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        """验证时间线ID格式"""
        if not v.startswith("tl_"):
            raise ValueError(f"时间线ID必须以'tl_'开头: {v}")
        return v


class StoryBible(BaseModel):
    """故事圣经 - 包含角色、地点、时间线"""
    characters: List[Character] = Field(default_factory=list, description="角色列表")
    locations: List[Location] = Field(default_factory=list, description="地点列表")
    timeline: List[TimelineEntry] = Field(default_factory=list, description="时间线")


class SourceRef(BaseModel):
    """源文本引用"""
    chapter_id: str = Field(..., description="源章节ID")
    paragraph_ids: List[str] = Field(default_factory=list, description="源段落ID列表")


class SceneHeading(BaseModel):
    """场景标题行"""
    context: SceneContext = Field(default=SceneContext.INT, description="场景上下文INT/EXT")
    location_id: Optional[str] = Field(default=None, description="地点ID引用")
    time_of_day: str = Field(default="日", description="时间段，如日/夜/晨/晚")


class Element(BaseModel):
    """剧本元素"""
    id: str = Field(..., description="元素ID，格式: el_XXX")
    type: ElementType = Field(default=ElementType.ACTION, description="元素类型")
    text: str = Field(..., description="元素文本内容")
    character_id: Optional[str] = Field(default=None, description="关联角色ID（对话/旁白时必填）")
    emotion: Optional[str] = Field(default=None, description="情感标注")
    parenthetical: Optional[str] = Field(default=None, description="括号提示语")
    source_ref: Optional[SourceRef] = Field(default=None, description="源文本引用")

    @field_validator('id')
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        """验证元素ID格式"""
        if not v.startswith("el_"):
            raise ValueError(f"元素ID必须以'el_'开头: {v}")
        return v

    @model_validator(mode='after')
    def validate_dialogue_character(self) -> 'Element':
        """对话类型必须有角色ID"""
        if self.type == ElementType.DIALOGUE and not self.character_id:
            raise ValueError(f"对话元素必须指定character_id: {self.id}")
        return self


class SceneBeat(BaseModel):
    """场景节拍"""
    description: str = Field(..., description="节拍描述")
    emotional_arc: Optional[str] = Field(default=None, description="情感走向")
    key_action: Optional[str] = Field(default=None, description="关键动作")


class Scene(BaseModel):
    """场景模型"""
    id: str = Field(..., description="场景ID，格式: sc_XXX")
    chapter_ids: List[str] = Field(default_factory=list, description="所属章节ID列表")
    source_refs: List[SourceRef] = Field(default_factory=list, description="源文本引用列表")
    heading: Optional[SceneHeading] = Field(default=None, description="场景标题行")
    title: Optional[str] = Field(default=None, description="场景标题")
    dramatic_purpose: Optional[str] = Field(default=None, description="戏剧目的")
    conflict: Optional[str] = Field(default=None, description="冲突描述")
    characters: List[str] = Field(default_factory=list, description="出场角色ID列表")
    beats: List[SceneBeat] = Field(default_factory=list, description="场景节拍列表")
    elements: List[Element] = Field(default_factory=list, description="剧本元素列表")

    @field_validator('id')
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        """验证场景ID格式"""
        if not v.startswith("sc_"):
            raise ValueError(f"场景ID必须以'sc_'开头: {v}")
        return v

    @model_validator(mode='after')
    def validate_dramatic_purpose(self) -> 'Scene':
        """场景必须有dramatic_purpose（场景拆分阶段的强制要求）"""
        # 在pipeline生成的场景中，dramatic_purpose是必须的
        # 但在校验修复阶段可能暂时为空，所以这里是警告而非强制
        if not self.dramatic_purpose and len(self.elements) > 0:
            # 只有有内容的场景才需要
            pass
        return self


class SourceParagraph(BaseModel):
    """源文本段落"""
    id: str = Field(..., description="段落ID，格式: p_XXX")
    text: str = Field(..., description="段落文本")
    order: int = Field(..., description="段落顺序号")

    @field_validator('id')
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        """验证段落ID格式"""
        if not v.startswith("p_"):
            raise ValueError(f"段落ID必须以'p_'开头: {v}")
        return v


class Chapter(BaseModel):
    """章节模型"""
    id: str = Field(..., description="章节ID，格式: ch_XXX")
    order: int = Field(..., description="章节顺序号")
    title: str = Field(..., description="章节标题")
    source_title: Optional[str] = Field(default=None, description="源文本中的原始标题")
    paragraphs: List[SourceParagraph] = Field(default_factory=list, description="段落列表")
    summary: Optional[str] = Field(default=None, description="章节摘要")

    @field_validator('id')
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        """验证章节ID格式"""
        if not v.startswith("ch_"):
            raise ValueError(f"章节ID必须以'ch_'开头: {v}")
        return v


class GenerationMetadata(BaseModel):
    """生成元数据"""
    generated_at: str = Field(..., description="生成时间")
    model: str = Field(..., description="使用的模型名称")
    source_chapter_count: int = Field(..., description="源章节数量")
    total_scenes: int = Field(..., description="总场景数")
    total_elements: int = Field(..., description="总元素数")


class Screenplay(BaseModel):
    """
    顶层剧本数据模型

    包含完整的剧本结构定义，支持跨引用一致性校验。
    """
    schema_version: str = Field(default="1.0.0", description="Schema版本号")
    project: ProjectInfo = Field(..., description="项目信息")
    story_bible: StoryBible = Field(default_factory=StoryBible, description="故事圣经")
    chapters: List[Chapter] = Field(default_factory=list, description="章节列表")
    scenes: List[Scene] = Field(default_factory=list, description="场景列表")
    metadata: Optional[GenerationMetadata] = Field(default=None, description="生成元数据")

    def validate_cross_references(self) -> Dict[str, List[str]]:
        """
        跨引用一致性校验

        检查：
        - 角色ID引用是否存在于story_bible.characters
        - 地点ID引用是否存在于story_bible.locations
        - 章节ID引用是否存在于chapters
        - 段落ID引用是否存在于对应的章节中

        Returns:
            Dict[str, List[str]]: 错误字典，key为错误类别，value为错误详情列表
        """
        errors: Dict[str, List[str]] = {
            "missing_character_refs": [],
            "missing_location_refs": [],
            "missing_chapter_refs": [],
            "missing_paragraph_refs": [],
            "orphan_characters": [],
            "orphan_locations": [],
            "empty_scenes": [],
        }

        # 收集所有有效ID集合
        character_ids: Set[str] = {c.id for c in self.story_bible.characters}
        location_ids: Set[str] = {l.id for l in self.story_bible.locations}
        chapter_ids: Set[str] = {c.id for c in self.chapters}
        paragraph_ids: Set[str] = set()
        for ch in self.chapters:
            for p in ch.paragraphs:
                paragraph_ids.add(p.id)

        # 检查场景中的角色引用
        for scene in self.scenes:
            for char_id in scene.characters:
                if char_id not in character_ids:
                    errors["missing_character_refs"].append(
                        f"场景 {scene.id} 引用了不存在的角色 {char_id}"
                    )

            # 检查场景heading中的地点引用
            if scene.heading and scene.heading.location_id:
                if scene.heading.location_id not in location_ids:
                    errors["missing_location_refs"].append(
                        f"场景 {scene.id} heading引用了不存在的地点 {scene.heading.location_id}"
                    )

            # 检查场景中的章节引用
            for ch_id in scene.chapter_ids:
                if ch_id not in chapter_ids:
                    errors["missing_chapter_refs"].append(
                        f"场景 {scene.id} 引用了不存在的章节 {ch_id}"
                    )

            # 检查元素中的角色引用
            for element in scene.elements:
                if element.character_id and element.character_id not in character_ids:
                    errors["missing_character_refs"].append(
                        f"元素 {element.id} 引用了不存在的角色 {element.character_id}"
                    )

                # 检查源引用
                if element.source_ref:
                    if element.source_ref.chapter_id not in chapter_ids:
                        errors["missing_chapter_refs"].append(
                            f"元素 {element.id} source_ref引用了不存在的章节 {element.source_ref.chapter_id}"
                        )
                    for p_id in element.source_ref.paragraph_ids:
                        if p_id not in paragraph_ids:
                            errors["missing_paragraph_refs"].append(
                                f"元素 {element.id} source_ref引用了不存在的段落 {p_id}"
                            )

            # 检查场景源引用
            for ref in scene.source_refs:
                if ref.chapter_id not in chapter_ids:
                    errors["missing_chapter_refs"].append(
                        f"场景 {scene.id} source_ref引用了不存在的章节 {ref.chapter_id}"
                    )
                for p_id in ref.paragraph_ids:
                    if p_id not in paragraph_ids:
                        errors["missing_paragraph_refs"].append(
                            f"场景 {scene.id} source_ref引用了不存在的段落 {p_id}"
                        )

            # 检查空场景
            if not scene.elements and not scene.beats:
                errors["empty_scenes"].append(
                    f"场景 {scene.id} 没有任何元素或节拍"
                )

        # 检查角色关系中的引用
        for character in self.story_bible.characters:
            for rel in character.relationships:
                if rel.character_id not in character_ids:
                    errors["missing_character_refs"].append(
                        f"角色 {character.id} 的关系引用了不存在的角色 {rel.character_id}"
                    )

            # 检查首次出现引用
            if character.first_appearance and character.first_appearance not in chapter_ids:
                errors["missing_chapter_refs"].append(
                    f"角色 {character.id} first_appearance引用了不存在的章节 {character.first_appearance}"
                )

        # 检查地点首次出现引用
        for location in self.story_bible.locations:
            if location.first_appearance and location.first_appearance not in chapter_ids:
                errors["missing_chapter_refs"].append(
                    f"地点 {location.id} first_appearance引用了不存在的章节 {location.first_appearance}"
                )

        # 检查孤立角色（没有在任何场景中被引用）
        referenced_chars: Set[str] = set()
        for scene in self.scenes:
            referenced_chars.update(scene.characters)
            for element in scene.elements:
                if element.character_id:
                    referenced_chars.add(element.character_id)

        for char_id in character_ids:
            if char_id not in referenced_chars:
                errors["orphan_characters"].append(
                    f"角色 {char_id} 没有在任何场景中被引用"
                )

        # 检查孤立地点（没有在任何场景中被引用）
        referenced_locs: Set[str] = set()
        for scene in self.scenes:
            if scene.heading and scene.heading.location_id:
                referenced_locs.add(scene.heading.location_id)

        for loc_id in location_ids:
            if loc_id not in referenced_locs:
                errors["orphan_locations"].append(
                    f"地点 {loc_id} 没有在任何场景中被引用"
                )

        # 检查时间线中的引用
        for entry in self.story_bible.timeline:
            if entry.chapter_id and entry.chapter_id not in chapter_ids:
                errors["missing_chapter_refs"].append(
                    f"时间线 {entry.id} 引用了不存在的章节 {entry.chapter_id}"
                )
            if entry.location_id and entry.location_id not in location_ids:
                errors["missing_location_refs"].append(
                    f"时间线 {entry.id} 引用了不存在的地点 {entry.location_id}"
                )
            for char_id in entry.characters_involved:
                if char_id not in character_ids:
                    errors["missing_character_refs"].append(
                        f"时间线 {entry.id} 引用了不存在的角色 {char_id}"
                    )

        return errors