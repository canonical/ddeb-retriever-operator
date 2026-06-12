# Copyright 2025 Canonical
# See LICENSE file for licensing details.

"""Functions for interacting with the workload.

The intention is that this module could be used outside the context of a charm.
"""

import json
import logging
import os
import pathlib
import subprocess
import sys
from grp import getgrnam
from pwd import getpwnam
from textwrap import dedent

from charmlibs import apt, pathops, systemd

logger = logging.getLogger(__name__)

DEST_INSTALL = pathlib.Path("/opt/ddeb-retriever")
DEST_ARCHIVE = pathlib.Path("/srv/ddebs")
DEST_CONF = pathlib.Path("/etc/ddeb-retriever")
SYSTEMD_UNIT = "ddeb-retriever"
USER_DDEB = "ddeb"
USER_WWW = "www-data"
RUN_COMMAND = (str(DEST_INSTALL / "ddeb-retriever"), "-r", str(DEST_ARCHIVE))


def do_conf(lp_sign_config: str):
    """Install the configuration."""
    pathops.ensure_contents(
        path=DEST_CONF / "lp-sign.conf",
        source=lp_sign_config,
        user=USER_DDEB,
        group="root",
        mode=0o440,
    )
    # Informative. Used by subordinate charm.
    pathops.ensure_contents(
        path=DEST_CONF / "conf.json",
        source=json.dumps(
            {
                "install": str(DEST_INSTALL),
                "archive": str(DEST_ARCHIVE),
                "user": str(USER_DDEB),
            }
        ),
        user=USER_DDEB,
        group="root",
        mode=0o440,
    )


def do_deps():
    """Install dependencies."""
    logger.info("Installing dependencies.")
    try:
        apt.update()
        apt.add_package(["git", "systemd", "python3-launchpadlib", "apache2"])
    except apt.Error as e:
        logger.error("Failed to install dependencies: %s", e.message)


def do_user():
    """Create ddeb user."""
    try:
        getpwnam(USER_DDEB)
        return
    except KeyError:
        pass

    logger.info("Creating user %s", USER_DDEB)
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


def do_dirs():
    """Create and manage archive dir."""
    if not DEST_ARCHIVE.exists():
        logger.info("Creating %s", DEST_ARCHIVE)
        DEST_ARCHIVE.mkdir()
    if DEST_ARCHIVE.owner() != USER_DDEB or DEST_ARCHIVE.group() != USER_WWW:
        logger.info("Setting owner of %s", DEST_ARCHIVE)
        ddeb_user = getpwnam(USER_DDEB)
        www_group = getgrnam(USER_WWW)
        os.chown(DEST_ARCHIVE, ddeb_user.pw_uid, www_group.gr_gid)
    if DEST_ARCHIVE.stat().st_mode & 0o777 != 0o755:
        logger.info("Setting perms of %s", DEST_ARCHIVE)
        DEST_ARCHIVE.chmod(0o755)


def do_git(*, remote: str, ref: str):
    """Install or update application from git."""
    if not DEST_INSTALL.exists():
        logger.info("Deploying app from git.")
        _git("clone", remote, str(DEST_INSTALL))

    current_remote = _git("remote", "get-url", "origin").strip()
    if remote != current_remote:
        logger.info("Current remote: %s", current_remote)
        logger.info("Updating origin.")
        _git("remote", "set-url", "origin", remote)
        logger.info("Updating git branch.")
        _git("fetch", "origin")

    current_ref = _git_current_ref()
    if ref != current_ref:
        logger.info("Current git ref: %s", current_ref)
        logger.info("Updating git branch.")
        _git("checkout", f"origin/{ref}")


def do_systemd(schedule: str):
    """Set or update application timers."""
    changed = pathops.ensure_contents(
        path=f"/etc/systemd/system/{SYSTEMD_UNIT}.timer",
        source=dedent(f"""\
        # Managed by ddeb charm.
        [Unit]
        Description=Trigger ddeb-retriever
        [Timer]
        OnCalendar={schedule}
        [Install]
        WantedBy=timers.target
        """),
        mode=0o444,
    )
    changed |= pathops.ensure_contents(
        path="/etc/systemd/system/ddeb-retriever.service",
        source=dedent(f"""\
        # Managed by ddeb charm.
        [Unit]
        Description=Trigger ddeb-retriever
        [Service]
        # Already runs on a schedule, no need to hammer Launchpad on error.
        Restart=no
        User={USER_DDEB}
        ExecStart={" ".join(RUN_COMMAND)}
        Environment=HTTP_PROXY={os.environ["HTTP_PROXY"]}
        Environment=HTTPS_PROXY={os.environ["HTTPS_PROXY"]}
        Environment=NO_PROXY={os.environ["NO_PROXY"]}
        """),
        mode=0o444,
    )
    systemd.daemon_reload()
    # Ensure consistent pause state of units.
    if service_is_paused():
        service_pause()
    else:
        service_resume()


def do_httpd():
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
        logger.info("Reloading apache.")
        systemd.service_reload("apache2.service")


def run_retriever(args):
    """Spawn the retriver with specific arguments."""
    subprocess.check_call(("sudo", "-u", USER_DDEB, "--") + RUN_COMMAND + args)


def update_git(git_ref: str):
    """Update the ddeb_retriever source tree from a git ref."""
    logger.info("Updating git branch.")
    _git("fetch", "origin")
    _git("checkout", f"origin/{git_ref}")


def service_pause():
    """Stop the service and schedule."""
    systemd.service_pause(f"{SYSTEMD_UNIT}.timer")
    systemd.service_stop(f"{SYSTEMD_UNIT}.service")


def service_resume():
    """Restart the importer schedule."""
    systemd.service_enable(f"{SYSTEMD_UNIT}.service")
    systemd.service_resume(f"{SYSTEMD_UNIT}.timer")


def service_is_paused() -> bool:
    """Return whether the importer service is currently disabled."""
    return not systemd.service_running(f"{SYSTEMD_UNIT}.timer")


def _git(*args: str, git_dir=DEST_INSTALL) -> str:
    """Run a git command against app and return output."""
    if args and args[0] == "clone":
        args = ("git", *args)
    else:
        args = ("git", "-C", str(git_dir), *args)
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
