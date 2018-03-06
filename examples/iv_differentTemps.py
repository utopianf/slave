#!/usr/bin/env python
#  -*- coding: utf-8 -*-
import time
import os
from datetime import datetime
import numpy as np
from slave.transport import Visa
from slave.quantum_design import PPMS
from slave.agilent import B2900

dirname = os.path.expanduser('~/Desktop/IV_data/{0:%Y%m%d-%H%M%S}'.format(datetime.now()))
os.makedirs(dirname, exist_ok=True)

ppms = PPMS(Visa('GPIB0::15'))
smu = B2900(Visa('GPIB0::23'))

source = 'voltage'  # 'voltage' or 'current'
sweep_start = -0.1
sweep_stop = 0.1
sweep_points = 101  # max 2500
compliance = 1e-2
integration_time = 0.05
four_wire = False
temps = (
    2, 4, 6, 8, 10
)

smu.reset()
smu.setup.sweep_source(source, sweep_start, sweep_stop, sweep_points)
smu.setup.sense('current' if source == 'voltage' else 'voltage',
                integration_time=integration_time, compliance=compliance, four_wire=four_wire)
for t in temps:
    print('-'*40)
    print('Setting temperature at %s K' % t)
    if (t < 10) and (ppms.temperature > 10):
        print('Setting at 10 K')
        ppms.set_temperature(10, 10, wait_for_stability=True)
        time.sleep(300)
    rate = 10 if t > 10 else 1
    ppms.set_temperature(t, rate, wait_for_stability=True)
    print('Wait for 5 min')
    time.sleep(300)
    print('Start sweep')
    t_before = ppms.temperature
    smu.initiate()
    smu.wait_to_continue()
    time.sleep(integration_time * sweep_points)
    data = smu.fetch_array()
    t_after = ppms.temperature
    f = os.path.join(dirname, '%.3f.dat' % t)
    np.savetxt(f, data)
    print('Temprature before and after sweep: %.3f, %.3f K' % (t_before, t_after))
    print('Saved data in %s' % f)
