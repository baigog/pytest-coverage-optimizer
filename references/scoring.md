# Target ranking model

The ranking is deliberately heuristic. Its purpose is to reduce model context and produce a strong first work queue, not to replace local reasoning.

## Quantities

For each AST symbol:

- `M`: missing executable lines.
- `B`: missing branch arcs originating inside the symbol.
- `E`: total executable lines.
- `D = M/E`: missing density.
- `C`: approximate cyclomatic complexity.
- `X`: dependency/setup cost inferred from async constructs and calls commonly associated with I/O, processes, time, randomness, databases, and networks.
- `P`: public API bonus.

Estimated gain units:

```text
G = M + 1.75 * B
```

Estimated setup cost:

```text
K = 1 + 0.8 * log2(1 + C) + X
```

Priority is proportional to:

```text
score = G * (0.65 + D) * (1 + P + risk_bonus) / K
```

Branch arcs are weighted more than lines because one test can execute a conditional line without testing both outcomes.

## Human adjustment

Raise priority for:

- existing nearby fixtures/tests;
- one public call reaching many missing lines;
- important validation, state, money, permissions, persistence, or concurrency behavior;
- deterministic behavior.

Lower priority for:

- external services or unavailable infrastructure;
- generated/deprecated/platform-only code;
- import-time-only gains;
- trivial property/delegation lines with low defect risk;
- defensive paths whose preconditions cannot occur through supported APIs.

Re-rank after every accepted iteration because marginal gain changes.
