"""Focused tests for Streamlit page wiring."""

from __future__ import annotations

import ast
import re
from pathlib import Path


STREAMLIT_APP = Path(__file__).parents[1] / "app" / "ui" / "streamlit_app.py"


def test_roadmap_page_selects_gemini_client() -> None:
    tree = ast.parse(STREAMLIT_APP.read_text())

    imported_clients = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "app.services.llm_client"
        for alias in node.names
    }
    roadmap_function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "roadmap_page"
    )
    constructors = {
        node.func.id
        for node in ast.walk(roadmap_function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert imported_clients == {"GeminiRoadmapLLMClient"}
    assert "GeminiRoadmapLLMClient" in constructors
    assert "OpenAIRoadmapLLMClient" not in constructors


def test_roadmap_diagnostic_includes_type_and_redacts_sensitive_values() -> None:
    tree = ast.parse(STREAMLIT_APP.read_text())
    diagnostic_function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_roadmap_generation_diagnostic"
    )
    namespace: dict[str, object] = {"re": re}
    exec(compile(ast.Module(body=[diagnostic_function], type_ignores=[]), str(STREAMLIT_APP), "exec"), namespace)

    diagnostic = namespace["_roadmap_generation_diagnostic"](
        RuntimeError(
            "request failed: GEMINI_API_KEY=gemini-secret "
            "Authorization: Bearer bearer-secret token=token-secret"
        )
    )

    assert diagnostic.startswith("RuntimeError: ")
    assert "gemini-secret" not in diagnostic
    assert "bearer-secret" not in diagnostic
    assert "token-secret" not in diagnostic
    assert "[REDACTED" in diagnostic


def test_roadmap_failure_message_includes_validation_errors_and_has_fallback() -> None:
    tree = ast.parse(STREAMLIT_APP.read_text())
    message_function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_roadmap_failure_message"
    )
    namespace: dict[str, object] = {}
    exec(compile(ast.Module(body=[message_function], type_ignores=[]), str(STREAMLIT_APP), "exec"), namespace)

    format_message = namespace["_roadmap_failure_message"]
    message = format_message("Generated roadmap failed validation.", ("Roadmap exceeds timeline.", "Missing PySpark phase."))
    fallback = format_message(None, ())

    assert "Validation errors:" in message
    assert "Roadmap exceeds timeline." in message
    assert "Missing PySpark phase." in message
    assert fallback == "Generated roadmap failed validation."
