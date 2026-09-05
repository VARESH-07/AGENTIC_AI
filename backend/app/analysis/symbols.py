import uuid
from typing import List, Optional, Tuple
from app.models.db import DBSymbol
from app.analysis.parser import parse_file

def extract_symbols(repository_id: str, file_path: str, language: str) -> List[DBSymbol]:
    """Extracts symbols from a file using tree-sitter."""
    try:
        tree, source_code = parse_file(file_path, language)
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return []

    symbols = []
    
    # Simple visitor to extract class and function/method definitions
    def visit(node, parent_name=None):
        node_type = node.type
        
        name = None
        sym_type = None
        
        if language == "python":
            if node_type == "class_definition":
                sym_type = "CLASS"
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = source_code[name_node.start_byte:name_node.end_byte].decode('utf8')
            elif node_type == "function_definition":
                sym_type = "METHOD" if parent_name else "FUNCTION"
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = source_code[name_node.start_byte:name_node.end_byte].decode('utf8')
        
        elif language == "java":
            if node_type == "class_declaration":
                sym_type = "CLASS"
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = source_code[name_node.start_byte:name_node.end_byte].decode('utf8')
            elif node_type == "interface_declaration":
                sym_type = "INTERFACE"
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = source_code[name_node.start_byte:name_node.end_byte].decode('utf8')
            elif node_type == "method_declaration":
                sym_type = "METHOD"
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = source_code[name_node.start_byte:name_node.end_byte].decode('utf8')
                    
        elif language in ["javascript", "typescript"]:
            if node_type == "class_declaration":
                sym_type = "CLASS"
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = source_code[name_node.start_byte:name_node.end_byte].decode('utf8')
            elif node_type == "function_declaration":
                sym_type = "FUNCTION"
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = source_code[name_node.start_byte:name_node.end_byte].decode('utf8')
            elif node_type == "method_definition":
                sym_type = "METHOD"
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = source_code[name_node.start_byte:name_node.end_byte].decode('utf8')
            elif node_type == "interface_declaration":
                sym_type = "INTERFACE"
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = source_code[name_node.start_byte:name_node.end_byte].decode('utf8')

        current_qualified_name = parent_name
        if name and sym_type:
            current_qualified_name = f"{parent_name}.{name}" if parent_name else name
            
            # Simple signature extraction (just taking first line or up to colon/brace for now)
            signature = ""
            docstring = "" # could extract docstrings specifically
            
            symbols.append(DBSymbol(
                id=str(uuid.uuid4()),
                repository_id=repository_id,
                file_path=file_path,
                name=name,
                qualified_name=current_qualified_name,
                type=sym_type,
                line_start=node.start_point[0] + 1,  # 1-indexed
                line_end=node.end_point[0] + 1,
                signature=signature,
                docstring=docstring
            ))

        for child in node.children:
            visit(child, current_qualified_name if (name and sym_type in ["CLASS", "INTERFACE"]) else parent_name)

    visit(tree.root_node)
    
    # Also add the file itself as a symbol
    symbols.append(DBSymbol(
        id=str(uuid.uuid4()),
        repository_id=repository_id,
        file_path=file_path,
        name=file_path.split("/")[-1],
        qualified_name=file_path,
        type="FILE",
        line_start=1,
        line_end=tree.root_node.end_point[0] + 1,
        signature=None,
        docstring=None
    ))
    
    return symbols
