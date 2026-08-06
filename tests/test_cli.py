from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


class CliTests(unittest.TestCase):
    def test_build_command_publishes_and_returns_json(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.txt").write_text("DOMAIN,example.com\n", encoding="utf-8")
            (root / "overrides.yaml").write_text(
                yaml.safe_dump(
                    {
                        "schema_version": 1,
                        "force_direct": [],
                        "force_reject": [],
                        "force_proxy": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "config.yaml").write_text(
                yaml.safe_dump(
                    {
                        "schema_version": 2,
                        "sources": {
                            "source": {
                                "type": "file",
                                "path": "source.txt",
                                "format": "text",
                                "behavior": "classical",
                                "redistributable": True,
                            }
                        },
                        "categories": {
                            "direct": {
                                "family": "domain",
                                "sources": ["source"],
                                "formats": ["yaml"],
                            }
                        },
                        "profiles": {
                            "default": {
                                "actions": {"direct-domain": ["direct"]},
                                "formats": ["yaml"],
                            }
                        },
                        "overrides": "overrides.yaml",
                        "quality": {"small_output_limit": 0},
                        "legacy": {"enabled": False, "aliases": {}},
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "rulemerger",
                    "build",
                    "--config",
                    str(root / "config.yaml"),
                    "--output",
                    str(root / "published"),
                ],
                cwd=repository_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout)["publishable"])
            self.assertTrue((root / "published" / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
