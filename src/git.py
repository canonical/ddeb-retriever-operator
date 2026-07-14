"""Git repo management utilities."""

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def git(*args: str, git_dir: Path | None) -> str:
    """Run a git command against app and return output."""
    if args and args[0] == "clone":
        args = ("git", *args)
    else:
        args = ("git", "-C", str(git_dir), *args)
    return subprocess.check_output(
        args,
        encoding=sys.getfilesystemencoding(),
    )


def get_current_ref(git_dir: Path):
    """Return the current ref for a `git_dir`."""
    try:
        ref = git("describe", "--all", "--exact-match", "--always", "HEAD", git_dir=git_dir)
        return ref.removeprefix("remote/origin/").removeprefix("heads/").strip()
    except subprocess.CalledProcessError:
        try:
            return git("rev-parse", "HEAD", git_dir=git_dir).strip()
        except subprocess.CalledProcessError:
            return None


def ensure_clone(dest: Path, remote: str, ref: str):
    """Ensure the state of a clone exists and matches remote/ref spec."""
    if not dest.exists():
        logger.info("Deploying app from git.")
        git("clone", remote, str(dest), git_dir=None)

    current_remote = git("remote", "get-url", "origin", git_dir=dest).strip()
    if remote != current_remote:
        logger.info("Current remote: %s", current_remote)
        logger.info("Updating origin.")
        git("remote", "set-url", "origin", remote, git_dir=dest)
        logger.info("Updating git branch.")
        git("fetch", "origin", git_dir=dest)

    current_ref = get_current_ref(git_dir=dest)
    if ref != current_ref:
        logger.info("Current git ref: %s", get_current_ref)
        logger.info("Updating git branch.")
        git("checkout", f"origin/{ref}", git_dir=dest)
