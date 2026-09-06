from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class RepositoryCreate(BaseModel):
    path: Optional[str] = Field(None, description="Absolute path to the local Git repository")
    git_url: Optional[str] = Field(None, description="Git clone URL (HTTPS/SSH)")

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

class EvidenceItem(BaseModel):
    type: str  # CODE, GRAPH, GIT, TEST, SEARCH
    summary: str
    details: Dict[str, Any] = {}

class ImpactChain(BaseModel):
    target: str
    chain: List[str] = []
    affected_functions: List[str] = []
    affected_files: List[str] = []

class RiskAssessment(BaseModel):
    level: str  # LOW, MEDIUM, HIGH, CRITICAL
    score: int
    reasons: List[str] = []

class RootCause(BaseModel):
    status: str  # CONFIRMED, LIKELY, POSSIBLE
    explanation: str
    confidence: str  # High, Medium, Low

class InvestigationRequest(BaseModel):
    repository_id: Optional[str] = None
    repository: Optional[str] = None
    query: str

class InvestigationResponse(BaseModel):
    query: str
    target: str
    impact: ImpactChain
    root_cause: RootCause
    risk: RiskAssessment
    evidence: List[EvidenceItem] = []
    affected_files: List[str] = []
    affected_functions: List[str] = []
    trace: List[str] = []

class FunctionImpactRequest(BaseModel):
    repository_id: Optional[str] = None
    repository: Optional[str] = None
    target_symbol: Optional[str] = None
    function: Optional[str] = None
    file_path: Optional[str] = None
    symbol_id: Optional[str] = None

class RippleImpactRequest(BaseModel):
    repository_id: Optional[str] = None
    repository: Optional[str] = None
    module: Optional[str] = None
    target_module: Optional[str] = None
    file_path: Optional[str] = None

class RippleImpactResponse(BaseModel):
    analysis_type: str = "ripple"
    repository_id: str
    repository: str
    target_module: str
    affected_modules: List[str] = []
    affected_functions: List[str] = []
    affected_tests: List[str] = []
    impact_chain: List[str] = []
    risk: str
    risk_score: int
    reasons: List[str] = []
    reason: Optional[str] = None


