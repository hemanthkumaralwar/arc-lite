from fastapi.testclient import TestClient

from app import config
from app.main import app

client = TestClient(app)  # no `with` block, so the startup database load does not run


def preflight(origin):
    return client.options(
        "/chat",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )


def test_configured_origin_is_allowed_to_call_the_api():
    origin = config.settings.cors_origin_list[0]
    response = preflight(origin)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin


def test_unknown_origin_gets_no_cors_header():
    response = preflight("https://evil.example")
    assert "access-control-allow-origin" not in response.headers


def test_wildcard_origin_is_never_returned():
    response = preflight("https://anything.example")
    assert response.headers.get("access-control-allow-origin") != "*"


def test_origin_list_parses_commas_spaces_and_blanks(monkeypatch):
    monkeypatch.setattr(config.settings, "cors_origins", " https://a.example , https://b.example ,, ")
    assert config.settings.cors_origin_list == ["https://a.example", "https://b.example"]
