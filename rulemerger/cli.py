"""Command line entry point for the v2 build interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .build import build
from .models import BuildRequest


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m rulemerger")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser(
        "build", help="build and atomically publish rule outputs"
    )
    build_parser.add_argument("--config", type=Path, required=True)
    build_parser.add_argument("--output", type=Path, required=True)
    build_parser.add_argument("--baseline", type=Path)
    build_parser.add_argument("--report", type=Path)
    build_parser.add_argument("--mihomo-path", default="mihomo")
    build_parser.add_argument("--sing-box-path", default="sing-box")
    build_parser.add_argument("--include-legacy", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    if args.command != "build":
        return 2
    report = build(
        BuildRequest(
            config_path=args.config,
            output_dir=args.output,
            baseline_manifest=args.baseline,
            report_path=args.report,
            mihomo_path=args.mihomo_path,
            sing_box_path=args.sing_box_path,
            include_legacy=args.include_legacy,
        )
    )
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.publishable else 1
