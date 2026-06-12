# Copyright 2026 Canonical
# See LICENSE file for licensing details.
"""Functions for interacting with the workload."""

import json
import logging
import pathlib
import time

from charmlibs import pathops

DEST_ARCHIVE = pathlib.Path("/srv/ddebs")
LOG = logging.getLogger(__name__)
USER_DDEB = "ddeb"


def reset_timestamp(ts: int | None):
    """Reset the timestamp to retrieve only newer ddebs."""
    with open("/etc/ddeb-retriever/conf.json") as fd:
        conf = json.load(fd)

    data = str(ts or int(time.time()))
    ts_file = pathlib.Path(conf["archive"]) / ".lp-threshold"
    pathops.ensure_contents(
        path=ts_file,
        source=data,
        user=conf["user"],
        group="root",
        mode=0o640,
    )
