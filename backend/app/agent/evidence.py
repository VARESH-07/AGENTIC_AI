from typing import List, Dict, Any, Optional
from app.models.schemas import EvidenceItem

class EvidenceCollector:
    def __init__(self):
        self.evidence: List[EvidenceItem] = []

    def add(self, ev_type: str, summary: str, details: Optional[Dict[str, Any]] = None):
        """Add a structured evidence item."""
        item = EvidenceItem(
            type=ev_type,
            summary=summary,
            details=details or {}
        )
        # Avoid duplicate summaries
        if not any(e.summary == summary for e in self.evidence):
            self.evidence.append(item)

    def get_all(self) -> List[EvidenceItem]:
        return self.evidence

    def to_dict_list(self) -> List[Dict[str, Any]]:
        return [e.model_dump() for e in self.evidence]
