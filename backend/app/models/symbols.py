from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SymbolKind(StrEnum):
    FUNCTION = "FUNCTION"
    CLASS = "CLASS"


class ImportRef(BaseModel):
    module: str
    raw: str
    line: int
    is_relative: bool
    is_external: bool = False
    resolved_path: str | None = None
    imported_name: str | None = None


class SymbolInfo(BaseModel):
    name: str
    kind: SymbolKind
    path: str
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    container_name: str | None = None
    exported: bool = False


class ParsedFile(BaseModel):
    path: str
    language: str
    size: int
    imports: list[ImportRef] = Field(default_factory=list)
    exports: list[str] = Field(default_factory=list)
    symbols: list[SymbolInfo] = Field(default_factory=list)
    parser_errors: list[str] = Field(default_factory=list)
