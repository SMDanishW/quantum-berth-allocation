# Phase 0 Summary — Scaffolding (closed 2026-07-16)

## What was built

Phase 0 established the full repo skeleton in three tickets:

**T0.1 — Python scaffold** (merge c51f908, feat 68bf5f1)
uv-managed project, Python 3.12, `src/bacap/` package, pydantic-settings config reading `DWAVE_API_TOKEN`, pytest/ruff/mypy wired, pre-commit hooks, `.env.example`.

**T0.2 — Next.js scaffold** (merge 782a413, feat 84947da)
Next.js 15 App Router in TypeScript under `web/`. Deps: react-three-fiber 9, drei 10, zustand 5, zod 4, Tailwind v4. Vitest and Playwright harnesses wired.

**T0.3 — CI + repo hygiene** (merge 5527814, feats 317b1af + aeee16e)
GitHub Actions CI with two jobs (Python: ruff/mypy/pytest via astral-sh/setup-uv; web: lint/typecheck/test via pnpm/action-setup). MIT LICENSE. `.gitattributes` LF normalization. `docs/data-sources.md` stub. Also folded deferred hygiene items from T0.1/T0.2 reviews: real layout.tsx metadata title, pruned 5 unused create-next-app SVGs, web/README.md project description.

## DoD status

DoD: "clean clone → `uv run pytest` and `cd web && pnpm test` pass in CI."

Code-complete and locally green. Reviewer confirmed all checks pass (4 pytest, ruff clean, mypy clean, pnpm lint/typecheck/test clean). CI YAML is valid. Full CI-green verification is pending the repo owner's push to origin/main — no remote push has been made yet (owner holding for manual review).

## Key decisions

- pnpm/action-setup in CI required `packageManager: "pnpm@10.30.3"` in `web/package.json`; without it the action cannot resolve the pnpm version. Caught on first reviewer pass, fixed before APPROVE.
- Next.js 15 pinned explicitly; create-next-app pulled Next 16 by default (outside stack spec).
- Git tag named `main` noted in T0.2 review as an ambiguous refname concern. Resolved: the user confirmed the remote is `origin`; the tag conflict did not recur after hygiene pass. Removed from open follow-ups.

## Deviations from spec

None. All T0 acceptance criteria met as written.

## Open issues carried forward

- `tests/test_config.py` defaults test does not isolate ambient env vars (`monkeypatch.delenv` not yet added) — may produce false failures in CI if env is polluted.
- `.pre-commit-config.yaml` ruff/mypy version pins will drift as dev deps float — sync needed when versions diverge.

## What is next

Phase 1 — Instance model, generator & real-data calibration. Spec at `docs/specs/phase-1-spec.md`. First ticket: T1.1 (Instance schema & loader).
