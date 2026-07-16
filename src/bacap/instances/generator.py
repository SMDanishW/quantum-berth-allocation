"""Synthetic BACAP instance generator (T1.4), per Phase 1 spec §3.4 / §4.4.

Draws a Vuosaari-scale instance from calibrated distributions. The draw order
below is part of the determinism contract: identical ``(args, seed)`` must give
byte-identical JSON, so all randomness comes from one ``default_rng(seed)`` and
the draws happen in the spec's fixed order (lengths -> service times ->
inter-arrivals -> priorities).
"""

from __future__ import annotations

import math
from typing import cast

import numpy as np

from bacap.instances.calibration import ArrivalCalibration
from bacap.instances.schema import BacapInstance, Vessel

# Hardcoded calibration constants, NOT loaded from JSON at import: the JSON at
# experiments/calibration/vuosaari.json is the provenance record, this constant
# is the code contract (no file I/O at import, no runtime path dependency).
# calibrated 2026-07-16 from experiments/calibration/vuosaari.json
# (n=982 Vuosaari port calls, 2026-01-18..2026-07-16)
LENGTH_MU = 5.245774855615497
LENGTH_SIGMA = 0.10263661697336583
LENGTH_CLIP_MIN = 60
LENGTH_CLIP_MAX = 300
SERVICE_MU = 2.5712707124574434
SERVICE_SIGMA = 0.8307310058157161

# Crane bounds by vessel length (spec §4.4 step 2).
FEEDER_MAX_LEN = 120  # < this -> (1, 2)
JUMBO_MIN_LEN = 200  # >= this -> (2, min(4, cranes))
JUMBO_CRANE_CAP = 4

LENGTH_ROUNDING_M = 5
DUE_DATE_SLACK_FACTOR = 1.5  # target_departure = eta + ceil(1.5 * d_min)
HORIZON_TAIL_FACTOR = 3  # time_horizon = max(eta) + 3 * max(d_min)
MAX_TIME_HORIZON = 2000  # steps; above this the parameters are wrong (fail loud)

PRIORITY_VALUES = (1, 2, 3)
PRIORITY_WEIGHTS = (0.7, 0.2, 0.1)


def _lognormal_params(spec: dict[str, object], keys: tuple[str, ...]) -> tuple[float, ...]:
    return tuple(float(cast(float, spec[k])) for k in keys)


def generate_instance(
    n_vessels: int,
    congestion: float,
    seed: int,
    calibration: ArrivalCalibration | None = None,
    *,
    quay_length_m: int = 750,
    cranes: int = 5,
    berth_grid_m: int = 25,
    time_step_min: int = 60,
) -> BacapInstance:
    """Generate a synthetic BACAP instance.

    Args:
        n_vessels: number of vessels (>= 1).
        congestion: target quay-time utilization rho in (0, 1) (spec D5); sets
            the arrival rate, so small values stretch the horizon.
        seed: mandatory; seeds the single RNG behind every draw.
        calibration: fitted distributions; ``None`` uses the Vuosaari constants.

    Raises:
        ValueError: on non-positive ``n_vessels``/``congestion``, or if the
            resulting ``time_horizon`` exceeds ``MAX_TIME_HORIZON`` steps
            (mis-parameterization, not silently fixed).
    """
    if n_vessels < 1:
        raise ValueError(f"n_vessels must be >= 1, got {n_vessels}")
    if congestion <= 0:
        raise ValueError(f"congestion must be > 0, got {congestion}")

    if calibration is None:
        len_mu, len_sigma = LENGTH_MU, LENGTH_SIGMA
        clip_min, clip_max = LENGTH_CLIP_MIN, LENGTH_CLIP_MAX
        svc_mu, svc_sigma = SERVICE_MU, SERVICE_SIGMA
    else:
        len_mu, len_sigma, clip_min_f, clip_max_f = _lognormal_params(
            calibration.vessel_length_m, ("mu", "sigma", "clip_min", "clip_max")
        )
        clip_min, clip_max = int(clip_min_f), int(clip_max_f)
        svc_mu, svc_sigma = _lognormal_params(
            calibration.service_time_steps, ("mu", "sigma")
        )

    rng = np.random.default_rng(seed)

    # 1. Lengths.
    raw_lengths = rng.lognormal(len_mu, len_sigma, n_vessels)
    lengths = [
        int(min(max(round(x / LENGTH_ROUNDING_M) * LENGTH_ROUNDING_M, clip_min), clip_max))
        for x in raw_lengths
    ]

    # 2. Crane bounds by length.
    crane_bounds = [_crane_bounds(length, cranes) for length in lengths]

    # 3. Processing volume = service-time draw (steps) * representative crane count.
    service_steps = rng.lognormal(svc_mu, svc_sigma, n_vessels)
    volumes = [
        max(1, int(round(s * math.ceil((c_min + c_max) / 2))))
        for s, (c_min, c_max) in zip(service_steps, crane_bounds, strict=True)
    ]
    min_durations = [
        math.ceil(q / c_max) for q, (_c_min, c_max) in zip(volumes, crane_bounds, strict=True)
    ]

    # 4. ETAs: Exp(lambda) inter-arrivals with lambda from the congestion knob (D5).
    mean_demand = float(
        np.mean([length * d for length, d in zip(lengths, min_durations, strict=True)])
    )
    rate = congestion * quay_length_m / mean_demand
    gaps = rng.exponential(1.0 / rate, n_vessels)
    raw_etas = np.round(np.cumsum(gaps))
    etas = [int(e - raw_etas.min()) for e in raw_etas]

    # 7. Horizon (needed before vessel construction: V6 checks against it).
    time_horizon = max(etas) + HORIZON_TAIL_FACTOR * max(min_durations)
    if time_horizon > MAX_TIME_HORIZON:
        raise ValueError(
            f"time_horizon ({time_horizon}) exceeds MAX_TIME_HORIZON "
            f"({MAX_TIME_HORIZON}) steps for n_vessels={n_vessels}, "
            f"congestion={congestion}: mis-parameterized (congestion too low?)"
        )

    # 6. Priorities.
    priorities = rng.choice(PRIORITY_VALUES, size=n_vessels, p=PRIORITY_WEIGHTS)

    vessels = [
        Vessel(
            id=f"v{i + 1}",
            name=f"SYN-{i + 1:03d}",
            length_m=lengths[i],
            eta=etas[i],
            processing_volume=volumes[i],
            priority=int(priorities[i]),
            cranes_min=crane_bounds[i][0],
            cranes_max=crane_bounds[i][1],
            # 5. Due dates: soft only; no hard deadline.
            target_departure=etas[i] + math.ceil(DUE_DATE_SLACK_FACTOR * min_durations[i]),
            latest_departure=None,
        )
        for i in range(n_vessels)
    ]

    return BacapInstance(
        instance_id=f"syn-n{n_vessels}-c{congestion}-s{seed}",
        source="synthetic",
        quay_length_m=quay_length_m,
        berth_grid_m=berth_grid_m,
        time_horizon=time_horizon,
        time_step_min=time_step_min,
        cranes=cranes,
        vessels=vessels,
    )


def _crane_bounds(length_m: int, cranes: int) -> tuple[int, int]:
    """Crane (min, max) by vessel length, per spec §4.4 step 2."""
    if length_m < FEEDER_MAX_LEN:
        return 1, min(2, cranes)
    if length_m < JUMBO_MIN_LEN:
        return 1, min(3, cranes)
    return min(2, cranes), min(JUMBO_CRANE_CAP, cranes)
