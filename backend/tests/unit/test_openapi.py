from app.main import app


def test_openapi_documents_all_implemented_endpoints_and_csv_upload() -> None:
    specification = app.openapi()
    paths = specification["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/ready" in paths
    upload = paths["/api/v1/ingestion/sales"]["post"]
    assert upload["requestBody"]["content"]["multipart/form-data"]
    assert {"Health", "Data Ingestion"}.issubset({tag["name"] for tag in specification["tags"]})
    assert {"413", "415", "422", "503"}.issubset(upload["responses"])


def test_builtin_documentation_routes_are_enabled() -> None:
    paths = {getattr(route, "path", None) for route in app.routes}
    assert {"/docs", "/openapi.json", "/redoc"}.issubset(paths)
