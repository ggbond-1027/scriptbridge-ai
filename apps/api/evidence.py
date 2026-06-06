from __future__ import annotations

import re
from collections import Counter

from .models import Chapter, Scene, SourceEvidence, SourceParagraph
from .storage import search_project_evidence


STOPWORDS = {
    "一个",
    "他们",
    "我们",
    "你们",
    "自己",
    "没有",
    "已经",
    "因为",
    "所以",
    "但是",
    "只是",
    "这个",
    "那个",
    "这里",
    "那里",
}


def retrieve_scene_evidence(
    chapters: list[Chapter],
    scene: Scene,
    instruction: str = "",
    limit: int = 8,
    neighbor_window: int = 1,
    project_id: str | None = None,
) -> list[SourceEvidence]:
    """Collect source paragraphs that can constrain a scene rewrite."""
    chapter_by_id = {chapter.id: chapter for chapter in chapters}
    paragraph_by_id = {
        paragraph.id: (chapter, paragraph)
        for chapter in chapters
        for paragraph in chapter.paragraphs
    }
    selected: dict[str, SourceEvidence] = {}

    if project_id:
        query = _query_for_scene(scene, instruction)
        for item in search_project_evidence(project_id, query, limit=limit):
            _put_evidence_item(selected, item)

    for source_ref in scene.source_refs:
        chapter = chapter_by_id.get(source_ref.chapter_id)
        if not chapter:
            continue
        for paragraph_id in source_ref.paragraph_ids:
            pair = paragraph_by_id.get(paragraph_id)
            if not pair:
                continue
            _, paragraph = pair
            _put_evidence(selected, chapter, paragraph, "场景 source_refs 直接引用", 100.0)
            for neighbor in _neighbor_paragraphs(chapter, paragraph.index, neighbor_window):
                _put_evidence(selected, chapter, neighbor, "相邻上下文", 72.0)

    keywords = _keywords_for_scene(scene, instruction)
    if keywords:
        for chapter in chapters:
            for paragraph in chapter.paragraphs:
                score = _keyword_score(paragraph.text, keywords)
                if score > 0:
                    _put_evidence(selected, chapter, paragraph, "关键词命中", 48.0 + score)

    ranked = sorted(selected.values(), key=lambda item: (-item.score, item.chapter_id, item.paragraph_index))
    return ranked[:limit]


def format_evidence_for_prompt(evidence: list[SourceEvidence]) -> str:
    if not evidence:
        return "无可用原文证据。"
    lines = []
    for item in evidence:
        lines.append(
            f"[{item.id}] {item.chapter_title} / 第 {item.paragraph_index} 段 / {item.reason}\n{item.text}"
        )
    return "\n\n".join(lines)


def _put_evidence(
    selected: dict[str, SourceEvidence],
    chapter: Chapter,
    paragraph: SourceParagraph,
    reason: str,
    score: float,
) -> None:
    existing = selected.get(paragraph.id)
    if existing and existing.score >= score:
        return
    selected[paragraph.id] = SourceEvidence(
        id=f"{chapter.id}:{paragraph.id}",
        chapter_id=chapter.id,
        chapter_title=chapter.title,
        paragraph_id=paragraph.id,
        paragraph_index=paragraph.index,
        text=paragraph.text,
        reason=reason,
        score=round(score, 1),
    )


def _put_evidence_item(selected: dict[str, SourceEvidence], item: SourceEvidence) -> None:
    existing = selected.get(item.paragraph_id)
    if existing and existing.score >= item.score:
        return
    selected[item.paragraph_id] = item


def _neighbor_paragraphs(chapter: Chapter, paragraph_index: int, window: int) -> list[SourceParagraph]:
    wanted = set(range(max(1, paragraph_index - window), paragraph_index + window + 1))
    return [paragraph for paragraph in chapter.paragraphs if paragraph.index in wanted and paragraph.index != paragraph_index]


def _keywords_for_scene(scene: Scene, instruction: str) -> list[str]:
    return _keywords_from_text(_query_for_scene(scene, instruction))


def _query_for_scene(scene: Scene, instruction: str) -> str:
    text = " ".join(
        [
            scene.title,
            scene.summary,
            scene.conflict,
            scene.dramatic_purpose,
            instruction,
            " ".join(scene.beats),
            " ".join(element.text for element in scene.elements),
        ]
    )
    return text


def _keywords_from_text(text: str) -> list[str]:
    tokens = re.findall(r"[\u4e00-\u9fa5]{2,6}|[A-Za-z][A-Za-z0-9_'-]{2,}", text)
    counter = Counter(token for token in tokens if token not in STOPWORDS)
    return [token for token, _ in counter.most_common(12)]


def _keyword_score(text: str, keywords: list[str]) -> float:
    hits = sum(1 for keyword in keywords if keyword and keyword in text)
    return min(32.0, hits * 6.0)
