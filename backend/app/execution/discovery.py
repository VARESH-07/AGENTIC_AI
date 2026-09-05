import os
from typing import List

class TestDiscovery:
    @staticmethod
    def detect_framework(repo_path: str) -> str:
        """Heuristic detection of test framework."""
        if os.path.exists(os.path.join(repo_path, "pytest.ini")) or os.path.exists(os.path.join(repo_path, "pyproject.toml")) or os.path.exists(os.path.join(repo_path, "requirements.txt")):
            return "pytest"
        if os.path.exists(os.path.join(repo_path, "pom.xml")):
            return "maven"
        if os.path.exists(os.path.join(repo_path, "build.gradle")):
            return "gradle"
        if os.path.exists(os.path.join(repo_path, "package.json")):
            return "npm"
        
        return "pytest" # Default fallback for this project

    @staticmethod
    def find_tests(repo_path: str, target_symbol: str = None) -> List[str]:
        """Find test files matching standard patterns."""
        test_files = []
        for root, dirs, files in os.walk(repo_path):
            if '.git' in dirs: dirs.remove('.git')
            if 'node_modules' in dirs: dirs.remove('node_modules')
            if 'venv' in dirs: dirs.remove('venv')
            if '.venv' in dirs: dirs.remove('.venv')
            
            for file in files:
                if file.startswith("test_") and file.endswith(".py"):
                    test_files.append(os.path.relpath(os.path.join(root, file), repo_path))
                elif file.endswith("Test.java"):
                    test_files.append(os.path.relpath(os.path.join(root, file), repo_path))
                elif file.endswith(".test.js") or file.endswith(".spec.ts"):
                    test_files.append(os.path.relpath(os.path.join(root, file), repo_path))
                    
        # In a real system, we'd use the graph to filter test_files to only those
        # that explicitly test the target_symbol via the TESTS relationship.
        return test_files
