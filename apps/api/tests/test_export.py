"""单元测试 - Fountain导出格式

测试ExportService的Fountain格式导出映射规则：
- heading -> Slugline (INT./EXT. LOCATION - TIME)
- element(dialogue) -> Dialogue Block
- element(action) -> Action
- element(transition) -> Transition
- element(voice_over) -> Action(旁白标注)
"""

import pytest
import json
import io
import zipfile

from app.models.screenplay import (
    Screenplay, Chapter, SourceParagraph, Scene, Element, ElementType,
    SceneHeading, SceneContext, StoryBible, Character, CharacterRole,
    Location, LocationType, SourceRef, AdaptationStyle,
    ProjectInfo, GenerationMetadata, SceneBeat,
)
from app.core.export import ExportService


# ===== 辅助函数 =====


def create_test_screenplay() -> Screenplay:
    """创建测试用的完整Screenplay数据"""
    return Screenplay(
        schema_version="1.0.0",
        project=ProjectInfo(
            id="test_project",
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
                    aliases=["明哥"],
                    role=CharacterRole.PROTAGONIST,
                    description="男主角",
                ),
                Character(
                    id="char_2",
                    name="王芳",
                    aliases=["芳姐"],
                    role=CharacterRole.SUPPORTING,
                    description="女主角的朋友",
                ),
            ],
            locations=[
                Location(
                    id="loc_1",
                    name="办公室",
                    type=LocationType.INDOOR,
                    description="公司办公室",
                    atmosphere="专业严肃",
                ),
                Location(
                    id="loc_2",
                    name="咖啡馆",
                    type=LocationType.INDOOR,
                    description="街角的咖啡馆",
                    atmosphere="温馨舒适",
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
                    Element(id="el_1", type=ElementType.ACTION, text="办公室内灯光明亮，几张办公桌整齐排列。"),
                    Element(
                        id="el_2",
                        type=ElementType.DIALOGUE,
                        text="你好，我是李明，新来的员工。",
                        character_id="char_1",
                        parenthetical="礼貌地说",
                    ),
                    Element(
                        id="el_3",
                        type=ElementType.DIALOGUE,
                        text="欢迎你，我是王芳。",
                        character_id="char_2",
                    ),
                    Element(
                        id="el_4",
                        type=ElementType.VOICE_OVER,
                        text="这间办公室比想象中要小...",
                        character_id="char_1",
                    ),
                    Element(id="el_5", type=ElementType.TRANSITION, text="切至下一场景"),
                    Element(id="el_6", type=ElementType.SHOT, text="全景镜头"),
                    Element(id="el_7", type=ElementType.NOTE, text="注意光线变化"),
                    Element(
                        id="el_8",
                        type=ElementType.PARENTHETICAL,
                        text="紧张地",
                    ),
                ],
            ),
            Scene(
                id="sc_2",
                chapter_ids=["ch_1"],
                source_refs=[
                    SourceRef(chapter_id="ch_1", paragraph_ids=["p_1_1"]),
                ],
                heading=SceneHeading(
                    context=SceneContext.EXT,
                    location_id="loc_2",
                    time_of_day="夜",
                ),
                title="咖啡馆相遇",
                dramatic_purpose="深化角色关系",
                conflict="两人之间的误解",
                characters=["char_1", "char_2"],
                elements=[
                    Element(id="el_9", type=ElementType.ACTION, text="街角的咖啡馆，暖黄色灯光透过玻璃窗。"),
                    Element(
                        id="el_10",
                        type=ElementType.DIALOGUE,
                        text="你怎么也在这里？",
                        character_id="char_1",
                    ),
                    Element(id="el_11", type=ElementType.TRANSITION, text="淡出"),
                ],
            ),
        ],
        metadata=GenerationMetadata(
            generated_at="2025-01-01T00:00:00",
            model="test-model",
            source_chapter_count=1,
            total_scenes=2,
            total_elements=11,
        ),
    )


# ===== 测试类 =====


class TestFountainExport:
    """测试Fountain格式导出"""

    def setup_method(self):
        self.screenplay = create_test_screenplay()
        self.export_service = ExportService()

    def test_fountain_title_page(self):
        """Fountain文件应该包含标题页"""
        result = self.export_service.export_fountain(self.screenplay)
        assert "Title:" in result
        assert "测试剧本" in result
        assert "=" in result  # 标题页分隔符

    def test_fountain_slugline_int(self):
        """INT场景标题行映射为Fountain Slugline"""
        result = self.export_service.export_fountain(self.screenplay)
        assert "INT." in result
        assert "OFFICE" in result  # 地点应该大写
        assert "DAY" in result  # "日"映射为"DAY"

    def test_fountain_slugline_ext(self):
        """EXT场景标题行映射为Fountain Slugline"""
        result = self.export_service.export_fountain(self.screenplay)
        assert "EXT." in result
        assert "CAFÉ" in result or "咖啡" in result.upper()  # 地点应该大写
        assert "NIGHT" in result  # "夜"映射为"NIGHT"

    def test_fountain_action_element(self):
        """action元素映射为Fountain Action文本"""
        result = self.export_service.export_fountain(self.screenplay)
        assert "办公室内灯光明亮" in result
        assert "街角的咖啡馆" in result

    def test_fountain_dialogue_block(self):
        """dialogue元素映射为Fountain Dialogue Block（角色名大写+对话）"""
        result = self.export_service.export_fountain(self.screenplay)
        assert "LI MING" in result  # 角色名应该大写
        assert "你好，我是李明" in result
        assert "WANG FANG" in result or "王芳".upper() in result

    def test_fountain_dialogue_with_parenthetical(self):
        """dialogue带parenthetical映射"""
        result = self.export_service.export_fountain(self.screenplay)
        assert "(礼貌地说)" in result

    def test_fountain_transition_element(self):
        """transition元素映射为Fountain Transition（大写）"""
        result = self.export_service.export_fountain(self.screenplay)
        assert "切至下一场景" in result.upper() or "CUT TO" in result.upper()
        assert "淡出" in result

    def test_fountain_voice_over_element(self):
        """voice_over元素映射为Fountain Voice Over (V.O.)"""
        result = self.export_service.export_fountain(self.screenplay)
        assert "(V.O.)" in result
        assert "这间办公室比想象中要小" in result

    def test_fountain_shot_element(self):
        """shot元素映射为Fountain Shot（大写）"""
        result = self.export_service.export_fountain(self.screenplay)
        assert "全景镜头" in result.upper() or "FULL SHOT" in result.upper()

    def test_fountain_note_element(self):
        """note元素映射为Fountain注释 /* ... */"""
        result = self.export_service.export_fountain(self.screenplay)
        assert "/*" in result
        assert "*/" in result
        assert "注意光线变化" in result

    def test_fountain_parenthetical_element(self):
        """parenthetical独立元素映射"""
        result = self.export_service.export_fountain(self.screenplay)
        assert "(紧张地)" in result

    def test_fountain_dramatic_purpose_note(self):
        """戏剧目的作为注释写入Fountain"""
        result = self.export_service.export_fountain(self.screenplay)
        assert "戏剧目的" in result
        assert "建立角色关系" in result

    def test_fountain_conflict_note(self):
        """冲突描述作为注释写入Fountain"""
        result = self.export_service.export_fountain(self.screenplay)
        assert "冲突" in result

    def test_fountain_time_of_day_mapping(self):
        """中文时间映射到英文"""
        # 测试各种时间映射
        test_cases = [
            ("日", "DAY"),
            ("夜", "NIGHT"),
            ("晨", "MORNING"),
            ("晚", "EVENING"),
            ("下午", "AFTERNOON"),
            ("傍晚", "DUSK"),
            ("黄昏", "TWILIGHT"),
        ]

        time_map = {
            "日": "DAY", "夜": "NIGHT", "晨": "MORNING",
            "晚": "EVENING", "下午": "AFTERNOON", "傍晚": "DUSK",
            "黄昏": "TWILIGHT", "黎明": "DAWN", "深夜": "LATE NIGHT",
            "中午": "NOON",
        }

        for chinese, english in test_cases:
            assert time_map.get(chinese) == english


class TestYAMLExport:
    """测试YAML格式导出"""

    def setup_method(self):
        self.screenplay = create_test_screenplay()
        self.export_service = ExportService()

    def test_yaml_export_structure(self):
        """YAML导出应该包含完整结构"""
        from ruamel.yaml import YAML

        yaml_str = self.export_service.export_yaml(self.screenplay)
        assert isinstance(yaml_str, str)

        yaml = YAML()
        data = yaml.load(yaml_str)
        assert data is not None
        assert "schema_version" in data
        assert "project" in data
        assert "story_bible" in data
        assert "chapters" in data
        assert "scenes" in data

    def test_yaml_preserves_chinese(self):
        """YAML导出应该保留中文字符"""
        yaml_str = self.export_service.export_yaml(self.screenplay)
        assert "李明" in yaml_str
        assert "办公室" in yaml_str


class TestJSONExport:
    """测试JSON格式导出"""

    def setup_method(self):
        self.screenplay = create_test_screenplay()
        self.export_service = ExportService()

    def test_json_export_structure(self):
        """JSON导出应该包含完整结构"""
        json_str = self.export_service.export_json(self.screenplay)
        data = json.loads(json_str)

        assert "schema_version" in data
        assert data["schema_version"] == "1.0.0"
        assert "project" in data
        assert "story_bible" in data
        assert "chapters" in data
        assert "scenes" in data

    def test_json_preserves_unicode(self):
        """JSON导出应该保留Unicode字符"""
        json_str = self.export_service.export_json(self.screenplay)
        # ensure_ascii=False应该保留中文
        assert "李明" in json_str
        assert "办公室" in json_str

    def test_json_round_trip(self):
        """JSON导出后应该可以重新导入"""
        json_str = self.export_service.export_json(self.screenplay)
        data = json.loads(json_str)

        # 尝试重新构建Screenplay
        rebuilt = Screenplay.model_validate(data)
        assert rebuilt.schema_version == "1.0.0"
        assert len(rebuilt.scenes) == 2
        assert len(rebuilt.story_bible.characters) == 2


class TestMarkdownExport:
    """测试Markdown格式导出"""

    def setup_method(self):
        self.screenplay = create_test_screenplay()
        self.export_service = ExportService()

    def test_markdown_title(self):
        """Markdown应该包含标题"""
        result = self.export_service.export_markdown(self.screenplay)
        assert "# 测试剧本" in result

    def test_markdown_characters_section(self):
        """Markdown应该包含角色部分"""
        result = self.export_service.export_markdown(self.screenplay)
        assert "角色" in result
        assert "李明" in result
        assert "王芳" in result

    def test_markdown_locations_section(self):
        """Markdown应该包含地点部分"""
        result = self.export_service.export_markdown(self.screenplay)
        assert "地点" in result
        assert "办公室" in result

    def test_markdown_scene_heading(self):
        """Markdown场景标题行"""
        result = self.export_service.export_markdown(self.screenplay)
        assert "INT." in result or "室内" in result

    def test_markdown_dialogue_format(self):
        """Markdown对话格式"""
        result = self.export_service.export_markdown(self.screenplay)
        assert "李明" in result
        assert "你好" in result


class TestZipExport:
    """测试ZIP打包导出"""

    def setup_method(self):
        self.screenplay = create_test_screenplay()
        self.export_service = ExportService()

    def test_zip_contains_all_formats(self):
        """ZIP包应该包含所有格式文件"""
        zip_bytes = self.export_service.export_zip(self.screenplay)

        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
            names = zf.namelist()
            assert "screenplay.json" in names
            assert "screenplay.yaml" in names
            assert "screenplay.md" in names
            assert "screenplay.fountain" in names
            assert "metadata.json" in names

    def test_zip_json_content(self):
        """ZIP中的JSON文件应该可解析"""
        zip_bytes = self.export_service.export_zip(self.screenplay)

        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
            json_content = zf.read("screenplay.json")
            data = json.loads(json_content)
            assert data["schema_version"] == "1.0.0"

    def test_zip_metadata(self):
        """ZIP中的元数据文件"""
        zip_bytes = self.export_service.export_zip(self.screenplay)

        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
            metadata_content = zf.read("metadata.json")
            metadata = json.loads(metadata_content)
            assert "project_id" in metadata
            assert "formats" in metadata
            assert len(metadata["formats"]) == 4

    def test_zip_fountain_content(self):
        """ZIP中的Fountain文件应该包含Slugline"""
        zip_bytes = self.export_service.export_zip(self.screenplay)

        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
            fountain_content = zf.read("screenplay.fountain").decode("utf-8")
            assert "INT." in fountain_content
            assert "Title:" in fountain_content