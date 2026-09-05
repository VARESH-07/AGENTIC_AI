import git
from typing import List, Dict, Any, Optional
import os

class GitService:
    @staticmethod
    def get_repo(path: str) -> git.Repo:
        if not os.path.exists(path):
            raise ValueError(f"Repository path does not exist: {path}")
        try:
            return git.Repo(path)
        except git.exc.InvalidGitRepositoryError:
            raise ValueError(f"Not a valid git repository: {path}")

    @staticmethod
    def get_git_history(repo_path: str, max_count: int = 50, path: Optional[str] = None) -> List[Dict[str, Any]]:
        repo = GitService.get_repo(repo_path)
        kwargs = {"max_count": max_count}
        if path:
            kwargs["paths"] = path
            
        history = []
        try:
            for commit in repo.iter_commits(**kwargs):
                history.append({
                    "hash": commit.hexsha,
                    "author": commit.author.name,
                    "email": commit.author.email,
                    "date": commit.authored_datetime.isoformat(),
                    "message": commit.message.strip()
                })
        except git.exc.GitCommandError:
            pass # possibly no commits yet
        return history

    @staticmethod
    def get_commit(repo_path: str, commit_hash: str) -> Dict[str, Any]:
        repo = GitService.get_repo(repo_path)
        # Attempt to resolve by tag, prefix, or full hash
        try:
            commit = repo.commit(commit_hash)
        except Exception:
            # Fallback: search by message prefix if not resolved directly
            found = None
            for c in repo.iter_commits():
                if c.hexsha.startswith(commit_hash) or (c.message and f"[{commit_hash}]" in c.message):
                    found = c
                    break
            if not found:
                raise ValueError(f"Commit {commit_hash} not found")
            commit = found

        stats = commit.stats.total
        changed_files = list(commit.stats.files.keys())
        
        return {
            "hash": commit.hexsha,
            "author": commit.author.name,
            "date": commit.authored_datetime.isoformat(),
            "message": commit.message.strip(),
            "stats": stats,
            "changed_files": changed_files
        }

    @staticmethod
    def get_git_diff(repo_path: str, commit_hash: Optional[str] = None, base_ref: Optional[str] = None, head_ref: Optional[str] = None) -> str:
        repo = GitService.get_repo(repo_path)
        
        if commit_hash:
            # Get diff of this commit vs its parent
            commit = repo.commit(commit_hash)
            if not commit.parents:
                # First commit
                return repo.git.show(commit.hexsha)
            parent = commit.parents[0]
            return repo.git.diff(parent.hexsha, commit.hexsha)
        elif base_ref and head_ref:
            return repo.git.diff(base_ref, head_ref)
        
        # Diff working directory
        return repo.git.diff()

    @staticmethod
    def get_file_history(repo_path: str, file_path: str) -> List[Dict[str, Any]]:
        return GitService.get_git_history(repo_path, max_count=100, path=file_path)

    @staticmethod
    def get_git_blame(repo_path: str, file_path: str) -> List[Dict[str, Any]]:
        repo = GitService.get_repo(repo_path)
        blame_data = []
        try:
            for commit, lines in repo.blame('HEAD', file_path):
                blame_data.append({
                    "commit": commit.hexsha,
                    "author": commit.author.name,
                    "date": commit.authored_datetime.isoformat(),
                    "lines": lines
                })
        except Exception as e:
            print(f"Blame error on {file_path}: {e}")
        return blame_data
