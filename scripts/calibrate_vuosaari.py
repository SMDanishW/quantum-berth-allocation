"""Fetch Vuosaari port calls + AIS dims, fit, and write the committed calibration.

Outputs:
  experiments/calibration/vuosaari.json   (ArrivalCalibration -- fitted params only)
  docs/figures/vuosaari-calibration.png    (histogram + fitted-density overlay)

Live call (small, rate-limit friendly, CC BY 4.0 public data). Window: most
recent 6 months, widened to 12 if the sample is too small for a stable fit.

Usage:  uv run python scripts/calibrate_vuosaari.py
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from bacap.instances.calibration import (  # noqa: E402
    LENGTH_CLIP_MAX,
    LENGTH_CLIP_MIN,
    SERVICE_MAX_HOURS,
    SERVICE_MIN_HOURS,
    CalibrationDataError,
    fetch_port_calls,
    fetch_vessel_dimensions,
    fit_calibration,
    save_calibration,
)

PORT_AREA = "VUOS"
OUT_JSON = Path("experiments/calibration/vuosaari.json")
OUT_FIG = Path("docs/figures/vuosaari-calibration.png")


def _samples(calls: list[dict], dims: dict[int, int]) -> dict[str, list[float]]:
    """Reproduce the fit's kept samples for plotting (post-filter)."""

    def dt(s: str) -> datetime:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))

    atas, lengths, services = [], [], []
    seen: set[object] = set()
    for c in calls:
        pcid = c.get("portCallId")
        if pcid in seen:
            continue
        seen.add(pcid)
        pad = next(
            (p for p in c.get("portAreaDetails", []) if p.get("portAreaCode") == PORT_AREA),
            None,
        )
        if pad is None or not pad.get("ata"):
            continue
        atas.append(dt(pad["ata"]))
        mmsi = c.get("mmsi")
        length = dims.get(int(mmsi)) if mmsi is not None else None
        if length is not None and LENGTH_CLIP_MIN <= length <= LENGTH_CLIP_MAX:
            lengths.append(float(length))
        if pad.get("atd"):
            svc = (dt(pad["atd"]) - dt(pad["ata"])).total_seconds() / 3600
            if SERVICE_MIN_HOURS <= svc <= SERVICE_MAX_HOURS:
                services.append(svc)
    atas.sort()
    gaps = [(b - a).total_seconds() / 3600 for a, b in zip(atas, atas[1:], strict=False)]
    return {"interarrival": [g for g in gaps if g > 0], "length": lengths, "service": services}


def _plot(samples: dict[str, list[float]], cal, out: Path) -> None:  # noqa: ANN001
    out.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))

    # inter-arrival: exponential
    ia = samples["interarrival"]
    rate = cal.interarrival["rate_per_hour"]
    axes[0].hist(ia, bins=30, density=True, alpha=0.6, color="steelblue")
    xs = [i * (max(ia) / 200) for i in range(1, 201)]
    axes[0].plot(xs, [rate * math.exp(-rate * x) for x in xs], "r-", lw=2)
    axes[0].set_title(f"Inter-arrival (h)\nExp rate={rate:.3f}/h")

    # length & service: lognormal
    for ax, key, params, label in (
        (axes[1], "length", cal.vessel_length_m, "Vessel length (m)"),
        (axes[2], "service", cal.service_time_steps, "Service time (h)"),
    ):
        data = samples[key]
        mu, sigma = params["mu"], params["sigma"]
        ax.hist(data, bins=30, density=True, alpha=0.6, color="steelblue")
        xs = [min(data) + i * (max(data) - min(data)) / 200 for i in range(1, 201)]
        pdf = [
            math.exp(-((math.log(x) - mu) ** 2) / (2 * sigma**2))
            / (x * sigma * math.sqrt(2 * math.pi))
            for x in xs
        ]
        ax.plot(xs, pdf, "r-", lw=2)
        ax.set_title(f"{label}\nLognormal mu={mu:.3f} sigma={sigma:.3f}")

    fig.suptitle(f"Vuosaari (FIHEL/VUOS) calibration -- n={cal.n_port_calls} port calls")
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    print(f"wrote {out}")


def main() -> None:
    to = datetime.now(UTC)
    for months in (6, 12):
        frm = to - timedelta(days=30 * months)
        print(f"fetching FIHEL port calls, last {months} months ...")
        calls = fetch_port_calls("FIHEL", frm.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                 to.strftime("%Y-%m-%dT%H:%M:%SZ"))
        dims = fetch_vessel_dimensions()
        try:
            cal = fit_calibration(calls, dims, PORT_AREA)
        except CalibrationDataError as exc:
            print(f"  {months}-month window insufficient: {exc}")
            continue
        print(f"  fitted on n={cal.n_port_calls} {PORT_AREA} port calls "
              f"({cal.window_from} .. {cal.window_to})")
        save_calibration(cal, OUT_JSON)
        print(f"wrote {OUT_JSON}")
        _plot(_samples(calls, dims), cal, OUT_FIG)
        return
    raise SystemExit("both 6- and 12-month windows were insufficient to calibrate")


if __name__ == "__main__":
    main()
