"""Migrate users.creator_id to a one-account-per-creator unique key."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from import_mock_to_mysql import DEFAULT_ENV_PATH, MySQLConfig, load_env_file


ROOT_DIR = Path(__file__).resolve().parents[1]


def migrate_users_creator_unique(config: MySQLConfig) -> dict[str, str]:
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
            cursor.execute(
                """
                SELECT creator_id, COUNT(*) AS user_count
                FROM users
                GROUP BY creator_id
                HAVING COUNT(*) > 1
                """
            )
            duplicates = cursor.fetchall()
            if duplicates:
                raise RuntimeError("Cannot add unique key: duplicate users.creator_id rows exist")

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.statistics
                WHERE table_schema = DATABASE()
                  AND table_name = 'users'
                  AND index_name = 'uk_users_creator'
                """
            )
            if cursor.fetchone()[0]:
                connection.commit()
                return {"usersCreatorUniqueKey": "already-present"}

            cursor.execute("ALTER TABLE users ADD UNIQUE KEY uk_users_creator (creator_id)")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    return {"usersCreatorUniqueKey": "created"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate users.creator_id to a unique key")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--execute", action="store_true", help="Actually update the MySQL users index")
    args = parser.parse_args()

    if not args.execute:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "mode": "dry-run",
                    "migration": "users.creator_id unique key",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    load_env_file(args.env_file)
    result = migrate_users_creator_unique(MySQLConfig.from_env())
    print(json.dumps({"status": "ok", "mode": "mysql-migration", "result": result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))
    main()
