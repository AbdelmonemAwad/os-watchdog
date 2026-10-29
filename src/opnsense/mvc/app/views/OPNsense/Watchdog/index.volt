{#
 # SPDX-License-Identifier: BSD-2-Clause
 # Copyright (c) 2026 Abdelmonem Awad <eg2@live.com>
 #
 # System: Hardware Watchdog (XGS: Hardware Watchdog when os-xgs-npu is installed) - the timer, who
 # holds it, the last reset, and the two settings.
 #}

<style>
    /* KIT-CSS-BEGIN */
    .xgs-cards { display: flex; flex-wrap: wrap; gap: 12px; padding: 15px; }
    .xgs-cards.xgs-top { padding: 0 0 15px; }
    .xgs-card { flex: 1 1 200px; min-width: 190px; border: 1px solid rgba(128, 128, 128, 0.25);
                border-inline-start: 4px solid #9e9e9e; border-radius: 3px; padding: 10px 14px;
                background-color: rgba(128, 128, 128, 0.04); }
    .xgs-card.ok { border-inline-start-color: #5cb85c; }
    .xgs-card.warn { border-inline-start-color: #f0ad4e; }
    .xgs-card.bad { border-inline-start-color: #d9534f; }
    .xgs-card .k { font-size: 11px; text-transform: uppercase; letter-spacing: .04em; opacity: 0.6; }
    .xgs-card .v { font-size: 19px; font-weight: 600; line-height: 1.3; margin: 2px 0; }
    .xgs-card .s { font-size: 12px; opacity: 0.7; }
    .xgs-card .fa { opacity: 0.35; float: inline-end; font-size: 18px; margin-top: 2px; }
    .xgs-head { padding-top: 5px; padding-bottom: 5px; font-size: 16px; }
    /* KIT-CSS-END */
</style>

<script>
    $(document).ready(function () {
        /* KIT-JS-BEGIN */
        /* A string as OPNsense's API and Volt's lang._() hand it over - escaped - made plain for .text(). */
        function plain(value) {
            return $('<textarea/>').html(value === null || value === undefined ? '' : String(value)).text();
        }

        /* One card: cls '' (grey, no judgement), 'ok', 'warn' or 'bad'; icon a Font Awesome name. */
        function card(cls, icon, key, value, sub) {
            return $('<div class="xgs-card"/>').addClass(cls)
                .append($('<i class="fa"/>').addClass(icon))
                .append($('<div class="k"/>').text(plain(key)))
                .append($('<div class="v"/>').text(plain(value)))
                .append($('<div class="s"/>').text(plain(sub || ' ')));
        }

        /* Until the first reading: the same cards, their keys, and an ellipsis for every value. */
        function cards_wait(target, keys) {
            $(target).empty();
            $.each(keys, function (i, key) {
                $(target).append(card('', 'fa-ellipsis-h', key, '…', ''));
            });
        }

        /* The selected tab kept in the address, as on OPNsense's own tabbed pages. */
        function keep_tab() {
            if (window.location.hash !== '') {
                $('a[href="' + window.location.hash + '"]').tab('show');
            }
            $('.nav-tabs a').on('shown.bs.tab', function (e) {
                history.pushState(null, null, e.target.hash);
            });
        }
        /* KIT-JS-END */

        /* The cause that matters most among the bits the chipset set, judged as os-xgs-npu's status
           page judges it, so the two pages never disagree about the same restart. */
        function restart(r) {
            if (!r || !r.value) {
                return {cls: '', what: "{{ lang._('not recorded') }}"};
            }
            const bits = (r.bits || []).map(function (b) { return b.bit; });
            const has = function (list) { return list.some(function (b) { return bits.indexOf(b) >= 0; }); };
            if (has([27, 31, 30])) { return {cls: 'bad', what: "{{ lang._('an uncorrected hardware error') }}"}; }
            if (has([23])) { return {cls: 'bad', what: "{{ lang._('the processor shut down') }}"}; }
            if (has([0, 9])) { return {cls: 'bad', what: "{{ lang._('overheating') }}"}; }
            if (has([25])) { return {cls: 'warn', what: "{{ lang._('the hardware watchdog') }}"}; }
            if (has([24, 29])) { return {cls: 'warn', what: "{{ lang._('a failed boot') }}"}; }
            if (has([16, 22, 26])) { return {cls: 'warn', what: "{{ lang._('the reset pin') }}"}; }
            if (has([1, 2, 4])) { return {cls: 'warn', what: "{{ lang._('the power button') }}"}; }
            if (has([17, 18, 19, 20])) { return {cls: 'ok', what: "{{ lang._('a reboot') }}"}; }
            if (has([21])) { return {cls: 'ok', what: "{{ lang._('a sleep state') }}"}; }
            return {cls: 'ok', what: "{{ lang._('power on') }}"};
        }

        /* What each bit means, in the page's language; reset_reason.py's English is the fallback for
           a bit with no published meaning. */
        const reasons = {
            0: "{{ lang._('the thermal trip pin') }}",
            1: "{{ lang._('the power button held for four seconds') }}",
            2: "{{ lang._('the shutdown pin') }}",
            4: "{{ lang._('a remote power-off (ASF)') }}",
            9: "{{ lang._('the processor thermal limit') }}",
            16: "{{ lang._('the system reset pin') }}",
            17: "{{ lang._('a software PCI reset') }}",
            18: "{{ lang._('software wrote 0x4 to port 0xCF9') }}",
            19: "{{ lang._('software wrote 0x6 to port 0xCF9, as a reboot does') }}",
            20: "{{ lang._('software wrote 0xE to port 0xCF9') }}",
            21: "{{ lang._('a sleep-state transition (ACPI)') }}",
            22: "{{ lang._('the keyboard reset pin') }}",
            23: "{{ lang._('the processor shut down, as after a triple fault') }}",
            24: "{{ lang._('the boot failed before its timer ran out') }}",
            25: "{{ lang._('the hardware watchdog expired') }}",
            26: "{{ lang._('a remote reset (ASF)') }}",
            27: "{{ lang._('a sync flood after an uncorrected error') }}",
            29: "{{ lang._('the chipset and the processor power controller failed the warm-reset handshake') }}",
            30: "{{ lang._('a parity error') }}",
            31: "{{ lang._('a sync flood asked for by software') }}"
        };

        function draw(data) {
            const $cards = $('#wd-cards').empty();
            if (!data || data.error) {
                $cards.append(card('bad', 'fa-heartbeat', "{{ lang._('Hardware watchdog') }}",
                    "{{ lang._('The status could not be read.') }}", ''));
                return;
            }
            let state, cls, sub = '';
            if (data.armed) {
                state = "{{ lang._('armed') }}";
                cls = 'ok';
                sub = (data.held_by === 'this plugin' ? "{{ lang._('by this plugin') }}" :
                       data.held_by === 'os-xgs-npu' ? "{{ lang._('by os-xgs-npu') }}" :
                       "{{ lang._('by another watchdogd') }}") +
                      (data.timeout ? ', ' + data.timeout + ' ' + "{{ lang._('s') }}" : '');
            } else {
                state = "{{ lang._('not armed') }}";
                const on = data.held_by === 'os-xgs-npu' ? data.project_enabled : data.enabled;
                cls = on ? 'warn' : '';
                sub = on ? "{{ lang._('on in the settings') }}" : "{{ lang._('off in the settings') }}";
            }
            $cards.append(card(cls, 'fa-heartbeat', "{{ lang._('Hardware watchdog') }}", state, sub));
            $cards.append(card(data.timer.desc ? 'ok' : '', 'fa-microchip', "{{ lang._('Timer') }}",
                data.timer.desc ? data.timer.driver : "{{ lang._('not found') }}",
                data.timer.desc || "{{ lang._('Apply loads its driver') }}"));
            /* Where the chipset keeps no record - not an AMD processor of family 17h or later, or a
               virtual machine - the restart is "not available" rather than "not recorded", and a
               record kept there by an older version is not shown (2026-10-29). */
            const supported = data.reset_supported !== false;
            const reset = supported ? data.reset : null;
            const r = supported ? restart(reset) : {cls: '', what: "{{ lang._('not available') }}"};
            const when = reset && reset.boot ? new Date(reset.boot * 1000).toLocaleString() : '';
            $cards.append(card(r.cls, 'fa-power-off', "{{ lang._('Last restart') }}", r.what,
                !supported ? '' : when ? "{{ lang._('since') }}" + ' ' + when :
                    "{{ lang._('read from the chipset at each boot') }}"));
            /* the record itself, as the chipset left it: no judgement, the card before makes it */
            const record = reset || {};
            $cards.append(card('', 'fa-list-ol', "{{ lang._('Value read') }}", record.value || '-',
                !supported ? '' : record.read_by ? "{{ lang._('Read by') }}" + ': ' + record.read_by :
                    "{{ lang._('read from the chipset at each boot') }}"));

            /* While os-xgs-npu's watchdog script is installed this plugin stands aside, whatever
               os-xgs-npu's own switch says: with that switch off nothing arms the timer, and the
               page says so rather than that os-xgs-npu arms it (2026-10-29). */
            const project = data.held_by === 'os-xgs-npu';
            $('#wd-project').toggle(project && data.project_enabled !== false);
            $('#wd-project-off').toggle(project && data.project_enabled === false);

            const $rows = $('#wd-bits tbody').empty();
            const bits = reset && reset.bits ? reset.bits : [];
            bits.forEach(function (b) {
                $rows.append($('<tr/>').append($('<td/>').text(b.bit)).append($('<td/>').text(
                    reasons[b.bit] || "{{ lang._('no published meaning') }}")));
            });
            if (!bits.length) {
                $rows.append($('<tr/>').append($('<td colspan="2" class="text-muted"/>').text(
                    !supported ? "{{ lang._('Not available on this host.') }}" :
                    reset && reset.read_by === 'os-xgs-npu' && !reset.value ?
                        "{{ lang._('os-xgs-npu reads the record on this host and kept none for this boot.') }}" :
                        "{{ lang._('No cause recorded at this boot.') }}")));
            }
            $('#wd-raw').text(reset && reset.value ? reset.value : '-');
            $('#wd-reader').text(reset && reset.read_by ? reset.read_by : '-');
        }

        /* One status feeds the cards and the Last restart tab; the settings are the form's own. */
        function refresh() {
            ajaxGet('/api/watchdog/service/status', {}, draw);
        }

        mapDataToFormUI({'frm_general': '/api/watchdog/settings/get'}).done(function () {
            $('.selectpicker').selectpicker('refresh');
        });
        cards_wait('#wd-cards', ["{{ lang._('Hardware watchdog') }}", "{{ lang._('Timer') }}",
            "{{ lang._('Last restart') }}", "{{ lang._('Value read') }}"]);
        refresh();

        $('#refreshAct').click(function () {
            refresh();
        });

        $('#saveAct').click(function () {
            const $button = $(this).prop('disabled', true);
            const $progress = $('#frm_general_progress').addClass('fa fa-spinner fa-pulse');
            const done = function () {
                $progress.removeClass('fa fa-spinner fa-pulse');
                $button.prop('disabled', false);
            };
            /* What watchdog.sh answers is not shown under the form: it is English, a sentence in the
               middle of a page in another language, and the cards read again right after say the
               same - armed or not, by whom, the timer - in the page's language (2026-10-29). */
            saveFormToEndpoint('/api/watchdog/settings/set', 'frm_general', function () {
                ajaxCall('/api/watchdog/service/reconfigure', {}, function () {
                    done();
                    refresh();
                });
            }, false, done);
        });

        keep_tab();
    });
</script>

<div class="xgs-cards xgs-top" id="wd-cards"></div>
<div class="clearfix" style="margin-bottom: 10px;">
    <button id="refreshAct" class="btn btn-default btn-xs pull-right" type="button" title="{{ lang._('Refresh') }}"><i class="fa fa-fw fa-refresh"></i></button>
    <span id="wd-project" class="text-muted" style="display: none;">
        {{ lang._('os-xgs-npu arms the watchdog of this host, by its own setting in XGS: Settings. While its watchdog script is installed this plugin leaves the timer to it and only shows it; the settings below take over once that script is removed.') }}
    </span>
    <span id="wd-project-off" class="text-muted" style="display: none;">
        {{ lang._('os-xgs-npu has its watchdog switched off in XGS: Settings. While its watchdog script is installed this plugin does not arm the timer either, so nothing arms it; the settings below take over once that script is removed.') }}
    </span>
</div>

<ul class="nav nav-tabs" data-tabs="tabs" id="maintabs">
    <li class="active"><a data-toggle="tab" href="#settings">{{ lang._('Settings') }}</a></li>
    <li><a data-toggle="tab" href="#reset">{{ lang._('Last restart') }}</a></li>
</ul>

<div class="tab-content content-box">
    <div id="settings" class="tab-pane active">
        {{ partial("layout_partials/base_form", ['fields': generalForm, 'id': 'frm_general', 'apply_btn_id': 'saveAct']) }}
    </div>
    <div id="reset" class="tab-pane">
        <div class="text-muted" style="padding: 10px 15px 0;">
            {{ lang._('Why the host last reset, as its chipset recorded it: one bit for each cause, read early in every boot and cleared for the next. Only on AMD processors of family 17h or later, and not in a virtual machine.') }}
        </div>
        <table id="wd-bits" class="table table-condensed table-striped">
            <thead>
                <tr>
                    <th style="width: 6em;">{{ lang._('Bit') }}</th>
                    <th>{{ lang._('Cause') }}</th>
                </tr>
            </thead>
            <tbody></tbody>
        </table>
        <div style="padding: 0 15px 15px;">
            {{ lang._('Value read') }}: <code id="wd-raw">-</code> &middot; {{ lang._('Read by') }}: <span id="wd-reader">-</span>
        </div>
    </div>
</div>

{{ partial("OPNsense/Watchdog/credit") }}
