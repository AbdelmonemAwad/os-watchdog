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
  disarms it at every shutdown, so turning the machine off stays off. The timer's driver is chosen by
  the processor: `amdsbwd` (the AMD FCH's timer) on AMD, `ichwd` on Intel;
- on AMD processors of family 17h or later, reads at every boot why the host last reset - the
  FCH's `S5_RESET_STATUS` register, one bit for each cause - keeps it, and clears it for the next boot;
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

Not tested: ~~installing it, the page in a browser~~ (both on 2026-10-25, above), arming and
disarming by this plugin (it stands aside on every appliance that has os-xgs-npu), `ichwd`, the
package (built by `tools/make-package.sh`, added with pkg), and an install on a plain OPNsense,
without os-xgs-npu.

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

Not tested yet: an update taken this way - 1.0.0 is the first release, so none has been ahead of an
installed copy.

## Where it fits

It is one part of the [os-xgs-npu](https://github.com/AbdelmonemAwad/os-xgs-npu) project, which puts OPNsense on Sophos XGS hardware, and works the way its other plugins do: changes by pull request, a release installed from **XGS: Updates** (once it is listed there), its Arabic in [opnsense-arabic](https://github.com/AbdelmonemAwad/opnsense-arabic)'s catalogue.

## Licence

BSD 2-Clause - see [LICENSE](LICENSE).
