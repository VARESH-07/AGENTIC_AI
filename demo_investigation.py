import os
import sys
import json
import uuid

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

from app.database.connection import DBConnection
from app.agent.orchestrator import RippleOrchestrator
from app.api.repositories import _run_analysis

REPO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "sample-repositories", "auth-demo"))

def setup_demo_repo() -> str:
    """Ensure the sample repository is initialized and analyzed in the database."""
    DBConnection.init_db()
    conn = DBConnection.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM repositories WHERE path = ?", (REPO_PATH,))
    row = cursor.fetchone()
    
    if row:
        repo_id = row["id"]
    else:
        repo_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO repositories (id, name, path, analysis_status, created_at)
            VALUES (?, ?, ?, 'NOT_ANALYZED', '2026-09-01')
        """, (repo_id, "auth-demo", REPO_PATH))
        conn.commit()
        _run_analysis(repo_id, REPO_PATH)
        
    conn.close()
    return repo_id

def print_header(title):
    print(f"\n============================================================\n{title}\n============================================================")

def main():
    repo_id = setup_demo_repo()
    query = "Why did changing process_payment() break checkout?"
    
    print_header("RIPPLE AI — AI DETECTIVE & IMPACT INVESTIGATOR")
    print(f"\nQuestion:\n{query}\n")
    
    orchestrator = RippleOrchestrator(repo_id)
    result = orchestrator.run_deterministic_investigation(query)
    
    # Print safe investigation trace
    for trace_step in result.trace:
        print(trace_step)
        
    print("\n---")
    print("\n## INVESTIGATION RESULT\n")
    print(f"Target:\n{result.target}\n")
    print(f"Likely Root Cause ({result.root_cause.status}):\n{result.root_cause.explanation}\n")
    print(f"Affected Functions:\n" + "\n".join([f"* {fn}" for fn in result.affected_functions]))
    print(f"\nAffected Files:\n" + "\n".join([f"* {f}" for f in result.affected_files]))
    print(f"\nRisk:\n{result.risk.level} (Score: {result.risk.score}/100)")
    print(f"Reasons:\n" + "\n".join([f"* {r}" for r in result.risk.reasons]))
    print(f"\nConfidence:\n{result.root_cause.confidence}\n")
    
    print("Evidence:")
    for ev in result.evidence:
        print(f"* [{ev.type}] {ev.summary}")
        
    print(f"\nImpact Chain:\n{' -> '.join(result.impact.chain)}")
    
    print_header("INVESTIGATION COMPLETE")

if __name__ == "__main__":
    main()
