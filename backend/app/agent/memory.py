from collections import deque
import threading
import datetime
from typing import List, Dict, Any, Optional

class MemoryManager:
    """
    Lightweight, thread-safe in-memory store for recent investigation results.
    Holds up to maxlen entries in memory (ephemeral).
    """
    def __init__(self, maxlen: int = 20):
        self.maxlen = maxlen
        self._memory = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def add_investigation(self, result: Any, repository_id: Optional[str] = None) -> None:
        """
        Record a completed investigation result into memory.
        """
        try:
            # Handle Pydantic model or dict
            if hasattr(result, "dict"):
                res_dict = result.dict()
            elif isinstance(result, dict):
                res_dict = result
            else:
                return

            entry = {
                "target": res_dict.get("target", "unknown"),
                "query": res_dict.get("query", ""),
                "repository": repository_id or res_dict.get("repository", ""),
                "risk": res_dict.get("risk", {}).get("level", "UNKNOWN") if isinstance(res_dict.get("risk"), dict) else getattr(res_dict.get("risk"), "level", "UNKNOWN"),
                "risk_score": res_dict.get("risk", {}).get("score", 0) if isinstance(res_dict.get("risk"), dict) else getattr(res_dict.get("risk"), "score", 0),
                "summary": res_dict.get("root_cause", {}).get("explanation", "") if isinstance(res_dict.get("root_cause"), dict) else getattr(res_dict.get("root_cause"), "explanation", ""),
                "affected_functions": res_dict.get("affected_functions", []),
                "affected_files": res_dict.get("affected_files", []),
                "timestamp": datetime.datetime.now().isoformat()
            }

            with self._lock:
                self._memory.appendleft(entry)
        except Exception as e:
            print(f"[MemoryManager] Error adding investigation to memory: {e}")

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Return the most recent N investigations.
        """
        with self._lock:
            return list(self._memory)[:limit]

    def find_by_target(self, target: str) -> List[Dict[str, Any]]:
        """
        Find past investigation entries matching target symbol name.
        """
        if not target:
            return []
        target_lower = target.lower()
        with self._lock:
            return [
                entry for entry in self._memory 
                if target_lower in entry["target"].lower() or entry["target"].lower() in target_lower
            ]

    def find_by_repository(self, repository_id: str) -> List[Dict[str, Any]]:
        """
        Find past investigation entries for a specific repository.
        """
        if not repository_id:
            return []
        with self._lock:
            return [entry for entry in self._memory if entry.get("repository") == repository_id]

    def clear(self) -> None:
        """
        Clear all in-memory investigation history.
        """
        with self._lock:
            self._memory.clear()

# Global singleton instance for memory manager
memory_manager = MemoryManager(maxlen=20)
