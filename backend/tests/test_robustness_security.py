import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from fastapi import status
from backend.app.main import app
from backend.app.core.config import settings

client = TestClient(app)

# ---------------------------------------------------------------------------
# 1. SECURITY HEADERS TESTS
# ---------------------------------------------------------------------------
def test_security_headers_presence():
    """
    Verifies that OWASP security headers are present and configured correctly.
    """
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    
    # Assert header configurations
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in response.headers
    
    csp = response.headers.get("Content-Security-Policy")
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "style-src 'self'" in csp


# ---------------------------------------------------------------------------
# 2. TRUSTED HOST TESTS
# ---------------------------------------------------------------------------
def test_trusted_host_enforcement():
    """
    Verifies that requests with untrusted Host headers are rejected with 400 Bad Request.
    """
    # Allowed host header
    allowed_response = client.get("/health", headers={"Host": "localhost"})
    assert allowed_response.status_code == status.HTTP_200_OK

    # Forbidden host header
    blocked_client = TestClient(app)
    blocked_response = blocked_client.get("/health", headers={"Host": "evil.com"})
    assert blocked_response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# 3. MALFORMED / ADVERSARIAL PAYLOAD TESTS
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("payload, expected_status", [
    # A. Null inputs
    (None, status.HTTP_422_UNPROCESSABLE_ENTITY),
    
    # B. Empty structures
    ({}, status.HTTP_422_UNPROCESSABLE_ENTITY),
    
    # C. Missing required fields (e.g. missing zone_id)
    ({"source": "CAMERA", "count": 150, "timestamp": "2026-07-09T12:00:00Z"}, status.HTTP_422_UNPROCESSABLE_ENTITY),
    
    # D. Invalid UUID string formats
    ({
        "zone_id": "not-a-uuid-string",
        "source": "CAMERA",
        "count": 150,
        "timestamp": "2026-07-09T12:00:00Z"
    }, status.HTTP_422_UNPROCESSABLE_ENTITY),
    
    # E. Invalid Enum values (not CAMERA or TURNSTILE)
    ({
        "zone_id": "11111111-1111-1111-1111-111111111111",
        "source": "DRONE",
        "count": 150,
        "timestamp": "2026-07-09T12:00:00Z"
    }, status.HTTP_422_UNPROCESSABLE_ENTITY),
    
    # F. Negative counts (should be rejected by ge=0)
    ({
        "zone_id": "11111111-1111-1111-1111-111111111111",
        "source": "CAMERA",
        "count": -50,
        "timestamp": "2026-07-09T12:00:00Z"
    }, status.HTTP_422_UNPROCESSABLE_ENTITY),
])
def test_telemetry_adversarial_payloads(payload, expected_status):
    """
    Submits invalid, null, negative, and malformed structures to POST /api/v1/telemetry
    and asserts they fail with 422 Unprocessable Entity, never an unhandled 500.
    """
    response = client.post(
        "/api/v1/telemetry", 
        json=payload, 
        headers={"X-API-Key": settings.API_KEY or "fifanexus_api_key_2026"}
    )
    assert response.status_code == expected_status
    assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR


@pytest.mark.parametrize("payload, expected_status", [
    # A. Missing source / event_type
    ({"zone_id": "11111111-1111-1111-1111-111111111111", "payload": {}}, status.HTTP_422_UNPROCESSABLE_ENTITY),
    
    # B. Invalid enum event_type
    ({
        "zone_id": "11111111-1111-1111-1111-111111111111",
        "source": "sensor:camera",
        "event_type": "INVALID_EVENT_TYPE_LITERAL",
        "payload": {}
    }, status.HTTP_422_UNPROCESSABLE_ENTITY),
])
def test_manual_event_adversarial_payloads(payload, expected_status):
    """
    Submits invalid structures to POST /api/v1/events and asserts they are caught by schemas.
    """
    response = client.post(
        "/api/v1/events",
        json=payload,
        headers={"X-API-Key": settings.API_KEY or "fifanexus_api_key_2026"}
    )
    assert response.status_code == expected_status
    assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR


# ---------------------------------------------------------------------------
# 4. PERFORMANCE SLA / LATENCY REGRESSION TESTS
# ---------------------------------------------------------------------------
def test_endpoint_latency_sla():
    """
    SLA Regression Test: Asserts that critical endpoints resolve within SLA thresholds (e.g. < 200ms).
    """
    import time
    
    # Measure GET /health latency
    start = time.perf_counter()
    response = client.get("/health")
    latency_ms = (time.perf_counter() - start) * 1000.0
    
    assert response.status_code == status.HTTP_200_OK
    assert latency_ms < 200.0, f"GET /health took too long: {latency_ms:.2f}ms (SLA: 200ms)"
    
    # Measure GET /api/v1/zones latency
    start = time.perf_counter()
    response = client.get("/api/v1/zones")
    latency_ms = (time.perf_counter() - start) * 1000.0
    
    assert response.status_code == status.HTTP_200_OK
    assert latency_ms < 200.0, f"GET /api/v1/zones took too long: {latency_ms:.2f}ms (SLA: 200ms)"


# ---------------------------------------------------------------------------
# 5. HEALTH ENDPOINT SPLIT & TIMING ATTACK TEST
# ---------------------------------------------------------------------------
def test_public_health_check():
    """
    Verifies that GET /health is public and returns basic service status.
    """
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert "api_key_configured" in data


def test_private_health_details():
    """
    Verifies that GET /health/details is protected by API key.
    """
    # 1. No key -> 401
    res_no_key = client.get("/health/details")
    assert res_no_key.status_code == status.HTTP_401_UNAUTHORIZED

    # 2. Invalid key -> 401
    res_invalid_key = client.get("/health/details", headers={"X-API-Key": "wrong-key"})
    assert res_invalid_key.status_code == status.HTTP_401_UNAUTHORIZED

    # 3. Valid key -> 200 with details
    valid_key = settings.API_KEY or "fifanexus_api_key_2026"
    with patch.object(settings, "API_KEY", valid_key):
        res_valid = client.get("/health/details", headers={"X-API-Key": valid_key})
        assert res_valid.status_code == status.HTTP_200_OK
        data = res_valid.json()
        assert "db_type" in data
        assert "redis" in data
        assert "uptime" in data


def test_api_key_timing_attack_compare_digest():
    """
    Timing Attack Mitigation: Verifies that secrets.compare_digest is utilized
    for API key comparisons.
    """
    with patch("backend.app.core.auth.secrets.compare_digest", return_value=True) as mock_compare:
        valid_key = settings.API_KEY or "fifanexus_api_key_2026"
        with patch.object(settings, "API_KEY", valid_key):
            response = client.get("/health/details", headers={"X-API-Key": valid_key})
            assert response.status_code == status.HTTP_200_OK
            mock_compare.assert_called_once_with(valid_key, valid_key)
