#!/usr/local/bin/python3
#-
# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 Abdelmonem Awad <eg2@live.com>
#
"""
What the page shows, as one JSON object: whether the timer is armed and by whom, the timer itself,
the timeout the running watchdogd asked for, the setting, and the last reset as reset_reason.py kept
it at this boot - or that this host has no reset record at all, as reset_reason.py judges it.

    status.py

Read only: no driver is loaded and nothing is armed or disarmed here - watchdog.sh does that. A
timer whose driver is not loaded yet is reported as not found; Apply loads it.

Where os-xgs-npu is installed, also its setting When the fast path stops (xgs.general.fastpath_restart
in XGS: Settings) - what its fastpath.py does when the coprocessor's fast path stops answering its
heartbeat: 1, its default, takes the coprocessor up again or restarts the appliance; 0 says so and
nothing more; 2, 5 or 10 restarts the appliance after that many minutes - as fastpath.py itself says
it (its "show": its own default and reading, whatever its version), and whether this host has a
heartbeat for it to watch. Where fastpath.py does not answer, the setting read from config.xml as it
reads it, the heartbeat unknown. Both null without os-xgs-npu (2026-11-17).

The paths can be named by WATCHDOG_* in the environment, for tools/test-watchdog.py.
"""

import json
import os
import re
import subprocess
import sys

# The same judgement as the start hook's, from the same file beside this one: an AMD processor of
# family 17h or later, not in a virtual machine (2026-10-29). Its directory is named rather than
# assumed, so that python3 -I, which leaves it out of the path, finds it too.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reset_reason                                                      # noqa: E402

PIDFILE = os.environ.get('WATCHDOG_PIDFILE', '/var/run/os-watchdog.pid')
XGS_SCRIPTS = os.environ.get('WATCHDOG_XGS_SCRIPTS', '/usr/local/opnsense/scripts/xgs')
PROJECT = os.path.join(XGS_SCRIPTS, 'watchdog.sh')
# os-xgs-npu's fast-path watchdog: present with os-xgs-npu, and what its setting governs
FASTPATH = os.path.join(XGS_SCRIPTS, 'fastpath.py')
FASTPATH_CHOICES = (0, 1, 2, 5, 10)
FASTPATH_DEFAULT = 1
PROJECT_PIDFILE = os.environ.get('WATCHDOG_PROJECT_PIDFILE', '/var/run/xgs-watchdogd.pid')
CONF = os.environ.get('WATCHDOG_CONF', '/conf/config.xml')
KEPT = os.environ.get('WATCHDOG_KEPT', '/var/db/os-watchdog/reset-reason.json')
DRIVERS = ('amdsbwd', 'ichwd')


def run(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ''


def alive(pidfile):
    try:
        with open(pidfile, encoding='utf-8') as handle:
            pid = int(handle.read().strip())
        os.kill(pid, 0)
        return pid
    except (OSError, ValueError):
        return None


def setting(name, default):
    """The plugin's own value out of config.xml, by element name, as watchdog.sh reads it."""
    try:
        with open(CONF, encoding='utf-8', errors='replace') as handle:
            text = handle.read()
    except OSError:
        return default
    section = re.search(r'<Watchdog[ >].*?</Watchdog>', text, re.S)
    found = section and re.search(r'<%s>(\d+)</%s>' % (name, name), section.group(0))
    return found.group(1) if found else default


def project_setting():
    """os-xgs-npu's own switch, xgs.general.watchdog - on unless it says 0, as its script reads it."""
    try:
        with open(CONF, encoding='utf-8', errors='replace') as handle:
            text = handle.read()
    except OSError:
        return None
    section = re.search(r'<XGS[ >].*?</XGS>', text, re.S)
    found = section and re.search(r'<watchdog>([01])</watchdog>', section.group(0))
    return (found.group(1) if found else '1') == '1'


def fastpath():
    """(os-xgs-npu's xgs.general.fastpath_restart, whether this host has a heartbeat for it): as its
    fastpath.py shows them, or the setting from config.xml and None where it does not answer; (None,
    None) without os-xgs-npu."""
    if not os.path.exists(FASTPATH):
        return None, None
    try:
        shown = json.loads(run([sys.executable, FASTPATH, 'show']) or 'null')
        minutes = int(shown['setting'])
        if minutes in FASTPATH_CHOICES:
            return minutes, shown.get('heartbeat') is not None
    except (ValueError, KeyError, TypeError):
        pass
    return fastpath_setting(), None


def fastpath_setting():
    """xgs.general.fastpath_restart as fastpath.py reads it: the default where the configuration has
    none, 0 for anything that is not one of the choices."""
    try:
        with open(CONF, encoding='utf-8', errors='replace') as handle:
            text = handle.read()
    except OSError:
        return FASTPATH_DEFAULT
    section = re.search(r'<XGS[ >].*?</XGS>', text, re.S)
    found = section and re.search(r'<fastpath_restart>([^<]*)</fastpath_restart>', section.group(0))
    raw = found.group(1).strip() if found else ''
    if raw == '':
        return FASTPATH_DEFAULT
    try:
        minutes = int(raw)
    except ValueError:
        return 0
    return minutes if minutes in FASTPATH_CHOICES else 0


def timeout_of(pid):
    """The -t a running watchdogd was started with, in seconds."""
    found = re.search(r'-t\s*(\d+)', run(['/bin/ps', '-o', 'args=', '-p', str(pid)]))
    return int(found.group(1)) if found else None


def timer():
    for driver in DRIVERS:
        desc = run(['/sbin/sysctl', '-n', 'dev.%s.0.%%desc' % driver])
        if desc:
            return {'driver': driver, 'desc': desc}
    return {'driver': None, 'desc': None}


def reset():
    try:
        with open(KEPT, encoding='utf-8') as handle:
            record = json.load(handle)
        return record if isinstance(record, dict) else None
    except (OSError, ValueError):
        return None


def main():
    restart, heartbeat = fastpath()
    ours = alive(PIDFILE)
    theirs = alive(PROJECT_PIDFILE) if os.path.exists(PROJECT) else None
    others = [int(p) for p in run(['/bin/pgrep', '-x', 'watchdogd']).split() if p.isdigit()]
    stray = [p for p in others if p not in (ours, theirs)]
    if ours:
        held_by, pid = 'this plugin', ours
    elif os.path.exists(PROJECT):
        held_by, pid = 'os-xgs-npu', theirs
    elif stray:
        held_by, pid = 'another watchdogd', stray[0]
    else:
        held_by, pid = None, None
    print(json.dumps({
        'armed': bool(pid),
        'held_by': held_by,
        'pid': pid,
        'timeout': timeout_of(pid) if pid else None,
        'timer': timer(),
        'enabled': setting('enabled', '1') == '1',
        'configured_timeout': int(setting('timeout', '128')),
        'project_enabled': project_setting() if os.path.exists(PROJECT) else None,
        # os-xgs-npu's When the fast path stops, read only here, and whether this host has a heartbeat
        # for it: null without os-xgs-npu
        'fastpath_restart': restart,
        'fastpath_heartbeat': heartbeat,
        'reset': reset(),
        # False where the chipset keeps no record to read: the page says "not available" then,
        # rather than "not recorded" and whatever an older record kept
        'reset_supported': reset_reason.no_register() is None,
    }))


if __name__ == '__main__':
    main()
