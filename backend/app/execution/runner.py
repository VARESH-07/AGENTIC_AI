import subprocess
import time
import os
import sys
from typing import Dict, Any

class SafeTestRunner:
    @staticmethod
    def run_tests(repo_path: str, framework: str, test_target: str = None, timeout: int = 60) -> Dict[str, Any]:
        """Safely run tests in a subprocess with timeout."""
        
        # NEVER execute arbitrary shell commands. Use structured arg list.
        # Ensure we run from repo root.
        
        cmd = []
        if framework == "pytest":
            # For this project specifically, if there is a venv, use it, otherwise sys.executable
            venv_python = os.path.join(repo_path, ".venv", "Scripts", "python.exe")
            if os.name != 'nt':
                venv_python = os.path.join(repo_path, ".venv", "bin", "python")
            
            executable = venv_python if os.path.exists(venv_python) else sys.executable
            
            cmd = [executable, "-m", "pytest"]
            if test_target:
                cmd.append(test_target)
        elif framework == "maven":
            cmd = ["mvn", "test"]
            if test_target:
                cmd.append(f"-Dtest={test_target}")
        elif framework == "gradle":
            cmd = ["gradle", "test"]
            if test_target:
                cmd.extend(["--tests", test_target])
        elif framework == "npm":
            cmd = ["npm", "test"]
            if test_target:
                cmd.extend(["--", test_target])
        else:
            raise ValueError(f"Unsupported framework: {framework}")

        start_time = time.time()
        try:
            # shell=False is CRITICAL for safety against command injection
            process = subprocess.run(
                cmd, 
                cwd=repo_path, 
                capture_output=True, 
                text=True, 
                timeout=timeout,
                shell=False
            )
            duration = time.time() - start_time
            
            # Safe truncation of output
            MAX_OUTPUT = 50 * 1024 # 50KB
            stdout = process.stdout[:MAX_OUTPUT]
            
            # Very basic parsing for pytest
            passed = 0
            failed = 0
            if framework == "pytest":
                # Naive parse for demo purposes
                if "failed" in stdout.lower() or process.returncode != 0:
                    failed = 1
                else:
                    passed = 1
                    
            return {
                "exit_code": process.returncode,
                "passed": passed,
                "failed": failed,
                "duration_seconds": round(duration, 2),
                "output": stdout
            }
        except subprocess.TimeoutExpired as e:
            return {
                "exit_code": -1,
                "passed": 0,
                "failed": 1,
                "duration_seconds": timeout,
                "output": f"Execution timed out after {timeout} seconds."
            }
        except Exception as e:
             return {
                "exit_code": -2,
                "passed": 0,
                "failed": 1,
                "duration_seconds": round(time.time() - start_time, 2),
                "output": f"Execution failed: {str(e)}"
            }
