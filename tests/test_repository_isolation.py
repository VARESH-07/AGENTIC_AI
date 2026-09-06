import os
import sys
import uuid
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.main import app
from app.database.connection import DBConnection
from app.analysis.investigator import CodeImpactInvestigator
from app.models.db import DBSymbol

@pytest.fixture(scope="module")
def setup_isolated_repos():
    DBConnection.init_db()
    conn = DBConnection.get_connection()
    cursor = conn.cursor()

    uid_a = str(uuid.uuid4())[:8]
    uid_b = str(uuid.uuid4())[:8]
    repo_a_id = f"repo_a_{uid_a}"
    repo_b_id = f"repo_b_{uid_b}"
    path_a = f"C:/repos/repo_a_{uid_a}"
    path_b = f"C:/repos/repo_b_{uid_b}"
    now = "2026-09-06T12:00:00"

    cursor.execute("""
        INSERT INTO repositories (id, name, path, analysis_status, created_at)
        VALUES (?, ?, ?, 'ANALYZED', ?)
    """, (repo_a_id, "Repo-A", path_a, now))

    cursor.execute("""
        INSERT INTO repositories (id, name, path, analysis_status, created_at)
        VALUES (?, ?, ?, 'ANALYZED', ?)
    """, (repo_b_id, "Repo-B", path_b, now))

    sym_a = DBSymbol(
        id=str(uuid.uuid4()),
        repository_id=repo_a_id,
        file_path="repo_a/payment.py",
        name="process_payment",
        qualified_name="repo_a.payment.process_payment",
        type="FUNCTION",
        line_start=10,
        line_end=20,
        signature="",
        docstring=""
    )

    sym_b = DBSymbol(
        id=str(uuid.uuid4()),
        repository_id=repo_b_id,
        file_path="repo_b/billing.py",
        name="process_payment",
        qualified_name="repo_b.billing.process_payment",
        type="FUNCTION",
        line_start=15,
        line_end=30,
        signature="",
        docstring=""
    )

    for sym in [sym_a, sym_b]:
        cursor.execute("""
            INSERT INTO symbols (id, repository_id, file_path, name, qualified_name, type, line_start, line_end)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (sym.id, sym.repository_id, sym.file_path, sym.name, sym.qualified_name, sym.type, sym.line_start, sym.line_end))

    conn.commit()
    conn.close()

    return {"repo_a_id": repo_a_id, "repo_b_id": repo_b_id}


def test_repository_isolation(setup_isolated_repos):
    repo_a_id = setup_isolated_repos["repo_a_id"]
    repo_b_id = setup_isolated_repos["repo_b_id"]

    res_a = CodeImpactInvestigator.analyze(repo_a_id, "process_payment")
    assert "repo_a/payment.py" in res_a["impact"].affected_files
    assert "repo_b/billing.py" not in res_a["impact"].affected_files

    res_b = CodeImpactInvestigator.analyze(repo_b_id, "process_payment")
    assert "repo_b/billing.py" in res_b["impact"].affected_files
    assert "repo_a/payment.py" not in res_b["impact"].affected_files


def test_repository_target_not_found(setup_isolated_repos):
    repo_a_id = setup_isolated_repos["repo_a_id"]

    with pytest.raises(ValueError) as exc_info:
        CodeImpactInvestigator.analyze(repo_a_id, "non_existent_function_xyz")
    assert "Target not found in selected repository." in str(exc_info.value)


def test_repository_api_validation(setup_isolated_repos):
    repo_a_id = setup_isolated_repos["repo_a_id"]
    client = TestClient(app)

    resp_valid = client.post(f"/api/v1/repositories/{repo_a_id}/function-impact", json={
        "target_symbol": "process_payment"
    })
    assert resp_valid.status_code == 200
    assert resp_valid.json()["repository_id"] == repo_a_id

    resp_invalid = client.post(f"/api/v1/repositories/{repo_a_id}/function-impact", json={
        "target_symbol": "non_existent_target"
    })
    assert resp_invalid.status_code == 404
    assert "Target not found in selected repository." in resp_invalid.json()["detail"]

    resp_bad_repo = client.post("/api/v1/repositories/invalid_repo_999/function-impact", json={
        "target_symbol": "process_payment"
    })
    assert resp_bad_repo.status_code == 404
