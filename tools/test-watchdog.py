#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 Abdelmonem Awad <eg2@live.com>
"""The plugin's scripts against files in a temporary directory, no OPNsense and no chipset:

  * reset_reason.py boot - the "watchdog" field of every record it keeps (true with bit 25, false
    with a value read without it, null with nothing read), and its line in the system log when true,
    whether it read the register itself (a file stands in for it) or took os-xgs-npu's record.

POSIX only (os.pread, as on the firewall): run it on Linux or FreeBSD, or under WSL.

    python3 tools/test-watchdog.py"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(ROOT, 'src', 'opnsense', 'scripts', 'watchdog')
failures = 0


def check(name, got, want):
    global failures
    ok = got == want
    failures += 0 if ok else 1
    print('%s %s%s' % ('ok  ' if ok else 'FAIL', name, '' if ok else ' - got %r, want %r' % (got, want)))


if not hasattr(os, 'pread'):
    print('FAIL this test needs a POSIX Python (os.pread): run it on Linux or FreeBSD, or under WSL')
    sys.exit(1)

TOP = tempfile.mkdtemp(prefix='os-watchdog-test-')
MEM = os.path.join(TOP, 'mem')
DMESG = os.path.join(TOP, 'dmesg.boot')
KEPT = os.path.join(TOP, 'db', 'reset-reason.json')
PROJECT = os.path.join(TOP, 'xgs', 'reset_reason.py')
PROJECT_KEPT = os.path.join(TOP, 'xgs-db', 'reset-reason.json')
BOOT = 1763337600

os.environ.update({
    'XGS_RESET_MEM': MEM, 'XGS_RESET_OFFSET': '0', 'XGS_RESET_DMESG': DMESG, 'XGS_RESET_STATE': KEPT,
    'XGS_RESET_PROJECT': PROJECT, 'XGS_RESET_PROJECT_STATE': PROJECT_KEPT, 'XGS_RESET_VM_GUEST': 'none',
})
with open(DMESG, 'w', encoding='utf-8') as handle:
    handle.write('CPU: AMD Ryzen Embedded\n  Origin="AuthenticAMD"  Id=0x810f81  Family=0x17  Model=0x18\n')


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), os.path.join(SCRIPTS, name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rr = load('reset_reason')
logged = []
rr.log = logged.append
rr.boot_time = lambda: BOOT


def chipset(value):
    """The register as the file standing in for it holds it; no record kept yet, os-xgs-npu absent."""
    with open(MEM, 'wb') as handle:
        handle.write(value.to_bytes(4, 'little'))
    for path in (KEPT, PROJECT, PROJECT_KEPT):
        if os.path.exists(path):
            os.remove(path)
    del logged[:]


def kept():
    with open(KEPT, encoding='utf-8') as handle:
        return json.load(handle)


def project(record):
    """os-xgs-npu installed, and what it kept at this boot (None: nothing)."""
    for path in (PROJECT, PROJECT_KEPT):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(PROJECT, 'w', encoding='utf-8') as handle:
        handle.write('# stands in for os-xgs-npu\n')
    if record is not None:
        with open(PROJECT_KEPT, 'w', encoding='utf-8') as handle:
            json.dump(record, handle)


def said():
    return [line for line in logged if line.startswith('the hardware watchdog reset this host')]


# ---------------------------------------------------------------- 1. the "watchdog" field (fix-13)

check('by_watchdog: bit 25 set', rr.by_watchdog(0x02000800), True)
check('by_watchdog: as the record keeps it', rr.by_watchdog('0x02080800'), True)
check('by_watchdog: a reboot', rr.by_watchdog('0x00080800'), False)
check('by_watchdog: nothing read', rr.by_watchdog(None), None)

chipset(0x02000800)
rr.at_boot()
record = kept()
check('read by this plugin, bit 25: watchdog true', (record.get('watchdog'), record.get('read_by')),
      (True, 'os-watchdog'))
check('read by this plugin, bit 25: its line in the system log', len(said()), 1)
check('read by this plugin, bit 25: the line names the reader', 'read by os-watchdog' in ''.join(said()), True)

chipset(0x00080800)
rr.at_boot()
check('read by this plugin, a reboot: watchdog false', kept().get('watchdog'), False)
check('read by this plugin, a reboot: no watchdog line', said(), [])

chipset(0)
rr.at_boot()
check('read by this plugin, no cause: watchdog false', (kept().get('value'), kept().get('watchdog')),
      ('0x00000000', False))

chipset(0xFFFFFFFF)
rr.at_boot()
check('nothing answers: no record kept, no watchdog line', (os.path.exists(KEPT), said()), (False, []))

chipset(0x02000800)
project({'boot': BOOT, 'read_at': BOOT + 20, 'value': '0x02080800', 'bits': rr.decode(0x02080800),
         'cleared': True, 'after': '0x00000800', 'read_by': 'os-xgs-npu'})
rr.at_boot()
record = kept()
check("os-xgs-npu's record, bit 25: watchdog true, kept as os-xgs-npu's",
      (record.get('watchdog'), record.get('read_by'), record.get('value')), (True, 'os-xgs-npu', '0x02080800'))
check("os-xgs-npu's record, bit 25: the line names os-xgs-npu", 'read by os-xgs-npu' in ''.join(said()), True)
with open(MEM, 'rb') as handle:
    check("os-xgs-npu's record: the register left alone", handle.read(), (0x02000800).to_bytes(4, 'little'))

chipset(0)
project({'boot': BOOT, 'read_at': BOOT + 20, 'value': '0x00080800', 'bits': rr.decode(0x00080800),
         'read_by': 'os-xgs-npu'})
rr.at_boot()
check("os-xgs-npu's record, a reboot: watchdog false", (kept().get('watchdog'), said()), (False, []))

chipset(0)
project(None)
rr.at_boot()
check('os-xgs-npu kept none for this boot: watchdog null', ('watchdog' in kept(), kept().get('watchdog'), said()),
      (True, None, []))

chipset(0)
project({'boot': BOOT - 86400, 'value': '0x02000800', 'read_by': 'os-xgs-npu'})
rr.at_boot()
check("os-xgs-npu's record of another boot: watchdog null", kept().get('watchdog'), None)

shutil.rmtree(TOP, ignore_errors=True)
print('%d failure(s)' % failures)
sys.exit(1 if failures else 0)
