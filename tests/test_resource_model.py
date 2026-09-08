"""Tests for the Module 12.1 resource model and schemas."""

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.database.base import Base
from app.database.models import Resource
from app.schemas.resource import ResourceCreate, ResourceResponse


def _resource_values() -> dict[str, str]:
    return {
        "title": "SQL Window Functions",
        "url": "https://example.com/sql-window-functions",
        "resource_type": "article",
        "topic": "SQL",
        "difficulty": "Intermediate",
        "source": "Example",
        "description": "A practical guide to SQL window functions.",
    }


def test_resource_model_defines_expected_columns() -> None:
    columns = {column.name for column in inspect(Resource).columns}

    assert columns == {
        "id",
        "title",
        "url",
        "resource_type",
        "topic",
        "difficulty",
        "source",
        "description",
    }


def test_resource_can_be_persisted() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Resource.__table__])

    with Session(engine) as session:
        resource = Resource(**_resource_values())
        session.add(resource)
        session.commit()
        session.refresh(resource)

        assert resource.id == 1
        assert resource.title == "SQL Window Functions"


def test_resource_schemas_validate_create_payload_and_serialize_model() -> None:
    payload = ResourceCreate(**_resource_values())
    assert payload.model_dump() == _resource_values()

    resource = Resource(id=7, **payload.model_dump())
    response = ResourceResponse.model_validate(resource)

    assert response.id == 7
    assert response.title == payload.title


def test_resource_schema_rejects_blank_required_fields() -> None:
    values = _resource_values()
    values["title"] = ""

    try:
        ResourceCreate(**values)
    except ValueError as error:
        assert "title" in str(error)
    else:
        raise AssertionError("Blank resource titles must be rejected.")
