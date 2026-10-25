<?php

/*
 * SPDX-License-Identifier: BSD-2-Clause
 * Copyright (c) 2026 Abdelmonem Awad <eg2@live.com>
 */

namespace OPNsense\Watchdog\Api;

use OPNsense\Base\ApiControllerBase;
use OPNsense\Core\Backend;

class ServiceController extends ApiControllerBase
{
    /**
     * the timer, who holds it and the last reset (scripts/watchdog/status.py)
     */
    public function statusAction()
    {
        $status = json_decode((new Backend())->configdRun('watchdog status'), true);
        return is_array($status) ? $status : ['error' => gettext('The status could not be read.')];
    }

    /**
     * arm the timer again from the settings just saved, or disarm it when they say off
     */
    public function reconfigureAction()
    {
        if (!$this->request->isPost()) {
            return ['status' => 'failed'];
        }
        $output = trim((new Backend())->configdRun('watchdog restart'));
        return ['status' => 'ok', 'output' => $output];
    }
}
