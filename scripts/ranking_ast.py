"""AST analysis helpers for deterministic coverage target selection."""
from __future__ import annotations

import ast
from typing import Any, Dict, Iterable, List, NamedTuple, Sequence, Set, Tuple


SYMBOL_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


class Symbol(NamedTuple):
    name: str
    kind: str
    node: ast.AST
    descendant_spans: Tuple[Tuple[int, int], ...]


def ranges_to_lines(values: Sequence[Any]) -> Set[int]:
    out = set()  # type: Set[int]
    for value in values or []:
        if isinstance(value, int):
            out.add(value)
        elif isinstance(value, (list, tuple)) and len(value) == 2:
            start, end = int(value[0]), int(value[1])
            out.update(range(start, end + 1))
    return out


def node_end(node: ast.AST) -> int:
    end = getattr(node, "end_lineno", None)
    if isinstance(end, int):
        return end
    maximum = int(getattr(node, "lineno", 1))
    for child in ast.walk(node):
        maximum = max(maximum, int(getattr(child, "lineno", maximum)))
    return maximum


def _child_symbols(node: ast.AST) -> Iterable[ast.AST]:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, SYMBOL_NODES):
            yield child
        else:
            for nested in _child_symbols(child):
                yield nested


def _descendant_spans(node: ast.AST) -> Tuple[Tuple[int, int], ...]:
    return tuple(
        (int(getattr(child, "lineno", 1)), node_end(child))
        for child in _child_symbols(node)
    )


def iter_symbols(tree: ast.AST) -> Iterable[Symbol]:
    yield Symbol("<module>", "module", tree, _descendant_spans(tree))

    def walk(body: Sequence[ast.stmt], prefix: str = "") -> Iterable[Symbol]:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = "%s%s" % (prefix, node.name)
                yield Symbol(name, "function", node, _descendant_spans(node))
                for item in walk(node.body, name + "."):
                    yield item
            elif isinstance(node, ast.ClassDef):
                name = "%s%s" % (prefix, node.name)
                yield Symbol(name, "class", node, _descendant_spans(node))
                for item in walk(node.body, name + "."):
                    yield item

    for symbol in walk(getattr(tree, "body", [])):
        yield symbol


def owned_span(start: int, end: int, descendants: Sequence[Tuple[int, int]]) -> Set[int]:
    lines = set(range(start, end + 1))
    for child_start, child_end in descendants:
        lines.difference_update(range(child_start, child_end + 1))
    return lines


def iter_owned_nodes(root: ast.AST) -> Iterable[ast.AST]:
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        for child in reversed(list(ast.iter_child_nodes(node))):
            if child is not root and isinstance(child, SYMBOL_NODES):
                continue
            stack.append(child)


def complexity(node: ast.AST) -> int:
    branch_nodes = (
        ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With,
        ast.AsyncWith, ast.IfExp, ast.Assert, ast.comprehension,
    )
    match_type = getattr(ast, "Match", None)
    score = 1
    for child in iter_owned_nodes(node):
        if child is node:
            continue
        if isinstance(child, branch_nodes):
            score += 1
        elif isinstance(child, ast.BoolOp):
            score += max(1, len(child.values) - 1)
        elif match_type is not None and isinstance(child, match_type):
            score += max(1, len(child.cases))
    return score


def qualified_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = qualified_name(node.value)
        return "%s.%s" % (left, node.attr) if left else node.attr
    return ""


def import_aliases(tree: ast.AST) -> Dict[str, str]:
    aliases = {}  # type: Dict[str, str]
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split(".")[0]] = item.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for item in node.names:
                if item.name == "*":
                    continue
                local = item.asname or item.name
                aliases[local] = "%s.%s" % (module, item.name) if module else item.name
    return aliases


def _expand_alias(name: str, aliases: Dict[str, str]) -> str:
    first, separator, rest = name.partition(".")
    replacement = aliases.get(first)
    if replacement is None:
        return name
    return replacement + (separator + rest if separator else "")


def boundary_analysis(node: ast.AST, aliases: Dict[str, str]) -> Tuple[int, List[str]]:
    fixture = ("open", "Path", "pathlib.Path", "os", "shutil", "time", "datetime", "random", "uuid", "tempfile")
    concurrent = ("subprocess", "multiprocessing", "threading", "concurrent", "asyncio")
    external = ("requests", "httpx", "aiohttp", "socket", "sqlalchemy", "psycopg", "psycopg2", "pymongo", "boto3", "redis", "kafka", "grpc")
    tier = 0
    flags = set()  # type: Set[str]
    for child in iter_owned_nodes(node):
        if isinstance(child, (ast.Await, ast.AsyncFor, ast.AsyncWith)):
            tier = max(tier, 2)
            flags.add("ASYNC")
        elif isinstance(child, ast.Call):
            name = _expand_alias(qualified_name(child.func), aliases)
            if any(name == item or name.startswith(item + ".") for item in external):
                tier = max(tier, 3)
                flags.add("EXTERNAL:%s" % name)
            elif any(name == item or name.startswith(item + ".") for item in concurrent):
                tier = max(tier, 2)
                flags.add("CONCURRENT:%s" % name)
            elif any(name == item or name.startswith(item + ".") for item in fixture):
                tier = max(tier, 1)
                flags.add("FIXTURE:%s" % name)
    return tier, sorted(flags)


def public_symbol(name: str, kind: str) -> bool:
    return kind == "function" and not name.split(".")[-1].startswith("_")
