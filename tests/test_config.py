from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from rulemerger.config import ConfigError, load_config


class ConfigTests(unittest.TestCase):
    def test_unknown_source_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {
                "schema_version": 2,
                "sources": {
                    "source": {
                        "type": "file",
                        "path": "source.txt",
                        "format": "text",
                        "behavior": "classical",
                        "behavicloudflareor": "classical",
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
                "quality": {},
                "legacy": {},
            }
            path = root / "config.yaml"
            path.write_text(yaml.safe_dump(config), encoding="utf-8")

            with self.assertRaisesRegex(ConfigError, "behavicloudflareor"):
                load_config(path)

    def test_source_locator_must_match_source_type(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {
                "schema_version": 2,
                "sources": {
                    "source": {
                        "type": "file",
                        "path": "source.txt",
                        "url": "https://example.com/source.txt",
                        "format": "text",
                        "behavior": "classical",
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
                "overrides": None,
                "quality": {},
                "legacy": {},
            }
            path = root / "config.yaml"
            path.write_text(yaml.safe_dump(config), encoding="utf-8")

            with self.assertRaisesRegex(ConfigError, "only valid for http"):
                load_config(path)

    def test_duplicate_yaml_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(
                """
schema_version: 2
schema_version: 2
sources: {}
categories: {}
profiles: {}
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ConfigError, "duplicate"):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
