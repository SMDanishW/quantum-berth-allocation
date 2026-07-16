# Data Sources

## Meisel & Bierwirth benchmark — regenerated (Path B, T1.2)

**Status: regenerated per Meisel & Bierwirth (2009), NOT the original files.**
The original M&B instance files were unreachable (prodlog downloads dead, TRE
2009 paper inaccessible), and the Iris et al. (2017) "BACAP_Benchmark_n60_n80"
dataset (architect's preferred Path A′) could not be obtained either. Per the
architect's fallback ordering, the benchmark is therefore *regenerated* from
M&B's published generation scheme via `regenerate_mb` / `regenerate_mb_set`
(`src/bacap/instances/meisel_bierwirth.py`), with `source =
"meisel_bierwirth_regenerated"`. A file parser (`parse_mb_file` / `load_mb_set`)
is **deferred** and intentionally not implemented until the Iris dataset (or the
original files) is obtained.

### Citations

- **PRIMARY source (scheme + parameters):** Meisel, F., Bierwirth, C. (2009),
  *Heuristics for the integration of crane productivity in the berth allocation
  problem*, Transportation Research Part E 45(1), 196–209,
  doi:10.1016/j.tre.2008.03.001. Local PDF:
  `docs/data/1-s2.0-S1366554508000768-main.pdf`. Generation scheme §7.2
  (pp.10–11); vessel class table Table 3; worked example Table 1 (p.6).
- **Corroborating:** Correcher, J. F., Alvarez-Valdes, R., et al. (2019),
  *New exact methods for the time-invariant berth allocation and quay crane
  assignment problem*, EJOR — open preprint §7.1 pp.22–23, scheme "GenMB-10m":
  https://optimization-online.org/wp-content/uploads/2017/03/BACAP_MILP_preprint.pdf
  (Note: Correcher phrases the due date as "desired departure = a_i + 1.5 × min
  handling time", which conflates M&B's *latest* finishing time (LFT) with the
  due date; our pre-amendment wiring followed that phrasing — now corrected to
  M&B §7.2, where 1.5 × min handling is explicitly the LFT hard deadline.)
- **Corroborating:** Bogerd, F. (2019) MSc thesis, Appendix Table 1, p.25
  (identical class table); Iris, Ç. A., Pacino, D., Ropke, S., Larsen, A.
  (2015), *Integrated Berth Allocation and Quay Crane Assignment Problem: Set
  partitioning models and computational results*, TRE 81:75–97,
  doi:10.1016/j.tre.2015.06.008, §5.1 (original set structure: 30 instances,
  10 each of n=20/30/40).

### Transcribed generation scheme (authoritative)

Terminal: quay 1000 m in 10 m sections (`quay_length_m=1000`, `berth_grid_m=10`);
`cranes=10`; `time_step_min=60`; `time_horizon=210` steps.
Arrival window: `eta ~ U[0, 168]` integer, inclusive. M&B §7.2 draws ETA uniform
over a planning horizon `H=168` (hard) and discards instances their construction
heuristic cannot solve (a feasibility filter). We do **not** replicate that
filter; instead we widen the horizon to 210 (Correcher's workaround) so the
210−168 tail absorbs the extra finishing time and no instance is infeasible.

Class shares within each instance: 60% Feeder / 30% Medium / 10% Jumbo
(exact counts: n=20 → 12/6/2, n=30 → 18/9/3, n=40 → 24/12/4).

| Class  | length (10 m units) | crane-hours m_i | cranes_min | cranes_max |
|--------|---------------------|-----------------|------------|------------|
| Feeder | U[8, 21]            | U[5, 15]        | 1          | 2          |
| Medium | U[21, 30]           | U[15, 50]       | 2          | 4          |
| Jumbo  | U[30, 40]           | U[50, 65]       | 4          | 6          |

(integer uniform, inclusive bounds; `length_m = draw × 10`;
`processing_volume = m_i` 1:1 at 60-min steps.)

Finishing times, with `min_duration = ceil(m_i / cranes_max)`:

- `target_departure` (EFT) = `eta + min_duration`. M&B state no EFT prose rule;
  the worked example Table 1 (p.6) fixes it arithmetically (vessel 3: m=5,
  r_max=3 → d_min=ceil(5/3)=2; ETA=4, EFT=6=4+2).
- `latest_departure` (LFT, hard deadline) = `eta + ceil(1.5 × min_duration)`.
  M&B §7.2 verbatim: "The latest finishing time LFT of a vessel is derived by
  adding 1.5 times a vessel's minimum handling time to ETA_i." `ceil` keeps it
  on the integer grid.

**Determinism contract:** one `numpy.random.default_rng(seed)` per instance.
Classes are assigned deterministically (exact counts above, feeder block →
medium → jumbo); then per vessel, in order, the rng draws length, m_i, then eta.
Same seed ⇒ byte-identical JSON. `regenerate_mb_set(seed)` derives 10 child
seeds from the base seed via `numpy.random.SeedSequence(seed).generate_state(10)`
and produces 30 instances (10 seeds × sizes 20/30/40). `instance_id` format:
`mb-regen-n{n}-s{seed}`; vessel ids `v01`, `v02`, …

### Documented deviations

- **EFT rule not stated in prose**: M&B §7.2 gives no formula for the earliest
  finishing time. We infer `EFT = eta + min_duration` from the worked example
  Table 1 (p.6), which is arithmetically consistent with it.
- **`ceil` rounding on the 1.5 LFT factor**: `ceil(1.5 × min_duration)` keeps
  `latest_departure` on the integer grid; the underlying continuous criterion
  would not round.
- **Horizon widened 168 → 210**: M&B use `H=168` (hard) plus a construction-
  heuristic feasibility filter that discards unsolvable instances. We do not
  replicate that filter; 210 (Correcher's workaround) is the tail that keeps
  every regenerated instance feasible.
- **Dropped fields** (per spec §4.2 mapping): desired berth position
  `U[0, L−l_i]`; cost rates (uniform Cw=1000 / Cd=2000 / Cp=200 in the
  preprint, per-class c1/c2/c3 in Bogerd); speedup / EST (`EST=ceil(0.9·ETA)`).
  `priority=1` for all vessels. We compare solvers against each other on these
  instances, not against the paper's published objective values.
- **Deterministic class-block draw order**: classes are assigned in fixed blocks
  (feeder → medium → jumbo, exact 60/30/10 counts) rather than drawn randomly,
  so a seed yields byte-identical JSON.
- **Seed derivation for the 30-instance set**: 10 child seeds via
  `numpy.random.SeedSequence(seed).generate_state(10)`, not M&B's original file
  numbering.

Regenerated instances **differ from pre-amendment regenerations**: this
amendment shifts `target_departure` (was `eta + ceil(1.5·min_duration)`, now
`eta + min_duration`) and populates `latest_departure` (was `None`).

## Digitraffic port-call API (T1.3)

**Attribution (verbatim, per spec §4.3):**

> Arrival-pattern calibration derived from Fintraffic / Digitraffic port-call
> data (https://www.digitraffic.fi/en/marine-traffic/), licensed CC BY 4.0. Raw
> data not redistributed; only fitted distribution parameters are stored.

### Step-0 verification (against the live OpenAPI, 2026-07-16)

Confirmed against `https://meri.digitraffic.fi/swagger/openapi.json` (the swagger
UI is a JS app; the OpenAPI JSON is the machine-readable source). Cross-checked
the endpoint shapes against the user's own `SMDanishW/maritime-intelligence`
repo, which uses the same `meri.digitraffic.fi` port-call + AIS vessel endpoints.

**Port calls — `GET /api/port-call/v1/port-calls`**
- Query params (verified): `date`, `from`, `to`, `etaFrom/etaTo`, `ataFrom/ataTo`,
  `etdFrom/etdTo`, `atdFrom/atdTo`, `locode`, `vesselName`, `mmsi`, `imo`,
  `nationality`, `vesselTypeCode`. We use `locode=FIHEL` + `ataFrom` + `ataTo`
  (ISO-8601 with `Z`).
- Response: `{ "dataUpdatedTime", "portCalls": [ { portCallId, mmsi, imoLloyds,
  vesselName, vesselTypeCode, portAreaDetails: [ { ata, atd, eta, portAreaCode,
  berthCode, berthName, portAreaName, … } ] } ] }`. ATA/ATD live inside
  `portAreaDetails[]`, not on the call.
- **No server-side pagination cursor** — a date range returns all matching calls
  in one payload. The client (`fetch_port_calls`) windows the requested range into
  ≤30-day sub-requests (rate-limit friendly, bounded), concatenates, dedupes by
  `portCallId`, hard cap 10 000. Server always gzips; `httpx` decodes transparently
  (raw `urllib` needs manual `gzip.decompress`).

**Vuosaari port-area code = `VUOS`** (name "Vuosaaren satama"), obtained from
`GET /api/port-call/v1/ports/FIHEL` → `portAreas.features[].portAreaCode`. (The
`portAreaCode` "VTL" is "Vuosaari, telakka" = the shipyard, deliberately excluded.)
The spec's expected `"VUOS"` is confirmed exactly.

**AIS vessel metadata — `GET /api/ais/v1/vessels`**
- Returns a flat array of `{ mmsi, referencePointA, referencePointB,
  referencePointC, referencePointD, imo, name, shipType, draught, … }`.
- **Vessel length = `referencePointA + referencePointB`** (bow + stern distances
  from the AIS reference point), per spec.
- Etiquette header `Digitraffic-User: bacap-thesis/1.0`, 30 s timeout, D8 retry
  (3 retries after the initial attempt, backoff 1/2/4 s; retry only on transport
  timeout / 5xx, 4xx fails loud immediately).

### AIS-snapshot join limitation (verified deviation from spec §4.3)

`/api/ais/v1/vessels` is a **live snapshot** of currently/recently tracked
vessels (~1100 near Finland), whereas port calls span months. Measured on
2026-07-16, a **structural ~30 % of Vuosaari port-call MMSIs are absent from the
AIS snapshot**, and this is stable across windows (30 d: 29 %, 90 d: 32 %,
180 d: 33 %) — i.e. not temporal decay but genuinely untracked craft (tugs, small
craft, `mmsi=0`, vessels outside AIS range). The spec's 20 % join-drop **raise**
threshold assumed near-complete coverage and makes calibration impossible against
the real data. Per the ticket's "proceed with verified reality" authority, the
guard is relaxed to **50 %** (`JOIN_DROP_RAISE_FRAC`) — it still fails loud on
catastrophic join failure (wrong endpoint → ~100 % miss) but tolerates the
structural ~30 %. The length distribution is therefore fitted on the ~70 % of
arrivals that carry AIS dimensions — the larger, AIS-tracked cargo ships, which is
exactly the population a container-terminal calibration wants; the dropped ~30 %
are small untracked craft we would exclude anyway (length filter is 60–300 m).

### `processing_volume` modeling assumption

Digitraffic carries no cargo/crane volumes, so `processing_volume` is not
calibrated directly. The **service time** `(ATD − ATA)` in hours is fitted
(lognormal); the generator (T1.4) turns a service-time draw into
`processing_volume` via a representative crane count (spec §4.4 step 3). Documented
field-standard assumption (spec risk table).

### Achieved calibration (real run, 2026-07-16)

`scripts/calibrate_vuosaari.py` → `experiments/calibration/vuosaari.json`
(committed — fitted parameters only, no raw data) and
`docs/figures/vuosaari-calibration.png` (histogram + fitted-density overlay).

- Window: **2026-01-18 → 2026-07-16** (most recent 6 months; sufficient, no need
  to widen to 12).
- **n_port_calls = 982** VUOS calls with a valid ATA (after dedupe).
- Inter-arrival: exponential, `rate_per_hour = 0.227` (mean ≈ 4.4 h between arrivals).
- Vessel length: lognormal, `mu = 5.246`, `sigma = 0.103` (median ≈ 190 m), clipped 60–300 m.
- Service time (60-min steps): lognormal, `mu = 2.571`, `sigma = 0.831` (median ≈ 13 h).

Raw responses are never committed. Deterministic unit tests use hand-built,
truncated fixtures (`tests/fixtures/digitraffic/port_calls_fit.json`,
`vessels_fit.json`, ≤50 records) with independently hand-computed MLE parameters,
served via `httpx.MockTransport` — no live HTTP in the test suite.
`scripts/record_digitraffic_fixtures.py` is a one-off recorder (not run in CI, its
output not committed).
