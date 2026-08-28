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

    def test_production_config_retires_compatibility_categories_and_splits_copilot(self) -> None:
        root = Path(__file__).resolve().parents[1]
        config = load_config(root / "config.yaml")

        self.assertNotIn("custom-direct-domain", config.categories)
        self.assertNotIn("custom-proxy-domain", config.categories)
        self.assertEqual(
            set(config.quality["allowed_removed_outputs"]),
            {
                "categories/custom-direct-domain",
                "categories/custom-proxy-domain",
            },
        )
        self.assertEqual(
            config.quality["max_growth_ratio_overrides"],
            {
                "categories/cn-ip": 1.1,
                "profiles/default/direct-ip": 1.1,
            },
        )
        self.assertIn("local_ai_general", config.categories["ai-domain"].sources)

        coding = yaml.safe_load(
            (root / "local" / "ai-coding.yaml").read_text(encoding="utf-8")
        )["payload"]
        general = yaml.safe_load(
            (root / "local" / "ai-general.yaml").read_text(encoding="utf-8")
        )["payload"]
        moved = {
            "DOMAIN-SUFFIX,copilot.com",
            "DOMAIN-SUFFIX,copilot.microsoft.com",
        }
        self.assertTrue(moved.isdisjoint(coding))
        self.assertTrue(moved.issubset(general))


if __name__ == "__main__":
    unittest.main()
