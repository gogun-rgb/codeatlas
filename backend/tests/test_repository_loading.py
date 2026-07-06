from __future__ import annotations

import pytest

from app.models.repository import RepositoryTreeEntry
from app.parsing.language import detect_language
from app.repositories.errors import InvalidRepositoryUrlError
from app.repositories.filtering import (
    FileCollectionLimits,
    eligible_tree_entries,
    is_excluded_path,
    looks_binary,
)
from app.repositories.github import normalize_github_repo


def test_normalize_github_url_and_owner_repo() -> None:
    assert normalize_github_repo("gogun-rgb/ai-hype-radar").identifier == "gogun-rgb/ai-hype-radar"
    assert (
        normalize_github_repo("https://github.com/gogun-rgb/ai-hype-radar.git").identifier
        == "gogun-rgb/ai-hype-radar"
    )


def test_rejects_invalid_github_url() -> None:
    with pytest.raises(InvalidRepositoryUrlError):
        normalize_github_repo("https://example.com/not/github")


def test_language_detection() -> None:
    assert detect_language("src/app.tsx") == "tsx"
    assert detect_language("src/server.py") == "python"
    assert detect_language("README.md") is None


def test_excluded_path_filtering() -> None:
    assert is_excluded_path("node_modules/pkg/index.js")
    assert is_excluded_path("src/generated/client.ts")
    assert not is_excluded_path("src/lib/scoring.ts")


def test_binary_filtering() -> None:
    assert looks_binary(b"abc\x00def")
    assert not looks_binary(b"export const ok = true;\n")


def test_eligible_entries_are_limited_and_sorted() -> None:
    entries = [
        RepositoryTreeEntry(path="src/b.ts", type="blob", sha="2", size=1),
        RepositoryTreeEntry(path="src/a.py", type="blob", sha="1", size=1),
        RepositoryTreeEntry(path="dist/generated.js", type="blob", sha="3", size=1),
    ]

    selected, warnings = eligible_tree_entries(entries, FileCollectionLimits(max_files=1))

    assert [entry.path for entry in selected] == ["src/a.py"]
    assert warnings == ["Supported file count was limited to 1 of 2 files."]
