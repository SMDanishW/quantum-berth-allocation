"""T1.3 calibration tests. All HTTP is mocked via httpx.MockTransport -- no live calls."""

from __future__ import annotations

import json
import math
import statistics
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from bacap.instances import calibration as cal
from bacap.instances.calibration import (
    ArrivalCalibration,
    CalibrationDataError,
    fetch_port_calls,
    fetch_vessel_dimensions,
    fit_calibration,
    load_calibration,
    save_calibration,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "digitraffic"


def _load(name: str) -> object:
    return json.loads((FIXTURES / name).read_text())


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------------------
# fetch_port_calls: windowing / termination / dedupe / cap
# ---------------------------------------------------------------------------
def test_pagination_terminates_and_accumulates_across_windows():
    """Two 30-day windows: first has records, second is empty. Loop must cover
    both and terminate (empty window does not lose the first window's data)."""
    calls_seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        ata_from = request.url.params["ataFrom"]
        calls_seen.append(ata_from)
        if ata_from.startswith("2026-01-01"):
            body = {"portCalls": [{"portCallId": 1}, {"portCallId": 2}]}
        else:
            body = {"portCalls": []}  # empty second window
        return httpx.Response(200, json=body)

    with _client(handler) as c:
        result = fetch_port_calls("FIHEL", "2026-01-01", "2026-02-20", client=c)

    assert len(calls_seen) == 2  # two 30-day sub-windows, then stop at end
    assert [r["portCallId"] for r in result] == [1, 2]


def test_dedupe_duplicate_portcallid_across_windows():
    def handler(request: httpx.Request) -> httpx.Response:
        # same portCallId returned in every window
        return httpx.Response(200, json={"portCalls": [{"portCallId": 42}]})

    with _client(handler) as c:
        result = fetch_port_calls("FIHEL", "2026-01-01", "2026-03-15", client=c)

    assert [r["portCallId"] for r in result] == [42]  # deduped to a single record


def test_hard_cap_stops_fetch(monkeypatch):
    monkeypatch.setattr(cal, "MAX_RECORDS", 5)

    def handler(request: httpx.Request) -> httpx.Response:
        pcs = [{"portCallId": i} for i in range(100)]
        return httpx.Response(200, json={"portCalls": pcs})

    with _client(handler) as c:
        result = fetch_port_calls("FIHEL", "2026-01-01", "2026-02-01", client=c)

    assert len(result) == 5


# ---------------------------------------------------------------------------
# retry / backoff (D8)
# ---------------------------------------------------------------------------
def test_retry_then_raise_on_persistent_500(monkeypatch):
    monkeypatch.setattr(cal, "_RETRY_BACKOFF_S", (0.0, 0.0, 0.0))
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(500, json={"error": "boom"})

    with _client(handler) as c:  # noqa: SIM117
        with pytest.raises(httpx.HTTPStatusError):
            fetch_port_calls("FIHEL", "2026-01-01", "2026-01-15", client=c)

    assert attempts["n"] == 4  # initial + 3 retries


def test_4xx_raises_immediately_no_retry(monkeypatch):
    monkeypatch.setattr(cal, "_RETRY_BACKOFF_S", (0.0, 0.0, 0.0))
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(404, json={"error": "nope"})

    with _client(handler) as c:  # noqa: SIM117
        with pytest.raises(httpx.HTTPStatusError):
            fetch_port_calls("FIHEL", "2026-01-01", "2026-01-15", client=c)

    assert attempts["n"] == 1  # no retries on 4xx


def test_retry_recovers_on_transient_500(monkeypatch):
    monkeypatch.setattr(cal, "_RETRY_BACKOFF_S", (0.0, 0.0, 0.0))
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(503, json={})
        return httpx.Response(200, json={"portCalls": [{"portCallId": 7}]})

    with _client(handler) as c:
        result = fetch_port_calls("FIHEL", "2026-01-01", "2026-01-15", client=c)

    assert attempts["n"] == 2
    assert [r["portCallId"] for r in result] == [7]


# ---------------------------------------------------------------------------
# fetch_vessel_dimensions
# ---------------------------------------------------------------------------
def test_fetch_vessel_dimensions_length_is_refa_plus_refb():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[
            {"mmsi": 111, "referencePointA": 64, "referencePointB": 15},
            {"mmsi": 222, "referencePointA": 100, "referencePointB": 40},
            {"mmsi": 333, "referencePointA": None, "referencePointB": 10},  # dropped
        ])

    with _client(handler) as c:
        dims = fetch_vessel_dimensions(client=c)

    assert dims == {111: 79, 222: 140}


# ---------------------------------------------------------------------------
# fit_calibration: hand-computed MLE against the 20-call fixture
# ---------------------------------------------------------------------------
def test_fit_matches_independent_mle_on_fixture():
    calls = _load("port_calls_fit.json")["portCalls"]
    vessels = _load("vessels_fit.json")
    dims = {v["mmsi"]: v["referencePointA"] + v["referencePointB"] for v in vessels}

    result = fit_calibration(calls, dims, "VUOS")

    # --- independent expected values from the raw fixture ---
    def dt(s):
        return datetime.fromisoformat(s.replace("Z", "+00:00"))

    atas = sorted(dt(c["portAreaDetails"][0]["ata"]) for c in calls)
    gaps = [(b - a).total_seconds() / 3600 for a, b in zip(atas, atas[1:], strict=False)]
    exp_rate = 1 / statistics.fmean(gaps)

    lengths = [float(dims[c["mmsi"]]) for c in calls]
    llen = [math.log(x) for x in lengths]
    exp_len_mu = statistics.fmean(llen)
    exp_len_sigma = statistics.stdev(llen)  # ddof=1

    services = [
        (dt(c["portAreaDetails"][0]["atd"]) - dt(c["portAreaDetails"][0]["ata"]))
        .total_seconds() / 3600
        for c in calls
    ]
    lsvc = [math.log(x) for x in services]
    exp_svc_mu = statistics.fmean(lsvc)
    exp_svc_sigma = statistics.stdev(lsvc)

    assert result.n_port_calls == 20
    assert result.port_area == "VUOS"
    assert result.locode == "FIHEL"
    assert result.interarrival["rate_per_hour"] == pytest.approx(exp_rate)
    assert result.vessel_length_m["mu"] == pytest.approx(exp_len_mu)
    assert result.vessel_length_m["sigma"] == pytest.approx(exp_len_sigma)
    assert result.vessel_length_m["clip_min"] == 60
    assert result.vessel_length_m["clip_max"] == 300
    assert result.service_time_steps["mu"] == pytest.approx(exp_svc_mu)
    assert result.service_time_steps["sigma"] == pytest.approx(exp_svc_sigma)
    assert result.window_from == "2026-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# fit_calibration edge cases
# ---------------------------------------------------------------------------
def _pad(ata, atd, code="VUOS"):
    return {"portAreaDetails": [{"ata": ata, "atd": atd, "portAreaCode": code}]}


def _call(pcid, mmsi, ata, atd, code="VUOS"):
    return {"portCallId": pcid, "mmsi": mmsi, **_pad(ata, atd, code)}


def _many(n, *, with_atd=True):
    """n valid VUOS calls, 6h apart, 24h service, mmsi 1..n with length 140."""
    calls, dims = [], {}
    for i in range(n):
        ata = f"2026-01-{1 + i // 4:02d}T{(i % 4) * 6:02d}:00:00Z"
        atd = f"2026-01-{2 + i // 4:02d}T{(i % 4) * 6:02d}:00:00Z" if with_atd else None
        calls.append(_call(1000 + i, 500 + i, ata, atd))
        dims[500 + i] = 140
    return calls, dims


def test_missing_ata_record_is_skipped_not_imputed():
    calls, dims = _many(10)
    # add a record with only an ETA and no ATA -> must be skipped
    calls.append({
        "portCallId": 9999, "mmsi": 12345,
        "portAreaDetails": [{"eta": "2026-01-01T00:00:00Z", "ata": None,
                             "atd": "2026-01-02T00:00:00Z", "portAreaCode": "VUOS"}],
    })
    dims[12345] = 140
    result = fit_calibration(calls, dims, "VUOS")
    assert result.n_port_calls == 10  # the ETA-only record excluded


def test_duplicate_portcallid_deduped_in_fit():
    calls, dims = _many(10)
    calls.append(calls[0])  # exact duplicate portCallId
    result = fit_calibration(calls, dims, "VUOS")
    assert result.n_port_calls == 10


def test_non_vuosaari_area_ignored():
    calls, dims = _many(10)
    calls.append(_call(7777, 8888, "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z",
                       code="LS"))
    dims[8888] = 140
    result = fit_calibration(calls, dims, "VUOS")
    assert result.n_port_calls == 10


def test_join_drop_over_threshold_raises():
    calls, dims = _many(10)
    # drop 6/10 from the AIS metadata -> 60% > 50% -> catastrophic-join raise
    for mmsi in (500, 501, 502, 503, 504, 505):
        del dims[mmsi]
    with pytest.raises(CalibrationDataError, match="AIS metadata"):
        fit_calibration(calls, dims, "VUOS")


def test_structural_join_drop_under_threshold_ok():
    # ~30% miss is the real AIS-snapshot reality (verified); must NOT raise.
    calls, dims = _many(20)
    for mmsi in (500, 501, 502, 503, 504, 505):  # 6/20 = 30% < 50%
        del dims[mmsi]
    result = fit_calibration(calls, dims, "VUOS")
    assert result.n_port_calls == 20  # arrival count unaffected by length-join drop


def test_nonpositive_service_over_5pct_raises():
    calls, dims = _many(10)
    # make 2/10 = 20% > 5% have atd <= ata (negative service)
    calls[0]["portAreaDetails"][0]["atd"] = "2025-12-31T00:00:00Z"
    calls[1]["portAreaDetails"][0]["atd"] = "2025-12-31T00:00:00Z"
    with pytest.raises(CalibrationDataError, match="non-positive service"):
        fit_calibration(calls, dims, "VUOS")


def test_out_of_range_service_dropped_not_raised():
    calls, dims = _many(20)
    # one absurd 30-day service time (> 7d) -> dropped, no raise
    calls[0]["portAreaDetails"][0]["atd"] = "2026-01-31T00:00:00Z"
    result = fit_calibration(calls, dims, "VUOS")
    assert result.n_port_calls == 20  # still counted as an arrival


# ---------------------------------------------------------------------------
# model round-trip
# ---------------------------------------------------------------------------
def test_arrival_calibration_round_trip(tmp_path):
    original = ArrivalCalibration(
        source="digitraffic port-call v1",
        locode="FIHEL",
        port_area="VUOS",
        window_from="2026-01-01T00:00:00Z",
        window_to="2026-07-01T00:00:00Z",
        n_port_calls=123,
        interarrival={"dist": "exponential", "rate_per_hour": 0.25},
        vessel_length_m={"dist": "lognormal", "mu": 4.9, "sigma": 0.35,
                         "clip_min": 60, "clip_max": 300},
        service_time_steps={"dist": "lognormal", "mu": 3.1, "sigma": 0.4},
        created_at="2026-07-16T00:00:00Z",
        attribution=cal.ATTRIBUTION,
    )
    path = tmp_path / "vuosaari.json"
    save_calibration(original, path)
    reloaded = load_calibration(path)
    assert reloaded == original
