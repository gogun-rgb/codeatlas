from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from app.models.repository import RepositoryTreeEntry, SourceFile
from app.parsing.language import detect_language

EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    ".next",
    "dist",
    "build",
    "coverage",
    "vendor",
    "generated",
}


@dataclass(frozen=True)
class FileCollectionLimits:
    max_files: int = 350
    max_file_bytes: int = 250_000
    max_total_bytes: int = 2_000_000


def is_excluded_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return any(part in EXCLUDED_DIRS for part in parts)


def is_supported_source_path(path: str) -> bool:
    return not is_excluded_path(path) and detect_language(path) is not None


def looks_binary(data: bytes) -> bool:
    if b"\x00" in data[:4096]:
        return True
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def eligible_tree_entries(
    entries: list[RepositoryTreeEntry],
    limits: FileCollectionLimits,
) -> tuple[list[RepositoryTreeEntry], list[str]]:
    warnings: list[str] = []
    candidates = sorted(
        (
            entry
            for entry in entries
            if entry.type == "blob" and is_supported_source_path(entry.path)
        ),
        key=lambda entry: entry.path,
    )
    if len(candidates) > limits.max_files:
        warnings.append(
            f"Supported file count was limited to {limits.max_files} of {len(candidates)} files."
        )
        candidates = candidates[: limits.max_files]
    return candidates, warnings


def source_file_from_bytes(path: str, data: bytes) -> SourceFile | None:
    if looks_binary(data):
        return None
    language = detect_language(path)
    if language is None:
        return None
    text = data.decode("utf-8")
    return SourceFile(path=path, content=text, size=len(data), language=language)
