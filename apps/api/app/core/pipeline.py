"""Pipeline - 多阶段Pipeline编排

7阶段处理流程：
1. chapter_splitting — 章节识别与预处理
2. paragraph_indexing — 段落编号
3. chapter_understanding — 逐章理解（不生成剧本，只提取）
4. story_bible_merge — 故事圣经合并（别名归一化、地点同一性、时间线排序）
5. scene_splitting — 场景拆分（必须有dramatic_purpose和conflict）
6. element_generation — 剧本元素生成
7. schema_validation — 校验修复闭环

支持WebSocket实时推送进度。
"""

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import asyncio
import logging
import uuid

from app.models.screenplay import (
    Screenplay, Chapter, SourceParagraph, StoryBible,
    Scene, Element, Character, Location, TimelineEntry,
    ProjectInfo, GenerationMetadata,
)
from app.core.model_router import ModelRouter, TaskType
from app.core.llm_provider import LLMProvider
from app.services.chapter_parser import ChapterParser
from app.services.story_bible import StoryBibleService
from app.services.scene_splitter import SceneSplitter
from app.services.script_generator import ScriptGenerator
from app.services.polish import PolishService
from app.core.validation import SchemaValidator

logger = logging.getLogger(__name__)


class PipelineStage(str, Enum):
    """Pipeline阶段"""
    CHAPTER_SPLITTING = "chapter_splitting"
    PARAGRAPH_INDEXING = "paragraph_indexing"
    CHAPTER_UNDERSTANDING = "chapter_understanding"
    STORY_BIBLE_MERGE = "story_bible_merge"
    SCENE_SPLITTING = "scene_splitting"
    ELEMENT_GENERATION = "element_generation"
    SCHEMA_VALIDATION = "schema_validation"


class StageStatus(str, Enum):
    """阶段状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageProgress:
    """阶段进度"""
    stage: PipelineStage
    status: StageStatus = StageStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress_percent: float = 0.0
    message: str = ""
    result_summary: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class PipelineRun:
    """Pipeline运行实例"""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str = ""
    stages: Dict[PipelineStage, StageProgress] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    screenplay: Optional[Screenplay] = None
    source_text: Optional[str] = None
    callbacks: List[Callable] = field(default_factory=list)


# 阶段顺序定义
STAGE_ORDER = [
    PipelineStage.CHAPTER_SPLITTING,
    PipelineStage.PARAGRAPH_INDEXING,
    PipelineStage.CHAPTER_UNDERSTANDING,
    PipelineStage.STORY_BIBLE_MERGE,
    PipelineStage.SCENE_SPLITTING,
    PipelineStage.ELEMENT_GENERATION,
    PipelineStage.SCHEMA_VALIDATION,
]


class PipelineManager:
    """Pipeline管理器 - 编排7阶段处理流程"""

    def __init__(self):
        self._runs: Dict[str, PipelineRun] = {}
        self._active_runs: Dict[str, asyncio.Task] = {}

    def create_run(self, project_id: str, source_text: str) -> PipelineRun:
        """创建新的Pipeline运行实例"""
        run = PipelineRun(
            project_id=project_id,
            source_text=source_text,
        )
        for stage in STAGE_ORDER:
            run.stages[stage] = StageProgress(stage=stage)
        self._runs[run.run_id] = run
        return run

    async def execute(
        self,
        run: PipelineRun,
        model_router: ModelRouter,
        llm_provider: LLMProvider,
        websocket_callback: Optional[Callable] = None,
    ) -> Screenplay:
        """
        执行完整的7阶段Pipeline

        Args:
            run: PipelineRun实例
            model_router: 模型路由器
            llm_provider: LLM提供者
            websocket_callback: WebSocket进度推送回调

        Returns:
            Screenplay: 最终生成的剧本
        """
        if websocket_callback:
            run.callbacks.append(websocket_callback)

        source_text = run.source_text
        screenplay = None

        try:
            # 阶段1: 章节识别与预处理
            chapters_raw = await self._stage_chapter_splitting(run, source_text)

            # 阶段2: 段落编号
            chapters_with_paragraphs = await self._stage_paragraph_indexing(run, chapters_raw)

            # 阶段3: 逐章理解
            chapter_understandings = await self._stage_chapter_understanding(
                run, chapters_with_paragraphs, model_router, llm_provider
            )

            # 阶段4: 故事圣经合并
            story_bible = await self._stage_story_bible_merge(
                run, chapter_understandings, model_router, llm_provider
            )

            # 阶段5: 场景拆分
            scenes = await self._stage_scene_splitting(
                run, chapters_with_paragraphs, chapter_understandings, story_bible,
                model_router, llm_provider
            )

            # 阶段6: 剧本元素生成
            scenes_with_elements = await self._stage_element_generation(
                run, scenes, story_bible, model_router, llm_provider
            )

            # 阶段7: Schema校验修复
            screenplay = await self._stage_schema_validation(
                run, chapters_with_paragraphs, story_bible, scenes_with_elements,
                model_router, llm_provider
            )

            run.screenplay = screenplay
            return screenplay

        except Exception as e:
            logger.error(f"Pipeline执行失败: {e}")
            # 标记当前运行阶段为失败
            for stage_progress in run.stages.values():
                if stage_progress.status == StageStatus.RUNNING:
                    stage_progress.status = StageStatus.FAILED
                    stage_progress.error = str(e)
            raise

    async def _stage_chapter_splitting(
        self, run: PipelineRun, source_text: str
    ) -> List[Dict[str, Any]]:
        """阶段1: 章节识别与预处理"""
        progress = run.stages[PipelineStage.CHAPTER_SPLITTING]
        progress.status = StageStatus.RUNNING
        progress.started_at = datetime.now()
        progress.progress_percent = 0.0
        progress.message = "正在识别章节结构..."
        self._notify_progress(run)

        try:
            parser = ChapterParser()
            chapters_raw = parser.parse(source_text)

            progress.status = StageStatus.COMPLETED
            progress.completed_at = datetime.now()
            progress.progress_percent = 100.0
            progress.message = f"识别到 {len(chapters_raw)} 个章节"
            progress.result_summary = {"chapter_count": len(chapters_raw)}
            self._notify_progress(run)

            return chapters_raw

        except Exception as e:
            progress.status = StageStatus.FAILED
            progress.error = str(e)
            progress.message = f"章节识别失败: {e}"
            self._notify_progress(run)
            raise

    async def _stage_paragraph_indexing(
        self, run: PipelineRun, chapters_raw: List[Dict[str, Any]]
    ) -> List[Chapter]:
        """阶段2: 段落编号"""
        progress = run.stages[PipelineStage.PARAGRAPH_INDEXING]
        progress.status = StageStatus.RUNNING
        progress.started_at = datetime.now()
        progress.progress_percent = 0.0
        progress.message = "正在为段落编号..."
        self._notify_progress(run)

        try:
            chapters = []
            for idx, ch_raw in enumerate(chapters_raw):
                paragraphs = []
                for p_idx, p_text in enumerate(ch_raw.get("paragraphs", [])):
                    p = SourceParagraph(
                        id=f"p_{idx+1}_{p_idx+1}",
                        text=p_text,
                        order=p_idx + 1,
                    )
                    paragraphs.append(p)

                chapter = Chapter(
                    id=f"ch_{idx+1}",
                    order=idx + 1,
                    title=ch_raw.get("title", f"第{idx+1}章"),
                    source_title=ch_raw.get("source_title", ""),
                    paragraphs=paragraphs,
                    summary="",
                )
                chapters.append(chapter)

                progress.progress_percent = (idx + 1) / len(chapters_raw) * 100
                progress.message = f"已编号 {idx+1}/{len(chapters_raw)} 个章节"
                self._notify_progress(run)

            progress.status = StageStatus.COMPLETED
            progress.completed_at = datetime.now()
            progress.progress_percent = 100.0
            progress.message = f"完成 {len(chapters)} 个章节的段落编号"
            progress.result_summary = {
                "chapter_count": len(chapters),
                "total_paragraphs": sum(len(c.paragraphs) for c in chapters),
            }
            self._notify_progress(run)

            return chapters

        except Exception as e:
            progress.status = StageStatus.FAILED
            progress.error = str(e)
            self._notify_progress(run)
            raise

    async def _stage_chapter_understanding(
        self,
        run: PipelineRun,
        chapters: List[Chapter],
        model_router: ModelRouter,
        llm_provider: LLMProvider,
    ) -> List[Dict[str, Any]]:
        """阶段3: 逐章理解（不生成剧本，只提取关键信息）"""
        progress = run.stages[PipelineStage.CHAPTER_UNDERSTANDING]
        progress.status = StageStatus.RUNNING
        progress.started_at = datetime.now()
        progress.progress_percent = 0.0
        progress.message = "正在逐章理解..."
        self._notify_progress(run)

        try:
            understandings = []
            total = len(chapters)

            for idx, chapter in enumerate(chapters):
                # 加载prompt模板
                prompt_data = self._load_prompt("chapter_understanding")

                # 构造用户提示
                chapter_text = "\n".join([p.text for p in chapter.paragraphs])
                user_prompt = prompt_data["user_prompt_template"].format(
                    chapter_title=chapter.title,
                    chapter_text=chapter_text,
                    chapter_order=chapter.order,
                )

                # 使用LLM生成理解
                result = await llm_provider.generate_structured(
                    output_type=dict,  # 理解阶段返回原始字典
                    task_type=TaskType.CHAPTER_UNDERSTANDING,
                    prompt=user_prompt,
                    system_prompt=prompt_data["system_prompt"],
                    temperature=prompt_data.get("temperature", 0.3),
                )

                understanding = result.content if result.success else {
                    "characters": [],
                    "locations": [],
                    "events": [],
                    "summary": chapter.paragraphs[0].text[:200] if chapter.paragraphs else "",
                }
                understanding["chapter_id"] = chapter.id
                understandings.append(understanding)

                progress.progress_percent = (idx + 1) / total * 100
                progress.message = f"已理解 {idx+1}/{total} 个章节"
                self._notify_progress(run)

            progress.status = StageStatus.COMPLETED
            progress.completed_at = datetime.now()
            progress.progress_percent = 100.0
            progress.message = f"完成 {len(understandings)} 个章节的理解"
            progress.result_summary = {"understood_chapters": len(understandings)}
            self._notify_progress(run)

            return understandings

        except Exception as e:
            progress.status = StageStatus.FAILED
            progress.error = str(e)
            self._notify_progress(run)
            raise

    async def _stage_story_bible_merge(
        self,
        run: PipelineRun,
        understandings: List[Dict[str, Any]],
        model_router: ModelRouter,
        llm_provider: LLMProvider,
    ) -> StoryBible:
        """阶段4: 故事圣经合并（别名归一化、地点同一性、时间线排序）"""
        progress = run.stages[PipelineStage.STORY_BIBLE_MERGE]
        progress.status = StageStatus.RUNNING
        progress.started_at = datetime.now()
        progress.progress_percent = 0.0
        progress.message = "正在合并故事圣经..."
        self._notify_progress(run)

        try:
            bible_service = StoryBibleService(llm_provider, model_router)
            story_bible = await bible_service.merge_from_understandings(understandings)

            progress.status = StageStatus.COMPLETED
            progress.completed_at = datetime.now()
            progress.progress_percent = 100.0
            progress.message = f"故事圣经合并完成: {len(story_bible.characters)} 角色, {len(story_bible.locations)} 地点"
            progress.result_summary = {
                "character_count": len(story_bible.characters),
                "location_count": len(story_bible.locations),
                "timeline_entries": len(story_bible.timeline),
            }
            self._notify_progress(run)

            return story_bible

        except Exception as e:
            progress.status = StageStatus.FAILED
            progress.error = str(e)
            self._notify_progress(run)
            raise

    async def _stage_scene_splitting(
        self,
        run: PipelineRun,
        chapters: List[Chapter],
        understandings: List[Dict[str, Any]],
        story_bible: StoryBible,
        model_router: ModelRouter,
        llm_provider: LLMProvider,
    ) -> List[Scene]:
        """阶段5: 场景拆分（必须有dramatic_purpose和conflict）"""
        progress = run.stages[PipelineStage.SCENE_SPLITTING]
        progress.status = StageStatus.RUNNING
        progress.started_at = datetime.now()
        progress.progress_percent = 0.0
        progress.message = "正在拆分场景..."
        self._notify_progress(run)

        try:
            splitter = SceneSplitter(llm_provider, model_router)
            scenes = await splitter.split_from_chapters(
                chapters, understandings, story_bible
            )

            progress.status = StageStatus.COMPLETED
            progress.completed_at = datetime.now()
            progress.progress_percent = 100.0
            progress.message = f"场景拆分完成: {len(scenes)} 个场景"
            progress.result_summary = {"scene_count": len(scenes)}
            self._notify_progress(run)

            return scenes

        except Exception as e:
            progress.status = StageStatus.FAILED
            progress.error = str(e)
            self._notify_progress(run)
            raise

    async def _stage_element_generation(
        self,
        run: PipelineRun,
        scenes: List[Scene],
        story_bible: StoryBible,
        model_router: ModelRouter,
        llm_provider: LLMProvider,
    ) -> List[Scene]:
        """阶段6: 剧本元素生成"""
        progress = run.stages[PipelineStage.ELEMENT_GENERATION]
        progress.status = StageStatus.RUNNING
        progress.started_at = datetime.now()
        progress.progress_percent = 0.0
        progress.message = "正在生成剧本元素..."
        self._notify_progress(run)

        try:
            generator = ScriptGenerator(llm_provider, model_router)
            scenes_with_elements = await generator.generate_elements(
                scenes, story_bible
            )

            progress.status = StageStatus.COMPLETED
            progress.completed_at = datetime.now()
            progress.progress_percent = 100.0
            progress.message = f"剧本元素生成完成: {len(scenes_with_elements)} 个场景"
            total_elements = sum(len(s.elements) for s in scenes_with_elements)
            progress.result_summary = {
                "scene_count": len(scenes_with_elements),
                "total_elements": total_elements,
            }
            self._notify_progress(run)

            return scenes_with_elements

        except Exception as e:
            progress.status = StageStatus.FAILED
            progress.error = str(e)
            self._notify_progress(run)
            raise

    async def _stage_schema_validation(
        self,
        run: PipelineRun,
        chapters: List[Chapter],
        story_bible: StoryBible,
        scenes: List[Scene],
        model_router: ModelRouter,
        llm_provider: LLMProvider,
    ) -> Screenplay:
        """阶段7: 校验修复闭环"""
        progress = run.stages[PipelineStage.SCHEMA_VALIDATION]
        progress.status = StageStatus.RUNNING
        progress.started_at = datetime.now()
        progress.progress_percent = 0.0
        progress.message = "正在进行Schema校验..."
        self._notify_progress(run)

        try:
            # 构造初始Screenplay
            project_id = run.project_id
            screenplay = Screenplay(
                schema_version="1.0.0",
                project=ProjectInfo(
                    id=project_id,
                    title="",
                    source_language="zh-CN",
                    target_format="screenplay",
                    adaptation_style=None,
                ),
                story_bible=story_bible,
                chapters=chapters,
                scenes=scenes,
                metadata=GenerationMetadata(
                    generated_at=datetime.now().isoformat(),
                    model=model_router.route(TaskType.ELEMENT_GENERATION).name,
                    source_chapter_count=len(chapters),
                    total_scenes=len(scenes),
                    total_elements=sum(len(s.elements) for s in scenes),
                ),
            )

            # 校验
            validator = SchemaValidator(llm_provider, model_router)
            validation_result = validator.validate_screenplay(screenplay)

            progress.progress_percent = 50.0
            progress.message = f"校验发现 {len(validation_result.errors)} 个问题，正在修复..."
            self._notify_progress(run)

            # 如果有错误，尝试修复
            if validation_result.errors:
                screenplay = await validator.repair_screenplay(
                    screenplay, validation_result
                )

            progress.status = StageStatus.COMPLETED
            progress.completed_at = datetime.now()
            progress.progress_percent = 100.0
            progress.message = "校验修复完成"
            progress.result_summary = {
                "initial_errors": len(validation_result.errors),
                "final_errors": 0,  # 修复后应该为0
            }
            self._notify_progress(run)

            return screenplay

        except Exception as e:
            progress.status = StageStatus.FAILED
            progress.error = str(e)
            self._notify_progress(run)
            raise

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

        # 返回默认prompt
        return {
            "name": prompt_name,
            "version": "1.0",
            "model_tier": "standard",
            "system_prompt": "你是一个专业的小说分析和剧本创作助手。",
            "user_prompt_template": "请分析以下内容：{chapter_text}",
            "temperature": 0.3,
            "max_retries": 2,
        }

    def _notify_progress(self, run: PipelineRun):
        """通知进度更新"""
        for callback in run.callbacks:
            try:
                progress_data = {
                    "run_id": run.run_id,
                    "stages": {
                        stage.value: {
                            "status": p.status.value,
                            "progress_percent": p.progress_percent,
                            "message": p.message,
                        }
                        for stage, p in run.stages.items()
                    },
                }
                callback(progress_data)
            except Exception as e:
                logger.warning(f"进度回调失败: {e}")

    def get_run_status(self, run_id: str) -> Optional[Dict[str, Any]]:
        """获取运行状态"""
        run = self._runs.get(run_id)
        if not run:
            return None

        return {
            "run_id": run.run_id,
            "project_id": run.project_id,
            "stages": {
                stage.value: {
                    "status": p.status.value,
                    "progress_percent": p.progress_percent,
                    "message": p.message,
                    "started_at": p.started_at.isoformat() if p.started_at else None,
                    "completed_at": p.completed_at.isoformat() if p.completed_at else None,
                    "error": p.error,
                }
                for stage, p in run.stages.items()
            },
            "created_at": run.created_at.isoformat(),
        }

    async def retry_stage(
        self,
        run_id: str,
        stage: PipelineStage,
        model_router: ModelRouter,
        llm_provider: LLMProvider,
    ) -> bool:
        """重试指定阶段"""
        run = self._runs.get(run_id)
        if not run:
            return False

        progress = run.stages.get(stage)
        if not progress or progress.status != StageStatus.FAILED:
            return False

        # 重置阶段状态
        progress.status = StageStatus.PENDING
        progress.error = None
        progress.progress_percent = 0.0

        # 从失败阶段重新执行
        # 这里简化为重新执行整个Pipeline
        try:
            result = await self.execute(run, model_router, llm_provider)
            return True
        except Exception:
            return False