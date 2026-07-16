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

- **Scheme origin:** Meisel, F., Bierwirth, C. (2009), *Heuristics for the
  integration of crane productivity in the berth allocation problem*,
  Transportation Research Part E 45(1), 196–209, doi:10.1016/j.tre.2008.03.001.
- **Parameter source (transcribed):** Correcher, J. F., Alvarez-Valdes, R.,
  et al. (2019), *New exact methods for the time-invariant berth allocation and
  quay crane assignment problem*, EJOR — open preprint §7.1 pp.22–23, scheme
  "GenMB-10m":
  https://optimization-online.org/wp-content/uploads/2017/03/BACAP_MILP_preprint.pdf
- **Corroborating:** Bogerd, F. (2019) MSc thesis, Appendix Table 1, p.25
  (identical class table); Iris, Ç. A., Pacino, D., Ropke, S., Larsen, A.
  (2015), *Integrated Berth Allocation and Quay Crane Assignment Problem: Set
  partitioning models and computational results*, TRE 81:75–97,
  doi:10.1016/j.tre.2015.06.008, §5.1 (original set structure: 30 instances,
  10 each of n=20/30/40).

### Transcribed generation scheme (authoritative)

Terminal: quay 1000 m in 10 m sections (`quay_length_m=1000`, `berth_grid_m=10`);
`cranes=10`; `time_step_min=60`; `time_horizon=210` steps.
Arrival window: `eta ~ U[0, 168]` integer, inclusive (the 210−168 tail prevents
infeasibility per the preprint).

Class shares within each instance: 60% Feeder / 30% Medium / 10% Jumbo
(exact counts: n=20 → 12/6/2, n=30 → 18/9/3, n=40 → 24/12/4).

| Class  | length (10 m units) | crane-hours m_i | cranes_min | cranes_max |
|--------|---------------------|-----------------|------------|------------|
| Feeder | U[8, 21]            | U[5, 15]        | 1          | 2          |
| Medium | U[21, 30]           | U[15, 50]       | 2          | 4          |
| Jumbo  | U[30, 40]           | U[50, 65]       | 4          | 6          |

(integer uniform, inclusive bounds; `length_m = draw × 10`;
`processing_volume = m_i` 1:1 at 60-min steps.)

Due date: `target_departure = eta + ceil(1.5 × min_duration)` where
`min_duration = ceil(m_i / cranes_max)`. The 1.5 factor is M&B's criterion
quoted verbatim in the preprint ("s_i = a_i + 1.5 × min handling time").

**Determinism contract:** one `numpy.random.default_rng(seed)` per instance.
Classes are assigned deterministically (exact counts above, feeder block →
medium → jumbo); then per vessel, in order, the rng draws length, m_i, then eta.
Same seed ⇒ byte-identical JSON. `regenerate_mb_set(seed)` derives 10 child
seeds from the base seed via `numpy.random.SeedSequence(seed).generate_state(10)`
and produces 30 instances (10 seeds × sizes 20/30/40). `instance_id` format:
`mb-regen-n{n}-s{seed}`; vessel ids `v01`, `v02`, …

### Documented deviations

- **`latest_departure = None`** (hard bound falls to horizon 210): M&B's LFT rule
  is not stated in any accessible source. Documented deviation.
- **`ceil` rounding on the 1.5 due-date factor**: `ceil(1.5 × min_duration)` keeps
  `target_departure` on the integer grid; the underlying continuous criterion
  would not round.
- **Dropped fields** (per spec §4.2 mapping): desired berth position
  `U[1, L+1−l_i]`; cost rates (uniform Cw=1000 / Cd=2000 / Cp=200 in the
  preprint, per-class c1/c2/c3 in Bogerd); speedup / EST. `priority=1` for all
  vessels. We compare solvers against each other on these instances, not against
  the paper's published objective values.

## Digitraffic port-call API (T1.3)

Placeholder — populated in T1.3. Arrival-pattern calibration will derive from
Fintraffic / Digitraffic port-call data
(https://www.digitraffic.fi/en/marine-traffic/), licensed CC BY 4.0. Raw data
not redistributed; only fitted distribution parameters are stored.
