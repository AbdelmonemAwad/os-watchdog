# Hardware Watchdog for OPNsense

Arms the hardware watchdog of the host, so a host that stops running is reset by its own hardware instead of waiting for someone to pull the power - and reads from the chipset why the host last reset. OPNsense arms no watchdog of its own.

> **Planned - nothing here runs yet.** This repository was opened on 2026-10-22 to hold
> Hardware Watchdog as a plugin of its own. No code has been written or moved into it, and there is no
> release.

## What it is to do

- the AMD FCH watchdog timer armed with watchdogd, when the setting says so;
- the reason of the last reset, as the chipset recorded it, read at every boot;
- a page in the XGS section of OPNsense's menu.

## Where its first code comes from

Its first code is to be what os-xgs-npu does in the background today: `scripts/xgs/watchdog.sh` with its start and stop hooks, and `scripts/xgs/reset_reason.py` with its start hook - moved here, with the setting that turns the watchdog on.

## Where it fits

It is one part of the [os-xgs-npu](https://github.com/AbdelmonemAwad/os-xgs-npu) project, which puts OPNsense on Sophos XGS hardware, and works the way its other plugins do: changes by pull request, a release installed from **XGS: Updates**, its Arabic in [opnsense-arabic](https://github.com/AbdelmonemAwad/opnsense-arabic)'s catalogue.

## Licence

BSD 2-Clause - see [LICENSE](LICENSE).
