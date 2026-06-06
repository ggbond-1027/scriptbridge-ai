from __future__ import annotations

import json

import yaml

from .models import Screenplay


def to_yaml(screenplay: Screenplay) -> str:
    return yaml.safe_dump(
        screenplay.model_dump(mode="json"),
        allow_unicode=True,
        sort_keys=False,
        width=100,
    )


def to_json(screenplay: Screenplay) -> str:
    return json.dumps(screenplay.model_dump(mode="json"), ensure_ascii=False, indent=2)


def to_markdown(screenplay: Screenplay) -> str:
    lines = [f"# {screenplay.project.title}", ""]
    lines.append("## 故事圣经")
    lines.append("")
    lines.append("### 人物")
    for character in screenplay.story_bible.characters:
        lines.append(f"- **{character.name}**：{character.description}")
    lines.append("")
    lines.append("### 地点")
    for location in screenplay.story_bible.locations:
        lines.append(f"- **{location.name}**：{location.description}")
    lines.append("")
    lines.append("## 剧本")
    for scene in screenplay.scenes:
        location = next(
            (item.name for item in screenplay.story_bible.locations if item.id == scene.heading.location_id),
            scene.heading.location_id,
        )
        lines.extend(
            [
                "",
                f"### {scene.heading.context}. {location} - {scene.heading.time_of_day}",
                "",
                f"**场景目的**：{scene.dramatic_purpose}",
                "",
                f"**冲突**：{scene.conflict}",
                "",
            ]
        )
        for element in scene.elements:
            if element.type == "dialogue":
                character = next(
                    (item.name for item in screenplay.story_bible.characters if item.id == element.character_id),
                    element.character_id or "角色",
                )
                lines.append(f"**{character}**：{element.text}")
            elif element.type == "transition":
                lines.append(f"> {element.text}")
            else:
                lines.append(element.text)
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def to_fountain(screenplay: Screenplay) -> str:
    lines: list[str] = []
    for scene in screenplay.scenes:
        location = next(
            (item.name for item in screenplay.story_bible.locations if item.id == scene.heading.location_id),
            scene.heading.location_id,
        )
        lines.append(f"{scene.heading.context}. {location} - {scene.heading.time_of_day}")
        lines.append("")
        for element in scene.elements:
            if element.type == "dialogue":
                character = next(
                    (item.name for item in screenplay.story_bible.characters if item.id == element.character_id),
                    element.character_id or "角色",
                )
                lines.append(character)
                if element.parenthetical:
                    lines.append(f"({element.parenthetical})")
                lines.append(element.text)
            elif element.type == "transition":
                lines.append(f"{element.text.upper()}:")
            else:
                lines.append(element.text)
            lines.append("")
    return "\n".join(lines).strip() + "\n"
