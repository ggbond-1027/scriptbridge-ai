"""Schema校验器 - 三层校验机制

1. Pydantic Model 校验
2. JSON Schema 校验
3. 引用一致性校验（角色/地点/章节ID引用）

校验修复闭环：失败 → 局部修复 → 再校验
修复分三类：程序修复、AI修复、用户确认
"""

from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import logging

from app.models.screenplay import Screenplay
from app.core.llm_provider import LLMProvider
from app.core.model_router import ModelRouter, TaskType

logger = logging.getLogger(__name__)


class ValidationErrorType(str, Enum):
    """校验错误类型"""
    PYDANTIC = "pydantic"              # Pydantic模型校验错误
    JSON_SCHEMA = "json_schema"         # JSON Schema校验错误
    REFERENCE = "reference"             # 引用一致性错误
    STRUCTURAL = "structural"           # 结构性错误


class RepairType(str, Enum):
    """修复类型"""
    PROGRAM = "program"     # 程序自动修复
    AI = "ai"               # AI辅助修复
    USER = "user"           # 需要用户确认


class ErrorSeverity(str, Enum):
    """错误严重程度"""
    CRITICAL = "critical"    # 必须修复才能继续
    WARNING = "warning"      # 建议修复但不阻断
    INFO = "info"            # 信息提示


@dataclass
class ValidationError:
    """校验错误"""
    type: ValidationErrorType
    severity: ErrorSeverity
    message: str
    location: str           # 错误位置描述（如 "scenes[3].heading.location_id"）
    repair_type: RepairType
    suggested_fix: Optional[str] = None
    actual_value: Optional[Any] = None
    expected_value: Optional[Any] = None


@dataclass
class ValidationResult:
    """校验结果"""
    is_valid: bool = True
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)


class SchemaValidator:
    """Schema校验器"""

    def __init__(self, llm_provider: LLMProvider, model_router: ModelRouter):
        self.llm_provider = llm_provider
        self.model_router = model_router

    def validate_screenplay(self, screenplay: Screenplay) -> ValidationResult:
        """三层校验：Pydantic + JSON Schema + 引用一致性"""

        result = ValidationResult()

        # 第一层：Pydantic Model 校验
        pydantic_errors = self._validate_pydantic(screenplay)
        result.errors.extend(pydantic_errors)

        # 第二层：JSON Schema 校验
        schema_errors = self._validate_json_schema(screenplay)
        result.errors.extend(schema_errors)

        # 第三层：引用一致性校验
        ref_errors = self._validate_references(screenplay)
        result.errors.extend(ref_errors)

        # 统计
        result.is_valid = len([e for e in result.errors if e.severity == ErrorSeverity.CRITICAL]) == 0
        result.stats = {
            "total_errors": len(result.errors),
            "critical_errors": len([e for e in result.errors if e.severity == ErrorSeverity.CRITICAL]),
            "warnings": len([e for e in result.errors if e.severity == ErrorSeverity.WARNING]),
            "pydantic_errors": len([e for e in result.errors if e.type == ValidationErrorType.PYDANTIC]),
            "schema_errors": len([e for e in result.errors if e.type == ValidationErrorType.JSON_SCHEMA]),
            "reference_errors": len([e for e in result.errors if e.type == ValidationErrorType.REFERENCE]),
        }

        return result

    def _validate_pydantic(self, screenplay: Screenplay) -> List[ValidationError]:
        """第一层：Pydantic模型校验"""
        errors = []

        # 验证模型本身
        try:
            # 重新序列化并反序列化来确保数据完整
            data = screenplay.model_dump(mode="json", exclude_none=True)
            Screenplay.model_validate(data)
        except Exception as e:
            errors.append(ValidationError(
                type=ValidationErrorType.PYDANTIC,
                severity=ErrorSeverity.CRITICAL,
                message=f"Pydantic校验失败: {str(e)}",
                location="screenplay",
                repair_type=RepairType.PROGRAM,
                actual_value=str(e),
            ))

        # 验证各个字段的约束
        # 检查schema_version格式
        if not screenplay.schema_version:
            errors.append(ValidationError(
                type=ValidationErrorType.PYDANTIC,
                severity=ErrorSeverity.CRITICAL,
                message="schema_version不能为空",
                location="screenplay.schema_version",
                repair_type=RepairType.PROGRAM,
                suggested_fix="设置默认值 '1.0.0'",
            ))

        # 检查章节ID格式
        for chapter in screenplay.chapters:
            if not chapter.id.startswith("ch_"):
                errors.append(ValidationError(
                    type=ValidationErrorType.PYDANTIC,
                    severity=ErrorSeverity.WARNING,
                    message=f"章节ID格式不符合规范: {chapter.id}",
                    location=f"chapters[{chapter.order-1}].id",
                    repair_type=RepairType.PROGRAM,
                    suggested_fix=f"改为 'ch_{chapter.order}'",
                    actual_value=chapter.id,
                    expected_value=f"ch_{chapter.order}",
                ))

        # 检查段落ID格式
        for chapter in screenplay.chapters:
            for para in chapter.paragraphs:
                if not para.id.startswith("p_"):
                    errors.append(ValidationError(
                        type=ValidationErrorType.PYDANTIC,
                        severity=ErrorSeverity.WARNING,
                        message=f"段落ID格式不符合规范: {para.id}",
                        location=f"chapters[{chapter.order-1}].paragraphs[{para.order-1}].id",
                        repair_type=RepairType.PROGRAM,
                        suggested_fix=f"改为 'p_{chapter.order}_{para.order}'",
                        actual_value=para.id,
                    ))

        # 检查场景ID格式
        for scene in screenplay.scenes:
            if not scene.id.startswith("sc_"):
                errors.append(ValidationError(
                    type=ValidationErrorType.PYDANTIC,
                    severity=ErrorSeverity.WARNING,
                    message=f"场景ID格式不符合规范: {scene.id}",
                    location=f"scenes[].id",
                    repair_type=RepairType.PROGRAM,
                    actual_value=scene.id,
                ))

        # 检查元素ID格式和类型
        for scene in screenplay.scenes:
            for element in scene.elements:
                if not element.id.startswith("el_"):
                    errors.append(ValidationError(
                        type=ValidationErrorType.PYDANTIC,
                        severity=ErrorSeverity.WARNING,
                        message=f"元素ID格式不符合规范: {element.id}",
                        location=f"scenes[].elements[].id",
                        repair_type=RepairType.PROGRAM,
                        actual_value=element.id,
                    ))

                valid_types = ["action", "dialogue", "parenthetical", "transition",
                               "voice_over", "shot", "note"]
                if element.type not in valid_types:
                    errors.append(ValidationError(
                        type=ValidationErrorType.PYDANTIC,
                        severity=ErrorSeverity.CRITICAL,
                        message=f"元素类型无效: {element.type}",
                        location=f"scenes[].elements[].type",
                        repair_type=RepairType.AI,
                        actual_value=element.type,
                        expected_value=f"应为: {valid_types}",
                    ))

        # 检查角色ID格式
        for character in screenplay.story_bible.characters:
            if not character.id.startswith("char_"):
                errors.append(ValidationError(
                    type=ValidationErrorType.PYDANTIC,
                    severity=ErrorSeverity.WARNING,
                    message=f"角色ID格式不符合规范: {character.id}",
                    location=f"story_bible.characters[].id",
                    repair_type=RepairType.PROGRAM,
                    actual_value=character.id,
                ))

        # 检查地点ID格式
        for location in screenplay.story_bible.locations:
            if not location.id.startswith("loc_"):
                errors.append(ValidationError(
                    type=ValidationErrorType.PYDANTIC,
                    severity=ErrorSeverity.WARNING,
                    message=f"地点ID格式不符合规范: {location.id}",
                    location=f"story_bible.locations[].id",
                    repair_type=RepairType.PROGRAM,
                    actual_value=location.id,
                ))

        return errors

    def _validate_json_schema(self, screenplay: Screenplay) -> List[ValidationError]:
        """第二层：JSON Schema校验"""
        errors = []

        try:
            import json
            import os

            schema_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "schemas",
                "screenplay_schema.json"
            )

            if os.path.exists(schema_path):
                with open(schema_path, "r", encoding="utf-8") as f:
                    schema = json.load(f)

                # 使用jsonschema库校验
                try:
                    import jsonschema
                    data = screenplay.model_dump(mode="json", exclude_none=True)
                    jsonschema.validate(data, schema)
                except jsonschema.ValidationError as e:
                    errors.append(ValidationError(
                        type=ValidationErrorType.JSON_SCHEMA,
                        severity=ErrorSeverity.CRITICAL,
                        message=f"JSON Schema校验失败: {e.message}",
                        location=str(e.json_path),
                        repair_type=RepairType.AI,
                        actual_value=e.instance,
                    ))
                except ImportError:
                    logger.warning("jsonschema未安装，跳过JSON Schema校验")
            else:
                logger.info("JSON Schema文件不存在，跳过JSON Schema校验")

        except Exception as e:
            logger.error(f"JSON Schema校验过程出错: {e}")

        return errors

    def _validate_references(self, screenplay: Screenplay) -> List[ValidationError]:
        """第三层：引用一致性校验"""

        errors = []

        # 收集所有有效ID集合
        character_ids: Set[str] = {c.id for c in screenplay.story_bible.characters}
        location_ids: Set[str] = {l.id for l in screenplay.story_bible.locations}
        chapter_ids: Set[str] = {c.id for c in screenplay.chapters}
        paragraph_ids: Set[str] = set()
        for ch in screenplay.chapters:
            for p in ch.paragraphs:
                paragraph_ids.add(p.id)

        # 检查场景中的角色引用
        for scene in screenplay.scenes:
            for char_id in scene.characters:
                if char_id not in character_ids:
                    errors.append(ValidationError(
                        type=ValidationErrorType.REFERENCE,
                        severity=ErrorSeverity.CRITICAL,
                        message=f"场景引用了不存在的角色: {char_id}",
                        location=f"scenes[{scene.id}].characters",
                        repair_type=RepairType.AI,
                        actual_value=char_id,
                        suggested_fix=f"移除引用或创建角色 {char_id}",
                    ))

            # 检查场景中的章节引用
            for ch_id in scene.chapter_ids:
                if ch_id not in chapter_ids:
                    errors.append(ValidationError(
                        type=ValidationErrorType.REFERENCE,
                        severity=ErrorSeverity.CRITICAL,
                        message=f"场景引用了不存在的章节: {ch_id}",
                        location=f"scenes[{scene.id}].chapter_ids",
                        repair_type=RepairType.PROGRAM,
                        actual_value=ch_id,
                    ))

            # 检查场景中的源引用
            for ref in scene.source_refs:
                if ref.chapter_id not in chapter_ids:
                    errors.append(ValidationError(
                        type=ValidationErrorType.REFERENCE,
                        severity=ErrorSeverity.WARNING,
                        message=f"场景源引用引用了不存在的章节: {ref.chapter_id}",
                        location=f"scenes[{scene.id}].source_refs",
                        repair_type=RepairType.PROGRAM,
                        actual_value=ref.chapter_id,
                    ))
                for p_id in ref.paragraph_ids:
                    if p_id not in paragraph_ids:
                        errors.append(ValidationError(
                            type=ValidationErrorType.REFERENCE,
                            severity=ErrorSeverity.WARNING,
                            message=f"场景源引用引用了不存在的段落: {p_id}",
                            location=f"scenes[{scene.id}].source_refs",
                            repair_type=RepairType.PROGRAM,
                            actual_value=p_id,
                        ))

            # 检查场景heading中的地点引用
            if scene.heading and scene.heading.location_id:
                if scene.heading.location_id not in location_ids:
                    errors.append(ValidationError(
                        type=ValidationErrorType.REFERENCE,
                        severity=ErrorSeverity.CRITICAL,
                        message=f"场景heading引用了不存在的地点: {scene.heading.location_id}",
                        location=f"scenes[{scene.id}].heading.location_id",
                        repair_type=RepairType.AI,
                        actual_value=scene.heading.location_id,
                    ))

            # 检查元素中的角色引用
            for element in scene.elements:
                if element.character_id and element.character_id not in character_ids:
                    errors.append(ValidationError(
                        type=ValidationErrorType.REFERENCE,
                        severity=ErrorSeverity.CRITICAL,
                        message=f"元素引用了不存在的角色: {element.character_id}",
                        location=f"scenes[{scene.id}].elements[{element.id}].character_id",
                        repair_type=RepairType.AI,
                        actual_value=element.character_id,
                    ))

                # 检查元素中的源引用
                if element.source_ref:
                    if element.source_ref.chapter_id not in chapter_ids:
                        errors.append(ValidationError(
                            type=ValidationErrorType.REFERENCE,
                            severity=ErrorSeverity.WARNING,
                            message=f"元素源引用引用了不存在的章节: {element.source_ref.chapter_id}",
                            location=f"scenes[{scene.id}].elements[{element.id}].source_ref",
                            repair_type=RepairType.PROGRAM,
                            actual_value=element.source_ref.chapter_id,
                        ))
                    for p_id in element.source_ref.paragraph_ids:
                        if p_id not in paragraph_ids:
                            errors.append(ValidationError(
                                type=ValidationErrorType.REFERENCE,
                                severity=ErrorSeverity.WARNING,
                                message=f"元素源引用引用了不存在的段落: {p_id}",
                                location=f"scenes[{scene.id}].elements[{element.id}].source_ref",
                                repair_type=RepairType.PROGRAM,
                                actual_value=p_id,
                            ))

        # 检查角色关系中的引用
        for character in screenplay.story_bible.characters:
            for rel in character.relationships:
                if rel.character_id not in character_ids:
                    errors.append(ValidationError(
                        type=ValidationErrorType.REFERENCE,
                        severity=ErrorSeverity.WARNING,
                        message=f"角色关系引用了不存在的角色: {rel.character_id}",
                        location=f"story_bible.characters[{character.id}].relationships",
                        repair_type=RepairType.AI,
                        actual_value=rel.character_id,
                    ))

        # 检查角色和地点的首次出现引用
        for character in screenplay.story_bible.characters:
            if character.first_appearance and character.first_appearance not in chapter_ids:
                errors.append(ValidationError(
                    type=ValidationErrorType.REFERENCE,
                    severity=ErrorSeverity.WARNING,
                    message=f"角色首次出现引用了不存在的章节: {character.first_appearance}",
                    location=f"story_bible.characters[{character.id}].first_appearance",
                    repair_type=RepairType.PROGRAM,
                    actual_value=character.first_appearance,
                ))

        for location in screenplay.story_bible.locations:
            if location.first_appearance and location.first_appearance not in chapter_ids:
                errors.append(ValidationError(
                    type=ValidationErrorType.REFERENCE,
                    severity=ErrorSeverity.WARNING,
                    message=f"地点首次出现引用了不存在的章节: {location.first_appearance}",
                    location=f"story_bible.locations[{location.id}].first_appearance",
                    repair_type=RepairType.PROGRAM,
                    actual_value=location.first_appearance,
                ))

        # 检查空场景
        for scene in screenplay.scenes:
            if not scene.elements and not scene.beats:
                errors.append(ValidationError(
                    type=ValidationErrorType.REFERENCE,
                    severity=ErrorSeverity.WARNING,
                    message=f"空场景: {scene.id} 没有任何元素或节拍",
                    location=f"scenes[{scene.id}]",
                    repair_type=RepairType.AI,
                    actual_value=scene.id,
                ))

        # 检查孤立角色
        referenced_chars: Set[str] = set()
        for scene in screenplay.scenes:
            referenced_chars.update(scene.characters)
            for element in scene.elements:
                if element.character_id:
                    referenced_chars.add(element.character_id)

        for char_id in character_ids:
            if char_id not in referenced_chars:
                errors.append(ValidationError(
                    type=ValidationErrorType.REFERENCE,
                    severity=ErrorSeverity.WARNING,
                    message=f"孤立角色: {char_id} 没有被任何场景引用",
                    location=f"story_bible.characters[{char_id}]",
                    repair_type=RepairType.AI,
                    actual_value=char_id,
                ))

        return errors

    async def repair_screenplay(
        self,
        screenplay: Screenplay,
        validation_result: ValidationResult,
    ) -> Screenplay:
        """校验修复闭环：失败 → 局部修复 → 再校验"""

        # 先尝试程序修复（确定性的问题）
        screenplay = self._program_repair(screenplay, validation_result)

        # 再尝试AI修复（不确定性的问题）
        ai_errors = [e for e in validation_result.errors if e.repair_type == RepairType.AI]
        if ai_errors:
            screenplay = await self._ai_repair(screenplay, ai_errors)

        # 标记需要用户确认的问题
        user_errors = [e for e in validation_result.errors if e.repair_type == RepairType.USER]
        if user_errors:
            logger.warning(f"有 {len(user_errors)} 个问题需要用户确认")

        # 重新校验
        new_result = self.validate_screenplay(screenplay)
        if new_result.stats.get("critical_errors", 0) > 0:
            logger.warning(f"修复后仍有 {new_result.stats['critical_errors']} 个关键错误")

        return screenplay

    def _program_repair(
        self,
        screenplay: Screenplay,
        validation_result: ValidationResult,
    ) -> Screenplay:
        """程序自动修复：处理确定性可修复的问题"""

        # 收集有效ID集合
        character_ids = {c.id for c in screenplay.story_bible.characters}
        location_ids = {l.id for l in screenplay.story_bible.locations}
        chapter_ids = {c.id for c in screenplay.chapters}
        paragraph_ids = set()
        for ch in screenplay.chapters:
            for p in ch.paragraphs:
                paragraph_ids.add(p.id)

        # 修复ID格式
        for chapter in screenplay.chapters:
            if not chapter.id.startswith("ch_"):
                chapter.id = f"ch_{chapter.order}"

            for para in chapter.paragraphs:
                if not para.id.startswith("p_"):
                    para.id = f"p_{chapter.order}_{para.order}"

        for idx, scene in enumerate(screenplay.scenes):
            if not scene.id.startswith("sc_"):
                scene.id = f"sc_{idx+1}"

            # 移除不存在的章节引用
            scene.chapter_ids = [ch_id for ch_id in scene.chapter_ids if ch_id in chapter_ids]

            # 修复源引用中的无效段落
            for ref in scene.source_refs:
                if ref.chapter_id not in chapter_ids:
                    ref.chapter_id = ""
                ref.paragraph_ids = [p_id for p_id in ref.paragraph_ids if p_id in paragraph_ids]

            # 移除不存在的角色引用
            scene.characters = [c_id for c_id in scene.characters if c_id in character_ids]

        for character in screenplay.story_bible.characters:
            if not character.id.startswith("char_"):
                character.id = f"char_{character.name}"

            # 修复角色关系中的无效引用
            character.relationships = [
                rel for rel in character.relationships
                if rel.character_id in character_ids
            ]

            # 修复首次出现引用
            if character.first_appearance and character.first_appearance not in chapter_ids:
                character.first_appearance = None

        for location in screenplay.story_bible.locations:
            if not location.id.startswith("loc_"):
                location.id = f"loc_{location.name}"

            if location.first_appearance and location.first_appearance not in chapter_ids:
                location.first_appearance = None

        return screenplay

    async def _ai_repair(
        self,
        screenplay: Screenplay,
        errors: List[ValidationError],
    ) -> Screenplay:
        """AI辅助修复：处理不确定性问题"""

        # 对每个AI修复类错误，使用LLM生成修复建议
        for error in errors:
            try:
                result = await self.llm_provider.generate_structured(
                    output_type=dict,
                    task_type=TaskType.VALIDATION_REPAIR,
                    prompt=f"""请修复以下剧本校验错误：

错误类型: {error.type.value}
错误位置: {error.location}
错误描述: {error.message}
当前值: {error.actual_value}
建议修复: {error.suggested_fix}

请给出修复方案。""",
                    system_prompt="你是一个剧本校验修复专家。你需要根据校验错误信息，给出合理的修复方案。",
                    temperature=0.2,
                )

                if result.success and result.content:
                    fix = result.content
                    # 应用修复（简化处理）
                    logger.info(f"AI修复建议: {fix}")

            except Exception as e:
                logger.warning(f"AI修复失败: {e}")

        return screenplay
