from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.enums import DocumentStatus
from app.database.models import (
    Document,
    EvaluationFinding,
    ImmigrationCase,
    RuleEvaluation,
    RuleSetVersion,
    RuleVersion,
    StudentPassCaseProfile,
)
from app.knowledge.dsl import validate_rule_condition

OUTCOME_PRIORITY = {"pass": 0, "manual_review": 1, "action_required": 2, "unsupported_scope": 3}
PENINSULAR_REGION_CODES = frozenset(
    {
        "MY-01",
        "MY-02",
        "MY-03",
        "MY-04",
        "MY-05",
        "MY-06",
        "MY-07",
        "MY-08",
        "MY-09",
        "MY-10",
        "MY-11",
        "MY-14",
        "MY-16",
    }
)


def condition_matches(
    condition: dict[str, object],
    facts: dict[str, object],
    datasets: dict[str, object],
) -> bool:
    if condition == {"always": True}:
        return True
    validate_rule_condition(condition)
    if "all" in condition:
        children = condition["all"]
        assert isinstance(children, list)
        return all(condition_matches(child, facts, datasets) for child in children)
    if "any" in condition:
        children = condition["any"]
        assert isinstance(children, list)
        return any(condition_matches(child, facts, datasets) for child in children)

    name = condition["fact"]
    operator = condition["operator"]
    expected = condition["value"]
    assert isinstance(name, str)
    actual = facts.get(name)
    if operator == "present":
        return actual is not None
    if operator == "absent":
        return actual is None
    if operator == "eq":
        return actual == expected
    if operator == "neq":
        return actual != expected
    if operator == "in":
        return isinstance(expected, list) and actual in expected
    if operator == "not_in":
        return isinstance(expected, list) and actual not in expected
    if operator == "dataset_contains":
        dataset = datasets.get(expected) if isinstance(expected, str) else None
        return isinstance(dataset, list) and actual in dataset
    if actual is None:
        return False
    if operator == "gte":
        return (
            isinstance(actual, (int, float))
            and isinstance(expected, (int, float))
            and actual >= expected
        )
    if operator == "lte":
        return (
            isinstance(actual, (int, float))
            and isinstance(expected, (int, float))
            and actual <= expected
        )
    raise ValueError("unsupported rule operator")


def build_snapshot(session: Session, case: ImmigrationCase, at: datetime) -> dict[str, object]:
    profile = session.get(StudentPassCaseProfile, case.id)
    if profile is None:
        raise ValueError("student pass profile is required for evaluation")
    documents = list(
        session.scalars(
            select(Document).where(
                Document.case_id == case.id, Document.status == DocumentStatus.ACTIVE
            )
        )
    )
    document_types = sorted({document.document_type.value for document in documents})
    expires = profile.passport_expires_at
    months = (expires.year - at.year) * 12 + expires.month - at.month
    if expires.day < at.day:
        months -= 1
    facts: dict[str, object] = {
        "application.type": profile.application_type.value.lower(),
        "institution.type": profile.institution_type.value,
        "applicant.location_at_submission": profile.applicant_location.value.lower(),
        "application.service_region": (
            "peninsular_malaysia"
            if profile.region_code.upper() in PENINSULAR_REGION_CODES
            else profile.region_code.lower()
        ),
        "applicant.nationality_code": profile.nationality_code,
        "passport.validity_months_at_submission": max(0, months),
        "travel.document_type": "ordinary_passport",
    }
    for document_type in document_types:
        facts[f"documents.{document_type.lower()}.present"] = True
    return {"facts": facts, "document_types": document_types, "captured_at": at.isoformat()}


def evaluate_case(
    session: Session,
    case: ImmigrationCase,
    release: RuleSetVersion,
    *,
    trigger: str,
    at: datetime,
    supersedes_evaluation_id: UUID | None = None,
) -> RuleEvaluation:
    snapshot = build_snapshot(session, case, at)
    facts = snapshot["facts"]
    assert isinstance(facts, dict)
    rules = list(
        session.scalars(
            select(RuleVersion)
            .where(RuleVersion.rule_set_version_id == release.id)
            .order_by(RuleVersion.priority, RuleVersion.id)
        )
    )
    outcome = release.default_outcome
    fired: list[RuleVersion] = []
    for rule in rules:
        if condition_matches(rule.condition_document, facts, release.dataset_snapshots):
            fired.append(rule)
            if OUTCOME_PRIORITY[rule.outcome] > OUTCOME_PRIORITY[outcome]:
                outcome = rule.outcome
    evaluation = RuleEvaluation(
        case_id=case.id,
        rule_set_version_id=release.id,
        trigger=trigger,
        input_snapshot=snapshot,
        outcome=outcome,
        evaluated_at=at,
        supersedes_evaluation_id=supersedes_evaluation_id,
        engine_version="student-pass-v1",
    )
    session.add(evaluation)
    session.flush()
    session.add_all(
        [
            EvaluationFinding(
                rule_evaluation_id=evaluation.id,
                rule_version_id=rule.id,
                outcome=rule.outcome,
                code=rule.finding_code,
                message=rule.message,
                details={
                    "task_type": rule.task_type,
                    "source_codes": rule.supplemental_source_codes,
                },
            )
            for rule in fired
        ]
    )
    return evaluation
