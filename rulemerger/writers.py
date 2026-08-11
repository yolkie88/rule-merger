"""Deterministic output writers with semantic round-trip verification."""

from __future__ import annotations

import hashlib
import ipaddress
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
    project_rule_for_sing_box,
    supports_mrs,
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
    omitted_kinds: tuple[str, ...] = ()

    def metadata(self) -> dict[str, object]:
        metadata: dict[str, object] = {"rules": self.rules}
        if self.omitted_kinds:
            metadata["omitted_kinds"] = list(self.omitted_kinds)
        if self.skipped:
            metadata["skipped"] = self.skipped
            return metadata
        assert self.content is not None
        metadata.update(
            {
                "bytes": len(self.content),
                "sha256": hashlib.sha256(self.content).hexdigest(),
            }
        )
        return metadata


def render_rules(
    rules: Iterable[Rule], family: str, output_format: str, tools: ExternalTools
) -> RenderResult:
    rules_list = dedupe(rules)
    if not rules_list:
        raise ValueError("output rule set is empty")

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
        rendered, omitted = _sing_box_projection(rules_list)
        if not rendered:
            return RenderResult(
                None,
                0,
                skipped="no_compatible_rules",
                omitted_kinds=omitted,
            )
        content = (
            json.dumps(
                {"version": 4, "rules": to_sing_box_rules(rendered)},
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
        _verify(content, rendered, family, "json", tools)
        return RenderResult(content, len(rendered), omitted_kinds=omitted)

    if output_format == "srs":
        rendered, omitted = _sing_box_projection(rules_list)
        if not rendered:
            return RenderResult(
                None,
                0,
                skipped="no_compatible_rules",
                omitted_kinds=omitted,
            )
        source = (
            json.dumps(
                {"version": 4, "rules": to_sing_box_rules(rendered)},
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
        content = tools.compile_srs(source)
        _verify(content, rendered, family, "srs", tools)
        return RenderResult(content, len(rendered), omitted_kinds=omitted)

    if output_format == "mrs":
        rendered = [rule for rule in rules_list if supports_mrs(rule)]
        omitted = _omitted_kinds(rules_list, rendered)
        if not rendered:
            return RenderResult(
                None,
                0,
                skipped="no_compatible_rules",
                omitted_kinds=omitted,
            )
        try:
            lines = [rule_to_domain_or_ip_text(rule) for rule in rendered]
        except RuleError as exc:
            raise LossyFormatError(str(exc)) from exc
        source = ("\n".join(lines) + "\n").encode("utf-8")
        content = tools.compile_mrs(source, family)
        _verify(content, rendered, family, "mrs", tools)
        return RenderResult(content, len(rendered), omitted_kinds=omitted)

    raise ValueError(f"unsupported output format: {output_format}")


def _sing_box_projection(rules: Iterable[Rule]) -> tuple[list[Rule], tuple[str, ...]]:
    rendered: list[Rule] = []
    omitted: list[str] = []
    for rule in rules:
        projected = project_rule_for_sing_box(rule)
        if projected is None:
            omitted.append(rule.kind)
        else:
            rendered.append(projected)
    return dedupe(rendered), tuple(sorted(set(omitted)))


def _omitted_kinds(original: Iterable[Rule], rendered: Iterable[Rule]) -> tuple[str, ...]:
    rendered_keys = {rule.key() for rule in rendered}
    return tuple(
        sorted({rule.kind for rule in original if rule.key() not in rendered_keys})
    )


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
    expected_rules = tuple(expected)
    actual_rules = tuple(actual)
    if output_format == "mrs" and family == "domain":
        # Mihomo's domain behavior has suffix matching semantics; its
        # decompiler makes that explicit with `+.`.  Validate against the
        # target representation rather than mistaking this canonical form for
        # a failed conversion.
        expected_rules = tuple(
            Rule("domain_suffix", rule.value) if rule.kind == "domain" else rule
            for rule in expected_rules
        )
    normalize_cidrs = family == "ipcidr" and output_format in {"srs", "mrs"}
    expected_keys = _semantic_keys(expected_rules, normalize_cidrs)
    actual_keys = _semantic_keys(actual_rules, normalize_cidrs)
    if expected_keys != actual_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        raise ValueError(
            f"{output_format} semantic round-trip mismatch; missing={missing[:5]}, extra={extra[:5]}"
        )


def _semantic_keys(
    rules: Iterable[Rule], normalize_cidrs: bool
) -> set[tuple[str, str]]:
    """Normalize tool canonicalisation while retaining matching semantics."""

    if not normalize_cidrs:
        return {rule.key() for rule in rules}
    networks = [ipaddress.ip_network(rule.value) for rule in rules]
    return {("ip_cidr", network.with_prefixlen) for network in ipaddress.collapse_addresses(networks)}
