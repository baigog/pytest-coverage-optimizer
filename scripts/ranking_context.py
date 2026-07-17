"""Test and iteration context for deterministic coverage ranking."""
from __future__ import annotations

import fnmatch
import json
import os
import re
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Sequence, Set, Tuple


STABLE_SKIP_REASONS = {
    "GENERATED", "VENDORED", "UNREACHABLE",
    "PLATFORM_UNSUPPORTED", "EXTERNAL_INFRA_REQUIRED",
}


class TestEvidence(NamedTuple):
    level: str
    paths: Tuple[str, ...]


class HistoryInfo(NamedTuple):
    attempts: int
    no_gain_attempts: int
    stable_skip_reason: str


class HistoryIndex(NamedTuple):
    targets: Dict[str, HistoryInfo]
    successful_files: Set[str]


def normalized(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def matches(path: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatch(normalized(path), pattern) for pattern in patterns)


def module_tokens(source_file: str) -> Tuple[str, ...]:
    path = normalized(source_file)
    parts = [part for part in (path[:-3] if path.endswith(".py") else path).split("/") if part]
    values = []  # type: List[str]
    if parts:
        values.extend([".".join(parts), parts[-1]])
    if parts and parts[0] in ("src", "lib") and len(parts) > 1:
        values.append(".".join(parts[1:]))
    return tuple(dict.fromkeys(values))


class TestIndex(object):
    def __init__(self, root: Path, test_roots: Sequence[Path]) -> None:
        self.files = []  # type: List[Tuple[str, str]]
        seen = set()  # type: Set[str]
        for test_root in test_roots:
            if not test_root.exists():
                continue
            for path in sorted(test_root.rglob("*.py")):
                try:
                    rel = normalized(os.path.relpath(str(path), str(root)))
                    if rel in seen or path.stat().st_size > 1024 * 1024:
                        continue
                    text = path.read_text(encoding="utf-8")
                except (OSError, UnicodeError):
                    continue
                seen.add(rel)
                self.files.append((rel, text))

    def evidence_for(self, source_file: str, symbol_name: str) -> TestEvidence:
        basename = Path(source_file).stem
        leaf = symbol_name.split(".")[-1]
        symbol_re = None if leaf in ("", "<module>") else re.compile(r"\b%s\b" % re.escape(leaf))
        import_res = [
            re.compile(r"(?m)^\s*(?:from|import)\s+%s(?:\b|\.)" % re.escape(token))
            for token in module_tokens(source_file)
        ]
        strong = []  # type: List[str]
        weak = []  # type: List[str]
        for path, text in self.files:
            path_match = bool(basename and basename in Path(path).stem)
            module_match = any(pattern.search(text) for pattern in import_res)
            symbol_match = bool(symbol_re is not None and symbol_re.search(text))
            if path_match or (module_match and symbol_match):
                strong.append(path)
            elif module_match or symbol_match:
                weak.append(path)
        if strong:
            return TestEvidence("strong", tuple(strong[:5]))
        if weak:
            return TestEvidence("weak", tuple(weak[:5]))
        return TestEvidence("none", ())


def parse_history(path: Optional[Path]) -> HistoryIndex:
    if path is None or not path.exists():
        return HistoryIndex({}, set())
    states = {}  # type: Dict[str, Dict[str, object]]
    successful = set()  # type: Set[str]
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return HistoryIndex({}, set())
    for line in lines:
        try:
            item = json.loads(line)
        except (TypeError, ValueError):
            continue
        target = str(item.get("target", ""))
        if not target:
            continue
        status = str(item.get("status", "")).lower()
        reason = str(item.get("reason_code", "")).upper()
        state = states.setdefault(target, {"attempts": 0, "no_gain": 0, "skip": ""})
        if status in ("accepted", "failed", "no_gain", "deferred", "rejected", "blocked"):
            state["attempts"] = int(state["attempts"]) + 1
        if status in ("failed", "no_gain"):
            state["no_gain"] = int(state["no_gain"]) + 1
        if status in ("rejected", "deferred", "blocked") and reason in STABLE_SKIP_REASONS:
            state["skip"] = reason
        if status == "accepted":
            successful.add(normalized(target.split("::", 1)[0]))
    targets = {
        target: HistoryInfo(int(state["attempts"]), int(state["no_gain"]), str(state["skip"]))
        for target, state in states.items()
    }
    return HistoryIndex(targets, successful)
