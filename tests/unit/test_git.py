# Copyright 2025 Canonical
# See LICENSE file for licensing details.
import tempfile
from pathlib import Path
from unittest import mock

import git


@mock.patch("subprocess.check_output")
def test_git_clone_args(mock_popen):
    """Test git clone doesn't try to change dir."""
    git.git("clone", "http://repo", "/target", git_dir=None)
    mock_popen.assert_called_once_with(
        ("git", "clone", "http://repo", "/target"), encoding=mock.ANY
    )


@mock.patch("subprocess.check_output")
def test_git_passes_context(mock_popen):
    """Test git clone doesn't try to change dir."""
    git.git("branch", git_dir=Path("/opt/dest"))
    mock_popen.assert_called_once_with(("git", "-C", "/opt/dest", "branch"), encoding=mock.ANY)


def test_ensure_clone_clones_when_dest_is_missing():
    with (
        tempfile.TemporaryDirectory() as tmp_dir,
        mock.patch("git.git") as mock_git,
        mock.patch("git.get_current_ref", return_value="main"),
    ):
        dest = Path(tmp_dir)
        dest.rmdir()
        mock_git.return_value = "https://repo\n"
        git.ensure_clone(dest=dest, remote="https://repo", ref="main")

    mock_git.assert_has_calls(
        [
            mock.call("clone", "https://repo", str(dest), git_dir=None),
            mock.call("remote", "get-url", "origin", git_dir=dest),
        ]
    )


def test_ensure_clone_updates_remote_when_it_differs():
    dest = Path("/opt/dest")
    with (
        mock.patch.object(Path, "exists", return_value=True),
        mock.patch("git.git") as mock_git,
        mock.patch("git.get_current_ref", return_value="main"),
    ):
        mock_git.return_value = "https://old-repo\n"
        git.ensure_clone(dest=dest, remote="https://repo", ref="main")

    mock_git.assert_has_calls(
        [
            mock.call("remote", "set-url", "origin", "https://repo", git_dir=dest),
            mock.call("fetch", "origin", git_dir=dest),
        ]
    )


def test_ensure_clone_checks_out_ref_when_it_differs():
    dest = Path("/opt/dest")
    with (
        mock.patch.object(Path, "exists", return_value=True),
        mock.patch("git.git") as mock_git,
        mock.patch("git.get_current_ref", return_value="old-ref"),
    ):
        mock_git.return_value = "https://repo\n"
        git.ensure_clone(dest=dest, remote="https://repo", ref="main")

    mock_git.assert_has_calls(
        [
            mock.call("checkout", "origin/main", git_dir=dest),
        ]
    )


def test_ensure_clone_noops_when_remote_and_ref_already_match():
    dest = Path("/opt/dest")
    with (
        mock.patch.object(Path, "exists", return_value=True),
        mock.patch("git.git") as mock_git,
        mock.patch("git.get_current_ref", return_value="main"),
    ):
        mock_git.return_value = "https://repo\n"
        git.ensure_clone(dest=dest, remote="https://repo", ref="main")

    mock_git.assert_called_once_with("remote", "get-url", "origin", git_dir=dest)
