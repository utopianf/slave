#!/usr/bin/env python3
#  -*- coding: utf-8 -*-
import time
import os
import traceback
from os import path
from datetime import datetime

import visa
import numpy as np
from PyQt5 import uic, QtWidgets, QtGui
from slave.transport import Visa
from slave.quantum_design import PPMS
from slave.agilent import B2900
import matplotlib as mpl
import matplotlib.pyplot as plt
try:
    from .dialog import Ui_Dialog
except ImportError:
    Ui_Dialog = None
mpl.use('Qt5Agg')
scriptdir = path.dirname(__file__)


class MyDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = uic.loadUiType(path.join(scriptdir, 'dialog.ui'))[0]()  # type: Ui_Dialog
        self.ui.setupUi(self)
        addrs = visa.ResourceManager().list_resources()
        idxP, idxB = -1, -1
        for i, a in enumerate(addrs):
            if '15' in a:
                idxP = i
            if '23' in a:
                idxB = i
        self.ui.cbPPMS.addItems(addrs)
        self.ui.cbPPMS.setCurrentIndex(idxP)
        self.ui.cbB290X.addItems(addrs)
        self.ui.cbB290X.setCurrentIndex(idxB)
        self.ui.leStart.setValidator(QtGui.QDoubleValidator())
        self.ui.leStop.setValidator(QtGui.QDoubleValidator())
        self.ui.leLimit.setValidator(QtGui.QDoubleValidator())
        self.ui.leIntegration.setValidator(QtGui.QDoubleValidator())

        self.ui.cbSource.currentTextChanged[str].connect(self.change_units)
        self.ui.cbUsePpms.stateChanged.connect(self.change_state)

    def change_state(self, use_ppms):
        self.ui.cbPPMS.setEnabled(bool(use_ppms))
        self.ui.leTemps.setEnabled(bool(use_ppms))

    def change_units(self, mode):
        if mode == 'voltage':
            u, lim = 'V', 'A'
        else:
            u, lim = 'A', 'V'
        self.ui.lbUnitStart.setText(u)
        self.ui.lbUnitStop.setText(u)
        self.ui.lbUnitLimit.setText(lim)


def main(
        addr_ppms, addr_b290x,
        four_wire: bool, source_mode: str,
        start: float, stop: float, points: int,
        compliance: float, integration_time: float, temps,
        use_ppms=True
):
    arguments = locals()
    print('----- parameters -----')
    print(*('%s: %s' % (k, v) for k, v in sorted(arguments.items(), key=lambda i: i[0])), sep='\n')
    if not temps:
        if use_ppms:
            print('No temperatures specified. aborting')
            return
        else:
            temps = [None]
    datadir = path.expanduser('~/Desktop/IV_data/{0:%Y%m%d-%H%M%S}'.format(datetime.now()))
    os.makedirs(datadir, exist_ok=True)

    print('Data will be saved in: %s' % datadir)
    with open(path.join(datadir, 'settings.txt'), 'w') as fp:
        for k, v in sorted(arguments.items(), key=lambda item: item[0]):
            fp.write('%s=%s\n' % (k, v))

    ppms = PPMS(Visa(addr_ppms)) if use_ppms else None
    smu = B2900(Visa(addr_b290x))

    smu.abort()
    smu.reset()
    smu.output.auto_on = True
    smu.output.auto_off = True
    smu.format.sense_elements = ('voltage', 'current')
    sense_function = 'curr' if source_mode.lower().startswith('volt') else 'volt'
    smu.setup.sense(sense_function, integration_time=integration_time, compliance=compliance, four_wire=four_wire)
    smu.setup.sweep_source(source_mode, start, stop, points)

    for t in temps:
        print('-' * 40)
        prefix = '{0:06.2f}K'.format(t) if t else 'data'
        if use_ppms:
            print('Setting temperature at %s K' % t)
            if t < 10 <= ppms.temperature:
                print('... Setting at 10 K and wait for 5 minutes')
                ppms.set_temperature(10, 10, wait_for_stability=True)
                time.sleep(300)
            rate = 10 if t >= 10 else 1
            ppms.set_temperature(t, rate, wait_for_stability=True)
            print('Wait for 5 min')
            time.sleep(300)
            temperature_before = ppms.temperature
        print('Start sweep')
        smu.initiate()
        smu.wait_to_continue()
        time.sleep(integration_time * points * 1.5)
        data = np.array(smu.fetch_array())
        data = data.reshape((-1, 2))
        if use_ppms:
            temperature_after = ppms.temperature
        with open(path.join(datadir, prefix + '.txt'), 'wb') as fp:
            if use_ppms:
                fp.write('# temperature before sweep: {0:.2f} K\n'.format(temperature_before).encode())
                fp.write('# temperature after sweep: {0:.2f} K\n'.format(temperature_after).encode())
            fp.write(b'# voltage\tcurrent\n')
            np.savetxt(fp, data)
        try:
            plt.plot(data[:, 0], data[:, 1], label=prefix)
            plt.xlabel('voltage (V)')
            plt.ylabel('current (A)')
            plt.legend(loc='best')
            plt.tight_layout()
            plt.savefig(path.join(datadir, prefix + '.png'))
            plt.clf()
        except Exception as e:
            print('Error plotting data:')
            print(traceback.format_exc())
    if use_ppms:
        print('Shutting down PPMS, please wait.')
        ppms.set_temperature(100, 10, wait_for_stability=True)
        ppms.shutdown()
    print('Finished!')

if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    d = MyDialog()
    ret = d.exec_()
    if ret == QtWidgets.QDialog.Accepted:
        main(d.ui.cbPPMS.currentText(), d.ui.cbB290X.currentText(), d.ui.cbFourWire.isChecked(),
             d.ui.cbSource.currentText(),
             float(d.ui.leStart.text()), float(d.ui.leStop.text()), d.ui.sbPoints.value(), float(d.ui.leLimit.text()),
             float(d.ui.leIntegration.text()),
             [float(x.strip()) for x in d.ui.leTemps.text().split(',') if x.strip()],
             d.ui.cbUsePpms.isChecked())
    else:
        print('Aborting')
