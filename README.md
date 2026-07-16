# BACAP — Quantum-Optimized Berth Allocation & Quay Crane Scheduling

Hybrid quantum-classical solver for the integrated Berth Allocation and Quay Crane
Assignment Problem, with a Next.js digital-twin frontend. See `CLAUDE.md` for scope
and `TICKETS.md` for status.

## Dev quickstart

```bash
uv sync
uv run pytest
uv run ruff check .
uv run mypy src
```

Copy `.env.example` to `.env` and fill secrets (`DWAVE_API_TOKEN`) as needed.
