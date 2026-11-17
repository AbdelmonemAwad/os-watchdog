#!/usr/local/bin/python3
#-
# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 Abdelmonem Awad <eg2@live.com>
#
"""
Why the host last reset, as its own chipset recorded it.

    reset_reason.py boot     at boot: read the record, log it, keep it, and clear it for the next boot;
                             on an Intel host only mark that this boot reached the start hook 07
    reset_reason.py ichwd    once the timer's driver is loaded: on an Intel host, what ichwd said of it
    reset_reason.py show     what was kept at this boot, as JSON

WHY. A host that resets without a shutdown leaves no dump and no log line that says why. The XGS 3300
did so on 2026-10-17 (#454): under a minute after its last log line, with the hardware watchdog armed
at 128 s, no machine-check record at the next boot and no crash dump - and nothing on the appliance
could say what had reset it. The AMD FCH beside the host's processor keeps that answer: from family
17h on, FCH::PM::S5_RESET_STATUS - power-management register 0xC0, at 0xFED803C0 in memory - holds one
bit per cause of the last reset: the watchdog, a sync flood after an uncorrected error, a thermal
trip, the reset pin, the power button, a software reset through port 0xCF9 and others. Linux prints
it at boot since 2025 ("x86/CPU/AMD: Print the reason for the last reset").

Read by hand on the XGS 3300 on 2026-10-18, after an ordinary reboot, it held 0x00080800: bit 19, the
reset written to port 0xCF9 that a reboot ends in, and bit 11, which the published list does not
name. Nothing in it told of the reset of the day before - several boots had passed since - so it
is read at every boot, or not at all. Written back the same day, bit 19 cleared and bit 11 stayed:
bit 11 is a state of this chipset, not the cause of a reset.

HOW. The start hook 07-watchdog-reset-reason runs `boot` early in every boot. The register is read
through /dev/mem, logged under os-watchdog-reset-reason, and kept in
/var/db/os-watchdog/reset-reason.json with the boot it belongs to; the page shows it. Then the value
is written back: the bits are write-one-to-clear and some of them are never cleared by the hardware,
so without it a bit could outlive the reset that set it - Linux's follow-up fix does the same
("Prevent reset reasons from being retained across reboot").

ONE READER A BOOT. The read clears the record, so only the first reader of a boot sees the cause.
os-xgs-npu has read it at every boot since 2026-10-18 (its scripts/xgs/reset_reason.py, start hook
06, before this one), and its problem reporter and status page read what it kept. While that reader
is installed this one never touches the register: it takes os-xgs-npu's record of this boot instead,
and says so. This file came from that one on 2026-10-22.

Only on an AMD processor of family 17h or later (Family= in dmesg.boot), where the register exists,
and only on the machine itself. A virtual machine can be handed a Ryzen or an EPYC processor as it
is, Family= and all, while nothing behind 0xFED803C0 is a chipset: what a read there returns is
whatever the hypervisor answers, and writing it back writes to an address nobody knows. So since
2026-10-29 nothing is read where kern.vm_guest is anything but "none", and a value with every bit set
- what a read returns where nothing answers, never 32 causes at once - is taken as no record, and
nothing is written back. Never fails the caller.

A RESET THE WATCHDOG CAUSED, IN ONE FIELD. Every record kept carries "watchdog": true when bit 25 -
the hardware watchdog expired - is set in the value and was not set before this boot, false when the
register was read and the bit is not set, and null when that cannot be told: nothing was read (os-xgs-
npu kept no record for this boot, or every bit is set - nothing answers), or bit 25 may be one an
earlier boot left. The bits are write-one-to-clear and every read clears them, so a bit the boot before
cleared is new; but where there is no record of the boot before (a first boot of this plugin, after the
installer or another system), where that boot read nothing, could not clear it (cleared false), or
still read it set after clearing (after), a set bit 25 may be old: null, not a reset to report. So
false says only that the bit is not set. os-netreport's alert reads this field, so it need not know the
chipset's bit numbers; a record kept by a version before this field has none, and is read by its bits
instead. When it is true a line of its own goes into the system log: "the hardware watchdog reset this
host" with the boot it belongs to (2026-11-17).

ON INTEL, ICHWD'S WORD (2026-11-17). An Intel chipset has no register like the FCH's, only the TCO
timer's own record of the reset it caused: SECOND_TO_STS, set when the timer ran out a second time and
reset the host, kept through the reset. Nothing here reads it. FreeBSD's ichwd(4) does, when it
attaches: it prints "ichwd0: resuming after hardware watchdog timeout" where the bit is set
(sys/dev/ichwd/ichwd.c, ichwd_attach()) and clears it, and that line is the only trace it leaves - it
has no sysctl, and watchdog(4) no boot status. So on an Intel processor (Origin= in dmesg.boot), not
in a virtual machine, the record is that line: "read_by" "ichwd", no "value" and no "bits", "said"
"timeout" with it, "nothing" where ichwd attached without it (an attach that failed - "device_attach:
ichwd0 attach returned" - is none), and null where ichwd did not attach; "watchdog" true with the line,
false with nothing - which says only that ichwd did not see the bit: some firmware clears it before
the system starts, as ichwd's own comment there says - and null otherwise. Null also for a line that
may be an earlier reset's: ichwd clears the bit when it attaches, so the line is this reset's only
where ichwd attached in the boot before - as that boot's messages say, or, where they are gone, its
record - and otherwise the bit may have waited through boots that had no ichwd.

THE BOOT BEFORE'S RECORD, KNOWN BY A MARK. The record kept is the last one kept, not always the boot
before's: a boot that stopped before the start hook 10, in a hang or a panic, kept none, and the
record is then of a boot further back, whose ichwd says nothing of the boot between. So `boot`, which
the start hook 07 runs at every boot, leaves on Intel a mark of its own beside the record
(/var/db/os-watchdog/boots.json; the record stays one a boot): this boot and the boot before it that
reached the hook, by kern.boottime. `ichwd` takes the record as the boot before's only where its boot
is the one this boot's mark names, within five seconds; otherwise it can tell nothing from it - null.
A boot that stopped before the start hook 07 left no mark, and cannot be seen: where its messages are
gone too, the boot before it is taken for the boot before this one. Where the board clears its memory
as it starts, the messages of the boot before are gone after every reset, and the mark is what tells
(2026-11-17).

THIS BOOT'S MESSAGES ONLY, ONCE ITS DRIVER IS LOADED. The kernel keeps its message buffer through a
reset, so dmesg(8) prints the boots before this one too, each after the boot tag the kernel prints
first (kern.boot_tag, "---<<BOOT>>---"): only what follows the last tag is this boot's, and what lies
between the last two the boot before's. ichwd is a module that watchdog.sh loads from the start hook
10-watchdog, after this one's 07, and rc writes dmesg.boot before either runs, so neither `boot` nor
dmesg.boot can have its line: `ichwd` reads it - run by the start hook 10 after watchdog.sh, and by
the installers after theirs where no record is kept yet - from dmesg, or from dmesg.boot where dmesg
holds this boot's tag no longer, which has what an ichwd the loader loaded said. With no tag nothing
can be told. One record a boot, true, false or null, kept by one reader, so that os-netreport reads
each boot's record once and final. Nothing is read from the hardware here.
"""

import json
import os
import re
import subprocess
import sys
import time

ADDRESS = 0xFED80300 + 0xC0		# FCH::PM::S5_RESET_STATUS
MEM = os.environ.get('XGS_RESET_MEM', '/dev/mem')
OFFSET = int(os.environ.get('XGS_RESET_OFFSET', str(ADDRESS)))	# another place in MEM, for the tests
DMESG = os.environ.get('XGS_RESET_DMESG', '/var/run/dmesg.boot')
KEPT = os.environ.get('XGS_RESET_STATE', '/var/db/os-watchdog/reset-reason.json')
TAG = 'os-watchdog-reset-reason'
# os-xgs-npu's own reader and what it keeps: while it is installed, its record is the one of this boot
PROJECT = os.environ.get('XGS_RESET_PROJECT', '/usr/local/opnsense/scripts/xgs/reset_reason.py')
PROJECT_KEPT = os.environ.get('XGS_RESET_PROJECT_STATE', '/var/db/os-xgs-npu/reset-reason.json')
# kern.vm_guest as a test gives it; read from the kernel otherwise
VM_GUEST = os.environ.get('XGS_RESET_VM_GUEST')
# what a read returns where nothing answers
NOTHING_ANSWERS = 0xFFFFFFFF
# AMD's bit for "the hardware watchdog expired"
WATCHDOG_BIT = 25
# os-xgs-npu's mark of its read in the kernel's environment (its read_at): every boot starts anew from
# the loader, and no step of the clock moves it
KENV = os.environ.get('XGS_RESET_KENV', '/bin/kenv')
PROJECT_MARK = 'xgs.reset_reason.read_at'
# On Intel: what dmesg(8) prints and kern.boot_tag, as a test gives them (a file, and the tag); read
# from the kernel otherwise
KMSG = os.environ.get('XGS_RESET_KMSG')
BOOT_TAG = os.environ.get('XGS_RESET_BOOT_TAG')
# what the kernel prints at the start of every boot, where the loader set no other (sys/kern/subr_prf.c)
DEFAULT_BOOT_TAG = '---<<BOOT>>---'
# On Intel: the mark `boot` leaves at every boot - this boot and the boot before it that reached the
# start hook 07, by kern.boottime - by which `ichwd` knows the boot before's record. Apart from the
# record, which stays one a boot.
BOOTS = os.environ.get('XGS_RESET_BOOTS', '/var/db/os-watchdog/boots.json')
# ichwd's line where it finds the TCO timer's record of a second timeout - printed only after every way
# its attach can fail (sys/dev/ichwd/ichwd.c, ichwd_attach()); the line newbus prints as an attach of
# it begins, "ichwd0: <its description>", the place on the bus after; and the one where one failed.
# The kernel may put the uptime before each line ("[44] ichwd0: ..."), so none is matched from the start.
ICHWD_TIMEOUT = re.compile(r'\bichwd\d+: resuming after hardware watchdog timeout')
ICHWD_ATTACH = re.compile(r'\bichwd\d+: <[^>\n]*>[^\n]*')
ICHWD_FAILED = re.compile(r'\bdevice_attach: ichwd\d+ attach returned -?\d+')

# The bits with a published meaning (the AMD list Linux carries); every other bit is printed by its
# number. Bit 19 is what an ordinary reboot leaves here (the XGS 3300, 2026-10-18).
REASONS = {
    0: 'the thermal trip pin',
    1: 'the power button held for four seconds',
    2: 'the shutdown pin',
    4: 'a remote power-off (ASF)',
    9: "the processor's own thermal limit",
    16: 'the system reset pin',
    17: 'a software PCI reset',
    18: 'software wrote 0x4 to port 0xCF9',
    19: 'software wrote 0x6 to port 0xCF9, as a reboot does',
    20: 'software wrote 0xE to port 0xCF9',
    21: 'a sleep-state transition (ACPI)',
    22: 'the keyboard reset pin',
    23: 'the processor shut down, as after a triple fault',
    24: 'the boot failed before its timer ran out',
    25: 'the hardware watchdog expired',
    26: 'a remote reset (ASF)',
    27: 'a sync flood after an uncorrected error',
    29: "the chipset and the processor's power controller failed the warm-reset handshake",
    30: 'a parity error',
    31: 'a sync flood asked for by software',
}


def decode(value):
    """The set bits, lowest first, each with what it means."""
    return [{'bit': b, 'reason': REASONS.get(b, 'no published meaning')}
            for b in range(32) if value >> b & 1]


def describe(value):
    bits = decode(value)
    if not bits:
        return '0x%08x - no cause recorded' % value
    return '0x%08x - %s' % (value, '; '.join('bit %d: %s' % (b['bit'], b['reason']) for b in bits))


def by_watchdog(value):
    """Whether the hardware watchdog's bit is set in a value read: True, False, or None when nothing
    was read - no value, or every bit set (nothing answers). The value as a number, or as the record
    keeps it ("0x02000800")."""
    if value is None or value == '':
        return None
    try:
        number = value if isinstance(value, int) else int(str(value), 16)
    except ValueError:
        return None
    if number == NOTHING_ANSWERS:
        return None
    return bool(number >> WATCHDOG_BIT & 1)


def watchdog_field(value, earlier):
    """The record's "watchdog" field for this boot's value, against the record of the boot before
    (earlier, {} where there is none): by_watchdog(), but None where a set bit 25 may be one an earlier
    boot left - no earlier record or one that read nothing, one that could not clear its bit 25, or
    one that still read it set after clearing."""
    said = by_watchdog(value)
    if said is not True:
        return said
    if not earlier.get('boot') or by_watchdog(earlier.get('value')) is None:
        return None
    if earlier.get('cleared') is False and by_watchdog(earlier.get('value')):
        return None
    if by_watchdog(earlier.get('after')):
        return None
    return True


def said_by_watchdog(record):
    """The line in the system log for a record that says the hardware watchdog reset the host."""
    if record.get('watchdog') is True:
        log('the hardware watchdog reset this host: the reset before the boot of %s, read by %s' % (
            time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(int(record.get('boot') or 0))),
            record.get('read_by') or 'os-watchdog'))


def vm_guest():
    """kern.vm_guest: "none" on the machine itself, the hypervisor's name in a virtual machine."""
    if VM_GUEST is not None:
        return VM_GUEST
    try:
        return subprocess.run(['/sbin/sysctl', '-n', 'kern.vm_guest'], capture_output=True,
                              text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ''


def no_register():
    """Why this host has no reset record to read, or None where it has one: an AMD processor of
    family 17h or later (dmesg.boot's Origin= and Family= lines), not in a virtual machine. The
    page asks the same question through status.py."""
    guest = vm_guest()
    if guest != 'none':
        return 'a virtual machine (%s), with no chipset behind the address' % (guest or 'unknown')
    try:
        with open(DMESG, 'r', encoding='utf-8', errors='replace') as handle:
            text = handle.read()
    except OSError:
        return 'no %s to tell the processor by' % DMESG
    match = re.search(r'Family=0x([0-9a-fA-F]+)', text)
    if 'AuthenticAMD' in text and match and int(match.group(1), 16) >= 0x17:
        return None
    return 'no AMD family 17h or later processor here'


def no_ichwd():
    """Why ichwd cannot say here whether the hardware watchdog reset the host, or None where it may: an
    Intel processor (dmesg.boot's Origin= line), not in a virtual machine - where nothing is read, as
    on AMD. The page asks the same question through status.py."""
    guest = vm_guest()
    if guest != 'none':
        return 'a virtual machine (%s)' % (guest or 'unknown')
    try:
        with open(DMESG, 'r', encoding='utf-8', errors='replace') as handle:
            text = handle.read()
    except OSError:
        return 'no %s to tell the processor by' % DMESG
    if 'GenuineIntel' in text:
        return None
    return 'no Intel processor here'


def boot_time():
    try:
        raw = subprocess.run(['/sbin/sysctl', '-n', 'kern.boottime'], capture_output=True,
                             text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    match = re.search(r'sec = (\d+)', raw)
    return int(match.group(1)) if match else 0


def log(message):
    try:
        subprocess.run(['/usr/bin/logger', '-t', TAG, message], timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass


def keep(record, path=None):
    """The record, or on Intel the mark of this boot (path BOOTS), on disk whole or not at all."""
    path = KEPT if path is None else path
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + '.new', 'w', encoding='utf-8') as handle:
            json.dump(record, handle, indent=1)
            # on disk before it replaces the old: a reset soon after this boot hook must not leave an
            # empty record
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(path + '.new', path)
    except OSError:
        pass


def kept_now(path=KEPT):
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            record = json.load(handle)
        return record if isinstance(record, dict) else {}
    except (OSError, ValueError):
        return {}


def this_boot(record, boot):
    return bool(boot) and abs(int(record.get('boot') or 0) - boot) <= 5


def number(value):
    """A time kept in a record or a mark, as a whole number; 0 where it is none."""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def of_boot(record, boot):
    """this_boot() for what a file may hold, on Intel: never true for a boot of 0, nor raises."""
    return bool(boot) and abs(number(record.get('boot')) - number(boot)) <= 5


def mark_boot(boot):
    """On Intel, from the start hook 07 at every boot: the mark that this boot reached it, with the boot
    before it that did - the mark's own boot until now - kept apart from the record. Once a boot: a
    second run in it (an installer's, after the hook) leaves the mark as it is."""
    if not boot:
        return
    mark = kept_now(BOOTS)
    if of_boot(mark, boot):
        return
    keep({'boot': boot, 'before': number(mark.get('boot')) or None}, BOOTS)


def boot_before(boot):
    """The boot before this one that reached the start hook 07, by its kern.boottime, as this boot's mark
    names it; 0 where this boot left no mark (another's is not this boot's), or its mark names none."""
    mark = kept_now(BOOTS)
    return number(mark.get('before')) if of_boot(mark, boot) else 0


def project_mark():
    """os-xgs-npu's mark of its read at this boot (its record's read_at), or None."""
    try:
        out = subprocess.run([KENV, '-q', PROJECT_MARK], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return out or None


def from_project(boot):
    """os-xgs-npu read the register at this boot (or will have, by its own hook): keep its record,
    and leave the register alone. Its record is this boot's where its mark in the kernel's environment
    names its read_at, or, without a mark, where its boot is kern.boottime within five seconds (a step
    of the clock between the two boot hooks moves kern.boottime, never the mark)."""
    earlier = kept_now()
    record = kept_now(PROJECT_KEPT)
    mark = project_mark()
    if not (mark == str(record.get('read_at')) if mark is not None else this_boot(record, boot)):
        keep({'boot': boot, 'read_at': int(time.time()), 'value': None, 'bits': [], 'watchdog': None,
              'read_by': 'os-xgs-npu', 'note': 'os-xgs-npu reads the record on this host and kept none for this boot'})
        print('os-xgs-npu reads the record on this host and kept none for this boot')
        return 0
    record = dict(record, read_by='os-xgs-npu', watchdog=watchdog_field(record.get('value'), earlier))
    keep(record)
    said_by_watchdog(record)
    print('last reset, as os-xgs-npu read it: ' + describe(int(record.get('value') or '0', 16)))
    return 0


def kernel_messages():
    """What dmesg(8) prints: the kernel's message buffer, with the boots before this one it still holds."""
    if KMSG is not None:
        try:
            with open(KMSG, 'r', encoding='utf-8', errors='replace') as handle:
                return handle.read()
        except OSError:
            return ''
    try:
        return subprocess.run(['/sbin/dmesg'], capture_output=True, text=True, errors='replace',
                              timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return ''


def boot_tag():
    """kern.boot_tag, the line the kernel prints first in every boot; empty where it prints none."""
    if BOOT_TAG is not None:
        return BOOT_TAG
    try:
        done = subprocess.run(['/sbin/sysctl', '-n', 'kern.boot_tag'], capture_output=True, text=True,
                              timeout=10)
    except (OSError, subprocess.SubprocessError):
        return DEFAULT_BOOT_TAG
    return done.stdout.rstrip('\n') if done.returncode == 0 else DEFAULT_BOOT_TAG


def boots(text, tag):
    """(the boot before's messages, this boot's, whether the boot before's are whole) in what dmesg
    prints: this boot's follow the last boot tag, the boot before's lie between the last two - whole
    there, and only its end before a lone tag, its start overwritten. (None, None, False) without a tag."""
    if not text or not tag or tag not in text:
        return None, None, False
    parts = text.split(tag)
    return parts[-2], parts[-1], len(parts) > 2


def ichwd_said(text):
    """What ichwd said in one boot's messages: ('timeout', its line) where it found the TCO timer's record
    of a second timeout, ('nothing', its attach line) where it attached without it, (None, None) where
    it did not attach - none began, or every one that began failed. A first attach that found nothing
    cleared the record, so no later attach in the boot finds it."""
    if not text:
        return None, None
    timeout = ICHWD_TIMEOUT.search(text)
    if timeout:
        return 'timeout', timeout.group(0)
    begun = ICHWD_ATTACH.findall(text)
    if len(begun) > len(ICHWD_FAILED.findall(text)):
        return 'nothing', begun[0]
    return None, None


def cleared_before(before, whole, earlier, before_boot):
    """Whether ichwd attached in the boot before this one, and so cleared the TCO timer's record then:
    from that boot's messages where they are here - an attach in them, or none in them whole - and
    where they are not, from the record kept (earlier), but only where it is that boot's: its boot is
    the one this boot's mark names as the boot before (before_boot, 0 for none). The last record kept
    may be of a boot further back, with a boot between that kept none: false then, so null."""
    if ichwd_said(before)[0] is not None:
        return True
    if whole or not of_boot(earlier, before_boot):
        return False
    return earlier.get('read_by') == 'ichwd' and earlier.get('said') is not None


def dmesg_boot():
    try:
        with open(DMESG, 'r', encoding='utf-8', errors='replace') as handle:
            return handle.read()
    except OSError:
        return ''


def from_ichwd(boot):
    """On an Intel host: what ichwd said of the last reset in this boot's messages, kept once a boot -
    true, false or null, so that every boot has one record."""
    earlier = kept_now()
    if this_boot(earlier, boot):
        print('read already at this boot: %s' % (earlier.get('line') or earlier.get('note') or
                                                  earlier.get('value') or 'nothing'))
        return 0
    tag = boot_tag()
    before, this, whole = boots(kernel_messages(), tag)
    if this is None:
        # dmesg holds this boot's start no longer: dmesg.boot, written early in this boot, still has
        # what an ichwd the loader loaded said; one loaded since cannot be told from what is left
        before, this, whole = boots(dmesg_boot(), tag)
        if ichwd_said(this)[0] is None:
            this = None
    said, line = ichwd_said(this)
    record = {'boot': boot, 'read_at': int(time.time()), 'value': None, 'bits': [], 'read_by': 'ichwd',
              'said': said, 'line': line}
    before_boot = boot_before(boot)
    if said == 'timeout' and cleared_before(before, whole, earlier, before_boot):
        record['watchdog'] = True
        message = 'last reset: the hardware watchdog, as ichwd said at this boot - ' + line
    elif said == 'timeout':
        record['watchdog'] = None
        if whole:
            why = 'ichwd did not attach in the boot before'
        elif of_boot(earlier, before_boot):
            why = "the boot before's record does not say that ichwd attached"
        else:
            why = 'nothing kept tells whether ichwd attached in the boot before'
        record['note'] = why + ', so its line may be of an earlier reset'
        message = '%s - but %s, so it may be of an earlier reset' % (line, why)
    elif said == 'nothing':
        record['watchdog'] = False
        message = 'last reset: not the hardware watchdog, as far as ichwd can tell - %s, no timeout' % line
    else:
        record['watchdog'] = None
        record['note'] = ("this boot's start is not in the kernel's messages" if this is None else
                          'ichwd did not attach at this boot')
        message = record['note'] + ': nothing to tell the last reset by'
    keep(record)
    said_by_watchdog(record)
    log(message)
    print(message)
    return 0


def after_driver():
    """`ichwd`: once the timer's driver had its chance to attach, on an Intel host, ichwd's word on the
    last reset, kept once a boot. Elsewhere nothing: the chipset's record is `boot`'s, and a virtual
    machine reads none."""
    why = no_ichwd()
    if why:
        print(why + '; nothing for ichwd to say')
        return 0
    return from_ichwd(boot_time())


def at_boot():
    why = no_register()
    if why:
        if no_ichwd() is None:
            # an Intel host: what ichwd says as it attaches, which is later in the boot (2026-11-17);
            # here only the mark that this boot reached this hook, by which `ichwd` knows the boot
            # before's record
            mark_boot(boot_time())
            print("an Intel processor: the cause is what ichwd says as it attaches, kept by "
                  "reset_reason.py ichwd once the timer's driver is loaded")
            return 0
        print(why + '; nothing to read')
        return 0
    boot = boot_time()
    if os.path.exists(PROJECT):
        return from_project(boot)
    # Once a boot: a second read finds the record already cleared, and would keep "nothing" over
    # the cause this boot started with.
    earlier = kept_now()
    if this_boot(earlier, boot) and earlier.get('value'):
        print('read already at this boot: ' + describe(int(earlier.get('value', '0'), 16)))
        return 0
    try:
        fd = os.open(MEM, os.O_RDONLY)
        try:
            value = int.from_bytes(os.pread(fd, 4, OFFSET), 'little')
        finally:
            os.close(fd)
    except OSError as error:
        log('cannot read the reset record: %s' % error.strerror)
        return 0
    # Every bit set is nothing answering, not a record: neither kept nor written back.
    if value == NOTHING_ANSWERS:
        message = 'the reset record reads 0x%08x - nothing answers at 0x%08x; nothing kept' % (
            value, OFFSET)
        log(message)
        print(message)
        return 0
    # Cleared apart from the read, so that a host that refuses writes to /dev/mem (a raised
    # securelevel) still has its reason read and kept.
    cleared, after = False, None
    if value:
        try:
            fd = os.open(MEM, os.O_RDWR)
            try:
                os.pwrite(fd, value.to_bytes(4, 'little'), OFFSET)
                after = int.from_bytes(os.pread(fd, 4, OFFSET), 'little')
                cleared = True
            finally:
                os.close(fd)
        except OSError:
            pass
    record = {
        'boot': boot, 'read_at': int(time.time()), 'value': '0x%08x' % value,
        'bits': decode(value), 'cleared': cleared,
        'after': None if after is None else '0x%08x' % after, 'read_by': 'os-watchdog',
        'watchdog': watchdog_field(value, earlier if not this_boot(earlier, boot) else {}),
    }
    keep(record)
    said_by_watchdog(record)
    message = 'last reset: ' + describe(value)
    if value and not cleared:
        message += ' (could not be cleared)'
    elif after:
        message += ' (0x%08x left after clearing)' % after
    log(message)
    print(message)
    return 0


def show():
    try:
        with open(KEPT, 'r', encoding='utf-8') as handle:
            print(handle.read().strip())
    except OSError:
        print('{}')
    return 0


def main(argv):
    command = argv[1] if len(argv) > 1 else 'show'
    if command == 'boot':
        return at_boot()
    if command == 'ichwd':
        return after_driver()
    if command == 'show':
        return show()
    print('usage: reset_reason.py boot|ichwd|show', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
