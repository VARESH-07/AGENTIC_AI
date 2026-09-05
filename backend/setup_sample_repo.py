import os
import subprocess
import shutil

REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sample-repositories", "auth-demo"))

def run_cmd(cmd, cwd=REPO_DIR):
    subprocess.run(cmd, cwd=cwd, check=True, shell=True)

def write_file(rel_path, content):
    path = os.path.join(REPO_DIR, rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)

import stat

def remove_readonly(func, path, _):
    os.chmod(path, stat.S_IWRITE)
    func(path)

def main():
    if os.path.exists(REPO_DIR):
        shutil.rmtree(REPO_DIR, onerror=remove_readonly)
    os.makedirs(REPO_DIR)

    run_cmd("git init")
    
    # Needs a config for commits
    run_cmd('git config user.email "test@ripple.ai"')
    run_cmd('git config user.name "Ripple Test"')

    # COMMIT 1: User Model & Repository
    write_file("app/models/user.py", '''class User:
    def __init__(self, username, password_hash):
        self.username = username
        self.password_hash = password_hash
''')
    write_file("app/repositories/user_repository.py", '''from app.models.user import User

class UserRepository:
    def __init__(self):
        self.users = {
            "admin": User("admin", "hashed_admin_pass"),
            "user": User("user", "hashed_user_pass")
        }

    def find_user_by_username(self, username: str) -> User:
        return self.users.get(username)
''')
    run_cmd("git add .")
    run_cmd('git commit -m "Initial commit: User model and UserRepository"')

    # COMMIT 2: Token Service
    write_file("app/services/token_service.py", '''class TokenService:
    def generate_token(self, user) -> str:
        return f"token_for_{user.username}"
        
    def validate_token(self, token: str) -> bool:
        return token.startswith("token_for_")
''')
    run_cmd("git add .")
    run_cmd('git commit -m "Feature: TokenService with JWT generation and validation"')

    # COMMIT 3: Auth Service & Login Controller & Tests
    write_file("app/services/auth_service.py", '''from app.repositories.user_repository import UserRepository
from app.services.token_service import TokenService

class AuthService:
    def __init__(self):
        self.user_repo = UserRepository()
        self.token_service = TokenService()
        
    def authenticate(self, username, password) -> str:
        user = self.user_repo.find_user_by_username(username)
        if not user:
            return None
        # Valid password check
        if password == user.password_hash.replace("hashed_", "") + "_pass":
            return self.token_service.generate_token(user)
        return None
''')
    write_file("app/controllers/login_controller.py", '''from app.services.auth_service import AuthService

class LoginController:
    def __init__(self):
        self.auth_service = AuthService()
        
    def login(self, username, password):
        token = self.auth_service.authenticate(username, password)
        if token:
            return {"status": "success", "token": token}
        return {"status": "error", "message": "Invalid credentials"}
''')
    write_file("tests/test_auth.py", '''import pytest
from app.services.auth_service import AuthService

def test_authenticate_success():
    auth = AuthService()
    token = auth.authenticate("admin", "admin")
    assert token == "token_for_admin"

def test_authenticate_failure():
    auth = AuthService()
    token = auth.authenticate("admin", "wrong")
    assert token is None
''')
    write_file("pytest.ini", "[pytest]\npythonpath = .\n")
    
    run_cmd("git add .")
    run_cmd('git commit -m "Feature: AuthService and LoginController with full test suite"')

    # COMMIT 4 (Regression)
    write_file("app/services/auth_service.py", '''from app.repositories.user_repository import UserRepository
from app.services.token_service import TokenService

class AuthService:
    def __init__(self):
        self.user_repo = UserRepository()
        self.token_service = TokenService()
        
    def authenticate(self, username, password) -> str:
        user = self.user_repo.find_user_by_username(username)
        if not user:
            return None
        # BUG: Flipped validation logic causing regression
        if password != user.password_hash.replace("hashed_", "") + "_pass":
            return self.token_service.generate_token(user)
        return None
''')
    run_cmd("git add .")
    run_cmd('git commit -m "[abc123] Fix: update password verification logic in AuthService"')
    # Tag it to ensure we can look it up reliably
    run_cmd('git tag abc123')
    
    print("Sample repository setup complete!")

if __name__ == "__main__":
    main()
