"""Application settings, read from environment variables or backend/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    GEMINI_API_KEY: str = Field(min_length=1, repr=False)
    GEMINI_MODEL: str = Field(min_length=1)
    GEMINI_MODEL_FAST: str = Field(min_length=1)
    GEMINI_MODEL_FALLBACK: str | None = None  # used when the main model stays overloaded
    GEMINI_RPM: int = Field(default=10, ge=1)
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    DATA_DIR: Path = BACKEND_DIR / "data"
    DATABASE_URL: str | None = None
    MAX_UPLOAD_MB: int = Field(default=10, ge=1)
    MAX_ROWS: int = Field(default=100_000, ge=1)
    MIN_ROWS: int = Field(default=100, ge=1)
    RISK_HIGH: float = Field(default=0.6, gt=0, lt=1)
    RISK_MEDIUM: float = Field(default=0.3, gt=0, lt=1)
    # Next best offer (Phase 5b): customer value horizon and eligibility rules.
    NBO_HORIZON_MONTHS: int = Field(default=12, ge=1, le=120)
    NBO_MAX_DISCOUNT: float = Field(default=0.20, ge=0, le=1)
    NBO_DECLINE_DAYS: int = Field(default=30, ge=0)

    @field_validator("DATA_DIR")
    @classmethod
    def _anchor_data_dir(cls, value: Path) -> Path:
        # Relative paths are relative to backend/, not to wherever the server starts.
        return value if value.is_absolute() else (BACKEND_DIR / value).resolve()


class SettingsError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        problems = ", ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        raise SettingsError(
            f"Invalid or missing configuration ({problems}). "
            "Copy backend/.env.example to backend/.env and fill in the values."
        ) from None
