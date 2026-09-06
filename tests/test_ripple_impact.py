import os
import sys
import uuid
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.main import app
from app.database.connection import DBConnection
from app.analysis.investigator import CodeImpactInvestigator
from app.models.db import DBSymbol, DBRelationship

@pytest.fixture(scope="module")
def setup_ripple_repo():
    DBConnection.init_db()
    conn = DBConnection.get_connection()
    cursor = conn.cursor()

    uid = str(uuid.uuid4())[:8]
    repo_id = f"ripple_repo_{uid}"
    path = f"C:/repos/ripple_demo_{uid}"
    now = "2026-09-06T12:00:00"

    cursor.execute("""
        INSERT INTO repositories (id, name, path, analysis_status, created_at)
        VALUES (?, ?, ?, 'ANALYZED', ?)
    """, (repo_id, "Ripple-Demo-Repo", path, now))

    mod_auth = DBSymbol(id=str(uuid.uuid4()), repository_id=repo_id, file_path="auth_service.py", name="auth_service.py", qualified_name="auth_service.py", type="FILE", line_start=1, line_end=100, signature="", docstring="")
    fn_login = DBSymbol(id=str(uuid.uuid4()), repository_id=repo_id, file_path="auth_service.py", name="login", qualified_name="auth_service.login", type="FUNCTION", line_start=10, line_end=30, signature="", docstring="")

    mod_ctrl = DBSymbol(id=str(uuid.uuid4()), repository_id=repo_id, file_path="auth_controller.py", name="auth_controller.py", qualified_name="auth_controller.py", type="FILE", line_start=1, line_end=80, signature="", docstring="")
    fn_handle_login = DBSymbol(id=str(uuid.uuid4()), repository_id=repo_id, file_path="auth_controller.py", name="handle_login", qualified_name="auth_controller.handle_login", type="FUNCTION", line_start=15, line_end=35, signature="", docstring="")

    mod_routes = DBSymbol(id=str(uuid.uuid4()), repository_id=repo_id, file_path="api/routes.py", name="routes.py", qualified_name="api/routes.py", type="FILE", line_start=1, line_end=50, signature="", docstring="")
    fn_login_route = DBSymbol(id=str(uuid.uuid4()), repository_id=repo_id, file_path="api/routes.py", name="login_route", qualified_name="api.routes.login_route", type="FUNCTION", line_start=10, line_end=25, signature="", docstring="")

    symbols = [mod_auth, fn_login, mod_ctrl, fn_handle_login, mod_routes, fn_login_route]
    for s in symbols:
        cursor.execute("""
            INSERT INTO symbols (id, repository_id, file_path, name, qualified_name, type, line_start, line_end)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (s.id, s.repository_id, s.file_path, s.name, s.qualified_name, s.type, s.line_start, s.line_end))

    rel1 = DBRelationship(id=str(uuid.uuid4()), repository_id=repo_id, source_id=fn_handle_login.id, target_id=fn_login.id, type="CALLS", metadata=None)
    rel2 = DBRelationship(id=str(uuid.uuid4()), repository_id=repo_id, source_id=fn_login_route.id, target_id=fn_handle_login.id, type="CALLS", metadata=None)

    for r in [rel1, rel2]:
        cursor.execute("""
            INSERT INTO relationships (id, repository_id, source_id, target_id, type, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (r.id, r.repository_id, r.source_id, r.target_id, r.type, r.metadata))

    conn.commit()
    conn.close()

    return repo_id


def test_ripple_impact_analysis(setup_ripple_repo):
    repo_id = setup_ripple_repo

    res = CodeImpactInvestigator.analyze_ripple_impact(repo_id, target_module="auth_service.py")

    assert res["analysis_type"] == "ripple"
    assert res["repository_id"] == repo_id
    assert res["target_module"] == "auth_service.py"
    assert "auth_service.py" in res["affected_modules"]
    assert "auth_controller.py" in res["affected_modules"]
    assert "routes.py" in res["affected_modules"]
    assert "login" in res["affected_functions"]
    assert "handle_login" in res["affected_functions"]
    assert res["risk"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert res["risk_score"] > 0
    assert len(res["reasons"]) > 0


def test_ripple_impact_api_endpoint(setup_ripple_repo):
    repo_id = setup_ripple_repo
    client = TestClient(app)

    response = client.post(f"/api/v1/repositories/{repo_id}/ripple-impact", json={
        "module": "auth_service.py"
    })

    assert response.status_code == 200
    data = response.json()

    assert data["analysis_type"] == "ripple"
    assert data["repository_id"] == repo_id
    assert data["target_module"] == "auth_service.py"
    assert isinstance(data["affected_modules"], list)
    assert isinstance(data["affected_functions"], list)
    assert isinstance(data["impact_chain"], list)
    assert "risk" in data
    assert "risk_score" in data


def test_ripple_impact_target_not_found(setup_ripple_repo):
    repo_id = setup_ripple_repo
    client = TestClient(app)

    response = client.post(f"/api/v1/repositories/{repo_id}/ripple-impact", json={
        "module": "non_existent_module.py"
    })

    assert response.status_code == 404
    assert "Target not found in selected repository." in response.json()["detail"]
