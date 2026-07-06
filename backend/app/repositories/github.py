from __future__ import annotations

import asyncio
import base64
import os
import re
from typing import Any
from urllib.parse import quote

import httpx

from app.models.repository import RepositoryRef, RepositorySnapshot, RepositoryTreeEntry, SourceFile
from app.repositories.errors import (
    GitHubNetworkError,
    GitHubRateLimitError,
    InvalidRepositoryUrlError,
    PrivateRepositoryError,
    RepositoryNotFoundError,
    SourceLimitExceededError,
    UnsupportedRepositoryError,
)
from app.repositories.filtering import (
    FileCollectionLimits,
    eligible_tree_entries,
    source_file_from_bytes,
)

GITHUB_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
DEFAULT_BLOB_CONCURRENCY = 8


def normalize_github_repo(value: str) -> RepositoryRef:
    raw = value.strip()
    if raw.endswith(".git"):
        raw = raw[:-4]
    if raw.startswith("https://github.com/"):
        raw = raw.removeprefix("https://github.com/").strip("/")
        raw = "/".join(raw.split("/")[:2])
    elif raw.startswith("http://github.com/"):
        raw = raw.removeprefix("http://github.com/").strip("/")
        raw = "/".join(raw.split("/")[:2])

    if not GITHUB_RE.match(raw):
        raise InvalidRepositoryUrlError()
    owner, name = raw.split("/", 1)
    return RepositoryRef(owner=owner, name=name)


class GitHubRepositoryLoader:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        limits: FileCollectionLimits | None = None,
        token: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        blob_concurrency: int = DEFAULT_BLOB_CONCURRENCY,
    ) -> None:
        self._client = client
        self._limits = limits or FileCollectionLimits()
        self._token = token if token is not None else os.getenv("GITHUB_TOKEN")
        self._transport = transport
        self._blob_concurrency = max(1, blob_concurrency)

    async def load(self, repository: str) -> RepositorySnapshot:
        ref = normalize_github_repo(repository)
        async with self._client or self._new_client() as client:
            repo_payload = await self._request_json(client, f"/repos/{ref.owner}/{ref.name}")
            if repo_payload.get("private") is True:
                raise PrivateRepositoryError()
            default_branch = str(repo_payload.get("default_branch") or "main")
            tree_payload = await self._request_json(
                client,
                f"/repos/{ref.owner}/{ref.name}/git/trees/{quote(default_branch, safe='')}",
                params={"recursive": "1"},
            )
            entries = [
                RepositoryTreeEntry.model_validate(item)
                for item in tree_payload.get("tree", [])
                if isinstance(item, dict)
            ]
            selected, warnings = eligible_tree_entries(entries, self._limits)
            if tree_payload.get("truncated"):
                warnings.append(
                    "GitHub returned a truncated repository tree; analysis may be incomplete."
                )

            files = await self._load_files(client, ref, selected)
            if not files:
                raise UnsupportedRepositoryError()

            return RepositorySnapshot(
                ref=ref,
                default_branch=default_branch,
                files=files,
                warnings=warnings,
                tree_truncated=bool(tree_payload.get("truncated")),
            )

    def _new_client(self) -> httpx.AsyncClient:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "CodeAtlas",
        }
        if self._token:
            headers["Authorization"] = "Bearer " + self._token
        return httpx.AsyncClient(
            base_url="https://api.github.com",
            headers=headers,
            timeout=20.0,
            transport=self._transport,
        )

    async def _request_json(
        self,
        client: httpx.AsyncClient,
        path: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise GitHubNetworkError() from exc

        if response.status_code == 404:
            raise RepositoryNotFoundError()
        if response.status_code == 403 and response.headers.get("x-ratelimit-remaining") == "0":
            raise GitHubRateLimitError()
        if response.status_code == 403:
            raise PrivateRepositoryError()
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise GitHubNetworkError()
        return payload

    async def _load_files(
        self,
        client: httpx.AsyncClient,
        ref: RepositoryRef,
        entries: list[RepositoryTreeEntry],
    ) -> list[SourceFile]:
        semaphore = asyncio.Semaphore(self._blob_concurrency)
        fetchable_entries = [
            entry
            for entry in entries
            if entry.size is None or entry.size <= self._limits.max_file_bytes
        ]
        fetched = await asyncio.gather(
            *[
                self._fetch_blob_payload(client, ref, entry, semaphore)
                for entry in fetchable_entries
            ]
        )

        files: list[SourceFile] = []
        total = 0
        for entry, payload in fetched:
            content = payload.get("content")
            encoding = payload.get("encoding")
            if not isinstance(content, str) or encoding != "base64":
                continue
            data = base64.b64decode(content, validate=False)
            if len(data) > self._limits.max_file_bytes:
                continue
            total += len(data)
            if total > self._limits.max_total_bytes:
                raise SourceLimitExceededError()
            source_file = source_file_from_bytes(entry.path, data)
            if source_file is not None:
                files.append(source_file)
        return files

    async def _fetch_blob_payload(
        self,
        client: httpx.AsyncClient,
        ref: RepositoryRef,
        entry: RepositoryTreeEntry,
        semaphore: asyncio.Semaphore,
    ) -> tuple[RepositoryTreeEntry, dict[str, Any]]:
        async with semaphore:
            payload = await self._request_json(
                client,
                f"/repos/{ref.owner}/{ref.name}/git/blobs/{entry.sha}",
            )
        return entry, payload
