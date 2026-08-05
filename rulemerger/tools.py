"""Narrow seams around Mihomo and sing-box command line tools."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


class ToolError(RuntimeError):
    """Raised when an external ruleset tool cannot perform an operation."""


class ExternalTools:
    def __init__(
        self, mihomo_path: str = "mihomo", sing_box_path: str = "sing-box"
    ) -> None:
        self.mihomo_path = mihomo_path
        self.sing_box_path = sing_box_path

    def versions(self) -> dict[str, str]:
        return {
            "mihomo": self._version(self.mihomo_path, ("-v",)),
            "sing-box": self._version(self.sing_box_path, ("version",)),
        }

    def _version(self, executable: str, args: tuple[str, ...]) -> str:
        try:
            result = subprocess.run(
                [executable, *args], capture_output=True, text=True, check=False
            )
        except OSError as exc:
            raise ToolError(f"tool not available: {executable}") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise ToolError(f"{executable} version check failed: {detail}")
        return (result.stdout or result.stderr).strip()

    def compile_mrs(self, source: bytes, behavior: str) -> bytes:
        return self._mihomo_convert(source, behavior, "text", "mrs")

    def decompile_mrs(self, source: bytes, behavior: str) -> bytes:
        return self._mihomo_convert(source, behavior, "mrs", "text")

    def _mihomo_convert(
        self, source: bytes, behavior: str, source_format: str, target_format: str
    ) -> bytes:
        with tempfile.TemporaryDirectory(prefix="rulemerger-mihomo-") as directory:
            root = Path(directory)
            source_path = root / f"source.{source_format}"
            target_path = root / f"target.{target_format}"
            source_path.write_bytes(source)
            self._run(
                [
                    self.mihomo_path,
                    "convert-ruleset",
                    behavior,
                    source_format,
                    str(source_path),
                    str(target_path),
                ],
                self.mihomo_path,
            )
            try:
                return target_path.read_bytes()
            except OSError as exc:
                raise ToolError(f"Mihomo did not create {target_path}") from exc

    def compile_srs(self, source: bytes) -> bytes:
        with tempfile.TemporaryDirectory(prefix="rulemerger-sing-box-") as directory:
            root = Path(directory)
            source_path = root / "source.json"
            target_path = root / "target.srs"
            source_path.write_bytes(source)
            self._run(
                [
                    self.sing_box_path,
                    "rule-set",
                    "compile",
                    "--output",
                    str(target_path),
                    str(source_path),
                ],
                self.sing_box_path,
            )
            try:
                return target_path.read_bytes()
            except OSError as exc:
                raise ToolError(f"sing-box did not create {target_path}") from exc

    def decompile_srs(self, source: bytes) -> bytes:
        with tempfile.TemporaryDirectory(prefix="rulemerger-sing-box-") as directory:
            root = Path(directory)
            source_path = root / "source.srs"
            target_path = root / "target.json"
            source_path.write_bytes(source)
            self._run(
                [
                    self.sing_box_path,
                    "rule-set",
                    "decompile",
                    "--output",
                    str(target_path),
                    str(source_path),
                ],
                self.sing_box_path,
            )
            try:
                return target_path.read_bytes()
            except OSError as exc:
                raise ToolError(f"sing-box did not create {target_path}") from exc

    @staticmethod
    def _run(command: list[str], executable: str) -> None:
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, check=False
            )
        except OSError as exc:
            raise ToolError(f"tool not available: {executable}") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise ToolError(f"{executable} command failed: {detail}")
