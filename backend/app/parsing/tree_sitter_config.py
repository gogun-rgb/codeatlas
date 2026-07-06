from __future__ import annotations

import os
from pathlib import Path

from tree_sitter_language_pack import PackConfig, configure

_CONFIGURED = False


def ensure_language_pack_configured() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    cache_dir = Path(os.getenv("CODEATLAS_TREE_SITTER_CACHE", ".tree-sitter-cache")).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    configure(PackConfig(cache_dir=str(cache_dir)))
    _CONFIGURED = True
