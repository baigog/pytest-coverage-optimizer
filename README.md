# pytest-coverage-optimizer

Agent Skill for increasing pytest line and branch coverage with coverage.py JSON, deterministic target classes, one-target test generation, and verified feedback.

The methodology is designed for agents using modest models: the script selects and describes candidates mechanically, while the agent follows a fixed gate and may attempt only one target at a time.

## What changed in methodology v0.3

The previous scalar ROI heuristic was replaced by explicit A-E selection classes:

- existing test evidence and setup tier determine the class;
- missing branches, missing lines, and owned-scope complexity determine order within the class;
- prior accepted, failed, rejected, and no-gain iterations adjust later rankings;
- stable rejected targets are skipped;
- each candidate contains an explicit agent action, limits, and rejection reason codes.

See [`references/scoring.md`](references/scoring.md) for the complete deterministic rules.

## Python compatibility

The bundled scripts support Python 3.7 and newer.

A known-compatible Python 3.7 toolchain is:

```bash
python3.7 -m pip install \
  "pytest==7.4.4" \
  "pytest-cov==4.1.0" \
  "coverage==6.5.0"
```

`pytest-json-report` is optional. Do not require pytest-cov to emit JSON directly.

## Machine-readable coverage workflow

Use pytest-cov to collect data and coverage.py to emit JSON:

```bash
mkdir -p .coverage-agent
python3.7 -m coverage erase
python3.7 -m pytest \
  --cov=<SOURCE_ROOT> \
  --cov-branch \
  --cov-report= \
  --cov-context=test \
  <TEST_ROOT>
python3.7 -m coverage json \
  --show-contexts \
  -o .coverage-agent/coverage.json
```

Do not depend on `--cov-report=json`; older pytest-cov versions may not expose that format.

Generate the deterministic queue:

```bash
python3.7 scripts/coverage_rank.py \
  --coverage .coverage-agent/coverage.json \
  --root . \
  --tests-root tests \
  --history .coverage-agent/iterations.jsonl \
  --output .coverage-agent/ranking.json
```

Omit `--history` on the first run.

Without pytest-cov:

```bash
python3.7 -m coverage erase
python3.7 -m coverage run \
  --branch \
  --source=<SOURCE_ROOT> \
  -m pytest <TEST_ROOT>
python3.7 -m coverage json \
  --show-contexts \
  -o .coverage-agent/coverage.json
```

## Install for OpenCode

Project-local:

```bash
mkdir -p .opencode/skills
cp -R pytest-coverage-optimizer .opencode/skills/
```

Global:

```bash
mkdir -p ~/.config/opencode/skills
cp -R pytest-coverage-optimizer ~/.config/opencode/skills/
```

OpenCode requires the directory name to match `name: pytest-coverage-optimizer` in `SKILL.md`.

## Optional pytest execution JSON

```bash
python3.7 -m pip install pytest-json-report
```
