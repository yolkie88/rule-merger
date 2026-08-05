"""HTTP and local source adapters with explicit failure metadata."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import requests

from .models import Rule, SourceSpec
from .rules import RuleError, parse_payload
from .tools import ExternalTools, ToolError


class SourceError(RuntimeError):
    """Raised when a source cannot be fetched or parsed completely."""


@dataclass(frozen=True)
class SourceResult:
    source_id: str
    rules: tuple[Rule, ...]
    sha256: str
    bytes: int
    attempts: int
    etag: str | None = None
    last_modified: str | None = None

    def metadata(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "sha256": self.sha256,
            "bytes": self.bytes,
            "attempts": self.attempts,
            "etag": self.etag,
            "last_modified": self.last_modified,
            "rules": len(self.rules),
        }


class SourceAdapter:
    """Default source adapter; the build accepts an object with the same load seam for tests."""

    def __init__(
        self,
        root: Path,
        tools: ExternalTools,
        *,
        request_get: Callable[..., Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.root = root.resolve()
        self.tools = tools
        self.request_get = request_get or requests.get
        self.sleep = sleep

    def load(self, spec: SourceSpec) -> SourceResult:
        if spec.type == "file":
            data, attempts, etag, last_modified = self._read_file(spec)
        elif spec.type == "http":
            data, attempts, etag, last_modified = self._read_http(spec)
        else:
            raise SourceError(f"{spec.id}: unsupported source type {spec.type}")
        if not data:
            raise SourceError(f"{spec.id}: source payload is empty")
        try:
            rules = self._parse(spec, data)
        except (RuleError, ToolError, UnicodeError) as exc:
            raise SourceError(f"{spec.id}: {exc}") from exc
        if not rules:
            raise SourceError(f"{spec.id}: source contains no valid rules")
        return SourceResult(
            source_id=spec.id,
            rules=tuple(rules),
            sha256=hashlib.sha256(data).hexdigest(),
            bytes=len(data),
            attempts=attempts,
            etag=etag,
            last_modified=last_modified,
        )

    def _read_file(self, spec: SourceSpec) -> tuple[bytes, int, None, None]:
        assert spec.path is not None
        path = (self.root / spec.path).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise SourceError(f"{spec.id}: source path escapes config root") from exc
        try:
            return path.read_bytes(), 1, None, None
        except OSError as exc:
            raise SourceError(f"{spec.id}: cannot read {path}: {exc}") from exc

    def _read_http(self, spec: SourceSpec) -> tuple[bytes, int, str | None, str | None]:
        assert spec.url is not None
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = self.request_get(spec.url, timeout=(10, 30))
                response.raise_for_status()
                return (
                    bytes(response.content),
                    attempt,
                    response.headers.get("ETag"),
                    response.headers.get("Last-Modified"),
                )
            except (
                Exception
            ) as exc:  # requests exposes several concrete transport exceptions
                last_error = exc
                if attempt < 3:
                    self.sleep(float(attempt))
        raise SourceError(
            f"{spec.id}: HTTP fetch failed after 3 attempts: {last_error}"
        ) from last_error

    def _parse(self, spec: SourceSpec, data: bytes) -> list[Rule]:
        if spec.format == "mrs":
            data = self.tools.decompile_mrs(data, spec.behavior)
            return parse_payload(data, "text", spec.behavior)
        if spec.format == "srs":
            data = self.tools.decompile_srs(data)
            return parse_payload(data, "json", "sing-box")
        return parse_payload(data, spec.format, spec.behavior)
