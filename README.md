# Hardware Watchdog for OPNsense

Arms the hardware watchdog of the host, so a host that stops running is reset by its own hardware instead of waiting for someone to pull the power - and reads from the chipset why the host last reset. OPNsense arms no watchdog of its own.

> ~~**Planned - nothing here runs yet.** This repository was opened on 2026-10-22 to hold
> Hardware Watchdog as a plugin of its own. No code has been written or moved into it, and there is no
> release.~~
>
> ~~**Written, not released (2026-10-22).** The code is here; there is no release, and it has not been
> installed on an appliance yet. What was run is listed under [What is tested](#what-is-tested).~~
>
> **1.0.0, the first release (2026-10-25).** Installed and its page opened on an XGS 3300 (OPNsense
> 26.7.7) before the release; updated from XGS: Updates when os-xgs-npu is installed, or by its own
> self-update - see [Updates](#updates).

## What it does

- arms the chipset's watchdog timer with watchdogd(8) at every boot, when the setting says so, and
  disarms it at every shutdown, so turning the machine off stays off. ~~The timer's driver is chosen
  by the processor: `amdsbwd` (the AMD FCH's timer) on AMD, `ichwd` on Intel;~~ The timer's driver is
  the first of `amdsbwd` (the AMD FCH's timer) and `ichwd` (Intel's ICH and PCH, and the ICH9 of
  qemu's q35 board) that attaches - since 2026-10-29: chosen by the processor, a virtual machine on
  an AMD host with the q35 board would be given `amdsbwd`, find no timer, and be left unarmed;
- on AMD processors of family 17h or later, reads at every boot why the host last reset - the
  FCH's `S5_RESET_STATUS` register, one bit for each cause - keeps it, and clears it for the next boot;
  on the machine itself only: not in a virtual machine, where the processor can be a Ryzen or an EPYC
  with no chipset behind the register's address, and never a value with every bit set, which is what
  a read returns where nothing answers - neither is kept or written back (since 2026-10-29);
- **System: Hardware Watchdog** (XGS: Hardware Watchdog when os-xgs-npu is installed): whether the
  timer is armed and by whom, the timer, the last restart with each bit it set, and two settings -
  on or off, and the timeout (64, 128 or 256 seconds).

~~a page in the XGS section of OPNsense's menu~~ - it is under **System**, beside Fan Control (under
**XGS** when os-xgs-npu is installed): the subject is the machine itself, and the plugin is not for
XGS appliances only.

## Beside os-xgs-npu

The code came from os-xgs-npu, which has armed the timer since 2026-10-17 (`scripts/xgs/watchdog.sh`
and its start and stop hooks) and read the reset record since 2026-10-18 (`scripts/xgs/reset_reason.py`
and its start hook). os-xgs-npu has not been changed: both still run there. So this plugin stands
aside while they are installed:

- **the timer** - one watchdogd at a time. While os-xgs-npu's script is installed, this plugin does
  not start its own; the page shows os-xgs-npu's watchdogd and says that its own settings take over
  once os-xgs-npu no longer arms it. A watchdogd started by anything else is left alone the same way;
- **the reset record** - the first read of a boot clears it, so there is one reader a boot.
  os-xgs-npu's hook runs first (start/06); this plugin's (start/07) takes os-xgs-npu's record of
  the boot instead of reading the register.

When os-xgs-npu stops doing either is its owner's decision; nothing here changes it.

## What is tested

On the second XGS 3300, 2026-10-22, from a copy in `/tmp`, nothing installed:

- every PHP file passes `php -l`; both Volt templates compile with Phalcon's compiler;
- `watchdog.sh status` says `held by os-xgs-npu`; `status.py` reports os-xgs-npu's watchdogd armed
  at 128 s on `amdsbwd` ("AMD FCH Rev 41h+ Watchdog Timer");
- `reset_reason.py boot` with os-xgs-npu present took os-xgs-npu's record of the boot
  (`0x00080800`: bit 19, a reboot, and bit 11) without touching the register; with os-xgs-npu
  hidden and a file standing in for the register, it read, decoded and kept `0x02080800`, and a
  second run in the same boot kept the first.

On the first XGS 3300, 2026-10-25, OPNsense 26.7.7 with os-xgs-npu installed, before the release:

- installed by `install/install.sh`: rc 0, its PHP passing `php -l` in the installer;
- the page opened in the browser, its four summary cards reading the status: armed by os-xgs-npu,
  128 s; timer `amdsbwd`; last restart a reboot; value read `0x00080800`;
- its menu place: under **XGS** with os-xgs-npu installed; in its own section, **System**, when
  os-xgs-npu's menu file was set aside, and back under XGS when it was put back (`place-menu.sh`).

On a plain OPNsense 26.7 in qemu, 2026-10-29: the nano image with nothing of os-xgs-npu on it, on
a q35 machine whose ICH9 TCO timer resets the machine when it fires, on an Intel Xeon host.

- **The package.** `os-watchdog-1.0.0.pkg` and `SHA256SUMS` were fetched from the release and the
  sum checked OK. `pkg add` returned 0, and the page is under **System**: System > Hardware Watchdog.
- **ichwd, armed by this plugin.** `ichwd0: <Intel ICH9 watchdog timer>` attached, and the plugin
  armed it at once - `armed: Intel ICH9 watchdog timer, 128 s` - and again at every boot after.
- **The timer firing.** With watchdogd paused (`kill -STOP`), the timer stayed armed and was no
  longer patted. The machine was reset about 270 seconds later, after the ICH9 timer's two runs of
  128 s. At the next boot ichwd said `resuming after hardware watchdog timeout`, and the plugin armed
  it again.
- **Disarming at shutdown.** An orderly reboot ran its stop script and came straight back, with no
  timeout reported. A `shutdown -h` - halted, not powered off - stayed halted for 330 seconds, longer
  than the timer's two runs: turning the machine off stays off.

The ICH9 timer here is qemu's, not an Intel board's; the driver and the plugin's handling of it are
the same.

On the old XGS 3300, 2026-10-29: OPNsense 26.7.7 with os-xgs-npu installed. os-xgs-npu holds the
AMD FCH timer there and reads the reset record itself, so this plugin stands aside. For the test,
os-xgs-npu's watchdog was stopped and its two scripts moved aside, as on a machine without it - its
hooks look for them first - and put back after.

- **amdsbwd, armed by this plugin.** The page's Apply (`configctl watchdog restart`) answered
  `armed: AMD FCH Rev 41h+ Watchdog Timer, 128 s`. Its status said armed by this plugin, and the
  page showed it.
- **The timer firing.** This plugin's watchdogd was killed with SIGKILL, so nothing disarmed the
  timer. The appliance stopped answering about 130 seconds later and came back by itself: the FCH
  timer resets after a single run of 128 s.
- **The reset reason, read by this plugin.** At the next boot its start hook read the chipset's
  record itself and logged `last reset: 0x02000800 - bit 11: no published meaning; bit 25: the
  hardware watchdog expired`, kept as read by os-watchdog. The page showed the last restart as "the
  hardware watchdog". The plugin armed the timer again at that boot.
- **Put back.** With its scripts back, os-xgs-npu armed the timer again, and this plugin stood aside.

Not tested: ~~installing it, the page in a browser~~ (both on 2026-10-25, above), ~~arming and
disarming by this plugin (it stands aside on every appliance that has os-xgs-npu), `ichwd`, the
package (built by `tools/make-package.sh`, added with pkg), and an install on a plain OPNsense,
without os-xgs-npu~~ (all on 2026-10-29 in qemu, above). ~~Still not: `amdsbwd` armed by this plugin,
which needs an AMD machine without os-xgs-npu, and the reset reason read by this plugin itself on
such a machine.~~ Both on the old XGS 3300, with os-xgs-npu's scripts set aside (2026-10-29, above).

## Installation

It is not in the OPNsense plugin repository, so there is no `pkg install os-watchdog`.

**From a checkout** of this repository, on the firewall, as root:

```sh
sh install/install.sh
```

It copies `src/` onto `/usr/local`, checks the PHP with `php -l` and the Python with `py_compile`,
puts the page in the menu (`place-menu.sh`: XGS with os-xgs-npu, System without) and records the
commit for the self-update. Safe to run again: the settings in config.xml are kept.
`sh install/uninstall.sh` disarms the timer first, then removes the files; the settings stay in
config.xml.

**From a release's package.** A release carries `os-watchdog-<version>.pkg` and `SHA256SUMS`, built
by `tools/make-package.sh` in the release workflow; installing it has not been tested yet. Check it
and read it before adding it, as root:

```sh
sha256sum -c SHA256SUMS
pkg info -lF os-watchdog-1.0.0.pkg      # every file it will write
pkg add os-watchdog-1.0.0.pkg
```

`pkg delete os-watchdog` disarms the timer before the files go, and keeps the settings and
`/var/db/os-watchdog`. The same package is built on the firewall from a checkout with
`sh tools/make-package.sh -o /tmp`.

## Updates

Taken by hand, to this repository's **releases**: from **XGS: Updates**, its *Plugins* tab, where an
[os-xgs-npu](https://github.com/AbdelmonemAwad/os-xgs-npu) that lists this plugin is installed - the
tab calls `/usr/local/opnsense/scripts/watchdog/self-update.py`, with `check` to ask and without it
to install - or by running that script. No cron entry runs it. It asks GitHub for the latest release
and, when that is ahead of what is installed, downloads it and runs the `install/install.sh` it
carries - the same script a hand install runs. A change merged on `main` reaches an installed
firewall when it is released, not before.

- **Only forward.** What is installed is recorded in `/usr/local/share/os-watchdog/installed.json` by
  the installer: the commit, from a git checkout or from the `.source-commit` stamp an update leaves
  in the tree. A firewall running something newer than the release is not taken back; an install
  with no commit recorded takes the latest release once.
- **A package install records no commit**, so its first self-update takes the latest release and
  installs it with `install/install.sh`, outside pkg. A package is updated with a newer package
  instead: `pkg add -f`.
- **What happened** is in the system log as `self-update`, in `/usr/local/share/os-watchdog/update.json`,
  and the installer's output in `update.log` beside it.
- `self-update.py check` says what it would do and changes nothing.

~~Not tested yet: an update taken this way - 1.0.0 is the first release, so none has been ahead of
an installed copy.~~ Tested on 2026-10-29 on a plain OPNsense 26.7 in qemu, where the package had
been added with pkg, which records no commit: `self-update.py check` found the release `v1.0.0`
(f3cd9b8781a5) and nothing installed to compare it with, so to be taken. `self-update.py` fetched
its source, ran its `install/install.sh` and answered `updated to v1.0.0 (f3cd9b8781a5)`, which the
system log has too. `installed.json` then recorded that commit, from the stamp, and a second check
found it identical: nothing to take. Not yet: a release ahead of the one installed - 1.0.0 is
still the only release.

## Where it fits

It is one part of the [os-xgs-npu](https://github.com/AbdelmonemAwad/os-xgs-npu) project, which puts OPNsense on Sophos XGS hardware, and works the way its other plugins do: changes by pull request, a release installed from **XGS: Updates** (listed there since os-xgs-npu 0.1.0-alpha.8, and installed with the project's update since 0.1.0-alpha.8.2), its Arabic in [opnsense-arabic](https://github.com/AbdelmonemAwad/opnsense-arabic)'s catalogue.

## Licence

BSD 2-Clause - see [LICENSE](LICENSE).
