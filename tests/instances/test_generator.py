"""T1.4 — generator tests (spec §4.4 "Required tests")."""

from __future__ import annotations

import math
import subprocess
import sys

import pytest

from bacap.cli import main
from bacap.instances.generator import (
    LENGTH_CLIP_MAX,
    LENGTH_CLIP_MIN,
    LENGTH_ROUNDING_M,
    MAX_TIME_HORIZON,
    generate_instance,
)
from bacap.instances.schema import congestion_index, load_instance


def test_same_seed_identical_json() -> None:
    a = generate_instance(8, 0.5, seed=42)
    b = generate_instance(8, 0.5, seed=42)
    assert a.model_dump_json() == b.model_dump_json()


def test_different_seed_differs() -> None:
    a = generate_instance(8, 0.5, seed=42)
    b = generate_instance(8, 0.5, seed=43)
    assert a.model_dump_json() != b.model_dump_json()


@pytest.mark.parametrize("seed", range(20))
def test_seed_sweep_validates(seed: int) -> None:
    # Construction IS the validation (V1-V7 run in the model validator).
    inst = generate_instance(10, 0.5, seed=seed)
    assert len(inst.vessels) == 10
    assert min(v.eta for v in inst.vessels) == 0


def test_congestion_monotonicity() -> None:
    """D5 AC: mean congestion_index strictly increases across {0.3, 0.5, 0.7}."""
    means = [
        sum(congestion_index(generate_instance(10, rho, seed=s)) for s in range(20)) / 20
        for rho in (0.3, 0.5, 0.7)
    ]
    assert means[0] < means[1] < means[2], means


def test_horizon_cap_raises() -> None:
    with pytest.raises(ValueError, match="MAX_TIME_HORIZON"):
        generate_instance(20, 0.001, seed=1)


def test_single_vessel() -> None:
    inst = generate_instance(1, 0.5, seed=7)
    (v,) = inst.vessels
    assert v.eta == 0
    assert inst.time_horizon == 3 * inst.min_duration(v)


@pytest.mark.parametrize("seed", range(10))
def test_draws_respect_calibration_ranges(seed: int) -> None:
    inst = generate_instance(12, 0.5, seed=seed)
    for v in inst.vessels:
        assert LENGTH_CLIP_MIN <= v.length_m <= LENGTH_CLIP_MAX
        assert v.length_m % LENGTH_ROUNDING_M == 0
        assert v.processing_volume >= 1
        assert 1 <= v.cranes_min <= v.cranes_max <= inst.cranes
        assert v.priority in {1, 2, 3}
        assert v.latest_departure is None
        assert v.target_departure == v.eta + math.ceil(1.5 * inst.min_duration(v))
    assert inst.time_horizon <= MAX_TIME_HORIZON


def test_cli_generate_writes_loadable_instance(tmp_path) -> None:  # type: ignore[no-untyped-def]
    main(["generate", "--n", "8", "--congestion", "0.5", "--seed", "42", "--out", str(tmp_path)])
    path = tmp_path / "syn-n8-c0.5-s42.json"
    assert load_instance(path).model_dump_json() == generate_instance(8, 0.5, 42).model_dump_json()


def test_cli_module_entrypoint(tmp_path) -> None:  # type: ignore[no-untyped-def]
    proc = subprocess.run(
        [sys.executable, "-m", "bacap.cli", "generate", "--n", "3",
         "--congestion", "0.5", "--seed", "1", "--out", str(tmp_path)],
        capture_output=True, text=True, check=True,
    )
    assert load_instance(proc.stdout.strip()).instance_id == "syn-n3-c0.5-s1"
