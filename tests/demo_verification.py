import os
import sys
import json
import uuid

# Add backend to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.database.connection import DBConnection
from app.api.repositories import _run_analysis
from app.tools import agent_tools
from app.git.service import GitService

REPO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sample-repositories", "auth-demo"))

def setup():
    # Reset DB for tests
    if os.path.exists("ripple.db"):
        os.remove("ripple.db")
        
    DBConnection.init_db()
    
    conn = DBConnection.get_connection()
    cursor = conn.cursor()
    repo_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO repositories (id, name, path, analysis_status, created_at)
        VALUES (?, ?, ?, 'NOT_ANALYZED', '2026-09-01')
    """, (repo_id, "auth-demo", REPO_PATH))
    conn.commit()
    conn.close()
    
    print(f"Running analysis on {REPO_PATH}...")
    _run_analysis(repo_id, REPO_PATH)
    return repo_id

def print_header(title):
    print(f"\n{'='*50}\n{title}\n{'='*50}")

def main():
    repo_id = setup()
    
    print_header("Test 1: Find AuthService.authenticate()")
    res1 = agent_tools.find_definition(repo_id, "AuthService.authenticate")
    print(json.dumps(res1, indent=2))
    
    print_header("Test 2: Find callers of AuthService.authenticate()")
    res2 = agent_tools.find_callers(repo_id, "AuthService.authenticate")
    print(json.dumps(res2, indent=2))

    print_header("Test 3: Find dependencies of AuthService.authenticate()")
    res3 = agent_tools.find_dependencies(repo_id, "AuthService.authenticate")
    print(json.dumps(res3, indent=2))

    print_header("Test 4: Find relevant tests")
    res4 = agent_tools.find_tests(repo_id, "AuthService.authenticate")
    print(json.dumps(res4, indent=2))

    print_header("Test 5: Inspect commit abc123")
    res5 = agent_tools.get_commit(repo_id, "abc123")
    print(json.dumps(res5, indent=2))

    print_header("Test 6: Show Git diff of commit abc123")
    res6 = agent_tools.get_git_diff(repo_id, "abc123")
    print(res6.get("diff"))

    print_header("Test 7: Run relevant authentication tests")
    res7 = agent_tools.run_tests(repo_id)
    print(f"Exit Code: {res7['results']['exit_code']}")
    print(f"Passed: {res7['results']['passed']}")
    print(f"Failed: {res7['results']['failed']}")
    print(f"Output snippet:\n{res7['results']['output'][:500]}...")

    print_header("Test 8: Return dependency graph summary")
    graph = agent_tools._build_graph(repo_id)
    print(f"Nodes: {len(graph.graph.nodes)}")
    print(f"Edges: {len(graph.graph.edges)}")
    for edge in graph.graph.edges(data=True):
        src_name = graph.graph.nodes[edge[0]].get('name', edge[0])
        tgt_name = graph.graph.nodes[edge[1]].get('name', edge[1])
        print(f"  {src_name} --[{edge[2].get('type')}]--> {tgt_name}")
        
    print("\nALL PHASE 1 DEMO TESTS EXECUTED.")

if __name__ == "__main__":
    main()
