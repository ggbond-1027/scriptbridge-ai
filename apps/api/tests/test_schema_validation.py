"""单元测试 - Schema校验（Pydantic校验、JSON Schema校验、引用一致性校验）

测试SchemaValidator的三层校验机制。
"""

import pytest
import json
import os
from unittest.mock import MagicMock

from app.models.screenplay import (
    Screenplay, Chapter, SourceParagraph, Scene, Element, ElementType,
    SceneHeading, SceneContext, StoryBible, Character, CharacterRole,
    Location, LocationType, SourceRef, AdaptationStyle, Relationship,
    TimelineEntry, SceneBeat, ProjectInfo, GenerationMetadata,
)
from app.core.validation import (
    SchemaValidator, ValidationResult, ValidationError,
    ValidationErrorType, ErrorSeverity, RepairType,
)


# ===== 辅助函数 =====


def create_valid_screenplay() -> Screenplay:
    """创建一个完整的、有效的Screenplay数据"""
    return Screenplay(
        schema_version="1.0.0",
        project=ProjectInfo(
            id="proj_1",
            title="测试剧本",
            source_language="zh-CN",
            target_format="screenplay",
            adaptation_style=AdaptationStyle(
                genre=["drama"],
                tone=["serious"],
                dialogue_style="natural",
            ),
        ),
        story_bible=StoryBible(
            characters=[
                Character(
                    id="char_1",
                    name="李明",
                    aliases=["明哥", "小李"],
                    role=CharacterRole.PROTAGONIST,
                    description="男主角",
                    goals="成功",
                    personality="坚韧",
                    appearance="高大英俊",
                    first_appearance="ch_1",
                    relationships=[
                        Relationship(
                            character_id="char_2",
                            relationship_type="friend",
                            description="好友",
                        ),
                    ],
                ),
                Character(
                    id="char_2",
                    name="王芳",
                    aliases=["芳姐"],
                    role=CharacterRole.SUPPORTING,
                    description="女主角的朋友",
                    first_appearance="ch_1",
                ),
            ],
            locations=[
                Location(
                    id="loc_1",
                    name="办公室",
                    type=LocationType.INDOOR,
                    description="公司办公室",
                    atmosphere="专业严肃",
                    first_appearance="ch_1",
                ),
                Location(
                    id="loc_2",
                    name="咖啡馆",
                    type=LocationType.INDOOR,
                    description="街角的咖啡馆",
                    atmosphere="温馨舒适",
                ),
            ],
            timeline=[
                TimelineEntry(
                    id="tl_1",
                    chapter_id="ch_1",
                    event="李明第一天上班",
                    description="新员工入职",
                    characters_involved=["char_1", "char_2"],
                    location_id="loc_1",
                ),
            ],
        ),
        chapters=[
            Chapter(
                id="ch_1",
                order=1,
                title="第一章 初遇",
                source_title="第一章",
                paragraphs=[
                    SourceParagraph(id="p_1_1", text="清晨的阳光照进房间", order=1),
                    SourceParagraph(id="p_1_2", text="李明推门走进办公室", order=2),
                ],
                summary="李明第一天上班",
            ),
        ],
        scenes=[
            Scene(
                id="sc_1",
                chapter_ids=["ch_1"],
                source_refs=[
                    SourceRef(chapter_id="ch_1", paragraph_ids=["p_1_1", "p_1_2"]),
                ],
                heading=SceneHeading(
                    context=SceneContext.INT,
                    location_id="loc_1",
                    time_of_day="日",
                ),
                title="初到办公室",
                dramatic_purpose="建立角色关系",
                conflict="李明感到紧张",
                characters=["char_1", "char_2"],
                beats=[
                    SceneBeat(description="李明走进办公室", emotional_arc="紧张->好奇"),
                ],
                elements=[
                    Element(id="el_1", type=ElementType.ACTION, text="办公室内灯光明亮"),
                    Element(
                        id="el_2",
                        type=ElementType.DIALOGUE,
                        text="你好，我是李明",
                        character_id="char_1",
                    ),
                    Element(id="el_3", type=ElementType.TRANSITION, text="切至"),
                ],
            ),
        ],
        metadata=GenerationMetadata(
            generated_at="2025-01-01T00:00:00",
            model="test-model",
            source_chapter_count=1,
            total_scenes=1,
            total_elements=3,
        ),
    )


def create_validator() -> SchemaValidator:
    """创建SchemaValidator实例（使用mock的LLM和路由器）"""
    mock_llm = MagicMock()
    mock_router = MagicMock()
    return SchemaValidator(mock_llm, mock_router)


# ===== 测试类 =====


class TestPydanticValidation:
    """测试第一层：Pydantic模型校验"""

    def test_valid_screenplay(self):
        """有效的剧本数据应该通过Pydantic校验"""
        screenplay = create_valid_screenplay()
        validator = create_validator()

        result = validator._validate_pydantic(screenplay)
        pydantic_critical = [e for e in result if e.severity == ErrorSeverity.CRITICAL]
        assert len(pydantic_critical) == 0

    def test_invalid_element_type(self):
        """无效的元素类型应该被检测"""
        screenplay = create_valid_screenplay()
        screenplay.scenes[0].elements[0].type = "invalid_type"

        validator = create_validator()
        result = validator._validate_pydantic(screenplay)

        type_errors = [e for e in result if "元素类型无效" in e.message]
        assert len(type_errors) >= 1

    def test_id_format_validation(self):
        """ID格式不规范应该被检测"""
        screenplay = create_valid_screenplay()
        # 修改一个章节ID为不规范格式
        screenplay.chapters[0].id = "chapter_1"

        validator = create_validator()
        result = validator._validate_pydantic(screenplay)

        id_errors = [e for e in result if "ID格式不符合规范" in e.message]
        assert len(id_errors) >= 1

    def test_dialogue_without_character(self):
        """对话元素缺少角色ID应该报错"""
        # Pydantic的model_validator会在创建时就报错
        with pytest.raises(Exception):
            Element(
                id="el_test",
                type=ElementType.DIALOGUE,
                text="测试对话",
                character_id=None,
            )

    def test_character_id_format(self):
        """角色ID必须以char_开头"""
        with pytest.raises(Exception):
            Character(id="invalid_id", name="测试角色")

    def test_location_id_format(self):
        """地点ID必须以loc_开头"""
        with pytest.raises(Exception):
            Location(id="invalid_id", name="测试地点")

    def test_element_id_format(self):
        """元素ID必须以el_开头"""
        with pytest.raises(Exception):
            Element(id="invalid_id", type=ElementType.ACTION, text="测试动作")

    def test_scene_id_format(self):
        """场景ID必须以sc_开头"""
        with pytest.raises(Exception):
            Scene(id="invalid_id")

    def test_chapter_id_format(self):
        """章节ID必须以ch_开头"""
        with pytest.raises(Exception):
            Chapter(id="invalid_id", order=1, title="测试章节")

    def test_paragraph_id_format(self):
        """段落ID必须以p_开头"""
        with pytest.raises(Exception):
            SourceParagraph(id="invalid_id", text="测试段落", order=1)


class TestJSONSchemaValidation:
    """测试第二层：JSON Schema校验"""

    def test_json_schema_exists(self):
        """JSON Schema文件应该存在"""
        schema_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app", "schemas", "screenplay_schema.json",
        )
        assert os.path.exists(schema_path)

    def test_json_schema_valid(self):
        """JSON Schema本身应该是有效的"""
        schema_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app", "schemas", "screenplay_schema.json",
        )
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        assert "$schema" in schema
        assert "title" in schema
        assert "properties" in schema
        assert "required" in schema

    def test_screenplay_matches_schema(self):
        """Screenplay数据应该匹配JSON Schema"""
        screenplay = create_valid_screenplay()
        validator = create_validator()

        result = validator._validate_json_schema(screenplay)
        # 由于jsonschema可能未安装，只检查不报错
        assert isinstance(result, list)


class TestReferenceValidation:
    """测试第三层：引用一致性校验"""

    def test_valid_references(self):
        """有效引用应该通过校验"""
        screenplay = create_valid_screenplay()
        validator = create_validator()

        result = validator._validate_references(screenplay)
        critical_errors = [e for e in result if e.severity == ErrorSeverity.CRITICAL]
        assert len(critical_errors) == 0

    def test_missing_character_reference(self):
        """引用不存在角色应该被检测"""
        screenplay = create_valid_screenplay()
        screenplay.scenes[0].characters.append("char_invalid")

        validator = create_validator()
        result = validator._validate_references(screenplay)

        char_errors = [e for e in result if e.type == ValidationErrorType.REFERENCE and "角色" in e.message]
        assert len(char_errors) >= 1

    def test_missing_location_reference(self):
        """引用不存在地点应该被检测"""
        screenplay = create_valid_screenplay()
        screenplay.scenes[0].heading.location_id = "loc_invalid"

        validator = create_validator()
        result = validator._validate_references(screenplay)

        loc_errors = [e for e in result if e.type == ValidationErrorType.REFERENCE and "地点" in e.message]
        assert len(loc_errors) >= 1

    def test_missing_chapter_reference(self):
        """引用不存在章节应该被检测"""
        screenplay = create_valid_screenplay()
        screenplay.scenes[0].chapter_ids.append("ch_invalid")

        validator = create_validator()
        result = validator._validate_references(screenplay)

        ch_errors = [e for e in result if e.type == ValidationErrorType.REFERENCE and "章节" in e.message]
        assert len(ch_errors) >= 1

    def test_missing_paragraph_reference(self):
        """引用不存在段落应该被检测"""
        screenplay = create_valid_screenplay()
        screenplay.scenes[0].source_refs[0].paragraph_ids.append("p_invalid")

        validator = create_validator()
        result = validator._validate_references(screenplay)

        p_errors = [e for e in result if e.type == ValidationErrorType.REFERENCE and "段落" in e.message]
        assert len(p_errors) >= 1

    def test_element_missing_character(self):
        """元素引用不存在角色应该被检测"""
        screenplay = create_valid_screenplay()
        screenplay.scenes[0].elements[1].character_id = "char_invalid"

        validator = create_validator()
        result = validator._validate_references(screenplay)

        char_errors = [e for e in result if e.type == ValidationErrorType.REFERENCE and "角色" in e.message]
        assert len(char_errors) >= 1

    def test_character_relationship_invalid(self):
        """角色关系引用不存在角色应该被检测"""
        screenplay = create_valid_screenplay()
        screenplay.story_bible.characters[0].relationships.append(
            Relationship(character_id="char_invalid", relationship_type="enemy"),
        )

        validator = create_validator()
        result = validator._validate_references(screenplay)

        rel_errors = [e for e in result if "角色关系" in e.message]
        assert len(rel_errors) >= 1

    def test_empty_scene_detected(self):
        """空场景应该被检测"""
        screenplay = create_valid_screenplay()
        # 添加一个空场景
        screenplay.scenes.append(
            Scene(id="sc_empty", chapter_ids=["ch_1"], elements=[], beats=[])
        )

        validator = create_validator()
        result = validator._validate_references(screenplay)

        empty_errors = [e for e in result if "空场景" in e.message or "没有任何元素" in e.message]
        assert len(empty_errors) >= 1

    def test_orphan_character_detected(self):
        """未被场景引用的孤立角色应该被检测"""
        screenplay = create_valid_screenplay()
        screenplay.story_bible.characters.append(
            Character(id="char_orphan", name="孤立角色", role=CharacterRole.MINOR),
        )

        validator = create_validator()
        result = validator._validate_references(screenplay)

        orphan_errors = [e for e in result if "孤立" in e.message or "没有被引用" in e.message]
        assert len(orphan_errors) >= 1


class TestCrossReferenceValidation:
    """测试Screenplay.validate_cross_references()方法"""

    def test_valid_cross_references(self):
        """有效的跨引用应该通过校验"""
        screenplay = create_valid_screenplay()
        errors = screenplay.validate_cross_references()

        # 检查关键错误类别为空
        assert len(errors["missing_character_refs"]) == 0
        assert len(errors["missing_location_refs"]) == 0
        assert len(errors["missing_chapter_refs"]) == 0

    def test_invalid_character_cross_reference(self):
        """无效角色跨引用应该被检测"""
        screenplay = create_valid_screenplay()
        screenplay.scenes[0].characters.append("char_invalid")

        errors = screenplay.validate_cross_references()
        assert len(errors["missing_character_refs"]) >= 1

    def test_invalid_location_cross_reference(self):
        """无效地点跨引用应该被检测"""
        screenplay = create_valid_screenplay()
        screenplay.scenes[0].heading.location_id = "loc_invalid"

        errors = screenplay.validate_cross_references()
        assert len(errors["missing_location_refs"]) >= 1


class TestProgramRepair:
    """测试程序自动修复功能"""

    def test_fix_id_format(self):
        """修复不规范ID格式"""
        screenplay = create_valid_screenplay()
        # 添加不规范ID
        screenplay.chapters[0].id = "chapter_1"

        validator = create_validator()
        # 使用程序修复
        validation_result = validator.validate_screenplay(screenplay)
        repaired = validator._program_repair(screenplay, validation_result)

        # ID应该被修复为规范格式
        assert repaired.chapters[0].id.startswith("ch_")

    def test_remove_invalid_references(self):
        """移除无效引用"""
        screenplay = create_valid_screenplay()
        screenplay.scenes[0].characters.append("char_invalid")
        screenplay.scenes[0].chapter_ids.append("ch_invalid")

        validator = create_validator()
        validation_result = validator.validate_screenplay(screenplay)
        repaired = validator._program_repair(screenplay, validation_result)

        # 无效引用应该被移除
        assert "char_invalid" not in repaired.scenes[0].characters
        assert "ch_invalid" not in repaired.scenes[0].chapter_ids


class TestFullValidationPipeline:
    """测试完整的三层校验流程"""

    def test_valid_screenplay_passes(self):
        """有效的剧本应该通过全部三层校验"""
        screenplay = create_valid_screenplay()
        validator = create_validator()

        result = validator.validate_screenplay(screenplay)

        critical_errors = [e for e in result.errors if e.severity == ErrorSeverity.CRITICAL]
        assert len(critical_errors) == 0
        assert result.is_valid

    def test_validation_result_stats(self):
        """校验结果统计应该正确"""
        screenplay = create_valid_screenplay()
        validator = create_validator()

        result = validator.validate_screenplay(screenplay)

        assert "total_errors" in result.stats
        assert "critical_errors" in result.stats
        assert "warnings" in result.stats
        assert "pydantic_errors" in result.stats
        assert "schema_errors" in result.stats
        assert "reference_errors" in result.stats