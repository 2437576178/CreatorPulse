"""Repository factory for CreatorPulse API data sources."""

from __future__ import annotations

from functools import lru_cache
from typing import Protocol

from config import ConfigError, get_data_source
from mock_repository import MockDataError, MockRepository
from mysql_repository import MySQLRepository


class CreatorPulseRepository(Protocol):
    def get_health(self) -> dict:
        ...

    def get_view_model(self, creator_id: str, key: str) -> dict:
        ...

    def list_reports(self, creator_id: str, report_type: str | None = None, page: int = 1, page_size: int = 10) -> dict:
        ...

    def get_report(self, creator_id: str, report_id: str) -> dict:
        ...


class RepositoryError(RuntimeError):
    """Raised when the configured repository cannot be created or queried."""


@lru_cache(maxsize=1)
def get_repository() -> CreatorPulseRepository:
    try:
        data_source = get_data_source()
    except ConfigError:
        raise

    if data_source == "mock":
        return MockRepository()
    if data_source == "mysql":
        return MySQLRepository()

    raise ConfigError(f"Unsupported data source: {data_source}")


def clear_repository_cache() -> None:
    get_repository.cache_clear()


__all__ = [
    "ConfigError",
    "CreatorPulseRepository",
    "MockDataError",
    "RepositoryError",
    "clear_repository_cache",
    "get_repository",
]
