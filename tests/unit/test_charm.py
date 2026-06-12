# Copyright 2025 Canonical
# See LICENSE file for licensing details.
from unittest import mock

import ddeb_retriever


@mock.patch("subprocess.check_output")
def test_git_clone_args(mock_popen):
    """Test git clone doesn't try to change dir."""
    ddeb_retriever._git("clone", "http://repo", "/target")
    mock_popen.assert_called_once_with(
        ("git", "clone", "http://repo", "/target"), encoding=mock.ANY
    )


@mock.patch("subprocess.check_output")
def test_git_passes_context(mock_popen):
    """Test git clone doesn't try to change dir."""
    ddeb_retriever._git("branch")
    mock_popen.assert_called_once_with(
        ("git", "-C", "/opt/ddeb-retriever", "branch"), encoding=mock.ANY
    )
