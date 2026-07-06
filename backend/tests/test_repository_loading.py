from __future__ import annotations

import asyncio
import base64

import httpx
import pytest

from app.models.repository import RepositoryTreeEntry
from app.parsing.language import detect_language
from app.repositories.errors import (
    GitHubRateLimitError,
    InvalidRepositoryUrlError,
    SourceLimitExceededError,
)
from app.repositories.filtering import (
    FileCollectionLimits,
    eligible_tree_entries,
    is_excluded_path,
    looks_binary,
)
from app.repositories.github import GitHubRepositoryLoader, normalize_github_repo


def _successful_github_transport(
    seen_requests: list[httpx.Request],
) -> httpx.MockTransport:
    source = base64.b64encode(b"export function boot() { return true; }\n").decode()

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        if request.url.path == "/repos/gogun-rgb/demo":
            return httpx.Response(200, json={"private": False, "default_branch": "main"})
        if request.url.path == "/repos/gogun-rgb/demo/git/trees/main":
            return httpx.Response(
                200,
                json={
                    "tree": [
                        {
                            "path": "src/app.ts",
                            "type": "blob",
                            "sha": "abc123",
                            "size": 40,
                        }
                    ],
                    "truncated": False,
                },
            )
        if request.url.path == "/repos/gogun-rgb/demo/git/blobs/abc123":
            return httpx.Response(200, json={"content": source, "encoding": "base64"})
        return httpx.Response(404, json={"message": "not found"})

    return httpx.MockTransport(handler)


def _rate_limited_github_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"x-ratelimit-remaining": "0"},
            json={"message": "rate limit"},
        )

    return httpx.MockTransport(handler)


def _encoded_source(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


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


async def test_public_repository_loading_without_github_token_sends_no_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    seen_requests: list[httpx.Request] = []

    snapshot = await GitHubRepositoryLoader(
        transport=_successful_github_transport(seen_requests)
    ).load("gogun-rgb/demo")

    assert snapshot.ref.identifier == "gogun-rgb/demo"
    assert [source.path for source in snapshot.files] == ["src/app.ts"]
    assert seen_requests
    assert all("authorization" not in request.headers for request in seen_requests)


async def test_public_repository_loading_with_github_token_sends_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-for-headers")
    seen_requests: list[httpx.Request] = []

    snapshot = await GitHubRepositoryLoader(
        transport=_successful_github_transport(seen_requests)
    ).load("gogun-rgb/demo")

    assert [source.path for source in snapshot.files] == ["src/app.ts"]
    assert seen_requests
    assert {
        request.headers.get("authorization") for request in seen_requests
    } == {"Bearer test-token-for-headers"}


async def test_github_token_is_not_returned_in_snapshots_or_rate_limit_errors() -> None:
    token = "unit-test-auth-placeholder"
    seen_requests: list[httpx.Request] = []
    snapshot = await GitHubRepositoryLoader(
        token=token,
        transport=_successful_github_transport(seen_requests),
    ).load("gogun-rgb/demo")

    assert token not in snapshot.model_dump_json()

    loader = GitHubRepositoryLoader(
        token=token,
        transport=_rate_limited_github_transport(),
    )
    with pytest.raises(GitHubRateLimitError) as exc_info:
        await loader.load("gogun-rgb/demo")

    assert token not in str(exc_info.value)
    assert token not in exc_info.value.user_message


async def test_blob_loading_uses_bounded_concurrency_and_preserves_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "unit-test-concurrency-placeholder")
    current_requests = 0
    max_requests = 0
    overlap_seen = False
    seen_requests: list[httpx.Request] = []
    sources = {
        "sha-a": _encoded_source("export const a = 1;\n"),
        "sha-b": _encoded_source("export const b = 2;\n"),
        "sha-c": _encoded_source("export const c = 3;\n"),
        "sha-d": _encoded_source("export const d = 4;\n"),
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal current_requests, max_requests, overlap_seen
        seen_requests.append(request)
        if request.url.path == "/repos/gogun-rgb/demo":
            return httpx.Response(200, json={"private": False, "default_branch": "main"})
        if request.url.path == "/repos/gogun-rgb/demo/git/trees/main":
            return httpx.Response(
                200,
                json={
                    "tree": [
                        {"path": "src/d.ts", "type": "blob", "sha": "sha-d", "size": 20},
                        {"path": "src/b.ts", "type": "blob", "sha": "sha-b", "size": 20},
                        {"path": "src/a.ts", "type": "blob", "sha": "sha-a", "size": 20},
                        {"path": "src/c.ts", "type": "blob", "sha": "sha-c", "size": 20},
                    ],
                    "truncated": False,
                },
            )
        sha = request.url.path.rsplit("/", 1)[-1]
        current_requests += 1
        max_requests = max(max_requests, current_requests)
        overlap_seen = overlap_seen or current_requests > 1
        await asyncio.sleep({"sha-a": 0.04, "sha-b": 0.03, "sha-c": 0.02, "sha-d": 0.01}[sha])
        current_requests -= 1
        return httpx.Response(200, json={"content": sources[sha], "encoding": "base64"})

    snapshot = await GitHubRepositoryLoader(
        transport=httpx.MockTransport(handler),
        blob_concurrency=2,
    ).load("gogun-rgb/demo")

    assert [source.path for source in snapshot.files] == [
        "src/a.ts",
        "src/b.ts",
        "src/c.ts",
        "src/d.ts",
    ]
    assert overlap_seen is True
    assert max_requests == 2
    assert {request.headers.get("authorization") for request in seen_requests} == {
        "Bearer unit-test-concurrency-placeholder"
    }
    assert "unit-test-concurrency-placeholder" not in snapshot.model_dump_json()


async def test_concurrent_blob_loading_enforces_total_source_size_deterministically() -> None:
    sources = {
        "sha-a": _encoded_source("export const a = 1;\n"),
        "sha-b": _encoded_source("export const b = 2;\n"),
        "sha-c": _encoded_source("export const c = 3;\n"),
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/gogun-rgb/demo":
            return httpx.Response(200, json={"private": False, "default_branch": "main"})
        if request.url.path == "/repos/gogun-rgb/demo/git/trees/main":
            return httpx.Response(
                200,
                json={
                    "tree": [
                        {"path": "src/a.ts", "type": "blob", "sha": "sha-a", "size": 20},
                        {"path": "src/b.ts", "type": "blob", "sha": "sha-b", "size": 20},
                        {"path": "src/c.ts", "type": "blob", "sha": "sha-c", "size": 20},
                    ],
                    "truncated": False,
                },
            )
        sha = request.url.path.rsplit("/", 1)[-1]
        await asyncio.sleep({"sha-a": 0.03, "sha-b": 0.01, "sha-c": 0.02}[sha])
        return httpx.Response(200, json={"content": sources[sha], "encoding": "base64"})

    loader = GitHubRepositoryLoader(
        transport=httpx.MockTransport(handler),
        limits=FileCollectionLimits(max_total_bytes=35),
        blob_concurrency=3,
    )

    with pytest.raises(SourceLimitExceededError) as first:
        await loader.load("gogun-rgb/demo")
    with pytest.raises(SourceLimitExceededError) as second:
        await loader.load("gogun-rgb/demo")

    assert first.value.user_message == second.value.user_message
