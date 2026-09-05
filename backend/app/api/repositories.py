from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Any
import uuid
import os
import datetime
from app.models.schemas import RepositoryCreate, RepositoryResponse, TestRunRequest, TestResultSchema, GraphResponse
from app.database.connection import DBConnection
from app.git.service import GitService
from app.tools import agent_tools
from app.analysis.symbols import extract_symbols
from app.analysis.relationships import extract_relationships

router = APIRouter()

@router.post("/repositories", response_model=RepositoryResponse)
def create_repository(repo_in: RepositoryCreate):
    path = repo_in.path
    git_url = repo_in.git_url
    
    if not path and not git_url:
        raise HTTPException(status_code=400, detail="Either 'path' or 'git_url' must be provided.")
        
    if git_url:
        # Generate target directory in sample-repositories/cloned-repos
        repo_name = git_url.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        if not repo_name:
            repo_name = "cloned_repo_" + str(uuid.uuid4())[:8]
            
        base_clone_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "sample-repositories", "cloned-repos"))
        os.makedirs(base_clone_dir, exist_ok=True)
        clone_path = os.path.join(base_clone_dir, repo_name)
        
        if os.path.exists(clone_path):
            clone_path = os.path.join(base_clone_dir, f"{repo_name}_{str(uuid.uuid4())[:6]}")
            
        try:
            import git
            git.Repo.clone_from(git_url, clone_path)
            path = clone_path
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to clone repository from URL '{git_url}': {str(e)}")
    else:
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            raise HTTPException(status_code=400, detail="Provided local path is not a valid directory")
            
    try:
        repo = GitService.get_repo(path)
    except ValueError as e:
        # If not a git repo, attempt git init so GitService works smoothly
        try:
            import git
            git.Repo.init(path)
        except Exception:
            raise HTTPException(status_code=400, detail=str(e))
        
    repo_id = str(uuid.uuid4())
    name = os.path.basename(path.rstrip("\\/"))
    now = datetime.datetime.now().isoformat()
    
    conn = DBConnection.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO repositories (id, name, path, analysis_status, created_at)
            VALUES (?, ?, ?, 'NOT_ANALYZED', ?)
        """, (repo_id, name, path, now))
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail="Repository already registered or DB error")
        
    conn.close()
    
    # Auto-run AST symbol & relationship analysis upon import
    try:
        _run_analysis(repo_id, path)
    except Exception as e:
        print(f"Auto-analysis failed during repository import: {e}")
        
    return RepositoryResponse(
        id=repo_id, name=name, path=path, 
        analysis_status="ANALYZED", created_at=datetime.datetime.fromisoformat(now)
    )

@router.get("/repositories", response_model=List[RepositoryResponse])
def get_repositories():
    conn = DBConnection.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM repositories")
    rows = cursor.fetchall()
    conn.close()
    
    return [RepositoryResponse(**dict(r)) for r in rows]

def _run_analysis(repo_id: str, path: str):
    conn = DBConnection.get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE repositories SET analysis_status = 'ANALYZING' WHERE id = ?", (repo_id,))
    conn.commit()
    
    try:
        # Very simple discovery of python files for phase 1
        for root, dirs, files in os.walk(path):
            if '.git' in dirs: dirs.remove('.git')
            if 'venv' in dirs: dirs.remove('venv')
            if '.venv' in dirs: dirs.remove('.venv')
            
            for f in files:
                if f.endswith('.py'):
                    file_path = os.path.join(root, f)
                    symbols = extract_symbols(repo_id, file_path, "python")
                    for sym in symbols:
                        cursor.execute("""
                            INSERT INTO symbols (id, repository_id, file_path, name, qualified_name, type, line_start, line_end)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (sym.id, repo_id, sym.file_path, sym.name, sym.qualified_name, sym.type, sym.line_start, sym.line_end))
                    
                    rels = extract_relationships(repo_id, file_path, "python", symbols)
                    for rel in rels:
                        cursor.execute("""
                            INSERT INTO relationships (id, repository_id, source_id, target_id, type, metadata)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (rel.id, repo_id, rel.source_id, rel.target_id, rel.type, rel.metadata))
                        
        now = datetime.datetime.now().isoformat()
        cursor.execute("UPDATE repositories SET analysis_status = 'ANALYZED', last_analyzed_at = ? WHERE id = ?", (now, repo_id))
        conn.commit()
    except Exception as e:
        print("Analysis error:", e)
        cursor.execute("UPDATE repositories SET analysis_status = 'FAILED' WHERE id = ?", (repo_id,))
        conn.commit()
    finally:
        conn.close()

@router.post("/repositories/{repo_id}/analyze")
def analyze_repository(repo_id: str, background_tasks: BackgroundTasks):
    conn = DBConnection.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT path FROM repositories WHERE id = ?", (repo_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Repository not found")
        
    # In a real app we'd use background tasks, but for simple tests we might run inline
    # background_tasks.add_task(_run_analysis, repo_id, row["path"])
    _run_analysis(repo_id, row["path"]) # Run synchronously for demo ease
    return {"status": "Analysis started/completed"}

@router.get("/repositories/{repo_id}/symbols")
def get_symbols(repo_id: str):
    conn = DBConnection.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM symbols WHERE repository_id = ?", (repo_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/repositories/{repo_id}/graph")
def get_graph(repo_id: str):
    graph = agent_tools._build_graph(repo_id)
    nodes = []
    edges = []
    for n, data in graph.graph.nodes(data=True):
        nodes.append({"id": n, "label": data.get("name", n), "type": data.get("type", "UNKNOWN"), "properties": data})
    for u, v, data in graph.graph.edges(data=True):
        edges.append({"source": u, "target": v, "type": data.get("type", "UNKNOWN")})
    return {"nodes": nodes, "edges": edges}

@router.get("/repositories/{repo_id}/impact/{symbol_id}")
def get_impact(repo_id: str, symbol_id: str):
    graph = agent_tools._build_graph(repo_id)
    return graph.calculate_impact(symbol_id)

@router.post("/repositories/{repo_id}/tests/run")
def run_tests(repo_id: str, request: TestRunRequest):
    res = agent_tools.run_tests(repo_id, test_target=request.test_target, timeout=request.timeout)
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error"))
    return res["results"]
