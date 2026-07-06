from __future__ import annotations

from pathlib import PurePosixPath

from app.models.repository import Language

EXTENSION_LANGUAGE: dict[str, Language] = {
    ".ts": Language.TYPESCRIPT,
    ".tsx": Language.TSX,
    ".js": Language.JAVASCRIPT,
    ".jsx": Language.JSX,
    ".py": Language.PYTHON,
}


def detect_language(path: str) -> Language | None:
    return EXTENSION_LANGUAGE.get(PurePosixPath(path).suffix.lower())
