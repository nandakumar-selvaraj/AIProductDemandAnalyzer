"""Actual multipart endpoint bounds behind real JWT, role and CSRF middleware."""

from contextlib import contextmanager

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import ingestion
from app.db.session import get_db
from app.main import http_error_handler
from tests.unit import test_authentication as helpers
from tests.unit.test_authentication import ORIGIN, sign_in


@pytest.fixture
def upload_system(monkeypatch):
    with contextmanager(helpers.auth_system.__wrapped__)(monkeypatch) as (client, config, factory):
        probe = client.app
        catchall = probe.router.routes.pop()
        probe.include_router(ingestion.router, prefix="/api/v1")
        probe.router.routes.append(catchall)
        probe.add_exception_handler(HTTPException, http_error_handler)

        def database():
            with factory() as db:
                yield db

        probe.dependency_overrides[get_db] = database
        monkeypatch.setattr(ingestion, "get_settings", lambda: config)
        yield client, config


@pytest.mark.parametrize(
    ("content", "media_type", "limit", "status", "code"),
    [
        (b"wrong,schema\n1,2\n", "text/csv", 1024, 422, "invalid_csv"),
        (b"", "text/csv", 1024, 422, "invalid_csv"),
        (b"x" * 17, "text/csv", 16, 413, "file_too_large"),
        (b"date,store,item,sales\n", "application/pdf", 1024, 415, "unsupported_media_type"),
    ],
)
def test_admin_csv_validation(upload_system, content, media_type, limit, status, code):
    client, config = upload_system
    config.max_upload_bytes = limit
    session = sign_in(client, "admin").json()
    response = client.post(
        "/api/v1/ingestion/sales",
        files={"file": ("sales.csv", content, media_type)},
        headers={"Origin": ORIGIN, "X-CSRF-Token": session["csrf_token"]},
    )
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_anonymous_and_viewer_denied_before_parsing(upload_system):
    client, _ = upload_system
    assert client.post("/api/v1/ingestion/sales", content=b"invalid").status_code == 401
    session = sign_in(client, "viewer").json()
    assert client.get("/api/v1/ingestion/config").status_code == 403
    assert (
        client.post(
            "/api/v1/ingestion/sales",
            content=b"invalid",
            headers={"Origin": ORIGIN, "X-CSRF-Token": session["csrf_token"]},
        ).status_code
        == 403
    )


def test_upload_config_and_csrf_remain_enforced(upload_system):
    client, config = upload_system
    config.max_upload_bytes = 4096
    config.max_request_bytes = 2048
    sign_in(client, "admin")
    assert client.get("/api/v1/ingestion/config").json() == {"max_upload_bytes": 1024}
    assert (
        client.post(
            "/api/v1/ingestion/sales",
            files={"file": ("sales.csv", b"", "text/csv")},
            headers={"Origin": ORIGIN},
        ).status_code
        == 403
    )
