from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from rulemerger.build import build
from rulemerger.models import BuildRequest


def write_project(
    root: Path,
    *,
    source_text: str,
    sources: dict,
    categories: dict,
    actions: dict,
    formats: list[str] | None = None,
    overrides: dict | None = None,
    quality: dict | None = None,
) -> Path:
    (root / "source.txt").write_text(source_text, encoding="utf-8")
    (root / "overrides.yaml").write_text(
        yaml.safe_dump(
            overrides
            or {
                "schema_version": 1,
                "force_direct": [],
                "force_reject": [],
                "force_proxy": [],
            }
        ),
        encoding="utf-8",
    )
    config = {
        "schema_version": 2,
        "sources": sources,
        "categories": categories,
        "profiles": {
            "default": {"actions": actions, "formats": formats or ["yaml", "json"]}
        },
        "overrides": "overrides.yaml",
        "quality": quality
        or {
            "max_drop_ratio": 0.15,
            "max_growth_ratio": 0.50,
            "small_output_limit": 100,
        },
        "legacy": {"enabled": False, "aliases": {}},
    }
    path = root / "config.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path


class BuildBehaviorTests(unittest.TestCase):
    class FakeTools:
        def versions(self) -> dict[str, str]:
            return {"mihomo": "fake-mihomo", "sing-box": "fake-sing-box"}

        def compile_mrs(self, source: bytes, behavior: str) -> bytes:
            return source

        def decompile_mrs(self, source: bytes, behavior: str) -> bytes:
            return source

        def compile_srs(self, source: bytes) -> bytes:
            return source

        def decompile_srs(self, source: bytes) -> bytes:
            return source

    def test_required_source_failure_preserves_existing_publish(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = write_project(
                root,
                source_text="DOMAIN,example.com\n",
                sources={
                    "missing": {
                        "type": "file",
                        "path": "does-not-exist.txt",
                        "format": "text",
                        "behavior": "classical",
                        "required": True,
                    }
                },
                categories={
                    "direct": {
                        "family": "domain",
                        "sources": ["missing"],
                        "formats": ["yaml", "json"],
                    }
                },
                actions={"direct-domain": ["direct"]},
            )
            output = root / "published"
            output.mkdir()
            (output / "sentinel.txt").write_text("keep", encoding="utf-8")
            report_path = root / "report.json"

            report = build(BuildRequest(config, output, report_path=report_path))

            self.assertFalse(report.publishable)
            self.assertTrue(any("missing" in error for error in report.errors))
            self.assertEqual(report.sources["missing"]["path"], "does-not-exist.txt")
            self.assertEqual(
                (output / "sentinel.txt").read_text(encoding="utf-8"), "keep"
            )
            self.assertFalse((output / "manifest.json").exists())
            self.assertTrue(report_path.exists())

    def test_baseline_removed_output_fails_before_replacing_publish(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = write_project(
                root,
                source_text="DOMAIN,example.com\n",
                sources={
                    "source": {
                        "type": "file",
                        "path": "source.txt",
                        "format": "text",
                        "behavior": "classical",
                    }
                },
                categories={
                    "direct": {
                        "family": "domain",
                        "sources": ["source"],
                        "formats": ["yaml"],
                    }
                },
                actions={"direct-domain": ["direct"]},
            )
            baseline = root / "baseline.json"
            baseline.write_text(
                json.dumps(
                    {
                        "outputs": {
                            "categories/direct.yaml": {"rules": 1},
                            "categories/removed.yaml": {"rules": 10},
                        }
                    }
                ),
                encoding="utf-8",
            )
            output = root / "published"
            output.mkdir()
            (output / "sentinel.txt").write_text("keep", encoding="utf-8")

            report = build(BuildRequest(config, output, baseline_manifest=baseline))

            self.assertFalse(report.publishable)
            self.assertTrue(any("removed.yaml" in error for error in report.errors))
            self.assertEqual(
                (output / "sentinel.txt").read_text(encoding="utf-8"), "keep"
            )

    def test_invalid_baseline_fails_before_replacing_publish(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = write_project(
                root,
                source_text="DOMAIN,example.com\n",
                sources={
                    "source": {
                        "type": "file",
                        "path": "source.txt",
                        "format": "text",
                        "behavior": "classical",
                    }
                },
                categories={
                    "direct": {
                        "family": "domain",
                        "sources": ["source"],
                        "formats": ["yaml"],
                    }
                },
                actions={"direct-domain": ["direct"]},
            )
            baseline = root / "baseline.json"
            baseline.write_text("[]", encoding="utf-8")
            output = root / "published"
            output.mkdir()
            (output / "sentinel.txt").write_text("keep", encoding="utf-8")

            report = build(BuildRequest(config, output, baseline_manifest=baseline))

            self.assertFalse(report.publishable)
            self.assertTrue(
                any("outputs must be a mapping" in error for error in report.errors)
            )
            self.assertEqual(
                (output / "sentinel.txt").read_text(encoding="utf-8"), "keep"
            )

    def test_optional_source_failure_is_degraded_but_publishable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = write_project(
                root,
                source_text="DOMAIN,example.com\n",
                sources={
                    "required": {
                        "type": "file",
                        "path": "source.txt",
                        "format": "text",
                        "behavior": "classical",
                        "required": True,
                    },
                    "extension": {
                        "type": "file",
                        "path": "missing.txt",
                        "format": "text",
                        "behavior": "classical",
                        "required": False,
                    },
                },
                categories={
                    "direct": {
                        "family": "domain",
                        "sources": ["required", "extension"],
                        "formats": ["yaml", "json"],
                    }
                },
                actions={"direct-domain": ["direct"]},
            )

            report = build(BuildRequest(config, root / "published"))

            self.assertTrue(report.publishable)
            self.assertEqual(report.status, "degraded")
            self.assertTrue(any("extension" in warning for warning in report.warnings))
            self.assertTrue((root / "published" / "manifest.json").exists())

    def test_same_action_exact_conflict_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.txt").write_text("DOMAIN,example.com\n", encoding="utf-8")
            (root / "b.txt").write_text("DOMAIN,example.com\n", encoding="utf-8")
            config = write_project(
                root,
                source_text="DOMAIN,unused.example\n",
                sources={
                    "a": {
                        "type": "file",
                        "path": "a.txt",
                        "format": "text",
                        "behavior": "classical",
                    },
                    "b": {
                        "type": "file",
                        "path": "b.txt",
                        "format": "text",
                        "behavior": "classical",
                    },
                },
                categories={
                    "one": {
                        "family": "domain",
                        "sources": ["a"],
                        "formats": ["yaml", "json"],
                    },
                    "two": {
                        "family": "domain",
                        "sources": ["b"],
                        "formats": ["yaml", "json"],
                    },
                },
                actions={"direct-domain": ["one", "two"]},
            )

            report = build(BuildRequest(config, root / "published"))

            self.assertFalse(report.publishable)
            self.assertTrue(any("exact" in error for error in report.errors))
            self.assertFalse((root / "published").exists())

    def test_explicit_override_allows_parent_child_and_writes_override_output(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "parent.txt").write_text(
                "DOMAIN-SUFFIX,example.com\n", encoding="utf-8"
            )
            (root / "child.txt").write_text(
                "DOMAIN,api.example.com\n", encoding="utf-8"
            )
            config = write_project(
                root,
                source_text="DOMAIN,unused.example\n",
                sources={
                    "parent": {
                        "type": "file",
                        "path": "parent.txt",
                        "format": "text",
                        "behavior": "classical",
                    },
                    "child": {
                        "type": "file",
                        "path": "child.txt",
                        "format": "text",
                        "behavior": "classical",
                    },
                },
                categories={
                    "parent": {
                        "family": "domain",
                        "sources": ["parent"],
                        "formats": ["yaml", "json"],
                    },
                    "child": {
                        "family": "domain",
                        "sources": ["child"],
                        "formats": ["yaml", "json"],
                    },
                },
                actions={"direct-domain": ["parent", "child"]},
                overrides={
                    "schema_version": 1,
                    "force_direct": ["DOMAIN,api.example.com"],
                    "force_reject": [],
                    "force_proxy": [],
                },
            )

            report = build(BuildRequest(config, root / "published"))

            self.assertTrue(report.publishable, report.errors)
            self.assertTrue(
                (
                    root
                    / "published"
                    / "profiles"
                    / "default"
                    / "override-direct-domain.yaml"
                ).exists()
            )
            direct = yaml.safe_load(
                (
                    root / "published" / "profiles" / "default" / "direct-domain.yaml"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(direct["payload"], ["DOMAIN-SUFFIX,example.com"])

    def test_parent_child_without_override_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "parent.txt").write_text(
                "DOMAIN-SUFFIX,example.com\n", encoding="utf-8"
            )
            (root / "child.txt").write_text(
                "DOMAIN,api.example.com\n", encoding="utf-8"
            )
            config = write_project(
                root,
                source_text="DOMAIN,unused.example\n",
                sources={
                    "parent": {
                        "type": "file",
                        "path": "parent.txt",
                        "format": "text",
                        "behavior": "classical",
                    },
                    "child": {
                        "type": "file",
                        "path": "child.txt",
                        "format": "text",
                        "behavior": "classical",
                    },
                },
                categories={
                    "parent": {
                        "family": "domain",
                        "sources": ["parent"],
                        "formats": ["yaml"],
                    },
                    "child": {
                        "family": "domain",
                        "sources": ["child"],
                        "formats": ["yaml"],
                    },
                },
                actions={"direct-domain": ["parent", "child"]},
            )

            report = build(BuildRequest(config, root / "published"))

            self.assertFalse(report.publishable)
            self.assertTrue(any("parent-child" in error for error in report.errors))

    def test_keyword_category_does_not_emit_lossy_mrs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = write_project(
                root,
                source_text="DOMAIN-KEYWORD,example\n",
                sources={
                    "source": {
                        "type": "file",
                        "path": "source.txt",
                        "format": "text",
                        "behavior": "classical",
                    }
                },
                categories={
                    "ai": {
                        "family": "domain",
                        "sources": ["source"],
                        "formats": ["yaml", "json", "mrs"],
                    }
                },
                actions={"proxy-domain": ["ai"]},
                formats=["yaml", "json", "mrs"],
            )

            report = build(BuildRequest(config, root / "published"))

            self.assertTrue(report.publishable, report.errors)
            self.assertFalse((root / "published" / "categories" / "ai.mrs").exists())
            self.assertTrue(
                any(
                    item.get("skipped") == "lossy_format"
                    for item in report.outputs.values()
                    if isinstance(item, dict)
                )
            )

    def test_manifest_records_rule_counts_and_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = write_project(
                root,
                source_text="DOMAIN,example.com\n",
                sources={
                    "source": {
                        "type": "file",
                        "path": "source.txt",
                        "format": "text",
                        "behavior": "classical",
                    }
                },
                categories={
                    "direct": {
                        "family": "domain",
                        "sources": ["source"],
                        "formats": ["yaml", "json"],
                    }
                },
                actions={"direct-domain": ["direct"]},
            )

            report = build(BuildRequest(config, root / "published"))
            manifest = json.loads(
                (root / "published" / "manifest.json").read_text(encoding="utf-8")
            )

            self.assertTrue(report.publishable, report.errors)
            self.assertEqual(manifest["schema_version"], 2)
            self.assertEqual(manifest["outputs"]["categories/direct.yaml"]["rules"], 1)
            self.assertEqual(
                len(manifest["outputs"]["categories/direct.yaml"]["sha256"]), 64
            )
            self.assertEqual(manifest["sources"]["source"]["path"], "source.txt")

    def test_binary_formats_are_round_tripped_at_the_tool_seam(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = write_project(
                root,
                source_text="DOMAIN-SUFFIX,example.com\n",
                sources={
                    "source": {
                        "type": "file",
                        "path": "source.txt",
                        "format": "text",
                        "behavior": "classical",
                    }
                },
                categories={
                    "direct": {
                        "family": "domain",
                        "sources": ["source"],
                        "formats": ["yaml", "json", "srs", "mrs"],
                    }
                },
                actions={"direct-domain": ["direct"]},
                formats=["yaml", "json", "srs", "mrs"],
            )

            report = build(
                BuildRequest(config, root / "published", tool_adapter=self.FakeTools())
            )

            self.assertTrue(report.publishable, report.errors)
            self.assertTrue((root / "published" / "categories" / "direct.srs").exists())
            self.assertTrue((root / "published" / "categories" / "direct.mrs").exists())
            self.assertEqual(report.tools["mihomo"], "fake-mihomo")

    def test_baseline_drop_gate_fails_before_replacing_publish(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = write_project(
                root,
                source_text="DOMAIN,example.com\n",
                sources={
                    "source": {
                        "type": "file",
                        "path": "source.txt",
                        "format": "text",
                        "behavior": "classical",
                    }
                },
                categories={
                    "direct": {
                        "family": "domain",
                        "sources": ["source"],
                        "formats": ["yaml"],
                    }
                },
                actions={"direct-domain": ["direct"]},
            )
            baseline = root / "baseline.json"
            baseline.write_text(
                json.dumps({"outputs": {"categories/direct.yaml": {"rules": 100}}}),
                encoding="utf-8",
            )
            output = root / "published"
            output.mkdir()
            (output / "sentinel.txt").write_text("keep", encoding="utf-8")

            report = build(BuildRequest(config, output, baseline_manifest=baseline))

            self.assertFalse(report.publishable)
            self.assertTrue(any("dropped" in error for error in report.errors))
            self.assertEqual(
                report.baseline["changes"]["categories/direct.yaml"]["ratio"],
                -0.99,
            )
            self.assertEqual(
                (output / "sentinel.txt").read_text(encoding="utf-8"), "keep"
            )


if __name__ == "__main__":
    unittest.main()
