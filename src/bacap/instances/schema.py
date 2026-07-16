"""Canonical BACAP instance schema, (de)serialization, and congestion metric.

Units are locked by Phase 1 spec D1: time in integer grid steps, space in
meters, berth segments derived. All models are frozen and int-only, so JSON
round-trips are exact. Validators raise with a rule number in the message
(``V1:`` .. ``V7:``) so tests can grep the specific failure.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Vessel(BaseModel):
    """A single vessel to berth. Frozen; extra fields rejected."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)  # unique within instance
    name: str
    length_m: int = Field(gt=0)  # INCLUDES safety clearance (M&B convention)
    eta: int = Field(ge=0)  # earliest berthing, in time steps
    processing_volume: int = Field(gt=0)  # crane-steps (D1/D3)
    priority: int = Field(default=1, ge=1)  # tardiness weight multiplier
    cranes_min: int = Field(default=1, ge=1)
    cranes_max: int = Field(ge=1)
    target_departure: int = Field(gt=0)  # soft due date, steps
    latest_departure: int | None = None  # hard; None => time_horizon

    @model_validator(mode="after")
    def _check_vessel(self) -> Self:
        if self.cranes_min > self.cranes_max:
            raise ValueError(
                f"vessel {self.id!r}: cranes_min ({self.cranes_min}) must be "
                f"<= cranes_max ({self.cranes_max})"
            )
        if self.eta >= self.target_departure:
            raise ValueError(
                f"vessel {self.id!r}: eta ({self.eta}) must be "
                f"< target_departure ({self.target_departure})"
            )
        if self.latest_departure is not None and self.latest_departure < self.target_departure:
            raise ValueError(
                f"vessel {self.id!r}: latest_departure ({self.latest_departure}) must be "
                f">= target_departure ({self.target_departure})"
            )
        return self


class BacapInstance(BaseModel):
    """A full BACAP instance: quay, time grid, cranes, and vessels."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    instance_id: str
    source: Literal[
        "synthetic",
        "meisel_bierwirth",
        "meisel_bierwirth_regenerated",
        "manual",
    ]
    quay_length_m: int = Field(gt=0)
    berth_grid_m: int = Field(gt=0)
    time_horizon: int = Field(gt=0)  # number of steps; grid t = 0..time_horizon-1
    time_step_min: int = Field(gt=0)
    cranes: int = Field(ge=1)  # identical, on one rail
    vessels: list[Vessel] = Field(min_length=1)

    # --- derived, pure, no state ---
    @property
    def n_segments(self) -> int:
        return self.quay_length_m // self.berth_grid_m

    def length_segments(self, v: Vessel) -> int:
        return math.ceil(v.length_m / self.berth_grid_m)

    def n_positions(self, v: Vessel) -> int:
        return self.n_segments - self.length_segments(v) + 1

    def min_duration(self, v: Vessel) -> int:
        return math.ceil(v.processing_volume / v.cranes_max)

    def hard_departure(self, v: Vessel) -> int:
        return v.latest_departure if v.latest_departure is not None else self.time_horizon

    @model_validator(mode="after")
    def _check_instance(self) -> Self:
        ids = [v.id for v in self.vessels]
        if len(set(ids)) != len(ids):
            raise ValueError(f"V1: vessel ids must be unique (got {ids})")
        if self.quay_length_m % self.berth_grid_m != 0:
            raise ValueError(
                f"V2: quay_length_m ({self.quay_length_m}) must be a multiple of "
                f"berth_grid_m ({self.berth_grid_m})"
            )
        for v in self.vessels:
            if v.length_m > self.quay_length_m:
                raise ValueError(
                    f"V3: vessel {v.id!r} length_m ({v.length_m}) exceeds "
                    f"quay_length_m ({self.quay_length_m})"
                )
        for v in self.vessels:
            if v.cranes_max > self.cranes:
                raise ValueError(
                    f"V4: vessel {v.id!r} cranes_max ({v.cranes_max}) exceeds "
                    f"instance cranes ({self.cranes})"
                )
        for v in self.vessels:
            if v.eta >= self.time_horizon:
                raise ValueError(
                    f"V5: vessel {v.id!r} eta ({v.eta}) must be "
                    f"< time_horizon ({self.time_horizon})"
                )
        for v in self.vessels:
            hard = self.hard_departure(v)
            earliest_finish = v.eta + self.min_duration(v)
            if not (earliest_finish <= hard <= self.time_horizon):
                raise ValueError(
                    f"V6: vessel {v.id!r} not schedulable: eta+min_duration "
                    f"({earliest_finish}) <= hard_departure ({hard}) <= time_horizon "
                    f"({self.time_horizon}) is violated"
                )
        if self.time_step_min not in {15, 30, 60, 120}:
            raise ValueError(
                f"V7: time_step_min ({self.time_step_min}) must be one of "
                "{15, 30, 60, 120}"
            )
        return self


def load_instance(path: str | Path) -> BacapInstance:
    """Load and validate an instance from JSON. Raises on invalid data."""
    return BacapInstance.model_validate_json(Path(path).read_text(encoding="utf-8"))


def save_instance(inst: BacapInstance, path: str | Path) -> None:
    """Serialize an instance to indented JSON."""
    Path(path).write_text(inst.model_dump_json(indent=2), encoding="utf-8")


def congestion_index(inst: BacapInstance) -> float:
    """Target quay-time utilization of an instance (Phase 1 spec D5).

    ``A / (L * T_span)`` where ``A = sum_v length_m * min_duration(v)`` and
    ``T_span = max_v(eta_v + min_duration(v)) - min_v(eta_v)``. Guards the
    degenerate ``T_span == 0`` (single instantaneous vessel) with a raise.
    """
    area = sum(v.length_m * inst.min_duration(v) for v in inst.vessels)
    t_span = max(v.eta + inst.min_duration(v) for v in inst.vessels) - min(
        v.eta for v in inst.vessels
    )
    if t_span == 0:
        raise ValueError(
            f"congestion_index undefined for instance {inst.instance_id!r}: "
            "T_span is 0 (all vessels have zero duration span)"
        )
    return area / (inst.quay_length_m * t_span)
