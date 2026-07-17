# Machine-readable data contracts

## ranking.json schema version 2

```json
{
  "schema_version": 2,
  "methodology": "deterministic-selection-classes-v1",
  "coverage_totals": {},
  "selection_order": ["A", "B", "C", "D", "E", "Z"],
  "target_count": 1,
  "targets": [
    {
      "target": "src/pkg/mod.py::Parser.parse",
      "file": "src/pkg/mod.py",
      "symbol": "Parser.parse",
      "kind": "function",
      "start_line": 40,
      "end_line": 93,
      "missing_lines": [48, 49],
      "missing_line_count": 2,
      "missing_branches": [[52, 55]],
      "missing_branch_count": 1,
      "complexity_estimate": 8,
      "setup_tier": 1,
      "boundary_flags": ["FIXTURE:Path.read_text"],
      "public_entry_point": true,
      "test_evidence": {
        "level": "strong",
        "paths": ["tests/test_mod.py"]
      },
      "history": {
        "attempts": 0,
        "no_gain_attempts": 0,
        "shared_setup": false,
        "stable_skip_reason": ""
      },
      "selection_class": "A",
      "agent_action": "ATTEMPT",
      "rank_vector": [0, -1, -2, 8],
      "why_selected": [
        "class=A",
        "missing_branches=1",
        "missing_lines=2",
        "setup_tier=1",
        "test_evidence=strong"
      ],
      "agent_limits": {
        "max_source_files_to_read": 4,
        "max_test_attempts": 2,
        "one_target_only": true
      },
      "reject_reason_codes": [
        "GENERATED",
        "VENDORED",
        "UNREACHABLE",
        "PLATFORM_UNSUPPORTED",
        "EXTERNAL_INFRA_REQUIRED",
        "NO_ASSERTABLE_BEHAVIOR"
      ]
    }
  ]
}
```

Class Z targets are omitted unless `--include-skipped` is passed.

## iterations.jsonl

One JSON object per line. Use these statuses:

- `accepted`: fresh global coverage verified a gain;
- `failed`: the two-attempt limit was reached;
- `no_gain`: the test passed but did not remove the intended gap;
- `rejected`: the target should not be tested;
- `deferred`: the target requires unavailable or disproportionate setup.

Recommended fields:

```json
{"target":"src/pkg/mod.py::Parser.parse","status":"accepted|failed|no_gain|rejected|deferred","reason_code":"VERIFIED_GAIN|ATTEMPT_LIMIT|DUPLICATE_PATH|GENERATED|VENDORED|UNREACHABLE|PLATFORM_UNSUPPORTED|EXTERNAL_INFRA_REQUIRED|NO_ASSERTABLE_BEHAVIOR","tests":[],"before":{},"after":{},"gain":{}}
```

JSONL lets the agent append one result without parsing and rewriting prior history. The ranker reads this file for deterministic promotion, demotion, and stable skipping.

## baseline.json

Store interpreter, commands, git revision when available, test summary, coverage totals, and timestamp. Do not store full terminal output.
