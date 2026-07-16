# CLAUDE.md — Quantum-Optimized Berth Allocation & Quay Crane Scheduling

Hybrid quantum-classical solver for the integrated Berth Allocation and Quay Crane Assignment Problem (BACAP), benchmarked against classical methods, with a Next.js "digital twin" that animates the resulting port schedule. Thesis-critical project (maritime logistics).

## What we're building
- Discrete berth-time grid BACAP → QUBO with penalty terms (spatial non-overlap, crane capacity, time windows).
- Solvers: simulated annealing (dwave-neal), D-Wave quantum annealing (Leap, `[HW]` tickets only), QAOA (Qiskit Aer, small instances). Baselines: MILP via OR-Tools CP-SAT/CBC + greedy heuristic.
- Output: **solution artifact JSON** (schema below) consumed by the frontend.
- Frontend: Next.js + react-three-fiber isometric port replay with timeline scrubber, synced Gantt strip, live KPIs, side-by-side solver comparison, red-glow conflict rendering for infeasible samples.

## Stack
- Python 3.12, uv for env/deps. Core: `dimod`, `dwave-neal`, `dwave-system`, `qiskit`, `qiskit-aer`, `ortools`, `numpy`, `pydantic`, `pandas`. Tests: pytest. Lint: ruff + mypy.
- Frontend: Next.js 15 (App Router, TypeScript), react-three-fiber + drei, zustand (sim clock/playback), Tailwind, zod (artifact validation), vitest + Playwright. **No Streamlit anywhere.** No backend — artifacts statically served from `web/public/artifacts/`; deploy on Vercel.
- Repo layout: `src/bacap/` (instances, qubo, solvers, artifact export) · `web/` (Next.js) · `experiments/` (configs + results) · `docs/` · `tests/`.

## Data
- **No public real berth schedules exist — this is normal; the field runs on benchmark + synthetic instances.**
- Literature benchmarks: Meisel & Bierwirth BACAP instances (Transportation Research Part E, 2009) — locate/download in Phase 1, cite properly.
- Own generator calibrated to a Vuosaari-scale terminal (~750 m quay, 4–6 cranes).
- Realistic arrival patterns: Digitraffic port-call API `https://meri.digitraffic.fi/api/port-call/v1/port-calls` (Fintraffic open data, CC BY 4.0 — attribute in docs/data-sources.md). Docs: https://www.digitraffic.fi/en/marine-traffic/

## Solution artifact JSON (the Python↔frontend contract — architect owns changes)
```
{
  "meta": { "instance_id", "solver", "seed", "git_sha", "created_at", "objective", "feasible", "kpis": {...} },
  "instance": { "quay_length_m", "time_horizon", "time_step_min", "cranes": n,
                "vessels": [{ "id", "name", "length_m", "eta", "processing_volume", "priority" }] },
  "schedule": [{ "vessel_id", "berth_pos_m", "berth_start", "berth_end",
                 "crane_assignments": [{ "crane_id", "from", "to" }] }],
  "violations": [{ "type", "vessel_ids", "time_range", "detail" }]   // present iff feasible=false
}
```
Frontend derives ALL animation keyframes from this — no extra state.

## Conventions
- Every QUBO build returns `(bqm, var_map, penalty_report)`; penalty weights are named, logged, never magic numbers.
- Every decoded sample passes through `check_feasibility(instance, schedule)` before export; infeasible → `feasible=false` + populated `violations` (frontend renders these red).
- Seeds mandatory on all stochastic calls; experiment entries go to docs/experiments.md via scribe.
- Hardware (D-Wave) only in tickets marked `[HW]`, behind `BACAP_USE_QPU=1`, budget printed before submit.
- Secrets: `DWAVE_API_TOKEN` via `.env` only.

## Commands
- `uv run pytest` · `uv run ruff check . && uv run mypy src` · `uv run python -m bacap.cli solve <instance> --solver sa|qpu|qaoa|milp|greedy --seed N --out web/public/artifacts/`
- `cd web && pnpm dev` · `pnpm lint && pnpm typecheck && pnpm test`

## Agents & workflow
Four subagents in `.claude/agents/` (architect / implementer / reviewer / scribe). Phase loop, gates, and escalation rules: see WORKFLOW.md. Tickets and phase status: TICKETS.md (single source of truth). QA gate: qa-security-checklist.md — reviewer runs it on every ticket; §5 (quantum) and §6 (frontend) are the hot sections here.
