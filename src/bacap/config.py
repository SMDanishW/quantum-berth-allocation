"""Runtime configuration and secrets, read from environment / `.env`.

Secrets live in `.env` only (gitignored). Importing this module never fails on a
missing token: non-QPU runs must work without any D-Wave credentials. The token is
only demanded, loudly, at the point it is actually needed (`require_dwave_token`).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings. Field names map to upper-case env vars."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Opt-in flag for real quantum hardware (D-Wave Leap). Off by default.
    bacap_use_qpu: bool = False
    # D-Wave Leap API token. None unless provided via .env / environment.
    dwave_api_token: str | None = None

    def require_dwave_token(self) -> str:
        """Return the D-Wave token or fail loudly if it is missing.

        Call this only on the QPU code path (never at import time), per the
        no-silent-fallback rule.
        """
        if not self.dwave_api_token:
            raise RuntimeError(
                "DWAVE_API_TOKEN is not set. Add it to .env to run against the "
                "D-Wave QPU (BACAP_USE_QPU=1)."
            )
        return self.dwave_api_token


settings = Settings()
