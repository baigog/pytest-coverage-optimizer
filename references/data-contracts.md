# Machine-readable data contracts

## ranking.json

```json
{
  "schema_version": 1,
  "coverage_totals": {},
  "target_count": 1,
  "targets": [
    {
      "file": "src/pkg/mod.py",
      "symbol": "Parser.parse",
      "kind": "function",
      "start_line": 40,
      "end_line": 93,
      "executable_lines": 38,
      "covered_lines": 12,
      "missing_lines": [48, 49],
      "missing_line_count": 26,
      "missing_branches": [[52, 55]],
      "missing_branch_count": 1,
      "complexity_estimate": 8,
      "dependency_cost": 0.0,
      "missing_density": 0.6842,
      "estimated_gain_units": 27.75,
      "priority_score": 12.3456
    }
  ]
}
```

## iterations.jsonl

One object per line. Required keys:

```json
{"target":"...","status":"accepted|rejected|blocked","reason":"optional","tests":[],"before":{},"after":{},"gain":{}}
```

JSONL is used so the agent can append one iteration without parsing or rewriting prior history.

## baseline.json

Store interpreter, commands, git revision when available, test summary, coverage totals, and timestamp. Do not store full terminal output.
