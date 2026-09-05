import tree_sitter_languages
from typing import Optional

def get_parser(language: str):
    """Returns a tree-sitter parser for the specified language."""
    lang_map = {
        "python": "python",
        "java": "java",
        "javascript": "javascript",
        "typescript": "typescript"
    }
    
    ts_lang = lang_map.get(language.lower())
    if not ts_lang:
        raise ValueError(f"Unsupported language: {language}")
        
    return tree_sitter_languages.get_parser(ts_lang)

def parse_file(file_path: str, language: str):
    """Parses a file and returns the tree-sitter Tree."""
    parser = get_parser(language)
    with open(file_path, 'rb') as f:
        source_code = f.read()
    
    return parser.parse(source_code), source_code
