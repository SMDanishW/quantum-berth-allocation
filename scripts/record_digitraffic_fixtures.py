"""One-off: record truncated Digitraffic fixtures for tests (NOT run in CI).

Hits the LIVE API once, truncates to <=50 records, strips vessel names, and
writes committed fixtures under tests/fixtures/digitraffic/. The recorded data
is only used to smoke-test the real client shape; deterministic unit tests use
the hand-built *_fit.json fixtures instead.

Usage:  uv run python scripts/record_digitraffic_fixtures.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from bacap.instances.calibration import (
    _HEADERS,
    PORT_CALL_URL,
    fetch_vessel_dimensions,
)

OUT = Path("tests/fixtures/digitraffic")
MAX_CALLS = 50


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    to = datetime.now(UTC)
    frm = to - timedelta(days=14)
    with httpx.Client() as client:
        resp = client.get(
            PORT_CALL_URL,
            params={
                "locode": "FIHEL",
                "ataFrom": frm.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "ataTo": to.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            headers=_HEADERS,
            timeout=30.0,
        )
        resp.raise_for_status()
        calls = resp.json()["portCalls"]

        # keep only VUOS calls, truncate, strip to fields the client uses
        trimmed = []
        mmsis = set()
        for c in calls:
            pads = [
                {
                    "ata": p.get("ata"),
                    "atd": p.get("atd"),
                    "portAreaCode": p.get("portAreaCode"),
                    "berthCode": p.get("berthCode"),
                }
                for p in c.get("portAreaDetails", [])
                if p.get("portAreaCode") == "VUOS"
            ]
            if not pads:
                continue
            trimmed.append({
                "portCallId": c["portCallId"],
                "mmsi": c.get("mmsi"),
                "imoLloyds": c.get("imoLloyds"),
                "portAreaDetails": pads,
            })
            if c.get("mmsi") is not None:
                mmsis.add(int(c["mmsi"]))
            if len(trimmed) >= MAX_CALLS:
                break

        dims_all = fetch_vessel_dimensions(client=client)

    dims = [
        {"mmsi": m, "referencePointA": dims_all[m] - 10, "referencePointB": 10}
        for m in sorted(mmsis)
        if m in dims_all
    ][:MAX_CALLS]

    (OUT / "port_calls_recorded.json").write_text(
        json.dumps({"portCalls": trimmed}, indent=1)
    )
    (OUT / "vessels_recorded.json").write_text(json.dumps(dims, indent=1))
    print(f"wrote {len(trimmed)} VUOS calls, {len(dims)} vessel dims to {OUT}")


if __name__ == "__main__":
    main()
