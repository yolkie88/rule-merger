"""Strict v2 configuration and override loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import CategorySpec, Config, OverrideSet, ProfileSpec, SourceSpec
from .rules import RuleError, dedupe, parse_rule


class ConfigError(ValueError):
    """Raised when a v2 configuration violates its schema."""


SOURCE_TYPES = {"http", "file"}
SOURCE_FORMATS = {"text", "yaml", "json", "srs", "mrs"}
BEHAVIORS = {"classical", "domain", "ipcidr", "sing-box"}
OUTPUT_FORMATS = {"yaml", "json", "srs", "mrs"}
FAMILIES = {"domain", "ipcidr"}
ACTION_NAMES = {
    f"{action}-{family}"
    for action in ("direct", "reject", "proxy")
    for family in ("domain", "ip")
}
TOP_LEVEL_FIELDS = {
    "schema_version",
    "sources",
    "categories",
    "profiles",
    "overrides",
    "quality",
    "legacy",
}
QUALITY_FIELDS = {
    "max_drop_ratio",
    "max_growth_ratio",
    "max_growth_ratio_overrides",
    "small_output_limit",
    "min_rules",
    "critical_rules",
    "allowed_removed_outputs",
}
LEGACY_FIELDS = {"enabled", "aliases"}


class UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader variant that does not silently overwrite duplicate keys."""


def _construct_mapping(
    loader: UniqueKeyLoader, node: yaml.nodes.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ConfigError("mapping keys must be hashable") from exc
        if duplicate:
            raise ConfigError(f"duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{label} must be a mapping")
    return value


def _strings(value: Any, label: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise ConfigError(f"{label} must be a non-empty string list")
    if not all(isinstance(item, str) and item for item in value):
        raise ConfigError(f"{label} must contain only non-empty strings")
    if len(set(value)) != len(value):
        raise ConfigError(f"{label} contains duplicates")
    return tuple(value)


def _allowed(item: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(item) - allowed
    if unknown:
        raise ConfigError(f"{label} has unknown fields: {', '.join(sorted(unknown))}")


def _load_yaml(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.load(handle, Loader=UniqueKeyLoader)
    except FileNotFoundError as exc:
        raise ConfigError(f"config not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML: {exc}") from exc


def load_config(path: str | Path) -> Config:
    config_path = Path(path).resolve()
    root = _mapping(_load_yaml(config_path), "config")
    _allowed(root, TOP_LEVEL_FIELDS, "config")
    missing = TOP_LEVEL_FIELDS - set(root)
    if missing:
        raise ConfigError(f"config is missing fields: {', '.join(sorted(missing))}")
    if root.get("schema_version") != 2:
        raise ConfigError("schema_version must be 2")

    source_values = _mapping(root["sources"], "sources")
    if not source_values:
        raise ConfigError("sources must not be empty")
    sources: dict[str, SourceSpec] = {}
    for source_id, value in source_values.items():
        if not isinstance(source_id, str) or not source_id:
            raise ConfigError("source IDs must be non-empty strings")
        item = _mapping(value, f"sources.{source_id}")
        _allowed(
            item,
            {
                "type",
                "format",
                "behavior",
                "url",
                "path",
                "required",
                "redistributable",
            },
            f"sources.{source_id}",
        )
        source_type = item.get("type")
        source_format = item.get("format")
        behavior = item.get("behavior")
        if source_type not in SOURCE_TYPES:
            raise ConfigError(f"sources.{source_id}.type must be http or file")
        if source_format not in SOURCE_FORMATS:
            raise ConfigError(f"sources.{source_id}.format is invalid")
        if behavior not in BEHAVIORS:
            raise ConfigError(f"sources.{source_id}.behavior is invalid")
        required = item.get("required", True)
        if not isinstance(required, bool):
            raise ConfigError(f"sources.{source_id}.required must be boolean")
        redistributable = item.get("redistributable", False)
        if not isinstance(redistributable, bool):
            raise ConfigError(f"sources.{source_id}.redistributable must be boolean")
        if source_type == "http":
            if "path" in item:
                raise ConfigError(
                    f"sources.{source_id}.path is only valid for file sources"
                )
            url = item.get("url")
            if not isinstance(url, str) or not url:
                raise ConfigError(f"sources.{source_id} requires url")
            if not url.startswith(("https://", "http://")):
                raise ConfigError(f"sources.{source_id}.url must be http or https")
            source_path = None
        else:
            if "url" in item:
                raise ConfigError(
                    f"sources.{source_id}.url is only valid for http sources"
                )
            source_path = item.get("path")
            if not isinstance(source_path, str) or not source_path:
                raise ConfigError(f"sources.{source_id} requires path")
            url = None

        if source_format in {"json", "srs"} and behavior != "sing-box":
            raise ConfigError(
                f"sources.{source_id}: {source_format} requires sing-box behavior"
            )
        if source_format == "mrs" and behavior not in {"domain", "ipcidr"}:
            raise ConfigError(
                f"sources.{source_id}: mrs requires domain or ipcidr behavior"
            )
        if behavior == "sing-box" and source_format not in {"json", "srs"}:
            raise ConfigError(
                f"sources.{source_id}: sing-box behavior requires json or srs"
            )

        sources[source_id] = SourceSpec(
            id=source_id,
            type=source_type,
            format=source_format,
            behavior=behavior,
            url=url,
            path=source_path,
            required=required,
            redistributable=redistributable,
        )

    category_values = _mapping(root["categories"], "categories")
    if not category_values:
        raise ConfigError("categories must not be empty")
    categories: dict[str, CategorySpec] = {}
    for category_id, value in category_values.items():
        if not isinstance(category_id, str) or not category_id:
            raise ConfigError("category IDs must be non-empty strings")
        item = _mapping(value, f"categories.{category_id}")
        _allowed(item, {"family", "sources", "formats"}, f"categories.{category_id}")
        family = item.get("family")
        if family not in FAMILIES:
            raise ConfigError(
                f"categories.{category_id}.family must be domain or ipcidr"
            )
        source_ids = _strings(item.get("sources"), f"categories.{category_id}.sources")
        missing_sources = set(source_ids) - set(sources)
        if missing_sources:
            raise ConfigError(
                f"categories.{category_id} references missing sources: {', '.join(sorted(missing_sources))}"
            )
        formats = _strings(item.get("formats"), f"categories.{category_id}.formats")
        if set(formats) - OUTPUT_FORMATS:
            raise ConfigError(
                f"categories.{category_id}.formats contains an invalid format"
            )
        categories[category_id] = CategorySpec(category_id, family, source_ids, formats)

    profile_values = _mapping(root["profiles"], "profiles")
    if not profile_values:
        raise ConfigError("profiles must not be empty")
    profiles: dict[str, ProfileSpec] = {}
    for profile_id, value in profile_values.items():
        if not isinstance(profile_id, str) or not profile_id:
            raise ConfigError("profile IDs must be non-empty strings")
        item = _mapping(value, f"profiles.{profile_id}")
        _allowed(item, {"actions", "formats"}, f"profiles.{profile_id}")
        action_values = _mapping(item.get("actions"), f"profiles.{profile_id}.actions")
        if not action_values:
            raise ConfigError(f"profiles.{profile_id}.actions must not be empty")
        actions: dict[str, tuple[str, ...]] = {}
        for action, category_ids_value in action_values.items():
            if action not in ACTION_NAMES:
                raise ConfigError(f"profiles.{profile_id}.actions.{action} is invalid")
            category_ids = _strings(
                category_ids_value, f"profiles.{profile_id}.actions.{action}"
            )
            missing_categories = set(category_ids) - set(categories)
            if missing_categories:
                raise ConfigError(
                    f"profiles.{profile_id}.actions.{action} references missing categories: "
                    + ", ".join(sorted(missing_categories))
                )
            family = "ipcidr" if action.endswith("-ip") else "domain"
            incompatible = [
                category_id
                for category_id in category_ids
                if categories[category_id].family != family
            ]
            if incompatible:
                raise ConfigError(
                    f"profiles.{profile_id}.actions.{action} requires {family} categories: "
                    + ", ".join(incompatible)
                )
            actions[action] = category_ids
        formats = _strings(item.get("formats"), f"profiles.{profile_id}.formats")
        if set(formats) - OUTPUT_FORMATS:
            raise ConfigError(
                f"profiles.{profile_id}.formats contains an invalid format"
            )
        profiles[profile_id] = ProfileSpec(profile_id, actions, formats)

    quality = _validate_quality(root["quality"])
    legacy = _validate_legacy(root["legacy"])
    overrides_value = root["overrides"]
    if overrides_value is None:
        overrides_path = None
    elif isinstance(overrides_value, str) and overrides_value:
        overrides_path = (config_path.parent / overrides_value).resolve()
    else:
        raise ConfigError("overrides must be a relative path or null")

    referenced_sources = {
        source_id for category in categories.values() for source_id in category.sources
    }
    unused_sources = set(sources) - referenced_sources
    if unused_sources:
        raise ConfigError(f"unreferenced sources: {', '.join(sorted(unused_sources))}")

    return Config(
        root=config_path.parent,
        sources=sources,
        categories=categories,
        profiles=profiles,
        overrides_path=overrides_path,
        quality=quality,
        legacy=legacy,
    )


def _validate_quality(value: Any) -> dict[str, Any]:
    item = _mapping(value, "quality")
    _allowed(item, QUALITY_FIELDS, "quality")
    result: dict[str, Any] = {
        "max_drop_ratio": 0.15,
        "max_growth_ratio": 0.50,
        "max_growth_ratio_overrides": {},
        "small_output_limit": 100,
        "min_rules": {},
        "critical_rules": {},
        "allowed_removed_outputs": (),
    }
    for key in ("max_drop_ratio", "max_growth_ratio"):
        if key in item:
            value_number = item[key]
            if (
                not isinstance(value_number, (int, float))
                or isinstance(value_number, bool)
                or value_number < 0
            ):
                raise ConfigError(f"quality.{key} must be a non-negative number")
            if key == "max_drop_ratio" and value_number >= 1:
                raise ConfigError("quality.max_drop_ratio must be less than 1")
            result[key] = float(value_number)
    if "max_growth_ratio_overrides" in item:
        overrides = item["max_growth_ratio_overrides"]
        if not isinstance(overrides, dict):
            raise ConfigError("quality.max_growth_ratio_overrides must be a mapping")
        normalized: dict[str, float] = {}
        for output_name, value_number in overrides.items():
            if (
                not isinstance(output_name, str)
                or not output_name
                or not isinstance(value_number, (int, float))
                or isinstance(value_number, bool)
                or value_number < 0
            ):
                raise ConfigError(
                    "quality.max_growth_ratio_overrides must map output names "
                    "to non-negative numbers"
                )
            normalized[output_name] = float(value_number)
        result["max_growth_ratio_overrides"] = normalized
    if "small_output_limit" in item:
        limit = item["small_output_limit"]
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
            raise ConfigError(
                "quality.small_output_limit must be a non-negative integer"
            )
        result["small_output_limit"] = limit
    for key in ("min_rules", "critical_rules"):
        if key not in item:
            continue
        if not isinstance(item[key], dict):
            raise ConfigError(f"quality.{key} must be a mapping")
        if key == "min_rules":
            for output_name, minimum in item[key].items():
                if (
                    not isinstance(output_name, str)
                    or not isinstance(minimum, int)
                    or isinstance(minimum, bool)
                    or minimum < 0
                ):
                    raise ConfigError(
                        "quality.min_rules must map output names to non-negative integers"
                    )
        else:
            for output_name, values in item[key].items():
                if (
                    not isinstance(output_name, str)
                    or not isinstance(values, list)
                    or not values
                    or not all(isinstance(value, str) and value for value in values)
                ):
                    raise ConfigError(
                        "quality.critical_rules must map output names to string lists"
                    )
        result[key] = item[key]
    if "allowed_removed_outputs" in item:
        result["allowed_removed_outputs"] = _strings(
            item["allowed_removed_outputs"],
            "quality.allowed_removed_outputs",
        )
    return result


def _validate_legacy(value: Any) -> dict[str, Any]:
    item = _mapping(value, "legacy")
    _allowed(item, LEGACY_FIELDS, "legacy")
    enabled = item.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ConfigError("legacy.enabled must be boolean")
    aliases_value = item.get("aliases", {})
    aliases = _mapping(aliases_value, "legacy.aliases")
    if any(
        not isinstance(key, str) or not isinstance(val, str)
        for key, val in aliases.items()
    ):
        raise ConfigError("legacy.aliases must map strings to strings")
    return {"enabled": enabled, "aliases": aliases}


def load_overrides(config: Config) -> OverrideSet:
    """Load and strictly parse explicit policy exceptions."""

    if config.overrides_path is None:
        return OverrideSet()
    raw = _load_yaml(config.overrides_path)
    item = _mapping(raw, "overrides")
    _allowed(
        item,
        {"schema_version", "force_direct", "force_reject", "force_proxy"},
        "overrides",
    )
    if item.get("schema_version") != 1:
        raise ConfigError("overrides.schema_version must be 1")

    parsed: dict[str, tuple] = {}
    for action in ("direct", "reject", "proxy"):
        values = item.get(f"force_{action}")
        if not isinstance(values, list):
            raise ConfigError(f"overrides.force_{action} must be a list")
        rules = []
        for value in values:
            if not isinstance(value, str):
                raise ConfigError(f"overrides.force_{action} must contain strings")
            try:
                rules.extend(parse_rule(value, "classical"))
            except RuleError as exc:
                raise ConfigError(f"overrides.force_{action}: {exc}") from exc
        parsed[action] = tuple(dedupe(rules))

    seen: dict[tuple[str, str], str] = {}
    for action, rules in parsed.items():
        for rule in rules:
            previous = seen.get(rule.key())
            if previous is not None and previous != action:
                raise ConfigError(
                    f"override rule {rule.kind}:{rule.value} is assigned to both {previous} and {action}"
                )
            seen[rule.key()] = action
    return OverrideSet(parsed["direct"], parsed["reject"], parsed["proxy"])
