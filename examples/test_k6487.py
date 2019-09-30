# -*- coding: utf-8 -*-
# tests with Keithley Model 6487 Picoammeter/Voltage Source
import unittest
import sys
from random import randint

from slave.transport import LinuxGpib, Visa
from slave.keithley import K6487

gpib_address = 22


class TestK6487(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform.startswith('linux'):
            transport = LinuxGpib(gpib_address)
        else:
            transport = Visa('GPIB0::%s' % gpib_address)
        cls.k6487w = K6487(transport)
        cls.k6487r = K6487(transport)

    @classmethod
    def tearDownClass(cls):
        cls.k6487w.reset()

    def setUp(self):
        self.k6487w.reset()

    def test_functions(self):
        for f in self.k6487w.sense.functions:
            with self.subTest(function=f):
                self.k6487w.sense.function = f
                self.assertEqual(f, self.k6487r.sense.function)

    def test_sub_senses(self):
        """tests settings for each sense function"""
        functions = ('current', 'voltage')
        for f in functions:
            with self.subTest(function=f):
                # TODO: test range setting
                sub_sense_w = getattr(self.k6487w.sense, f)
                sub_sense_r = getattr(self.k6487r.sense, f)
                for nplc in (0.01, 10, randint(1, 1000)/100):
                    with self.subTest(nplc=nplc):
                        sub_sense_w.nplc = '%.2f' % nplc
                        self.assertAlmostEqual(sub_sense_r.nplc, nplc, delta=0.1)
                for b in (True, False):
                    sub_sense_w.auto_range = b
                    self.assertEqual(sub_sense_r.auto_range, b)

    def test_triggering(self):
        for b in (True, False):
            self.k6487w.triggering.continuous_initiation = b
            self.assertEqual(self.k6487r.triggering.continuous_initiation, b)
        for c in (1, 1000, randint(1, 1000)):
            with self.subTest(trigger_count=c):
                self.k6487w.triggering.count = c
                self.assertEqual(self.k6487r.triggering.count ,c)
        for d in (0, 9999, randint(0, 9999000)/1000):
            with self.subTest(trigger_delay=d):
                self.k6487w.triggering.delay = d
                self.assertAlmostEqual(self.k6487r.triggering.delay, d, delta=0.1)
        for s in ('immediate', 'external', 'timer', 'manual', 'bus'):
            with self.subTest(trigger_source=s):
                self.k6487w.triggering.source = s
                self.assertEqual(self.k6487r.triggering.source, s)
        for t in (0.001, 9999, randint(1, 9999000)/1000):
            with self.subTest(trigger_time=t):
                self.k6487w.triggering.timer = t
                self.assertAlmostEqual(self.k6487r.triggering.timer, t, delta=0.01)
        for sc in (1, 1024, randint(1, 1024)):
            with self.subTest(sample_count=sc):
                self.k6487w.triggering.sample_count = sc
                self.assertEqual(self.k6487r.triggering.sample_count, sc)
        self.k6487w.reset()
        self.k6487w.triggering.initiate()
        self.k6487w.triggering.abort()
        # self.k6487w.triggering.signal()

    def test_data_acquisition(self):
        for f in self.k6487w.sense.functions:
            with self.subTest(function=f):
                self.k6487w.sense.function = f
                self.k6487w.initiate()
                self.assertIsInstance(self.k6487r.fetch(), (float))
                self.k6487w.reset()
                self.assertIsInstance(self.k6487r.measure(function=f), (float))

    def test_sample_count(self):
        # test with dc voltage mode only
        for sc in (10, 1024, randint(1, 1024)):
            with self.subTest(sample_count=sc):
                self.k6487w.triggering.sample_count = sc
                self.k6487w.sense.voltage.nplc = 0.01
                self.k6487w.initiate()
                ret = self.k6487r.fetch()
                self.assertIsInstance(ret, list)
                self.assertEqual(len(ret), sc)


if __name__ == '__main__':
    unittest.main()
