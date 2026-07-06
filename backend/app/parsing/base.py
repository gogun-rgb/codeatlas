from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.repository import SourceFile
from app.models.symbols import ParsedFile


class SymbolExtractor(ABC):
    @abstractmethod
    def parse(self, source_file: SourceFile) -> ParsedFile:
        """Parse one source file without executing it."""
