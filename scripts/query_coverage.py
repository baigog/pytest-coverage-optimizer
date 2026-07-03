#!/usr/bin/env python3
"""Extract a compact file/line slice from coverage.py JSON."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional


def norm(p: str) -> str:
    return p.replace("\\", "/").lstrip("./")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--coverage", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=10**9)
    args = ap.parse_args()
    data = json.loads(Path(args.coverage).read_text(encoding="utf-8"))
    wanted = norm(args.file)
    match = None  # type: Optional[Dict[str, Any]]
    matched_name = ""
    for name, value in data.get("files", {}).items():
        if norm(name) == wanted or norm(name).endswith("/" + wanted):
            match, matched_name = value, name
            break
    if match is None:
        raise SystemExit("file not found in coverage JSON: %s" % args.file)

    def in_range(n: Any) -> bool:
        return isinstance(n, int) and args.start <= n <= args.end

    contexts = {
        str(line): values for line, values in (match.get("contexts", {}) or {}).items()
        if str(line).isdigit() and args.start <= int(line) <= args.end
    }
    output = {
        "file": matched_name,
        "range": [args.start, args.end],
        "executed_lines": [n for n in match.get("executed_lines", []) if in_range(n)],
        "missing_lines": [n for n in match.get("missing_lines", []) if in_range(n)],
        "executed_branches": [a for a in match.get("executed_branches", []) if a and in_range(a[0])],
        "missing_branches": [a for a in match.get("missing_branches", []) if a and in_range(a[0])],
        "contexts": contexts,
    }
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
