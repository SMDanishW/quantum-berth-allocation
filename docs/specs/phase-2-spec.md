# Phase 2 Spec — QUBO formulation

Governs tickets **T2.1–T2.3**. Builds on Phase 1 (docs/specs/phase-1-spec.md): integer time steps, `berth_grid_m` spatial grid, `processing_volume` in crane-steps, `cranes_min/max`, `target_departure`/`latest_departure`. Author: architect. Status: awaiting gate approval.

Per Phase 2 DoD, this document is the symbol-for-symbol reference: T2.2's code must match §2 exactly; deviations return to the architect.

---

## 1. Objective

Define the complete BACAP → QUBO mapping: decision variables on the berth-time grid, objective (weighted stay + priority-weighted tardiness), penalty terms with named weights and computable lower bounds, the `build_qubo(instance, weights) -> (bqm, var_map, penalty_report)` contract, sample decoding, and a `check_feasibility` that is the single source of truth for constraints and shares no code with the QUBO builder. DoD: the written formulation here matches code symbol-for-symbol.

---

## 2. The formulation (normative math)

### 2.1 Notation (all from `BacapInstance`, integer arithmetic)

| Symbol | Meaning | Source |
|---|---|---|
| `V` | vessel set | `instance.vessels` |
| `S` | quay segments | `quay_length_m // berth_grid_m` |
| `T` | horizon steps, grid `t = 0..T−1` | `time_horizon` |
| `Q` | total cranes | `cranes` |
| `λ_v` | vessel length in segments | `ceil(length_m / berth_grid_m)` |
| `e_v` | earliest berthing step | `eta` |
| `g_v` | soft due step | `target_departure` |
| `L_v` | hard latest departure | `latest_departure` or `T` |
| `q_v` | crane work (crane-steps) | `processing_volume` |
| `r⁻_v, r⁺_v` | crane count bounds | `cranes_min`, `cranes_max` |
| `p_v` | priority | `priority` |
| `d_v(c)` | service duration with `c` cranes | `ceil(q_v / c)` |

### 2.2 Decision variables (D1: start-time encoding, crane count in the index)

$$x_{v,b,t,c} \in \{0,1\}$$

= 1 iff vessel `v` moors with its bow at segment `b`, starts service at step `t`, and uses exactly `c` cranes for its entire stay (time-invariant, per Phase 1 D3), departing at `t + d_v(c)`.

**Pruned index domains (D3 — pruning IS the time-window constraint):**

- `b ∈ B_v = {0, …, S − λ_v}`  (vessel fits the quay — structural)
- `c ∈ C_v = {r⁻_v, …, r⁺_v}`
- `t ∈ T_v(c) = {e_v, …, L_v − d_v(c)}`  (never before ETA, never past hard window — structural)

If `T_v(c)` is empty for all `c`, the instance is infeasible for `v`: `build_qubo` raises `ValueError` (fail loud; Phase 1 validator V6 should have caught it).

**Slack variables** for crane capacity (only when needed, see P3):

$$y_{t,k} \in \{0,1\},\quad t \in \{0..T{-}1\},\ k \in \{0..K{-}1\},\ K = \lceil \log_2(Q+1) \rceil$$

with bounded-encoding coefficients `w_k = 2^k` for `k < K−1` and `w_{K−1} = Q − (2^{K−1} − 1)`, so `Σ_k w_k y_{t,k}` ranges over exactly `0..Q` (for Q=5: coefficients 1, 2, 2).

**Skip rule:** if `Σ_v r⁺_v ≤ Q`, crane capacity cannot be violated — emit no `y` variables and no `H_crane` (reported as structural in `penalty_report`).

*Alternatives rejected:* occupancy encoding `x_{v,b,t}` = "occupies cell" needs contiguity penalties (cubic-ish, fragile); post-hoc crane counts (fix `c_v = r⁺_v`) deletes the crane-assignment half of BACAP that the thesis is about. Start-time encoding makes one variable = one complete berthing decision, so every constraint is pairwise — the whole problem is naturally quadratic.

### 2.3 Hamiltonian

$$H = H_{obj} + A_{\text{onehot}} H_{\text{onehot}} + A_{\text{overlap}} H_{\text{overlap}} + A_{\text{crane}} H_{\text{crane}}$$

**Objective (linear — every cost is known once (v,b,t,c) is fixed):**

$$H_{obj} = \sum_{v} \sum_{b,t,c} \kappa_{v,t,c}\, x_{v,b,t,c},\qquad
\kappa_{v,t,c} = W_{\text{stay}}\,\big(t + d_v(c) - e_v\big) \;+\; W_{\text{tard}}\; p_v\, \max\!\big(0,\; t + d_v(c) - g_v\big)$$

Note `κ` does not depend on `b`: berth position carries no cost (Phase 1 dropped M&B's position-deviation cost). This is deliberate; see degeneracy risk §6.

**P1 — one berthing per vessel:**

$$H_{\text{onehot}} = \sum_{v} \Big(1 - \sum_{b,t,c} x_{v,b,t,c}\Big)^2$$

**P2 — spatial non-overlap:** for every unordered pair of variables belonging to *different* vessels whose space-time rectangles intersect:

$$H_{\text{overlap}} = \sum_{v<w} \sum_{\substack{(b,t,c),(b',t',c')\\ \text{conflict}}} x_{v,b,t,c}\; x_{w,b',t',c'}$$

$$\text{conflict} \iff [b, b{+}\lambda_v) \cap [b', b'{+}\lambda_w) \neq \emptyset \;\wedge\; [t, t{+}d_v(c)) \cap [t', t'{+}d_w(c')) \neq \emptyset$$

(i.e. `|b−b'| < min-shift`: `b < b'+λ_w and b' < b+λ_v`, and likewise in time.)

**P3 — crane capacity (equality with bounded slack, per time step):**

$$H_{\text{crane}} = \sum_{t=0}^{T-1} \Big( Q \;-\; \underbrace{\sum_{v}\sum_{\substack{(b,s,c):\\ s \le t < s + d_v(c)}} c\; x_{v,b,s,c}}_{\text{load}_t} \;-\; \sum_{k} w_k\, y_{t,k} \Big)^2$$

Load ≥ 0 and slack ∈ [0, Q] exactly, so the equality is satisfiable iff load_t ≤ Q. Expansion produces x·x, x·y, y·y quadratic terms; same-vessel x·x cross terms inside the square are fine (they co-fire only when one-hot is already violated).

**P4 — time windows: structural.** Enforced by the pruned domains in §2.2 — zero penalty terms, zero weight to tune. Reported in `penalty_report` as `{"time_windows": {"structural": true, "quadratic": 0}}`. This is intentional: exact enforcement, one fewer weight to balance.

### 2.4 Named weights and lower-bound guidance

```python
class PenaltyWeights(BaseModel):          # frozen, extra="forbid"
    w_stay: float = 1.0                   # W_stay
    w_tardiness: float = 2.0              # W_tard
    a_onehot: float                       # A_onehot
    a_overlap: float                      # A_overlap
    a_crane: float                        # A_crane

def default_weights(instance: BacapInstance,
                    w_stay: float = 1.0, w_tardiness: float = 2.0) -> PenaltyWeights: ...
```

Sufficient bound (violating any hard constraint must never pay): a single unit of penalty (cost `A_·`) must exceed the largest objective saving any single reassignment can buy, which is bounded by the largest objective coefficient:

$$\Lambda(\text{instance}) = \max_{v,c,\,t \in T_v(c)} \kappa_{v,t,c}
= \max_v\Big[ W_{\text{stay}} (L_v - e_v) + W_{\text{tard}}\, p_v \,(L_v - g_v) \Big]$$

`default_weights` sets `a_onehot = a_overlap = a_crane = 2Λ` (factor 2 = safety margin over the ≥ Λ+1 sufficient condition). This is provably safe but likely over-stiff (flat landscape for SA); **T4.2 tunes downward from here**, never below `Λ`. `penalty_report["recommended_min"]` carries `Λ` per weight so experiments log the floor they must respect.

---

## 3. Module & file layout

```
src/bacap/qubo.py         # T2.2 — PenaltyWeights, default_weights, build_qubo,
                          #         decode_sample, DecodeError, VarKey
src/bacap/schedule.py     # T2.3 — ScheduleEntry, CraneAssignment, Violation (pure pydantic, no logic)
src/bacap/feasibility.py  # T2.3 — check_feasibility (imports schema.py + schedule.py ONLY;
                          #         importing qubo.py here is a review-blocking offense)
tests/test_qubo.py  tests/test_feasibility.py
```

### 3.1 `qubo.py` public contract

```python
VarKey = tuple  # ("x", vessel_id: str, b: int, t: int, c: int) | ("y", t: int, k: int)

def build_qubo(
    instance: BacapInstance,
    weights: PenaltyWeights,
) -> tuple[dimod.BinaryQuadraticModel, dict[str, VarKey], dict]:
    """BQM variable labels are strings: 'x[v3,4,12,2]', 'y[12,0]'.
    var_map: label -> VarKey. penalty_report: see §3.2.
    Raises ValueError if any vessel has an empty domain."""

class DecodeError(Exception): ...   # carries vessel_id and n_set

def decode_sample(
    instance: BacapInstance,
    sample: Mapping[str, int],      # label -> 0/1, as returned by dimod samplers
    var_map: dict[str, VarKey],
) -> list[ScheduleEntry]:
    """Raises DecodeError iff any vessel has != 1 set x-variable (no repair, fail loud).
    Spatial/crane violations do NOT raise — they decode fine and are caught by
    check_feasibility (that's what feasible=false artifacts are for)."""
```

**Decode rules (normative):**
1. Per vessel, collect set `x` labels. Count ≠ 1 → `DecodeError` (solvers skip the sample and count it; if *all* reads fail, solver raises — no silent empty artifact).
2. From the unique `(b, t, c)`: `berth_pos_m = b · berth_grid_m`, `berth_start = t`, `berth_end = t + d_v(c)` (steps, per Phase 1 D1).
3. **Crane IDs (deterministic, post-hoc):** for each step `u`, sort vessels active at `u` by `berth_pos_m` (tie-break by `vessel_id`), hand out crane ids `0, 1, 2, …` left-to-right, `c_v` consecutive ids each. Consecutive-id blocks in position order never cross within a step (rail constraint satisfied per step; inter-step crane travel is animation detail, documented). Ids ≥ `Q` are allowed to appear — that is exactly the over-capacity case and `check_feasibility` flags it; the frontend renders it red.
4. `crane_assignments`: per vessel, merge maximal runs of steps with an unchanged id set into `{crane_id, from, to}` records (one record per id per run; `to` exclusive, in steps).
5. Slack variables `y` are ignored by the decoder.

### 3.2 `penalty_report` schema (plain dict, logged verbatim by solvers)

```python
{
  "weights": {"w_stay": 1.0, "w_tardiness": 2.0, "a_onehot": ..., "a_overlap": ..., "a_crane": ...},
  "recommended_min": {"a_onehot": Λ, "a_overlap": Λ, "a_crane": Λ},
  "terms": {
    "objective":       {"linear": int},
    "onehot":          {"linear": int, "quadratic": int},
    "overlap":         {"quadratic": int},
    "crane_capacity":  {"linear": int, "quadratic": int, "slack_vars": int, "structural": bool},
    "time_windows":    {"structural": True, "quadratic": 0},
  },
  "n_x": int, "n_slack": int, "n_variables": int, "n_quadratic_total": int,
  "domain_pruning": {"positions_pruned": int, "starts_pruned": int},  # vs unpruned S·T·|C| grid
}
```

### 3.3 `schedule.py` / `feasibility.py` contract

```python
class CraneAssignment(BaseModel):   # frozen
    crane_id: int; from_step: int; to_step: int          # serialize as "from"/"to" (aliases) to match artifact

class ScheduleEntry(BaseModel):     # frozen — one artifact "schedule" element
    vessel_id: str; berth_pos_m: int; berth_start: int; berth_end: int
    crane_assignments: list[CraneAssignment]

class Violation(BaseModel):         # frozen — one artifact "violations" element
    type: Literal["unassigned","duplicate_assignment","off_grid","outside_quay",
                  "before_eta","after_latest","insufficient_work","crane_bounds",
                  "spatial_overlap","crane_overcapacity","crane_conflict"]
    vessel_ids: list[str]
    time_range: tuple[int, int]     # [from, to) in steps; whole-stay range when constraint is not time-local
    detail: str                     # human-readable, includes the numbers

def check_feasibility(instance: BacapInstance,
                      schedule: list[ScheduleEntry]) -> list[Violation]:
    """Empty list == feasible. Recomputes EVERYTHING from instance + schedule;
    never trusts decoder invariants; shares zero code with qubo.py."""
```

**Constraint list (each checked independently, in order; all reported, not just the first):**

| # | Check | Violation type |
|---|---|---|
| F1 | every instance vessel appears exactly once in schedule | `unassigned` / `duplicate_assignment` |
| F2 | `berth_pos_m % berth_grid_m == 0` and `berth_pos_m + length_m ≤ quay_length_m` | `off_grid` / `outside_quay` |
| F3 | `berth_start ≥ eta` | `before_eta` |
| F4 | `berth_end ≤ hard_departure(v)` and `berth_start < berth_end` | `after_latest` |
| F5 | crane count `c_v` := distinct ids in `crane_assignments` is constant over every step of `[berth_start, berth_end)`, `r⁻_v ≤ c_v ≤ r⁺_v`, and `c_v · (berth_end − berth_start) ≥ q_v` | `crane_bounds` / `insufficient_work` |
| F6 | no two vessels' `[pos, pos+length_m) × [start, end)` rectangles intersect | `spatial_overlap` |
| F7a | per step: total assigned crane ids ≤ `Q` and every id < `Q` | `crane_overcapacity` |
| F7b | per step: no crane id serves two vessels | `crane_conflict` |

Tardiness past `target_departure` is a **cost, not a violation** — never reported here.

---

## 4. Variable / qubit-count table (T2.1 AC)

**Formula (exact, computed per-instance by `build_qubo` into `penalty_report`):**

$$n_x = \sum_{v}\; |B_v| \sum_{c \in C_v} \max\big(0,\; L_v - d_v(c) - e_v + 1\big),
\qquad n_y = T \cdot \lceil \log_2(Q{+}1)\rceil \text{ (or 0 via skip rule)},\qquad n = n_x + n_y$$

**Estimates below use the "annealing preset"** — the discretization mandated for all quantum-track experiments: `time_step_min=120`, `berth_grid_m=50`, quay 750 m (S=15), Q=5 (K=3), congestion 0.5, representative vessel `λ=3` (|B|=13), `|C_v|=2`, `d̄≈6.5` steps, generator horizon `T ≈ 2N+22`, `latest_departure=None`. Numbers are ±30% envelope estimates — **recompute exactly from `penalty_report` in T2.2 and update this table (scribe)**.

**AMENDED 2026-07-17 (spike B):** the phase-1-spec §4.4 amendment gives synthetic instances a hard LFT: `L_v = eta + ceil(1.5·d_v^min)`, so `latest_departure=None` above is superseded. The per-`(v,b,c)` start window shrinks from `T − d_v(c) − e_v + 1` to `ceil(1.5·d_v^min) − d_v(c) + 1` ≈ 2–5 starts (e.g. `d_min=6`: window `9 − d(c) + 1`, i.e. 4 starts at `c=r⁺`, ~1–2 at `c=r⁻`), making the table entries **stale worst-case upper bounds** — actual `n_x` drops roughly an order of magnitude (≈ `N·|B|·(3–6)` ≈ 40–80·N, e.g. N=8 → n_x ≈ 500 vs ≈ 5 100 above). `n_y` is unchanged. Solver-viability conclusions only improve (direct QPU may become reachable at N=3–5 without the micro preset's quay shrink — verify in T2.2). The T2.2 recompute-and-update mandate stands and now matters more. The `n_x` formula, `g_v`/`L_v` symbol table, P4 structural pruning, F4, and the tardiness definition (§2) are already written against `target_departure`/`latest_departure` generically and need **no change**.

| N vessels | T (steps) | n_x | n_y | **n total** | est. quadratic terms | Solver viability |
|---|---|---|---|---|---|---|
| 5  | 32 | ≈ 2 800  | 96  | **≈ 2.9 k**  | ≈ 3×10⁵ | SA ✓ · LeapHybrid ✓ · direct QPU ✗ · QAOA ✗ |
| 8  | 38 | ≈ 5 100  | 114 | **≈ 5.2 k**  | ≈ 1×10⁶ | SA ✓ · LeapHybrid ✓ |
| 10 | 42 | ≈ 6 900  | 126 | **≈ 7.0 k**  | ≈ 2×10⁶ | SA ✓ · LeapHybrid ✓ |
| 15 | 52 | ≈ 12 300 | 156 | **≈ 12.5 k** | ≈ 6×10⁶ | SA (slow) · LeapHybrid ✓ |
| 20 | 62 | ≈ 19 000 | 186 | **≈ 19.2 k** | ≈ 1.5×10⁷ | LeapHybrid ✓ · SA at the edge |

Phase 1's *default* fine grid (60 min / 25 m) roughly ×3.5 these counts — it exists for MILP/greedy baselines and the frontend; **never build QUBOs on it above N=5**.

**Direct-QPU micro preset (T3.5):** N=3–4, quay 300 m / grid 75 m (|B|≈2–3), `|C|=1` (set `cranes_min=cranes_max`), T≈16 → n ≈ 100–200 logical variables — the realistic clean-embedding ceiling on Advantage.

**QAOA toy (T3.4, ≤25 qubits — LOCKED):** 2 vessels, quay 200 m / grid 50 m (S=4, λ_v=2 ⇒ |B|=3), T=8 with windows pruned to 4 starts each, `|C|=1`, `Σ r⁺ ≤ Q` (skip rule ⇒ no slacks): **n = 2·3·4 = 24 ≤ 25**. Three vessels cannot fit under the guard; T3.4's brute-force cross-checks use `dimod.ExactSolver` on n ≤ 24, QAOA runs only this toy.

---

## 5. Ticket refinement

### T2.1 — Formulation spec
This document. Merge to `docs/specs/phase-2-spec.md` (done); AC's risk section on penalty balance is §6.

### T2.2 — QUBO encoder
Notes: build as a pure function; accumulate linear/quadratic dicts keyed by string labels, then one `dimod.BinaryQuadraticModel(linear, quadratic, offset, "BINARY")` construction (offset = `A_onehot·|V| + A_crane·Σ_t Q²` from expanding the squares — get the constant right or ground energy ≠ objective and the brute-force test fails). Overlap enumeration: precompute per-vessel variable lists with their rectangles; O(pairs) double loop with early rejection on time then space — no cleverness until `penalty_report["n_quadratic_total"]` proves it's needed.
Edge cases: single vessel (no overlap/crane terms via skip rule); vessel with `r⁻=r⁺`; `t` window of exactly one start; two vessels that cannot temporally overlap (zero P2 terms — assert pruning works).
Required tests: (a) 2-vessel toy (the locked QAOA toy above): enumerate all 2²⁴ states impossible — use `ExactSolver` on the BQM; assert ground state decodes to the enumerated optimal feasible schedule and ground energy == its objective (offset check); (b) 3-vessel toy on a tiny grid with a forced conflict: assert optimal feasible schedule found by classical enumeration = BQM ground state, and every lower-energy infeasible candidate is priced above it; (c) `penalty_report` term counts match hand-counted values on the 2-vessel toy; (d) `default_weights` Λ matches hand-computed formula; (e) empty-domain vessel raises `ValueError`.

### T2.3 — Decoder + feasibility checker
Notes: `check_feasibility` recomputes durations, rectangles, and per-step crane tallies from raw `ScheduleEntry` fields only. Build the per-step crane occupancy as a plain `dict[(step, crane_id) -> vessel_id]` — first conflict wins the report, keep scanning (all violations reported).
Edge cases: `berth_end == berth_start` (F4); back-to-back vessels sharing a boundary step/segment (half-open intervals ⇒ no violation — test both boundary cases); crane id reused by the same vessel in disjoint runs (legal); vessel with `crane_assignments` gaps inside its stay (F5 constant-count fails).
Required tests (AC): adversarial fixed cases — overlapping rectangles, `Σc > Q` at one step, crane id shared by two vessels, off-grid position — each caught with the exact `type`; **property test** (seeded, ~200 iterations): a constructive random-feasible-schedule helper (greedy left-to-right placement respecting all constraints by construction) always yields `[]`; a mutation helper that injects exactly one named violation type always yields exactly ≥1 violation of that type; round-trip: `decode_sample` output of any one-hot-valid sample is structurally valid input to `check_feasibility` (never raises).

---

## 6. Risks

| Risk | Impact | Mitigation / fallback |
|---|---|---|
| **Penalty-weight balance** (T2.1 AC): `2Λ` is provably safe but stiff — SA landscape dominated by penalties, poor objective refinement; too-low weights yield infeasible ground states | Solution quality | `recommended_min` (Λ) logged in every `penalty_report`; T4.2 sweeps `[Λ, 4Λ]`; feasibility-rate metric already defined (share of seeds whose best sample passes `check_feasibility`) |
| **Degeneracy**: `κ` ignores `b` → all feasible positions of an otherwise-fixed assignment are energy-equal | Non-reproducible layouts across seeds; harmless for objective-value science | Tests compare energy/objective, never exact layouts; if the frontend demo needs stable layouts, add an explicit tiny position tiebreak cost `ε·b` via a new weight — architect change, not a hack |
| **Quadratic blow-up**: ~10⁷ terms at N=20 even on the annealing preset; BQM build memory ~GBs | Build time/memory, SA throughput | Annealing preset is mandatory for quantum-track (this spec); N=20 routed to LeapHybrid; if BQM construction itself chokes, spike: switch overlap accumulation to numpy-batched arrays before touching the formulation |
| **Direct QPU embedding fails above ~200 variables** | T3.5 scope | Micro preset (§4) is the direct-QPU story; everything larger is LeapHybrid — set this expectation in the thesis now, not after burning Leap minutes |
| **Offset/constant errors** in expanded squares | Ground energy ≠ objective, silently wrong experiment plots | T2.2 test (a) pins ground energy to an independently computed objective |
| Phase 1 constraint: `d_v(c)=⌈q_v/c⌉` overshoot means `c·d ≥ q_v` with slack work | None — F5 checks `≥`, consistent by construction | documented here |
| M&B fine-grid instances (1000 m/10 m, hourly week) | Never QUBO-viable | Already flagged in Phase 1 risks: benchmarks serve MILP/greedy; quantum instances come from the generator presets |
