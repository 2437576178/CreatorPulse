"""Seed local demo login accounts for CreatorPulse."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

from import_mock_to_mysql import DEFAULT_ENV_PATH, MySQLConfig, load_env_file


ROOT_DIR = Path(__file__).resolve().parents[1]

DEMO_USERS = [
    {
        "user_id": "user_demo_beauty",
        "creator_id": "creator_001",
        "email": "demo@creatorpulse.local",
        "password": "demo123456",
        "display_name": "通勤美妆研究所",
        "role": "CREATOR",
    },
    {
        "user_id": "user_demo_style",
        "creator_id": "creator_002",
        "email": "style@creatorpulse.local",
        "password": "demo123456",
        "display_name": "职场穿搭研究所",
        "role": "CREATOR",
    },
]


def seed_users(config: MySQLConfig) -> dict[str, int]:
    try:
        import pymysql
    except ImportError as exc:
        raise RuntimeError("PyMySQL is not installed. Run: pip install -r requirements.txt") from exc

    connection = pymysql.connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        database=config.database,
        charset="utf8mb4",
        autocommit=False,
    )
    try:
        with connection.cursor() as cursor:
            for user in DEMO_USERS:
                cursor.execute(
                    """
                    INSERT INTO users
                      (user_id, creator_id, email, password_hash, display_name, role, is_active)
                    VALUES
                      (%s, %s, %s, %s, %s, %s, 1)
                    ON DUPLICATE KEY UPDATE
                      creator_id = VALUES(creator_id),
                      password_hash = VALUES(password_hash),
                      display_name = VALUES(display_name),
                      role = VALUES(role),
                      is_active = VALUES(is_active)
                    """,
                    (
                        user["user_id"],
                        user["creator_id"],
                        user["email"],
                        generate_password_hash(user["password"]),
                        user["display_name"],
                        user["role"],
                    ),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    return {"users": len(DEMO_USERS)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed CreatorPulse demo login users")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--execute", action="store_true", help="Actually write demo users to MySQL")
    args = parser.parse_args()

    if not args.execute:
        print(json.dumps({"status": "ok", "mode": "dry-run", "counts": {"users": len(DEMO_USERS)}}, ensure_ascii=False, indent=2))
        return

    load_env_file(args.env_file)
    counts = seed_users(MySQLConfig.from_env())
    print(json.dumps({"status": "ok", "mode": "mysql-seed-users", "counts": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))
    main()
