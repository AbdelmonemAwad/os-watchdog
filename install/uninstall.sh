#!/bin/sh
#-
# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 Abdelmonem Awad <eg2@live.com>
#
# Remove the Hardware Watchdog plugin files. Settings stay in config.xml and the last reset record in
# /var/db/os-watchdog, so a later reinstall picks up where it left off.

# Disarmed first, while the script that knows how is still here: a timer left armed with nothing to
# stop it at shutdown would reset the machine after somebody asked it to power off.
if [ -f /usr/local/opnsense/scripts/watchdog/watchdog.sh ]; then
    /bin/sh /usr/local/opnsense/scripts/watchdog/watchdog.sh stop || true
fi

rm -rf /usr/local/share/os-watchdog
rm -f /usr/local/etc/rc.syshook.d/start/07-watchdog-reset-reason
rm -f /usr/local/etc/rc.syshook.d/start/10-watchdog
rm -f /usr/local/etc/rc.syshook.d/stop/04-watchdog
rm -f /usr/local/opnsense/service/conf/actions.d/actions_watchdog.conf
rm -rf /usr/local/opnsense/scripts/watchdog
# the menu file place-menu.sh wrote, which is not one of src/'s files
rm -f /usr/local/opnsense/mvc/app/models/OPNsense/Watchdog/Menu/Menu.xml
rmdir /usr/local/opnsense/mvc/app/models/OPNsense/Watchdog/Menu 2>/dev/null || true
rm -rf /usr/local/opnsense/mvc/app/models/OPNsense/Watchdog
rm -rf /usr/local/opnsense/mvc/app/controllers/OPNsense/Watchdog
rm -rf /usr/local/opnsense/mvc/app/views/OPNsense/Watchdog
service configd restart > /dev/null
# PHP keeps them in its own temporary directory on 26.7 (/var/lib/php/tmp); /tmp is where they were
rm -f /var/lib/php/tmp/opnsense_menu_cache.xml /var/lib/php/tmp/opnsense_acl_cache.json \
    /tmp/opnsense_menu_cache.xml /tmp/opnsense_acl_cache.json
echo "Hardware Watchdog removed"
