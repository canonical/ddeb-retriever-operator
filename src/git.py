import subprocess
import sys
from pathlib import Path


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


def current_ref(git_dir: Path):
    """Return the current ref for a `git_dir`."""
    try:
        ref = git("describe", "--all", "--exact-match", "--always", "HEAD", git_dir=git_dir)
        return ref.removeprefix("remote/origin/").removeprefix("heads/").strip()
    except subprocess.CalledProcessError:
        return git("rev-parse", "HEAD", git_dir=git_dir).strip()
