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

PIDFILE = '/var/run/os-watchdog.pid'
PROJECT = '/usr/local/opnsense/scripts/xgs/watchdog.sh'
PROJECT_PIDFILE = '/var/run/xgs-watchdogd.pid'
CONF = '/conf/config.xml'
KEPT = '/var/db/os-watchdog/reset-reason.json'
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
        'reset': reset(),
        # False where the chipset keeps no record to read: the page says "not available" then,
        # rather than "not recorded" and whatever an older record kept
        'reset_supported': reset_reason.no_register() is None,
    }))


if __name__ == '__main__':
    main()
