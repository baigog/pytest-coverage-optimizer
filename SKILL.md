---
name: pytest-coverage-optimizer
description: Increase Python pytest line and branch coverage with machine-readable coverage, deterministic target classes, one-target test generation, and verified feedback. Use when asked to improve or analyze pytest coverage without manually reading HTML or terminal reports.
license: MIT
compatibility: OpenCode and Agent Skills compatible agents. Requires Python 3.7+, pytest, coverage.py or pytest-cov; optional pytest-json-report.
metadata:
  author: OpenAI
  version: "0.3.0"
  python: ">=3.7"
  domain: python-testing
---

# Pytest Coverage Optimizer

Follow this state machine exactly. Do not replace it with an improvised repository-wide review.

## Objective

Increase verified line and branch coverage with meaningful behavioral assertions while minimizing source files read, test attempts, and full-suite executions.

The ranking script makes the mechanical target-selection decisions. The agent validates reachability and writes tests for one target at a time.

## Non-negotiable rules

- Use machine-readable coverage JSON. Do not rank targets from HTML, screenshots, ANSI tables, or prose.
- Enable branch coverage unless the project explicitly measures lines only.
- Do not modify production behavior solely to increase coverage.
- Do not add assertion-free tests or tests that only prove code does not crash.
- Prefer public return values, state changes, emitted data, persisted data, and documented exceptions.
- Preserve existing fixtures, markers, naming, and dependency policy.
- Work on one target per iteration.
- Make at most two test attempts for one target before deferring it.
- Never claim coverage gain until a fresh global coverage run confirms it.
- Never reorder candidate classes using intuition. Use the selection protocol below.

## Required artifacts

Create transient files below `.coverage-agent/`:

- `coverage.json`: global line and branch coverage.
- `tests.json`: optional pytest execution metadata.
- `ranking.json`: deterministic target queue.
- `baseline.json`: baseline commands and metrics.
- `iterations.jsonl`: one compact result per attempted or rejected target.

Add `.coverage-agent/` to `.git/info/exclude`, not `.gitignore`, unless the user asks to commit the workflow.

## State 0 — Discover the canonical commands

Read only relevant sections of these files, in this order:

1. `pyproject.toml`, `pytest.ini`, `tox.ini`, `setup.cfg`, `.coveragerc`.
2. CI, Makefile, tox, nox, or project documentation containing the test command.
3. Dependency files and supported Python versions.
4. Source roots and test roots.
5. `conftest.py` and nearby tests only when a candidate requires them.

Use `python -m pytest`, not bare `pytest`.

## State 1 — Establish a passing baseline

With pytest-cov:

```bash
mkdir -p .coverage-agent
python -m coverage erase
python -m pytest \
  --cov=<SOURCE_ROOT> \
  --cov-branch \
  --cov-report= \
  --cov-context=test \
  <TEST_ROOT>
python -m coverage json --show-contexts -o .coverage-agent/coverage.json
```

When `pytest-json-report` is already available, add:

```bash
--json-report \
--json-report-file=.coverage-agent/tests.json \
--json-report-omit=streams log warnings keywords
```

Without pytest-cov:

```bash
python -m coverage erase
python -m coverage run --branch --source=<SOURCE_ROOT> -m pytest <TEST_ROOT>
python -m coverage json --show-contexts -o .coverage-agent/coverage.json
```

If the baseline fails, stop coverage optimization. Fix only environment or collection failures required to run the existing suite unless the user also requested test repair.

Record exact baseline line percentage, branch percentage, missing lines, missing branches, interpreter, and command in `baseline.json`.

## State 2 — Generate the deterministic queue

Run:

```bash
python <SKILL_ROOT>/scripts/coverage_rank.py \
  --coverage .coverage-agent/coverage.json \
  --root . \
  --tests-root <TEST_ROOT> \
  --history .coverage-agent/iterations.jsonl \
  --top 30 \
  --output .coverage-agent/ranking.json
```

Omit `--history` only on the first iteration. Repeat `--tests-root` for multiple test roots.

The ranker produces these classes:

| Class | Meaning | Agent action |
|---|---|---|
| A | Public function, local or fixture-only setup, strong nearby test evidence | Attempt first |
| B | Public function, local or fixture-only setup, weaker nearby test evidence | Attempt after A |
| C | Public function, local or fixture-only setup, no nearby test evidence | Inspect, then attempt |
| D | Private/concurrent target with existing test evidence | Attempt only when A-C are absent |
| E | External-infrastructure, module-body, class-body, or otherwise costly target | Do not attempt automatically |
| Z | Stable rejection already recorded in history | Skip |

Within a class, the ranker orders by:

1. More missing branch arcs.
2. More missing executable lines.
3. Lower owned-scope complexity.
4. File path and source line for deterministic ties.

Do not invent a new score. Do not move an E target above an A-D target.

## State 3 — Select exactly one target

Read candidate summaries only. Apply this exact selection rule:

1. Select the first class A target.
2. If no A exists, select the first B target.
3. If no A or B exists, select the first C target.
4. If no A-C exists, select the first D target only when `test_evidence.paths` is non-empty.
5. If only E targets remain, stop and report that the remaining work requires manual integration decisions.

After selecting a target, read no more than:

- the target source span;
- the first matching test file from `test_evidence.paths`, when present;
- the relevant fixture definitions;
- directly used collaborator definitions only when required to construct inputs.

Maximum source/test files read for one target: four.

## State 4 — Candidate gate

Answer each gate with YES or NO before editing tests. Use the first matching rejection rule.

1. **Countable code:** Is the target generated, vendored, migration-only, unsupported-platform-only, deprecated, or type-only?
   - YES: record `status=rejected` with `reason_code=GENERATED`, `VENDORED`, or `PLATFORM_UNSUPPORTED`.
2. **Reachable behavior:** Can a supported public call reach the missing behavior?
   - NO: record `status=rejected`, `reason_code=UNREACHABLE`.
3. **Observable contract:** Can the test assert a return value, state change, exception contract, emitted/persisted data, or required collaborator interaction?
   - NO: record `status=rejected`, `reason_code=NO_ASSERTABLE_BEHAVIOR`.
4. **Available setup:** Can existing fixtures, real lightweight values, `tmp_path`, or `monkeypatch` provide the setup?
   - NO, and external infrastructure is required: record `status=deferred`, `reason_code=EXTERNAL_INFRA_REQUIRED`.
5. **Distinct path:** Does the proposed test execute a currently missing line or branch rather than duplicate an existing context?
   - NO: choose another input path. If none exists, record `status=no_gain`, `reason_code=DUPLICATE_PATH`.

After a rejection or deferral, append history, regenerate `ranking.json`, and return to State 3.

## State 5 — Write one explicit test plan

Before editing, write this four-field plan in scratch output:

```text
TARGET: <file::symbol>
SETUP: <fixtures and inputs>
ACTION: <single public call>
ASSERT: <exact observable result>
COVERS: <missing line numbers and/or branch arcs>
```

If `ASSERT` is vague, do not write the test. Return to the candidate gate.

Test construction order:

1. Extend the first existing matching test file.
2. Reuse existing fixtures.
3. Use real lightweight values.
4. Use pytest built-ins such as `tmp_path`, `monkeypatch`, `capsys`, `caplog`, and parametrization.
5. Mock only external boundaries or expensive collaborators.
6. Patch where the collaborator is looked up.

Do not mock the target itself. Avoid mocking internal functions merely to execute lines.

## State 6 — Two-attempt verification limit

Attempt 1:

1. Add the smallest test implementing the plan.
2. Run only the changed test node.
3. When it passes, run the test module.
4. Measure focused coverage for the target module when practical.

```bash
python -m pytest -q path/to/test_file.py::test_name
python -m pytest -q path/to/test_file.py
```

Attempt 2 is allowed only to correct one of these concrete problems:

- incorrect fixture or constructor;
- incorrect patch location;
- incorrect expected value;
- test reached the target but missed the intended path.

After two failed attempts, stop editing that target. Append:

```json
{"target":"pkg/mod.py::symbol","status":"failed","reason_code":"ATTEMPT_LIMIT","tests":["tests/test_mod.py::test_name"]}
```

Then regenerate the queue. Do not continue improvising on the same target.

## State 7 — Verify globally and record evidence

After the focused test passes:

1. Run the canonical global coverage command.
2. Regenerate `coverage.json`.
3. Confirm the intended missing lines or branch arcs disappeared.
4. Confirm branch coverage did not regress.
5. Append one history object.

Accepted example:

```json
{"target":"pkg/mod.py::Parser.parse","status":"accepted","reason_code":"VERIFIED_GAIN","tests":["tests/test_mod.py::test_parse_empty"],"before":{"missing_lines":4,"missing_branches":2},"after":{"missing_lines":1,"missing_branches":0},"gain":{"lines":3,"branches":2}}
```

No-gain example:

```json
{"target":"pkg/mod.py::Parser.parse","status":"no_gain","reason_code":"DUPLICATE_PATH","tests":["tests/test_mod.py::test_parse_empty"]}
```

Regenerate `ranking.json` after every history append. A successful target in one file promotes remaining targets in that file because fixture setup may be reusable. Two no-gain or failed attempts demote a target. Stable rejection reason codes place it in class Z.

## Coverage contexts

Use contexts only for the selected target:

```bash
python <SKILL_ROOT>/scripts/query_coverage.py \
  --coverage .coverage-agent/coverage.json \
  --file src/pkg/mod.py \
  --start 40 --end 95
```

Use the result to identify existing tests and avoid duplicate paths. Do not load every context into the model.

## Stop conditions

Stop when any condition is true:

- requested line and branch thresholds are verified;
- no class A-D candidates remain;
- remaining targets require unavailable external infrastructure;
- every remaining reachable target has reached the two-attempt limit;
- remaining gaps have documented stable rejection reasons.

Do not create fake tests for unreachable or excluded code. Prefer explicit coverage configuration only when the code truly should not count.

## Optional mutation check

Coverage proves execution, not fault detection. Run mutation testing only for changed targets when the project already uses a mutation tool or the user explicitly requests it. Do not run repository-wide mutation testing by default.

## Completion report

Report exact verified values:

```text
Coverage: <before> -> <after> lines; <before> -> <after> branches
Targets accepted: <count>
Targets deferred/rejected: <count and reason codes>
Tests added/changed: <paths or node IDs>
Validation: <canonical command and result>
Remaining classes: <A/B/C/D/E counts>
Exclusions added: <none or explicit list>
```

Never report only that coverage improved.

## Supporting material

- Deterministic ranking: [references/scoring.md](references/scoring.md)
- Failure and environment handling: [references/failure-playbook.md](references/failure-playbook.md)
- Machine-readable schemas: [references/data-contracts.md](references/data-contracts.md)
