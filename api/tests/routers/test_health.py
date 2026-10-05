# api/tests/routers/test_health.py
#
# Tests for the health endpoint.
#
# Tested:
# - Returns status 200 with an ok status body
#
# What is covered:
# - Success response (the endpoint documents no failures)
#
# Run with: cd api && .venv/bin/python -m pytest tests/routers/test_health.py
#
# SEE: api/app/routers/health.py

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok_status() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
