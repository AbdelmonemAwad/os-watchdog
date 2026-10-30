#!/bin/sh
# Copyright (C) 2026 Abdelmonem Awad <eg2@live.com>. BSD 2-Clause License.
#
# Run by pkg(8) after the files of os-watchdog are in place, on install and on upgrade alike.
# tools/make-package.sh inlines it into the package manifest. The first block and the
# registration are what every OPNsense plugin runs; what install/install.sh does besides - the
# chmod lines, the syntax checks - is not repeated here, for the reasons os-netreport's
# post-install gives.

# configd reads actions_watchdog.conf once, at start.
if [ -f /usr/local/etc/rc.d/configd ]; then
	/usr/local/etc/rc.d/configd restart
fi

# The reset record kept at each boot, made here first so it is never world-readable.
install -d -o root -g wheel -m 0750 /var/db/os-watchdog

if [ -f /usr/local/opnsense/mvc/script/run_migrations.php ]; then
	/usr/local/opnsense/mvc/script/run_migrations.php OPNsense/Watchdog
fi

# In config.xml's system/firmware/plugins, so System > Firmware > Plugins lists it as managed.
if [ -x /usr/local/opnsense/scripts/firmware/register.php ]; then
	/usr/local/opnsense/scripts/firmware/register.php install os-watchdog > /dev/null 2>&1 || true
fi

if [ -f /usr/local/etc/rc.configure_plugins ]; then
	echo "Reloading plugin configuration"
	/usr/local/etc/rc.configure_plugins POST_INSTALL
fi

# What the boot hooks would do, now: the cause of this boot's reset, and the timer armed if the
# setting says so - left alone where os-xgs-npu holds it, and left running across an upgrade.
#
# The cause only where none is kept yet, which is a first install: an upgrade comes after the start
# hook read this boot's record and cleared the register, and a second read after a clock step can
# keep the empty register over the real cause - install/install.sh says why.
[ -e /var/db/os-watchdog/reset-reason.json ] ||
    /usr/local/opnsense/scripts/watchdog/reset_reason.py boot > /dev/null 2>&1 || true
/bin/sh /usr/local/opnsense/scripts/watchdog/watchdog.sh start || true

# The page's place in the menu: the XGS section where os-xgs-npu is installed, System where it is
# not. The menu file is not one of the package's files; place-menu.sh writes it and says which it
# chose.
WHERE=
if [ -x /usr/local/opnsense/scripts/watchdog/place-menu.sh ]; then
	WHERE=$(/usr/local/opnsense/scripts/watchdog/place-menu.sh) || WHERE=
fi
case "${WHERE}" in
xgs)	echo "Hardware Watchdog installed: the page is at XGS > Hardware Watchdog" ;;
own)	echo "Hardware Watchdog installed: the page is at System > Hardware Watchdog" ;;
*)	echo "Hardware Watchdog installed; its menu file was not written: run /usr/local/opnsense/scripts/watchdog/place-menu.sh" ;;
esac
