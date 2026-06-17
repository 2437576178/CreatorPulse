"""Tests for exporting the MVP OpenAPI contract."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
API_DIR = ROOT_DIR / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from openapi_contract import openapi_schema  # noqa: E402
from scripts.export_openapi import export_openapi, is_openapi_current  # noqa: E402


class ExportOpenAPITest(unittest.TestCase):
    def test_exports_openapi_schema_to_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "openapi.json"
            exported = export_openapi(output_path)

            self.assertEqual(exported, openapi_schema())
            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8")), openapi_schema())
            self.assertTrue(is_openapi_current(output_path))

    def test_detects_stale_openapi_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "openapi.json"
            output_path.write_text('{"openapi":"stale"}\n', encoding="utf-8")

            self.assertFalse(is_openapi_current(output_path))


if __name__ == "__main__":
    unittest.main()
