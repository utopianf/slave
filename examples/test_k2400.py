# -*- coding: utf-8 -*-
import unittest
import re
import random
from random import randint
from itertools import product

import visa

from slave.transport import Visa
from slave.keithley.k2400 import K2400


def search_k2400():
    rm = visa.ResourceManager()
    for res in rm.list_resources():
        try:
            i = rm.open_resource(res)
        except visa.VisaIOError:
            continue
        else:
            try:
                i.clear()
                identity = i.query('*IDN?').split(',')
            except visa.VisaIOError:
                continue
            if re.search(r'MODEL 24[0-9][0-9]', identity[1]):
                break
    else:
        raise RuntimeError('Could not find 2400 SourceMeter.')
    return res


class TestK2400(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tr = Visa(search_k2400())
        cls.k2400_write = K2400(tr)
        cls.k2400_read = K2400(tr)
        cls.k2400_write.reset()

    def tearDown(self):
        self.k2400_write.reset()

    def test_fixed_source(self):
        for func, val in product(('voltage', 'current'), (0, 0.1, -0.1)):
            with self.subTest(mode=func, value=val):
                self.k2400_write.setup.fixed_source(func, val)

                self.assertEqual(self.k2400_read.source.function_mode, func)
                obj = getattr(self.k2400_read.source, func)
                self.assertAlmostEqual(obj.level, val, delta=0.01)

    def test_sweep(self):
        for func, start in product(('voltage', 'current'), (0.1, -0.1)):
            with self.subTest(mode=func, start=start):
                n = random.randint(5, 21)
                self.k2400_write.setup.sweep_source(func, start, -start, n)
                self.k2400_write.sense_elements = ('voltage', 'current')
                self.k2400_write.output.state = True
                self.k2400_write.initiate()
                self.k2400_write.wait_to_continue()
                data = self.k2400_read.fetch()

                self.assertEqual(len(data), n * 2)
                self.assertTrue(self.k2400_read.output.state)
                self.assertEqual(self.k2400_read.source.function_mode, func)
                obj = getattr(self.k2400_read.source, func)
                self.assertAlmostEqual(obj.level, -start, delta=abs(start)*0.01)

    def test_sense(self):
        for func, arange, nplc, compl, fw in product(('voltage', 'current'), (True, False), (0.1, 1), (0.1,), (True, False)):
            with self.subTest(mode=func, auto_range=arange, nplc=nplc, compliance=compl, four_wire=fw):
                self.k2400_write.setup.sense(func, arange, nplc=nplc, compliance=compl, four_wire=fw)

                obj = getattr(self.k2400_read.sense, func)
                self.assertEqual(self.k2400_read.sense.four_wire, fw)
                self.assertEqual(obj.auto_range, arange)
                self.assertAlmostEqual(obj.nplc, nplc, delta=0.01*nplc)
                self.assertAlmostEqual(obj.compliance, compl, delta=0.01*compl)

    def test_triggering(self):
        for cn, d in product(
                (2, 2500, randint(2, 2500)),
                (0, 100, randint(0, 10000) / 100),
        ):
            with self.subTest(count=cn, delay=d):
                self.k2400_write.setup.triggering(count=cn, delay=d)
                self.assertEqual(self.k2400_read.triggering.count, cn)
                self.assertAlmostEqual(self.k2400_read.triggering.delay, d, delta=0.01)


if __name__ == '__main__':
    if not input('Hit ENTER to start tests. Input something to abort: '):
        unittest.main()
