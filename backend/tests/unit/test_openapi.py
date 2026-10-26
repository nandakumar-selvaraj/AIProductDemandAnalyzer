from fastapi.testclient import TestClient

from app.main import app


def test_openapi_documents_all_implemented_endpoints_and_csv_upload() -> None:
    specification = app.openapi()
    paths = specification["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/ready" in paths
    assert "post" in paths["/api/v1/forecasts"]
    assert "get" in paths["/api/v1/forecasts/{run_id}/predictions"]
    assert "post" in paths["/api/v1/forecasts/evaluate"]
    assert "get" in paths["/api/v1/recommendations"]
    assert "get" in paths["/api/v1/products"]
    assert "get" in paths["/api/v1/stores"]
    assert "get" in paths["/api/v1/forecasts/latest"]
    assert "get" in paths["/api/v1/forecasts/runs"]
    assert "post" in paths["/api/v1/forecasts/backtest"]
    assert "get" in paths["/api/v1/products/{product_id}/analytics"]
    assert "get" in paths["/api/v1/dashboard/summary"]
    assert "post" in paths["/api/v1/assistant/chat"]
    assert "get" in paths["/api/v1/assistant/ready"]
    upload = paths["/api/v1/ingestion/sales"]["post"]
    assert upload["requestBody"]["content"]["multipart/form-data"]
    assert {"Health", "Data Ingestion", "Sales", "Forecasts"}.issubset(
        {tag["name"] for tag in specification["tags"]}
    )
    assert {"413", "415", "422", "503"}.issubset(upload["responses"])


def test_builtin_documentation_routes_are_enabled() -> None:
    paths = {getattr(route, "path", None) for route in app.routes}
    assert {"/docs", "/openapi.json", "/redoc"}.issubset(paths)


def test_root_redirects_to_swagger_docs() -> None:
    response = TestClient(app).get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/docs"
