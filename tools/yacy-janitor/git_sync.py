"""
Git synchronization for host lists.

Automatically commits and pushes changes to host lists.
"""

import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
import structlog

logger = structlog.get_logger()


class GitSync:
    """Handles git operations for host list synchronization."""

    def __init__(self, repo_path: Path, files_to_track: list[Path]):
        self.repo_path = repo_path
        self.files_to_track = files_to_track

    def _run_git(self, *args: str) -> tuple[bool, str]:
        """Run a git command and return (success, output)."""
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)

    def is_git_repo(self) -> bool:
        """Check if the path is a git repository."""
        success, _ = self._run_git("rev-parse", "--git-dir")
        return success

    def has_changes(self) -> bool:
        """Check if there are uncommitted changes to tracked files."""
        for file_path in self.files_to_track:
            if file_path.exists():
                rel_path = file_path.relative_to(self.repo_path) if file_path.is_relative_to(self.repo_path) else file_path
                success, output = self._run_git("status", "--porcelain", str(rel_path))
                if success and output.strip():
                    return True
        return False

    def commit_changes(self, message: Optional[str] = None) -> bool:
        """Stage and commit changes to tracked files."""
        if not self.is_git_repo():
            logger.warning("not_a_git_repo", path=str(self.repo_path))
            return False

        if not self.has_changes():
            logger.debug("no_changes_to_commit")
            return True

        # Stage files
        for file_path in self.files_to_track:
            if file_path.exists():
                rel_path = file_path.relative_to(self.repo_path) if file_path.is_relative_to(self.repo_path) else file_path
                success, output = self._run_git("add", str(rel_path))
                if not success:
                    logger.error("git_add_failed", file=str(rel_path), output=output)
                    return False

        # Commit
        if message is None:
            message = f"Auto-update host lists - {datetime.utcnow().isoformat()}"

        success, output = self._run_git("commit", "-m", message)
        if not success:
            if "nothing to commit" in output:
                return True
            logger.error("git_commit_failed", output=output)
            return False

        logger.info("git_commit_success", message=message)
        return True

    def push_changes(self, remote: str = "origin", branch: Optional[str] = None) -> bool:
        """Push committed changes to remote."""
        if branch is None:
            # Get current branch
            success, output = self._run_git("branch", "--show-current")
            if not success:
                logger.error("git_branch_failed", output=output)
                return False
            branch = output.strip()

        success, output = self._run_git("push", remote, branch)
        if not success:
            logger.error("git_push_failed", output=output)
            return False

        logger.info("git_push_success", remote=remote, branch=branch)
        return True

    def sync(self, message: Optional[str] = None, push: bool = True) -> bool:
        """Commit and optionally push changes."""
        if not self.commit_changes(message):
            return False

        if push:
            return self.push_changes()

        return True


async def auto_sync(
    repo_path: Path,
    files: list[Path],
    message: Optional[str] = None,
    push: bool = True,
) -> bool:
    """Async wrapper for git sync operations."""
    sync = GitSync(repo_path, files)

    # Run in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: sync.sync(message, push)
    )
