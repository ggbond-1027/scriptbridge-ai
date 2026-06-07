# Project Memory

## 2026-06-06 Validation

- Cleaned regenerated local residue only: pytest cache, UI check screenshots, Next build cache, Python `__pycache__`, Codex run logs, and old UI screenshots.
- Kept `.scriptbridge_data/` because it can contain user project/runtime data.
- Verification passed with `npm run test`: 79 backend tests, YAML editor static check, model profile static check, and Next production build.
- Targeted evidence verification passed with `python -m pytest apps/api/tests/test_pipeline.py -q -k "evidence_index_search or vector_evidence"`: 2 passed.
- Real runtime model validation passed through the model profile API and through generation/rewrite flows using an OpenAI-compatible API profile. The runtime key and base URL were not written to repo files.
- Real model generation/rewrite validation produced `provider_status=ok`, 3 scenes, valid YAML, and a valid rewritten scene preserving the scene id.
- Governance validation passed for project creation, inline generation job, versions, readiness, markdown export, approval submit/approve, delivery package creation, queue status, and empty dead-letter queue.
- Import validation passed for direct import, queued import in inline mode, import history, generation from imported project, and chunked import session completion.
- Browser validation passed on local production preview with the frontend running on an allowed CORS origin and the API on `127.0.0.1:8000`: the app rendered on desktop/mobile, loaded capabilities/projects/system/queue data, and the model connection button showed a successful connection test.
- Browser pitfall: backend default CORS permits local frontend origins on ports 3000, 3010, and 3011. Testing from ad-hoc ports such as 3090 requires `APP_CORS_ORIGINS`; otherwise browser preflight can fail even when backend/model calls work directly.
- Sensitive scan after validation found no runtime key, runtime base URL, or generic `sk-...` key pattern persisted in project files, excluding ignored runtime data and dependencies.

## 2026-06-06 Local Single-User Mode

- User confirmed this local web workbench should not block core actions with multi-role switching. Default behavior is now local single-user: current user is treated as the project owner for generation, batch rewrite, export, approval, delivery packages, job retry/cancel, and version restore.
- Backend keeps RBAC/session foundations for future enterprise mode, but only enforces role permissions when `AUTH_MODE=strict-rbac` (also accepts `rbac` or `enterprise`). Default `AUTH_MODE` is `local-single-user`.
- Frontend defaults to `项目负责人`, shows `本地全权限` / `本地项目模式`, and no longer exposes member identity switching or member-add controls in the main project inspector.
- Verification passed with `npm run test`: 80 backend tests, YAML editor static check, model profile static check, and Next production build.
- Added regression coverage proving default local mode allows a reviewer actor to start batch rewrite, while strict RBAC tests still cover permission blocking behavior.
- After frontend HMR produced the known `__webpack_modules__[moduleId] is not a function` dev-cache issue, cleaned `apps/web/.next` and restarted the 3011 dev server. Browser reopened successfully on `http://127.0.0.1:3011`.
