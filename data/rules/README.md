# Machine-Readable Rules

Rules in this directory are deterministic preparation and workflow checks derived from reviewed requirements. They do not predict or make official decisions.

## Evaluation contract

- Rules are evaluated in ascending `priority` order.
- `when` uses explicit fact/operator/value conditions; omitted `when` means always.
- `all` requires every condition; `any` requires at least one.
- Supported operators in V1 are `eq`, `neq`, `in`, `not_in`, `gte`, `lte`, `present`, `absent`, `true`, `false`, `dataset_contains`, `dataset_stale`, and `days_after_lte`.
- Outcomes are `pass`, `action_required`, `manual_review`, or `unsupported_scope`; there is no `approved` outcome.
- When no rule produces a finding, the evaluation result is the declared `default_outcome: pass`, meaning preparation checks passed—not that Immigration approved the case.
- Every rule cites requirement IDs and official source IDs.
- A dataset-dependent rule must define behavior for stale or unknown data.
- When several findings trigger, outcome severity is `unsupported_scope` → `manual_review` → `action_required` → `pass`; all findings remain visible.

The first evaluator implementation must validate the rule file against `rule-set.schema.json` and run the cases in `tests/rules/` before use.

Run `ruby scripts/validate_knowledge_base.rb` for syntax, referential-integrity, dataset, and rule-case checks.
