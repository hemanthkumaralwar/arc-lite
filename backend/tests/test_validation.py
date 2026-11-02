import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import install_error_handlers
from app.schemas import MAX_QUESTION_LENGTH, ChatRequest


def build_test_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.post("/validate")
    def validate(body: ChatRequest):
        return {"question": body.question}

    return app


client = TestClient(build_test_app())


def assert_bad_request(response):
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "invalid_request"
    assert isinstance(body["message"], str) and body["message"]


@pytest.mark.parametrize("question", ["", "   ", "\n\t  \r\n"])
def test_empty_or_whitespace_only_question_is_400(question):
    response = client.post("/validate", json={"question": question})
    assert_bad_request(response)
    assert "empty" in response.json()["message"].lower()


def test_question_over_500_characters_is_400():
    response = client.post("/validate", json={"question": "a" * (MAX_QUESTION_LENGTH + 1)})
    assert_bad_request(response)
    assert "500" in response.json()["message"]


def test_question_of_exactly_500_characters_is_accepted():
    question = "a" * MAX_QUESTION_LENGTH
    response = client.post("/validate", json={"question": question})
    assert response.status_code == 200
    assert response.json()["question"] == question


def test_surrounding_whitespace_is_trimmed():
    response = client.post("/validate", json={"question": "   how do I get my certificate?  \n"})
    assert response.status_code == 200
    assert response.json()["question"] == "how do I get my certificate?"


def test_length_is_checked_after_trimming():
    # 500 real characters plus padding is still valid once trimmed.
    question = "   " + ("a" * MAX_QUESTION_LENGTH) + "   "
    response = client.post("/validate", json={"question": question})
    assert response.status_code == 200


def test_missing_question_field_is_400():
    response = client.post("/validate", json={})
    assert_bad_request(response)
    assert "question" in response.json()["message"]


def test_non_string_question_is_400():
    response = client.post("/validate", json={"question": 12345})
    assert_bad_request(response)


def test_malformed_json_is_400_not_500():
    response = client.post(
        "/validate",
        content="{not valid json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400


def test_validation_never_returns_422():
    cases = [
        {"question": ""},
        {"question": "x" * 501},
        {},
        {"question": None},
    ]
    for body in cases:
        assert client.post("/validate", json=body).status_code != 422


def test_unknown_route_returns_404_json():
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "not_found"
    assert "message" in body
