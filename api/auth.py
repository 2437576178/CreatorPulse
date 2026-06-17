"""Session authentication helpers for CreatorPulse."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from flask import session
from sqlalchemy import text
from werkzeug.security import check_password_hash, generate_password_hash

from mysql_repository import MySQLRepository
from registration_service import normalize_platforms, seed_registered_creator_rows
from database.import_mock_to_mysql import MySQLConfig, load_env_file, write_mysql


class AuthError(RuntimeError):
    """Raised when authentication cannot be completed."""


class AuthenticationFailed(AuthError):
    """Raised when credentials are invalid."""


class Unauthenticated(AuthError):
    """Raised when an endpoint requires a logged-in user."""


@dataclass(frozen=True)
class AuthUser:
    user_id: str
    creator_id: str
    email: str
    display_name: str
    role: str

    def to_payload(self) -> dict[str, str]:
        return {
            "userId": self.user_id,
            "creatorId": self.creator_id,
            "email": self.email,
            "displayName": self.display_name,
            "role": self.role,
        }


def row_to_user(row: dict[str, Any]) -> AuthUser:
    return AuthUser(
        user_id=row["user_id"],
        creator_id=row["creator_id"],
        email=row["email"],
        display_name=row["display_name"],
        role=row["role"],
    )


class AuthRepository:
    def __init__(self, repository: MySQLRepository | None = None) -> None:
        self.repository = repository or MySQLRepository()

    def authenticate(self, email: str, password: str) -> AuthUser:
        normalized_email = email.strip().lower()
        with self.repository.engine.connect() as connection:
            result = connection.execute(
                text(
                    """
                    SELECT user_id, creator_id, email, password_hash, display_name, role
                    FROM users
                    WHERE email = :email AND is_active = 1
                    """
                ),
                {"email": normalized_email},
            )
            row = result.mappings().first()

        if not row or not check_password_hash(row["password_hash"], password):
            raise AuthenticationFailed("Invalid email or password")
        return row_to_user(dict(row))

    def get_user(self, user_id: str) -> AuthUser:
        with self.repository.engine.connect() as connection:
            result = connection.execute(
                text(
                    """
                    SELECT user_id, creator_id, email, display_name, role
                    FROM users
                    WHERE user_id = :user_id AND is_active = 1
                    """
                ),
                {"user_id": user_id},
            )
            row = result.mappings().first()
        if not row:
            raise Unauthenticated("Login required")
        return row_to_user(dict(row))

    def register(self, email: str, password: str, display_name: str, platforms: list[str]) -> AuthUser:
        normalized_email = email.strip().lower()
        normalized_name = display_name.strip()
        if not normalized_email:
            raise ValueError("Email is required")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not normalized_name:
            raise ValueError("Display name is required")

        selected_platforms = normalize_platforms(platforms)
        user_id = f"user_{uuid4().hex[:12]}"
        creator_id = f"creator_{uuid4().hex[:12]}"

        with self.repository.engine.connect() as connection:
            existing = connection.execute(text("SELECT user_id FROM users WHERE email = :email"), {"email": normalized_email}).first()
        if existing:
            raise ValueError("Email is already registered")

        rows = seed_registered_creator_rows(creator_id, normalized_name, selected_platforms)

        load_env_file()
        config = MySQLConfig.from_env()
        write_mysql(rows, config)

        with self.repository.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO users
                      (user_id, creator_id, email, password_hash, display_name, role, is_active)
                    VALUES
                      (:user_id, :creator_id, :email, :password_hash, :display_name, 'CREATOR', 1)
                    """
                ),
                {
                    "user_id": user_id,
                    "creator_id": creator_id,
                    "email": normalized_email,
                    "password_hash": generate_password_hash(password),
                    "display_name": normalized_name,
                },
            )

        return AuthUser(user_id=user_id, creator_id=creator_id, email=normalized_email, display_name=normalized_name, role="CREATOR")


def set_session_user(user: AuthUser) -> None:
    session.clear()
    session["user_id"] = user.user_id
    session["creator_id"] = user.creator_id


def clear_session_user() -> None:
    session.clear()


def current_user() -> AuthUser:
    user_id = session.get("user_id")
    if not user_id:
        raise Unauthenticated("Login required")
    return AuthRepository().get_user(user_id)
