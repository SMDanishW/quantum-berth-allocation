# TICKETS — Berth Allocation & Quay Crane Scheduling

Status values: TODO / IN-PROGRESS / IN-REVIEW / DONE. `[P]` = parallel-safe within phase. `[HW]` = consumes quantum-hardware budget. Scribe updates statuses; nobody else.

---

## Phase 0 — Scaffolding
**DoD:** clean clone → `uv run pytest` and `cd web && pnpm test` pass in CI; agents/checklist in place.

- **T0.1 — Python scaffold** · DONE · merged 2026-07-16 · branch ticket/T0.1-python-scaffold (merge commit c51f908, feature commit 68bf5f1)
  uv project, `src/bacap/` package, pytest/ruff/mypy configured, pre-commit hooks, `.env.example` (`DWAVE_API_TOKEN=`), config module.
  *AC:* `uv run pytest` green on a placeholder test; lint/type clean; `.env` gitignored.
- **T0.2 [P] — Next.js scaffold** · DONE · merged 2026-07-16 · branch ticket/T0.2-nextjs-scaffold (merge commit 782a413, feature commit 84947da)
  Next.js 15 TS app in `web/`, Tailwind, r3f+drei+zustand+zod installed, vitest + Playwright wired.
  *AC:* `pnpm dev` renders placeholder; lint/typecheck/test green.
- **T0.3 [P] — CI + repo hygiene** · DONE · merged 2026-07-16 · branch ticket/T0.3-ci-hygiene (merge commit 5527814, feature commits 317b1af + aeee16e)
  GitHub Actions: Python lint+type+test job, web lint+type+test job. LICENSE, README stub, docs/ skeleton. Also folded: layout.tsx metadata title, pruned 5 unused create-next-app SVGs, web/README.md project description, .gitattributes LF normalization. pnpm/action-setup version pin fixed via `packageManager: "pnpm@10.30.3"` in web/package.json after first review round-trip.
  *AC:* CI green on main.

## Phase 1 — Instance model, generator & real-data calibration
**DoD:** `bacap.cli generate` produces valid instances; benchmark instances load; arrival-pattern stats documented.

- **T1.1 — Instance schema & loader** · DONE · merged 2026-07-16 · branch ticket/T1.1-instance-schema (merge commit ed113ed, feature commit c063491)
  Pydantic models for instance (quay, horizon, time step, cranes, vessels); JSON (de)serialization; validation rules (vessel fits quay, ETA in horizon).
  *AC:* round-trip serialization test; 5+ validation-failure tests.
- **T1.2 — Meisel–Bierwirth benchmark import** · TODO
  Locate the published BACAP instance files, write parser → our schema, document provenance/citation in docs/data-sources.md. If originals unreachable, implement the paper's generation procedure and mark instances "regenerated per M&B (2009)".
  *AC:* ≥1 instance set parsed; parser tests; provenance documented.
- **T1.3 [P] — Digitraffic port-call calibration** · TODO
  Client for `meri.digitraffic.fi/api/port-call/v1/port-calls` (timeout, retry, rate-limit friendly); pull recent Vuosaari calls; extract arrival-interval + vessel-size distributions; store fitted parameters (no raw-data commit).
  *AC:* fitted distributions serialized + plotted; API client tested against recorded fixtures; CC BY 4.0 attribution added.
- **T1.4 — Instance generator** · TODO
  Generator sampling from T1.3 distributions, configurable (n vessels, congestion level, seed).
  *AC:* seeded determinism test; generated instances pass T1.1 validation; congestion knob measurably shifts overlap pressure.

## Phase 2 — QUBO formulation
**DoD:** written formulation in docs/specs matches code symbol-for-symbol; feasibility checker is the single truth for constraints.

- **T2.1 — Formulation spec (architect-led)** · TODO
  Decision-variable encoding x_{v,b,t} on berth-time grid; objective (weighted stay + tardiness); penalties: one-berthing-per-vessel, spatial non-overlap, crane capacity, time windows. Variable-count table for N=5..20 vessels.
  *AC:* spec merged to docs/specs/phase-2-spec.md with explicit math; risk section covers penalty-weight balance.
- **T2.2 — QUBO encoder** · TODO
  `build_qubo(instance, weights) -> (BQM, var_map, penalty_report)` per spec.
  *AC:* unit tests on 2–3-vessel toy instances where the optimum is known by enumeration; brute-force check that ground state = optimal feasible schedule.
- **T2.3 — Decoder + feasibility checker** · TODO
  Sample → schedule decoding; `check_feasibility` covering every constraint independently of the QUBO (no shared code paths).
  *AC:* adversarial tests (overlapping schedules, over-capacity cranes) all caught; property test: any feasible-checker-passing schedule violates no constraint by construction.

## Phase 3 — Solvers & baselines
**DoD:** all five solvers runnable via CLI on any instance, emitting the artifact JSON.

- **T3.1 — Simulated annealing solver** · TODO (dwave-neal, sweep/beta config, multi-read best-of)
  *AC:* solves 8-vessel instance to feasibility ≥95% of seeds; artifact JSON valid per zod schema.
- **T3.2 [P] — MILP baseline** · TODO (OR-Tools CP-SAT model of the same discrete problem; time-limited)
  *AC:* proves optimality on toy instances; matches brute force; artifact export.
- **T3.3 [P] — Greedy heuristic baseline** · TODO (FCFS + best-fit berth + proportional cranes)
  *AC:* always feasible; artifact export; documented as lower bar.
- **T3.4 — QAOA solver (simulator)** · TODO (Qiskit Aer; p=1..3; COBYLA; QUBO→Ising; ≤~25 qubits guard)
  *AC:* recovers optimum on toy instance; qubit-count guard raises cleanly; transpile depth logged.
- **T3.5 [HW] — D-Wave QPU runs** · TODO (LeapHybrid + direct QPU with embedding stats; behind BACAP_USE_QPU)
  *AC:* budget printout before submit; chain-break stats logged; results land in experiment log.

## Phase 4 — Experiments
**DoD:** penalty-tuning + scaling studies reproducible from committed configs; docs/experiments.md is thesis-ready.

- **T4.1 — Experiment runner** · TODO (config-driven: instance set × solver × seeds; parquet results; resumable)
  *AC:* one command reruns a study end-to-end.
- **T4.2 — Penalty-weight study** · TODO (grid/adaptive search; feasibility-rate + objective-gap vs weights)
  *AC:* plots + recommended weights per instance size; written analysis.
- **T4.3 — Scaling study** · TODO (N=5..20 vessels: solution quality gap vs MILP, time-to-solution, feasibility rate per solver)
  *AC:* the headline thesis figure (quality vs size per solver) generated by script, seeds logged.

## Phase 5 — Digital twin frontend
**DoD:** Vercel-deployed demo replaying any artifact; side-by-side comparison works; Playwright suite green.

- **T5.1 — Artifact schema (zod) + loader** · TODO (mirror of Python schema; loud failure on invalid artifact; sample artifacts in web/public/artifacts/)
  *AC:* schema tests incl. malformed artifacts; Python→zod round-trip test in CI.
- **T5.2 — Sim clock & playback store** · TODO (zustand: play/pause/speed/scrub; keyframe derivation from schedule)
  *AC:* unit tests on keyframe math (arrival→berth→depart interpolation); scrubbing is deterministic.
- **T5.3 — 3D port scene** · TODO (r3f isometric: quay strip, water, anchorage; vessels scaled to length; cranes on rail; load frontend-design skill)
  *AC:* 60fps with 20 vessels on mid-range laptop; vessels/cranes positioned per artifact at any t.
- **T5.4 — Gantt strip + KPI panel** · TODO (synced playhead; click-to-highlight both views; cumulative waiting time, crane utilization, vessels served counting up)
  *AC:* KPI values at t=end match artifact meta.kpis exactly (test).
- **T5.5 — Conflict rendering** · TODO (feasible=false artifacts: violating vessels/spans glow red in 3D + Gantt; violations panel)
  *AC:* Playwright test with an infeasible artifact shows red state.
- **T5.6 — Side-by-side comparison + deploy** · TODO (two synced viewports, same clock, solver picker; Vercel deploy)
  *AC:* comparison URL shareable; Lighthouse perf ≥ 85; deployed link in README.

## Phase 6 — Report & release
**DoD:** repo is portfolio-ready; report is thesis-chapter-ready.

- **T6.1 — Written report** · TODO (paper-structured: problem, formulation, methods, experiments, honest limitations; figures from Phase 4 scripts)
- **T6.2 — README + demo polish** · TODO (quickstart verified on clean clone; GIF of the twin; architecture diagram)
- **T6.3 — Full-repo review** · TODO (reviewer runs checklist §7; scribe closes project summary)
