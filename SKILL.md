---
name: pytest-coverage-optimizer
description: Systematically increase Python pytest line and branch coverage using machine-readable coverage data, AST-based target ranking, focused tests, and iterative verification. Use when asked to improve, repair, analyze, or maximize pytest coverage without manually reading HTML or terminal reports.
license: MIT
compatibility: OpenCode and Agent Skills compatible agents. Requires Python, pytest, coverage.py or pytest-cov; optional pytest-json-report.
metadata:
  author: OpenAI
  version: "1.0.0"
  domain: python-testing
---

# Pytest Coverage Optimizer

Use this skill to improve test coverage efficiently. Treat coverage improvement as an optimization problem, not as a request to make every file green.

## Objective

Maximize **verified coverage gain per unit of implementation and execution cost**, while preserving behavior and test quality.

The default optimization order is:

1. Restore a clean, passing baseline.
2. Measure line and branch coverage in JSON.
3. Rank executable targets by expected gain, cost, risk, and reachability.
4. Add the smallest meaningful tests for the highest-value target.
5. Run only affected tests first.
6. Recompute global coverage and repeat.
7. Stop when the requested threshold is reached or remaining gaps are justified exclusions, unreachable defensive paths, or disproportionately expensive integration behavior.

## Non-negotiable rules

- Never optimize from HTML, ANSI terminal tables, screenshots, or prose reports when JSON is available.
- Never modify production behavior merely to make a line executable.
- Never write assertion-free tests or tests that only check that code does not crash.
- Prefer externally visible behavior over private implementation details.
- Enable branch coverage unless the project explicitly measures lines only.
- Preserve the existing test style, fixtures, markers, and dependency policy.
- Do not run the entire suite after every edit when a focused subset can validate the change.
- Do not chase generated files, migrations, vendored code, protocol stubs, or type-only code unless explicitly required.
- Never claim a gain until it is confirmed by a fresh coverage run.

## Inputs to discover

Inspect, in this order:

1. `pyproject.toml`, `pytest.ini`, `tox.ini`, `setup.cfg`, `.coveragerc`.
2. Dependency files and supported Python version.
3. Source roots and test roots.
4. Existing fixtures in `conftest.py`.
5. Current test command from CI, Makefile, tox, nox, scripts, or project docs.
6. Coverage omit/include rules and threshold.

Do not dump whole files into context. Search configuration keys and read only relevant sections.

## Required artifacts

Create all transient files below `.coverage-agent/` unless the repository already defines an artifact directory:

- `.coverage-agent/coverage.json`: coverage.py JSON with branches.
- `.coverage-agent/tests.json`: pytest execution metadata when `pytest-json-report` is installed.
- `.coverage-agent/ranking.json`: ranked code targets from `scripts/coverage_rank.py`.
- `.coverage-agent/baseline.json`: baseline summary and command metadata.
- `.coverage-agent/iterations.jsonl`: one compact JSON object per optimization iteration.

Add `.coverage-agent/` to `.git/info/exclude` rather than changing `.gitignore`, unless the user asks for a committed workflow.

## Phase 0 — Establish a trustworthy baseline

Determine the canonical test command. Use `python -m pytest`, not a bare `pytest`, to bind execution to the selected interpreter.

Recommended command when pytest-cov is available:

```bash
mkdir -p .coverage-agent
python -m pytest \
  --cov=<SOURCE_ROOT> \
  --cov-branch \
  --cov-report= \
  --cov-context=test \
  --json-report \
  --json-report-file=.coverage-agent/tests.json \
  --json-report-omit=streams log warnings keywords \
  <TEST_ROOT>
python -m coverage json --show-contexts -o .coverage-agent/coverage.json
```

If `pytest-json-report` is unavailable, omit its options. Do not install new dependencies unless project policy permits it; coverage JSON alone is sufficient.

Alternative without pytest-cov:

```bash
python -m coverage erase
python -m coverage run --branch -m pytest <TEST_ROOT>
python -m coverage json --show-contexts -o .coverage-agent/coverage.json
```

If the baseline fails:

1. Save the failure metadata.
2. Separate environment/import/dependency failure from actual test failure.
3. Fix only infrastructure necessary to run the existing suite.
4. Do not start coverage optimization while the baseline is red unless the user explicitly asks to repair failing tests too.

Record:

```json
{
  "python": "3.x.y",
  "command": "...",
  "tests_passed": 0,
  "tests_failed": 0,
  "line_percent": 0.0,
  "branch_percent": 0.0,
  "covered_lines": 0,
  "missing_lines": 0,
  "covered_branches": 0,
  "missing_branches": 0
}
```

## Phase 1 — Produce a machine-ranked work queue

Run:

```bash
python <SKILL_ROOT>/scripts/coverage_rank.py \
  --coverage .coverage-agent/coverage.json \
  --root . \
  --output .coverage-agent/ranking.json
```

Optional filters:

```bash
python <SKILL_ROOT>/scripts/coverage_rank.py \
  --coverage .coverage-agent/coverage.json \
  --root . \
  --include 'src/**/*.py' \
  --exclude '*/generated/*' '*/migrations/*' \
  --top 30 \
  --output .coverage-agent/ranking.json
```

Read only the first 5–10 ranked entries, not the complete report. Each entry contains:

- source file and symbol;
- executable, covered, and missing lines;
- missing branch arcs where available;
- estimated maximum line gain;
- complexity and dependency indicators;
- priority score;
- exact source spans to inspect.

See [references/scoring.md](references/scoring.md) for the ranking model.

## Phase 2 — Validate the highest-value target

For each candidate, inspect only:

1. The target function/class span.
2. Directly imported collaborators used by the target.
3. Existing tests for the same module or public API.
4. Relevant fixtures.
5. Missing branch lines from `coverage.json`.

Reject or defer a candidate when:

- it is dead, deprecated, generated, platform-specific, or intentionally unreachable;
- testing it requires unavailable external infrastructure;
- uncovered lines are exception guards with no realistic trigger;
- the apparent gain comes primarily from import-time execution rather than meaningful behavior;
- a lower-ranked target gives a much cheaper verified gain.

When rejecting a target, append a compact reason to `iterations.jsonl` and continue.

## Phase 3 — Design tests from paths, not lines

Translate missing lines and branch arcs into behavior partitions.

For a target, enumerate only distinct control-flow cases needed to execute missing behavior:

- normal path;
- each uncovered `if`/`elif` outcome;
- loop empty/non-empty and boundary cases;
- expected exception path;
- collaborator success/failure;
- state transition before/after;
- serialization or parsing boundary;
- async completion/cancellation where applicable.

Use equivalence partitioning. One parametrized test should cover multiple equivalent inputs when assertions remain clear.

Test priority inside a symbol:

1. Public return values and state changes.
2. Error contracts and validation.
3. High-risk branches involving money, persistence, permissions, concurrency, or destructive behavior.
4. Boundary conditions.
5. Low-value formatting and logging branches.

## Phase 4 — Implement minimal meaningful tests

Prefer this order:

1. Reuse existing fixtures.
2. Construct real lightweight values.
3. Use `tmp_path`, `monkeypatch`, `capsys`, `caplog`, and pytest parametrization.
4. Mock only process/network/time/randomness/filesystem boundaries or expensive collaborators.
5. Patch where the dependency is looked up, not where it was originally defined.

Each test must contain assertions that would fail under a plausible defect. Good assertions include:

- exact or structural return value;
- state transition;
- exception type and relevant message;
- collaborator call arguments when that interaction is the contract;
- persisted/serialized output;
- invariant across parametrized inputs.

Avoid over-mocking internal functions because it can execute lines without validating behavior.

## Phase 5 — Fast verification loop

After editing tests:

1. Run the changed test node(s):

```bash
python -m pytest -q path/to/test_file.py::test_name
```

2. Run the target test module:

```bash
python -m pytest -q path/to/test_file.py
```

3. Recompute focused coverage when supported:

```bash
python -m pytest -q path/to/test_file.py \
  --cov=<TARGET_MODULE_OR_PACKAGE> --cov-branch --cov-report=
python -m coverage json -o .coverage-agent/coverage-focused.json
```

4. Once focused tests pass, run the canonical global coverage command.
5. Regenerate `ranking.json`.
6. Verify that the intended missing lines/arcs disappeared.

Append one JSON object to `.coverage-agent/iterations.jsonl`:

```json
{"target":"pkg/mod.py::Class.method","tests":["tests/test_mod.py::test_case"],"before":{"lines":71.2,"branches":55.0},"after":{"lines":73.8,"branches":61.0},"gain":{"lines":2.6,"branches":6.0},"status":"accepted"}
```

If coverage does not improve, determine whether:

- the new test never reached the target;
- the wrong module was measured;
- a subprocess was not measured;
- exclusions or source mapping hide the lines;
- the test duplicated an already-covered path;
- the intended branch is optimized away or version-dependent.

Delete or strengthen tests that add no behavioral value.

## Phase 6 — Re-rank and repeat

After every accepted target, regenerate the ranking. Coverage gain changes the marginal value of remaining targets.

Use batches of at most three tightly related targets when setup is shared. Otherwise make one target per iteration.

Stop reading source once enough information exists to write and verify the next test. Do not map the entire repository before acting.

## Choosing the next target

Use the ranking score as a starting point, then apply these tie-breakers:

1. More missing executable lines reachable through one public entry point.
2. More missing branches covered by the same fixture setup.
3. Existing nearby tests that can be extended.
4. Lower external dependency and nondeterminism cost.
5. Higher business risk.

A file with 30 missing lines may be better than one with 100 missing lines if those 30 are reachable with two deterministic unit tests and the 100 require an integration environment.

## Coverage contexts and test-to-code mapping

When `--cov-context=test` is available, request `--show-contexts` in JSON. Use contexts to answer:

- which tests already execute a line;
- whether a proposed test duplicates an existing path;
- which narrow test subset can validate a change;
- whether a broad integration test is the only current caller.

Do not load all contexts into the model. Query only the target file and line range using `scripts/query_coverage.py`.

Example:

```bash
python <SKILL_ROOT>/scripts/query_coverage.py \
  --coverage .coverage-agent/coverage.json \
  --file src/pkg/mod.py \
  --start 40 --end 95
```

## Branch interpretation

Line coverage alone can report a conditional line as covered while one outcome is untested. Prioritize uncovered branch arcs in logic-heavy code.

For an arc `[from, to]`:

- positive `to` is a destination line;
- negative values can represent entry/exit arcs depending on coverage.py representation;
- inspect the local AST/control flow before designing a test;
- verify the arc disappears from `missing_branches` after the test.

## Exclusions

Prefer configuration exclusions over fake tests for code that should not count:

- `if TYPE_CHECKING:`;
- abstract-method placeholders;
- defensive `raise AssertionError("unreachable")` with a proven invariant;
- platform branches outside the supported matrix;
- generated code.

Do not add exclusions solely because a path is inconvenient. Explain each new exclusion in the final report.

## Mutation testing: optional quality gate

Coverage says code executed; it does not prove assertions detect wrong behavior. After reaching the line/branch goal, mutation-test only the changed target or package when the project already uses a mutation tool or the user asks for stronger validation.

Do not run repository-wide mutation testing by default. It is expensive and is a second-stage quality check, not the primary coverage discovery mechanism.

## Completion criteria

A coverage task is complete only when:

- the canonical suite passes;
- fresh machine-readable coverage confirms the target threshold or documented best achievable result;
- branch coverage did not regress;
- added tests assert behavior;
- no production semantics were weakened;
- generated/transient artifacts are not accidentally committed;
- the final response reports exact before/after metrics, tests added, remaining gaps, and any exclusions.

## Final response format

Return a compact summary:

```text
Coverage: 72.4% -> 81.7% lines; 58.2% -> 74.0% branches
Tests added/changed: 7
Highest-impact targets covered: ...
Validation: <canonical command> (passed)
Remaining gaps: ...
Exclusions added: none
```

Never report only “coverage improved.” Include exact verified metrics.

## Supporting material

- Ranking details: [references/scoring.md](references/scoring.md)
- Failure and environment handling: [references/failure-playbook.md](references/failure-playbook.md)
- Machine-readable schemas: [references/data-contracts.md](references/data-contracts.md)
