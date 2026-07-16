# BACAP — Quantum-Optimized Berth Allocation & Quay Crane Scheduling

Hybrid quantum-classical solver for the integrated Berth Allocation and Quay Crane
Assignment Problem (BACAP), benchmarked against classical methods (MILP, greedy),
with a Next.js "digital twin" that animates the resulting port schedule.
Thesis-critical maritime-logistics project.

## Stack

- **Python 3.12** (uv) — QUBO encoding (`dimod`), solvers: simulated annealing
  (`dwave-neal`), D-Wave quantum annealing, QAOA (`qiskit-aer`); baselines via
  OR-Tools. Lint/type/test: ruff + mypy + pytest.
- **Next.js 15** (App Router, TypeScript) — react-three-fiber isometric port
  replay driven by a static solution-artifact JSON. Lint/type/test: eslint + tsc
  + vitest/Playwright.

## Quickstart

```bash
# Python
uv sync
uv run pytest
uv run ruff check . && uv run mypy src

# Web
cd web && pnpm install && pnpm dev
```

Copy `.env.example` to `.env` and fill secrets (`DWAVE_API_TOKEN`) as needed.

## Docs

- Scope and conventions: `CLAUDE.md`
- Phase specs: [`docs/specs/`](docs/specs/)
- Ticket status (single source of truth): [`TICKETS.md`](TICKETS.md)
