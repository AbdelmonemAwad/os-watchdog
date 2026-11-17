#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 Abdelmonem Awad <eg2@live.com>
"""The plugin's scripts against files in a temporary directory, no OPNsense and no chipset:

  * reset_reason.py boot - the "watchdog" field of every record it keeps (true with bit 25, false
    with a value read without it, null with nothing read), and its line in the system log when true,
    whether it read the register itself (a file stands in for it) or took os-xgs-npu's record;
  * status.py - os-xgs-npu's coprocessor watchdog (xgs.general.fastpath_restart) as the page shows
    it: null without os-xgs-npu, its default 1 where the configuration has none, each choice as set,
    0 for a value that is not one, and the page's line for each;
  * on by default: Watchdog.xml's defaults, and a config.xml with no Watchdog section (or none at
    all) taken as on by status.py and by watchdog.sh, whose "status" alone runs here (it reads and
    never arms); off only where the section says 0;
  * on Intel, reset_reason.py's record of what ichwd said as it attached, against kernel messages as
    OPNsense 26.7 printed them in qemu: this boot's only, after the last boot tag; true with its line
    where ichwd attached in the boot before, false where it attached without it, null where it did not
    attach or the line may be an earlier reset's; "boot" before the driver is loaded keeps nothing,
    "ichwd" after it keeps one record a boot; nothing in a virtual machine or on AMD; the page, the
    start hook 10 and both installers.

POSIX only (os.pread, as on the firewall): run it on Linux or FreeBSD, or under WSL.

    python3 tools/test-watchdog.py"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

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


def before(value='0x00080800', cleared=True, after='0x00000800', read_by='os-watchdog'):
    """The record of the boot before this one, as it was kept then."""
    os.makedirs(os.path.dirname(KEPT), exist_ok=True)
    with open(KEPT, 'w', encoding='utf-8') as handle:
        json.dump({'boot': BOOT - 86400, 'read_at': BOOT - 86380, 'value': value, 'cleared': cleared,
                   'after': after, 'read_by': read_by}, handle)


# ---------------------------------------------------------------- 1. the "watchdog" field (fix-13)

check('by_watchdog: bit 25 set', rr.by_watchdog(0x02000800), True)
check('by_watchdog: as the record keeps it', rr.by_watchdog('0x02080800'), True)
check('by_watchdog: a reboot', rr.by_watchdog('0x00080800'), False)
check('by_watchdog: nothing read', rr.by_watchdog(None), None)
check('by_watchdog: every bit set is nothing answering', rr.by_watchdog('0xffffffff'), None)

chipset(0x02000800)
before()
rr.at_boot()
record = kept()
check('read by this plugin, bit 25: watchdog true', (record.get('watchdog'), record.get('read_by')),
      (True, 'os-watchdog'))
check('read by this plugin, bit 25: its line in the system log', len(said()), 1)
check('read by this plugin, bit 25: the line names the reader', 'read by os-watchdog' in ''.join(said()), True)

# a bit 25 that may be one an earlier boot left: null, no line - not a reset to report
for name, earlier in (('no record of the boot before (a first boot)', None),
                      ('the boot before read nothing', {'value': None}),
                      ('the boot before could not clear its bit 25', {'value': '0x02080800', 'cleared': False, 'after': None}),
                      ('the boot before still read bit 25 after clearing', {'value': '0x02080800', 'after': '0x02000800'})):
    chipset(0x02000800)
    if earlier is not None:
        before(**earlier)
    rr.at_boot()
    check('read by this plugin, bit 25, %s: watchdog null, no line' % name, (kept().get('watchdog'), said()), (None, []))
chipset(0x02000800)
before(value='0x00000800', cleared=False, after=None)
rr.at_boot()
check('read by this plugin, bit 25, the boot before could not clear but had no bit 25: watchdog true',
      kept().get('watchdog'), True)

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
before(read_by='os-xgs-npu')
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

chipset(0)
project({'boot': BOOT, 'read_at': BOOT + 20, 'value': '0xffffffff', 'read_by': 'os-xgs-npu'})
before()
rr.at_boot()
check("os-xgs-npu's record, every bit set (nothing answers): watchdog null, no line", (kept().get('watchdog'), said()),
      (None, []))

# os-xgs-npu's mark in the kernel's environment names its record of this boot, whatever the clock did: a step
# between the two boot hooks moves kern.boottime, and the record is still this boot's
real_mark = rr.project_mark
chipset(0)
project({'boot': BOOT - 3600, 'read_at': BOOT - 3580, 'value': '0x02080800', 'read_by': 'os-xgs-npu'})
before()
rr.project_mark = lambda: str(BOOT - 3580)
try:
    rr.at_boot()
    marked = (kept().get('value'), kept().get('watchdog'))
    chipset(0)
    project({'boot': BOOT, 'read_at': BOOT + 20, 'value': '0x02080800', 'read_by': 'os-xgs-npu'})
    before()
    rr.project_mark = lambda: str(BOOT + 999)
    rr.at_boot()
    other = (kept().get('value'), kept().get('watchdog'))
finally:
    rr.project_mark = real_mark
check("os-xgs-npu's mark names its read_at: its record is this boot's, the clock stepped or not", marked,
      ('0x02080800', True))
check("os-xgs-npu's mark names another read: its record is not this boot's", other, (None, None))

# ---------------------------------------------------------------- 2. the coprocessor's watchdog (svc-5-08)

CONF = os.path.join(TOP, 'config.xml')
XGS = os.path.join(TOP, 'xgs-scripts')
os.environ.update({'WATCHDOG_CONF': CONF, 'WATCHDOG_XGS_SCRIPTS': XGS,
                   'WATCHDOG_PIDFILE': os.path.join(TOP, 'os-watchdog.pid'),
                   'WATCHDOG_PROJECT_PIDFILE': os.path.join(TOP, 'xgs-watchdogd.pid'), 'WATCHDOG_KEPT': KEPT})
st = load('status')


def config(xgs=None, watchdog=None):
    """A config.xml with os-xgs-npu's general section (xgs: its inner XML) and os-watchdog's."""
    with open(CONF, 'w', encoding='utf-8') as handle:
        handle.write('<?xml version="1.0"?>\n<opnsense>\n  <system>\n    <hostname>fw</hostname>\n  </system>\n'
                     '  <OPNsense>\n')
        if xgs is not None:
            handle.write('    <XGS version="1.0.0">\n      <general>\n        %s\n      </general>\n    </XGS>\n' % xgs)
        if watchdog is not None:
            handle.write('    <Watchdog version="1.0.0">\n      %s\n    </Watchdog>\n' % watchdog)
        handle.write('  </OPNsense>\n</opnsense>\n')


def xgs_installed(yes, show=None):
    """os-xgs-npu's fastpath.py there or not; show: what its "show" prints (None: nothing - one that does
    not answer)."""
    os.makedirs(XGS, exist_ok=True)
    path = os.path.join(XGS, 'fastpath.py')
    if yes:
        with open(path, 'w', encoding='utf-8') as handle:
            if show is not None:
                handle.write('print(%r)\n' % show)
    elif os.path.exists(path):
        os.remove(path)


xgs_installed(False)
config('<fastpath_restart>1</fastpath_restart>')
check('without os-xgs-npu: no line (null, null)', st.fastpath(), (None, None))
# fastpath.py that does not answer: the setting from config.xml as it reads it, the heartbeat unknown
xgs_installed(True)
config('<watchdog>1</watchdog>')
check('os-xgs-npu, page never saved: its default, 1', st.fastpath(), (1, None))
config(None)
check('os-xgs-npu, no XGS section: its default, 1', st.fastpath()[0], 1)
config('<fastpath_restart></fastpath_restart>')
check('os-xgs-npu, empty value: its default, 1', st.fastpath()[0], 1)
for value in (0, 1, 2, 5, 10):
    config('<watchdog>1</watchdog><fastpath_restart>%d</fastpath_restart>' % value)
    check('os-xgs-npu, fastpath_restart %d: shown as %d' % (value, value), st.fastpath()[0], value)
for raw in ('7', '\u00b2', ' 2x'):
    config('<fastpath_restart>%s</fastpath_restart>' % raw)
    check('os-xgs-npu, %r, not a choice: 0, as fastpath.py takes it' % raw, st.fastpath()[0], 0)
config(None, '<fastpath_restart>2</fastpath_restart>')
check("another section's element of the same name is not os-xgs-npu's", st.fastpath()[0], 1)
# fastpath.py's own show: its setting (an older os-xgs-npu's default 0 included) and whether it has a heartbeat
config('<fastpath_restart>2</fastpath_restart>')
xgs_installed(True, '{"heartbeat": null, "setting": 0, "now": "none"}')
check("fastpath.py's show: its own setting, and no heartbeat on this host", st.fastpath(), (0, False))
xgs_installed(True, '{"heartbeat": {"node": "dev.octep.0.heartbeat", "state": "alive"}, "setting": 5}')
check("fastpath.py's show: a heartbeat to watch", st.fastpath(), (5, True))
xgs_installed(True, '{"heartbeat": null, "setting": 3}')
check("fastpath.py's show with a setting that is not a choice: config.xml's, the heartbeat unknown", st.fastpath(),
      (2, None))
xgs_installed(True)

VOLT = os.path.join(ROOT, 'src', 'opnsense', 'mvc', 'app', 'views', 'OPNsense', 'Watchdog', 'index.volt')
with open(VOLT, encoding='utf-8') as handle:
    volt = handle.read()
for value, words in ((0, 'Say so, and nothing more'), (1, 'Take it up again, or restart'),
                     (2, 'Restart the appliance after 2 minutes'), (5, 'Restart the appliance after 5 minutes'),
                     (10, 'Restart the appliance after 10 minutes')):
    check('the page words choice %d as XGS: Settings does' % value,
          ('%d: "{{ lang._(\'%s\') }}"' % (value, words)) in volt, True)
check('the page links to XGS: Settings', 'href="/ui/xgs/settings"' in volt, True)
check('the page names the setting as XGS: Settings does, and not a "coprocessor watchdog" (that is its hardware '
      'watchdog, os-xgs-npu keeps it fed)', ("<strong>{{ lang._('When the fast path stops') }}</strong>" in volt,
                                             'Coprocessor watchdog' in volt), (True, False))
check('the page says when this host has no heartbeat for the setting',
      "data.fastpath_heartbeat === false" in volt and 'no fast-path heartbeat' in volt, True)

# ---------------------------------------------------------------- 3. on by default (svc-5-08)
# A config.xml with no Watchdog section - a box that never saved the page - arms the timer: the
# model's default, and the decision of both scripts that read config.xml by element name. Only
# watchdog.sh's "status" runs here, which reads and never arms.

MODEL = os.path.join(ROOT, 'src', 'opnsense', 'mvc', 'app', 'models', 'OPNsense', 'Watchdog', 'Watchdog.xml')
model = ET.parse(MODEL).getroot()
check('Watchdog.xml: enabled defaults to 1', model.findtext('items/general/enabled/Default'), '1')
check('Watchdog.xml: timeout defaults to 128', model.findtext('items/general/timeout/Default'), '128')

SH = shutil.which('sh')
WATCHDOG_SH = os.path.join(SCRIPTS, 'watchdog.sh')


def sh_status():
    env = dict(os.environ, WATCHDOG_CONF=CONF, WATCHDOG_PIDFILE=os.path.join(TOP, 'os-watchdog.pid'),
               WATCHDOG_PROJECT=os.path.join(TOP, 'no-os-xgs-npu', 'watchdog.sh'))
    return subprocess.run([SH, WATCHDOG_SH, 'status'], capture_output=True, text=True, env=env,
                          timeout=30).stdout.strip()


xgs_installed(False)
held = subprocess.run(['pgrep', '-x', 'watchdogd'], capture_output=True, text=True).stdout.split()
if held:
    print('skip: a watchdogd runs here (pid %s): watchdog.sh says it holds the timer, not what the settings say'
          % held[0])
for name, xgs, ours, armed in (
        ('no Watchdog section', '<watchdog>1</watchdog>', None, True),
        ('a Watchdog section without enabled', None, '<general><timeout>128</timeout></general>', True),
        ("another plugin's enabled 0, no Watchdog section", '<enabled>0</enabled>', None, True),
        ('enabled 1', None, '<general><enabled>1</enabled><timeout>64</timeout></general>', True),
        ('enabled 0', None, '<general><enabled>0</enabled><timeout>128</timeout></general>', False)):
    config(xgs, ours)
    check('status.py, %s: %s' % (name, 'on' if armed else 'off'), st.setting('enabled', '1') == '1', armed)
    if not held:
        check('watchdog.sh, %s: %s' % (name, 'on' if armed else 'off'), sh_status(),
              'not armed (on in the settings)' if armed else 'not armed (off in the settings)')
os.remove(CONF)
check('status.py, no config.xml at all: on', st.setting('enabled', '1') == '1', True)
if not held:
    check('watchdog.sh, no config.xml at all: on', sh_status(), 'not armed (on in the settings)')
config('<watchdog>1</watchdog>')
check('status.py, no Watchdog section: timeout 128', int(st.setting('timeout', '128')), 128)

# ---------------------------------------------------------------- 4. Intel: what ichwd said (fix-13, d6 a)
# Kernel messages as dmesg(8) printed them on OPNsense 26.7 in qemu - its q35 board's ICH9 TCO timer -
# in the test of 2026-10-29: a boot in which ichwd attached at 460 s and the timer was then let run out,
# so no shutdown follows, and the boot after it, whose ichwd found the timer's record at 44 s and which
# ended in an orderly shutdown. The buffer keeps the boots before, each after the boot tag. Each line as
# the kernel wrote it there, its uptime first; the boots are cut down to the lines read here.

TAG = '---<<BOOT>>---'
INTEL = '[1]   Origin="GenuineIntel"  Id=0x50657  Family=0x6  Model=0x55  Stepping=7'
ISA = '[1] isa0: <ISA bus> on isab0'
ATTACHED_THEN_RESET = '[460] ichwd0: <Intel ICH9 watchdog timer> on isa0'
ATTACH = '[44] ichwd0: <Intel ICH9 watchdog timer> on isa0'
TIMEOUT = '[44] ichwd0: resuming after hardware watchdog timeout'
UPTIME = '[434] Uptime: 7m14s'
# Not seen there, so written as the source prints them: an attach that failed after its line began, as
# newbus says it (sys/kern/subr_bus.c, device_attach()), with ichwd's reason (ichwd_clear_noreboot());
# and the line of a TCO v4 timer, whose I/O and memory the bus prints (sys/isa/isa_common.c,
# isa_print_child()) - its addresses made up
FAILED = ('[25] ichwd0: <Intel ICH9 watchdog timer> on isa0',
          '[25] ichwd0: ICH WDT present but disabled in BIOS or hardware',
          '[25] device_attach: ichwd0 attach returned 6')
V4 = '[31] ichwd0: <Intel Atom C3000 watchdog timer> at port 0x400-0x41f iomem 0xfd6e000c-0xfd6e000f on isa0'
LINE = 'ichwd0: resuming after hardware watchdog timeout'


def booted(*lines):
    """One boot as dmesg prints it: the boot tag, the processor, the ISA bus, then lines."""
    return TAG + '\n' + ''.join(line + '\n' for line in (INTEL, ISA) + lines)


RESET_BOOT = booted(ATTACHED_THEN_RESET)           # ichwd attached, then the timer ran out: no shutdown
NO_ICHWD_BOOT = booted(UPTIME)                     # a boot that never loaded ichwd
TIMEOUT_BOOT = booted(ATTACH, TIMEOUT, UPTIME)     # ichwd found the timer's record, then a shutdown
QUIET_BOOT = booted(ATTACH)                        # ichwd attached and found nothing
KMSG = os.path.join(TOP, 'dmesg.out')
INTEL_DMESG = os.path.join(TOP, 'dmesg-intel.boot')

check('ichwd_said: the timeout line', rr.ichwd_said(booted(ATTACH, TIMEOUT)), ('timeout', LINE))
check('ichwd_said: attached without it', rr.ichwd_said(QUIET_BOOT),
      ('nothing', 'ichwd0: <Intel ICH9 watchdog timer> on isa0'))
check('ichwd_said: a TCO v4 line, with its I/O and memory', rr.ichwd_said(booted(V4))[0], 'nothing')
check('ichwd_said: an attach that failed is none', rr.ichwd_said(booted(*FAILED)), (None, None))
check('ichwd_said: one that failed, then one that attached', rr.ichwd_said(booted(*FAILED + (ATTACH,)))[0],
      'nothing')
check('ichwd_said: no ichwd', rr.ichwd_said(NO_ICHWD_BOOT), (None, None))
check('ichwd_said: no message at all', rr.ichwd_said(None), (None, None))

check("boots: this boot's after the last tag, the boot before's between the last two",
      rr.boots(RESET_BOOT + TIMEOUT_BOOT + QUIET_BOOT, TAG), (TIMEOUT_BOOT[len(TAG):], QUIET_BOOT[len(TAG):], True))
check("boots: before a lone tag, only the end of the boot before", rr.boots('[460] older\n' + QUIET_BOOT, TAG),
      ('[460] older\n', QUIET_BOOT[len(TAG):], False))
check('boots: a tag after a line with no end', rr.boots('[434] Uptime: 7m14s' + QUIET_BOOT, TAG)[1],
      QUIET_BOOT[len(TAG):])
check('boots: no tag, nothing to tell this boot by', (rr.boots(QUIET_BOOT[len(TAG):], TAG),
                                                      rr.boots(QUIET_BOOT, '')), ((None, None, False),) * 2)


def intel(kmsg, earlier=None, dmesg_boot=None, guest='none', tag=TAG):
    """An Intel host: what dmesg prints (kmsg), the record kept before (earlier), dmesg.boot - as rc
    wrote it early in this boot, before the start hooks: by default kmsg without this boot's lines from
    ichwd - kern.vm_guest and kern.boot_tag. No record of this boot yet, no line logged."""
    rr.DMESG, rr.KMSG, rr.VM_GUEST, rr.BOOT_TAG = INTEL_DMESG, KMSG, guest, tag
    if dmesg_boot is None:
        head, _, this = kmsg.rpartition(TAG)
        dmesg_boot = head + _ + '\n'.join(line for line in this.split('\n') if 'ichwd' not in line)
    for path, text in ((KMSG, kmsg), (INTEL_DMESG, dmesg_boot)):
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(text)
    if os.path.exists(KEPT):
        os.remove(KEPT)
    if earlier is not None:
        os.makedirs(os.path.dirname(KEPT), exist_ok=True)
        with open(KEPT, 'w', encoding='utf-8') as handle:
            json.dump(dict({'boot': BOOT - 86400, 'read_at': BOOT - 86380}, **earlier), handle)
    del logged[:]


def fields(*names):
    record = kept()
    return tuple(record.get(name) for name in names)


# ichwd's line, where ichwd attached in the boot before - as in the test of 2026-10-29
intel(RESET_BOOT + TIMEOUT_BOOT)
rr.after_driver()
check("ichwd's line, ichwd attached in the boot before: watchdog true, read by ichwd, no value",
      fields('watchdog', 'read_by', 'said', 'line', 'value', 'bits', 'boot'), (True, 'ichwd', 'timeout', LINE, None, [], BOOT))
check("ichwd's line: its line in the system log, naming ichwd", (len(said()), 'read by ichwd' in ''.join(said())),
      (1, True))

# a line that may be an earlier reset's: the boot before had no ichwd to clear the timer's record
intel(NO_ICHWD_BOOT + TIMEOUT_BOOT)
rr.after_driver()
check("ichwd's line, the boot before whole and without ichwd: watchdog null, no line in the log",
      (fields('watchdog', 'said'), said()), ((None, 'timeout'), []))
# the boot before's messages gone (a lone tag): its record says whether ichwd attached then
for name, earlier, want in (
        ("the record of the boot before says ichwd attached", {'read_by': 'ichwd', 'said': 'nothing'}, True),
        ("the record of the boot before says ichwd did not attach", {'read_by': 'ichwd', 'said': None}, None),
        ('no record of the boot before', None, None),
        ("the record of the boot before is the chipset's, not ichwd's",
         {'read_by': 'os-watchdog', 'value': '0x00080800'}, None)):
    intel('[434] end of an older boot\n' + TIMEOUT_BOOT, earlier)
    rr.after_driver()
    check("ichwd's line, the boot before's messages gone, %s: watchdog %s" % (name, json.dumps(want)),
          fields('watchdog'), (want,))

# attached without the line: false; and an earlier boot's line is not this boot's
intel(RESET_BOOT + QUIET_BOOT)
rr.after_driver()
check('ichwd attached and said nothing: watchdog false, no line in the log',
      (fields('watchdog', 'said', 'line'), said()), ((False, 'nothing', 'ichwd0: <Intel ICH9 watchdog timer> on isa0'), []))
intel(RESET_BOOT + TIMEOUT_BOOT + QUIET_BOOT)
rr.after_driver()
check("the boot before's line is not this boot's: false where this boot's ichwd said nothing",
      fields('watchdog', 'said'), (False, 'nothing'))
intel(RESET_BOOT + TIMEOUT_BOOT + NO_ICHWD_BOOT)
rr.after_driver()
check("the boot before's line is not this boot's: null where ichwd did not attach at this boot",
      (fields('watchdog', 'said', 'note'), said()), ((None, None, 'ichwd did not attach at this boot'), []))
intel(RESET_BOOT + booted(*FAILED))
rr.after_driver()
check('an attach that failed: watchdog null', fields('watchdog', 'said'), (None, None))
intel(TIMEOUT_BOOT[len(TAG):], dmesg_boot=INTEL + '\n')
rr.after_driver()
check("no boot tag in dmesg nor in dmesg.boot: null, this boot's start not there",
      fields('watchdog', 'note'), (None, "this boot's start is not in the kernel's messages"))
intel(RESET_BOOT + TIMEOUT_BOOT, tag='')
rr.after_driver()
check('kern.boot_tag empty: nothing tells this boot from the ones before, null', fields('watchdog', 'said'), (None, None))
# dmesg's buffer has turned over since this boot began (its tag gone); dmesg.boot, written early in it,
# holds the boot's start - with ichwd where the loader had loaded it, and without where it was loaded
# later, which what is left of the buffer cannot tell from a second attach: null
intel(TIMEOUT_BOOT[len(TAG) + 200:], dmesg_boot=RESET_BOOT + booted(ATTACH, TIMEOUT))
rr.after_driver()
check("dmesg without this boot's tag: dmesg.boot's, where the loader's ichwd said it", fields('watchdog', 'said'),
      (True, 'timeout'))
intel('[9000] em0: link state changed to UP\n' + QUIET_BOOT[len(TAG):].split(ISA + '\n')[1], dmesg_boot=RESET_BOOT + booted())
rr.after_driver()
check("dmesg without this boot's tag, dmesg.boot without ichwd: null, this boot's start not there",
      fields('watchdog', 'said', 'note'), (None, None, "this boot's start is not in the kernel's messages"))

# boot (the start hook 07) runs before watchdog.sh loads the driver, and keeps nothing on Intel - not
# even what an ichwd the loader loaded said: one reader a boot, ichwd, so that os-netreport sees one
# record a boot, final. The record of the boot before stays until then.
for name, kmsg in (('ichwd not attached yet', RESET_BOOT + booted()),
                   ('ichwd attached already, the loader loaded it', RESET_BOOT + TIMEOUT_BOOT)):
    intel(kmsg, {'read_by': 'ichwd', 'said': 'nothing', 'watchdog': False})
    rr.at_boot()
    check('boot on Intel, %s: nothing kept, the record of the boot before as it was' % name, fields('boot', 'said'),
          (BOOT - 86400, 'nothing'))
intel(RESET_BOOT + booted(), {'read_by': 'ichwd', 'said': 'nothing', 'watchdog': False})
with open(KMSG, 'a', encoding='utf-8') as handle:
    handle.write(ATTACH + '\n' + TIMEOUT + '\n')
rr.after_driver()
check('ichwd, once watchdog.sh loaded the driver: this boot kept, true', fields('boot', 'watchdog'), (BOOT, True))
first = kept()
with open(KMSG, 'w', encoding='utf-8') as handle:
    handle.write(TIMEOUT_BOOT[len(TAG):])
rr.after_driver()
check('ichwd again in the same boot: the record kept first stays', kept(), first)

# nothing in a virtual machine, as on AMD; nothing for ichwd to say on AMD
intel(RESET_BOOT + TIMEOUT_BOOT, guest='kvm')
rr.at_boot()
rr.after_driver()
check('a virtual machine: neither boot nor ichwd keeps a record', os.path.exists(KEPT), False)
intel(RESET_BOOT + TIMEOUT_BOOT, {'read_by': 'os-watchdog', 'value': '0x00080800'},
      dmesg_boot='CPU: AMD Ryzen Embedded\n  Origin="AuthenticAMD"  Id=0x810f81  Family=0x17  Model=0x18\n')
rr.after_driver()
check("an AMD host: ichwd leaves the chipset's record alone", fields('read_by', 'value', 'boot'),
      ('os-watchdog', '0x00080800', BOOT - 86400))

# the page shows ichwd's record where it is read: on Intel, not in a virtual machine
for name, dmesg_boot, guest, want in (
        ('Intel', booted(), 'none', True), ('Intel in a virtual machine', booted(), 'kvm', False),
        ('AMD family 17h', 'Origin="AuthenticAMD"  Id=0x810f81  Family=0x17\n', 'none', True),
        ('AMD family 16h', 'Origin="AuthenticAMD"  Id=0x730f01  Family=0x16\n', 'none', False)):
    with open(INTEL_DMESG, 'w', encoding='utf-8') as handle:
        handle.write(dmesg_boot)
    st.reset_reason.DMESG, st.reset_reason.VM_GUEST = INTEL_DMESG, guest
    check('status.py, %s: reset_supported %s' % (name, want), st.reset_supported(), want)

with open(VOLT, encoding='utf-8') as handle:
    volt = handle.read()
ichwd_branch = volt[volt.find("if (r && r.read_by === 'ichwd')"):volt.find('if (!r || !r.value)')]
check("the page: ichwd's timeout as bit 25's cause, 'hardware watchdog'",
      "if (r.said === 'timeout') { return {cls: 'warn', what: \"{{ lang._('hardware watchdog') }}\"}; }" in ichwd_branch,
      True)
check("the page: attached without it, 'not the hardware watchdog'",
      "if (r.said === 'nothing') { return {cls: '', what: \"{{ lang._('not the hardware watchdog') }}\"}; }"
      in ichwd_branch, True)
check("the page: ichwd's line as the value read, its cause as a row, and nothing read said so",
      ("ichwd && reset.line ? reset.line" in volt, "if (ichwd && reset.said === 'timeout')" in volt,
       "ichwd && !reset.said ? \"{{ lang._('Nothing was read from ichwd at this boot.') }}\"" in volt),
      (True, True, True))
check('the page says where the record is read: AMD, Intel, not in a virtual machine',
      "On Intel: only whether the hardware watchdog caused it, as ichwd says when it attaches." in volt, True)

# ichwd's word is read after watchdog.sh loads the driver: by the start hook 10 at every boot, and by
# both installers where no record is kept yet, as they read the chipset's
HOOK10 = os.path.join(ROOT, 'src', 'etc', 'rc.syshook.d', 'start', '10-watchdog')
with open(HOOK10, encoding='utf-8') as handle:
    hook = handle.read()
check('start/10: reset_reason.py ichwd after watchdog.sh start',
      0 <= hook.find('/bin/sh "${SCRIPT}" start') < hook.find('"${R}" ichwd') and
      'R=/usr/local/opnsense/scripts/watchdog/reset_reason.py' in hook, True)
AFTER_START = re.compile(r'watchdog\.sh start[^\n]*\n(?:#[^\n]*\n)*\[ -e /var/db/os-watchdog/reset-reason\.json \] \|\|\n'
                         r'\s+/usr/local/opnsense/scripts/watchdog/reset_reason\.py ichwd')
for installer in (('install', 'install.sh'), ('pkg', 'post-install.sh')):
    with open(os.path.join(ROOT, *installer), encoding='utf-8') as handle:
        check('%s: reset_reason.py ichwd after watchdog.sh start, where no record is kept yet' % '/'.join(installer),
              bool(AFTER_START.search(handle.read())), True)

shutil.rmtree(TOP, ignore_errors=True)
print('%d failure(s)' % failures)
sys.exit(1 if failures else 0)
