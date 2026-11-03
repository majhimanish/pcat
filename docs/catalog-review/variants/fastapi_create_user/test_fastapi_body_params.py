import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import fastapi_body_params as mod  # noqa: E402

GOOD = {"username": "ada_l", "email": "Ada@Example.com", "password": "correct horse battery"}


@pytest.fixture
def client_and_store():
    store = []

    def save(user):
        if any(u["username"] == user["username"] or u["email"] == user["email"] for u in store):
            return None
        record = {"id": len(store) + 1, **user}
        store.append(record)
        return record

    app = FastAPI()
    mod.register_routes(app)
    app.dependency_overrides[mod.get_create_user] = lambda: save
    app.dependency_overrides[mod.get_password_hasher] = lambda: (lambda pw: "hashed:" + pw[::-1])
    return TestClient(app), store


def test_creates_user_and_hides_password(client_and_store):
    client, store = client_and_store
    response = client.post("/users", json=GOOD)
    assert response.status_code == 201
    assert response.json() == {"id": 1, "username": "ada_l", "email": "ada@example.com"}
    assert store[0]["password_hash"].startswith("hashed:") and "password" not in store[0]
    assert "battery" not in response.text


def test_duplicate_is_409(client_and_store):
    client, _ = client_and_store
    client.post("/users", json=GOOD)
    response = client.post("/users", json={**GOOD, "username": "other"})
    assert response.status_code == 409


@pytest.mark.parametrize("field,value", [
    ("username", "ab"), ("username", "bad name!"), ("email", "nope"), ("email", "a@b"),
    ("email", "a@" + "b" * 300 + ".com"), ("password", "short"), ("password", "x" * 129)])
def test_invalid_input_is_422_and_nothing_stored(client_and_store, field, value):
    client, store = client_and_store
    response = client.post("/users", json={**GOOD, field: value})
    assert response.status_code == 422 and store == []


def test_missing_field_is_422(client_and_store):
    client, _ = client_and_store
    assert client.post("/users", json={"username": "ada_l"}).status_code == 422


def test_unwired_dependencies_fail_closed():
    app = FastAPI()
    mod.register_routes(app)
    with pytest.raises(NotImplementedError):
        TestClient(app).post("/users", json=GOOD)


def test_openapi_documents_the_fields():
    app = FastAPI()
    mod.register_routes(app)
    schema = app.openapi()
    body = schema["paths"]["/users"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    props = schema["components"]["schemas"][body["$ref"].split("/")[-1]]["properties"]
    assert set(props) == {"username", "email", "password"}
