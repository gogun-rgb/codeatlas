from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class RepositoryRef(BaseModel):
    owner: str
    name: str

    @property
    def identifier(self) -> str:
        return f"{self.owner}/{self.name}"


class RepositoryTreeEntry(BaseModel):
    path: str
    type: str
    sha: str
    size: int | None = None


class Language(StrEnum):
    TYPESCRIPT = "typescript"
    TSX = "tsx"
    JAVASCRIPT = "javascript"
    JSX = "jsx"
    PYTHON = "python"


class SourceFile(BaseModel):
    path: str
    content: str
    size: int
    language: Language


class RepositorySnapshot(BaseModel):
    ref: RepositoryRef
    default_branch: str
    files: list[SourceFile]
    warnings: list[str] = Field(default_factory=list)
    tree_truncated: bool = False
