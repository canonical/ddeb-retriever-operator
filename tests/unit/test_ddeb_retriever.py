# Copyright 2025 Canonical
# See LICENSE file for licensing details.
import os
from unittest import mock

import charm
import ddeb_retriever


def test_run_retriever_invokes_sudo_as_ddeb_user():
    with mock.patch("subprocess.check_call") as mock_check_call:
        ddeb_retriever.run_retriever()

    mock_check_call.assert_called_once_with(
        ["systemctl", "start", "--wait", "ddeb-retriever.service"]
    )


def test_service_pause_stops_timer_and_service():
    with (
        mock.patch("ddeb_retriever.systemd.service_pause") as mock_pause,
        mock.patch("ddeb_retriever.systemd.service_stop") as mock_stop,
    ):
        ddeb_retriever.service_pause()

    mock_pause.assert_called_once_with("ddeb-retriever.timer")
    mock_stop.assert_called_once_with("ddeb-retriever.service")


def test_service_resume_enables_service_and_resumes_timer():
    with (
        mock.patch("ddeb_retriever.systemd.service_enable") as mock_enable,
        mock.patch("ddeb_retriever.systemd.service_resume") as mock_resume,
    ):
        ddeb_retriever.service_resume()

    mock_enable.assert_called_once_with("ddeb-retriever.service")
    mock_resume.assert_called_once_with("ddeb-retriever.timer")


def test_service_is_paused_true_when_timer_not_running():
    with mock.patch("ddeb_retriever.systemd.service_running", return_value=False):
        assert ddeb_retriever.service_is_paused() is True


def test_service_is_paused_false_when_timer_running():
    with mock.patch("ddeb_retriever.systemd.service_running", return_value=True):
        assert ddeb_retriever.service_is_paused() is False


def test_wb_proxy_config():
    """Whitebox testing for proxy config."""
    os.environ["JUJU_CHARM_HTTP_PROXY"] = "http://theproxy"
    conf_valid = []

    class MockDdeb(charm.DdebCharm):
        on = mock.MagicMock()

        def config_is_valid(self):
            assert os.environ["HTTP_PROXY"] == "http://theproxy"
            conf_valid.append(True)

    # force early return
    ddeb = MockDdeb(mock.MagicMock())
    charm.DdebCharm.apply(ddeb)
    assert conf_valid
