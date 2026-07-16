# Changelog

All notable changes to this project will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Commits follow Conventional Commits.

---

## [Unreleased]

### Deferred / follow-ups (open, carried forward to Phase 1)
- `tests/test_config.py` defaults test does not clear ambient env vars — add `monkeypatch.delenv` when it bites in CI.
- `.pre-commit-config.yaml` pins ruff/mypy versions while dev deps float — sync versions when they drift.

---

## Phase 0 — Scaffolding (closed 2026-07-16)

All three Phase 0 tickets (T0.1, T0.2, T0.3) are DONE. The DoD ("clean clone → `uv run pytest` and `cd web && pnpm test` pass in CI") is code-complete and locally green (reviewer confirmed: uv run pytest 4 passed, ruff clean, mypy clean, pnpm lint/typecheck/test clean). Full CI-green verification is pending the repo owner's push to origin/main — no push has been made yet; the owner is holding for manual review before any remote push.

Phase 1 (Instance model, generator & real-data calibration) is next. Spec approved at `docs/specs/phase-1-spec.md`. First open ticket: T1.1 (Instance schema & loader).

---

## [0.3.0] — 2026-07-16

### Added — T0.3 CI + repo hygiene (branch `ticket/T0.3-ci-hygiene`, merge 5527814, feats 317b1af + aeee16e)
- `.github/workflows/ci.yml`: two jobs — Python (ruff check, mypy, pytest via `astral-sh/setup-uv`); web (pnpm lint, typecheck, vitest via `pnpm/action-setup`).
- `LICENSE`: MIT.
- `docs/data-sources.md`: stub for data provenance tracking.
- `.gitattributes`: LF normalization baseline; resolves Windows autocrlf commit warnings.

### Changed — hygiene items deferred from T0.1/T0.2 reviews
- `web/src/app/layout.tsx`: metadata title set to actual project name (was "Create Next App").
- `web/README.md`: replaced create-next-app boilerplate with project-specific description.
- `web/package.json`: added `packageManager: "pnpm@10.30.3"` — required by `pnpm/action-setup` in CI (action could not resolve pnpm version without explicit declaration; caught in first review round).

### Removed
- `web/public/`: pruned 5 unused create-next-app default SVGs (file, globe, next, vercel, window).

### Verified (reviewer, post-fix round)
- `uv run pytest` — 4 passed.
- `uv run ruff check .` — clean.
- `uv run mypy src` (strict) — clean.
- `pnpm lint` — clean.
- `pnpm typecheck` — clean.
- `pnpm test` (vitest) — clean.
- CI YAML validated.
- QA checklist §1/§2/§3/§7 — all PASS. Verdict: APPROVE.

---

## [0.2.0] — 2026-07-16

### Added — T0.2 Next.js scaffold (branch `ticket/T0.2-nextjs-scaffold`, merge 782a413, feat 84947da)
- `web/`: Next.js 15.5.20 App Router project in TypeScript. Note: `create-next-app` initially pulled Next 16; pinned back to 15 per CLAUDE.md stack constraint.
- `web/package.json`: pnpm workspace; deps include `@react-three/fiber` 9, `@react-three/drei` 10, `zustand` 5, `zod` 4, Tailwind v4.
- `web/src/app/page.tsx` + `layout.tsx`: placeholder route; renders under `pnpm dev`.
- `web/vitest.config.ts` + example test: vitest wired; 1 test passing.
- `web/playwright.config.ts`: Playwright e2e harness wired (no tests yet).
- `web/public/artifacts/.gitkeep`: artifacts directory created empty, ready to receive solution JSON from solvers.
- `web/tailwind.config.ts`: Tailwind v4 config.

### Verified
- `pnpm install --frozen-lockfile` — clean.
- `pnpm lint` — clean.
- `pnpm typecheck` (`tsc --noEmit`) — clean.
- `pnpm test` (vitest) — 1 passed.
- `pnpm build` — prerenders placeholder route.

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
