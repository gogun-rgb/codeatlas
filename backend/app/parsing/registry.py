from __future__ import annotations

from app.models.repository import Language, SourceFile
from app.models.symbols import ParsedFile
from app.parsing.base import SymbolExtractor
from app.parsing.javascript import JavaScriptLikeExtractor
from app.parsing.python import PythonExtractor


class ParserRegistry:
    def __init__(self, extractors: dict[Language, SymbolExtractor] | None = None) -> None:
        self._extractors = extractors or {
            Language.TYPESCRIPT: JavaScriptLikeExtractor("typescript"),
            Language.TSX: JavaScriptLikeExtractor("tsx"),
            Language.JAVASCRIPT: JavaScriptLikeExtractor("javascript"),
            Language.JSX: JavaScriptLikeExtractor("tsx"),
            Language.PYTHON: PythonExtractor(),
        }

    def parse_file(self, source_file: SourceFile) -> ParsedFile:
        return self._extractors[source_file.language].parse(source_file)

    def parse_files(self, source_files: list[SourceFile]) -> list[ParsedFile]:
        return [self.parse_file(source_file) for source_file in source_files]
