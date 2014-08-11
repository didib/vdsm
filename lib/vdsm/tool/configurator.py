# Copyright 2013 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

import argparse
import sys
import traceback

from . import service, expose
from .configurators import \
    CONFIGURED, \
    InvalidConfig, \
    InvalidRun, \
    libvirt, \
    NOT_CONFIGURED, \
    sanlock


__configurers = (
    libvirt.Libvirt(),
    sanlock.Sanlock(),
)


@expose("configure")
def configure(*args):
    """
    configure [-h|...]
    Configure external services for vdsm
    Invoke with -h for complete usage.
    """
    args = _parse_args(*args)
    configurer_to_trigger = []

    sys.stdout.write("\nChecking configuration status...\n\n")
    for c in __configurers:
        if c.getName() in args.modules:
            isconfigured = c.isconfigured()
            override = args.force and isconfigured != CONFIGURED
            if not override and not c.validate():
                raise InvalidConfig(
                    "Configuration of %s is invalid" % c.getName()
                )
            if override or isconfigured == NOT_CONFIGURED:
                configurer_to_trigger.append(c)

    services = []
    for c in configurer_to_trigger:
        for s in c.getServices():
            if service.service_status(s, False) == 0:
                if not args.force:
                    raise InvalidRun(
                        "\n\nCannot configure while service '%s' is "
                        "running.\n Stop the service manually or use the "
                        "--force flag.\n" % s
                    )
                services.append(s)

    for s in services:
        service.service_stop(s)

    sys.stdout.write("\nRunning configure...\n")
    for c in configurer_to_trigger:
        c.configure()
        sys.stdout.write("Reconfiguration of %s is done.\n" % (c.getName(),))

    for s in reversed(services):
        service.service_start(s)
    sys.stdout.write("\nDone configuring modules to VDSM.\n")


@expose("is-configured")
def isconfigured(*args):
    """
    is-configured [-h|...]
    Determine if module is configured
    Invoke with -h for complete usage.
    """
    ret = True
    args = _parse_args(*args)

    m = [
        c.getName() for c in __configurers
        if c.getName() in args.modules and c.isconfigured() == NOT_CONFIGURED
    ]

    if m:
        sys.stdout.write(
            "Modules %s are not configured\n " % ','.join(m),
        )
        ret = False

    if not ret:
        msg = \
            """

One of the modules is not configured to work with VDSM.
To configure the module use the following:
'vdsm-tool configure [module_name]'.

If all modules are not configured try to use:
'vdsm-tool configure --force'
(The force flag will stop the module's service and start it
afterwards automatically to load the new configuration.)
"""
        raise InvalidRun(msg)


@expose("validate-config")
def validate_config(*args):
    """
    validate-config [-h|...]
    Determine if configuration is valid
    Invoke with -h for complete usage.
    """
    ret = True
    args = _parse_args(*args)

    m = [
        c.getName() for c in __configurers
        if c.getName() in args.modules and not c.validate()
    ]

    if m:
        sys.stdout.write(
            "Modules %s contains invalid configuration\n " % ','.join(m),
        )
        ret = False

    if not ret:
        raise InvalidConfig("Config is not valid. Check conf files")


@expose("remove-config")
def remove_config(*args):
    """
    Remove vdsm configuration from conf files
    """
    args = _parse_args(*args)
    failed = False
    for c in __configurers:
        if c.getName() in args.modules:
            try:
                c.removeConf()
                sys.stderr.write(
                    "removed configuration of module %s successfully\n" %
                    c.getName()
                )

            except Exception:
                sys.stderr.write(
                    "can't remove configuration of module %s\n" %
                    c.getName()
                )
                traceback.print_exc(file=sys.stderr)
                failed = True
    if failed:
        raise InvalidRun("Remove configuration failed")


def _parse_args(action, *args):
    parser = argparse.ArgumentParser('vdsm-tool %s' % (action))
    allModules = [n.getName() for n in __configurers]
    parser.add_argument(
        '--module',
        dest='modules',
        choices=allModules,
        default=[],
        metavar='STRING',
        action='append',
        help=(
            'Specify the module to run the action on '
            '(e.g %(choices)s).\n'
            'If non is specified, operation will run for '
            'all related modules.'
        ),
    )
    if action == "configure":
        parser.add_argument(
            '--force',
            dest='force',
            default=False,
            action='store_true',
            help='Force configuration, trigger services restart',
        )
    args = parser.parse_args(args)
    if not args.modules:
        args.modules = allModules
    return args
