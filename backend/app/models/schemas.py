from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class RepositoryCreate(BaseModel):
    path: str = Field(..., description="Absolute path to the local Git repository")

class RepositoryResponse(BaseModel):
    id: str
    name: str
    path: str
    git_status: Optional[Dict[str, Any]] = None
    languages: Optional[Dict[str, int]] = None
    analysis_status: str
    created_at: datetime
    last_analyzed_at: Optional[datetime] = None

class SymbolSchema(BaseModel):
    id: str
    name: str
    qualified_name: str
    type: str
    file_path: str
    line_start: Optional[int]
    line_end: Optional[int]
    signature: Optional[str] = None
    docstring: Optional[str] = None

class TestResultSchema(BaseModel):
    id: str
    framework: str
    exit_code: int
    passed: int
    failed: int
    duration_seconds: float
    output: str

class TestRunRequest(BaseModel):
    test_target: Optional[str] = None
    framework: Optional[str] = None
    timeout: int = 60

class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    properties: Dict[str, Any]

class GraphEdge(BaseModel):
    source: str
    target: str
    type: str

class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]

class CodeSearchResponse(BaseModel):
    file: str
    line: int
    content: str
    symbol: Optional[str] = None
    context: Optional[List[str]] = None
