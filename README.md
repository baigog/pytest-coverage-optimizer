# pytest-coverage-optimizer

Agent Skill for increasing pytest line and branch coverage using coverage.py JSON, AST-based target prioritization, and a focused verification loop.

## Python compatibility

The bundled scripts support Python 3.7 and newer.

A known-compatible Python 3.7 toolchain is:

```bash
python3.7 -m pip install \
  "pytest==7.4.4" \
  "pytest-cov==4.1.0" \
  "coverage==6.5.0"
```

`pytest-json-report` is optional. Do not require `pytest-cov` to emit JSON directly.

## Machine-readable coverage workflow

Use pytest-cov only to collect coverage data and suppress human-readable reports:

```bash
mkdir -p .coverage-agent
python3.7 -m coverage erase
python3.7 -m pytest \
  --cov=<SOURCE_ROOT> \
  --cov-branch \
  --cov-report= \
  <TEST_ROOT>
python3.7 -m coverage json \
  --show-contexts \
  -o .coverage-agent/coverage.json
```

Do **not** depend on:

```bash
--cov-report=json
```

Older pytest-cov installations may not expose that report format. The separate `coverage json` command is the canonical workflow used by this skill.

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
