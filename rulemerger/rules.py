"""Parsing, canonicalisation, and format projections for rule values."""

from __future__ import annotations

import ipaddress
import json
import re
from typing import Any, Iterable

from .models import Rule


DOMAIN_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
DOMAIN_KINDS = {"domain", "domain_suffix", "domain_keyword", "domain_regex"}


class RuleError(ValueError):
    """Raised when a source contains an invalid or unsupported rule."""


def parse_payload(payload: Any, source_format: str, behavior: str) -> list[Rule]:
    """Parse a source payload and fail on the first non-comment invalid rule."""

    if source_format == "text":
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        if not isinstance(payload, str):
            raise RuleError("text payload must be a string")
        result: list[Rule] = []
        for line_number, line in enumerate(payload.splitlines(), start=1):
            cleaned = _clean_line(line)
            if not cleaned:
                continue
            try:
                result.extend(parse_rule(cleaned, behavior))
            except RuleError as exc:
                raise RuleError(f"line {line_number}: {exc}") from exc
        return result

    if source_format == "yaml":
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        if isinstance(payload, str):
            try:
                payload = (
                    json.loads(payload)
                    if payload.lstrip().startswith(("{", "["))
                    else _safe_yaml(payload)
                )
            except (ValueError, TypeError) as exc:
                raise RuleError(f"invalid YAML payload: {exc}") from exc
        values = _extract_values(payload, "YAML")
        return _parse_values(values, behavior)

    if source_format == "json":
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise RuleError(f"invalid JSON payload: {exc}") from exc
        return parse_sing_box(payload)

    raise RuleError(f"source format {source_format} must be decompiled before parsing")


def _safe_yaml(value: str) -> Any:
    import yaml

    return yaml.safe_load(value)


def _extract_values(payload: Any, label: str) -> list[Any]:
    if isinstance(payload, dict):
        for key in ("payload", "rules", "items"):
            if isinstance(payload.get(key), list):
                return payload[key]
        raise RuleError(f"{label} payload must contain a list under payload")
    if isinstance(payload, list):
        return payload
    raise RuleError(f"{label} payload must be a list")


def _parse_values(values: Iterable[Any], behavior: str) -> list[Rule]:
    result: list[Rule] = []
    for index, value in enumerate(values, start=1):
        if not isinstance(value, str):
            raise RuleError(f"rule {index} must be a string")
        cleaned = _clean_line(value)
        if not cleaned:
            continue
        try:
            result.extend(parse_rule(cleaned, behavior))
        except RuleError as exc:
            raise RuleError(f"rule {index}: {exc}") from exc
    return result


def parse_rule(value: str, behavior: str = "classical") -> tuple[Rule, ...]:
    if not isinstance(value, str):
        raise RuleError("rule must be a string")
    cleaned = _clean_line(value)
    if not cleaned:
        return ()
    if behavior == "sing-box":
        raise RuleError("sing-box rules must be supplied as JSON objects")

    if "," in cleaned:
        rule_type, raw_value = cleaned.split(",", 1)
        rule_type = rule_type.strip().upper()
        if rule_type in {
            "DOMAIN",
            "DOMAIN-SUFFIX",
            "DOMAIN-KEYWORD",
            "IP-CIDR",
            "IP-CIDR6",
        }:
            raw_value = raw_value.split(",", 1)[0].strip()
        else:
            raw_value = raw_value.strip()
        if rule_type == "DOMAIN":
            return (_domain_rule("domain", raw_value),)
        if rule_type == "DOMAIN-SUFFIX":
            return (_domain_rule("domain_suffix", raw_value),)
        if rule_type == "DOMAIN-KEYWORD":
            if not raw_value:
                raise RuleError("DOMAIN-KEYWORD value is empty")
            return (Rule("domain_keyword", raw_value.lower()),)
        if rule_type == "DOMAIN-REGEX":
            if not raw_value:
                raise RuleError("DOMAIN-REGEX value is empty")
            try:
                re.compile(raw_value)
            except re.error as exc:
                raise RuleError(f"invalid DOMAIN-REGEX: {exc}") from exc
            return (Rule("domain_regex", raw_value),)
        if rule_type in {"IP-CIDR", "IP-CIDR6"}:
            rule = _ip_rule(raw_value)
            expected_version = 6 if rule_type == "IP-CIDR6" else 4
            if ipaddress.ip_network(rule.value).version != expected_version:
                raise RuleError(f"{rule_type} has the wrong IP version")
            return (rule,)
        raise RuleError(f"unsupported classical rule type: {rule_type}")

    if behavior == "domain":
        if cleaned.startswith("+."):
            return (_domain_rule("domain_suffix", cleaned[2:]),)
        return (_domain_rule("domain", cleaned),)
    if behavior == "ipcidr":
        return (_ip_rule(cleaned),)
    if behavior == "classical":
        raise RuleError("classical rule must have a supported type prefix")
    raise RuleError(f"unsupported behavior: {behavior}")


def parse_sing_box(payload: Any) -> list[Rule]:
    if not isinstance(payload, dict):
        raise RuleError("sing-box payload must be an object")
    raw_rules = payload.get("rules")
    if not isinstance(raw_rules, list):
        raise RuleError("sing-box payload must contain a rules list")
    result: list[Rule] = []
    for index, item in enumerate(raw_rules, start=1):
        if not isinstance(item, dict):
            raise RuleError(f"sing-box rule {index} must be an object")
        result.extend(_parse_sing_box_item(item))
    return result


def _parse_sing_box_item(item: dict[str, Any]) -> list[Rule]:
    if item.get("type") == "logical":
        raise RuleError(
            "logical sing-box rules are unsupported because the unified model "
            "cannot preserve their AND/OR semantics"
        )
    result: list[Rule] = []
    for key, kind in (
        ("domain", "domain"),
        ("domain_suffix", "domain_suffix"),
        ("domain_keyword", "domain_keyword"),
        ("domain_regex", "domain_regex"),
    ):
        for value in _as_list(item.get(key)):
            if not isinstance(value, str):
                raise RuleError(f"sing-box {key} values must be strings")
            if kind in {"domain", "domain_suffix"}:
                result.append(
                    _domain_rule(
                        kind, value.lstrip(".") if kind == "domain_suffix" else value
                    )
                )
            elif kind == "domain_keyword":
                if not value:
                    raise RuleError("sing-box domain_keyword value is empty")
                result.append(Rule(kind, value.lower()))
            else:
                try:
                    re.compile(value)
                except re.error as exc:
                    raise RuleError(f"invalid sing-box domain_regex: {exc}") from exc
                result.append(Rule(kind, value))
    for value in _as_list(item.get("ip_cidr")):
        if not isinstance(value, str):
            raise RuleError("sing-box ip_cidr values must be strings")
        result.append(_ip_rule(value))
    if not result:
        raise RuleError("sing-box rule contains no supported match fields")
    return result


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _clean_line(value: str) -> str:
    value = value.strip()
    if not value or value.startswith("#"):
        return ""
    return re.split(r"\s+#", value, maxsplit=1)[0].strip()


def _domain_rule(kind: str, value: str) -> Rule:
    value = value.strip().lower().lstrip(".")
    if not value or not _valid_domain(value):
        raise RuleError(f"invalid domain: {value!r}")
    return Rule(kind, value)


def _valid_domain(value: str) -> bool:
    if not value or len(value) > 253:
        return False
    try:
        ascii_value = value.encode("idna").decode("ascii")
    except UnicodeError:
        return False
    return all(DOMAIN_LABEL.fullmatch(label) for label in ascii_value.split("."))


def _ip_rule(value: str) -> Rule:
    try:
        network = ipaddress.ip_network(value.strip(), strict=False)
    except ValueError as exc:
        raise RuleError(f"invalid CIDR: {value!r}") from exc
    return Rule("ip_cidr", network.with_prefixlen)


def dedupe(rules: Iterable[Rule]) -> list[Rule]:
    result: list[Rule] = []
    seen: set[tuple[str, str]] = set()
    for rule in rules:
        if rule.key() not in seen:
            seen.add(rule.key())
            result.append(rule)
    return result


def rule_to_classical(rule: Rule) -> str:
    prefixes = {
        "domain": "DOMAIN",
        "domain_suffix": "DOMAIN-SUFFIX",
        "domain_keyword": "DOMAIN-KEYWORD",
        "domain_regex": "DOMAIN-REGEX",
    }
    if rule.kind in prefixes:
        return f"{prefixes[rule.kind]},{rule.value}"
    if rule.kind == "ip_cidr":
        version = ipaddress.ip_network(rule.value).version
        return f"IP-CIDR{6 if version == 6 else ''},{rule.value}"
    raise RuleError(f"unsupported rule kind: {rule.kind}")


def rule_to_sing_box(rule: Rule) -> dict[str, list[str]]:
    fields = {
        "domain": "domain",
        "domain_suffix": "domain_suffix",
        "domain_keyword": "domain_keyword",
        "domain_regex": "domain_regex",
        "ip_cidr": "ip_cidr",
    }
    try:
        field = fields[rule.kind]
    except KeyError as exc:
        raise RuleError(f"unsupported rule kind: {rule.kind}") from exc
    return {field: [rule.value]}


def to_sing_box_rules(rules: Iterable[Rule]) -> list[dict[str, list[str]]]:
    grouped: dict[str, list[str]] = {}
    for rule in rules:
        item = rule_to_sing_box(rule)
        field, values = next(iter(item.items()))
        grouped.setdefault(field, []).extend(values)
    return [{field: values} for field, values in grouped.items()]


def rule_to_domain_or_ip_text(rule: Rule) -> str:
    if rule.kind == "domain_suffix":
        return f"+.{rule.value}"
    if rule.kind == "domain":
        return rule.value
    if rule.kind == "ip_cidr":
        return rule.value
    raise RuleError(f"{rule.kind} cannot be represented losslessly by MRS")


def family_of(rule: Rule) -> str:
    if rule.kind == "ip_cidr":
        return "ipcidr"
    if rule.kind in DOMAIN_KINDS:
        return "domain"
    raise RuleError(f"unknown rule family: {rule.kind}")
