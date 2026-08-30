# Rule Cases

`student-pass-v1.cases.yaml` is an evaluator-neutral acceptance suite.

Each case applies its `overrides` to `base_facts` using JSON Merge Patch semantics, evaluates every rule in priority order, and compares triggered rule IDs. `must_include` is mandatory; `must_not_include` prevents known false positives. A case with no triggered rules receives the rule set's `default_outcome`.

These fixtures contain synthetic data only.

