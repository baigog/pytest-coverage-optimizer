#!/usr/bin/env python3
"""Rank Python coverage targets with deterministic agent-friendly classes."""
from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Sequence

from ranking_ast import (
    boundary_analysis, complexity, import_aliases, iter_symbols, node_end,
    owned_span, public_symbol, ranges_to_lines,
)
from ranking_context import (
    HistoryInfo, HistoryIndex, TestEvidence, TestIndex, matches, normalized,
    parse_history,
)


CLASS_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "Z": 5}


def extract_files(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    files = data.get("files", {})
    if not isinstance(files, dict):
        raise ValueError("coverage JSON has no 'files' mapping")
    return files


def promote(value: str) -> str:
    return chr(ord(value) - 1) if value in ("B", "C", "D", "E") else value


def demote(value: str) -> str:
    return chr(ord(value) + 1) if value in ("A", "B", "C", "D") else value


def choose_class(
    kind: str,
    is_public: bool,
    setup_tier: int,
    evidence: str,
    history: HistoryInfo,
    shared_setup: bool,
) -> str:
    if history.stable_skip_reason:
        return "Z"
    if kind == "function" and is_public and setup_tier <= 1 and evidence == "strong":
        value = "A"
    elif kind == "function" and is_public and setup_tier <= 1 and evidence == "weak":
        value = "B"
    elif kind == "function" and is_public and setup_tier <= 1:
        value = "C"
    elif setup_tier <= 2 and evidence != "none":
        value = "D"
    else:
        value = "E"
    if shared_setup:
        value = promote(value)
    if history.no_gain_attempts >= 2:
        value = demote(value)
    return value


def action_for(value: str) -> str:
    return {
        "A": "ATTEMPT", "B": "ATTEMPT", "C": "INSPECT_THEN_ATTEMPT",
        "D": "DEFER_UNLESS_NO_A_B_C", "E": "DEFER", "Z": "SKIP",
    }[value]


def selection_reasons(
    value: str,
    missing_lines: int,
    missing_branches: int,
    setup_tier: int,
    evidence: TestEvidence,
    shared_setup: bool,
    history: HistoryInfo,
) -> List[str]:
    reasons = [
        "class=%s" % value,
        "missing_branches=%d" % missing_branches,
        "missing_lines=%d" % missing_lines,
        "setup_tier=%d" % setup_tier,
        "test_evidence=%s" % evidence.level,
    ]
    if shared_setup:
        reasons.append("same_file_previously_succeeded")
    if history.no_gain_attempts:
        reasons.append("previous_no_gain_attempts=%d" % history.no_gain_attempts)
    if history.stable_skip_reason:
        reasons.append("stable_skip=%s" % history.stable_skip_reason)
    return reasons


def rank_file(
    root: Path,
    reported_path: str,
    coverage: Dict[str, Any],
    tests: TestIndex,
    history_index: HistoryIndex,
) -> List[Dict[str, Any]]:
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

    source_file = normalized(os.path.relpath(str(source_path), str(root)))
    executed = ranges_to_lines(coverage.get("executed_lines", []))
    missing = ranges_to_lines(coverage.get("missing_lines", []))
    executable = executed | missing
    missing_branches = coverage.get("missing_branches", []) or []
    aliases = import_aliases(tree)
    results = []  # type: List[Dict[str, Any]]

    for symbol in iter_symbols(tree):
        name, kind, node, descendants = symbol
        start = 1 if kind == "module" else int(getattr(node, "lineno", 1))
        end = node_end(node) if kind != "module" else max(1, len(text.splitlines()))
        span = owned_span(start, end, descendants)
        symbol_exec = executable & span
        symbol_missing = missing & span
        if not symbol_exec or not symbol_missing:
            continue
        arcs = [arc for arc in missing_branches if isinstance(arc, list) and arc and arc[0] in span]
        target = "%s::%s" % (source_file, name)
        history = history_index.targets.get(target, HistoryInfo(0, 0, ""))
        shared_setup = source_file in history_index.successful_files
        evidence = tests.evidence_for(source_file, name)
        setup_tier, boundary_flags = boundary_analysis(node, aliases)
        comp = complexity(node)
        value = choose_class(
            kind, public_symbol(name, kind), setup_tier,
            evidence.level, history, shared_setup,
        )
        missing_count = len(symbol_missing)
        branch_count = len(arcs)
        results.append({
            "target": target,
            "file": source_file,
            "symbol": name,
            "kind": kind,
            "start_line": start,
            "end_line": end,
            "executable_lines": len(symbol_exec),
            "covered_lines": len(executed & span),
            "missing_lines": sorted(symbol_missing),
            "missing_line_count": missing_count,
            "missing_branches": arcs,
            "missing_branch_count": branch_count,
            "complexity_estimate": comp,
            "setup_tier": setup_tier,
            "boundary_flags": boundary_flags,
            "public_entry_point": public_symbol(name, kind),
            "test_evidence": {"level": evidence.level, "paths": list(evidence.paths)},
            "history": {
                "attempts": history.attempts,
                "no_gain_attempts": history.no_gain_attempts,
                "shared_setup": shared_setup,
                "stable_skip_reason": history.stable_skip_reason,
            },
            "selection_class": value,
            "agent_action": action_for(value),
            "rank_vector": [CLASS_ORDER[value], -branch_count, -missing_count, comp],
            "why_selected": selection_reasons(
                value, missing_count, branch_count, setup_tier,
                evidence, shared_setup, history,
            ),
            "agent_limits": {
                "max_source_files_to_read": 4,
                "max_test_attempts": 2,
                "one_target_only": True,
            },
            "reject_reason_codes": [
                "GENERATED", "VENDORED", "UNREACHABLE",
                "PLATFORM_UNSUPPORTED", "EXTERNAL_INFRA_REQUIRED",
                "NO_ASSERTABLE_BEHAVIOR",
            ],
        })
    return results


def test_roots(root: Path, supplied: Sequence[str]) -> List[Path]:
    if supplied:
        return [root / value for value in supplied]
    return [path for path in (root / "tests", root / "test") if path.exists()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="-")
    parser.add_argument("--include", action="append", default=[])
    parser.add_argument("--exclude", nargs="*", default=[])
    parser.add_argument("--tests-root", action="append", default=[])
    parser.add_argument("--history", default="")
    parser.add_argument("--include-skipped", action="store_true")
    parser.add_argument("--top", type=int, default=100)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    try:
        data = json.loads(Path(args.coverage).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error("cannot read coverage JSON: %s" % exc)

    excludes = [
        "*/site-packages/*", "*/dist-packages/*", "*/.venv/*", "*/venv/*",
        "*/migrations/*", "*/generated/*", "*/__pycache__/*",
    ] + list(args.exclude)
    roots = test_roots(root, args.tests_root)
    tests = TestIndex(root, roots)
    history = parse_history(Path(args.history) if args.history else None)
    ranked = []  # type: List[Dict[str, Any]]
    for reported_path, coverage in extract_files(data).items():
        path = normalized(reported_path)
        if args.include and not matches(path, args.include):
            continue
        if matches(path, excludes):
            continue
        ranked.extend(rank_file(root, reported_path, coverage, tests, history))

    if not args.include_skipped:
        ranked = [item for item in ranked if item["selection_class"] != "Z"]
    ranked.sort(key=lambda item: (tuple(item["rank_vector"]), item["file"], item["start_line"]))
    ranked = ranked[:max(0, args.top)]
    payload = {
        "schema_version": 2,
        "methodology": "deterministic-selection-classes-v1",
        "source_coverage": str(Path(args.coverage)),
        "source_history": args.history or None,
        "test_roots": [normalized(os.path.relpath(str(path), str(root))) for path in roots],
        "coverage_totals": data.get("totals", {}),
        "target_count": len(ranked),
        "selection_order": ["A", "B", "C", "D", "E", "Z"],
        "targets": ranked,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=False)
    if args.output == "-":
        print(rendered)
    else:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
