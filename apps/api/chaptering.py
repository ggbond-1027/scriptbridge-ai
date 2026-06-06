from __future__ import annotations

import re

from .models import Chapter, SourceParagraph


CHAPTER_PATTERNS = [
    re.compile(r"^\s*(第[一二三四五六七八九十百千万零〇两0-9]+[章节回部].*)\s*$"),
    re.compile(r"^\s*(Chapter\s+\d+.*)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(#{1,3}\s+.+)\s*$"),
]


def detect_chapters(text: str) -> list[Chapter]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []

    matches: list[tuple[int, str]] = []
    offset = 0
    for line in normalized.split("\n"):
        stripped = line.strip()
        if any(pattern.match(stripped) for pattern in CHAPTER_PATTERNS):
            matches.append((offset, stripped.lstrip("#").strip()))
        offset += len(line) + 1

    if len(matches) < 2:
        return [_build_chapter("ch_001", 1, "全文", normalized)]

    chapters: list[Chapter] = []
    for index, (start, title) in enumerate(matches):
        end = matches[index + 1][0] if index + 1 < len(matches) else len(normalized)
        chunk = normalized[start:end].strip()
        lines = chunk.split("\n")
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
        chapters.append(_build_chapter(f"ch_{index + 1:03d}", index + 1, title, body))
    return chapters


def _build_chapter(chapter_id: str, order: int, title: str, text: str) -> Chapter:
    paragraphs: list[SourceParagraph] = []
    cursor = 0
    raw_parts = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not raw_parts and text.strip():
        raw_parts = [line.strip() for line in text.split("\n") if line.strip()]

    for idx, paragraph in enumerate(raw_parts, start=1):
        start = text.find(paragraph, cursor)
        if start < 0:
            start = cursor
        end = start + len(paragraph)
        cursor = end
        paragraphs.append(
            SourceParagraph(
                id=f"p_{chapter_id.split('_')[-1]}_{idx:03d}",
                chapter_id=chapter_id,
                index=idx,
                text=paragraph,
                char_start=start,
                char_end=end,
            )
        )
    return Chapter(id=chapter_id, order=order, title=title, text=text, paragraphs=paragraphs)
