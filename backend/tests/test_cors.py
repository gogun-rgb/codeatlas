from __future__ import annotations

from fastapi.middleware.cors import CORSMiddleware

from app.main import allowed_origins, create_app


def _cors_allow_origins() -> list[str]:
    app = create_app()
    middleware = next(item for item in app.user_middleware if item.cls is CORSMiddleware)
    return list(middleware.kwargs["allow_origins"])


def test_localhost_cors_origins_remain_supported(monkeypatch) -> None:
    monkeypatch.delenv("CODEATLAS_ALLOWED_ORIGINS", raising=False)

    origins = allowed_origins()

    assert "http://localhost:5173" in origins
    assert "http://127.0.0.1:5173" in origins


def test_configured_deployment_origins_are_accepted(monkeypatch) -> None:
    monkeypatch.setenv(
        "CODEATLAS_ALLOWED_ORIGINS",
        "https://codeatlas.example.test, https://preview-codeatlas.example.test",
    )

    origins = allowed_origins()

    assert "https://codeatlas.example.test" in origins
    assert "https://preview-codeatlas.example.test" in origins


def test_empty_origin_entries_are_ignored_and_deduplicated(monkeypatch) -> None:
    monkeypatch.setenv(
        "CODEATLAS_ALLOWED_ORIGINS",
        "https://codeatlas.example.test, ,https://codeatlas.example.test,",
    )

    origins = allowed_origins()

    assert "" not in origins
    assert origins.count("https://codeatlas.example.test") == 1


def test_wildcard_cors_origin_is_not_introduced(monkeypatch) -> None:
    monkeypatch.setenv("CODEATLAS_ALLOWED_ORIGINS", "*, https://codeatlas.example.test")

    origins = _cors_allow_origins()

    assert "*" not in origins
    assert "https://codeatlas.example.test" in origins
