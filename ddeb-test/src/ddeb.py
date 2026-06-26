# Copyright 2026 Canonical
# See LICENSE file for licensing details.
"""Functions for interacting with the workload."""

import json
import logging
import os
import textwrap
import time

from charmlibs import apt, pathops, systemd

LOG = logging.getLogger(__name__)


def reset_timestamp(ts: int | None):
    """Reset the timestamp to retrieve only newer ddebs."""
    with open("/etc/ddeb-retriever/conf.json") as fd:
        conf = json.load(fd)

    data = str(ts or int(time.time()))
    ts_file = os.path.join(conf["archive"], ".lp-threshold")
    pathops.ensure_contents(
        path=ts_file,
        source=data,
        user=conf["user"],
        group="root",
        mode=0o640,
    )


def install_mock_lpsign():
    """Install test lpsign service."""
    apt.update()
    apt.add_package(["python3-flask"])

    pathops.ensure_contents(
        path="/usr/local/bin/lpsign",
        source=open(os.path.join(os.path.dirname(__file__), "lpsign.py")),
        user="root",
        group="root",
        mode=0o755,
    )
    unit = textwrap.dedent("""\
        [Service]
        Type=simple
        ExecStart=/usr/local/bin/lpsign

        [Install]
        WantedBy=default.target
    """)
    pathops.ensure_contents(
        path="/etc/systemd/system/lpsign.service",
        source=unit,
        user="root",
        group="root",
        mode=0o644,
    )
    systemd.daemon_reload()
    systemd.service_enable("lpsign")
    systemd.service_start("lpsign")


def monkey_patch_site():
    """Patch through python preload to only do "thin" syncs."""
    with open("/etc/ddeb-retriever/conf.json") as fd:
        conf = json.load(fd)

    data = (
        f"import sys; sys.path.append({conf['install']!r}); "
        # make a capturing lambda, because the import won't stay
        "import lpinfo; wrap = lambda f: (lambda *a, **k: f(*a, **k)[:2]); "
        "lpinfo.get_binary_publications = wrap(lpinfo.get_binary_publications)"
    )
    pathops.ensure_contents(
        path="/usr/lib/python3/dist-packages/ddeb.pth",
        source=data,
        user=conf["user"],
        group="root",
        mode=0o640,
    )
