import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import pytest
from app.agent.memory import MemoryManager, memory_manager
from app.models.schemas import InvestigationResponse, ImpactChain, RiskAssessment, RootCause, EvidenceItem

def test_memory_add_and_retrieve():
    mem = MemoryManager(maxlen=5)
    mem.clear()
    
    mock_res = {
        "query": "Why did process_payment break?",
        "target": "process_payment",
        "risk": {"level": "HIGH", "score": 85},
        "root_cause": {"explanation": "Broken payment logic", "status": "CONFIRMED", "confidence": "High"},
        "affected_functions": ["process_payment", "checkout"],
        "affected_files": ["payment.py", "checkout.py"]
    }
    
    mem.add_investigation(mock_res, repository_id="repo-123")
    
    recent = mem.get_recent(limit=10)
    assert len(recent) == 1
    assert recent[0]["target"] == "process_payment"
    assert recent[0]["risk"] == "HIGH"
    assert recent[0]["risk_score"] == 85
    assert recent[0]["repository"] == "repo-123"

def test_memory_find_by_target():
    mem = MemoryManager(maxlen=5)
    mem.clear()
    
    mem.add_investigation({"target": "process_payment", "risk": {"level": "HIGH"}})
    mem.add_investigation({"target": "AuthService.authenticate", "risk": {"level": "LOW"}})
    
    found = mem.find_by_target("process_payment")
    assert len(found) == 1
    assert found[0]["target"] == "process_payment"
    
    not_found = mem.find_by_target("non_existent_func")
    assert len(not_found) == 0

def test_memory_limit_bounded():
    mem = MemoryManager(maxlen=3)
    mem.clear()
    
    for i in range(5):
        mem.add_investigation({"target": f"func_{i}", "risk": {"level": "LOW"}})
        
    recent = mem.get_recent(limit=10)
    assert len(recent) == 3
    # Most recent added was func_4
    assert recent[0]["target"] == "func_4"

def test_memory_clear():
    mem = MemoryManager(maxlen=5)
    mem.add_investigation({"target": "test_target", "risk": {"level": "LOW"}})
    assert len(mem.get_recent()) > 0
    
    mem.clear()
    assert len(mem.get_recent()) == 0

def test_memory_resilience_to_errors():
    mem = MemoryManager(maxlen=5)
    # Invalid object should not crash add_investigation
    mem.add_investigation(None)
    mem.add_investigation(12345)
    assert len(mem.get_recent()) == 0
