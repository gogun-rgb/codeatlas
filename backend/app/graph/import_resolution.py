from __future__ import annotations

from pathlib import PurePosixPath

from app.models.symbols import ImportRef

TS_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx")
JS_EXTENSIONS = (".js", ".jsx", ".ts", ".tsx")
PY_EXTENSIONS = (".py",)


def resolve_import(importer_path: str, import_ref: ImportRef, all_paths: set[str]) -> str | None:
    if not import_ref.is_relative:
        return None
    if importer_path.endswith(".py"):
        return resolve_python_import(
            importer_path,
            import_ref.module,
            all_paths,
            imported_name=import_ref.imported_name,
        )
    return resolve_javascript_import(importer_path, import_ref.module, all_paths)


def resolve_javascript_import(importer_path: str, module: str, all_paths: set[str]) -> str | None:
    base = PurePosixPath(importer_path).parent.joinpath(module)
    extension_order = _javascript_extension_order(importer_path)
    candidates: list[str] = []
    suffix = PurePosixPath(module).suffix
    if suffix:
        candidates.append(_normalize(base))
        if _is_typescript_importer(importer_path):
            candidates.extend(_typescript_source_equivalents(base, suffix))
    else:
        candidates.extend(_normalize(base.with_suffix(ext)) for ext in extension_order)
        candidates.extend(_normalize(base / f"index{ext}") for ext in extension_order)
    return _first_existing(candidates, all_paths)


def resolve_python_import(
    importer_path: str,
    module: str,
    all_paths: set[str],
    imported_name: str | None = None,
) -> str | None:
    leading_dots = len(module) - len(module.lstrip("."))
    if leading_dots == 0:
        return None

    remainder = module[leading_dots:].replace(".", "/")
    base = PurePosixPath(importer_path).parent
    for _ in range(max(leading_dots - 1, 0)):
        base = base.parent
    target = base / remainder if remainder else base
    candidates: list[str] = []
    if imported_name is not None:
        imported_target = target / imported_name
        candidates.extend(_python_module_candidates(imported_target))
    candidates.extend(_python_module_candidates(target))
    return _first_existing(candidates, all_paths)


def _javascript_extension_order(importer_path: str) -> tuple[str, ...]:
    return TS_EXTENSIONS if _is_typescript_importer(importer_path) else JS_EXTENSIONS


def _is_typescript_importer(importer_path: str) -> bool:
    return PurePosixPath(importer_path).suffix in {".ts", ".tsx"}


def _typescript_source_equivalents(base: PurePosixPath, suffix: str) -> list[str]:
    if suffix == ".js":
        return [_normalize(base.with_suffix(".ts")), _normalize(base.with_suffix(".tsx"))]
    if suffix == ".jsx":
        return [_normalize(base.with_suffix(".tsx")), _normalize(base.with_suffix(".ts"))]
    return []


def _python_module_candidates(target: PurePosixPath) -> list[str]:
    return [_normalize(target.with_suffix(".py")), _normalize(target / "__init__.py")]


def _normalize(path: PurePosixPath) -> str:
    parts: list[str] = []
    for part in path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def _first_existing(candidates: list[str], all_paths: set[str]) -> str | None:
    for candidate in candidates:
        if candidate in all_paths:
            return candidate
    return None
