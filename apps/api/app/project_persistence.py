"""SQLite persistence for the current project-scoped demo runtime.

The active API keeps complete project state in memory. This module stores a
sanitized JSON snapshot per project so local restarts do not drop work.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

SENSITIVE_KEY_PARTS = ("api_key", "apikey", "token", "secret", "password", "private_key")


def _default_db_path() -> Path:
    configured = os.getenv("NOVELSCRIPTER_PROJECT_DB", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    api_root = Path(__file__).resolve().parents[1]
    return api_root / "data" / "novelscripter_projects.sqlite3"


DB_PATH = _default_db_path()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_project_db() -> None:
    """Create the local snapshot table if needed."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS project_snapshots (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT '',
                payload TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_project_snapshots_updated_at "
            "ON project_snapshots(updated_at)"
        )


def _sanitize_for_storage(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in SENSITIVE_KEY_PARTS):
                continue
            sanitized[key] = _sanitize_for_storage(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_for_storage(item) for item in value]
    return value


def sanitize_project(project: Dict[str, Any]) -> Dict[str, Any]:
    """Return a deep copied project snapshot with secrets removed."""
    snapshot = _sanitize_for_storage(copy.deepcopy(project))
    snapshot.pop("_model_config", None)
    return snapshot


def save_project_snapshot(project: Dict[str, Any]) -> None:
    """Persist one project snapshot.

    Persistence failures should not break the editing flow, so callers can use
    this in hot paths without wrapping every API handler in database errors.
    """
    project_id = project.get("id")
    if not project_id:
        return

    try:
        init_project_db()
        snapshot = sanitize_project(project)
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        snapshot.setdefault("created_at", now)
        snapshot["updated_at"] = now
        payload = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))

        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO project_snapshots
                    (id, title, status, created_at, updated_at, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    status = excluded.status,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    payload = excluded.payload
                """,
                (
                    project_id,
                    snapshot.get("title") or snapshot.get("name") or "",
                    snapshot.get("status") or "",
                    snapshot.get("created_at") or "",
                    snapshot.get("updated_at") or now,
                    payload,
                ),
            )
    except Exception as exc:
        logger.warning("Failed to save project snapshot %s: %s", project_id, exc)


def delete_project_snapshot(project_id: str) -> None:
    try:
        init_project_db()
        with _connect() as conn:
            conn.execute("DELETE FROM project_snapshots WHERE id = ?", (project_id,))
    except Exception as exc:
        logger.warning("Failed to delete project snapshot %s: %s", project_id, exc)


def load_project_snapshots() -> Dict[str, Dict[str, Any]]:
    """Load all persisted project snapshots keyed by project id."""
    init_project_db()
    projects: Dict[str, Dict[str, Any]] = {}
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, payload FROM project_snapshots ORDER BY updated_at DESC"
        ).fetchall()

    for project_id, payload in rows:
        try:
            project = json.loads(payload)
            if not isinstance(project, dict):
                continue
            project["id"] = project.get("id") or project_id
            project.setdefault("chapters", [])
            project.setdefault("scenes", [])
            project.setdefault("story_bible", {"characters": [], "locations": [], "timeline": []})
            project.setdefault("source_paragraphs", {})
            project.setdefault("validation_errors", [])
            if "dialogue_style" in project and "_dialogue_style" not in project:
                project["_dialogue_style"] = project.get("dialogue_style")
            projects[project["id"]] = project
        except Exception as exc:
            logger.warning("Skipping invalid project snapshot %s: %s", project_id, exc)
    return projects
