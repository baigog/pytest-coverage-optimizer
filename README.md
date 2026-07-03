# pytest-coverage-optimizer

Agent Skill for increasing pytest line and branch coverage using coverage.py JSON, AST-based target prioritization, and a focused verification loop.

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

## Minimal dependencies

```bash
python -m pip install pytest coverage pytest-cov
```

Optional machine-readable pytest execution report:

```bash
python -m pip install pytest-json-report
```
