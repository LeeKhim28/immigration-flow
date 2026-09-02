from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.enums import (
    ActorType,
    ApplicantLocation,
    ApplicationType,
    CaseStage,
    CaseStatus,
    DocumentCheckResult,
    DocumentStatus,
    DocumentType,
    InstitutionType,
    ServiceType,
    SubmissionChannel,
    SubmissionType,
)
from app.database.models import (
    Actor,
    ApplicantProfile,
    CaseSubmission,
    Document,
    DocumentCheck,
    DocumentVersion,
    ImmigrationCase,
    Institution,
    Programme,
    StudentPassCaseProfile,
    SubmissionDocument,
)


@pytest.fixture
def session(test_database_url: str) -> Iterator[Session]:
    engine: Engine = create_engine(test_database_url)
    _truncate_submission_test_data(engine)
    database_session = Session(engine)
    try:
        yield database_session
    finally:
        database_session.rollback()
        database_session.close()
        _truncate_submission_test_data(engine)
        engine.dispose()


def _truncate_submission_test_data(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                TRUNCATE TABLE
                    document_check,
                    submission_document,
                    case_submission,
                    document_version,
                    document,
                    case_status_history,
                    student_pass_case_profile,
                    "case",
                    programme,
                    institution,
                    applicant_profile,
                    actor
                CASCADE
                """
            )
        )


def _persist_case(session: Session, suffix: str) -> tuple[ImmigrationCase, Actor]:
    applicant = Actor(
        actor_type=ActorType.APPLICANT,
        display_name=f"Applicant {suffix}",
    )
    worker = Actor(
        actor_type=ActorType.INSTITUTION_WORKER,
        display_name=f"Worker {suffix}",
    )
    institution = Institution(
        institution_code=f"INST-{suffix}",
        name=f"Institution {suffix}",
        institution_type="UA",
        region_code="MY-14",
        active=True,
    )
    session.add_all([applicant, worker, institution])
    session.flush()

    applicant_profile = ApplicantProfile(
        actor_id=applicant.id,
        synthetic_reference=f"SYN-{suffix}",
    )
    programme = Programme(
        institution_id=institution.id,
        programme_code=f"PROG-{suffix}",
        name=f"Programme {suffix}",
        level="BACHELOR",
        active=True,
    )
    session.add_all([applicant_profile, programme])
    session.flush()

    case = ImmigrationCase(
        case_number=f"CASE-{suffix}",
        applicant_profile_id=applicant_profile.id,
        service_type=ServiceType.STUDENT_PASS,
        status=CaseStatus.DRAFT,
        stage=CaseStage.PRE_SUBMISSION,
        created_by_actor_id=worker.id,
    )
    session.add(case)
    session.flush()
    session.add(
        StudentPassCaseProfile(
            case_id=case.id,
            application_type=ApplicationType.NEW,
            institution_id=institution.id,
            programme_id=programme.id,
            institution_type=InstitutionType.UA,
            region_code="MY-14",
            applicant_location=ApplicantLocation.OUTSIDE_MALAYSIA,
            nationality_code="MY",
            passport_expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        )
    )
    session.commit()
    return case, worker


def _document(
    case: ImmigrationCase,
    owner: Actor,
    suffix: str,
    **overrides: object,
) -> Document:
    values: dict[str, object] = {
        "case_id": case.id,
        "document_type": DocumentType.PASSPORT_BIODATA,
        "owner_actor_id": owner.id,
        "status": DocumentStatus.DRAFT,
    }
    values.update(overrides)
    return Document(**values)


def _document_version(
    document: Document,
    creator: Actor,
    suffix: str,
    **overrides: object,
) -> DocumentVersion:
    values: dict[str, object] = {
        "document_id": document.id,
        "version_number": 1,
        "storage_reference": f"metadata-only://document/{suffix}",
        "content_hash": f"sha256:{suffix.lower()}",
        "mime_type": "application/pdf",
        "size_bytes": 1024,
        "captured_at": datetime(2026, 8, 31, 12, 0, tzinfo=UTC),
        "created_by_actor_id": creator.id,
    }
    values.update(overrides)
    return DocumentVersion(**values)


def _persist_document_version(
    session: Session,
    case: ImmigrationCase,
    owner: Actor,
    suffix: str,
    *,
    document_type: DocumentType = DocumentType.PASSPORT_BIODATA,
) -> DocumentVersion:
    document = _document(
        case,
        owner,
        suffix,
        document_type=document_type,
        status=DocumentStatus.ACTIVE,
    )
    session.add(document)
    session.flush()
    version = _document_version(document, owner, suffix)
    session.add(version)
    session.flush()
    return version


def _submission(
    case: ImmigrationCase,
    submitter: Actor,
    **overrides: object,
) -> CaseSubmission:
    values: dict[str, object] = {
        "case_id": case.id,
        "submission_type": SubmissionType.INITIAL,
        "channel": SubmissionChannel.EMGS,
        "submitted_by_actor_id": submitter.id,
    }
    values.update(overrides)
    return CaseSubmission(**values)


def test_valid_draft_document_version_and_check_round_trip(session: Session) -> None:
    case, worker = _persist_case(session, "VALID-DRAFT")
    document = _document(case, worker, "VALID-DRAFT")
    session.add(document)
    session.flush()
    version = _document_version(document, worker, "VALID-DRAFT", size_bytes=0)
    session.add(version)
    session.flush()
    check = DocumentCheck(
        document_version_id=version.id,
        check_type="FILE_INTEGRITY",
        result=DocumentCheckResult.PASS,
        details={"scanner": "synthetic", "score": 1},
        checked_by_actor_id=worker.id,
        checked_at=datetime(2026, 8, 31, 12, 5, tzinfo=UTC),
    )
    session.add(check)
    session.commit()
    session.expire_all()

    assert isinstance(document.id, UUID)
    assert document.document_type is DocumentType.PASSPORT_BIODATA
    assert document.status is DocumentStatus.DRAFT
    assert document.created_at.tzinfo is not None
    assert document.updated_at.tzinfo is not None
    assert version.version_number == 1
    assert version.size_bytes == 0
    assert version.captured_at.tzinfo is not None
    assert check.result is DocumentCheckResult.PASS
    assert check.details == {"scanner": "synthetic", "score": 1}
    assert check.checked_at.tzinfo is not None


def test_valid_confirmed_submission_links_exact_receipt_version(session: Session) -> None:
    case, worker = _persist_case(session, "VALID-CONFIRMED")
    receipt = _persist_document_version(
        session,
        case,
        worker,
        "VALID-CONFIRMED-RECEIPT",
        document_type=DocumentType.IMMIGRATION_RECEIPT,
    )
    passport = _persist_document_version(
        session,
        case,
        worker,
        "VALID-CONFIRMED-PASSPORT",
    )
    accepted_at = datetime(2026, 8, 31, 13, 0, tzinfo=UTC)
    submission = _submission(
        case,
        worker,
        accepted_at=accepted_at,
        immigration_reference="EMGS-SYNTHETIC-001",
        receipt_document_version_id=receipt.id,
        confirmed_at=accepted_at,
    )
    session.add(submission)
    session.flush()
    link = SubmissionDocument(
        submission_id=submission.id,
        document_version_id=passport.id,
        purpose="IDENTITY_EVIDENCE",
    )
    session.add(link)
    session.commit()
    session.expire_all()

    assert submission.submission_type is SubmissionType.INITIAL
    assert submission.channel is SubmissionChannel.EMGS
    assert submission.accepted_at == accepted_at
    assert submission.confirmed_at == accepted_at
    assert submission.receipt_document_version_id == receipt.id
    assert link.included_at.tzinfo is not None


def test_duplicate_document_version_number_is_rejected(session: Session) -> None:
    case, worker = _persist_case(session, "DUP-VERSION")
    document = _document(case, worker, "DUP-VERSION")
    session.add(document)
    session.flush()
    session.add_all(
        [
            _document_version(document, worker, "DUP-VERSION-A"),
            _document_version(document, worker, "DUP-VERSION-B"),
        ]
    )

    with pytest.raises(IntegrityError):
        session.flush()


def test_duplicate_submission_document_purpose_link_is_rejected(session: Session) -> None:
    case, worker = _persist_case(session, "DUP-LINK")
    version = _persist_document_version(session, case, worker, "DUP-LINK")
    submission = _submission(case, worker)
    session.add(submission)
    session.flush()
    session.add_all(
        [
            SubmissionDocument(
                submission_id=submission.id,
                document_version_id=version.id,
                purpose="IDENTITY_EVIDENCE",
            ),
            SubmissionDocument(
                submission_id=submission.id,
                document_version_id=version.id,
                purpose="IDENTITY_EVIDENCE",
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize(
    ("model_name", "field", "invalid_value"),
    [
        ("document_type", "document_type", "BANK_STATEMENT"),
        ("document_status", "status", "DELETED"),
        ("submission_type", "submission_type", "RENEWAL"),
        ("submission_channel", "channel", "EMAIL"),
        ("document_check_result", "result", "UNKNOWN"),
    ],
)
def test_unknown_persisted_enum_values_are_rejected(
    session: Session,
    model_name: str,
    field: str,
    invalid_value: str,
) -> None:
    case, worker = _persist_case(session, f"BAD-ENUM-{model_name}")

    if model_name.startswith("document_") and model_name != "document_check_result":
        invalid_record = _document(
            case,
            worker,
            f"BAD-ENUM-{model_name}",
            **{field: invalid_value},
        )
    elif model_name.startswith("submission_"):
        invalid_record = _submission(case, worker, **{field: invalid_value})
    else:
        version = _persist_document_version(
            session,
            case,
            worker,
            f"BAD-ENUM-{model_name}",
        )
        invalid_record = DocumentCheck(
            document_version_id=version.id,
            check_type="FILE_INTEGRITY",
            result=invalid_value,
            details=None,
            checked_by_actor_id=worker.id,
            checked_at=datetime(2026, 8, 31, 12, 5, tzinfo=UTC),
        )
    session.add(invalid_record)

    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [("version_number", 0), ("size_bytes", -1)],
)
def test_document_version_rejects_invalid_nonnegative_boundaries(
    session: Session,
    field: str,
    invalid_value: int,
) -> None:
    case, worker = _persist_case(session, f"BAD-BOUNDARY-{field}")
    document = _document(case, worker, f"BAD-BOUNDARY-{field}")
    session.add(document)
    session.flush()
    session.add(
        _document_version(
            document,
            worker,
            f"BAD-BOUNDARY-{field}",
            **{field: invalid_value},
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


def test_two_confirmed_initial_submissions_for_one_case_are_rejected(
    session: Session,
) -> None:
    case, worker = _persist_case(session, "TWO-INITIAL")
    first_receipt = _persist_document_version(
        session,
        case,
        worker,
        "TWO-INITIAL-A",
        document_type=DocumentType.IMMIGRATION_RECEIPT,
    )
    second_receipt = _persist_document_version(
        session,
        case,
        worker,
        "TWO-INITIAL-B",
        document_type=DocumentType.IMMIGRATION_RECEIPT,
    )
    accepted_at = datetime(2026, 8, 31, 13, 0, tzinfo=UTC)
    session.add_all(
        [
            _submission(
                case,
                worker,
                accepted_at=accepted_at,
                immigration_reference="EMGS-SYNTHETIC-A",
                receipt_document_version_id=first_receipt.id,
                confirmed_at=accepted_at,
            ),
            _submission(
                case,
                worker,
                accepted_at=accepted_at,
                immigration_reference="EMGS-SYNTHETIC-B",
                receipt_document_version_id=second_receipt.id,
                confirmed_at=accepted_at,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        session.flush()


# Mutation caught: removing `confirmed_at IS NOT NULL` from the partial-index predicate.
def test_multiple_unconfirmed_initial_submissions_for_one_case_can_commit(
    session: Session,
) -> None:
    case, worker = _persist_case(session, "MULTIPLE-DRAFT-INITIAL")
    first = _submission(case, worker)
    second = _submission(case, worker)
    session.add_all([first, second])
    session.commit()
    session.expire_all()

    assert first.submission_type is SubmissionType.INITIAL
    assert first.confirmed_at is None
    assert second.submission_type is SubmissionType.INITIAL
    assert second.confirmed_at is None


# Mutation caught: removing `submission_type = 'INITIAL'` from the partial-index predicate.
def test_multiple_confirmed_supplementary_submissions_for_one_case_can_commit(
    session: Session,
) -> None:
    case, worker = _persist_case(session, "MULTIPLE-CONFIRMED-SUPPLEMENTARY")
    first_receipt = _persist_document_version(
        session,
        case,
        worker,
        "SUPPLEMENTARY-RECEIPT-A",
        document_type=DocumentType.IMMIGRATION_RECEIPT,
    )
    second_receipt = _persist_document_version(
        session,
        case,
        worker,
        "SUPPLEMENTARY-RECEIPT-B",
        document_type=DocumentType.IMMIGRATION_RECEIPT,
    )
    accepted_at = datetime(2026, 8, 31, 14, 0, tzinfo=UTC)
    first = _submission(
        case,
        worker,
        submission_type=SubmissionType.SUPPLEMENTARY,
        accepted_at=accepted_at,
        immigration_reference="EMGS-SYNTHETIC-SUPPLEMENTARY-A",
        receipt_document_version_id=first_receipt.id,
        confirmed_at=accepted_at,
    )
    second = _submission(
        case,
        worker,
        submission_type=SubmissionType.SUPPLEMENTARY,
        accepted_at=accepted_at,
        immigration_reference="EMGS-SYNTHETIC-SUPPLEMENTARY-B",
        receipt_document_version_id=second_receipt.id,
        confirmed_at=accepted_at,
    )
    session.add_all([first, second])
    session.commit()
    session.expire_all()

    assert first.submission_type is SubmissionType.SUPPLEMENTARY
    assert first.confirmed_at == accepted_at
    assert second.submission_type is SubmissionType.SUPPLEMENTARY
    assert second.confirmed_at == accepted_at


@pytest.mark.parametrize("immigration_reference", [None, "", "   "])
def test_accepted_submission_requires_nonblank_reference(
    session: Session,
    immigration_reference: str | None,
) -> None:
    case, worker = _persist_case(session, f"NO-REF-{immigration_reference!r}")
    receipt = _persist_document_version(
        session,
        case,
        worker,
        f"NO-REF-{immigration_reference!r}",
        document_type=DocumentType.IMMIGRATION_RECEIPT,
    )
    session.add(
        _submission(
            case,
            worker,
            accepted_at=datetime(2026, 8, 31, 13, 0, tzinfo=UTC),
            immigration_reference=immigration_reference,
            receipt_document_version_id=receipt.id,
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


def test_accepted_submission_requires_receipt_evidence(session: Session) -> None:
    case, worker = _persist_case(session, "NO-RECEIPT")
    session.add(
        _submission(
            case,
            worker,
            accepted_at=datetime(2026, 8, 31, 13, 0, tzinfo=UTC),
            immigration_reference="EMGS-SYNTHETIC-NO-RECEIPT",
            receipt_document_version_id=None,
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


def test_confirmed_submission_requires_accepted_at(session: Session) -> None:
    case, worker = _persist_case(session, "CONFIRMED-NOT-ACCEPTED")
    session.add(
        _submission(
            case,
            worker,
            confirmed_at=datetime(2026, 8, 31, 13, 0, tzinfo=UTC),
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


# Mutation caught: making receipt evidence mandatory even while a submission is a draft.
def test_draft_submission_with_null_receipt_and_acceptance_fields_can_commit(
    session: Session,
) -> None:
    case, worker = _persist_case(session, "NULL-DRAFT-EVIDENCE")
    submission = _submission(case, worker)
    session.add(submission)
    session.commit()
    session.expire_all()

    assert submission.accepted_at is None
    assert submission.immigration_reference is None
    assert submission.receipt_document_version_id is None
    assert submission.confirmed_at is None


# Mutation caught: removing the receipt-document-version foreign key.
def test_nonexistent_receipt_document_version_is_rejected(session: Session) -> None:
    case, worker = _persist_case(session, "MISSING-RECEIPT-VERSION")
    session.add(
        _submission(
            case,
            worker,
            accepted_at=datetime(2026, 8, 31, 15, 0, tzinfo=UTC),
            immigration_reference="EMGS-SYNTHETIC-MISSING-RECEIPT",
            receipt_document_version_id=uuid4(),
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


# Mutation caught: making the same-case receipt constraint trigger immediate.
def test_receipt_case_may_be_repaired_after_flush_before_deferred_commit(
    session: Session,
) -> None:
    submission_case, submitter = _persist_case(session, "DEFERRED-REPAIR-A")
    receipt_case, receipt_owner = _persist_case(session, "DEFERRED-REPAIR-B")
    receipt = _persist_document_version(
        session,
        receipt_case,
        receipt_owner,
        "DEFERRED-REPAIR-RECEIPT",
        document_type=DocumentType.IMMIGRATION_RECEIPT,
    )
    accepted_at = datetime(2026, 8, 31, 16, 0, tzinfo=UTC)
    submission = _submission(
        submission_case,
        submitter,
        accepted_at=accepted_at,
        immigration_reference="EMGS-SYNTHETIC-DEFERRED-REPAIR",
        receipt_document_version_id=receipt.id,
        confirmed_at=accepted_at,
    )
    session.add(submission)

    session.flush()

    receipt_document = session.get(Document, receipt.document_id)
    assert receipt_document is not None
    receipt_document.case_id = submission_case.id
    session.commit()
    session.expire_all()

    assert receipt_document.case_id == submission_case.id
    assert submission.receipt_document_version_id == receipt.id


def test_receipt_document_version_must_belong_to_submission_case(
    session: Session,
) -> None:
    submission_case, submitter = _persist_case(session, "RECEIPT-CASE-A")
    receipt_case, receipt_owner = _persist_case(session, "RECEIPT-CASE-B")
    foreign_receipt = _persist_document_version(
        session,
        receipt_case,
        receipt_owner,
        "FOREIGN-RECEIPT",
        document_type=DocumentType.IMMIGRATION_RECEIPT,
    )
    accepted_at = datetime(2026, 8, 31, 13, 0, tzinfo=UTC)
    session.add(
        _submission(
            submission_case,
            submitter,
            accepted_at=accepted_at,
            immigration_reference="EMGS-SYNTHETIC-FOREIGN",
            receipt_document_version_id=foreign_receipt.id,
            confirmed_at=accepted_at,
        )
    )

    with pytest.raises(
        IntegrityError,
        match="receipt document version must belong to submission case",
    ):
        session.commit()
