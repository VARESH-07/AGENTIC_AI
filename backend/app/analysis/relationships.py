import uuid
from typing import List, Dict, Tuple
from app.models.db import DBRelationship, DBSymbol
from app.analysis.parser import parse_file

def extract_relationships(repository_id: str, file_path: str, language: str, symbols: List[DBSymbol]) -> List[DBRelationship]:
    """Extracts relationships (CALLS, IMPORTS, CONTAINS, etc.) from a file."""
    try:
        tree, source_code = parse_file(file_path, language)
    except Exception:
        return []

    relationships = []
    symbol_lookup = {sym.qualified_name: sym for sym in symbols}
    file_symbol = next((sym for sym in symbols if sym.type == "FILE" and sym.file_path == file_path), None)
    
    if not file_symbol:
        return []

    # Simple hierarchical containment extraction
    for sym in symbols:
        if sym.type != "FILE":
            parent_qname = ".".join(sym.qualified_name.split(".")[:-1])
            parent_sym = symbol_lookup.get(parent_qname)
            
            # If no parent in qualified name, parent is the FILE
            if parent_sym:
                relationships.append(DBRelationship(
                    id=str(uuid.uuid4()),
                    repository_id=repository_id,
                    source_id=parent_sym.id,
                    target_id=sym.id,
                    type="CONTAINS",
                    metadata=None
                ))
            else:
                relationships.append(DBRelationship(
                    id=str(uuid.uuid4()),
                    repository_id=repository_id,
                    source_id=file_symbol.id,
                    target_id=sym.id,
                    type="CONTAINS",
                    metadata=None
                ))

    # A more sophisticated visitor could be used for CALLS and IMPORTS.
    # For Phase 1 backend, we can implement basic CALLS detection by checking
    # if a function/method AST node contains call expressions.
    
    def visit_for_calls(node, current_symbol):
        if language == "python" and node.type == "call":
            func_node = node.child_by_field_name("function")
            if func_node:
                called_name = source_code[func_node.start_byte:func_node.end_byte].decode('utf8')
                # Attempt naive resolution for intra-file calls
                target_sym = symbol_lookup.get(called_name)
                # In a real system, we'd resolve cross-file using an index
                
                # We'll just emit a "DEPENDS_ON" or "CALLS" with metadata if unresolved
                relationships.append(DBRelationship(
                    id=str(uuid.uuid4()),
                    repository_id=repository_id,
                    source_id=current_symbol.id,
                    target_id=target_sym.id if target_sym else "UNRESOLVED_" + called_name,
                    type="CALLS",
                    metadata=f'{{"called_name": "{called_name}"}}'
                ))
        
        # Traverse children
        for child in node.children:
            # Check if this child enters a new symbol scope
            next_symbol = current_symbol
            # Basic scope tracking
            if child.type in ["function_definition", "method_declaration", "method_definition", "arrow_function"]:
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = source_code[name_node.start_byte:name_node.end_byte].decode('utf8')
                    # Find matching symbol in our extracted symbols
                    matching = [s for s in symbols if s.name == name and s.line_start == child.start_point[0] + 1]
                    if matching:
                        next_symbol = matching[0]

            visit_for_calls(child, next_symbol)

    visit_for_calls(tree.root_node, file_symbol)
    
    return relationships
