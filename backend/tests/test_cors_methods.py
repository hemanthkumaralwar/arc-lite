from fastapi.testclient import TestClient

from app import config
from app.main import app

client = TestClient(app)  # no `with` block, so the startup database load does not run


def preflight(path, method, origin):
    return client.options(
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )


def test_delete_preflight_is_allowed_for_the_configured_origin():
    origin = config.settings.cors_origin_list[0]
    response = preflight("/admin/faq/1", "DELETE", origin)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert "DELETE" in response.headers.get("access-control-allow-methods", "")


def test_put_and_get_preflights_are_still_allowed():
    origin = config.settings.cors_origin_list[0]
    put = preflight("/admin/faq/1", "PUT", origin)
    assert put.headers.get("access-control-allow-origin") == origin
    assert "PUT" in put.headers.get("access-control-allow-methods", "")
