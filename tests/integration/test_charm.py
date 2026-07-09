# Copyright 2025 Canonical
# See LICENSE file for licensing details.
#
# The integration tests use the Jubilant library. See https://documentation.ubuntu.com/jubilant/
# To learn more about testing, see https://documentation.ubuntu.com/ops/latest/explanation/testing/

import logging
import pathlib

import jubilant
import pytest
import requests
import yaml

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(pathlib.Path("charmcraft.yaml").read_text())
APP = METADATA["name"]


@pytest.mark.dependency()
def test_deploy(charm: pathlib.Path, juju: jubilant.Juju):
    """Deploy the charm under test."""
    juju.deploy(charm.resolve(), app=APP, config={})
    secret_path = pathlib.Path(__file__).parent / "mock_lp_config.conf"
    secret_uri = juju.add_secret("lpsign", {"config": secret_path.read_text()})
    juju.grant_secret("lpsign", app=APP)
    juju.config(APP, values={"lp-sign-config": secret_uri})
    juju.wait(jubilant.all_active)

    # service is listing
    ip_addr = next(iter(juju.status().apps[APP].units.values())).public_address
    assert 200 == requests.get(f"http://{ip_addr}").status_code

    # timers are active
    juju.exec(f"systemctl is-active {APP}.timer", unit=f"{APP}/leader")


@pytest.mark.dependency(depends=["test_deploy"])
def test_retriever(juju: jubilant.Juju):
    """Run a "short" retriever pass."""
    # Add devel charm. Patches to truncate sync and mock signing.
    juju.deploy(list(pathlib.Path("ddeb-test").glob("*.charm"))[0], app="test")
    juju.integrate("test", APP)
    juju.wait(jubilant.all_active)

    juju.run(unit="ddeb-retriever/leader", action="run", wait=600)
    # ensure the run ended correctly
    with pytest.raises(jubilant.TaskError):
        juju.exec(f"systemctl is-failed {APP}.service", unit=f"{APP}/leader")

    # Check for signed release
    ip_addr = next(iter(juju.status().apps[APP].units.values())).public_address
    response = requests.get(f"http://{ip_addr}/dists/resolute/Release.gpg")
    assert 200 == response.status_code
    assert response.text.startswith("-----BEGIN ")
    # Check for inline signature
    response = requests.get(f"http://{ip_addr}/dists/resolute/InRelease")
    assert 200 == response.status_code
    assert "SIGNED MESSAGE" in response.text


@pytest.mark.dependency(depends=["test_deploy"])
def test_pause_resume(juju: jubilant.Juju):
    """Test service maintenance actions."""
    assert juju.status().apps[APP].app_status.current == "active"

    # idempotency check
    for call_pass in range(2):
        print("pause pass", call_pass)
        juju.run(unit=f"{APP}/leader", action="pause")
        juju.wait(jubilant.any_maintenance)
        with pytest.raises(jubilant.TaskError):
            juju.exec(f"systemctl is-active {APP}.timer", unit=f"{APP}/leader")
        with pytest.raises(jubilant.TaskError):
            juju.exec(f"systemctl is-active {APP}.service", unit=f"{APP}/leader")

    # idempotency check
    for call_pass in range(2):
        print("resume pass", call_pass)
        juju.run(unit=f"{APP}/leader", action="resume")
        juju.wait(jubilant.all_active)
        cmd = juju.exec(f"systemctl is-active {APP}.timer", unit=f"{APP}/leader")
        assert cmd.return_code == 0, f"resume pass {call_pass}"


@pytest.mark.dependency(depends=["test_deploy"])
def test_proxy(juju: jubilant.Juju):
    """Test service maintenance actions."""
    try:
        juju.model_config(values={"juju-http-proxy": "http://myproxy"})
        # force charm hook without redeploy
        juju.config(APP, values={"schedule": "weekly"})
        juju.wait(jubilant.all_active)
        task = juju.exec(f"systemctl show {APP}.service", unit=f"{APP}/leader")
        assert "HTTP_PROXY=http://myproxy" in task.stdout
    finally:
        juju.model_config(reset={"juju-http-proxy"})
        juju.config(APP, reset={"schedule"})
        juju.wait(jubilant.all_active)
