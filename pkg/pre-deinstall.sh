#!/bin/sh
# Copyright (C) 2026 Abdelmonem Awad <eg2@live.com>. BSD 2-Clause License.
#
# Run by pkg(8) BEFORE the files of os-watchdog are removed. The script that disarms the timer is
# itself a packaged file, and the stop hook that would disarm it at shutdown goes with it: a
# watchdogd left running after this would keep the timer armed through the next halt and reset the
# machine a couple of minutes after somebody asked it to power off. So it is stopped here, while
# the script is still on disk.
#
# Not in an upgrade: PKG_UPGRADE is set then, the new package's post-install finds watchdogd still
# running and leaves it, and the host stays covered through the update.
if [ -n "${PKG_UPGRADE}" ]; then
	exit 0
fi

if [ -f /usr/local/opnsense/scripts/watchdog/watchdog.sh ]; then
	/bin/sh /usr/local/opnsense/scripts/watchdog/watchdog.sh stop || true
fi
