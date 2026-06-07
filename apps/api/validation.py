from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from .models import Screenplay, ValidationIssue, ValidationResult


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "screenplay.schema.json"


def validate_yaml_text(yaml_text: str) -> ValidationResult:
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        return ValidationResult(valid=False, issues=[ValidationIssue(path="$", message=f"YAML 语法错误：{exc}")])

    try:
        screenplay = Screenplay.model_validate(data)
    except ValidationError as exc:
        issues = [
            ValidationIssue(path=".".join(str(part) for part in error["loc"]), message=str(error["msg"]))
            for error in exc.errors()
        ]
        return ValidationResult(valid=False, issues=issues)
    return validate_screenplay(screenplay)


def validate_screenplay(screenplay: Screenplay) -> ValidationResult:
    issues: list[ValidationIssue] = []
    schema_issues = _validate_json_schema(screenplay.model_dump(mode="json"))
    issues.extend(schema_issues)
    issues.extend(_validate_references(screenplay))
    return ValidationResult(valid=not any(issue.severity == "error" for issue in issues), issues=issues)


def _validate_json_schema(data: dict[str, Any]) -> list[ValidationIssue]:
    if not SCHEMA_PATH.exists():
        return [ValidationIssue(path="$", message="缺少 screenplay.schema.json。", severity="warning")]
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    issues: list[ValidationIssue] = []
    for error in sorted(validator.iter_errors(data), key=lambda item: item.path):
        path = "$" + "".join(f".{part}" for part in error.path)
        issues.append(ValidationIssue(path=path, message=error.message))
    return issues


def _validate_references(screenplay: Screenplay) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    character_ids = {character.id for character in screenplay.story_bible.characters}
    location_ids = {location.id for location in screenplay.story_bible.locations}
    chapter_ids = {chapter.id for chapter in screenplay.chapters}
    paragraph_ids = {paragraph.id for chapter in screenplay.chapters for paragraph in chapter.paragraphs}

    for scene in screenplay.scenes:
        if scene.heading.location_id not in location_ids:
            issues.append(ValidationIssue(path=f"scenes.{scene.id}.heading.location_id", message="场景引用了未定义地点。"))
        for character_id in scene.characters:
            if character_id not in character_ids:
                issues.append(ValidationIssue(path=f"scenes.{scene.id}.characters", message=f"场景引用了未定义人物 {character_id}。"))
        if not scene.source_refs:
            issues.append(ValidationIssue(path=f"scenes.{scene.id}.source_refs", message="场景缺少原文来源。"))
        for source_ref in scene.source_refs:
            if source_ref.chapter_id not in chapter_ids:
                issues.append(ValidationIssue(path=f"scenes.{scene.id}.source_refs", message="来源引用了未定义章节。"))
            for paragraph_id in source_ref.paragraph_ids:
                if paragraph_id not in paragraph_ids:
                    issues.append(ValidationIssue(path=f"scenes.{scene.id}.source_refs", message=f"来源引用了未定义段落 {paragraph_id}。"))
        for element in scene.elements:
            if element.type == "dialogue" and element.character_id not in character_ids:
                issues.append(ValidationIssue(path=f"scenes.{scene.id}.elements.{element.id}", message="对白元素缺少有效角色引用。"))
    return issues
