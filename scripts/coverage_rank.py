#!/usr/bin/env python3
"""Rank Python functions/classes/modules by estimated pytest coverage ROI."""
from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple


def ranges_to_lines(values: Sequence[Any]) -> Set[int]:
    out: Set[int] = set()
    for value in values or []:
        if isinstance(value, int):
            out.add(value)
        elif isinstance(value, (list, tuple)) and len(value) == 2:
            a, b = int(value[0]), int(value[1])
            out.update(range(a, b + 1))
    return out


def node_end(node: ast.AST) -> int:
    end = getattr(node, "end_lineno", None)
    if isinstance(end, int):
        return end
    maximum = getattr(node, "lineno", 1)
    for child in ast.walk(node):
        maximum = max(maximum, int(getattr(child, "lineno", maximum)))
    return maximum


def complexity(node: ast.AST) -> int:
    branch_nodes = (
        ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With,
        ast.AsyncWith, ast.IfExp, ast.Assert, ast.comprehension,
    )
    score = 1
    for child in ast.walk(node):
        if isinstance(child, branch_nodes):
            score += 1
        elif isinstance(child, ast.BoolOp):
            score += max(1, len(child.values) - 1)
        elif isinstance(child, ast.Match):
            score += max(1, len(child.cases))
    return score


def dependency_cost(node: ast.AST) -> float:
    score = 0.0
    expensive_names = {
        "requests", "httpx", "aiohttp", "socket", "subprocess", "multiprocessing",
        "sqlalchemy", "boto3", "redis", "kafka", "time", "sleep", "random",
        "open", "Path", "os", "shutil",
    }
    for child in ast.walk(node):
        if isinstance(child, (ast.Await, ast.AsyncFor, ast.AsyncWith)):
            score += 0.5
        elif isinstance(child, ast.Call):
            name = ""
            if isinstance(child.func, ast.Name):
                name = child.func.id
            elif isinstance(child.func, ast.Attribute):
                name = child.func.attr
            if name in expensive_names:
                score += 0.35
        elif isinstance(child, (ast.Raise, ast.Try)):
            score += 0.1
    return min(score, 5.0)


def public_bonus(name: str, kind: str) -> float:
    if kind == "module":
        return 0.0
    return 0.5 if not name.split(".")[-1].startswith("_") else 0.0


def iter_symbols(tree: ast.AST) -> Iterable[Tuple[str, str, ast.AST]]:
    yield "<module>", "module", tree

    def walk(body: Sequence[ast.stmt], prefix: str = "") -> Iterable[Tuple[str, str, ast.AST]]:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{node.name}"
                yield name, "function", node
            elif isinstance(node, ast.ClassDef):
                cname = f"{prefix}{node.name}"
                yield cname, "class", node
                yield from walk(node.body, cname + ".")
    yield from walk(getattr(tree, "body", []))


def normalized(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def matches(path: str, patterns: Sequence[str]) -> bool:
    p = normalized(path)
    return any(fnmatch.fnmatch(p, pattern) for pattern in patterns)


def extract_file_data(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    files = data.get("files", {})
    if not isinstance(files, dict):
        raise ValueError("coverage JSON has no 'files' mapping")
    return files


def rank_file(root: Path, reported_path: str, cov: Dict[str, Any]) -> List[Dict[str, Any]]:
    source_path = Path(reported_path)
    if not source_path.is_absolute():
        source_path = root / source_path
    if not source_path.exists() or source_path.suffix != ".py":
        return []
    try:
        text = source_path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(source_path))
    except (OSError, UnicodeError, SyntaxError):
        return []

    executed = ranges_to_lines(cov.get("executed_lines", []))
    missing = ranges_to_lines(cov.get("missing_lines", []))
    executable = executed | missing
    missing_branches = cov.get("missing_branches", []) or []
    results: List[Dict[str, Any]] = []

    for name, kind, node in iter_symbols(tree):
        start = 1 if kind == "module" else int(getattr(node, "lineno", 1))
        end = node_end(node) if kind != "module" else max(1, len(text.splitlines()))
        span = set(range(start, end + 1))
        symbol_exec = executable & span
        symbol_missing = missing & span
        if not symbol_exec or not symbol_missing:
            continue
        symbol_covered = executed & span
        arcs = [arc for arc in missing_branches if isinstance(arc, list) and arc and arc[0] in span]
        comp = complexity(node)
        dep = dependency_cost(node)
        missing_count = len(symbol_missing)
        branch_count = len(arcs)
        density = missing_count / max(1, len(symbol_exec))
        setup_cost = 1.0 + math.log2(1 + comp) * 0.8 + dep
        gain = missing_count + branch_count * 1.75
        risk_bonus = min(2.0, math.log2(1 + comp) * 0.35)
        score = (gain * (0.65 + density) * (1.0 + public_bonus(name, kind) + risk_bonus)) / setup_cost
        results.append({
            "file": normalized(os.path.relpath(source_path, root)),
            "symbol": name,
            "kind": kind,
            "start_line": start,
            "end_line": end,
            "executable_lines": len(symbol_exec),
            "covered_lines": len(symbol_covered),
            "missing_lines": sorted(symbol_missing),
            "missing_line_count": missing_count,
            "missing_branches": arcs,
            "missing_branch_count": branch_count,
            "complexity_estimate": comp,
            "dependency_cost": round(dep, 2),
            "missing_density": round(density, 4),
            "estimated_gain_units": round(gain, 2),
            "priority_score": round(score, 4),
        })
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage", required=True, help="coverage.py JSON file")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--output", default="-", help="output JSON path or -")
    parser.add_argument("--include", action="append", default=[], help="glob to include; repeatable")
    parser.add_argument("--exclude", nargs="*", default=[], help="glob patterns to exclude")
    parser.add_argument("--top", type=int, default=100, help="maximum targets")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    try:
        data = json.loads(Path(args.coverage).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        parser.error(f"cannot read coverage JSON: {exc}")

    default_excludes = [
        "*/site-packages/*", "*/dist-packages/*", "*/.venv/*", "*/venv/*",
        "*/migrations/*", "*/generated/*", "*/__pycache__/*",
    ]
    excludes = default_excludes + list(args.exclude)
    ranked: List[Dict[str, Any]] = []
    for reported_path, cov in extract_file_data(data).items():
        p = normalized(reported_path)
        if args.include and not matches(p, args.include):
            continue
        if matches(p, excludes):
            continue
        ranked.extend(rank_file(root, reported_path, cov))

    ranked.sort(key=lambda item: (-item["priority_score"], -item["estimated_gain_units"], item["file"], item["start_line"]))
    ranked = ranked[: max(0, args.top)]
    totals = data.get("totals", {})
    payload = {
        "schema_version": 1,
        "source_coverage": str(Path(args.coverage)),
        "coverage_totals": totals,
        "target_count": len(ranked),
        "targets": ranked,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=False)
    if args.output == "-":
        print(rendered)
    else:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
