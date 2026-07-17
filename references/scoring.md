# Deterministic target selection

The ranker does not estimate a universal numeric return on investment. It produces explicit selection classes that a small model can follow without inventing weights.

## Inputs per owned AST symbol

- missing executable lines;
- missing branch arcs originating in the symbol-owned line span;
- owned-scope complexity, excluding nested functions, methods, and classes;
- setup tier inferred from fully qualified call names;
- public function status;
- evidence that an existing test references the source module or symbol;
- prior accepted, failed, no-gain, rejected, or deferred iterations.

Parent class and module targets do not inherit missing lines, complexity, or dependency flags from descendant functions and methods.

## Setup tiers

| Tier | Meaning | Examples |
|---|---|---|
| 0 | Isolated synchronous logic | arithmetic, parsing, validation |
| 1 | Standard pytest fixtures or monkeypatch | filesystem, environment, time, randomness |
| 2 | Concurrency/process setup | async, subprocess, threading, multiprocessing |
| 3 | External infrastructure | HTTP, sockets, databases, cloud SDKs, brokers |

The analyzer resolves qualified names such as `requests.get`, `os.remove`, and `Path.read_text`. It does not infer cost from only the final attribute name.

## Test evidence

- `strong`: the test filename matches the source basename, or the test both imports the source module and references the symbol.
- `weak`: the test imports the source module or references the symbol, but not both.
- `none`: no matching test file was found.

Evidence identifies where setup may already exist. It is not proof that the target is already tested.

## Selection classes

| Class | Rule |
|---|---|
| A | Public function, setup tier 0-1, strong test evidence |
| B | Public function, setup tier 0-1, weak test evidence |
| C | Public function, setup tier 0-1, no test evidence |
| D | Setup tier 0-2 with test evidence, but not A-C |
| E | All other candidates |
| Z | Stable rejection from history |

Within a class, sort by this lexicographic vector:

```text
[class_order, -missing_branch_count, -missing_line_count, complexity]
```

Path and start line break exact ties. No scalar score is used.

## History adaptation

- An accepted target marks its source file as having reusable setup. Remaining targets in that file are promoted by one class.
- Two `failed` or `no_gain` attempts demote the target by one class.
- `GENERATED`, `VENDORED`, `UNREACHABLE`, `PLATFORM_UNSUPPORTED`, and `EXTERNAL_INFRA_REQUIRED` are stable rejection reasons and place the target in class Z.
- Coverage is regenerated after every accepted iteration, so already-covered targets naturally leave the queue.

## Why this method is intentionally limited

Static analysis cannot reliably determine semantic reachability, assertion quality, or real integration cost. The script performs only deterministic mechanical selection. The agent performs a fixed candidate gate for the first eligible target and may not override the class order by intuition.
