from dataclasses import dataclass
from typing import Optional, List, Dict, Any

@dataclass
class DBRepository:
    id: str
    name: str
    path: str
    git_status: Optional[str]
    languages: Optional[str]
    analysis_status: str
    created_at: str
    last_analyzed_at: Optional[str]

@dataclass
class DBFile:
    id: str
    repository_id: str
    path: str
    language: Optional[str]
    size_bytes: Optional[int]
    line_count: Optional[int]

@dataclass
class DBSymbol:
    id: str
    repository_id: str
    file_path: str
    name: str
    qualified_name: str
    type: str
    line_start: Optional[int]
    line_end: Optional[int]
    signature: Optional[str]
    docstring: Optional[str]

@dataclass
class DBRelationship:
    id: str
    repository_id: str
    source_id: str
    target_id: str
    type: str
    metadata: Optional[str]

@dataclass
class DBTestResult:
    id: str
    repository_id: str
    framework: Optional[str]
    exit_code: Optional[int]
    passed: Optional[int]
    failed: Optional[int]
    duration_seconds: Optional[float]
    output: Optional[str]
    executed_at: str
