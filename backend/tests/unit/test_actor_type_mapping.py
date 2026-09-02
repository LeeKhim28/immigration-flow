from sqlalchemy.dialects import postgresql

from app.database.enums import ActorType
from app.database.models import Actor


def test_actor_type_column_converts_database_text_to_enum() -> None:
    dialect = postgresql.dialect()
    actor_type = Actor.__table__.c.actor_type.type
    result_processor = actor_type.result_processor(
        dialect,
        None,
    )

    assert str(actor_type.compile(dialect=dialect)) == "TEXT"
    assert result_processor is not None
    assert result_processor("APPLICANT") is ActorType.APPLICANT
