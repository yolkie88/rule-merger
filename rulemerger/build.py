"""The single public build seam: load, validate, render, and publish on success."""

from __future__ import annotations

import json
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Mapping

from .config import ConfigError, load_config, load_overrides
from .models import BuildReport, BuildRequest, Config, OverrideSet, Rule
from .quality import (
    Conflict,
    compare_count,
    critical_rule_errors,
    critical_rules_for,
    duplicate_category_conflicts,
    find_segment_conflicts,
    max_growth_ratio_for,
)
from .rules import RuleError, dedupe, family_of
from .sources import SourceAdapter, SourceError, SourceResult
from .tools import ExternalTools, ToolError
from .writers import LossyFormatError, render_rules


class BuildError(RuntimeError):
    """Raised when a build cannot produce a publishable version."""


def build(request: BuildRequest) -> BuildReport:
    """Build a complete version and replace the published directory only on success."""

    report = BuildReport()
    staging: Path | None = None
    try:
        config = load_config(request.config_path)
        if not _check_redistributable_sources(config, report):
            raise BuildError("source redistribution gate failed")
        tools = request.tool_adapter or ExternalTools(
            request.mihomo_path, request.sing_box_path
        )
        source_adapter = request.source_adapter or SourceAdapter(config.root, tools)
        source_results = _load_sources(config, source_adapter, report)
        category_rules = _load_categories(config, source_results, report)
        overrides = load_overrides(config)
        _record_category_overlaps(config, category_rules, report)
        profile_rules = _build_profiles(config, category_rules, overrides, report)

        if report.errors:
            raise BuildError("quality gates failed before writing outputs")

        staging = _make_staging_dir(request.output_dir)
        logical_rules: dict[str, tuple[Rule, ...]] = {}
        _render_categories(
            config, category_rules, staging, tools, report, logical_rules
        )
        _render_profiles(
            config, profile_rules, overrides, staging, tools, report, logical_rules
        )
        _render_legacy(config, request, staging, report)
        _apply_minimums(config, logical_rules, report)
        _apply_baseline(config, request, logical_rules, report)
        if report.errors:
            raise BuildError("quality gates failed after rendering")

        report.publishable = True
        report.status = "degraded" if report.warnings else "ok"
        report.manifest = _manifest(report)
        (staging / "manifest.json").write_text(
            json.dumps(report.manifest, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        _publish(staging, request.output_dir)
        staging = None
    except (
        ConfigError,
        SourceError,
        BuildError,
        ToolError,
        LossyFormatError,
        OSError,
        RuleError,
    ) as exc:
        report.errors.append(str(exc))
        report.publishable = False
        report.status = "failed"
    except Exception as exc:  # keep an unexpected adapter failure visible in the report
        report.errors.append(f"unexpected build failure: {type(exc).__name__}: {exc}")
        report.publishable = False
        report.status = "failed"
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
        _write_report(request.report_path, report)
    return report


def _check_redistributable_sources(config: Config, report: BuildReport) -> bool:
    blocked = False
    for source_id, spec in config.sources.items():
        if spec.redistributable:
            continue
        blocked = True
        report.sources[source_id] = {
            "status": "blocked",
            "required": spec.required,
            "redistributable": False,
            "type": spec.type,
            "format": spec.format,
            "behavior": spec.behavior,
            "url": spec.url,
            "path": spec.path,
            "error": "redistributable: true is required after license review",
        }
        report.errors.append(
            f"{source_id}: source is not approved for redistribution; "
            "set redistributable: true only after license review"
        )
    return not blocked


def _load_sources(
    config: Config, adapter: object, report: BuildReport
) -> dict[str, SourceResult]:
    results: dict[str, SourceResult] = {}
    for source_id, spec in config.sources.items():
        try:
            result = adapter.load(spec)  # type: ignore[attr-defined]
            if not isinstance(result, SourceResult):
                raise SourceError(
                    f"{source_id}: adapter returned an invalid SourceResult"
                )
            results[source_id] = result
            report.sources[source_id] = {
                **result.metadata(),
                "required": spec.required,
                "redistributable": spec.redistributable,
                "type": spec.type,
                "format": spec.format,
                "behavior": spec.behavior,
                "url": spec.url,
                "path": spec.path,
            }
        except SourceError as exc:
            message = f"{source_id}: {exc}"
            report.sources[source_id] = {
                "status": "failed",
                "required": spec.required,
                "redistributable": spec.redistributable,
                "type": spec.type,
                "format": spec.format,
                "behavior": spec.behavior,
                "url": spec.url,
                "path": spec.path,
                "error": str(exc),
            }
            (report.errors if spec.required else report.warnings).append(message)
    return results


def _load_categories(
    config: Config,
    source_results: Mapping[str, SourceResult],
    report: BuildReport,
) -> dict[str, tuple[Rule, ...]]:
    category_rules: dict[str, tuple[Rule, ...]] = {}
    for category_id, category in config.categories.items():
        rules: list[Rule] = []
        source_counts: dict[str, int] = {}
        for source_id in category.sources:
            result = source_results.get(source_id)
            if result is None:
                continue
            selected = tuple(
                rule for rule in result.rules if family_of(rule) == category.family
            )
            wrong_family = len(result.rules) - len(selected)
            if wrong_family:
                report.warnings.append(
                    f"{category_id}: omitted {wrong_family} {source_id} rules outside "
                    f"the {category.family} family"
                )
            rules.extend(selected)
            source_counts[source_id] = len(selected)
        unique = tuple(dedupe(rules))
        if not unique:
            report.errors.append(f"{category_id} is empty")
        category_rules[category_id] = unique
        report.categories[category_id] = {
            "family": category.family,
            "sources": source_counts,
            "rules": len(unique),
            "duplicates": len(rules) - len(unique),
        }
    return category_rules


def _record_category_overlaps(
    config: Config,
    category_rules: Mapping[str, tuple[Rule, ...]],
    report: BuildReport,
) -> None:
    overlaps: dict[str, object] = {}
    category_names = list(config.categories)
    for left_index, left_id in enumerate(category_names[:-1]):
        for right_id in category_names[left_index + 1 :]:
            if config.categories[left_id].family != config.categories[right_id].family:
                continue
            conflicts = find_segment_conflicts(
                {left_id: category_rules[left_id], right_id: category_rules[right_id]}
            )
            if conflicts:
                overlaps[f"{left_id}:{right_id}"] = {
                    "total": len(conflicts),
                    "items": [item.as_dict() for item in conflicts[:100]],
                }
    report.conflicts["categories"] = overlaps


def _build_profiles(
    config: Config,
    category_rules: Mapping[str, tuple[Rule, ...]],
    overrides: OverrideSet,
    report: BuildReport,
) -> dict[str, dict[str, tuple[Rule, ...]]]:
    profile_rules: dict[str, dict[str, tuple[Rule, ...]]] = {}
    override_keys = {
        rule.key() for rules in overrides.by_action().values() for rule in rules
    }

    for profile_id, profile in config.profiles.items():
        segments: dict[str, dict[str, tuple[Rule, ...]]] = {}
        for action, category_ids in profile.actions.items():
            filtered_segments = {
                category_id: tuple(
                    rule
                    for rule in category_rules[category_id]
                    if rule.key() not in override_keys
                )
                for category_id in category_ids
            }
            segments[action] = filtered_segments

        normal: dict[str, tuple[Rule, ...]] = {}
        profile_conflicts: dict[str, object] = {}
        for action, category_segments in segments.items():
            exact_conflicts = duplicate_category_conflicts(category_segments)
            containment_conflicts = find_segment_conflicts(
                category_segments, overrides_for_family(overrides, action)
            )
            conflicts = exact_conflicts + [
                item for item in containment_conflicts if item.relation != "exact"
            ]
            # Categories routed to the same action are intentionally composable.
            # Their exact and parent/child overlaps are recorded and then deduped
            # below; only cross-action conflicts are policy violations.
            profile_conflicts[action] = {
                "total": len(conflicts),
                "items": [item.as_dict() for item in conflicts[:100]],
            }
            normal[action] = tuple(
                dedupe(rule for rules in category_segments.values() for rule in rules)
            )

        for family in ("domain", "ipcidr"):
            family_actions = {
                _base_action(action): tuple(
                    rule for rule in rules if family_of(rule) == family
                )
                for action, rules in normal.items()
                if action.endswith("-domain" if family == "domain" else "-ip")
            }
            resolved, resolved_exact = _resolve_exact_action_conflicts(family_actions)
            cross_conflicts = find_segment_conflicts(
                resolved,
                [
                    rule
                    for rules in overrides.by_action().values()
                    for rule in rules
                    if family_of(rule) == family
                ],
            )
            # Profile artifacts are deliberately separate and the documented
            # matcher order (reject -> direct -> proxy) resolves containment.
            # Keep these overlaps visible in the report, but only exact rules
            # require rewriting according to the action precedence above.
            unauthorized = [item for item in cross_conflicts if not item.authorized]
            profile_conflicts[family] = {
                "resolved_exact": [item.as_dict() for item in resolved_exact],
                "ordered_containment": [item.as_dict() for item in unauthorized],
                "total": len(cross_conflicts),
            }
            for action, rules in resolved.items():
                normal[f"{action}-{family if family == 'domain' else 'ip'}"] = tuple(
                    rules
                )

        report.conflicts[profile_id] = profile_conflicts
        profile_rules[profile_id] = normal
    return profile_rules


def _base_action(action: str) -> str:
    return action.rsplit("-", 1)[0]


def _resolve_exact_action_conflicts(
    actions: Mapping[str, tuple[Rule, ...]],
) -> tuple[dict[str, tuple[Rule, ...]], list[Conflict]]:
    precedence = {"reject": 0, "direct": 1, "proxy": 2}
    owners: dict[tuple[str, str], list[str]] = {}
    for action, rules in actions.items():
        for rule in rules:
            owners.setdefault(rule.key(), []).append(action)
    dropped: dict[str, set[tuple[str, str]]] = {action: set() for action in actions}
    resolved: list[Conflict] = []
    for key, owner_names in owners.items():
        if len(owner_names) < 2:
            continue
        ordered = sorted(owner_names, key=lambda name: precedence[name])
        winner = ordered[0]
        winner_rule = next(rule for rule in actions[winner] if rule.key() == key)
        for loser in ordered[1:]:
            loser_rule = next(rule for rule in actions[loser] if rule.key() == key)
            dropped[loser].add(key)
            resolved.append(
                Conflict(
                    winner,
                    loser,
                    "exact",
                    f"{winner_rule.kind}:{winner_rule.value}",
                    f"{loser_rule.kind}:{loser_rule.value}",
                    authorized=True,
                )
            )
    return {
        action: tuple(rule for rule in rules if rule.key() not in dropped[action])
        for action, rules in actions.items()
    }, resolved


def overrides_for_family(overrides: OverrideSet, action: str) -> tuple[Rule, ...]:
    base = _base_action(action)
    return tuple(
        rule
        for rule in overrides.by_action().get(base, ())
        if family_of(rule) == ("ipcidr" if action.endswith("-ip") else "domain")
    )


def _render_categories(
    config: Config,
    category_rules: Mapping[str, tuple[Rule, ...]],
    staging: Path,
    tools: object,
    report: BuildReport,
    logical_rules: dict[str, tuple[Rule, ...]],
) -> None:
    for category_id, category in config.categories.items():
        for output_format in category.formats:
            relative = f"categories/{category_id}.{output_format}"
            logical_rules[relative] = category_rules[category_id]
            _render_one(
                relative,
                category_rules[category_id],
                category.family,
                output_format,
                staging,
                tools,
                report,
            )


def _render_profiles(
    config: Config,
    profile_rules: Mapping[str, Mapping[str, tuple[Rule, ...]]],
    overrides: OverrideSet,
    staging: Path,
    tools: object,
    report: BuildReport,
    logical_rules: dict[str, tuple[Rule, ...]],
) -> None:
    for profile_id, profile in config.profiles.items():
        rules = profile_rules[profile_id]
        for action, action_rules in rules.items():
            if action not in profile.actions:
                continue
            family = "ipcidr" if action.endswith("-ip") else "domain"
            for output_format in profile.formats:
                relative = f"profiles/{profile_id}/{action}.{output_format}"
                logical_rules[relative] = action_rules
                _render_one(
                    relative,
                    action_rules,
                    family,
                    output_format,
                    staging,
                    tools,
                    report,
                )
        for base_action, override_rules in overrides.by_action().items():
            for family, suffix in (("domain", "domain"), ("ipcidr", "ip")):
                family_rules = tuple(
                    rule for rule in override_rules if family_of(rule) == family
                )
                if not family_rules:
                    continue
                for output_format in profile.formats:
                    relative = f"profiles/{profile_id}/override-{base_action}-{suffix}.{output_format}"
                    logical_rules[relative] = family_rules
                    _render_one(
                        relative,
                        family_rules,
                        family,
                        output_format,
                        staging,
                        tools,
                        report,
                    )


def _render_one(
    relative: str,
    rules: tuple[Rule, ...],
    family: str,
    output_format: str,
    staging: Path,
    tools: object,
    report: BuildReport,
) -> None:
    try:
        result = render_rules(rules, family, output_format, tools)  # type: ignore[arg-type]
        if result.content is not None:
            _record_tool_versions(output_format, tools, report)
        metadata = result.metadata()
        metadata.update({"format": output_format, "family": family})
        report.outputs[relative] = metadata
        if result.omitted_kinds:
            report.warnings.append(
                f"{relative}: omitted target-incompatible rule kinds: "
                + ", ".join(result.omitted_kinds)
            )
        if result.content is None:
            return
        path = staging / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(result.content)
    except (ToolError, LossyFormatError, RuleError, ValueError, OSError) as exc:
        report.errors.append(f"{relative}: {exc}")


def _record_tool_versions(
    output_format: str, tools: object, report: BuildReport
) -> None:
    if output_format not in {"mrs", "srs"} or report.tools:
        return
    versions = getattr(tools, "versions", None)
    if versions is None:
        return
    report.tools.update(versions())


def _render_legacy(
    config: Config, request: BuildRequest, staging: Path, report: BuildReport
) -> None:
    if not request.include_legacy:
        return
    if not config.legacy.get("enabled", False):
        report.warnings.append("legacy output requested but legacy.enabled is false")
        return
    aliases = config.legacy.get("aliases", {})
    for legacy_name, source_base in aliases.items():
        for extension in ("yaml", "json", "srs", "mrs"):
            source = staging / f"{source_base}.{extension}"
            if not source.exists():
                continue
            target = staging / f"{legacy_name}.{extension}"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            report.outputs[str(target.relative_to(staging))] = {
                "alias_of": str(source.relative_to(staging)),
                "rules": report.outputs[str(source.relative_to(staging))]["rules"],
                "bytes": target.stat().st_size,
                "sha256": _sha256(target.read_bytes()),
            }


def _apply_minimums(
    config: Config, logical_rules: Mapping[str, tuple[Rule, ...]], report: BuildReport
) -> None:
    minimums = config.quality.get("min_rules", {})
    if isinstance(minimums, dict):
        for output_name, minimum in minimums.items():
            if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0:
                report.errors.append(
                    f"quality.min_rules.{output_name} must be a non-negative integer"
                )
                continue
            actual = len(logical_rules.get(output_name, ()))
            if actual < minimum:
                report.errors.append(
                    f"{output_name} has {actual} rules, below minimum {minimum}"
                )
    report.errors.extend(
        critical_rule_errors(logical_rules, config.quality.get("critical_rules", {}))
    )
    critical_rules = config.quality.get("critical_rules", {})
    small_output_limit = int(config.quality["small_output_limit"])
    for output_name, rules in logical_rules.items():
        if not rules:
            report.errors.append(f"{output_name} is empty")
            continue
        metadata = report.outputs.get(output_name, {})
        if (
            len(rules) < small_output_limit
            and not (
                isinstance(metadata, dict)
                and metadata.get("skipped") in {"lossy_format", "no_compatible_rules"}
            )
            and not critical_rules_for(output_name, critical_rules)
        ):
            report.errors.append(
                f"{output_name} is below {small_output_limit} rules and requires a non-empty critical rule list"
            )


def _apply_baseline(
    config: Config,
    request: BuildRequest,
    logical_rules: Mapping[str, tuple[Rule, ...]],
    report: BuildReport,
) -> None:
    if request.baseline_manifest is None:
        return
    if not request.baseline_manifest.exists():
        report.baseline = {
            "path": str(request.baseline_manifest),
            "checked": False,
            "reason": "not_found",
        }
        return
    try:
        baseline = json.loads(request.baseline_manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report.errors.append(f"invalid baseline manifest: {exc}")
        return
    if not isinstance(baseline, dict) or not isinstance(baseline.get("outputs"), dict):
        message = "invalid baseline manifest: outputs must be a mapping"
        report.errors.append(message)
        report.baseline = {
            "path": str(request.baseline_manifest),
            "checked": False,
            "reason": "invalid",
            "errors": [message],
        }
        return
    previous = baseline["outputs"]
    errors: list[str] = []
    changes: dict[str, dict[str, object]] = {}
    default_max_growth_ratio = float(config.quality["max_growth_ratio"])
    max_growth_ratio_overrides = config.quality.get(
        "max_growth_ratio_overrides", {}
    )
    for name, rules in logical_rules.items():
        old = previous.get(name)
        old_count = old.get("rules") if isinstance(old, dict) else None
        current_count = len(rules)
        change: dict[str, object] = {"current": current_count}
        if isinstance(old_count, int) and not isinstance(old_count, bool):
            delta = current_count - old_count
            change.update(
                {
                    "baseline": old_count,
                    "delta": delta,
                    "ratio": delta / old_count if old_count else None,
                }
            )
        changes[name] = change
        error = compare_count(
            name,
            current_count,
            old_count
            if isinstance(old_count, int) and not isinstance(old_count, bool)
            else None,
            float(config.quality["max_drop_ratio"]),
            max_growth_ratio_for(
                name,
                max_growth_ratio_overrides,
                default_max_growth_ratio,
            ),
            int(config.quality["small_output_limit"]),
        )
        if error:
            errors.append(error)
    allowed_removed = set(config.quality.get("allowed_removed_outputs", ()))
    removable_extensions = {"yaml", "json", "srs", "mrs"}

    def removal_is_allowed(name: str) -> bool:
        base, dot, extension = name.rpartition(".")
        return name in allowed_removed or (
            bool(dot)
            and extension in removable_extensions
            and base in allowed_removed
        )

    removed = sorted(
        name
        for name, metadata in previous.items()
        if name not in logical_rules
        and not (isinstance(metadata, dict) and metadata.get("alias_of"))
        and not removal_is_allowed(name)
    )
    for name, metadata in previous.items():
        if name in logical_rules or not isinstance(metadata, dict):
            continue
        old_count = metadata.get("rules")
        if not isinstance(old_count, int) or isinstance(old_count, bool):
            continue
        changes[name] = {
            "baseline": old_count,
            "current": 0,
            "delta": -old_count,
            "ratio": -1.0,
            "status": (
                "legacy-alias-removed"
                if metadata.get("alias_of")
                else "allowed-removed"
                if removal_is_allowed(name)
                else "removed"
            ),
        }
    errors.extend(
        f"{name} was removed from the current build; baseline output is missing"
        for name in removed
    )
    report.baseline = {
        "path": str(request.baseline_manifest),
        "checked": True,
        "changes": changes,
        "errors": errors,
    }
    report.errors.extend(errors)


def _manifest(report: BuildReport) -> dict[str, object]:
    return {
        "schema_version": 2,
        "status": report.status,
        "publishable": report.publishable,
        "tools": report.tools,
        "sources": report.sources,
        "categories": report.categories,
        "outputs": report.outputs,
        "baseline": report.baseline,
        "conflicts": report.conflicts,
    }


def _make_staging_dir(output_dir: Path) -> Path:
    output_dir = output_dir.resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    return Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent)
    )


def _publish(staging: Path, output_dir: Path) -> None:
    output_dir = output_dir.resolve()
    previous: Path | None = None
    if output_dir.exists():
        previous = output_dir.parent / f".{output_dir.name}.previous-{uuid.uuid4().hex}"
        output_dir.replace(previous)
    try:
        staging.replace(output_dir)
    except Exception:
        if previous is not None and previous.exists() and not output_dir.exists():
            previous.replace(output_dir)
        raise
    if previous is not None:
        shutil.rmtree(previous, ignore_errors=True)


def _write_report(path: Path | None, report: BuildReport) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.as_dict(), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _sha256(content: bytes) -> str:
    import hashlib

    return hashlib.sha256(content).hexdigest()
