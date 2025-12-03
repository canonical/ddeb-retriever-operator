#!/usr/bin/env python3
# Copyright 2025 Canonical Limited
# See LICENSE file for licensing details.

"""Charm for the ddeb-retriever, debug deb collector."""

import logging
import os
import pathlib
import subprocess
import sys
from grp import getgrnam
from pwd import getpwnam
from textwrap import dedent

import ops
from charmlibs import apt, pathops, systemd
from charms.traefik_k8s.v2.ingress import IngressPerAppRequirer
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus

import charm

logger = logging.getLogger(__name__)

VALID_LOG_LEVELS = ["info", "debug", "warning", "error", "critical"]

DEST_INSTALL = pathlib.Path("/opt/ddeb-retriever")
DEST_ARCHIVE = pathlib.Path("/srv/ddebs")
CONF_GPG_KEY = "gpg-key"
CONF_SCHEDULE = "schedule"
CONF_REF = "git-ref"
CONF_REMOTE = "git-repository"
RUN_COMMAND = (str(DEST_INSTALL / "ddeb-retriever"), "-r", str(DEST_ARCHIVE))
USER_DDEB = "ddeb"
USER_WWW = "www-data"


class DdebCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        os.environ["HTTPS_PROXY"] = os.getenv("JUJU_HTTPS_PROXY", "")
        os.environ["HTTP_PROXY"] = os.getenv("JUJU_HTTP_PROXY", "")
        os.environ["NO_PROXY"] = os.getenv("JUJU_NO_PROXY", "")
        framework.observe(self.on.install, self.apply)
        framework.observe(self.on.config_changed, self.apply)
        framework.observe(self.on.start, self.apply)
        framework.observe(self.on.update_action, self.action_update)
        framework.observe(self.on.run_action, self.action_run)

        self.ingress = IngressPerAppRequirer(self, port=80)

    def apply(self, *_):
        """Apply the full state of the application."""
        if not self.config_is_valid():
            return

        self.do_deps()
        self.do_git()
        self.do_user()
        self.do_dirs()
        self.do_systemd()
        self.do_httpd()
        self.unit.set_ports(80)
        self.unit.status = ActiveStatus()

    def config_is_valid(self) -> bool:
        """Validate configuration."""
        required = {CONF_GPG_KEY, CONF_SCHEDULE, CONF_REF, CONF_REMOTE}
        if missing := required.difference(self.config.keys()):
            self.unit.status = BlockedStatus(f"Needs: {', '.join(missing)}")
            return False
        return True

    def do_deps(self):
        """Install dependencies."""
        logger.info("Installing dependencies.")
        try:
            apt.update()
            apt.add_package(["git", "systemd", "python3-launchpadlib", "apache2"])
        except apt.Error as e:
            logger.error("Failed to install dependencies: %s", e.message)

    def do_user(self):
        """Create ddeb user."""
        try:
            getpwnam(USER_DDEB)
            return
        except KeyError:
            pass

        logging.info("Creating user %s", charm.USER_DDEB)
        subprocess.check_call(
            [
                "adduser",
                "--system",
                "--gid",
                str(getgrnam(USER_WWW).gr_gid),
                "--home",
                "/var/cache/ddeb",
                USER_DDEB,
            ]
        )

    def do_dirs(self):
        """Create and manage archive dir."""
        if not DEST_ARCHIVE.exists():
            logging.info("Creating %s", DEST_ARCHIVE)
            DEST_ARCHIVE.mkdir()
        if DEST_ARCHIVE.owner() != USER_DDEB or DEST_ARCHIVE.group() != USER_WWW:
            logging.info("Setting owner of %s", DEST_ARCHIVE)
            ddeb_user = getpwnam(charm.USER_DDEB)
            www_group = getgrnam(USER_WWW)
            os.chown(DEST_ARCHIVE, ddeb_user.pw_uid, www_group.gr_gid)
        if DEST_ARCHIVE.stat().st_mode & 0o777 != 0o755:
            logging.info("Setting perms of %s", DEST_ARCHIVE)
            DEST_ARCHIVE.chmod(0o755)

    def do_git(self):
        """Install or update application from git."""
        conf_ref = self.config[CONF_REF]
        conf_remote = self.config[CONF_REMOTE]
        if not DEST_INSTALL.exists():
            logger.info("Deploying app from git.")
            _git("clone", conf_remote, DEST_INSTALL)

        current_remote = _git("remote", "get-url", "origin").strip()
        if conf_remote != current_remote:
            logger.info("Current remote: %s", current_remote)
            logger.info("Updating origin.")
            _git("remote", "set-url", "origin", conf_remote)
            logger.info("Updating git branch.")
            _git("fetch", "origin")

        current_ref = _git_current_ref()
        if conf_ref != current_ref:
            logger.info("Current git ref: %s", current_ref)
            logger.info("Updating git branch.")
            _git("checkout", f"origin/{conf_ref}")

    def do_systemd(self):
        """Set or update application timers."""
        changed = pathops.ensure_contents(
            path="/etc/systemd/system/ddeb-retriever.timer",
            source=dedent(f"""\
            # Managed by ddeb charm.
            [Unit]
            Description=Trigger ddeb-retriever
            [Timer]
            OnCalendar={self.config[CONF_SCHEDULE]}
            [Install]
            WantedBy=timers.target
            """),
        )
        changed |= pathops.ensure_contents(
            path="/etc/systemd/system/ddeb-retriever.service",
            source=dedent(f"""\
            # Managed by ddeb charm.
            [Unit]
            Description=Trigger ddeb-retriever
            [Service]
            Restart=on-failure
            User={USER_DDEB}
            ExecStart={" ".join(RUN_COMMAND)}
            Environment=HTTP_PROXY={os.environ["HTTP_PROXY"]}
            Environment=HTTPS_PROXY={os.environ["HTTPS_PROXY"]}
            Environment=NO_PROXY={os.environ["NO_PROXY"]}
            """),
        )
        systemd.daemon_reload()
        systemd.service_enable("ddeb-retriever.timer")
        systemd.service_start("ddeb-retriever.timer")

    def do_httpd(self):
        """Set httpd service."""
        a2conf = pathlib.Path("/etc/apache2/conf-available/ddebs.conf")
        conf_text = dedent("""\
            # Managed by ddeb charm.
            Alias / /srv/ddebs/
            <Directory />
              Options Indexes MultiViews FollowSymLinks
              Require all granted
            </Directory>
            """)

        needs_reload = pathops.ensure_contents(
            path=a2conf,
            source=conf_text,
            user="www-data",
            group="www-data",
            mode=0o644,
        )
        if not os.path.exists("/etc/apache2/conf-enabled/ddebs.conf"):
            subprocess.check_call(["a2enconf", "ddebs"])
            needs_reload = True
        if needs_reload:
            logging.info("Reloading apache.")
            systemd.service_reload("apache2.service")

    def action_update(self, event: ops.ActionEvent):
        """Update the retriever git tree."""
        conf_ref = self.config[CONF_REF]
        logger.info("Updating git branch.")
        _git("fetch", "origin")
        _git("checkout", f"origin/{conf_ref}")

    def action_run(self, event: ops.ActionEvent):
        """Run the retriever."""
        args = tuple(value for value in event.params.get("args", "").split(" ") if value)
        subprocess.check_call(("sudo", "-u", USER_DDEB, "--") + RUN_COMMAND + args)

    def action_pause(self, event: ops.ActionEvent):
        """Pause the service."""
        systemd.service_pause("ddeb-retriever.timer")
        systemd.service_pause("ddeb-retriever.service")
        self.unit.status = MaintenanceStatus()

    def action_resume(self, event: ops.ActionEvent):
        """Resume the service."""
        systemd.service_resume("ddeb-retriever.timer")
        systemd.service_resume("ddeb-retriever.service")
        self.unit.status = ActiveStatus()


def _git(*args, git_dir=DEST_INSTALL) -> str:
    """Run a git command against app and return output."""
    if args and args[0] == "clone":
        args = ["git", *args]
    else:
        args = ["git", "-C", str(git_dir), *args]
    return subprocess.check_output(
        args,
        encoding=sys.getfilesystemencoding(),
    )


def _git_current_ref():
    try:
        ref = _git("describe", "--all", "--exact-match", "--always", "HEAD")
        return ref.removeprefix("remote/origin/").removeprefix("heads/").strip()
    except subprocess.CalledProcessError:
        return _git("rev-parse", "HEAD").strip()


if __name__ == "__main__":  # pragma: nocover
    ops.main(DdebCharm)
