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

## ⛔ Fable 5 checkpoint (token budget — MANDATORY)
`architect` and `reviewer` run on claude-fable-5 (expensive). NEVER invoke a Fable-5 subagent silently. Before any such call:
1. STOP and print exactly:
   > ⛔ **FABLE 5 CHECKPOINT** — `<architect|reviewer>` needed for <ticket/step>: <one-line reason>. Reply: **fable** (proceed) / **opus** (downgrade this call) / **defer**.
2. Wait for the user's reply. **opus** → invoke the same subagent with model overridden to claude-opus-4-8. **defer** → note it in TICKETS.md and continue other work.
3. Default recommendation per call: routine reviews (scaffolding, docs, frontend polish, config) → suggest **opus**; QUBO/math formulations, statistical protocol, artifact-schema contracts, secret/API-key-handling code → suggest **fable**.

# context-mode — MANDATORY routing rules

You have context-mode MCP tools available. These rules are NOT optional — they protect your context window from flooding. A single unrouted command can dump 56 KB into context and waste the entire session.

## BLOCKED commands — do NOT attempt these

### curl / wget — BLOCKED
Any Bash command containing `curl` or `wget` is intercepted and replaced with an error message. Do NOT retry.
Instead use:
- `ctx_fetch_and_index(url, source)` to fetch and index web pages
- `ctx_execute(language: "javascript", code: "const r = await fetch(...)")` to run HTTP calls in sandbox

### Inline HTTP — BLOCKED
Any Bash command containing `fetch('http`, `requests.get(`, `requests.post(`, `http.get(`, or `http.request(` is intercepted and replaced with an error message. Do NOT retry with Bash.
Instead use:
- `ctx_execute(language, code)` to run HTTP calls in sandbox — only stdout enters context

### WebFetch — BLOCKED
WebFetch calls are denied entirely. The URL is extracted and you are told to use `ctx_fetch_and_index` instead.
Instead use:
- `ctx_fetch_and_index(url, source)` then `ctx_search(queries)` to query the indexed content

## REDIRECTED tools — use sandbox equivalents

### Bash (>20 lines output)
Bash is ONLY for: `git`, `mkdir`, `rm`, `mv`, `cd`, `ls`, `npm install`, `pip install`, and other short-output commands.
For everything else, use:
- `ctx_batch_execute(commands, queries)` — run multiple commands + search in ONE call
- `ctx_execute(language: "shell", code: "...")` — run in sandbox, only stdout enters context

### Read (for analysis)
If you are reading a file to **Edit** it → Read is correct (Edit needs content in context).
If you are reading to **analyze, explore, or summarize** → use `ctx_execute_file(path, language, code)` instead. Only your printed summary enters context. The raw file content stays in the sandbox.

### Grep (large results)
Grep results can flood context. Use `ctx_execute(language: "shell", code: "grep ...")` to run searches in sandbox. Only your printed summary enters context.

## Tool selection hierarchy

1. **GATHER**: `ctx_batch_execute(commands, queries)` — Primary tool. Runs all commands, auto-indexes output, returns search results. ONE call replaces 30+ individual calls.
2. **FOLLOW-UP**: `ctx_search(queries: ["q1", "q2", ...])` — Query indexed content. Pass ALL questions as array in ONE call.
3. **PROCESSING**: `ctx_execute(language, code)` | `ctx_execute_file(path, language, code)` — Sandbox execution. Only stdout enters context.
4. **WEB**: `ctx_fetch_and_index(url, source)` then `ctx_search(queries)` — Fetch, chunk, index, query. Raw HTML never enters context.
5. **INDEX**: `ctx_index(content, source)` — Store content in FTS5 knowledge base for later search.

## Subagent routing

When spawning subagents (Agent/Task tool), the routing block is automatically injected into their prompt. Bash-type subagents are upgraded to general-purpose so they have access to MCP tools. You do NOT need to manually instruct subagents about context-mode.

## Output constraints

- Keep responses under 500 words.
- Write artifacts (code, configs, PRDs) to FILES — never return them as inline text. Return only: file path + 1-line description.
- When indexing content, use descriptive source labels so others can `ctx_search(source: "label")` later.

## ctx commands

| Command | Action |
|---------|--------|
| `ctx stats` | Call the `ctx_stats` MCP tool and display the full output verbatim |
| `ctx doctor` | Call the `ctx_doctor` MCP tool, run the returned shell command, display as checklist |
| `ctx upgrade` | Call the `ctx_upgrade` MCP tool, run the returned shell command, display as checklist |
