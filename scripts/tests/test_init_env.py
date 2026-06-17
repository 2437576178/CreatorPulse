"""Tests for safe .env initialization."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.init_env import init_env, preview_init_env  # noqa: E402


class InitEnvTest(unittest.TestCase):
    def test_copies_example_when_env_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            example = root / ".env.example"
            env = root / ".env"
            example.write_text("MYSQL_USER=your_user\n", encoding="utf-8")

            result = init_env(example, env, force=False)

            self.assertEqual(result["status"], "created")
            self.assertEqual(env.read_text(encoding="utf-8"), "MYSQL_USER=your_user\n")

    def test_does_not_overwrite_existing_env_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            example = root / ".env.example"
            env = root / ".env"
            example.write_text("MYSQL_USER=your_user\n", encoding="utf-8")
            env.write_text("MYSQL_USER=real_user\n", encoding="utf-8")

            result = init_env(example, env, force=False)

            self.assertEqual(result["status"], "exists")
            self.assertEqual(env.read_text(encoding="utf-8"), "MYSQL_USER=real_user\n")

    def test_force_overwrites_existing_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            example = root / ".env.example"
            env = root / ".env"
            example.write_text("MYSQL_USER=template_user\n", encoding="utf-8")
            env.write_text("MYSQL_USER=old_user\n", encoding="utf-8")

            result = init_env(example, env, force=True)

            self.assertEqual(result["status"], "overwritten")
            self.assertEqual(env.read_text(encoding="utf-8"), "MYSQL_USER=template_user\n")

    def test_missing_example_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            with self.assertRaises(FileNotFoundError):
                init_env(root / ".env.example", root / ".env", force=False)

    def test_preview_reports_would_create_without_writing_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            example = root / ".env.example"
            env = root / ".env"
            example.write_text("MYSQL_USER=your_user\n", encoding="utf-8")

            result = preview_init_env(example, env)

            self.assertEqual(result["status"], "would-create")
            self.assertFalse(env.exists())


if __name__ == "__main__":
    unittest.main()
