"""Git 同步服务（FR-12，阶段三）。

基于 GitPython，对 notebooks 目录提供 status / commit / push / pull。
仓库未初始化时给出引导性错误信息，而不是直接崩溃。
"""
from __future__ import annotations

import os


class GitError(Exception):
    pass


class GitService:
    def __init__(self, repo_dir: str, branch: str = "main") -> None:
        self.repo_dir = os.path.abspath(repo_dir)
        self.branch = branch

    # ------------------------------------------------------------------
    def status(self) -> dict:
        repo = self._repo(required=False)
        if repo is None:
            return {"initialized": False, "branch": self.branch, "changed": []}
        return {
            "initialized": True,
            "branch": self._current_branch(repo),
            "changed": list(repo.untracked_files)
            + [i.a_path or "" for i in repo.index.diff(None)],
        }

    def commit(self, message: str) -> dict:
        repo = self._repo()
        repo.git.add(A=True)
        if not repo.index.diff("HEAD") and not repo.untracked_files:
            return {"committed": False, "reason": "没有变更"}
        repo.index.commit(message or "update notes")
        return {"committed": True, "sha": repo.head.commit.hexsha[:8]}

    def push(self, remote: str = "origin") -> dict:
        repo = self._repo()
        repo.git.push(remote, self._current_branch(repo))
        return {"pushed": True, "remote": remote}

    def pull(self, remote: str = "origin") -> dict:
        repo = self._repo()
        repo.git.pull(remote, self._current_branch(repo))
        return {"pulled": True, "remote": remote}

    def init_repo(self) -> dict:
        from git import Repo

        repo = Repo.init(self.repo_dir)
        return {"initialized": True, "path": self.repo_dir}

    # ------------------------------------------------------------------
    def _repo(self, required: bool = True):
        try:
            from git import InvalidGitRepositoryError, Repo
        except ImportError as exc:
            raise GitError("未安装 GitPython，请先 pip install -r requirements.txt") from exc

        try:
            return Repo(self.repo_dir)
        except InvalidGitRepositoryError:
            if required:
                raise GitError(
                    "notebooks 目录还不是 Git 仓库，请先执行 git init 或调用 /api/git/init"
                )
            return None

    def _current_branch(self, repo) -> str:
        try:
            return str(repo.active_branch)
        except TypeError:
            return self.branch
