from typing import List, Dict, Any, Optional
from app.search.service import SearchService
from app.git.service import GitService
from app.execution.discovery import TestDiscovery
from app.execution.runner import SafeTestRunner
from app.analysis.graph import CodeGraph
from app.database.connection import DBConnection
from app.models.db import DBSymbol

# These functions represent the clean, standalone, typed tool interfaces
# that the future ReAct agent will call. They return structured JSON-compatible dicts.

def _get_repo_path(repo_id: str) -> str:
    """Helper to get repo path from DB."""
    conn = DBConnection.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT path FROM repositories WHERE id = ?", (repo_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise ValueError(f"Repository not found: {repo_id}")
    return row["path"]

def _get_symbols(repo_id: str) -> List[DBSymbol]:
    """Helper to fetch symbols for a repo."""
    conn = DBConnection.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM symbols WHERE repository_id = ?", (repo_id,))
    rows = cursor.fetchall()
    conn.close()
    return [DBSymbol(**dict(r)) for r in rows]

def _build_graph(repo_id: str) -> CodeGraph:
    """Helper to build the CodeGraph for a repo from DB."""
    conn = DBConnection.get_connection()
    cursor = conn.cursor()
    
    from app.models.db import DBRelationship
    
    cursor.execute("SELECT * FROM symbols WHERE repository_id = ?", (repo_id,))
    sym_rows = cursor.fetchall()
    symbols = [DBSymbol(**dict(r)) for r in sym_rows]
    
    cursor.execute("SELECT * FROM relationships WHERE repository_id = ?", (repo_id,))
    rel_rows = cursor.fetchall()
    rels = [DBRelationship(**dict(r)) for r in rel_rows]
    
    conn.close()
    
    graph = CodeGraph()
    graph.build_from_db(symbols, rels)
    return graph

def _find_symbol_id(graph: CodeGraph, symbol_name: str) -> Optional[str]:
    for node_id, data in graph.graph.nodes(data=True):
        if data.get("qualified_name") == symbol_name or data.get("name") == symbol_name:
            return node_id
    return None

def search_code(repo_id: str, query: str, context_lines: int = 2) -> Dict[str, Any]:
    try:
        repo_path = _get_repo_path(repo_id)
        results = SearchService.search_code(repo_path, query, context_lines)
        return {"success": True, "target": query, "results": results}
    except Exception as e:
        return {"success": False, "error": str(e)}

def read_file(repo_id: str, file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> Dict[str, Any]:
    try:
        repo_path = _get_repo_path(repo_id)
        content = SearchService.read_file(repo_path, file_path, start_line, end_line)
        return {"success": True, "file_path": file_path, "content": content}
    except Exception as e:
        return {"success": False, "error": str(e)}

def find_definition(repo_id: str, symbol_name: str) -> Dict[str, Any]:
    try:
        symbols = _get_symbols(repo_id)
        sym = SearchService.find_definition(symbols, symbol_name)
        if sym:
            return {"success": True, "target": symbol_name, "result": sym.__dict__}
        return {"success": False, "error": f"Symbol not found: {symbol_name}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def find_callers(repo_id: str, symbol_name: str) -> Dict[str, Any]:
    try:
        graph = _build_graph(repo_id)
        sym_id = _find_symbol_id(graph, symbol_name)
        if not sym_id:
            return {"success": False, "error": f"Symbol not found: {symbol_name}"}
        
        callers = graph.find_callers(sym_id)
        # format results for agent
        formatted = [{"file": c["node_data"].get("file_path"), "symbol": c["node_data"].get("qualified_name"), "line": c["node_data"].get("line_start")} for c in callers]
        return {"success": True, "target": symbol_name, "results": formatted}
    except Exception as e:
        return {"success": False, "error": str(e)}

def find_callees(repo_id: str, symbol_name: str) -> Dict[str, Any]:
    try:
        graph = _build_graph(repo_id)
        sym_id = _find_symbol_id(graph, symbol_name)
        if not sym_id:
            return {"success": False, "error": f"Symbol not found: {symbol_name}"}
        
        callees = graph.find_callees(sym_id)
        formatted = [{"file": c["node_data"].get("file_path"), "symbol": c["node_data"].get("qualified_name"), "line": c["node_data"].get("line_start")} for c in callees]
        return {"success": True, "target": symbol_name, "results": formatted}
    except Exception as e:
        return {"success": False, "error": str(e)}

def find_dependencies(repo_id: str, symbol_name: str) -> Dict[str, Any]:
    try:
        graph = _build_graph(repo_id)
        sym_id = _find_symbol_id(graph, symbol_name)
        if not sym_id:
            return {"success": False, "error": f"Symbol not found: {symbol_name}"}
        
        deps = graph.find_dependencies(sym_id)
        formatted = [{"file": c["node_data"].get("file_path"), "symbol": c["node_data"].get("qualified_name"), "line": c["node_data"].get("line_start")} for c in deps]
        return {"success": True, "target": symbol_name, "results": formatted}
    except Exception as e:
        return {"success": False, "error": str(e)}

def find_dependents(repo_id: str, symbol_name: str) -> Dict[str, Any]:
    try:
        graph = _build_graph(repo_id)
        sym_id = _find_symbol_id(graph, symbol_name)
        if not sym_id:
            return {"success": False, "error": f"Symbol not found: {symbol_name}"}
        
        # In a generic dependency graph, incoming DEPENDS_ON or CALLS edges are dependents
        deps = []
        for src, tgt, data in graph.graph.in_edges(sym_id, data=True):
            if data.get("type") in ["CALLS", "DEPENDS_ON", "IMPORTS"]:
                deps.append(graph.graph.nodes[src])
                
        formatted = [{"file": d.get("file_path"), "symbol": d.get("qualified_name"), "line": d.get("line_start")} for d in deps]
        return {"success": True, "target": symbol_name, "results": formatted}
    except Exception as e:
        return {"success": False, "error": str(e)}

def query_code_graph(repo_id: str, query_type: str, symbol_name: str, depth: int = 1) -> Dict[str, Any]:
    # Placeholder for more complex graph queries
    return {"success": False, "error": "Not fully implemented yet"}

def get_git_diff(repo_id: str, commit_hash: Optional[str] = None) -> Dict[str, Any]:
    try:
        repo_path = _get_repo_path(repo_id)
        diff = GitService.get_git_diff(repo_path, commit_hash=commit_hash)
        return {"success": True, "diff": diff}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_commit(repo_id: str, commit_hash: str) -> Dict[str, Any]:
    try:
        repo_path = _get_repo_path(repo_id)
        info = GitService.get_commit(repo_path, commit_hash)
        return {"success": True, "commit": info}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_git_history(repo_id: str, max_count: int = 50, path: Optional[str] = None) -> Dict[str, Any]:
    try:
        repo_path = _get_repo_path(repo_id)
        history = GitService.get_git_history(repo_path, max_count, path)
        return {"success": True, "history": history}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_file_history(repo_id: str, file_path: str) -> Dict[str, Any]:
    try:
        repo_path = _get_repo_path(repo_id)
        history = GitService.get_file_history(repo_path, file_path)
        return {"success": True, "file_path": file_path, "history": history}
    except Exception as e:
        return {"success": False, "error": str(e)}

def find_tests(repo_id: str, target_symbol: str = None) -> Dict[str, Any]:
    try:
        repo_path = _get_repo_path(repo_id)
        tests = TestDiscovery.find_tests(repo_path, target_symbol)
        return {"success": True, "target": target_symbol, "results": tests}
    except Exception as e:
        return {"success": False, "error": str(e)}

def run_tests(repo_id: str, test_target: str = None, timeout: int = 60) -> Dict[str, Any]:
    try:
        repo_path = _get_repo_path(repo_id)
        framework = TestDiscovery.detect_framework(repo_path)
        result = SafeTestRunner.run_tests(repo_path, framework, test_target, timeout)
        return {"success": True, "results": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
