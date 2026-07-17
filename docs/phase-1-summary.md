# Phase 1 Summary — Instance model, generator & real-data calibration (closed 2026-07-17)

## What was built

Phase 1 produced the full instance layer in four tickets:

**T1.1 — Instance schema & loader** (merge ed113ed, feat c063491)
`Vessel` and `BacapInstance` Pydantic v2 models (frozen, `extra=forbid`). All 7 instance-level validators (V1–V7) and 3 vessel-level validators. Derived properties: `n_segments`, `length_segments`, `n_positions`, `min_duration`, `hard_departure`, `congestion_index`. `load_instance` / `save_instance` JSON (de)serialization. 28 tests.

**T1.2 — Meisel–Bierwirth benchmark import** (merge 72263cf, feat 4f5d7a8; amendment merge 7d452c7, feat 9a67b8b)
Path B regeneration (original dataset files unreachable). `regenerate_mb(size, seed)` and `regenerate_mb_set(seed)` in `src/bacap/instances/meisel_bierwirth.py`. Generation parameters transcribed from Correcher & Alvarez-Valdes EJOR-2019 (corroborating primary), Bogerd (2019) MSc, and Iris et al. (2015). After T1.2 merged, the M&B (2009) PDF was obtained and revealed a formula mis-wiring introduced by Correcher's conflated phrasing: `target_departure` was `eta + ceil(1.5×min_duration)` (wrong); corrected to `eta + min_duration` (EFT per M&B Table 1). `latest_departure` was `None`; corrected to `eta + ceil(1.5×min_duration)` (LFT, M&B §7.2 verbatim). M&B (2009) is now the primary source; Correcher is corroborating. 42 tests.

**T1.3 — Digitraffic port-call calibration** (merge 7a6a6b8, feat d56fe07)
Client for `meri.digitraffic.fi/api/port-call/v1/port-calls`. Fetched 6 months of Vuosaari calls (2026-01-18 to 2026-07-16, n=982 port calls) using 30-day date-windowed chunks (no pagination cursor exists on the real API). Fitted distributions written to `experiments/calibration/vuosaari.json`: inter-arrival exponential rate=0.227/h; vessel length lognormal mu=5.246 sigma=0.103 (median ≈190 m); service time lognormal mu=2.571 sigma=0.831 (median ≈13 h). ~30% of VUOS MMSIs are structurally absent from the live AIS snapshot; join-drop threshold relaxed from 20% to 50% (approved deviation); fitted length distribution describes the AIS-tracked ~70% subpopulation only. 16 new tests; 58 total.

**T1.4 — Instance generator** (merge 6370b9c, feats c7259bc + dcb66fe)
`generate_instance(n, congestion, seed)` in `src/bacap/instances/generator.py` sampling from T1.3 `VUOSAARI_DEFAULTS`. Minimal `bacap.cli generate` command. Reviewer (fable) required one docs-only round-trip before APPROVE: fleet-homogeneity limitation and congestion knob semantics documented in `docs/data-sources.md`. 95 tests total in repo.

## DoD status

DoD: "`bacap.cli generate` produces valid instances; benchmark instances load; arrival-pattern stats documented."

**Met.** `bacap.cli generate` produces `BacapInstance` JSON passing all T1.1 validators. Benchmark instances regenerated per M&B (2009) primary source. Arrival-pattern stats documented for n=982 Vuosaari calls in `experiments/calibration/vuosaari.json` and `docs/data-sources.md`.

## Key decisions

- **Path B regeneration for M&B benchmarks** — neither M&B (2009) nor Iris et al. (2017) dataset files were obtainable. Three independent open sources were triangulated for generation parameters. `parse_mb_file` stub included but deferred pending dataset acquisition.
- **EFT/LFT correction post-merge** — the T1.2 primary-source amendment changed the semantics of `target_departure` and `latest_departure` after T1.2 was already merged. This was handled as a versioned amendment (0.5.1) rather than a re-open/re-review of the original ticket.
- **AIS join-drop threshold** — relaxed from 20% to 50% after empirical testing showed ~30% of VUOS MMSIs are structurally absent from the live AIS snapshot. The selection-bias question (Vuosaari reality vs. AIS coverage artifact) was explicitly left unresolved; the caveat is recorded in `docs/data-sources.md`.
- **Congestion knob as target not output** — `rho` controls a placement-loop target; `congestion_index` (per T1.1 schema) is the measured output. Observed sublinear relationship (~0.30/0.43/0.53 for rho=0.3/0.5/0.7) documented.

## Deviations from spec

- T1.2: `parse_mb_file` deferred (raises `NotImplementedError`); Iris-2017 file parser not yet implemented. Spec allowed Path B as fallback; deferred Path A' per spec §4.2.
- T1.3: 30-day windowed chunking used instead of a pagination cursor (no cursor exists on the real API); approved by reviewer.
- T1.3: AIS join-drop threshold 50% vs. spec's 20%; approved by reviewer; caveat documented.
- T1.4: Generator `target_departure` / `latest_departure` semantics follow stale Phase 1 spec §4.4, diverging from the corrected T1.2 M&B semantics. This is an **open escalation** (see below), not a closed deviation.

## Open issues carried forward

### ⚠ OPEN ARCHITECT DECISIONS (must be resolved before gated tickets proceed)

**(B) EFT/LFT due-date semantic alignment — blocks T2.1**
The generator uses `target_departure = eta + ceil(1.5×min_duration)`, `latest_departure = None` (stale Phase 1 spec §4.4). The T1.2 M&B regeneration now uses `target_departure = eta + min_duration` (EFT) and `latest_departure = eta + ceil(1.5×min_duration)` (LFT per M&B §7.2). Synthetic and benchmark instances carry DIFFERENT due-date semantics. The architect must rule: align the generator to EFT/LFT, or formally accept and document the divergence. **Must be resolved before T2.1**, because T2.1's objective/penalty formulation depends on due-date semantics being well-defined across instance sources.

**(A) Wide-calibration profile decision — blocks Phase 4 experiment design**
The Vuosaari-calibrated generator produces homogeneous fleets (140–265 m, `cranes_max` ∈ {3,4}). M&B benchmarks use a 60/30/10 Small/Medium/Large class mix with `cranes_max` spanning 1–4, giving crane-assignment diversity that quantum experiments may need. The architect must decide: (a) accept homogeneous instances, (b) add a documented "synthetic-wide" calibration profile, or (c) other. **Must be resolved before Phase 4** (T4.1+). Does not block Phase 2 or Phase 3.

### Non-blocking follow-ups (no ticket, tracked in CHANGELOG.md [Unreleased])

- Obtain Iris et al. (2017) benchmark dataset files → unlocks `parse_mb_file` Path A'.
- `docs/data-sources.md`: replace "clipped" with "excluded/filtered" for the AIS join description.
- `scripts/calibrate_vuosaari.py`: surface drop-counts in stdout.
- `src/bacap/instances/calibration.py`: document or handle zero-gap ties and `portCallId=None` dedup bypass.

## What is next

Phase 2 — QUBO formulation. Spec drafted at `docs/specs/phase-2-spec.md`.

**Caution:** `docs/specs/phase-2-spec.md` was drafted before the T1.2 primary-source amendment and before T1.4's homogeneity limitation was documented. It may not be consistent with the corrected EFT/LFT semantics (open escalation B) or the fleet-homogeneity constraint (open escalation A). The architect should review `docs/specs/phase-2-spec.md` for consistency with amended T1.2 semantics **before T2.1 starts**. Starting T2.1 against a stale spec risks formulating the objective/penalty terms against incorrect due-date semantics.
