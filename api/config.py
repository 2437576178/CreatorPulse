"""Runtime configuration for CreatorPulse API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = ROOT_DIR / ".env"


class ConfigError(RuntimeError):
    """Raised when runtime configuration is invalid."""


def load_env_file(path: Path = DEFAULT_ENV_PATH) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class MySQLSettings:
    host: str
    port: int
    database: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> "MySQLSettings":
        required = ["MYSQL_HOST", "MYSQL_PORT", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD"]
        missing = [key for key in required if not os.environ.get(key)]
        if missing:
            raise ConfigError(f"Missing MySQL environment variables: {', '.join(missing)}")

        try:
            port = int(os.environ["MYSQL_PORT"])
        except ValueError as exc:
            raise ConfigError("MYSQL_PORT must be an integer") from exc

        return cls(
            host=os.environ["MYSQL_HOST"],
            port=port,
            database=os.environ["MYSQL_DATABASE"],
            user=os.environ["MYSQL_USER"],
            password=os.environ["MYSQL_PASSWORD"],
        )

    @property
    def sqlalchemy_url(self) -> str:
        user = quote_plus(self.user)
        password = quote_plus(self.password)
        return f"mysql+pymysql://{user}:{password}@{self.host}:{self.port}/{self.database}?charset=utf8mb4"


def get_data_source() -> str:
    load_env_file()
    value = os.environ.get("CREATORPULSE_DATA_SOURCE", "mock").strip().lower()
    if value not in {"mock", "mysql"}:
        raise ConfigError("CREATORPULSE_DATA_SOURCE must be 'mock' or 'mysql'")
    return value


def get_secret_key() -> str:
    load_env_file()
    return os.environ.get("CREATORPULSE_SECRET_KEY", "creatorpulse-local-dev-secret")
