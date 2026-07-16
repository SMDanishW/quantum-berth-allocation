# Phase 1 Spec — Instance model, generator & real-data calibration

Governs tickets **T1.1–T1.4**. Author: architect. Status: awaiting gate approval.

---

## 1. Objective

Deliver the canonical BACAP instance representation (Pydantic v2 + JSON), a parser/regenerator for the Meisel & Bierwirth (2009) benchmark set, a Digitraffic-calibrated arrival/size model for Vuosaari, and a seeded synthetic generator with a measurable congestion knob — satisfying the Phase 1 DoD: `bacap.cli generate` produces valid instances, benchmark instances load, arrival-pattern stats are documented. Everything downstream (QUBO grid in Phase 2, artifact JSON in Phase 3, frontend in Phase 5) consumes exactly the units and discretization locked here.

---

## 2. Design decisions

### D1 — Canonical units: **integer time steps** for time, **meters** for space, **segments** derived (LOCKED, cross-phase)

| Quantity | Stored as | Physical meaning |
|---|---|---|
| All time fields (`eta`, `target_departure`, `latest_departure`, `time_horizon`) | `int` grid steps | `steps × time_step_min` minutes; grid is `t = 0 .. time_horizon-1` |
| `time_step_min` | `int` minutes | size of one step (benchmark default 60) |
| Positions / lengths (`quay_length_m`, `length_m`, `berth_grid_m`) | `int` meters | physical |
| Berth position on the QUBO grid | derived segment index `b`, `berth_pos_m = b × berth_grid_m` | Phase 2 variables live on `(vessel, b, t)` |
| `processing_volume` | `int` **crane-steps** | total crane work; duration with `c` cranes = `ceil(processing_volume / c)` steps |

*Alternatives considered:* minutes everywhere (float creep, off-grid ETAs); continuous berth positions (matches M&B's continuous model but makes the QUBO grid a Phase 2 re-decision). Chosen: integers-on-grid because Phase 2's `x_{v,b,t}` encoding needs a finite grid and the artifact contract already exposes `time_step_min`. **Any change to D1 after Phase 2 starts is a breaking change and returns to the architect.**

The QUBO variable count at Phase 2 is `≈ V × B × T` with `B = (quay_length_m − length_m)/berth_grid_m + 1` positions per vessel. This is why `berth_grid_m` is an instance field, not a solver option: coarse grids (25–50 m) are how N=10–20-vessel instances stay under annealer limits. (Full formulation, encoding and variable-count table are Phase 2 / T2.1 — not this spec.)

### D2 — Instance schema is a **superset** of the artifact `instance` block
The artifact's `instance` block (CLAUDE.md contract) is produced as `instance.model_dump(mode="json")` — the full serialization, unmodified. The six vessel fields listed in CLAUDE.md are the *minimum projection*; this spec adds `cranes_min`, `cranes_max`, `target_departure`, `latest_departure`, and instance-level `berth_grid_m`, `instance_id`, `source`, `schema_version`. As contract owner I declare these additive fields part of the artifact contract; the Phase 5 zod schema must include them (scribe: note in CLAUDE.md contract comment when Phase 5 spec is written).

### D3 — Crane model: identical cranes, per-vessel min/max, volume-based duration
Vessels carry `processing_volume` (crane-steps) plus `cranes_min/cranes_max`. Duration is *not* stored — it is `ceil(volume / cranes_assigned)`. *Alternative:* fixed handling time per vessel (simpler, but kills the crane-assignment half of BACAP and doesn't match M&B). Chosen: volume-based, time-invariant crane count per vessel (M&B's "time-invariant" variant) — we deliberately drop M&B's variable-in-time crane profiles and their speedup option (documented deviation, see §4.2).

### D4 — Time windows: soft `target_departure` (tardiness cost, weighted by `priority`), hard `latest_departure`
Maps to M&B's EFT (soft) / LFT (hard). Needed now because the Phase 2 objective (weighted stay + tardiness, per T2.1) cannot be formulated without a due date. `latest_departure = None` means the horizon end.

### D5 — Congestion knob = target quay-time utilization ρ; metric is `congestion_index`
Define demand area `A = Σ_v l_v · d_v^min` (m·steps), where `d_v^min = ceil(q_v / cranes_max_v)`. The generator draws Poisson arrivals with rate `λ = ρ · L / E[l·d^min]` (vessels per step) so that expected instantaneous berth demand ≈ `ρ · L`. Measured metric on a finished instance:

```
congestion_index(inst) = A / (L · T_span),   T_span = max_v(eta_v + d_v^min) − min_v(eta_v)
```

AC test: mean index over ≥20 seeds is strictly increasing across knob values {0.3, 0.5, 0.7}. *Alternative:* pairwise-overlap counting (noisier, order-dependent). Chosen: utilization is the standard queueing quantity and trivially testable.

### D6 — Calibration artifact is a tiny committed JSON of *fitted parameters*, never raw data
Digitraffic responses stay local/scratch; only the `ArrivalCalibration` JSON (a dozen numbers + provenance) is committed at `experiments/calibration/vuosaari.json`. Fits use closed-form MLE (no scipy dependency): exponential inter-arrivals (`rate = 1/mean`), lognormal lengths and service times (`mu = mean(ln x)`, `sigma = std(ln x, ddof=1)`).

### D7 — M&B ingestion: download-first, regenerate-fallback, both behind one parser API
**AMENDED 2026-07-16 (spike):** M&B originals confirmed unreachable (prodlog downloads dead; TRE 2009 paper not obtainable via user's library). Ruling: primary source is now the **Iris/Pacino/Ropke (2017) "BACAP_Benchmark_n60_n80" dataset** (ResearchGate, published with their TRE 2017 ALNS paper) — actual instance files in the M&B lineage, same problem variant (time-invariant BACAP, 1000 m quay, 1 h periods), user downloads manually. Fallback: transcribe the M&B generation table from Iris et al. (2015, TRE 81:75–97) and regenerate via the existing `regenerate_mb` machinery. Same parser API either way; `source` distinguishes `"iris_2017"` (new Literal value — **T1.1 schema amendment, needs review**) vs `"meisel_bierwirth_regenerated"`. Original D7 text below kept for history.

~~Hosting is **not fully verified** (see §4.2): the historical host `prodlog.wiwi.uni-halle.de/forschung/container/` (Bierwirth's chair, "Seaside operations planning in container terminals") exists as of 2026-07-16, but I could not fetch its contents from this environment. Spec covers both paths; the module exposes the same `BacapInstance` either way, with `source` distinguishing `"meisel_bierwirth"` vs `"meisel_bierwirth_regenerated"`.~~

### D8 — HTTP: `httpx` (new dep), fail-loud, no fallbacks
Retry only on transport timeouts and 5xx (3 attempts, exponential backoff 1/2/4 s); any 4xx or exhausted retries raises. No cached-response fallback (CLAUDE.md: fail loudly). `matplotlib` added as a dev/extra dependency for the T1.3 plot AC.

---

## 3. Module & file layout

```
src/bacap/instances/
    __init__.py          # re-exports: BacapInstance, Vessel, load_instance, save_instance
    schema.py            # T1.1 — models + (de)serialization + congestion_index
    meisel_bierwirth.py  # T1.2 — parse_mb_file, regenerate_mb
    generator.py         # T1.4 — generate_instance
    calibration.py       # T1.3 — Digitraffic client + fitting + ArrivalCalibration model
scripts/
    record_digitraffic_fixtures.py   # one-off; writes tests/fixtures/digitraffic/*.json
    calibrate_vuosaari.py            # fetch → fit → experiments/calibration/vuosaari.json + plot
experiments/calibration/vuosaari.json
docs/data-sources.md                 # provenance + CC BY 4.0 attribution (T1.2 + T1.3)
docs/figures/vuosaari-calibration.png
tests/instances/                     # test_schema.py, test_mb.py, test_calibration.py, test_generator.py
tests/fixtures/digitraffic/          # recorded, truncated API responses (committed)
tests/fixtures/mb/                   # 1–2 raw M&B files if redistributable, else omitted (see §4.2)
```

### 3.1 `schema.py` — public contract (T1.1)

```python
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Vessel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)          # unique within instance
    name: str
    length_m: int = Field(gt=0)            # INCLUDES safety clearance (M&B convention)
    eta: int = Field(ge=0)                 # earliest berthing, in time steps
    processing_volume: int = Field(gt=0)   # crane-steps (see D1/D3)
    priority: int = Field(default=1, ge=1) # tardiness weight multiplier
    cranes_min: int = Field(default=1, ge=1)
    cranes_max: int = Field(ge=1)
    target_departure: int = Field(gt=0)    # soft due date, steps
    latest_departure: int | None = None    # hard; None ⇒ time_horizon

    # model_validator(mode="after"): cranes_min <= cranes_max; eta < target_departure;
    #                                latest_departure is None or >= target_departure

class BacapInstance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    instance_id: str
    source: Literal["synthetic", "meisel_bierwirth",
                    "meisel_bierwirth_regenerated", "manual"]
    quay_length_m: int = Field(gt=0)
    berth_grid_m: int = Field(gt=0)
    time_horizon: int = Field(gt=0)        # number of steps; grid t = 0..time_horizon-1
    time_step_min: int = Field(gt=0)
    cranes: int = Field(ge=1)              # identical, on one rail
    vessels: list[Vessel] = Field(min_length=1)

    # --- derived, pure, no state ---
    @property
    def n_segments(self) -> int: ...                       # quay_length_m // berth_grid_m
    def length_segments(self, v: Vessel) -> int: ...       # ceil(v.length_m / berth_grid_m)
    def n_positions(self, v: Vessel) -> int: ...           # n_segments - length_segments(v) + 1
    def min_duration(self, v: Vessel) -> int: ...          # ceil(v.processing_volume / v.cranes_max)
    def hard_departure(self, v: Vessel) -> int: ...        # latest_departure or time_horizon

def load_instance(path: str | Path) -> BacapInstance: ...  # raises pydantic.ValidationError / ValueError
def save_instance(inst: BacapInstance, path: str | Path) -> None:  # model_dump_json(indent=2)
def congestion_index(inst: BacapInstance) -> float: ...    # per D5
```

**Instance-level validation** (`model_validator(mode="after")`), each rule with a distinct error message:

| # | Rule |
|---|---|
| V1 | vessel ids unique |
| V2 | `quay_length_m % berth_grid_m == 0` |
| V3 | every `length_m <= quay_length_m` |
| V4 | every `cranes_max <= cranes` |
| V5 | every `eta < time_horizon` |
| V6 | schedulability: `eta + min_duration(v) <= hard_departure(v) <= time_horizon` |
| V7 | `time_step_min in {15, 30, 60, 120}` (keeps grids sane; extend only via architect) |

Serialization: JSON via `model_dump_json` / `model_validate_json`. No YAML, no CSV. Round-trip must be exact (frozen models, ints only ⇒ trivially exact).

### 3.2 `meisel_bierwirth.py` (T1.2)

```python
def parse_mb_file(text: str, instance_id: str,
                  *, source: Literal["iris_2017", "meisel_bierwirth"] = "iris_2017") -> BacapInstance: ...
def regenerate_mb(n_vessels: Literal[20, 30, 40], seed: int) -> BacapInstance: ...
def load_mb_set(dir: Path) -> list[BacapInstance]: ...
```

**AMENDED 2026-07-16 (spike):** `parse_mb_file` gained the `source` keyword (Iris files are M&B-format lineage; one parser serves both). `"meisel_bierwirth"` stays in the Literal only for the case that original files ever surface. Requires adding `"iris_2017"` to `BacapInstance.source` (T1.1 amendment — see §4.2).

### 3.3 `calibration.py` (T1.3)

```python
class ArrivalCalibration(BaseModel):
    schema_version: Literal[1] = 1
    source: str                     # "digitraffic port-call v1"
    locode: str                     # "FIHEL"
    port_area: str                  # Vuosaari area code as returned by API (expected "VUOS" — verify)
    window_from: str; window_to: str          # ISO dates of the data window
    n_port_calls: int
    interarrival: dict              # {"dist": "exponential", "rate_per_hour": float}
    vessel_length_m: dict           # {"dist": "lognormal", "mu": float, "sigma": float, "clip_min": 60, "clip_max": 300}
    service_time_steps: dict        # {"dist": "lognormal", "mu": float, "sigma": float}  @ time_step_min=60
    created_at: str
    attribution: str                # fixed CC BY 4.0 string, see §4.3

def fetch_port_calls(locode: str, from_iso: str, to_iso: str,
                     *, client: httpx.Client | None = None) -> list[dict]: ...
def fetch_vessel_dimensions(client: httpx.Client | None = None) -> dict[int, int]:
    """mmsi -> length_m from AIS vessel-metadata endpoint."""
def fit_calibration(port_calls: list[dict], dims: dict[int, int],
                    port_area: str) -> ArrivalCalibration: ...
def load_calibration(path: str | Path) -> ArrivalCalibration: ...
```

`client` injection is the test seam: tests build an `httpx.Client(transport=httpx.MockTransport(...))` serving recorded fixtures. **No live HTTP in tests.**

### 3.4 `generator.py` (T1.4)

```python
def generate_instance(
    n_vessels: int,
    congestion: float,                       # target ρ ∈ (0, 1)
    seed: int,                               # mandatory, no default
    calibration: ArrivalCalibration | None = None,   # None ⇒ VUOSAARI_DEFAULTS (see §4.4)
    *,
    quay_length_m: int = 750,
    cranes: int = 5,                         # Vuosaari-scale 4–6
    berth_grid_m: int = 25,
    time_step_min: int = 60,
) -> BacapInstance: ...
```

Single `numpy.random.default_rng(seed)` for all draws; identical `(args, seed)` ⇒ byte-identical JSON.

---

## 4. Ticket refinement

### 4.1 T1.1 — schema & loader
Implementation notes: exactly as §3.1; models frozen; validators raise with the rule number in the message (greppable in tests). `congestion_index` lives here (pure function of the instance) so the generator test doesn't import generator internals.
Edge cases: single vessel; vessel exactly quay-length; `eta = time_horizon - min_duration` (tight but valid); `latest_departure == time_horizon`.
Required tests: (a) round-trip `save → load → ==`; (b) one failing test per rule V1–V7 (satisfies the "5+ validation-failure" AC); (c) derived-property arithmetic (`n_positions` for a vessel of 190 m on 25 m grid, 750 m quay ⇒ `ceil(190/25)=8`, `30−8+1=23`); (d) `model_dump(mode="json")` contains all six CLAUDE.md-contract vessel keys (guards D2).

### 4.2 T1.2 — Benchmark import (M&B lineage via Iris et al.)

> **AMENDED 2026-07-16 (spike ruling, architect).** M&B originals are dead (prodlog downloads gone, TRE 2009 paper inaccessible to the user). Old Path A (download originals) is **superseded**; old Path B survives as the fallback with a new table source. New ordering:
>
> **Path A′ (primary): parse the Iris et al. (2017) dataset.** The user manually downloads (architect cannot reach ResearchGate):
> 1. Dataset **"BACAP_Benchmark_n60_n80"** (Iris, Pacino, Ropke — ResearchGate, July 2017, companion to their TRE 2017 ALNS paper) — the full archive, placed at `data/benchmarks/iris2017/` (**gitignored**, add the entry).
> 2. Full-text PDF of **Iris, Pacino, Ropke, Larsen (2015), "Integrated Berth Allocation and Quay Crane Assignment Problem: Set partitioning models and computational results", TRE 81:75–97, doi:10.1016/j.tre.2015.06.008** — needed regardless of path: it documents the instance format/generation and is the citation anchor.
> 3. If ResearchGate access is refused: email C. A. Iris (Univ. of Liverpool) requesting the instance files; this is standard practice in the field.
>
> Implementer's first step is unchanged in spirit: inspect the raw format, record it verbatim in `docs/data-sources.md` (column table), then implement `parse_mb_file`. The field mapping table below (written for the M&B format) is the expected mapping — Iris et al. use the same problem data (length, ETA, `m_i`, `r_i^min/max`, EFT, LFT on a 1000 m quay, 1 h periods); verify against the actual files and correct the table in data-sources.md, not by inventing values. If the archive also contains the original n=20/30/40 M&B sets, parse those too (same parser).
>
> **Schema change (T1.1 amendment, requires review):** add `"iris_2017"` to the `BacapInstance.source` Literal in `schema.py`. No other schema change. Parsed instances get `source="iris_2017"`.
>
> **Path B (fallback, unchanged machinery, new table source):** if the dataset download fails or the files are unparseable, transcribe the generation table from the Iris et al. (2015) PDF (§ test instances — their reproduction of M&B's procedure) and run `regenerate_mb(n ∈ {20,30,40}, seed)` with `source="meisel_bierwirth_regenerated"`; data-sources.md must say "generation parameters transcribed from Iris et al. (2015), reproducing Meisel & Bierwirth (2009); not the original files; seeds S". **Never invent table values.**
>
> **Path C (last resort):** cited-deviation synthetic table — only after both downloads fail AND an author email goes unanswered; escalate to architect before building it.
>
> **Redistribution policy:** the ResearchGate dataset carries no explicit license → do **not** commit the raw files. Tests parse a hand-written 3-vessel fixture in the same format at `tests/fixtures/mb/` (as already spec'd). `load_mb_set(dir)` takes the local gitignored directory.
>
> **Solver-reality note (why n60–80 is acceptable):** these instances feed only the MILP/greedy baselines (§5 risk table) — quantum solvers run on synthetic Vuosaari instances either way. CP-SAT on n60–80 runs under a wall-clock limit reporting objective + bound gap, which is exactly how Iris et al. treat these sizes; if the archive yields the n20–40 sets too, those give exactly-solvable baseline points. If it doesn't, Path B can additionally regenerate n20–40 later without a new spec.
>
> **Citation block for docs/data-sources.md:**
> > Benchmark instances: Iris, Ç. A., Pacino, D., Ropke, S. (2017), dataset "BACAP_Benchmark_n60_n80" (ResearchGate), published with *Improved formulations and an Adaptive Large Neighborhood Search heuristic for the integrated berth allocation and quay crane assignment problem*, Transportation Research Part E. Instance lineage: Meisel, F., Bierwirth, C. (2009), TRE 45(1):196–209, doi:10.1016/j.tre.2008.03.001; format and generation documented in Iris, Pacino, Ropke, Larsen (2015), TRE 81:75–97, doi:10.1016/j.tre.2015.06.008. Files obtained from the authors' ResearchGate distribution; not redistributed in this repository.

**~~Provenance status (2026-07-16, architect)~~ (superseded, kept for history):** the paper is Meisel, F., Bierwirth, C. (2009), *Heuristics for the integration of crane productivity in the berth allocation problem*, Transportation Research Part E 45(1), 196–209, doi:10.1016/j.tre.2008.03.001. Instances were historically distributed via Bierwirth's chair page, `http://prodlog.wiwi.uni-halle.de/forschung/container/` — downloads confirmed dead 2026-07-16.

**Path A (superseded — originals unreachable).** ~~Implementer fetches the instance archive from the page above (or by author request — F. Meisel, CAU Kiel).~~ First real step: inspect the raw format and record it verbatim in `docs/data-sources.md` (column table). Expected content per vessel (per the paper): length, ETA, crane-capacity demand `m_i` (crane-hours), `r_i^min`, `r_i^max`, EST, EFT, LFT, cost rates. Mapping to our schema (now applied to the Iris 2017 files):

| M&B field | Ours | Conversion |
|---|---|---|
| quay length (1000 m) | `quay_length_m = 1000`, `berth_grid_m = 10` | their 10 m berth sections = our segments |
| 1 h periods, horizon H | `time_step_min = 60`, `time_horizon = H` | 1:1 |
| vessel length (10 m units) | `length_m = units × 10` | includes clearance already |
| ETA_i | `eta` | 1:1 (steps = hours) |
| m_i (crane-hours) | `processing_volume` | 1:1 at 60-min steps |
| r_i^min / r_i^max | `cranes_min` / `cranes_max` | 1:1 |
| EFT_i | `target_departure` | 1:1 |
| LFT_i | `latest_departure` | 1:1 |
| cost rates c¹/c²/c³, EST < ETA (speedup) | **dropped** | we fix earliest start = ETA and use `priority=1`; document as a deviation in docs/data-sources.md |

Redistribution: do **not** commit the raw archive unless its license explicitly allows; commit at most 1–2 files as test fixtures if permitted, otherwise tests parse a hand-written 3-vessel file in the same format.

**Path B (fallback): regeneration.** *(AMENDED 2026-07-16: table source is now the Iris et al. 2015 PDF — the optimization-online preprint proved unextractable and unverified; the TRE 2009 paper is inaccessible. Ordering per the amendment block above.)* Implement `regenerate_mb` from the generation procedure as reproduced in Iris et al. (2015). Structure: 3 vessel classes (feeder / medium / deep-sea) with class shares and per-class uniform ranges for length, `m_i`, `r_min/max`, and EFT/LFT slack factors; sets of 20/30/40 vessels on a 1000 m quay, 1 h periods. **The exact numeric class table must be transcribed from the paper — do not invent values.** If that PDF is also unobtainable, STOP and escalate to architect. Regenerated instances get `source="meisel_bierwirth_regenerated"` and a `docs/data-sources.md` note per the amendment block.
Edge cases: blank lines / trailing whitespace in raw files; vessels whose LFT exceeds the stated horizon (clamp is forbidden — raise).
Required tests: parser on a fixture file with hand-checked expected `BacapInstance`; malformed-file raises; (Path B) regeneration determinism per seed; every parsed/regenerated instance passes T1.1 validation.

### 4.3 T1.3 — Digitraffic calibration
Endpoints: `GET https://meri.digitraffic.fi/api/port-call/v1/port-calls` (arrivals) and the AIS vessel-metadata endpoint `GET https://meri.digitraffic.fi/api/ais/v1/vessels` (dimensions; length = refA+refB). **First implementation step:** confirm exact query-parameter names and Vuosaari's `portAreaCode` against the live OpenAPI doc (`https://meri.digitraffic.fi/swagger/`) and record them in `docs/data-sources.md`; expected filters are LOCODE `FIHEL` + date window, with Vuosaari selected by port-area code (expected `"VUOS"`) client-side if the API lacks a server-side filter. This is a lookup, not a design decision.
Client policy: `Digitraffic-User: bacap-thesis/1.0` header (API etiquette), 30 s timeout, retry/backoff per D8, respect pagination if present (follow until empty page; hard cap 10 000 calls). Data window: most recent 6 months.
Extraction per port call: ATA (fallback ETA if ATA missing → **skip the record**, don't impute), ATD, MMSI/IMO, port-area/berth code. Join length via MMSI. Fits per D6: inter-arrival hours from sorted ATAs → exponential; lengths → lognormal (clip 60–300 m); service time `(ATD−ATA)` in hours → lognormal, filtered to 2 h–7 days (outside = data error, drop and count).
Outputs: `experiments/calibration/vuosaari.json` (ArrivalCalibration), histogram+fit overlay plot `docs/figures/vuosaari-calibration.png`, attribution block in `docs/data-sources.md`:
> Arrival-pattern calibration derived from Fintraffic / Digitraffic port-call data (https://www.digitraffic.fi/en/marine-traffic/), licensed CC BY 4.0. Raw data not redistributed; only fitted distribution parameters are stored.
Edge cases: duplicate portCallId (dedupe); vessels missing from metadata join (drop, count, warn if >20% dropped — then raise); zero/negative service time (raise on fit input, not silently drop >5%).
Required tests (all against `tests/fixtures/digitraffic/` via `httpx.MockTransport`): pagination termination; retry-then-raise on persistent 500; parse+join on a fixture of ~20 calls with hand-computed expected MLE parameters (exact float compare with `pytest.approx`); `ArrivalCalibration` round-trip. Fixture recording script strips vessel names down to what tests need and truncates to ≤50 records.

### 4.4 T1.4 — generator
Algorithm (all draws from one `default_rng(seed)`, in this fixed order — order is part of the contract for determinism):
1. Lengths: `l_v = clip(round_to_5(lognormal(mu, sigma)), clip_min, clip_max)` from calibration (or `VUOSAARI_DEFAULTS: mu=ln(140), sigma=0.35, clip 60–300` — placeholder constants, overwritten by T1.3 output once available; mark with `# calibrated 20XX-XX-XX from vuosaari.json`).
2. Crane bounds by length: `<120 m → (1,2)`, `120–199 → (1,3)`, `≥200 → (2, min(4, cranes))`.
3. `processing_volume`: service-time draw `s_v` (steps, lognormal from calibration) × representative crane count `ceil((cranes_min+cranes_max)/2)`, min 1.
4. ETAs: inter-arrivals `~ Exp(λ)` with `λ = congestion × quay_length_m / mean(l_v · d_v^min)` per step (D5); `eta_v = round(cumsum)`; shift so `min(eta)=0`.
5. Due dates: `target_departure = eta + ceil(1.5 × d_v^min)`; `latest_departure = None`.
6. Priority: categorical `{1: 0.7, 2: 0.2, 3: 0.1}`.
7. `time_horizon = max(eta_v) + 3 × max(d_v^min)`; `instance_id = f"syn-n{n}-c{congestion}-s{seed}"`; validate via `BacapInstance` (construction failure = generator bug, let it raise).
Edge cases: `n_vessels=1`; `congestion` near 0 (huge horizon — cap raises `ValueError` if `time_horizon > 2000` steps, that's a mis-parameterization, not something to silently fix); vessel longer than quay impossible by clip ≤ 300 < 750.
Required tests: same seed ⇒ identical `model_dump_json`; different seed ⇒ different; every instance over a seed sweep passes validation; congestion monotonicity per D5 AC; horizon-cap raises.

### CLI (DoD hook, minimal)
`uv run python -m bacap.cli generate --n 8 --congestion 0.5 --seed 42 --out instances/` → writes `<instance_id>.json`. Thin argparse wrapper over `generate_instance` + `save_instance`; lives in `src/bacap/cli.py` (started here, extended by Phase 3's `solve`).

---

## 5. Risks

| Risk | Impact | Fallback |
|---|---|---|
| ~~M&B originals unreachable~~ **Realized 2026-07-16** — superseded by Iris 2017 dataset (Path A′, §4.2 amendment) | — | — |
| Iris 2017 ResearchGate download fails / files unparseable | T1.2 blocked | Path B: transcribe generation table from Iris et al. (2015) PDF, regenerate n20–40; then author email; Path C (cited-deviation synthetic) only after architect escalation |
| CP-SAT cannot close n60–80 instances to optimality | Baseline reports gaps, not optima | Acceptable — report objective + bound gap under a wall-clock limit (Iris et al.'s own treatment); regenerate n20–40 via Path B if exact baseline points are needed |
| M&B full grid (1000 m/10 m × ~week/1 h) is far beyond annealer capacity | Phase 2 can't run benchmarks on quantum solvers | Expected and fine: benchmarks serve the MILP/greedy baselines and small extracted subsets; quantum instances come from the generator with coarse `berth_grid_m`. Phase 2 spec must include the variable-count table before committing grid sizes |
| Digitraffic param names / Vuosaari area code differ from expectations | T1.3 client rework | Verification-first step in §4.3; client takes params as data, not hardcoded strings |
| Vuosaari sample too small in 6-month window for stable lognormal fit | Noisy calibration | Widen window to 12 months; report `n_port_calls` in the calibration file so the thesis can state sample size honestly |
| `processing_volume` derived from service time × cranes is a modeling assumption (Digitraffic has no cargo volumes) | Calibration realism | Documented assumption in docs/data-sources.md; acceptable — the field standard is synthetic volumes anyway |
| Dropping M&B speedup/cost-rate structure changes their objective | Benchmark objective values not directly comparable to the paper's | Documented deviation; we compare solvers against *each other* on these instances, not against published objective values |

## 6. Acceptance-criteria mapping

| Ticket | AC (TICKETS.md) | Where satisfied |
|---|---|---|
| T1.1 | round-trip test; 5+ validation failures | §4.1 tests (a), (b: V1–V7) |
| T1.2 | ≥1 set parsed; parser tests; provenance | §4.2 Path A/B; docs/data-sources.md |
| T1.3 | fitted dists serialized + plotted; fixture-tested client; CC BY 4.0 | §4.3 outputs + tests |
| T1.4 | seeded determinism; validation-clean; congestion knob measurable | §4.4 tests + D5 metric |
