"""Deterministic output writers with semantic round-trip verification."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

import yaml

from .models import Rule
from .rules import (
    RuleError,
    dedupe,
    parse_payload,
    rule_to_classical,
    rule_to_domain_or_ip_text,
    to_sing_box_rules,
)
from .tools import ExternalTools


class LossyFormatError(ValueError):
    """Raised when a requested binary format cannot express every rule."""


@dataclass(frozen=True)
class RenderResult:
    content: bytes | None
    rules: int
    skipped: str | None = None

    def metadata(self) -> dict[str, object]:
        if self.skipped:
            return {"rules": self.rules, "skipped": self.skipped}
        assert self.content is not None
        return {
            "rules": self.rules,
            "bytes": len(self.content),
            "sha256": hashlib.sha256(self.content).hexdigest(),
        }


def render_rules(
    rules: Iterable[Rule], family: str, output_format: str, tools: ExternalTools
) -> RenderResult:
    rules_list = dedupe(rules)
    if not rules_list:
        raise ValueError("output rule set is empty")
    if output_format == "mrs" and any(
        rule.kind in {"domain_keyword", "domain_regex"} for rule in rules_list
    ):
        return RenderResult(None, len(rules_list), skipped="lossy_format")

    if output_format == "yaml":
        content = (
            yaml.safe_dump(
                {"payload": [rule_to_classical(rule) for rule in rules_list]},
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            )
            or ""
        ).encode("utf-8")
        _verify(content, rules_list, family, "yaml", tools)
        return RenderResult(content, len(rules_list))

    if output_format == "json":
        content = (
            json.dumps(
                {"version": 4, "rules": to_sing_box_rules(rules_list)},
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
        _verify(content, rules_list, family, "json", tools)
        return RenderResult(content, len(rules_list))

    if output_format == "srs":
        source = (
            json.dumps(
                {"version": 4, "rules": to_sing_box_rules(rules_list)},
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
        content = tools.compile_srs(source)
        _verify(content, rules_list, family, "srs", tools)
        return RenderResult(content, len(rules_list))

    if output_format == "mrs":
        try:
            lines = [rule_to_domain_or_ip_text(rule) for rule in rules_list]
        except RuleError as exc:
            raise LossyFormatError(str(exc)) from exc
        source = ("\n".join(lines) + "\n").encode("utf-8")
        content = tools.compile_mrs(source, family)
        _verify(content, rules_list, family, "mrs", tools)
        return RenderResult(content, len(rules_list))

    raise ValueError(f"unsupported output format: {output_format}")


def _verify(
    content: bytes,
    expected: Iterable[Rule],
    family: str,
    output_format: str,
    tools: ExternalTools,
) -> None:
    if not content:
        raise ValueError(f"{output_format} output is empty")
    if output_format == "yaml":
        actual = parse_payload(content, "yaml", "classical")
    elif output_format == "json":
        actual = parse_payload(content, "json", "sing-box")
    elif output_format == "srs":
        actual = parse_payload(tools.decompile_srs(content), "json", "sing-box")
    elif output_format == "mrs":
        behavior = "ipcidr" if family == "ipcidr" else "domain"
        actual = parse_payload(tools.decompile_mrs(content, behavior), "text", behavior)
    else:
        raise ValueError(f"cannot verify output format: {output_format}")
    expected_keys = {rule.key() for rule in expected}
    actual_keys = {rule.key() for rule in actual}
    if expected_keys != actual_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        raise ValueError(
            f"{output_format} semantic round-trip mismatch; missing={missing[:5]}, extra={extra[:5]}"
        )
