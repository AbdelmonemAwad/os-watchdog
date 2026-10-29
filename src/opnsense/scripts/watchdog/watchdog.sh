#!/bin/sh
#-
# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 Abdelmonem Awad <eg2@live.com>
#
# The host's hardware watchdog, armed when the setting says so.
#
#   watchdog.sh start     load the timer's driver and start watchdogd, if the setting is on
#   watchdog.sh stop      stop watchdogd, which disarms the timer on its way out
#   watchdog.sh restart   stop, then start - what the page's Apply runs
#   watchdog.sh status    one line: armed, or why not
#
# WHY. Many firewall boards carry a watchdog timer in their chipset - the AMD FCH's (amdsbwd) on the
# Sophos XGS 136 and 3300, Intel's ICH/PCH (ichwd) on many others - and nothing on OPNsense arms it,
# so a host that stops scheduling stays stopped until somebody pulls the power. With watchdogd
# running, a host that stops for longer than the timeout is reset by the hardware.
#
# HOW. watchdogd(8) pats the timer every second and asks for TIMEOUT seconds each time. It is started
# from the boot's start hook and stopped first thing at shutdown, because watchdogd disarms the timer
# only when it is asked to stop: a timer left armed through a halt would reset the machine a couple of
# minutes after somebody asked it to power off.
#
# ONE WATCHDOG AT A TIME. os-xgs-npu has armed the timer itself since 2026-10-17
# (scripts/xgs/watchdog.sh, its setting in XGS: Settings). While that script is installed this one
# leaves the timer to it and only reports: two daemons patting one timer, each disarming it when it
# stops, would leave nobody sure whether the host is covered. The same goes for a watchdogd somebody
# started by hand. This plugin's own settings take over once os-xgs-npu no longer arms it.
#
# Never fails the caller: a host without a timer, the setting off, or the timer held elsewhere is
# reported and exits 0.

PIDFILE=/var/run/os-watchdog.pid
PROJECT=/usr/local/opnsense/scripts/xgs/watchdog.sh
CONF=/conf/config.xml

# The plugin's settings, by element name, out of its section of config.xml; the model's defaults when
# the page was never saved.
setting() {
	/usr/bin/sed -n "/<Watchdog[ >]/,/<\/Watchdog>/s:.*<$1>\([0-9]*\)</$1>.*:\1:p" "${CONF}" 2>/dev/null | /usr/bin/head -1
}

wanted() {
	v=$(setting enabled)
	[ "${v:-1}" = 1 ]
}

timeout() {
	v=$(setting timeout)
	case ${v} in
	64|128|256) echo "${v}" ;;
	*) echo 128 ;;
	esac
}

running() {
	[ -s "${PIDFILE}" ] && /bin/kill -0 "$(/bin/cat "${PIDFILE}")" 2>/dev/null
}

# Who else holds the timer: os-xgs-npu's script, or a watchdogd that is not this plugin's. Empty when
# nobody does.
held_elsewhere() {
	if [ -f "${PROJECT}" ]; then
		echo "os-xgs-npu"
		return
	fi
	ours=$([ -s "${PIDFILE}" ] && /bin/cat "${PIDFILE}")
	for p in $(/bin/pgrep -x watchdogd 2>/dev/null); do
		[ "${p}" = "${ours}" ] && continue
		echo "watchdogd ${p}"
		return
	done
}

# The timer's driver: amdsbwd, then ichwd - each loaded if it is not, and the description of the first
# that attached printed; nothing printed when neither found a timer. Until 2026-10-29 the processor
# chose one, amdsbwd on AMD and ichwd on Intel, but the timer is the chipset's: a virtual machine on
# an AMD host, on qemu's q35 board, has the ICH9 timer that ichwd drives, and would be given amdsbwd,
# which finds nothing there - so it would never be armed. Each driver looks for its own maker's
# controller by its PCI identity and attaches nothing where it is not; one that found nothing stays
# loaded, idle, as ichwd always did on an Intel board without the timer.
timer() {
	for m in amdsbwd ichwd; do
		/sbin/kldstat -q -m "${m}" || /sbin/kldload -n "${m}" 2>/dev/null
		d=$(/sbin/sysctl -n "dev.${m}.0.%desc" 2>/dev/null)
		if [ -n "${d}" ]; then
			echo "${d}"
			return
		fi
	done
}

say() {
	echo "$1"
	/usr/bin/logger -t os-watchdog "$1"
}

stop() {
	if running; then
		PID=$(/bin/cat "${PIDFILE}")
		/bin/kill -TERM "${PID}" 2>/dev/null
		n=0
		while /bin/kill -0 "${PID}" 2>/dev/null && [ ${n} -lt 50 ]; do
			sleep 0.1
			n=$((n + 1))
		done
		/bin/rm -f "${PIDFILE}"
		say "disarmed"
	else
		echo "not armed by this plugin"
	fi
}

start() {
	OTHER=$(held_elsewhere)
	if [ -n "${OTHER}" ]; then
		echo "the timer is held by ${OTHER}; this plugin leaves it to it"
		return
	fi
	if ! wanted; then
		say "the hardware watchdog is switched off in the settings"
		stop
		return
	fi
	if running; then
		echo "armed already, watchdogd $(/bin/cat "${PIDFILE}")"
		return
	fi
	DESC=$(timer)
	if [ -z "${DESC}" ]; then
		say "no hardware watchdog timer this plugin knows on this host; nothing armed"
		return
	fi
	T=$(timeout)
	/usr/sbin/watchdogd -t "${T}" -s 1 -I "${PIDFILE}"
	sleep 1
	if running; then
		say "armed: ${DESC}, ${T} s, watchdogd $(/bin/cat "${PIDFILE}")"
	else
		say "watchdogd did not start; the timer is not armed"
	fi
}

case ${1:-status} in
start)
	start
	;;
stop)
	stop
	;;
restart)
	stop
	start
	;;
status)
	OTHER=$(held_elsewhere)
	if running; then
		echo "armed by this plugin, $(timeout) s, watchdogd $(/bin/cat "${PIDFILE}")"
	elif [ -n "${OTHER}" ]; then
		echo "held by ${OTHER}"
	elif wanted; then
		echo "not armed (on in the settings)"
	else
		echo "not armed (off in the settings)"
	fi
	;;
*)
	echo "usage: watchdog.sh start|stop|restart|status" >&2
	;;
esac
exit 0
