"""Tests for the Module 12.3 resource UI renderer."""

from dataclasses import dataclass, field

from app.schemas.resource import ResourceResponse
from app.ui import resources as resources_ui


@dataclass
class _FakeStreamlit:
    calls: list[tuple[str, str]] = field(default_factory=list)

    def subheader(self, value: str) -> None:
        self.calls.append(("subheader", value))

    def markdown(self, value: str) -> None:
        self.calls.append(("markdown", value))

    def info(self, value: str) -> None:
        self.calls.append(("info", value))


def _resource() -> ResourceResponse:
    return ResourceResponse(
        id=1,
        title="SQLBolt",
        url="https://sqlbolt.com/",
        resource_type="Learning resource",
        topic="SQL",
        difficulty="Beginner",
        source="SQLBolt",
        description="Interactive SQL lessons.",
    )


def test_render_resources_uses_recommendation_service_and_displays_required_fields(monkeypatch) -> None:
    fake_streamlit = _FakeStreamlit()
    captured: dict[str, str] = {}

    def fake_recommend_resources(topic: str, learner_level: str) -> list[ResourceResponse]:
        captured.update(topic=topic, learner_level=learner_level)
        return [_resource()]

    monkeypatch.setattr(resources_ui, "st", fake_streamlit)
    monkeypatch.setattr(resources_ui, "recommend_resources", fake_recommend_resources)

    resources_ui.render_resources("SQL", "Beginner")

    rendered = "\n".join(value for _, value in fake_streamlit.calls)
    assert captured == {"topic": "SQL", "learner_level": "Beginner"}
    assert "SQLBolt" in rendered
    assert "Type:" in rendered
    assert "Learning resource" in rendered
    assert "Difficulty:" in rendered
    assert "Beginner" in rendered
    assert "Description:" in rendered
    assert "Interactive SQL lessons." in rendered
    assert "Link:" in rendered
    assert "https://sqlbolt.com/" in rendered


def test_render_resources_shows_empty_state_when_no_resources_exist(monkeypatch) -> None:
    fake_streamlit = _FakeStreamlit()
    monkeypatch.setattr(resources_ui, "st", fake_streamlit)
    monkeypatch.setattr(resources_ui, "recommend_resources", lambda topic, learner_level: [])

    resources_ui.render_resources("Unknown topic", "Beginner")

    assert ("info", "No resources are available for this topic yet.") in fake_streamlit.calls
