import networkx as nx
from typing import List, Dict, Any, Optional
from app.models.db import DBSymbol, DBRelationship

class CodeGraph:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.symbol_lookup = {}

    def build_from_db(self, symbols: List[DBSymbol], relationships: List[DBRelationship]):
        self.graph.clear()
        self.symbol_lookup.clear()

        # Add nodes
        for sym in symbols:
            self.symbol_lookup[sym.id] = sym
            self.graph.add_node(sym.id, 
                                name=sym.name, 
                                qualified_name=sym.qualified_name, 
                                type=sym.type,
                                file_path=sym.file_path,
                                line_start=sym.line_start,
                                repository_id=sym.repository_id)
                                
        # Add edges
        for rel in relationships:
            # Avoid adding edges to unresolved nodes if they are not in the graph,
            # or add them as placeholder external nodes.
            if rel.source_id not in self.graph:
                self.graph.add_node(rel.source_id, type="UNKNOWN", name=rel.source_id)
            if rel.target_id not in self.graph:
                self.graph.add_node(rel.target_id, type="UNKNOWN", name=rel.target_id)
                
            self.graph.add_edge(rel.source_id, rel.target_id, type=rel.type, metadata=rel.metadata)

    def find_callers(self, target_id: str, max_depth: int = 1) -> List[Dict[str, Any]]:
        """Find nodes that call the target."""
        if target_id not in self.graph:
            return []
            
        callers = []
        for src, tgt, data in self.graph.in_edges(target_id, data=True):
            if data.get("type") == "CALLS":
                callers.append({
                    "symbol_id": src,
                    "node_data": self.graph.nodes[src],
                    "edge_data": data
                })
        return callers

    def find_callees(self, source_id: str, max_depth: int = 1) -> List[Dict[str, Any]]:
        """Find nodes called by the source."""
        if source_id not in self.graph:
            return []
            
        callees = []
        for src, tgt, data in self.graph.out_edges(source_id, data=True):
            if data.get("type") == "CALLS":
                callees.append({
                    "symbol_id": tgt,
                    "node_data": self.graph.nodes[tgt],
                    "edge_data": data
                })
        return callees

    def find_dependencies(self, source_id: str) -> List[Dict[str, Any]]:
        """Find outgoing dependencies (CALLS, DEPENDS_ON, IMPORTS)."""
        if source_id not in self.graph:
            return []
            
        deps = []
        for src, tgt, data in self.graph.out_edges(source_id, data=True):
            if data.get("type") in ["CALLS", "DEPENDS_ON", "IMPORTS"]:
                deps.append({
                    "symbol_id": tgt,
                    "node_data": self.graph.nodes[tgt],
                    "edge_data": data
                })
        return deps

    def calculate_impact(self, symbol_id: str) -> Dict[str, Any]:
        """Calculate Blast Radius / Impact of a symbol changing."""
        if symbol_id not in self.graph:
            return {"impacted_nodes": []}
            
        # Impact flows backwards along CALLS/DEPENDS_ON/IMPORTS
        # meaning who depends on ME? That's BFS on in_edges.
        
        impacted_nodes = []
        # simple BFS reverse traversal
        visited = set()
        queue = [symbol_id]
        
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            
            for src, tgt, data in self.graph.in_edges(current, data=True):
                if data.get("type") in ["CALLS", "DEPENDS_ON", "IMPORTS", "TESTS"]:
                    if src not in visited:
                        queue.append(src)
                        impacted_nodes.append({
                            "symbol_id": src,
                            "node_data": self.graph.nodes[src],
                            "path_from_target": f"{src} -> {current}"
                        })
                        
        return {"impacted_nodes": impacted_nodes}
