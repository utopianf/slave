#!/usr/bin/env python
#  -*- coding: utf-8 -*-
import time
import os
from datetime import datetime
import numpy as np
from slave.quantum_design import PPMS
from slave.agilent import B2900

dirname = os.path.expanduser('~/Desktop/IV_data/{0:%Y%m%d-%H%M%S}'.format(datetime.now()))
os.makedirs(dirname, exist_ok=True)

ppms = PPMS('GPIB0::15')
smu = B2900('GPIB0::23')

source = 'volt'  # 'volt' or 'curr'
sweep_start = -0.1
sweep_stop = 0.1
sweep_points = 2001  # max 2500
compliance = 1e-2
nplc = 1  # measurement time (unit: power line cycle = 1/50 s)
temps = (
    2, 4, 6, 8, 10
)

smu.reset()
smu.setup.sweep_source(source, sweep_start, sweep_stop, sweep_points)
for t in temps:
    print('-'*40)
    print('Setting temperature at %s K' % t)
    if t < 10 and ppms.temperature > 10:
        print('Setting at 10 K')
        ppms.set_temperature(10, 10, wait_for_stability=True)
        time.sleep(300)
    rate = 10 if t > 10 else 1
    ppms.set_temperature(t, rate, wait_for_stability=True)
    print('Wait for 5 min')
    print('Start sweep')
    time.sleep(300)
    smu.initiate()
    smu.wait_to_continue()
    time.sleep(nplc / 50 * sweep_points)
    data = smu.fetch_array()
    np.savetxt(os.path.join(dirname, '%.3e.dat' % t), data)
