"""Meisel & Bierwirth (2009) benchmark — Path B regeneration (T1.2).

The original M&B instance files are unreachable and the Iris (2017) dataset
could not be obtained either, so per the architect's fallback ordering the
benchmark is *regenerated* from M&B's published generation scheme rather than
parsed from files. Parameters are grounded in the primary source, Meisel &
Bierwirth (2009), Transportation Research Part E 45(1) — §7.2 (pp.10-11), the
Table 3 class table, and the example vessel Table 1 (p.6). Correcher (2019) and
Bogerd (2019) are corroborating only (see ``docs/data-sources.md`` for full
provenance and documented deviations).

Due-date semantics (primary-source correction, amends the pre-amendment
regeneration — regenerated instances therefore DIFFER from earlier ones):

- ``target_departure`` (EFT, earliest finishing time) = ``eta + min_duration``.
  M&B state no EFT prose rule; the example Table 1 (p.6) fixes it arithmetically
  (vessel 3: m=5, r_max=3 -> d_min=ceil(5/3)=2; ETA=4, EFT=6=4+2).
- ``latest_departure`` (LFT, the hard deadline) = ``eta + ceil(1.5 x min_duration)``.
  §7.2 verbatim: "The latest finishing time LFT of a vessel is derived by adding
  1.5 times a vessel's minimum handling time to ETA_i." ``ceil`` keeps it on the
  integer grid (documented deviation). The 1.5 rule is the LFT, NOT the EFT/due
  date — the earlier wiring followed Correcher's phrasing which conflates the two.

with ``min_duration = ceil(m_i / cranes_max)``.

Determinism contract: one ``numpy.random.default_rng(seed)`` per instance, with
a fixed draw order. Classes are assigned deterministically (exact 60/30/10
counts, feeder block then medium then jumbo); then, per vessel in that order,
the rng draws length, crane-hours (m_i), then eta. Same seed => byte-identical
``model_dump_json``.
"""

from __future__ import annotations

import math
from typing import Literal, NamedTuple

import numpy as np

from bacap.instances.schema import BacapInstance, Vessel

# --- Terminal constants (M&B "GenMB-10m"): quay 1000 m in 10 m sections, 10
# cranes, 1 h periods, horizon 210 steps. Source: Correcher & Alvarez-Valdes
# et al., EJOR 2019, preprint §7.1 pp.22-23; Bogerd (2019) Appendix Table 1 p.25.
QUAY_LENGTH_M = 1000
BERTH_GRID_M = 10
CRANES = 10
TIME_STEP_MIN = 60
TIME_HORIZON = 210
ETA_HI = 168  # eta ~ U[0, 168] integer inclusive; 210-168 tail avoids infeasibility

# 1.5 x min handling time = M&B's latest finishing time (LFT), §7.2 verbatim:
# "adding 1.5 times a vessel's minimum handling time to ETA_i"; ceil keeps it on
# the grid. This is the HARD deadline (latest_departure), not the EFT/due date.
LFT_FACTOR = 1.5


class _ClassSpec(NamedTuple):
    name: str
    len_lo: int  # length in 10 m units, inclusive
    len_hi: int
    mi_lo: int  # crane-hours m_i, inclusive
    mi_hi: int
    cranes_min: int
    cranes_max: int


# Vessel classes transcribed from the sources above (integer uniform, inclusive
# bounds; length_m = draw x 10; processing_volume = m_i at 60-min steps).
_FEEDER = _ClassSpec("Feeder", 8, 21, 5, 15, 1, 2)
_MEDIUM = _ClassSpec("Medium", 21, 30, 15, 50, 2, 4)
_JUMBO = _ClassSpec("Jumbo", 30, 40, 50, 65, 4, 6)

# Class shares within each instance: 60% Feeder / 30% Medium / 10% Jumbo.
_SHARES = (0.6, 0.3, 0.1)

# Number of derived instances per size in a full set (10 seeds x 3 sizes = 30).
_SET_SEEDS = 10
_SET_SIZES: tuple[Literal[20, 30, 40], ...] = (20, 30, 40)


def _class_sequence(n_vessels: int) -> list[_ClassSpec]:
    """Deterministic class list: exact 60/30/10 counts, feeder->medium->jumbo."""
    n_feeder = round(n_vessels * _SHARES[0])
    n_medium = round(n_vessels * _SHARES[1])
    n_jumbo = n_vessels - n_feeder - n_medium
    return [_FEEDER] * n_feeder + [_MEDIUM] * n_medium + [_JUMBO] * n_jumbo


def regenerate_mb(n_vessels: Literal[20, 30, 40], seed: int) -> BacapInstance:
    """Regenerate one M&B-scheme instance of ``n_vessels`` vessels.

    Draw order per vessel (determinism contract): length, m_i, eta. Constructs
    through ``BacapInstance`` validation — a validation failure is a generator
    bug and is allowed to raise.
    """
    rng = np.random.default_rng(seed)
    vessels: list[Vessel] = []
    for i, spec in enumerate(_class_sequence(n_vessels), start=1):
        length_units = int(rng.integers(spec.len_lo, spec.len_hi + 1))
        m_i = int(rng.integers(spec.mi_lo, spec.mi_hi + 1))
        eta = int(rng.integers(0, ETA_HI + 1))
        min_duration = math.ceil(m_i / spec.cranes_max)
        target_departure = eta + min_duration  # EFT (example Table 1, p.6)
        latest_departure = eta + math.ceil(LFT_FACTOR * min_duration)  # LFT (§7.2)
        vessels.append(
            Vessel(
                id=f"v{i:02d}",
                name=f"{spec.name} {i:02d}",
                length_m=length_units * BERTH_GRID_M,
                eta=eta,
                processing_volume=m_i,
                priority=1,
                cranes_min=spec.cranes_min,
                cranes_max=spec.cranes_max,
                target_departure=target_departure,
                latest_departure=latest_departure,
            )
        )
    return BacapInstance(
        instance_id=f"mb-regen-n{n_vessels}-s{seed}",
        source="meisel_bierwirth_regenerated",
        quay_length_m=QUAY_LENGTH_M,
        berth_grid_m=BERTH_GRID_M,
        time_horizon=TIME_HORIZON,
        time_step_min=TIME_STEP_MIN,
        cranes=CRANES,
        vessels=vessels,
    )


def regenerate_mb_set(seed: int) -> list[BacapInstance]:
    """The 30-instance set: 10 seeds (derived from ``seed``) x sizes 20/30/40."""
    child_seeds = np.random.SeedSequence(seed).generate_state(_SET_SEEDS)
    return [
        regenerate_mb(n, int(child))
        for child in child_seeds
        for n in _SET_SIZES
    ]
