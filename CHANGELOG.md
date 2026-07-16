# Changelog

All notable changes to this project will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Commits follow Conventional Commits.

---

## [Unreleased]

### Deferred / follow-ups (non-blocking, carried from T0.1 review)
- `tests/test_config.py` defaults test does not clear ambient env vars — add `monkeypatch.delenv` when it bites in CI (natural home: T0.3).
- `.pre-commit-config.yaml` pins ruff/mypy versions while dev deps float — sync versions when they drift during T0.3 or later.

---

## [0.1.0] — 2026-07-16

### Added — T0.1 Python scaffold (branch `ticket/T0.1-python-scaffold`, merge c51f908, feat 68bf5f1)
- `pyproject.toml` + `uv.lock`: uv-managed project, Python 3.12, dev deps (pytest, ruff, mypy, pre-commit).
- `.python-version`: pins 3.12 for uv.
- `src/bacap/__init__.py`: package root.
- `src/bacap/config.py`: `pydantic-settings` config model; reads `DWAVE_API_TOKEN` from `.env`; defaults documented.
- `tests/test_config.py`: placeholder test covering config defaults; 4 tests, all passing.
- `.pre-commit-config.yaml`: ruff (lint + format) and mypy hooks wired.
- `.env.example`: documents `DWAVE_API_TOKEN=` (sole env var at this stage).
- `README.md`: stub with quickstart commands (`uv run pytest`, `uv run ruff check .`, `uv run mypy src`).

### Verified
- `uv run pytest` — 4 passed.
- `uv run ruff check .` — clean.
- `uv run mypy src` (strict) — clean.
- `.env` confirmed gitignored.
