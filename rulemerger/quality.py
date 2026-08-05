"""Conflict, baseline, and semantic quality gates."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Iterable, Mapping

from .models import Rule


@dataclass(frozen=True)
class Conflict:
    left: str
    right: str
    relation: str
    rule: str
    other: str
    authorized: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "left": self.left,
            "right": self.right,
            "relation": self.relation,
            "rule": self.rule,
            "other": self.other,
            "authorized": self.authorized,
        }


def duplicate_category_conflicts(
    segments: Mapping[str, Iterable[Rule]],
) -> list[Conflict]:
    """Find exact duplicate rules assigned to two categories in one action."""

    owners: dict[tuple[str, str], list[str]] = {}
    for segment, rules in segments.items():
        for rule in rules:
            owners.setdefault(rule.key(), []).append(segment)
    conflicts: list[Conflict] = []
    for rule_key, names in owners.items():
        if len(names) < 2:
            continue
        for index, left in enumerate(names[:-1]):
            for right in names[index + 1 :]:
                conflicts.append(
                    Conflict(
                        left,
                        right,
                        "exact",
                        f"{rule_key[0]}:{rule_key[1]}",
                        f"{rule_key[0]}:{rule_key[1]}",
                    )
                )
    return conflicts


def find_segment_conflicts(
    segments: Mapping[str, Iterable[Rule]],
    override_rules: Iterable[Rule] = (),
) -> list[Conflict]:
    """Find exact and containment conflicts between named segments efficiently."""

    names = list(segments)
    normalized = {name: tuple(segments[name]) for name in names}
    override_keys = {rule.key() for rule in override_rules}
    conflicts: list[Conflict] = []
    seen: set[tuple[str, str, str, tuple[str, str], tuple[str, str]]] = set()

    for left_index, left_name in enumerate(names[:-1]):
        for right_name in names[left_index + 1 :]:
            left_rules = normalized[left_name]
            right_rules = normalized[right_name]
            right_by_key = {rule.key(): rule for rule in right_rules}
            right_suffixes = {
                rule.value: rule for rule in right_rules if rule.kind == "domain_suffix"
            }
            right_cidrs = {
                ipaddress.ip_network(rule.value): rule
                for rule in right_rules
                if rule.kind == "ip_cidr"
            }

            for left_rule in left_rules:
                exact = right_by_key.get(left_rule.key())
                if exact is not None:
                    _append_conflict(
                        conflicts,
                        seen,
                        left_name,
                        right_name,
                        "exact",
                        left_rule,
                        exact,
                        False,
                        override_keys,
                    )

                if left_rule.kind in {"domain", "domain_suffix"}:
                    for parent_value in _domain_parent_values(left_rule.value):
                        parent = right_suffixes.get(parent_value)
                        if parent is not None and parent.key() != left_rule.key():
                            _append_conflict(
                                conflicts,
                                seen,
                                left_name,
                                right_name,
                                "parent-child",
                                left_rule,
                                parent,
                                _specific_key(left_rule, parent) in override_keys,
                                override_keys,
                            )

                if left_rule.kind == "ip_cidr":
                    network = ipaddress.ip_network(left_rule.value)
                    for prefix_length in range(network.prefixlen):
                        parent_network = network.supernet(new_prefix=prefix_length)
                        parent = right_cidrs.get(parent_network)
                        if parent is not None:
                            _append_conflict(
                                conflicts,
                                seen,
                                left_name,
                                right_name,
                                "cidr-overlap",
                                left_rule,
                                parent,
                                _specific_key(left_rule, parent) in override_keys,
                                override_keys,
                            )

            # The first direction finds a right-side parent of a left rule.
            # Walk the other direction as well so a left-side parent and a
            # right-side child are not silently missed.
            left_by_key = {rule.key(): rule for rule in left_rules}
            left_suffixes = {
                rule.value: rule for rule in left_rules if rule.kind == "domain_suffix"
            }
            left_cidrs = {
                ipaddress.ip_network(rule.value): rule
                for rule in left_rules
                if rule.kind == "ip_cidr"
            }
            for right_rule in right_rules:
                exact = left_by_key.get(right_rule.key())
                if exact is not None:
                    _append_conflict(
                        conflicts,
                        seen,
                        right_name,
                        left_name,
                        "exact",
                        right_rule,
                        exact,
                        False,
                        override_keys,
                    )
                if right_rule.kind in {"domain", "domain_suffix"}:
                    for parent_value in _domain_parent_values(right_rule.value):
                        parent = left_suffixes.get(parent_value)
                        if parent is not None and parent.key() != right_rule.key():
                            _append_conflict(
                                conflicts,
                                seen,
                                right_name,
                                left_name,
                                "parent-child",
                                right_rule,
                                parent,
                                _specific_key(right_rule, parent) in override_keys,
                                override_keys,
                            )
                if right_rule.kind == "ip_cidr":
                    network = ipaddress.ip_network(right_rule.value)
                    for prefix_length in range(network.prefixlen):
                        parent_network = network.supernet(new_prefix=prefix_length)
                        parent = left_cidrs.get(parent_network)
                        if parent is not None:
                            _append_conflict(
                                conflicts,
                                seen,
                                right_name,
                                left_name,
                                "cidr-overlap",
                                right_rule,
                                parent,
                                _specific_key(right_rule, parent) in override_keys,
                                override_keys,
                            )

    return conflicts


def _append_conflict(
    conflicts: list[Conflict],
    seen: set[tuple[str, str, str, tuple[str, str], tuple[str, str]]],
    left_name: str,
    right_name: str,
    relation: str,
    left: Rule,
    right: Rule,
    _authorized_hint: bool,
    override_keys: set[tuple[str, str]],
) -> None:
    marker = (left_name, right_name, relation, left.key(), right.key())
    reverse = (right_name, left_name, relation, right.key(), left.key())
    if marker in seen or reverse in seen:
        return
    seen.add(marker)
    conflicts.append(
        Conflict(
            left_name,
            right_name,
            relation,
            f"{left.kind}:{left.value}",
            f"{right.kind}:{right.value}",
            authorized=_specific_key(left, right) in override_keys
            if relation != "exact"
            else False,
        )
    )


def _specific_key(left: Rule, right: Rule) -> tuple[str, str]:
    if left.kind == "ip_cidr" and right.kind == "ip_cidr":
        left_network = ipaddress.ip_network(left.value)
        right_network = ipaddress.ip_network(right.value)
        return (
            left.key()
            if left_network.prefixlen > right_network.prefixlen
            else right.key()
        )
    if left.kind == "domain" and right.kind == "domain_suffix":
        return left.key()
    if left.kind == "domain_suffix" and right.kind == "domain":
        return right.key()
    if left.kind == "domain_suffix" and right.kind == "domain_suffix":
        return left.key() if len(left.value) > len(right.value) else right.key()
    return left.key()


def _domain_parent_values(value: str) -> tuple[str, ...]:
    labels = value.split(".")
    return tuple(
        ".".join(labels[index:]) for index in range(0, max(0, len(labels) - 1))
    )


def compare_count(
    name: str,
    current: int,
    baseline: int | None,
    max_drop_ratio: float,
    max_growth_ratio: float,
    small_output_limit: int,
) -> str | None:
    if current <= 0:
        return f"{name} is empty"
    if baseline is None or baseline < small_output_limit:
        return None
    drop = (baseline - current) / baseline
    growth = (current - baseline) / baseline
    if drop > max_drop_ratio:
        return f"{name} dropped from {baseline} to {current} ({drop:.1%})"
    if growth > max_growth_ratio:
        return f"{name} grew from {baseline} to {current} ({growth:.1%})"
    return None


def critical_rule_errors(
    outputs: Mapping[str, Iterable[Rule]],
    critical_rules: Mapping[str, Iterable[str]],
) -> list[str]:
    errors: list[str] = []
    from .rules import parse_rule

    for output_name, expected_values in critical_rules.items():
        actual = {rule.key() for rule in outputs.get(output_name, ())}
        for value in expected_values:
            try:
                expected = parse_rule(value, "classical")
            except ValueError as exc:
                errors.append(f"{output_name} critical rule is invalid: {value}: {exc}")
                continue
            if any(rule.key() not in actual for rule in expected):
                errors.append(f"{output_name} is missing critical rule: {value}")
    return errors
