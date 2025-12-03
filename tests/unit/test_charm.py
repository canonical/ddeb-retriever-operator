# Copyright 2025 Canonical
# See LICENSE file for licensing details.
#
# To learn more about testing, see https://documentation.ubuntu.com/ops/latest/explanation/testing/
from unittest import mock

import charm


@mock.patch("subprocess.check_output")
def test_git_clone_args(mock_popen):
    """Test git clone doesn't try to change dir."""
    charm._git("clone", "http://repo", "/target")
    mock_popen.assert_called_once_with(
        ["git", "clone", "http://repo", "/target"], encoding=mock.ANY
    )


@mock.patch("subprocess.check_output")
def test_git_passes_context(mock_popen):
    """Test git clone doesn't try to change dir."""
    charm._git("branch")
    mock_popen.assert_called_once_with(
        ["git", "-C", "/opt/ddeb-retriever", "branch"], encoding=mock.ANY
    )
