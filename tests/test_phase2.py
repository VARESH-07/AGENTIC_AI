import os
import sys
import pytest
from fastapi.testclient import TestClient

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.main import app
from app.database.connection import DBConnection
from app.analysis.investigator import CodeImpactInvestigator
from app.agent.evidence import EvidenceCollector
from app.agent.orchestrator import RippleOrchestrator, MAX_STEPS
from app.api.repositories import _run_analysis

REPO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sample-repositories", "auth-demo"))

@pytest.fixture(scope="module")
def setup_repo():
    DBConnection.init_db()
    conn = DBConnection.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM repositories WHERE path = ?", (REPO_PATH,))
    row = cursor.fetchone()
    
    if row:
        repo_id = row["id"]
    else:
        import uuid
        repo_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO repositories (id, name, path, analysis_status, created_at)
            VALUES (?, ?, ?, 'NOT_ANALYZED', '2026-09-01')
        """, (repo_id, "auth-demo", REPO_PATH))
        conn.commit()
        _run_analysis(repo_id, REPO_PATH)
        
    conn.close()
    return repo_id

def test_no_llm_app_import():
    """Verify application imports cleanly without requiring LLM credentials."""
    import app.main
    assert app.main.app is not None

def test_impact_analysis_and_risk(setup_repo):
    repo_id = setup_repo
    res = CodeImpactInvestigator.analyze(repo_id, "AuthService.authenticate")
    
    impact = res["impact"]
    risk = res["risk"]
    
    assert impact.target == "AuthService.authenticate"
    assert len(impact.affected_functions) >= 1
    assert risk.level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert risk.score >= 0
    assert len(risk.reasons) > 0

def test_evidence_collector():
    collector = EvidenceCollector()
    collector.add("CODE", "Definition found", {"file": "auth.py", "line": 10})
    collector.add("GIT", "Commit abc123", {"hash": "abc123"})
    
    ev_list = collector.get_all()
    assert len(ev_list) == 2
    assert ev_list[0].type == "CODE"
    assert ev_list[1].type == "GIT"

def test_max_step_limit():
    assert MAX_STEPS == 15

def test_deterministic_orchestrator(setup_repo):
    repo_id = setup_repo
    orchestrator = RippleOrchestrator(repo_id)
    query = "Why did changing process_payment() break checkout?"
    
    res = orchestrator.run_deterministic_investigation(query)
    
    assert res.query == query
    assert res.target is not None
    assert res.root_cause.status in ["CONFIRMED", "LIKELY", "POSSIBLE"]
    assert res.risk.level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert len(res.evidence) > 0
    assert len(res.trace) > 0

def test_investigation_api_endpoint(setup_repo):
    repo_id = setup_repo
    client = TestClient(app)
    
    response = client.post("/api/v1/investigate", json={
        "repository_id": repo_id,
        "query": "Why did changing process_payment() break checkout?"
    })
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["query"] == "Why did changing process_payment() break checkout?"
    assert "target" in data
    assert "impact" in data
    assert "root_cause" in data
    assert "risk" in data
    assert "evidence" in data
    assert "trace" in data
