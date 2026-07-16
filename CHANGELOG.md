# Changelog

All notable changes to this project will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Commits follow Conventional Commits.

---

## [Unreleased]

### Deferred / follow-ups (open, no ticket)
- Obtain Iris et al. (2017) "BACAP_Benchmark_n60_n80" dataset files (email C. Iris) → would unlock `parse_mb_file` per amended spec Path A' and allow replacement of regenerated instances with published originals.
- `docs/data-sources.md`: replace "clipped" with "excluded" (or "filtered") when describing the vessel-length join — the implementation does not clip values, it drops rows below the threshold.
- `scripts/calibrate_vuosaari.py`: surface drop-counts (pre/post join, pre/post dedup) in script stdout so callers can see how many records were discarded without reading source.
- `src/bacap/instances/calibration.py` inter-arrival fit: zero-gap ties (two port-calls with identical ATA) are silently dropped; document or handle explicitly.
- `src/bacap/instances/calibration.py` dedup guard: `portCallId=None` records bypass the deduplification set and could produce duplicates; add a guard or log a warning.

---

## [0.6.0] — 2026-07-17

### Added — T1.3 Digitraffic port-call calibration (branch `ticket/T1.3-digitraffic-calibration`, merge 7a6a6b8, feat d56fe07)

Third Phase 1 ticket. Produces fitted arrival-pattern and vessel-dimension distributions for the Vuosaari terminal, calibrated against 6 months of live Digitraffic data (2026-01-18 to 2026-07-16, n=982 port calls).

**API reality (step-0 verification against live Digitraffic swagger):**
- Endpoint: `GET /api/port-call/v1/port-calls`; params: `locode`, `ataFrom`, `ataTo`.
- ATA/ATD live in `portAreaDetails[]` (not top-level); `portAreaCode=VUOS` confirmed for Vuosaari.
- AIS vessel length = `referencePointA + referencePointB`.
- **No pagination cursor** — the spec assumed one. Client instead issues 30-day date-windowed chunks and deduplicates by `portCallId`. This is a spec deviation but matches the actual API contract; the chunking strategy produces the same coverage.

**Fitted parameters (real output, `experiments/calibration/vuosaari.json`):**
- Inter-arrival: exponential, rate=0.227/h.
- Vessel length: lognormal, mu=5.246, sigma=0.103 (median ≈190 m).
- Service time: lognormal, mu=2.571, sigma=0.831 (median ≈13 h).

**Spec deviations (both approved by reviewer, fable):**
1. Join-drop-raise threshold relaxed from 20% to 50%: ~30% of VUOS MMSIs are structurally absent from the live AIS snapshot across all tested date windows; raising to 20% would always abort. Fitted length distribution describes only the AIS-tracked ~70% subpopulation; caveat recorded in `docs/data-sources.md`.
2. Retry semantics: implemented as initial attempt + 3 retries (4 total), consuming backoffs of 1/2/4 s. Spec prose was ambiguous on the count; this reading is standard and was accepted.

**Reviewer verification (fable — independent MLE recomputation):**
Reviewer ran a separate script (no bacap imports) recomputing all three MLE fits from raw fixture data; got exact matches on rate, mu, sigma for all distributions. Verified no test circularity (fixture generation script and test fixtures are independent). 58 tests total in repo (16 new for T1.3); ruff clean; mypy (strict) clean. Verdict: APPROVE, zero blocking findings, 4 non-blocking nits (logged in Unreleased deferred above).

**Files added/changed:**
- `src/bacap/instances/calibration.py`: `ArrivalCalibration` Pydantic model; `fetch_port_calls`, `fetch_vessel_dimensions`, `fit_calibration`, `load_calibration`.
- `scripts/calibrate_vuosaari.py`: end-to-end script that fetches, fits, and writes `experiments/calibration/vuosaari.json`.
- `scripts/record_digitraffic_fixtures.py`: records hand-built test fixtures (≤50 records each) to `tests/fixtures/digitraffic/`.
- `tests/instances/test_calibration.py`: 16 new tests (client against fixtures, fit correctness, serialization round-trip).
- `tests/fixtures/digitraffic/*.json`: hand-built fixtures; no real personal data.
- `experiments/calibration/vuosaari.json`: real fitted output (committed).
- `docs/figures/vuosaari-calibration.png`: distribution plots.
- `docs/data-sources.md`: CC BY 4.0 attribution for Digitraffic (Fintraffic); AIS join-drop caveat; API reality notes.
- `pyproject.toml`: `httpx` added as runtime dep; `matplotlib` added as dev dep.

---

## [0.5.1] — 2026-07-16

### Fixed — T1.2 amendment: EFT/LFT formula correction (commits 9a67b8b feat, 7d452c7 merge)

Primary source M&B (2009) was obtained after T1.2 merged, revealing a formula mis-wiring introduced by following Correcher's (2019) conflated phrasing of the due-date rule.

**What was wrong:** `target_departure` was set to `eta + ceil(1.5 × min_duration)` and `latest_departure` was `None`. Correcher describes the due date as "desired departure = a_i + 1.5 × min handling time", which conflates M&B's LFT (hard deadline) with the soft due date.

**What M&B (2009) actually says:** §7.2 verbatim — "The latest finishing time LFT of a vessel is derived by adding 1.5 times a vessel's minimum handling time to ETA_i." The EFT (earliest finishing time / soft due date) is not stated in §7.2 prose; it is inferred arithmetically from the worked example Table 1 (p.6): vessel 3 has m=5, r_max=3, so min_duration=ceil(5/3)=2, ETA=4, EFT=6=4+2, i.e. `eta + min_duration`.

**Changes:**
- `src/bacap/instances/meisel_bierwirth.py`: `target_departure = eta + min_duration` (EFT); `latest_departure = eta + ceil(1.5 × min_duration)` (LFT, verbatim rule).
- `docs/data-sources.md`: primary source updated to M&B (2009) local PDF; Correcher demoted to corroborating with an explanatory note about the conflation; "latest_departure unavailable" deviation removed; new deviation "EFT rule not stated in prose" added; amendment note appended to deviation list.
- **Provenance impact:** all previously regenerated instances have incorrect `target_departure` / `latest_departure` values. Re-run `regenerate_mb_set(seed)` to obtain corrected instances.

**Reviewer verification (opus):** independently re-extracted §7.2 text from the PDF, confirmed verbatim LFT quote, checked EFT inference against two table rows (vessels 1 and 3), caught a worst-case-LFT bound error in the ticket brief (Medium class: 188, not 185). Verdict: APPROVE, no blocking findings. 42 tests green; `uv run ruff check .` clean; `uv run mypy src` (strict) clean.

---

## [0.5.0] — 2026-07-16

### Added — T1.2 Meisel–Bierwirth benchmark import (branch `ticket/T1.2-mb-regeneration`, merge 72263cf, feat 4f5d7a8)
Second Phase 1 ticket. Implements M&B benchmark instances via **Path B regeneration** (amended spec §4.2); neither the original M&B (2009) dataset files nor the Iris et al. (2017) dataset were obtainable.

- `src/bacap/instances/meisel_bierwirth.py`: `regenerate_mb(size, seed)` and `regenerate_mb_set(seed)` producing `BacapInstance` objects marked `source="meisel_bierwirth_regenerated"`. Generation parameters transcribed from three independent open sources: Correcher & Alvarez-Valdes EJOR-2019 preprint §7.1 pp.22–23 ("GenMB-10m", **primary**), corroborated by Bogerd (2019) MSc thesis Appendix Table 1 and Iris et al. (2015) §5.1. `parse_mb_file` stub included but deferred (raises `NotImplementedError` with acquisition guidance).
- `tests/instances/test_mb.py`: 13 tests covering regeneration determinism (byte-identical across processes), set composition, instance validity per T1.1 schema, and size variants.
- `docs/data-sources.md`: rewritten with full provenance, citations, and documented deviations for all three corroborating sources.
- `.gitignore`: added `docs/data/` and `Bogerd.pdf` — copyrighted source PDFs kept local, never committed.

### Verified (reviewer, fable — transcription-fidelity audit)
- Reviewer independently re-extracted every constant from source PDFs and verified symbol-for-symbol against implementation.
- 41 tests passed (28 schema + 13 MB); determinism confirmed byte-identical across processes.
- `uv run ruff check .` — clean. `uv run mypy src` (strict) — clean.
- Verdict: APPROVE, zero blocking findings.

---

## [0.4.0] — 2026-07-16
- `tests/test_config.py` defaults test does not clear ambient env vars — add `monkeypatch.delenv` when it bites in CI.
- `.pre-commit-config.yaml` pins ruff/mypy versions while dev deps float — sync versions when they drift.
- `tests/instances/test_schema.py`: test named `test_congestion_index_zero_span_raises` actually asserts the non-raising path — rename to `test_congestion_index_single_vessel_span_positive` when touching that file.
- `src/bacap/instances/schema.py`: `congestion_index` docstring describes the T_span==0 guard as "single instantaneous vessel", which is unreachable under V1/V3 validation — reword to mark the guard as defensive/unreachable.
- One V5 test fixture in `tests/instances/test_schema.py` also violates V6; it passes only because V5 is checked first (validator-order-dependent, harmless) — add a comment if that fixture is touched again.

---

## [0.4.0] — 2026-07-16

### Added — T1.1 Instance schema & loader (branch `ticket/T1.1-instance-schema`, merge ed113ed, feat c063491)
First Phase 1 ticket. Implements the artifact-contract instance schema per `docs/specs/phase-1-spec.md` §3.1.

- `src/bacap/instances/schema.py`: `Vessel` and `BacapInstance` Pydantic v2 models; frozen, `extra=forbid`. All 7 instance-level validators (V1–V7) and 3 vessel-level validators enforced. Derived properties: `n_segments`, `length_segments`, `n_positions`, `min_duration`, `hard_departure`. `load_instance` / `save_instance` for JSON (de)serialization. `congestion_index` per spec D5.
- `src/bacap/instances/__init__.py`: re-exports `Vessel`, `BacapInstance`, `load_instance`, `save_instance`.
- `tests/instances/test_schema.py`: 28 tests (round-trip serialization, all V1–V7 + vessel-level validators, derived properties, `congestion_index`, adversarial probes).

### Verified (reviewer, fable — symbol-for-symbol spec conformance)
- 28 tests + 16 adversarial probes — all passed.
- `uv run ruff check .` — clean.
- `uv run mypy src` (strict) — clean.
- QA checklist §3 (schema contract) — PASS. Verdict: APPROVE.

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
