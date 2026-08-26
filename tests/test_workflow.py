from __future__ import annotations

import unittest
from pathlib import Path

import yaml


class WorkflowTests(unittest.TestCase):
    def test_release_lookup_fails_closed_on_fetch_errors(self) -> None:
        workflow_path = (
            Path(__file__).parents[1] / ".github" / "workflows" / "resolve.yml"
        )
        workflow = workflow_path.read_text(encoding="utf-8")
        document = yaml.safe_load(workflow)
        self.assertIn("  push:\n    branches:\n      - master", workflow)
        build_step = next(
            step
            for step in document["jobs"]["build"]["steps"]
            if step.get("name") == "Test and build"
        )
        script = build_step["run"]

        self.assertNotIn(
            "git fetch origin release:refs/remotes/origin/release || true",
            script,
        )
        self.assertIn("git ls-remote --exit-code --heads origin release", script)
        self.assertIn("git fetch origin release:refs/remotes/origin/release", script)
        self.assertIn("remote_status=$?", script)
        self.assertIn('if [ "$remote_status" -eq 0 ]', script)
        self.assertIn('elif [ "$remote_status" -eq 2 ]', script)
        self.assertIn('exit "$remote_status"', script)

    def test_manual_run_can_approve_only_named_output_growth(self) -> None:
        workflow_path = (
            Path(__file__).parents[1] / ".github" / "workflows" / "resolve.yml"
        )
        workflow = workflow_path.read_text(encoding="utf-8")
        document = yaml.safe_load(workflow)
        build_step = next(
            step
            for step in document["jobs"]["build"]["steps"]
            if step.get("name") == "Test and build"
        )

        self.assertEqual(
            build_step["env"]["ALLOWED_GROWTH_OUTPUTS"],
            "${{ inputs.allowed_growth_outputs }}",
        )
        self.assertIn('growth_args+=(--allow-growth "$output")', build_step["run"])
        self.assertIn('"${growth_args[@]}"', build_step["run"])


if __name__ == "__main__":
    unittest.main()
