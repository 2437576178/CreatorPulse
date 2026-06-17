# CreatorPulse MVP Database

This folder contains the first MySQL-ready slice of the MVP roadmap.

## Files

- `schema.sql`: MySQL tables for the current MVP data contract.
- `apply_schema.py`: validates or applies `schema.sql` to local MySQL.
- `import_mock_to_mysql.py`: maps `mvp_mock/data/creatorpulse_mvp_mock.json` into database rows.
- `tests/test_import_mock_to_mysql.py`: verifies table mapping without requiring a live MySQL server.

## Dry Run

```powershell
python database\apply_schema.py
python database\import_mock_to_mysql.py
```

Dry-run validates schema parsing and row mapping, then prints counts. It does not connect to MySQL.

## Real Import

1. Copy `.env.example` to `.env`.
2. Fill your local MySQL host, port, database, user, and password.
3. Apply schema.
4. Import mock data.

```powershell
python database\apply_schema.py --execute
python database\import_mock_to_mysql.py --execute
```

Flask/Python will use SQLAlchemy + PyMySQL in the next phase. Spark JDBC config is kept in `.env.example` for the later Spark write-to-MySQL phase.
