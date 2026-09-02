from collections.abc import Iterator
from datetime import UTC, datetime
from typing import NamedTuple
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.exc import DBAPIError

EXPECTED_REVISION = "0004_events_audit_and_immutability"


class SeededRecords(NamedTuple):
    engine: Engine
    ids: dict[str, UUID]


@pytest.fixture
def seeded_records(test_database_url: str) -> Iterator[SeededRecords]:
    engine = create_engine(test_database_url)
    database_was_reached = False
    try:
        _truncate_event_test_data(engine)
        database_was_reached = True
        ids = _insert_valid_records(engine)
        yield SeededRecords(engine=engine, ids=ids)
    finally:
        try:
            if database_was_reached:
                _truncate_event_test_data(engine)
        finally:
            engine.dispose()


def _truncate_event_test_data(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                TRUNCATE TABLE
                    audit_event,
                    case_event,
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


def _insert_valid_records(engine: Engine) -> dict[str, UUID]:
    ids = {
        name: uuid4()
        for name in (
            "applicant_actor",
            "worker_actor",
            "applicant_profile",
            "institution",
            "programme",
            "case",
            "case_status_history",
            "append_only_document",
            "append_only_document_version",
            "checked_document",
            "checked_document_version",
            "document_check",
            "receipt_document",
            "receipt_document_version",
            "confirmed_initial",
            "draft_initial",
            "supplementary",
            "case_event",
            "audit_event",
        )
    }
    occurred_at = datetime(2026, 9, 1, 1, 2, 3, tzinfo=UTC)

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO actor (id, actor_type, display_name)
                VALUES
                    (:applicant_actor, 'APPLICANT', 'Append-only Applicant'),
                    (:worker_actor, 'INSTITUTION_WORKER', 'Append-only Worker')
                """
            ),
            ids,
        )
        connection.execute(
            text(
                """
                INSERT INTO applicant_profile (id, actor_id, synthetic_reference)
                VALUES (:applicant_profile, :applicant_actor, 'SYN-APPEND-ONLY')
                """
            ),
            ids,
        )
        connection.execute(
            text(
                """
                INSERT INTO institution
                    (id, institution_code, name, institution_type, region_code, active)
                VALUES
                    (:institution, 'INST-APPEND-ONLY', 'Append-only Institution',
                     'UA', 'MY-14', true)
                """
            ),
            ids,
        )
        connection.execute(
            text(
                """
                INSERT INTO programme
                    (id, institution_id, programme_code, name, level, active)
                VALUES
                    (:programme, :institution, 'PROG-APPEND-ONLY',
                     'Append-only Programme', 'BACHELOR', true)
                """
            ),
            ids,
        )
        connection.execute(
            text(
                """
                INSERT INTO "case"
                    (id, case_number, applicant_profile_id, service_type, status, stage,
                     created_by_actor_id)
                VALUES
                    (:case, 'CASE-APPEND-ONLY', :applicant_profile, 'STUDENT_PASS',
                     'DRAFT', 'PRE_SUBMISSION', :worker_actor)
                """
            ),
            ids,
        )
        connection.execute(
            text(
                """
                INSERT INTO student_pass_case_profile
                    (case_id, application_type, institution_id, programme_id,
                     institution_type, region_code, applicant_location,
                     nationality_code, passport_expires_at)
                VALUES
                    (:case, 'NEW', :institution, :programme, 'UA', 'MY-14',
                     'OUTSIDE_MALAYSIA', 'MY', '2030-01-01T00:00:00+00:00')
                """
            ),
            ids,
        )
        connection.execute(
            text(
                """
                INSERT INTO case_status_history
                    (id, case_id, from_status, to_status, reason_code,
                     changed_by_actor_id, changed_at)
                VALUES
                    (:case_status_history, :case, NULL, 'DRAFT', 'CASE_CREATED',
                     :worker_actor, :occurred_at)
                """
            ),
            {**ids, "occurred_at": occurred_at},
        )

        _insert_document_version(
            connection,
            ids,
            document_key="append_only_document",
            version_key="append_only_document_version",
            suffix="APPEND-ONLY",
            document_type="PASSPORT_BIODATA",
            occurred_at=occurred_at,
        )
        _insert_document_version(
            connection,
            ids,
            document_key="checked_document",
            version_key="checked_document_version",
            suffix="CHECKED",
            document_type="PASSPORT_BIODATA",
            occurred_at=occurred_at,
        )
        connection.execute(
            text(
                """
                INSERT INTO document_check
                    (id, document_version_id, check_type, result, details,
                     checked_by_actor_id, checked_at)
                VALUES
                    (:document_check, :checked_document_version, 'FILE_INTEGRITY', 'PASS',
                     CAST(:details AS jsonb), :worker_actor, :occurred_at)
                """
            ),
            {
                **ids,
                "details": '{"scanner": "synthetic"}',
                "occurred_at": occurred_at,
            },
        )
        _insert_document_version(
            connection,
            ids,
            document_key="receipt_document",
            version_key="receipt_document_version",
            suffix="RECEIPT",
            document_type="IMMIGRATION_RECEIPT",
            occurred_at=occurred_at,
        )
        connection.execute(
            text(
                """
                INSERT INTO case_submission
                    (id, case_id, submission_type, channel, submitted_by_actor_id,
                     accepted_at, immigration_reference, receipt_document_version_id,
                     confirmed_at)
                VALUES
                    (:confirmed_initial, :case, 'INITIAL', 'EMGS', :worker_actor,
                     :occurred_at, 'EMGS-CONFIRMED', :receipt_document_version, :occurred_at),
                    (:draft_initial, :case, 'INITIAL', 'EMGS', :worker_actor,
                     NULL, NULL, NULL, NULL),
                    (:supplementary, :case, 'SUPPLEMENTARY', 'EMGS', :worker_actor,
                     :occurred_at, 'EMGS-SUPPLEMENTARY', :receipt_document_version,
                     :occurred_at)
                """
            ),
            {**ids, "occurred_at": occurred_at},
        )
        connection.execute(
            text(
                """
                INSERT INTO case_event
                    (id, case_id, event_type, event_payload, occurred_at, actor_id)
                VALUES
                    (:case_event, :case, 'CASE_CREATED', CAST(:event_payload AS jsonb),
                     :occurred_at, NULL)
                """
            ),
            {
                **ids,
                "event_payload": '{"source": "synthetic"}',
                "occurred_at": occurred_at,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO audit_event
                    (id, case_id, actor_id, action, entity_type, entity_id,
                     before_summary, after_summary, occurred_at)
                VALUES
                    (:audit_event, :case, NULL, 'CREATE', 'case', :case,
                     NULL, CAST(:after_summary AS jsonb), :occurred_at)
                """
            ),
            {
                **ids,
                "after_summary": '{"status": "DRAFT"}',
                "occurred_at": occurred_at,
            },
        )

    return ids


def _insert_document_version(
    connection: Connection,
    ids: dict[str, UUID],
    *,
    document_key: str,
    version_key: str,
    suffix: str,
    document_type: str,
    occurred_at: datetime,
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO document (id, case_id, document_type, owner_actor_id, status)
            VALUES (:document_id, :case, :document_type, :worker_actor, 'ACTIVE')
            """
        ),
        {
            **ids,
            "document_id": ids[document_key],
            "document_type": document_type,
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO document_version
                (id, document_id, version_number, storage_reference, content_hash,
                 mime_type, size_bytes, captured_at, created_by_actor_id)
            VALUES
                (:version_id, :document_id, 1, :storage_reference, :content_hash,
                 'application/pdf', 1024, :occurred_at, :worker_actor)
            """
        ),
        {
            **ids,
            "document_id": ids[document_key],
            "version_id": ids[version_key],
            "storage_reference": f"metadata-only://document/{suffix}",
            "content_hash": f"sha256:{suffix.lower()}",
            "occurred_at": occurred_at,
        },
    )


def test_alembic_version_column_holds_current_descriptive_revision(
    test_database_url: str,
) -> None:
    engine = create_engine(test_database_url)
    try:
        with engine.connect() as connection:
            version_num = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            column_width = connection.execute(
                text(
                    """
                    SELECT character_maximum_length
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'alembic_version'
                      AND column_name = 'version_num'
                    """
                )
            ).scalar_one()
    finally:
        engine.dispose()

    assert column_width == 64
    assert version_num == EXPECTED_REVISION


APPEND_ONLY_UPDATES = [
    (
        "append_only_document_version",
        "UPDATE document_version SET storage_reference = 'metadata-only://mutated' WHERE id = :id",
    ),
    (
        "document_check",
        "UPDATE document_check SET check_type = 'MUTATED' WHERE id = :id",
    ),
    (
        "case_status_history",
        "UPDATE case_status_history SET reason_code = 'MUTATED' WHERE id = :id",
    ),
    (
        "case_event",
        "UPDATE case_event SET event_type = 'MUTATED' WHERE id = :id",
    ),
    (
        "audit_event",
        "UPDATE audit_event SET action = 'MUTATED' WHERE id = :id",
    ),
]


@pytest.mark.parametrize(("record_key", "statement"), APPEND_ONLY_UPDATES)
def test_append_only_table_rejects_update(
    seeded_records: SeededRecords,
    record_key: str,
    statement: str,
) -> None:
    with seeded_records.engine.connect() as connection:
        savepoint = connection.begin_nested()
        with pytest.raises(DBAPIError, match="append-only"):
            connection.execute(text(statement), {"id": seeded_records.ids[record_key]})
        savepoint.rollback()


@pytest.mark.parametrize(
    ("record_key", "table_name"),
    [
        ("append_only_document_version", "document_version"),
        ("document_check", "document_check"),
        ("case_status_history", "case_status_history"),
        ("case_event", "case_event"),
        ("audit_event", "audit_event"),
    ],
)
def test_append_only_table_rejects_delete(
    seeded_records: SeededRecords,
    record_key: str,
    table_name: str,
) -> None:
    statement = text(f"DELETE FROM {table_name} WHERE id = :id")
    with seeded_records.engine.connect() as connection:
        savepoint = connection.begin_nested()
        with pytest.raises(DBAPIError, match="append-only"):
            connection.execute(statement, {"id": seeded_records.ids[record_key]})
        savepoint.rollback()


def test_confirmed_initial_submission_rejects_update(seeded_records: SeededRecords) -> None:
    with seeded_records.engine.connect() as connection:
        savepoint = connection.begin_nested()
        with pytest.raises(DBAPIError, match="confirmed initial submission is immutable"):
            connection.execute(
                text(
                    """
                    UPDATE case_submission
                    SET channel = 'ONLINE_PORTAL'
                    WHERE id = :id
                    """
                ),
                {"id": seeded_records.ids["confirmed_initial"]},
            )
        savepoint.rollback()


def test_confirmed_initial_submission_rejects_delete(seeded_records: SeededRecords) -> None:
    with seeded_records.engine.connect() as connection:
        savepoint = connection.begin_nested()
        with pytest.raises(DBAPIError, match="confirmed initial submission is immutable"):
            connection.execute(
                text("DELETE FROM case_submission WHERE id = :id"),
                {"id": seeded_records.ids["confirmed_initial"]},
            )
        savepoint.rollback()


@pytest.mark.parametrize("record_key", ["draft_initial", "supplementary"])
def test_mutable_submission_may_be_updated(
    seeded_records: SeededRecords,
    record_key: str,
) -> None:
    with seeded_records.engine.begin() as connection:
        result = connection.execute(
            text(
                """
                UPDATE case_submission
                SET channel = 'ONLINE_PORTAL'
                WHERE id = :id
                """
            ),
            {"id": seeded_records.ids[record_key]},
        )
        stored_channel = connection.execute(
            text("SELECT channel FROM case_submission WHERE id = :id"),
            {"id": seeded_records.ids[record_key]},
        ).scalar_one()

    assert result.rowcount == 1
    assert stored_channel == "ONLINE_PORTAL"


@pytest.mark.parametrize("record_key", ["draft_initial", "supplementary"])
def test_mutable_submission_may_be_deleted(
    seeded_records: SeededRecords,
    record_key: str,
) -> None:
    with seeded_records.engine.begin() as connection:
        result = connection.execute(
            text("DELETE FROM case_submission WHERE id = :id"),
            {"id": seeded_records.ids[record_key]},
        )
        remaining_count = connection.execute(
            text("SELECT count(*) FROM case_submission WHERE id = :id"),
            {"id": seeded_records.ids[record_key]},
        ).scalar_one()

    assert result.rowcount == 1
    assert remaining_count == 0


def test_event_payloads_and_timestamps_round_trip(seeded_records: SeededRecords) -> None:
    with seeded_records.engine.connect() as connection:
        case_event = connection.execute(
            text(
                """
                SELECT event_payload, occurred_at, recorded_at
                FROM case_event
                WHERE id = :id
                """
            ),
            {"id": seeded_records.ids["case_event"]},
        ).one()
        audit_event = connection.execute(
            text(
                """
                SELECT before_summary, after_summary, occurred_at
                FROM audit_event
                WHERE id = :id
                """
            ),
            {"id": seeded_records.ids["audit_event"]},
        ).one()

    assert case_event.event_payload == {"source": "synthetic"}
    assert case_event.occurred_at.tzinfo is not None
    assert case_event.recorded_at.tzinfo is not None
    assert audit_event.before_summary is None
    assert audit_event.after_summary == {"status": "DRAFT"}
    assert audit_event.occurred_at.tzinfo is not None
