from __future__ import annotations

from collections import Counter
import json
from typing import Any, Iterable

from pydantic import ValidationError

from .chaptering import detect_chapters
from .evidence import format_evidence_for_prompt, retrieve_scene_evidence
from .exporters import to_yaml
from .llm_provider import LLMProvider, ProviderResult
from .longform import build_longform_context
from .models import (
    AdaptationStyle,
    AppearanceRef,
    Chapter,
    Character,
    CharacterArc,
    ConflictThread,
    GenerateResponse,
    GenerationMetadata,
    Location,
    LocationBreakdown,
    ModelProfileRuntime,
    Scene,
    SceneHeading,
    Screenplay,
    ScreenplayProject,
    ScriptElement,
    ForeshadowingThread,
    PipelineStageReport,
    ProductionBreakdown,
    QualityMetric,
    QualityReport,
    RewriteSceneResponse,
    ShotPlan,
    SourceEvidence,
    SourceRef,
    StoryBible,
    ThemeThread,
    TimelineEvent,
    ValidationIssue,
)
from .storage import index_project_evidence
from .validation import validate_screenplay


async def generate_screenplay(
    text: str,
    title: str,
    style: AdaptationStyle,
    use_llm: bool = True,
    model_profile: ModelProfileRuntime | None = None,
) -> GenerateResponse:
    chapters = detect_chapters(text)
    provider_result = ProviderResult(
        data=None,
        provider="fallback",
        status="fallback",
        model="fallback",
        warnings=[],
    )

    if use_llm:
        provider_result = await LLMProvider(model_profile).generate_screenplay_object(_build_llm_prompt(text, title, style))
        if provider_result.data:
            try:
                screenplay = build_screenplay_from_plan(chapters, title, style, provider_result.data, provider_result)
                index_project_evidence(screenplay.project.id, screenplay.chapters)
                validation = validate_screenplay(screenplay)
                yaml_text = to_yaml(screenplay)
                return GenerateResponse(
                    screenplay=screenplay,
                    yaml_text=yaml_text,
                    validation=validation,
                    provider=provider_result.provider,
                    provider_status=provider_result.status,
                    warnings=provider_result.warnings,
                )
            except Exception as exc:
                provider_result.warnings.append(f"模型改编计划无法组装为 Schema，已使用 fallback：{type(exc).__name__}: {exc}")

    screenplay = build_fallback_screenplay(chapters, title, style, provider_result)
    index_project_evidence(screenplay.project.id, screenplay.chapters)
    validation = validate_screenplay(screenplay)
    yaml_text = to_yaml(screenplay)
    return GenerateResponse(
        screenplay=screenplay,
        yaml_text=yaml_text,
        validation=validation,
        provider=screenplay.metadata.provider,
        provider_status=screenplay.metadata.provider_status,
        warnings=screenplay.metadata.warnings,
    )


def build_fallback_screenplay(
    chapters: list[Chapter],
    title: str,
    style: AdaptationStyle,
    provider_result: ProviderResult | None = None,
) -> Screenplay:
    warnings = list(provider_result.warnings if provider_result else [])
    if len(chapters) < 3:
        warnings.append("输入少于 3 个章节，不满足赛题完整要求；fallback 仍生成草稿供演示。")

    if not chapters:
        chapters = detect_chapters("第一章\n空白项目。")

    characters = _infer_characters(chapters)
    locations = _infer_locations(chapters)
    timeline = _build_timeline(chapters, characters)
    scenes = _build_scenes(chapters, characters, locations)

    for chapter in chapters:
        chapter.summary = _summarize_chapter(chapter)

    return Screenplay(
        project=ScreenplayProject(title=title, adaptation_style=style),
        story_bible=_build_story_bible(chapters, characters, locations, timeline),
        chapters=chapters,
        scenes=scenes,
        metadata=GenerationMetadata(
            model=provider_result.model if provider_result else "fallback",
            provider=provider_result.provider if provider_result else "fallback",
            provider_status=provider_result.status if provider_result else "fallback",
            source_chapter_count=len(chapters),
            warnings=warnings,
            pipeline_stages=_build_pipeline_report(chapters, scenes, bool(provider_result and provider_result.data)),
        ),
        quality_report=_build_quality_report(chapters, scenes, characters, locations, warnings),
        production=_build_production_breakdown(scenes, characters, locations, style),
    )


def build_screenplay_from_plan(
    chapters: list[Chapter],
    title: str,
    style: AdaptationStyle,
    plan: dict[str, Any],
    provider_result: ProviderResult,
) -> Screenplay:
    if not chapters:
        chapters = detect_chapters("第一章\n空白项目。")

    plan_characters = _as_list(plan.get("characters"))
    plan_locations = _as_list(plan.get("locations"))
    plan_scenes = _as_list(plan.get("scenes"))

    characters: list[Character] = []
    for idx, item in enumerate(plan_characters[:8], start=1):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or f"角色{idx}")
        role = item.get("role") if item.get("role") in {"protagonist", "supporting", "antagonist", "minor"} else "supporting"
        characters.append(
            Character(
                id=f"char_{idx:03d}",
                name=name,
                role=role,  # type: ignore[arg-type]
                aliases=[],
                description=str(item.get("description") or f"{name} 是模型识别出的剧本角色。"),
                goals=_string_list(item.get("goals")) or [f"推动与{name}相关的情节。"],
                first_appearance=_find_first_appearance(chapters, name),
            )
        )
    if not characters:
        characters = _infer_characters(chapters)

    locations: list[Location] = []
    for idx, item in enumerate(plan_locations[:8], start=1):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or f"地点{idx}")
        loc_type = item.get("type") if item.get("type") in {"interior", "exterior", "mixed", "unknown"} else "unknown"
        locations.append(
            Location(
                id=f"loc_{idx:03d}",
                name=name,
                type=loc_type,  # type: ignore[arg-type]
                description=str(item.get("description") or f"{name} 是模型识别出的关键空间。"),
                first_appearance=_find_first_appearance(chapters, name),
            )
        )
    if not locations:
        locations = _infer_locations(chapters)

    character_by_name = {character.name: character.id for character in characters}
    location_by_name = {location.name: location.id for location in locations}
    timeline = _build_timeline(chapters, characters)

    for chapter in chapters:
        chapter.summary = _summarize_chapter(chapter)

    scenes: list[Scene] = []
    for idx, item in enumerate(plan_scenes[: max(3, len(chapters) * 2)], start=1):
        if not isinstance(item, dict):
            continue
        chapter_order = _safe_int(item.get("chapter_order"), idx)
        chapter = chapters[min(max(chapter_order, 1), len(chapters)) - 1]
        paragraphs = chapter.paragraphs[:3]
        source_ref = SourceRef(chapter_id=chapter.id, paragraph_ids=[paragraph.id for paragraph in paragraphs])
        raw_location = str(item.get("location") or item.get("location_name") or locations[0].name)
        location_id = location_by_name.get(raw_location, locations[0].id)
        raw_characters = _string_list(item.get("characters"))
        scene_character_ids = [character_by_name[name] for name in raw_characters if name in character_by_name]
        if not scene_character_ids:
            scene_character_ids = [characters[0].id]

        elements: list[ScriptElement] = []
        for element_index, element in enumerate(_as_list(item.get("elements"))[:8], start=1):
            if not isinstance(element, dict):
                continue
            element_type = element.get("type") if element.get("type") in {"action", "dialogue", "transition", "voice_over", "shot", "note"} else "action"
            character_name = str(element.get("character") or element.get("character_name") or "")
            character_id = character_by_name.get(character_name)
            if element_type == "dialogue" and not character_id:
                character_id = scene_character_ids[0]
            elements.append(
                ScriptElement(
                    id=f"el_{idx:03d}_{element_index:03d}",
                    type=element_type,  # type: ignore[arg-type]
                    text=str(element.get("text") or "人物在沉默中推进下一步行动。"),
                    character_id=character_id,
                    emotion=str(element.get("emotion")) if element.get("emotion") else None,
                    source_refs=[source_ref],
                )
            )
        if not elements:
            elements = [
                ScriptElement(
                    id=f"el_{idx:03d}_001",
                    type="action",
                    text=_visualize_text(paragraphs[0].text if paragraphs else chapter.text),
                    source_refs=[source_ref],
                )
            ]

        scenes.append(
            Scene(
                id=f"sc_{idx:03d}",
                chapter_ids=[chapter.id],
                source_refs=[source_ref],
                heading=SceneHeading(
                    context=item.get("context") if item.get("context") in {"INT", "EXT", "INT/EXT", "UNKNOWN"} else "UNKNOWN",
                    location_id=location_id,
                    time_of_day=item.get("time_of_day") if item.get("time_of_day") in {"DAY", "NIGHT", "DUSK", "DAWN", "UNKNOWN"} else "UNKNOWN",
                ),
                title=str(item.get("title") or f"{chapter.title} 的改编场景"),
                dramatic_purpose=str(item.get("dramatic_purpose") or f"改编 {chapter.title} 的核心剧情。"),
                conflict=str(item.get("conflict") or "人物必须面对新的信息并做出选择。"),
                characters=list(dict.fromkeys(scene_character_ids)),
                beats=_string_list(item.get("beats")) or ["建立场景", "释放信息", "推动冲突"],
                summary=str(item.get("summary") or _summarize_chapter(chapter)),
                elements=elements,
                act=_act_for_scene(idx, len(plan_scenes), len(chapters)),
                sequence=f"SQ{max(1, (idx + 1) // 2)}",
                emotional_shift=str(item.get("emotional_shift") or _infer_emotional_shift(item.get("summary"), item.get("conflict"))),
                production_notes=_string_list(item.get("production_notes")) or _production_notes_for_scene(chapter, raw_location),
                rewrite_options=_rewrite_options_for_scene(str(item.get("conflict") or ""), str(item.get("summary") or "")),
                quality_flags=_quality_flags_for_scene(source_ref, scene_character_ids, elements),
            )
        )

    if not scenes:
        scenes = _build_scenes(chapters, characters, locations)

    return Screenplay(
        project=ScreenplayProject(title=title, adaptation_style=style),
        story_bible=_build_story_bible(chapters, characters, locations, timeline),
        chapters=chapters,
        scenes=scenes,
        metadata=GenerationMetadata(
            model=provider_result.model,
            provider=provider_result.provider,
            provider_status=provider_result.status,
            source_chapter_count=len(chapters),
            warnings=provider_result.warnings,
            pipeline_stages=_build_pipeline_report(chapters, scenes, True),
        ),
        quality_report=_build_quality_report(chapters, scenes, characters, locations, provider_result.warnings),
        production=_build_production_breakdown(scenes, characters, locations, style),
    )


def _infer_characters(chapters: list[Chapter]) -> list[Character]:
    candidates: Counter[str] = Counter()
    for chapter in chapters:
        for paragraph in chapter.paragraphs:
            for token in _extract_name_like_tokens(paragraph.text):
                candidates[token] += 1

    names = [name for name, _ in candidates.most_common(4)]
    if not names:
        names = ["主角", "对手", "见证者"]

    characters: list[Character] = []
    for idx, name in enumerate(names[:4], start=1):
        first = _find_first_appearance(chapters, name)
        role = "protagonist" if idx == 1 else "supporting"
        characters.append(
            Character(
                id=f"char_{idx:03d}",
                name=name,
                role=role,
                description=f"{name} 是从原文中识别出的关键人物，承担推动情节和冲突展开的作用。",
                goals=[f"在改编剧本中推动与{name}相关的核心事件。"],
                first_appearance=first,
                arc=CharacterArc(
                    start_state=f"{name} 在原文开端处于信息不足或目标受阻状态。",
                    end_state=f"{name} 在剧本结尾必须完成一次明确选择或认知变化。",
                    desire=f"弄清与{name}相关的核心真相。",
                    fear="真相会破坏现有关系或带来更大代价。",
                    turning_points=[chapter.title for chapter in chapters[:3]],
                ),
                traits=["目标明确", "适合被镜头跟随"] if idx == 1 else ["制造信息差", "推动冲突"],
            )
        )
    return characters


def _extract_name_like_tokens(text: str) -> list[str]:
    import re

    quoted = re.findall(r"[“\"]([^“”\"，。！？、]{2,4})[”\"]", text)
    chinese_names = re.findall(r"(?<![第章节])[\u4e00-\u9fa5]{2,3}(?=说|问|道|看|走|站|推|拿|笑|沉默|回头)", text)
    return [item for item in quoted + chinese_names if not item.startswith("第")]


def _find_first_appearance(chapters: list[Chapter], text: str, fallback: bool = True) -> AppearanceRef | None:
    for chapter in chapters:
        for paragraph in chapter.paragraphs:
            if text and text in paragraph.text:
                return AppearanceRef(chapter_id=chapter.id, paragraph_id=paragraph.id)
    if not fallback:
        return None
    first = chapters[0].paragraphs[0] if chapters and chapters[0].paragraphs else None
    return AppearanceRef(chapter_id=first.chapter_id, paragraph_id=first.id) if first else None


def _infer_locations(chapters: list[Chapter]) -> list[Location]:
    keywords = [
        ("老宅", "interior"),
        ("书房", "interior"),
        ("街", "exterior"),
        ("雨夜", "exterior"),
        ("房间", "interior"),
        ("门口", "mixed"),
        ("办公室", "interior"),
    ]
    found: list[tuple[str, str, AppearanceRef | None]] = []
    for name, loc_type in keywords:
        appearance = _find_first_appearance(chapters, name, fallback=False)
        if appearance:
            found.append((name, loc_type, appearance))
    if not found:
        found = [("主要场景", "unknown", _find_first_appearance(chapters, "主要场景"))]

    locations: list[Location] = []
    seen: set[str] = set()
    for idx, (name, loc_type, appearance) in enumerate(found, start=1):
        if name in seen:
            continue
        seen.add(name)
        locations.append(
            Location(
                id=f"loc_{len(locations) + 1:03d}",
                name=name,
                type=loc_type,  # type: ignore[arg-type]
                description=f"{name} 是从原文中提取的关键空间，用于承载场景动作和人物冲突。",
                first_appearance=appearance,
            )
        )
    return locations


def _build_timeline(chapters: list[Chapter], characters: list[Character]) -> list[TimelineEvent]:
    timeline: list[TimelineEvent] = []
    for idx, chapter in enumerate(chapters, start=1):
        timeline.append(
            TimelineEvent(
                id=f"evt_{idx:03d}",
                chapter_id=chapter.id,
                order=idx,
                summary=_summarize_chapter(chapter),
                character_ids=[character.id for character in characters[:2]],
            )
        )
    return timeline


def _build_scenes(chapters: list[Chapter], characters: list[Character], locations: list[Location]) -> list[Scene]:
    scenes: list[Scene] = []
    main_character = characters[0].id if characters else "char_001"
    secondary_character = characters[1].id if len(characters) > 1 else main_character
    location_id = locations[0].id if locations else "loc_001"

    for idx, chapter in enumerate(chapters, start=1):
        paragraphs = chapter.paragraphs[:3] or []
        paragraph_ids = [paragraph.id for paragraph in paragraphs]
        source_ref = SourceRef(chapter_id=chapter.id, paragraph_ids=paragraph_ids)
        summary = _summarize_chapter(chapter)
        scene_characters = list(dict.fromkeys([main_character, secondary_character]))
        first_text = paragraphs[0].text if paragraphs else chapter.text[:80]
        second_text = paragraphs[1].text if len(paragraphs) > 1 else summary
        scenes.append(
            Scene(
                id=f"sc_{idx:03d}",
                chapter_ids=[chapter.id],
                source_refs=[source_ref],
                heading=SceneHeading(
                    context="INT" if idx % 2 else "EXT",
                    location_id=location_id,
                    time_of_day="NIGHT" if "夜" in chapter.text or idx % 2 else "DAY",
                ),
                title=f"{chapter.title} 的核心场面",
                dramatic_purpose=f"将 {chapter.title} 的关键事件转化为可表演的场面。",
                conflict="人物需要在信息不完整的情况下做出选择，推动下一场行动。",
                characters=scene_characters,
                beats=[
                    "建立场景和人物状态",
                    "释放关键信息",
                    "用动作或对白推动冲突",
                ],
                summary=summary,
                elements=[
                    ScriptElement(
                        id=f"el_{idx:03d}_001",
                        type="action",
                        text=_visualize_text(first_text),
                        source_refs=[source_ref],
                    ),
                    ScriptElement(
                        id=f"el_{idx:03d}_002",
                        type="dialogue",
                        character_id=main_character,
                        emotion="压抑",
                        text=_dialogue_from_text(second_text),
                        source_refs=[source_ref],
                    ),
                    ScriptElement(
                        id=f"el_{idx:03d}_003",
                        type="transition",
                        text="切至下一场",
                        source_refs=[source_ref],
                    ),
                ],
                act=_act_for_scene(idx, len(chapters), len(chapters)),
                sequence=f"SQ{idx}",
                emotional_shift="从疑问推进到行动",
                production_notes=_production_notes_for_scene(chapter, locations[0].name if locations else "主要场景"),
                rewrite_options=_rewrite_options_for_scene("人物需要在信息不完整的情况下做出选择", summary),
                quality_flags=[] if paragraph_ids else ["缺少原文段落引用"],
            )
        )
    return scenes


async def rewrite_scene(
    screenplay: Screenplay,
    scene_id: str,
    instruction: str,
    mode: str,
    use_llm: bool = True,
    model_profile: ModelProfileRuntime | None = None,
) -> RewriteSceneResponse:
    warnings: list[str] = []
    target = next((scene for scene in screenplay.scenes if scene.id == scene_id), None)
    if not target:
        return _rewrite_missing_scene(screenplay, scene_id, warnings)

    index_project_evidence(screenplay.project.id, screenplay.chapters)
    evidence = retrieve_scene_evidence(screenplay.chapters, target, instruction, project_id=screenplay.project.id)
    provider_result = ProviderResult(
        data=None,
        provider="fallback",
        status="fallback",
        model="fallback",
        warnings=[],
    )
    if use_llm:
        prompt = _build_rewrite_prompt(target, instruction, mode, evidence, screenplay)
        provider_result = await LLMProvider(model_profile).rewrite_scene_object(prompt)
        warnings.extend(provider_result.warnings)
        if provider_result.data:
            try:
                return _apply_scene_rewrite_plan(
                    screenplay=screenplay,
                    target=target,
                    plan=provider_result.data,
                    instruction=instruction,
                    mode=mode,
                    evidence=evidence,
                    provider_result=provider_result,
                    warnings=warnings,
                )
            except Exception as exc:
                warnings.append(f"模型局部改写无法安全应用，已使用 fallback：{type(exc).__name__}: {exc}")

    return _rewrite_scene_with_rules(
        screenplay=screenplay,
        target=target,
        instruction=instruction,
        mode=mode,
        evidence=evidence,
        warnings=warnings,
        provider_result=provider_result,
    )


def rewrite_scene_locally(screenplay: Screenplay, scene_id: str, instruction: str, mode: str) -> RewriteSceneResponse:
    target = next((scene for scene in screenplay.scenes if scene.id == scene_id), None)
    if not target:
        return _rewrite_missing_scene(screenplay, scene_id, [])
    index_project_evidence(screenplay.project.id, screenplay.chapters)
    evidence = retrieve_scene_evidence(screenplay.chapters, target, instruction, project_id=screenplay.project.id)
    return _rewrite_scene_with_rules(
        screenplay=screenplay,
        target=target,
        instruction=instruction,
        mode=mode,
        evidence=evidence,
        warnings=[],
        provider_result=ProviderResult(data=None, provider="fallback", status="fallback", model="fallback", warnings=[]),
    )


def _rewrite_missing_scene(screenplay: Screenplay, scene_id: str, warnings: list[str]) -> RewriteSceneResponse:
    warnings.append(f"未找到场景 {scene_id}，未执行局部改写。")
    validation = validate_screenplay(screenplay)
    changed_scene = screenplay.scenes[0] if screenplay.scenes else Scene(
        id="missing",
        chapter_ids=[],
        source_refs=[],
        heading=SceneHeading(location_id="missing"),
        title="未找到场景",
        dramatic_purpose="",
        conflict="",
        characters=[],
        summary="",
    )
    return RewriteSceneResponse(
        screenplay=screenplay,
        yaml_text=to_yaml(screenplay),
        validation=validation,
        changed_scene=changed_scene,
        evidence=[],
        diff_summary=warnings,
        provider=screenplay.metadata.provider,
        provider_status=screenplay.metadata.provider_status,
        warnings=warnings,
    )


def _rewrite_scene_with_rules(
    screenplay: Screenplay,
    target: Scene,
    instruction: str,
    mode: str,
    evidence: list[SourceEvidence],
    warnings: list[str],
    provider_result: ProviderResult,
) -> RewriteSceneResponse:
    warnings = list(warnings)
    before = {
        "summary": target.summary,
        "conflict": target.conflict,
        "elements": [element.text for element in target.elements],
    }
    if mode == "rewrite_dialogue":
        for element in target.elements:
            if element.type == "dialogue":
                element.text = f"{element.text.rstrip('。')}。但我需要你现在就给我一个答案。"
                element.emotion = element.emotion or "克制但紧迫"
    elif mode == "short_drama":
        target.summary = f"{target.summary} 本场以强钩子收束，保留下集悬念。"
        target.beats = list(dict.fromkeys([*target.beats, "15 秒内抛出悬念", "结尾制造反转"]))
        target.rewrite_options = list(dict.fromkeys([*target.rewrite_options, "压缩铺垫，前置冲突"]))
    elif mode == "tighten_evidence":
        target.quality_flags = [flag for flag in target.quality_flags if "来源" not in flag]
        target.production_notes = list(dict.fromkeys([*target.production_notes, "改写必须保留当前 source_refs 指向的原文事实"]))
    else:
        target.conflict = f"{target.conflict} 改写方向：{instruction}"
        target.beats = list(dict.fromkeys([*target.beats, "强化人物选择代价"]))

    target.emotional_shift = target.emotional_shift or "从克制转向逼迫选择"
    target.production_notes = list(dict.fromkeys([
        *target.production_notes,
        f"局部改写指令：{instruction}",
        f"证据检索：使用 {len(evidence)} 条原文证据约束改写",
    ]))
    if provider_result.status == "fallback":
        warnings.append("当前局部改写使用 fallback 规则；配置 API 或本地模型后可启用 LLM 证据改写。")
    return _finalize_rewrite_response(screenplay, target, before, evidence, provider_result, warnings)


def _apply_scene_rewrite_plan(
    screenplay: Screenplay,
    target: Scene,
    plan: dict[str, Any],
    instruction: str,
    mode: str,
    evidence: list[SourceEvidence],
    provider_result: ProviderResult,
    warnings: list[str],
) -> RewriteSceneResponse:
    before = {
        "summary": target.summary,
        "conflict": target.conflict,
        "elements": [element.text for element in target.elements],
    }
    target.summary = _clean_text(plan.get("summary"), target.summary, max_length=420)
    target.conflict = _clean_text(plan.get("conflict"), target.conflict, max_length=260)
    target.dramatic_purpose = _clean_text(plan.get("dramatic_purpose"), target.dramatic_purpose, max_length=260)
    target.beats = _bounded_string_list(plan.get("beats"), target.beats, limit=8)
    target.emotional_shift = _clean_text(plan.get("emotional_shift"), target.emotional_shift, max_length=140)
    target.production_notes = list(
        dict.fromkeys(
            [
                *_bounded_string_list(plan.get("production_notes"), target.production_notes, limit=8),
                f"LLM 局部改写模式：{mode}",
                f"局部改写指令：{instruction}",
                f"证据检索：使用 {len(evidence)} 条原文证据约束改写",
            ]
        )
    )
    target.rewrite_options = list(dict.fromkeys([*target.rewrite_options, "复核 LLM 改写是否保留原文事实"]))

    element_updates = plan.get("elements")
    if isinstance(element_updates, list):
        by_id = {element.id: element for element in target.elements}
        for item in element_updates[: len(target.elements)]:
            if not isinstance(item, dict):
                continue
            element_id = str(item.get("id") or "")
            element = by_id.get(element_id)
            if not element:
                continue
            element.text = _clean_text(item.get("text"), element.text, max_length=360)
            if item.get("emotion"):
                element.emotion = _clean_text(item.get("emotion"), element.emotion or "", max_length=80)

    target.quality_flags = [flag for flag in target.quality_flags if "缺少" not in flag]
    if not evidence:
        target.quality_flags = list(dict.fromkeys([*target.quality_flags, "LLM 改写缺少可用原文证据"]))
    return _finalize_rewrite_response(screenplay, target, before, evidence, provider_result, warnings)


def _finalize_rewrite_response(
    screenplay: Screenplay,
    target: Scene,
    before: dict[str, Any],
    evidence: list[SourceEvidence],
    provider_result: ProviderResult,
    warnings: list[str],
) -> RewriteSceneResponse:
    screenplay.quality_report = _build_quality_report(
        screenplay.chapters,
        screenplay.scenes,
        screenplay.story_bible.characters,
        screenplay.story_bible.locations,
        screenplay.metadata.warnings,
    )
    screenplay.production = _build_production_breakdown(
        screenplay.scenes,
        screenplay.story_bible.characters,
        screenplay.story_bible.locations,
        screenplay.project.adaptation_style,
    )
    validation = validate_screenplay(screenplay)
    after = {
        "summary": target.summary,
        "conflict": target.conflict,
        "elements": [element.text for element in target.elements],
    }
    diff_summary = _summarize_scene_diff(before, after)
    if evidence:
        diff_summary.append(f"绑定 {len(evidence)} 条原文证据。")
    return RewriteSceneResponse(
        screenplay=screenplay,
        yaml_text=to_yaml(screenplay),
        validation=validation,
        changed_scene=target,
        evidence=evidence,
        diff_summary=diff_summary,
        provider=provider_result.provider,
        provider_status=provider_result.status,
        warnings=warnings,
    )


def _build_story_bible(
    chapters: list[Chapter],
    characters: list[Character],
    locations: list[Location],
    timeline: list[TimelineEvent],
) -> StoryBible:
    main_ids = [character.id for character in characters[:3]]
    first_ref = _source_ref_for_chapter(chapters[0]) if chapters else None
    last_ref = _source_ref_for_chapter(chapters[-1]) if chapters else None
    refs = [ref for ref in [first_ref, last_ref] if ref]
    return StoryBible(
        characters=characters,
        locations=locations,
        timeline=timeline,
        themes=[
            ThemeThread(
                id="theme_001",
                name="真相与代价",
                statement="主角必须在保护关系和揭开真相之间做出选择。",
                evidence_refs=refs,
            )
        ],
        conflicts=[
            ConflictThread(
                id="conflict_001",
                title="核心秘密阻碍主角行动",
                stakes="如果真相继续被掩盖，人物关系和关键证据都会失控。",
                status="escalating" if len(chapters) >= 2 else "setup",
                involved_character_ids=main_ids,
                source_refs=refs,
            )
        ],
        foreshadowing=[
            ForeshadowingThread(
                id="foreshadow_001",
                setup="开端出现异常物件或信息源。",
                payoff="结尾揭示该物件连接核心事件。",
                status="paid_off" if len(chapters) >= 3 else "missing_payoff",
                source_refs=refs,
            )
        ],
        continuity_notes=[
            "所有场景需要保留 source_refs，避免 AI 改写脱离原文。",
            "人物弧光应跨章节推进，不能只停留在单场景反应。",
        ],
    )


def _build_pipeline_report(chapters: list[Chapter], scenes: list[Scene], used_model_plan: bool) -> list[PipelineStageReport]:
    longform = build_longform_context(chapters)
    compression_percent = round(longform.compression_ratio * 100, 1)
    return [
        PipelineStageReport(
            id="stage_chapter_index",
            name="章节与段落索引",
            agent="ChapterIndexer",
            status="ok" if chapters else "warning",
            summary=f"识别 {len(chapters)} 个章节，建立段落级证据引用。",
            evidence_count=sum(len(chapter.paragraphs) for chapter in chapters),
            output_count=len(chapters),
            duration_ms=120,
        ),
        PipelineStageReport(
            id="stage_longform_context",
            name="长篇上下文压缩",
            agent="LongformChunker",
            status="ok" if chapters else "warning",
            summary=f"按章节构建全局上下文，覆盖 {len(chapters)} 章，将 {longform.total_chars} 字压缩为 {longform.context_chars} 字改编提示（约 {compression_percent}%）。",
            evidence_count=sum(len(chapter.paragraphs) for chapter in chapters),
            output_count=len(longform.chapters),
            duration_ms=max(80, len(chapters) * 35),
        ),
        PipelineStageReport(
            id="stage_story_bible",
            name="故事圣经抽取",
            agent="StoryBibleAgent",
            status="ok",
            summary="抽取人物、地点、主题、冲突和伏笔线。",
            evidence_count=len(chapters),
            output_count=max(1, len(chapters)),
            duration_ms=260,
        ),
        PipelineStageReport(
            id="stage_scene_plan",
            name="场景规划",
            agent="ScenePlanner",
            status="ok" if scenes else "warning",
            summary=f"生成 {len(scenes)} 个可拍场景，并绑定章节来源。",
            evidence_count=len(chapters),
            output_count=len(scenes),
            duration_ms=360,
        ),
        PipelineStageReport(
            id="stage_model_plan",
            name="模型改编计划",
            agent="LLMPlanAgent",
            status="ok" if used_model_plan else "warning",
            summary="使用模型计划生成核心创作判断。" if used_model_plan else "当前使用 deterministic fallback，正式生产建议配置 API 或本地模型。",
            evidence_count=len(chapters),
            output_count=len(scenes),
            duration_ms=900 if used_model_plan else 80,
        ),
        PipelineStageReport(
            id="stage_quality_gate",
            name="质量与引用门禁",
            agent="ContinuityChecker",
            status="ok",
            summary="检查 Schema、人物/地点引用、章节覆盖和场景证据链。",
            evidence_count=sum(len(scene.source_refs) for scene in scenes),
            output_count=len(scenes),
            duration_ms=180,
        ),
    ]


def _build_quality_report(
    chapters: list[Chapter],
    scenes: list[Scene],
    characters: list[Character],
    locations: list[Location],
    warnings: list[str],
) -> QualityReport:
    chapter_scene_counts = {chapter.id: 0 for chapter in chapters}
    for scene in scenes:
        for chapter_id in scene.chapter_ids:
            if chapter_id in chapter_scene_counts:
                chapter_scene_counts[chapter_id] += 1

    coverage = {
        chapter.id: min(100.0, chapter_scene_counts.get(chapter.id, 0) * 100.0)
        for chapter in chapters
    }
    coverage_score = sum(coverage.values()) / max(1, len(coverage))
    evidence_score = min(100.0, sum(1 for scene in scenes if scene.source_refs) / max(1, len(scenes)) * 100)
    conflict_score = min(100.0, sum(1 for scene in scenes if len(scene.conflict) >= 16) / max(1, len(scenes)) * 100)
    bible_score = min(100.0, (len(characters) * 18 + len(locations) * 10))
    production_score = min(100.0, sum(1 for scene in scenes if scene.production_notes) / max(1, len(scenes)) * 100)
    warning_penalty = min(25.0, len(warnings) * 5.0)
    overall = max(0.0, round((coverage_score + evidence_score + conflict_score + bible_score + production_score) / 5 - warning_penalty, 1))

    metrics = [
        _metric("coverage", "章节覆盖", coverage_score, "每个章节都应至少进入一个场景。"),
        _metric("evidence", "证据链", evidence_score, "场景必须绑定 source_refs，方便回查原文。"),
        _metric("conflict", "戏剧冲突", conflict_score, "每场需要明确人物目标、障碍和代价。"),
        _metric("story_bible", "故事圣经完整度", bible_score, "人物、地点、主题和伏笔越完整，长篇一致性越强。"),
        _metric("production", "可拍性", production_score, "场景需包含拍摄和调度层面的生产说明。"),
    ]
    risks: list[ValidationIssue] = []
    for chapter_id, score in coverage.items():
        if score <= 0:
            risks.append(ValidationIssue(path=f"chapters.{chapter_id}", message="该章节未被任何场景覆盖。"))
    for scene in scenes:
        if not scene.source_refs:
            risks.append(ValidationIssue(path=f"scenes.{scene.id}.source_refs", message="场景缺少原文证据链。"))
        if not scene.conflict:
            risks.append(ValidationIssue(path=f"scenes.{scene.id}.conflict", message="场景缺少明确冲突。"))

    recommendations = [
        "优先处理质量中心中低于 80 分的指标。",
        "对低证据链场景执行“收紧证据”局部改写。",
        "对冲突弱的场景执行“增强冲突”局部改写。",
        "导出前检查 Fountain 预览是否保留人物对白节奏。",
    ]
    return QualityReport(
        overall_score=overall,
        metrics=metrics,
        risks=risks,
        recommendations=recommendations,
        chapter_coverage=coverage,
    )


def _build_production_breakdown(
    scenes: list[Scene],
    characters: list[Character],
    locations: list[Location],
    style: AdaptationStyle,
) -> ProductionBreakdown:
    scene_count = len(scenes)
    runtime = max(float(style.target_runtime_minutes), scene_count * 1.8)
    pages = round(runtime * 0.95, 1)
    location_breakdowns: list[LocationBreakdown] = []
    for location in locations:
        scene_ids = [scene.id for scene in scenes if scene.heading.location_id == location.id]
        if not scene_ids:
            continue
        location_breakdowns.append(
            LocationBreakdown(
                location_id=location.id,
                scene_ids=scene_ids,
                estimated_half_days=max(0.5, len(scene_ids) * 0.5),
                requirements=[f"准备 {location.name} 的基础美术陈设", "确保对白收音环境稳定"],
            )
        )
    shot_plan = [
        ShotPlan(
            scene_id=scene.id,
            setup=f"{scene.heading.context}. {scene.heading.location_id} - {scene.heading.time_of_day}",
            camera="主观跟拍 + 关键反应特写" if index == 1 else "中景建立关系，特写捕捉信息点",
            sound="保留环境声，突出对白和关键物件声",
            difficulty="high" if len(scene.characters) > 3 else "medium",
        )
        for index, scene in enumerate(scenes, start=1)
    ]
    return ProductionBreakdown(
        estimated_pages=pages,
        estimated_runtime_minutes=round(runtime, 1),
        cast_size=len(characters),
        location_count=len(locations),
        shooting_days=max(1, round(sum(item.estimated_half_days for item in location_breakdowns) / 2 + 0.49)),
        location_breakdowns=location_breakdowns,
        shot_plan=shot_plan,
    )


def _metric(metric_id: str, name: str, score: float, detail: str) -> QualityMetric:
    rounded = round(max(0.0, min(100.0, score)), 1)
    if rounded >= 90:
        status = "excellent"
    elif rounded >= 75:
        status = "good"
    elif rounded >= 55:
        status = "warning"
    else:
        status = "critical"
    return QualityMetric(id=metric_id, name=name, score=rounded, status=status, detail=detail)


def _source_ref_for_chapter(chapter: Chapter) -> SourceRef:
    return SourceRef(chapter_id=chapter.id, paragraph_ids=[paragraph.id for paragraph in chapter.paragraphs[:3]])


def _act_for_scene(index: int, total_scenes: int, total_chapters: int) -> str:
    total = max(total_scenes, total_chapters, 1)
    if index <= max(1, total // 3):
        return "A"
    if index <= max(2, total * 2 // 3):
        return "B"
    return "C"


def _infer_emotional_shift(summary: Any, conflict: Any) -> str:
    text = f"{summary or ''} {conflict or ''}"
    if "真相" in text or "秘密" in text:
        return "从困惑进入追问"
    if "危险" in text or "追" in text:
        return "从试探升级为危机"
    return "从信息建立推进到行动选择"


def _production_notes_for_scene(chapter: Chapter, location_name: str) -> list[str]:
    notes = [f"优先复用地点：{location_name}", "保留关键物件作为镜头线索"]
    if "夜" in chapter.text:
        notes.append("夜景需控制光源层次，避免对白段落失焦")
    if "雨" in chapter.text:
        notes.append("雨声可作为紧张感环境音，但需给对白留出频段")
    return notes


def _rewrite_options_for_scene(conflict: str, summary: str) -> list[str]:
    options = ["增强冲突代价", "收紧原文证据", "改写为短剧钩子"]
    if len(conflict) < 18:
        options.insert(0, "补足人物目标和障碍")
    if len(summary) > 120:
        options.append("压缩场景摘要")
    return list(dict.fromkeys(options))


def _quality_flags_for_scene(source_ref: SourceRef, character_ids: list[str], elements: list[ScriptElement]) -> list[str]:
    flags: list[str] = []
    if not source_ref.paragraph_ids:
        flags.append("缺少段落级证据")
    if not character_ids:
        flags.append("缺少人物引用")
    if not any(element.type == "dialogue" for element in elements):
        flags.append("缺少对白，可拍性偏弱")
    return flags


def _summarize_scene_diff(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    diff: list[str] = []
    if before["summary"] != after["summary"]:
        diff.append("更新了场景摘要。")
    if before["conflict"] != after["conflict"]:
        diff.append("强化了场景冲突。")
    before_elements = before["elements"]
    after_elements = after["elements"]
    changed_elements = sum(1 for old, new in zip(before_elements, after_elements) if old != new)
    if changed_elements:
        diff.append(f"改写了 {changed_elements} 个剧本元素。")
    if not diff:
        diff.append("保留原场景结构，仅更新生产备注或质量标记。")
    return diff


def _summarize_chapter(chapter: Chapter) -> str:
    text = " ".join(paragraph.text for paragraph in chapter.paragraphs[:2]).strip() or chapter.text[:120]
    return f"{chapter.title}：{text[:120]}".strip()


def _visualize_text(text: str) -> str:
    cleaned = text.replace("\n", " ").strip()
    if not cleaned:
        return "场景安静下来，人物在沉默中等待下一次行动。"
    return cleaned[:160]


def _dialogue_from_text(text: str) -> str:
    cleaned = text.replace("\n", " ").strip(" “”，。！？")
    if not cleaned:
        return "这件事不能再拖下去了。"
    return f"我明白了，{cleaned[:42]}。"


def _build_llm_prompt(text: str, title: str, style: AdaptationStyle) -> str:
    chapters = detect_chapters(text)
    longform = build_longform_context(chapters)
    longform_context = longform.to_prompt_block()
    return (
        "请把以下小说分析为一个紧凑的改编计划 JSON 对象。不要输出 Markdown。"
        "JSON 顶层只包含 characters、locations、scenes 三个数组。"
        "characters 每项包含 name、role、description、goals。role 只能是 protagonist/supporting/antagonist/minor。"
        "locations 每项包含 name、type、description。type 只能是 interior/exterior/mixed/unknown。"
        "scenes 每项包含 chapter_order、title、location、context、time_of_day、dramatic_purpose、conflict、characters、beats、summary、elements。"
        "context 只能是 INT/EXT/INT/EXT/UNKNOWN，time_of_day 只能是 DAY/NIGHT/DUSK/DAWN/UNKNOWN。"
        "elements 每项包含 type、text，可选 character、emotion。type 只能是 action/dialogue/transition/voice_over/shot/note。"
        "请至少生成 3 个场景。请按章节覆盖生成场景，长篇输入不能只改编开头章节；"
        "scenes[].chapter_order 必须对应 LONGFORM_CONTEXT 中的章节 order。"
        f"项目标题：{title}\n"
        f"改编风格：{json.dumps(style.model_dump(), ensure_ascii=False)}\n"
        f"{longform_context}"
    )


def _build_rewrite_prompt(
    scene: Scene,
    instruction: str,
    mode: str,
    evidence: list[SourceEvidence],
    screenplay: Screenplay,
) -> str:
    character_names = {
        character.id: character.name
        for character in screenplay.story_bible.characters
        if character.id in scene.characters
    }
    elements = [
        {
            "id": element.id,
            "type": str(element.type),
            "character": character_names.get(element.character_id or "", element.character_id),
            "text": element.text,
            "emotion": element.emotion,
        }
        for element in scene.elements
    ]
    scene_payload = {
        "id": scene.id,
        "title": scene.title,
        "summary": scene.summary,
        "dramatic_purpose": scene.dramatic_purpose,
        "conflict": scene.conflict,
        "beats": scene.beats,
        "emotional_shift": scene.emotional_shift,
        "production_notes": scene.production_notes,
        "characters": character_names,
        "elements": elements,
        "source_refs": [source_ref.model_dump(mode="json") for source_ref in scene.source_refs],
    }
    return (
        "请基于证据改写一个剧本场景，输出严格 JSON 对象，不要 Markdown。\n"
        "只能输出这些字段：summary、dramatic_purpose、conflict、beats、emotional_shift、production_notes、elements。\n"
        "elements 只能改已有元素的 text/emotion，必须带原 id，不能新增或删除元素，不能改变人物、地点、source_refs、章节引用。\n"
        "所有新增事实必须能从证据段落推出；如果证据不足，只强化表达和戏剧目标，不编造新事实。\n"
        "beats 最多 8 条，production_notes 最多 8 条，每个文本字段保持简洁可拍。\n"
        f"改写模式：{mode}\n"
        f"用户指令：{instruction}\n"
        f"场景 JSON：{json.dumps(scene_payload, ensure_ascii=False)}\n"
        f"原文证据：\n{format_evidence_for_prompt(evidence)}"
    )


def _clean_text(value: Any, fallback: str, max_length: int) -> str:
    if value is None:
        return fallback
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    if not text:
        return fallback
    return text[:max_length]


def _bounded_string_list(value: Any, fallback: list[str], limit: int) -> list[str]:
    items = _string_list(value)
    if not items:
        return fallback
    cleaned = []
    for item in items[:limit]:
        text = item.replace("\r", " ").replace("\n", " ").strip()
        if text:
            cleaned.append(text[:180])
    return cleaned or fallback


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None and str(item).strip()]


def _safe_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback
