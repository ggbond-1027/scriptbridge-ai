from __future__ import annotations

from dataclasses import dataclass

from .models import Chapter


MAX_EXCERPT_CHARS = 180
MAX_SUMMARY_CHARS = 260


@dataclass(frozen=True)
class LongformChapterContext:
    order: int
    chapter_id: str
    title: str
    char_count: int
    paragraph_count: int
    summary: str
    excerpts: list[str]
    scene_guidance: str


@dataclass(frozen=True)
class LongformContext:
    chapter_count: int
    total_chars: int
    context_chars: int
    chapters: list[LongformChapterContext]

    @property
    def compression_ratio(self) -> float:
        if self.total_chars <= 0:
            return 1.0
        return round(self.context_chars / self.total_chars, 4)

    def to_prompt_block(self) -> str:
        lines = [
            "LONGFORM_CONTEXT",
            f"章节总数: {self.chapter_count}",
            f"原文字数: {self.total_chars}",
            f"压缩后上下文字数: {self.context_chars}",
            f"压缩比例: {self.compression_ratio}",
            "压缩策略: 每章保留标题、字数、段落数、首部/中部/尾部证据摘录和场景规划提示，避免只读取小说开头。",
            "章节上下文:",
        ]
        for chapter in self.chapters:
            lines.extend(
                [
                    f"[{chapter.order}] {chapter.title}",
                    f"chapter_id: {chapter.chapter_id}",
                    f"char_count: {chapter.char_count}",
                    f"paragraph_count: {chapter.paragraph_count}",
                    f"summary: {chapter.summary}",
                    "key_excerpts:",
                ]
            )
            for excerpt in chapter.excerpts:
                lines.append(f"- {excerpt}")
            lines.append(f"scene_guidance: {chapter.scene_guidance}")
        return "\n".join(lines)


def build_longform_context(chapters: list[Chapter]) -> LongformContext:
    chapter_contexts = [_build_chapter_context(chapter) for chapter in chapters]
    prompt_body = "\n".join(
        "\n".join(
            [
                context.title,
                context.summary,
                "\n".join(context.excerpts),
                context.scene_guidance,
            ]
        )
        for context in chapter_contexts
    )
    return LongformContext(
        chapter_count=len(chapters),
        total_chars=sum(len(chapter.text) for chapter in chapters),
        context_chars=len(prompt_body),
        chapters=chapter_contexts,
    )


def _build_chapter_context(chapter: Chapter) -> LongformChapterContext:
    excerpts = _chapter_excerpts(chapter)
    summary_source = " / ".join(excerpts) if excerpts else _clean(chapter.text)
    summary = _clip(f"{chapter.title}: {summary_source}", MAX_SUMMARY_CHARS)
    guidance = (
        f"围绕 {chapter.title} 规划可拍场景，保留本章关键线索、人物选择和结尾信息，"
        f"输出 scenes[].chapter_order={chapter.order} 的场景。"
    )
    return LongformChapterContext(
        order=chapter.order,
        chapter_id=chapter.id,
        title=chapter.title,
        char_count=len(chapter.text),
        paragraph_count=len(chapter.paragraphs),
        summary=summary,
        excerpts=excerpts,
        scene_guidance=guidance,
    )


def _chapter_excerpts(chapter: Chapter) -> list[str]:
    paragraph_texts = [_clean(paragraph.text) for paragraph in chapter.paragraphs if _clean(paragraph.text)]
    if paragraph_texts:
        candidates = [
            ("开头", paragraph_texts[0]),
            ("中部", paragraph_texts[len(paragraph_texts) // 2]),
            ("结尾", paragraph_texts[-1]),
        ]
    else:
        text = _clean(chapter.text)
        if not text:
            return []
        candidates = [
            ("开头", text[:MAX_EXCERPT_CHARS * 2]),
            ("中部", _window(text, len(text) // 2)),
            ("结尾", text[-MAX_EXCERPT_CHARS * 2 :]),
        ]

    excerpts: list[str] = []
    seen: set[str] = set()
    for label, text in candidates:
        clipped = _clip(text, MAX_EXCERPT_CHARS)
        if not clipped or clipped in seen:
            continue
        seen.add(clipped)
        excerpts.append(f"{label}: {clipped}")
    return excerpts


def _window(text: str, center: int) -> str:
    half = MAX_EXCERPT_CHARS
    start = max(0, center - half)
    end = min(len(text), center + half)
    return text[start:end]


def _clean(text: str) -> str:
    return " ".join(text.replace("\r", " ").replace("\n", " ").split())


def _clip(text: str, max_chars: int) -> str:
    cleaned = _clean(text)
    if len(cleaned) <= max_chars:
        return cleaned
    return f"{cleaned[: max_chars - 1]}…"
