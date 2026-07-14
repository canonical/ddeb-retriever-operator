#!/usr/bin/env python3
# Copyright 2025 Canonical Limited
# See LICENSE file for licensing details.

"""Charm for the ddeb-retriever, debug deb collector."""

import logging
import os
from enum import StrEnum
from typing import cast

import ops
from charms.traefik_k8s.v2.ingress import IngressPerAppRequirer
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus

import ddeb_retriever

logger = logging.getLogger(__name__)


class ConfigKey(StrEnum):
    """Keys for configuring the charm."""

    LP_SIGN_CONFIG = "lp-sign-config"
    SCHEDULE = "schedule"
    GIT_REF = "git-ref"
    GIT_REMOTE = "git-repository"


class DdebCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        os.environ["HTTPS_PROXY"] = os.getenv("JUJU_CHARM_HTTPS_PROXY", "")
        os.environ["HTTP_PROXY"] = os.getenv("JUJU_CHARM_HTTP_PROXY", "")
        os.environ["NO_PROXY"] = os.getenv("JUJU_CHARM_NO_PROXY", "")
        framework.observe(self.on.install, self.apply)
        framework.observe(self.on.config_changed, self.apply)
        framework.observe(self.on.start, self.apply)
        framework.observe(self.on.secret_changed, self.apply)
        framework.observe(self.on.secret_rotate, self.apply)

        framework.observe(self.on.update_action, self.action_update)
        framework.observe(self.on.run_action, self.action_run)
        framework.observe(self.on.pause_action, self.action_pause)
        framework.observe(self.on.resume_action, self.action_resume)

        self.ingress = IngressPerAppRequirer(self, port=80)

    def apply(self, *_):
        """Apply the full state of the application."""
        if not self.config_is_valid():
            return

        ddeb_retriever.do_deps()
        ddeb_retriever.do_git(
            remote=cast(str, self.config[ConfigKey.GIT_REMOTE]),
            ref=cast(str, self.config[ConfigKey.GIT_REF]),
        )
        ddeb_retriever.do_user()
        ddeb_retriever.do_conf(self.lp_sign_config)
        ddeb_retriever.do_dirs()
        ddeb_retriever.do_systemd(cast(str, self.config[ConfigKey.SCHEDULE]))
        ddeb_retriever.do_httpd()
        self.unit.set_ports(80)
        self.update_status()

    @property
    def lp_sign_config(self) -> str:
        """Getter for the lp-sign-config secret.

        Returns the secret or a RuntimeError with a relevant status message.
        """
        try:
            secret = self.model.get_secret(
                id=str(self.model.config[ConfigKey.LP_SIGN_CONFIG])
            ).get_content()
        except ops.SecretNotFoundError as e:
            raise RuntimeError("The configured `lp-sign-config` is not a valid secret URI") from e

        try:
            return secret["config"]
        except KeyError as e:
            raise RuntimeError("lp-sign-config secret is missing the `config` key") from e

    def config_is_valid(self) -> bool:
        """Validate configuration."""
        required: set[ConfigKey] = set(ConfigKey)  # type: ignore
        if missing := required.difference(self.config.keys()):
            self.unit.status = BlockedStatus(f"Needs: {', '.join(missing)}")
            return False

        try:
            self.lp_sign_config
        except RuntimeError as e:
            self.unit.status = BlockedStatus(str(e))
            return False

        return True

    def action_update(self, event: ops.ActionEvent):
        """Update the retriever git tree."""
        conf_ref = cast(str, self.config[ConfigKey.GIT_REF])
        ddeb_retriever.update_git(conf_ref)

    def action_run(self, event: ops.ActionEvent):
        """Run the retriever."""
        ddeb_retriever.run_retriever()

    def action_pause(self, event):
        """Pause the service."""
        ddeb_retriever.service_pause()
        self.update_status()

    def action_resume(self, event: ops.ActionEvent):
        """Resume the service."""
        ddeb_retriever.service_resume()
        self.update_status()

    def update_status(self):
        """Update the charm status based on service status."""
        if ddeb_retriever.service_is_paused():
            self.unit.status = MaintenanceStatus("paused")
        else:
            self.unit.status = ActiveStatus()


if __name__ == "__main__":  # pragma: nocover
    ops.main(DdebCharm)
