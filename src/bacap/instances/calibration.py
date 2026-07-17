"""Digitraffic port-call calibration (T1.3).

Fetches recent Vuosaari port calls + AIS vessel dimensions from Fintraffic's
Digitraffic open API and fits closed-form MLE distributions (exponential
inter-arrivals, lognormal vessel lengths and service times). Only the fitted
parameters are ever persisted -- raw data stays local (CC BY 4.0, see docs).

Verified against the live OpenAPI (https://meri.digitraffic.fi/swagger/) on
2026-07-16:
  * port calls: GET /api/port-call/v1/port-calls?locode=&ataFrom=&ataTo=
    -> {"portCalls": [{portCallId, mmsi, imoLloyds, vesselName,
                       portAreaDetails: [{ata, atd, portAreaCode, ...}]}]}
  * AIS vessels: GET /api/ais/v1/vessels -> flat array of
    {mmsi, referencePointA, referencePointB, ...}; length = refA + refB
  * Vuosaari port-area code = "VUOS" (name "Vuosaaren satama"), locode FIHEL.
The API has no server-side pagination cursor; the client windows the requested
date range into <=30-day sub-requests (rate-limit friendly) and concatenates,
deduping by portCallId, with a hard cap of 10 000 records.
"""

from __future__ import annotations

import math
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

# --- API constants (verified 2026-07-16) -----------------------------------
PORT_CALL_URL = "https://meri.digitraffic.fi/api/port-call/v1/port-calls"
AIS_VESSELS_URL = "https://meri.digitraffic.fi/api/ais/v1/vessels"
DIGITRAFFIC_USER = "bacap-thesis/1.0"
_HEADERS = {"Digitraffic-User": DIGITRAFFIC_USER, "Accept": "application/json"}
TIMEOUT_S = 30.0
MAX_RECORDS = 10_000
WINDOW_DAYS = 30
# 3 retries after the initial attempt, exponential backoff (D8).
_RETRY_BACKOFF_S: tuple[float, ...] = (1.0, 2.0, 4.0)

# --- fit policy constants ---------------------------------------------------
LENGTH_CLIP_MIN = 60
LENGTH_CLIP_MAX = 300
SERVICE_MIN_HOURS = 2.0
SERVICE_MAX_HOURS = 7 * 24.0  # 168 h
# The AIS /vessels endpoint is a live snapshot; a structural ~30% of Vuosaari
# port-call MMSIs are never in it (small craft, tugs, mmsi=0, vessels outside AIS
# coverage) -- verified stable across 30/90/180-day windows on 2026-07-16. The
# guard therefore only trips on catastrophic join failure (wrong endpoint etc.);
# the length fit uses the ~70% that do join (the larger, AIS-tracked cargo ships
# -- exactly the population a container terminal calibration wants). See docs.
JOIN_DROP_RAISE_FRAC = 0.50
NONPOSITIVE_SERVICE_RAISE_FRAC = 0.05
CALIBRATION_TIME_STEP_MIN = 60  # service_time_steps are in 60-min steps

ATTRIBUTION = (
    "Arrival-pattern calibration derived from Fintraffic / Digitraffic "
    "port-call data (https://www.digitraffic.fi/en/marine-traffic/), licensed "
    "CC BY 4.0. Raw data not redistributed; only fitted distribution "
    "parameters are stored."
)


class CalibrationDataError(RuntimeError):
    """Raised when fetched data is too sparse/corrupt to fit (fail loud)."""


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
class ArrivalCalibration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    source: str
    locode: str
    port_area: str
    window_from: str
    window_to: str
    n_port_calls: int = Field(ge=0)
    interarrival: dict[str, object]
    vessel_length_m: dict[str, object]
    service_time_steps: dict[str, object]
    created_at: str
    attribution: str


def load_calibration(path: str | Path) -> ArrivalCalibration:
    return ArrivalCalibration.model_validate_json(Path(path).read_text(encoding="utf-8"))


def save_calibration(cal: ArrivalCalibration, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(cal.model_dump_json(indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def _parse_dt(value: str) -> datetime:
    """Parse an ISO date or datetime; naive values are treated as UTC."""
    s = value.strip().replace("Z", "+00:00")
    if len(s) == 10:  # bare date
        s += "T00:00:00+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _request_json(
    client: httpx.Client, url: str, params: dict[str, str] | None
) -> object:
    """GET with D8 retry: retry only on transport timeout / 5xx; 4xx raises now."""
    last_exc: Exception | None = None
    for attempt in range(len(_RETRY_BACKOFF_S) + 1):
        try:
            resp = client.get(url, params=params, headers=_HEADERS, timeout=TIMEOUT_S)
        except httpx.TimeoutException as exc:
            last_exc = exc
        else:
            if resp.status_code < 400:
                return resp.json()
            if resp.status_code < 500:
                resp.raise_for_status()  # 4xx -> fail loud immediately
            last_exc = httpx.HTTPStatusError(
                f"server error {resp.status_code}", request=resp.request, response=resp
            )
        if attempt < len(_RETRY_BACKOFF_S):
            time.sleep(_RETRY_BACKOFF_S[attempt])
    assert last_exc is not None
    raise last_exc


def fetch_port_calls(
    locode: str, from_iso: str, to_iso: str, *, client: httpx.Client | None = None
) -> list[dict[str, object]]:
    """Fetch port calls for ``locode`` over [from_iso, to_iso).

    Windows the range into <=WINDOW_DAYS sub-requests (the API has no pagination
    cursor), deduping by portCallId, hard-capped at MAX_RECORDS.
    """
    own = client is None
    client = client or httpx.Client()
    try:
        start, end = _parse_dt(from_iso), _parse_dt(to_iso)
        calls: list[dict[str, object]] = []
        seen: set[object] = set()
        cur = start
        while cur < end:
            nxt = min(cur + timedelta(days=WINDOW_DAYS), end)
            data = _request_json(
                client,
                PORT_CALL_URL,
                {"locode": locode, "ataFrom": _iso(cur), "ataTo": _iso(nxt)},
            )
            page = data.get("portCalls", []) if isinstance(data, dict) else []
            for rec in page:
                pcid = rec.get("portCallId")
                if pcid in seen:
                    continue
                seen.add(pcid)
                calls.append(rec)
                if len(calls) >= MAX_RECORDS:
                    return calls
            cur = nxt
        return calls
    finally:
        if own:
            client.close()


def fetch_vessel_dimensions(client: httpx.Client | None = None) -> dict[int, int]:
    """mmsi -> length_m (referencePointA + referencePointB) from AIS metadata."""
    own = client is None
    client = client or httpx.Client()
    try:
        data = _request_json(client, AIS_VESSELS_URL, None)
        rows = data if isinstance(data, list) else []
        dims: dict[int, int] = {}
        for v in rows:
            mmsi, a, b = v.get("mmsi"), v.get("referencePointA"), v.get("referencePointB")
            if mmsi is None or a is None or b is None:
                continue
            length = int(a) + int(b)
            if length > 0:
                dims[int(mmsi)] = length
        return dims
    finally:
        if own:
            client.close()


# ---------------------------------------------------------------------------
# Fitting (closed-form MLE, per D6)
# ---------------------------------------------------------------------------
def _fit_lognormal(values: list[float]) -> tuple[float, float]:
    """MLE: mu = mean(ln x), sigma = std(ln x, ddof=1). Needs >=2 samples."""
    if len(values) < 2:
        raise CalibrationDataError(f"need >=2 samples for lognormal fit, got {len(values)}")
    logs = [math.log(x) for x in values]
    mu = sum(logs) / len(logs)
    var = sum((z - mu) ** 2 for z in logs) / (len(logs) - 1)
    return mu, math.sqrt(var)


def _fit_exponential_rate(interarrivals_h: list[float]) -> float:
    """MLE exponential rate = 1 / mean(inter-arrival)."""
    if len(interarrivals_h) < 1:
        raise CalibrationDataError("need >=1 inter-arrival for exponential fit")
    mean = sum(interarrivals_h) / len(interarrivals_h)
    if mean <= 0:
        raise CalibrationDataError("non-positive mean inter-arrival")
    return 1.0 / mean


def _select_area(call: dict[str, object], port_area: str) -> dict[str, object] | None:
    details = call.get("portAreaDetails") or []
    if not isinstance(details, list):
        return None
    for pad in details:
        if isinstance(pad, dict) and pad.get("portAreaCode") == port_area:
            return pad
    return None


def fit_calibration(
    port_calls: list[dict[str, object]], dims: dict[int, int], port_area: str
) -> ArrivalCalibration:
    """Extract + fit per spec §4.3 / D6. Fails loud on corrupt/sparse data."""
    # 1. Extract Vuosaari records with a valid ATA (dedupe portCallId; no ETA impute).
    seen: set[object] = set()
    atas: list[datetime] = []
    recs: list[tuple[datetime, datetime | None, int | None]] = []  # (ata, atd|None, mmsi)
    for call in port_calls:
        pcid = call.get("portCallId")
        if pcid in seen:
            continue
        seen.add(pcid)
        pad = _select_area(call, port_area)
        if pad is None:
            continue
        ata_raw = pad.get("ata")
        if not isinstance(ata_raw, str):  # missing ATA -> skip (do NOT impute ETA)
            continue
        ata = _parse_dt(ata_raw)
        atd_raw = pad.get("atd")
        atd = _parse_dt(atd_raw) if isinstance(atd_raw, str) else None
        mmsi_raw = call.get("mmsi")
        mmsi = mmsi_raw if isinstance(mmsi_raw, int) else None
        atas.append(ata)
        recs.append((ata, atd, mmsi))

    n_port_calls = len(recs)
    if n_port_calls < 2:
        raise CalibrationDataError(
            f"only {n_port_calls} usable {port_area} port calls; cannot calibrate"
        )

    # 2. Inter-arrivals (hours) from sorted ATAs -> exponential.
    atas.sort()
    interarrivals_h = [
        (b - a).total_seconds() / 3600.0 for a, b in zip(atas, atas[1:], strict=False)
    ]
    interarrivals_h = [d for d in interarrivals_h if d > 0]
    rate_per_hour = _fit_exponential_rate(interarrivals_h)

    # 3. Vessel lengths via MMSI join -> lognormal (drop out-of-range, raise if
    #    too many vessels are missing from the AIS metadata).
    joined_lengths: list[float] = []
    dropped_join = 0
    for _ata, _atd, mmsi in recs:
        length = dims.get(mmsi) if mmsi is not None else None
        if length is None:
            dropped_join += 1
            continue
        joined_lengths.append(float(length))
    join_drop_frac = dropped_join / n_port_calls
    if join_drop_frac > JOIN_DROP_RAISE_FRAC:
        raise CalibrationDataError(
            f"{join_drop_frac:.0%} of port calls missing from AIS metadata join "
            f"(> {JOIN_DROP_RAISE_FRAC:.0%}); calibration unreliable"
        )
    lengths_in_range = [
        x for x in joined_lengths if LENGTH_CLIP_MIN <= x <= LENGTH_CLIP_MAX
    ]
    length_mu, length_sigma = _fit_lognormal(lengths_in_range)

    # 4. Service time (ATD - ATA) hours -> lognormal.
    #    Zero/negative durations are corruption: drop, but RAISE if > 5% of the
    #    records carrying an ATD are non-positive. Then filter to [2h, 7d].
    durations_h = [
        (atd - ata).total_seconds() / 3600.0 for ata, atd, _m in recs if atd is not None
    ]
    n_with_atd = len(durations_h)
    if n_with_atd < 2:
        raise CalibrationDataError("fewer than 2 port calls carry an ATD")
    nonpositive = [d for d in durations_h if d <= 0]
    if len(nonpositive) / n_with_atd > NONPOSITIVE_SERVICE_RAISE_FRAC:
        raise CalibrationDataError(
            f"{len(nonpositive)}/{n_with_atd} port calls have non-positive service "
            f"time (> {NONPOSITIVE_SERVICE_RAISE_FRAC:.0%}); data corrupt"
        )
    positive = [d for d in durations_h if d > 0]
    service_in_range = [d for d in positive if SERVICE_MIN_HOURS <= d <= SERVICE_MAX_HOURS]
    service_mu, service_sigma = _fit_lognormal(service_in_range)

    return ArrivalCalibration(
        source="digitraffic port-call v1",
        locode="FIHEL",
        port_area=port_area,
        window_from=_iso(atas[0]),
        window_to=_iso(atas[-1]),
        n_port_calls=n_port_calls,
        interarrival={"dist": "exponential", "rate_per_hour": rate_per_hour},
        vessel_length_m={
            "dist": "lognormal",
            "mu": length_mu,
            "sigma": length_sigma,
            "clip_min": LENGTH_CLIP_MIN,
            "clip_max": LENGTH_CLIP_MAX,
        },
        service_time_steps={
            "dist": "lognormal",
            "mu": service_mu,
            "sigma": service_sigma,
        },
        created_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        attribution=ATTRIBUTION,
    )
