# Failure playbook

## Collection or import failure

Capture compact diagnostics:

```bash
python -m pytest --collect-only -q >.coverage-agent/collect.txt 2>&1
python -m pip check >.coverage-agent/pip-check.txt 2>&1
python -c 'import sys; print(sys.executable); print(sys.version); print(*sys.path, sep="\n")'
```

Inspect only the first causal traceback, not repeated downstream failures.

Common causes:

- wrong interpreter or stale `PYTHONHOME`/`PYTHONPATH`;
- missing test extras;
- incompatible plugin auto-loaded globally;
- package not installed in editable mode;
- source-root mismatch;
- compiled dependency unavailable for the Python version.

Use `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` only diagnostically, then explicitly enable required plugins.

## Test passes alone but fails globally

Check shared state, environment variables, current directory, monkeypatch cleanup, singleton caches, random order, and time dependence. Reproduce with the smallest pair/order of tests.

## Coverage lower than expected

Check:

- measured source root;
- subprocess/concurrency coverage configuration;
- stale `.coverage` files;
- xdist data combination;
- source aliases/path mapping;
- code imported before measurement starts;
- branch measurement actually enabled.

## Flaky test

Do not count flaky coverage as success. Remove nondeterminism by controlling time, randomness, scheduling, I/O, and process boundaries. Run the focused test repeatedly before accepting it.
