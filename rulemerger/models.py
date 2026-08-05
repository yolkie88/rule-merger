"""Small serialisable types shared by the build pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class Rule:
    """A canonical rule independent of an input or output format."""

    kind: str
    value: str

    def key(self) -> tuple[str, str]:
        return self.kind, self.value


@dataclass(frozen=True)
class SourceSpec:
    id: str
    type: str
    format: str
    behavior: str
    url: str | None = None
    path: str | None = None
    required: bool = True


@dataclass(frozen=True)
class CategorySpec:
    id: str
    family: str
    sources: tuple[str, ...]
    formats: tuple[str, ...]


@dataclass(frozen=True)
class ProfileSpec:
    id: str
    actions: Mapping[str, tuple[str, ...]]
    formats: tuple[str, ...]


@dataclass(frozen=True)
class OverrideSet:
    direct: tuple[Rule, ...] = ()
    reject: tuple[Rule, ...] = ()
    proxy: tuple[Rule, ...] = ()

    def by_action(self) -> Mapping[str, tuple[Rule, ...]]:
        return {
            "direct": self.direct,
            "reject": self.reject,
            "proxy": self.proxy,
        }


@dataclass(frozen=True)
class Config:
    root: Path
    sources: Mapping[str, SourceSpec]
    categories: Mapping[str, CategorySpec]
    profiles: Mapping[str, ProfileSpec]
    overrides_path: Path | None
    quality: Mapping[str, Any]
    legacy: Mapping[str, Any]


@dataclass(frozen=True)
class BuildRequest:
    config_path: Path
    output_dir: Path
    baseline_manifest: Path | None = None
    report_path: Path | None = None
    mihomo_path: str = "mihomo"
    sing_box_path: str = "sing-box"
    include_legacy: bool = False
    source_adapter: Any | None = None
    tool_adapter: Any | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "config_path", Path(self.config_path))
        object.__setattr__(self, "output_dir", Path(self.output_dir))
        if self.baseline_manifest is not None:
            object.__setattr__(self, "baseline_manifest", Path(self.baseline_manifest))
        if self.report_path is not None:
            object.__setattr__(self, "report_path", Path(self.report_path))


@dataclass
class BuildReport:
    status: str = "failed"
    publishable: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sources: dict[str, Any] = field(default_factory=dict)
    categories: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    conflicts: dict[str, Any] = field(default_factory=dict)
    baseline: dict[str, Any] = field(default_factory=dict)
    tools: dict[str, str] = field(default_factory=dict)
    manifest: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "publishable": self.publishable,
            "errors": self.errors,
            "warnings": self.warnings,
            "sources": self.sources,
            "categories": self.categories,
            "outputs": self.outputs,
            "conflicts": self.conflicts,
            "baseline": self.baseline,
            "tools": self.tools,
            "manifest": self.manifest,
        }
