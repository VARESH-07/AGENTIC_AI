import os
import re
from typing import List, Dict, Any, Optional

class SearchService:
    @staticmethod
    def search_code(repo_path: str, query: str, context_lines: int = 2) -> List[Dict[str, Any]]:
        results = []
        try:
            pattern = re.compile(query)
        except re.error:
            # Fallback to literal search if invalid regex
            pattern = re.compile(re.escape(query))
            
        for root, dirs, files in os.walk(repo_path):
            if '.git' in dirs:
                dirs.remove('.git')
            # optionally skip build/node_modules/venv
            for skip in ['node_modules', 'venv', '.venv', '__pycache__', 'build', 'dist']:
                if skip in dirs:
                    dirs.remove(skip)
                    
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        
                    for i, line in enumerate(lines):
                        if pattern.search(line):
                            start = max(0, i - context_lines)
                            end = min(len(lines), i + context_lines + 1)
                            context = [l.rstrip() for l in lines[start:end]]
                            
                            results.append({
                                "file": os.path.relpath(file_path, repo_path),
                                "line": i + 1,
                                "content": line.rstrip(),
                                "context": context
                            })
                except UnicodeDecodeError:
                    pass # Skip binary files
        return results

    @staticmethod
    def read_file(repo_path: str, file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
        full_path = os.path.join(repo_path, file_path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            if start_line is not None and end_line is not None:
                start = max(0, start_line - 1)
                end = min(len(lines), end_line)
                return "".join(lines[start:end])
                
            return "".join(lines)
        except UnicodeDecodeError:
            raise ValueError(f"File appears to be binary: {file_path}")

    @staticmethod
    def find_definition(db_symbols: List[Any], symbol_name: str) -> Optional[Any]:
        # Search exact qualified name first
        for sym in db_symbols:
            if sym.qualified_name == symbol_name:
                return sym
        # Search by short name
        for sym in db_symbols:
            if sym.name == symbol_name:
                return sym
        return None
