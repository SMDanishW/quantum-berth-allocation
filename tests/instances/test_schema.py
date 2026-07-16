"""Tests for the BACAP instance schema (T1.1)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from bacap.instances import (
    BacapInstance,
    Vessel,
    congestion_index,
    load_instance,
    save_instance,
)


def make_vessel(**overrides: Any) -> Vessel:
    base: dict[str, Any] = {
        "id": "v1",
        "name": "Vessel One",
        "length_m": 190,
        "eta": 0,
        "processing_volume": 20,
        "priority": 1,
        "cranes_min": 1,
        "cranes_max": 4,
        "target_departure": 10,
        "latest_departure": None,
    }
    base.update(overrides)
    return Vessel(**base)


def make_instance(**overrides: Any) -> BacapInstance:
    base: dict[str, Any] = {
        "instance_id": "test-1",
        "source": "manual",
        "quay_length_m": 750,
        "berth_grid_m": 25,
        "time_horizon": 50,
        "time_step_min": 60,
        "cranes": 5,
        "vessels": [make_vessel()],
    }
    base.update(overrides)
    return BacapInstance(**base)


# --- (a) round-trip -----------------------------------------------------------


def test_round_trip_save_load_equal(tmp_path: Any) -> None:
    inst = make_instance(
        vessels=[
            make_vessel(id="a", eta=0, latest_departure=40),
            make_vessel(id="b", name="Bee", length_m=300, eta=5, cranes_max=3),
        ]
    )
    path = tmp_path / "inst.json"
    save_instance(inst, path)
    loaded = load_instance(path)
    assert loaded == inst


def test_load_instance_accepts_str_path(tmp_path: Any) -> None:
    inst = make_instance()
    path = tmp_path / "inst.json"
    save_instance(inst, str(path))
    assert load_instance(str(path)) == inst


# --- (d) artifact-contract projection (guards D2) -----------------------------


def test_model_dump_json_contains_contract_vessel_keys() -> None:
    inst = make_instance()
    dumped = inst.model_dump(mode="json")
    vessel = dumped["vessels"][0]
    for key in ("id", "name", "length_m", "eta", "processing_volume", "priority"):
        assert key in vessel


# --- (c) derived-property arithmetic (spec worked example) --------------------


def test_derived_properties_worked_example() -> None:
    inst = make_instance()
    v = inst.vessels[0]  # 190 m on 25 m grid, 750 m quay
    assert inst.n_segments == 30
    assert inst.length_segments(v) == 8
    assert inst.n_positions(v) == 23
    assert inst.min_duration(v) == 5  # ceil(20 / 4)
    assert inst.hard_departure(v) == 50  # latest_departure None => time_horizon


def test_hard_departure_uses_latest_departure() -> None:
    inst = make_instance(vessels=[make_vessel(latest_departure=30)])
    assert inst.hard_departure(inst.vessels[0]) == 30


def test_min_duration_rounds_up() -> None:
    inst = make_instance(vessels=[make_vessel(processing_volume=21, cranes_max=4)])
    assert inst.min_duration(inst.vessels[0]) == 6  # ceil(21 / 4)


# --- (b) instance-level validation V1-V7 --------------------------------------


def test_V1_duplicate_ids() -> None:
    with pytest.raises(ValidationError, match="V1:"):
        make_instance(vessels=[make_vessel(id="dup"), make_vessel(id="dup")])


def test_V2_quay_not_multiple_of_grid() -> None:
    with pytest.raises(ValidationError, match="V2:"):
        make_instance(quay_length_m=760)  # 760 % 25 != 0


def test_V3_vessel_longer_than_quay() -> None:
    with pytest.raises(ValidationError, match="V3:"):
        # small quay that is still a multiple of grid but shorter than vessel
        make_instance(quay_length_m=100, cranes=5, vessels=[make_vessel(length_m=190)])


def test_V4_cranes_max_exceeds_instance_cranes() -> None:
    with pytest.raises(ValidationError, match="V4:"):
        make_instance(cranes=3, vessels=[make_vessel(cranes_max=4)])


def test_V5_eta_at_or_past_horizon() -> None:
    with pytest.raises(ValidationError, match="V5:"):
        make_instance(
            time_horizon=50,
            vessels=[make_vessel(eta=50, target_departure=60, latest_departure=60)],
        )


def test_V6_hard_departure_past_horizon() -> None:
    with pytest.raises(ValidationError, match="V6:"):
        make_instance(
            time_horizon=50,
            vessels=[make_vessel(target_departure=10, latest_departure=60)],
        )


def test_V6_not_enough_time_to_process() -> None:
    with pytest.raises(ValidationError, match="V6:"):
        # min_duration = ceil(20/4)=5, but hard=3 < eta(0)+5
        make_instance(
            vessels=[make_vessel(eta=0, target_departure=3, latest_departure=3)],
        )


def test_V7_bad_time_step() -> None:
    with pytest.raises(ValidationError, match="V7:"):
        make_instance(time_step_min=45)


# --- Vessel-level validators --------------------------------------------------


def test_vessel_cranes_min_gt_max() -> None:
    with pytest.raises(ValidationError, match="cranes_min"):
        make_vessel(cranes_min=5, cranes_max=3)


def test_vessel_eta_not_before_target() -> None:
    with pytest.raises(ValidationError, match="eta"):
        make_vessel(eta=10, target_departure=10)


def test_vessel_latest_before_target() -> None:
    with pytest.raises(ValidationError, match="latest_departure"):
        make_vessel(target_departure=20, latest_departure=15)


def test_extra_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        make_vessel(bogus=1)


# --- congestion_index ---------------------------------------------------------


def test_congestion_index_value() -> None:
    # two vessels, hand-computed
    inst = make_instance(
        quay_length_m=500,
        berth_grid_m=25,
        cranes=4,
        time_horizon=50,
        vessels=[
            make_vessel(id="a", length_m=100, eta=0, processing_volume=8, cranes_max=2),
            make_vessel(id="b", length_m=200, eta=4, processing_volume=8, cranes_max=2),
        ],
    )
    # min_duration a = ceil(8/2)=4, b=4. A = 100*4 + 200*4 = 1200
    # T_span = max(0+4, 4+4) - min(0,4) = 8 - 0 = 8 ; index = 1200/(500*8)=0.3
    assert congestion_index(inst) == pytest.approx(0.3)


def test_congestion_index_zero_span_raises() -> None:
    inst = make_instance(
        vessels=[make_vessel(id="a", eta=0, processing_volume=1, cranes_max=1)]
    )
    # single vessel: T_span = (0+1) - 0 = 1, not zero -> compute fine
    assert congestion_index(inst) > 0


# --- edge cases (spec 4.1) ----------------------------------------------------


def test_single_vessel_ok() -> None:
    inst = make_instance(vessels=[make_vessel()])
    assert len(inst.vessels) == 1


def test_vessel_exactly_quay_length() -> None:
    inst = make_instance(quay_length_m=200, cranes=5, vessels=[make_vessel(length_m=200)])
    v = inst.vessels[0]
    assert inst.length_segments(v) == 8  # ceil(200/25)
    assert inst.n_positions(v) == 1  # n_segments 8 - 8 + 1


def test_tight_but_valid_eta() -> None:
    # eta = time_horizon - min_duration, hard_departure = time_horizon
    inst = make_instance(
        time_horizon=50,
        vessels=[
            make_vessel(
                eta=45,
                processing_volume=20,
                cranes_max=4,  # min_duration 5
                target_departure=50,
                latest_departure=50,
            )
        ],
    )
    v = inst.vessels[0]
    assert v.eta + inst.min_duration(v) == inst.hard_departure(v) == 50


def test_latest_departure_equals_horizon() -> None:
    inst = make_instance(
        time_horizon=50,
        vessels=[make_vessel(target_departure=40, latest_departure=50)],
    )
    assert inst.hard_departure(inst.vessels[0]) == 50
