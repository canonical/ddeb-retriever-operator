#!/usr/bin/env python3
# Copyright 2026 Canonical
# See LICENSE file for licensing details.

"""ddeb-retriever test sidecar."""

import logging

import ops

import ddeb

logger = logging.getLogger(__name__)


class DdebTestCharm(ops.CharmBase):
    """Charm the application."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        framework.observe(self.on.reset_timestamp_action, self.reset_timestamp_action)
        framework.observe(self.on.install, self.install)

    def reset_timestamp_action(self, event: ops.ActionEvent):
        """Reset the fetch last timestamp."""
        ts = event.params.get("timestamp")
        ddeb.reset_timestamp(ts)

    def install(self, event):
        """Install hook."""
        ddeb.monkey_patch_site()
        ddeb.install_mock_lpsign()
        self.unit.status = ops.ActiveStatus()


if __name__ == "__main__":  # pragma: nocover
    ops.main(DdebTestCharm)
