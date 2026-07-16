"""Placeholder + config smoke tests for the scaffold (T0.1)."""

from __future__ import annotations

import pytest

from bacap import __version__
from bacap.config import Settings


def test_package_importable() -> None:
    assert __version__ == "0.1.0"


def test_defaults_without_env() -> None:
    # No token, QPU off, and import/instantiation must not raise.
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.bacap_use_qpu is False
    assert s.dwave_api_token is None


def test_require_dwave_token_fails_loud_when_missing() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    with pytest.raises(RuntimeError, match="DWAVE_API_TOKEN"):
        s.require_dwave_token()


def test_require_dwave_token_returns_value_when_set() -> None:
    s = Settings(_env_file=None, dwave_api_token="tok-123")  # type: ignore[call-arg]
    assert s.require_dwave_token() == "tok-123"
