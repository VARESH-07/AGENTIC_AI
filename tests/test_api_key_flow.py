import os
import sys
import pytest
from fastapi.testclient import TestClient

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.main import app
from app.agent.session import session_key_manager, SessionKeyManager

@pytest.fixture(autouse=True)
def reset_session_key():
    session_key_manager.clear()
    yield
    session_key_manager.clear()

def test_initial_api_key_status_not_configured():
    client = TestClient(app)
    response = client.get("/api/v1/config/api-key/status")
    assert response.status_code == 200
    data = response.json()
    assert data == {"configured": False}
    assert "api_key" not in data

def test_initial_api_key_status_unprefixed_endpoint():
    client = TestClient(app)
    response = client.get("/api/config/api-key/status")
    assert response.status_code == 200
    data = response.json()
    assert data == {"configured": False}

def test_submit_empty_api_key_rejected():
    client = TestClient(app)
    response = client.post("/api/v1/config/api-key", json={"api_key": "   "})
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert response.json() != {"configured": True}
    assert session_key_manager.is_configured() is False

def test_submit_placeholder_api_key_rejected():
    client = TestClient(app)
    response = client.post("/api/v1/config/api-key", json={"api_key": "YOUR_OPENROUTER_API_KEY"})
    assert response.status_code == 400
    data = response.json()
    assert "placeholder" in data["detail"].lower() or "invalid" in data["detail"].lower()
    assert session_key_manager.is_configured() is False

def test_submit_valid_test_api_key():
    client = TestClient(app)
    test_key = "sk-or-v1-valid-test-key"
    response = client.post("/api/v1/config/api-key", json={"api_key": test_key})
    assert response.status_code == 200
    data = response.json()
    assert data == {"configured": True}
    assert "sk-or-v1" not in str(data)  # Key MUST NOT be present in response

    # Check status endpoint
    status_resp = client.get("/api/v1/config/api-key/status")
    assert status_resp.status_code == 200
    assert status_resp.json() == {"configured": True}
    assert "sk-or-v1" not in str(status_resp.json())

def test_clear_api_key():
    session_key_manager.set_api_key("sk-or-v1-valid-test-key")
    assert session_key_manager.is_configured() is True

    client = TestClient(app)
    response = client.delete("/api/v1/config/api-key")
    assert response.status_code == 200
    assert response.json() == {"configured": False}
    assert session_key_manager.is_configured() is False
