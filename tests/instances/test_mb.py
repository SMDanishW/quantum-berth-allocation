"""Tests for the regenerated Meisel & Bierwirth benchmark (T1.2, Path B)."""

from __future__ import annotations

import math
import re

import numpy as np
import pytest

from bacap.instances import BacapInstance, regenerate_mb, regenerate_mb_set
from bacap.instances.meisel_bierwirth import _FEEDER, _JUMBO, _MEDIUM, _ClassSpec

_SIZES = (20, 30, 40)
# exact class counts per size (60/30/10), keyed by (cranes_min, cranes_max)
_EXPECTED_COUNTS: dict[int, dict[tuple[int, int], int]] = {
    20: {(1, 2): 12, (2, 4): 6, (4, 6): 2},
    30: {(1, 2): 18, (2, 4): 9, (4, 6): 3},
    40: {(1, 2): 24, (2, 4): 12, (4, 6): 4},
}
_LEN_RANGE = {  # length_m bounds per (cranes_min, cranes_max) class signature
    (1, 2): (80, 210),
    (2, 4): (210, 300),
    (4, 6): (300, 400),
}
_MI_RANGE = {(1, 2): (5, 15), (2, 4): (15, 50), (4, 6): (50, 65)}


def _sig(v: object) -> tuple[int, int]:
    return (v.cranes_min, v.cranes_max)  # type: ignore[attr-defined]


# (1) determinism
def test_same_seed_identical() -> None:
    assert (
        regenerate_mb(20, 7).model_dump_json()
        == regenerate_mb(20, 7).model_dump_json()
    )


def test_different_seed_differs() -> None:
    assert (
        regenerate_mb(20, 7).model_dump_json()
        != regenerate_mb(20, 8).model_dump_json()
    )


def test_set_is_deterministic() -> None:
    a = [i.model_dump_json() for i in regenerate_mb_set(42)]
    b = [i.model_dump_json() for i in regenerate_mb_set(42)]
    assert a == b


# (2) set structure: 30 instances, all valid, exact class counts
def test_set_size_and_ids_unique() -> None:
    instances = regenerate_mb_set(42)
    assert len(instances) == 30
    assert all(isinstance(i, BacapInstance) for i in instances)  # construction == validation
    assert len({i.instance_id for i in instances}) == 30
    assert sorted(len(i.vessels) for i in instances) == sorted(_SIZES * 10)


@pytest.mark.parametrize("n", _SIZES)
def test_class_counts(n: int) -> None:
    inst = regenerate_mb(n, 3)
    counts: dict[tuple[int, int], int] = {}
    for v in inst.vessels:
        counts[_sig(v)] = counts.get(_sig(v), 0) + 1
    assert counts == _EXPECTED_COUNTS[n]


# (3) all drawn values within transcribed ranges
def test_values_within_ranges() -> None:
    for inst in regenerate_mb_set(99):
        for v in inst.vessels:
            lo, hi = _LEN_RANGE[_sig(v)]
            assert lo <= v.length_m <= hi
            mlo, mhi = _MI_RANGE[_sig(v)]
            assert mlo <= v.processing_volume <= mhi
            assert 0 <= v.eta <= 168


# (4) EFT (target_departure) and LFT (latest_departure) formulas spot-checked
@pytest.mark.parametrize("spec", [_FEEDER, _MEDIUM, _JUMBO])
def test_due_date_formula(spec: _ClassSpec) -> None:
    inst = regenerate_mb(20, 5)
    v = next(x for x in inst.vessels if _sig(x) == (spec.cranes_min, spec.cranes_max))
    min_duration = math.ceil(v.processing_volume / v.cranes_max)
    assert v.target_departure == v.eta + min_duration  # EFT (example Table 1, p.6)
    assert v.latest_departure == v.eta + math.ceil(1.5 * min_duration)  # LFT (§7.2)


def test_due_date_known_draw() -> None:
    # Reproduce the exact first (feeder) vessel draw order: length, m_i, eta.
    rng = np.random.default_rng(5)
    _ = int(rng.integers(_FEEDER.len_lo, _FEEDER.len_hi + 1))  # length
    m_i = int(rng.integers(_FEEDER.mi_lo, _FEEDER.mi_hi + 1))
    eta = int(rng.integers(0, 169))
    min_duration = math.ceil(m_i / _FEEDER.cranes_max)
    v0 = regenerate_mb(20, 5).vessels[0]
    assert v0.target_departure == eta + min_duration
    assert v0.latest_departure == eta + math.ceil(1.5 * min_duration)


# (4b) V6 safety: LFT must never exceed the planning horizon across the full set
def test_latest_departure_within_horizon() -> None:
    for inst in regenerate_mb_set(99):
        for v in inst.vessels:
            assert v.latest_departure is not None
            assert v.latest_departure <= inst.time_horizon


# (5) source literal + instance_id / vessel id format
def test_source_and_id_format() -> None:
    inst = regenerate_mb(30, 11)
    assert inst.source == "meisel_bierwirth_regenerated"
    assert inst.instance_id == "mb-regen-n30-s11"
    assert all(re.fullmatch(r"v\d{2}", v.id) for v in inst.vessels)
    assert inst.vessels[0].id == "v01"
