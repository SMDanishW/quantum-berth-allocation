# Changelog

All notable changes to this project will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Commits follow Conventional Commits.

---

## [Unreleased]

### Deferred / follow-ups (non-blocking, carried from T0.1 review)
- `tests/test_config.py` defaults test does not clear ambient env vars — add `monkeypatch.delenv` when it bites in CI (natural home: T0.3).
- `.pre-commit-config.yaml` pins ruff/mypy versions while dev deps float — sync versions when they drift during T0.3 or later.

### Deferred / follow-ups (non-blocking, carried from T0.2 review)
- `web/src/app/layout.tsx` metadata title still reads "Create Next App" — set project title to the actual project name.
- `web/public/` contains leftover create-next-app default SVGs (file/globe/next/vercel/window.svg) — unused, prune when convenient.
- `web/README.md` is unmodified create-next-app boilerplate — replace with project-specific content.
- A `.gitattributes` for LF/CRLF normalization is worth adding in T0.3; Windows `autocrlf` produces commit warnings on this repo.
- A git tag named `main` collides with the branch name (ambiguous refname warning on `git checkout main`) — repo-hygiene item, resolve in T0.3.

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
