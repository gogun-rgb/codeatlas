from __future__ import annotations

from collections.abc import Iterator
from typing import Any


def node_value(node: Any, name: str) -> Any:
    value = getattr(node, name)
    return value() if callable(value) else value


def node_kind(node: Any) -> str:
    if hasattr(node, "type"):
        return str(node_value(node, "type"))
    return str(node_value(node, "kind"))


def node_has_error(node: Any) -> bool:
    return bool(node_value(node, "has_error"))


def node_parent(node: Any) -> Any | None:
    parent = getattr(node, "parent", None)
    if parent is None:
        return None
    return parent() if callable(parent) else parent


def node_text(source: bytes, node: Any) -> str:
    start_byte = int(node_value(node, "start_byte"))
    end_byte = int(node_value(node, "end_byte"))
    return source[start_byte:end_byte].decode("utf-8", errors="replace")


def node_byte_range(node: Any) -> tuple[int, int]:
    return int(node_value(node, "start_byte")), int(node_value(node, "end_byte"))


def node_line_range(node: Any) -> tuple[int, int]:
    if hasattr(node, "start_point"):
        start_point = node_value(node, "start_point")
        end_point = node_value(node, "end_point")
        return int(start_point[0]) + 1, int(end_point[0]) + 1
    start_position = node_value(node, "start_position")
    end_position = node_value(node, "end_position")
    return int(start_position.row) + 1, int(end_position.row) + 1


def node_children(node: Any) -> list[Any]:
    if hasattr(node, "children"):
        children = node_value(node, "children")
        if children is not None:
            return list(children)
    child_count = int(node_value(node, "child_count"))
    return [node.child(index) for index in range(child_count)]


def walk(node: Any) -> Iterator[Any]:
    yield node
    for child in node_children(node):
        yield from walk(child)


def first_named_child_text(source: bytes, node: Any) -> str | None:
    child = node.child_by_field_name("name")
    if child is None:
        return None
    return node_text(source, child)
