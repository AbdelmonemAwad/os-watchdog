#!/bin/sh
# Copyright (C) 2026 Abdelmonem Awad <eg2@live.com>. BSD 2-Clause License.
#
# Run by pkg(8) after the files of os-watchdog have been removed; not during an upgrade. The timer
# was disarmed by pre-deinstall. What is left is what pkg cannot know about: the entry this plugin
# made in config.xml, and the GUI's caches.

if [ -x /usr/local/opnsense/scripts/firmware/register.php ]; then
	/usr/local/opnsense/scripts/firmware/register.php remove os-watchdog > /dev/null 2>&1 || true
fi

# actions_watchdog.conf is gone; configd is still holding it.
if [ -f /usr/local/etc/rc.d/configd ]; then
	/usr/local/etc/rc.d/configd restart
fi

if [ -f /usr/local/etc/rc.configure_plugins ]; then
	echo "Reloading plugin configuration"
	/usr/local/etc/rc.configure_plugins POST_DEINSTALL
fi

# The menu file place-menu.sh wrote is not one of the package's files, so pkg left it, and the
# model's directory with it. The menu is cached by PHP in /var/lib/php/tmp on 26.7, in /tmp before.
rm -f /usr/local/opnsense/mvc/app/models/OPNsense/Watchdog/Menu/Menu.xml
rmdir /usr/local/opnsense/mvc/app/models/OPNsense/Watchdog/Menu /usr/local/opnsense/mvc/app/models/OPNsense/Watchdog 2>/dev/null || true
rm -f /var/lib/php/tmp/opnsense_menu_cache.xml /tmp/opnsense_menu_cache.xml

# Kept on purpose: the settings in config.xml, and /var/db/os-watchdog with the last reset record.
# Remove the record with:  rm -rf /var/db/os-watchdog
echo "Hardware Watchdog removed; the settings in config.xml are kept"
