# Copyright 2025 Canonical
# See LICENSE file for licensing details.
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
