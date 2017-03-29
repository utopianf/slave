# -*- coding: utf-8 -*-
# tests with Keithley Model 2000 digital multimeter
import unittest
import sys
from random import uniform, randint

from slave.transport import LinuxGpib, Visa
from slave.keithley import K2000

gpib_address = 16


class TestK2000(unittest.TestCase):
    def setUpClass(cls):
        if sys.platform.startswith('linux'):
            transport = LinuxGpib(gpib_address)
        else:
            transport = Visa('GPIB0::%s' % gpib_address)
        cls.k2000w = K2000(transport)
        cls.k2000r = K2000(transport)

    def tearDownClass(cls):
        cls.k2000w.reset()

    def test_functions(self):
        for f in self.k2000w.sense.functions:
            with self.subTest(function=f):
                self.k2000w.sense.function = f
                self.assertEqual(f, self.k2000r.sense.function)

    def test_sub_senses(self):
        """tests settings for each sense function"""
        functions = ('current', 'current_ac', 'voltage', 'voltage_ac', 'resistance',
                     'fresistance', 'voltage_dc', 'current_dc')
        for f in functions:
            with self.subTest(function=f):
                # TODO: test range setting
                sub_sense_w = getattr(self.k2000w.sense, f)
                sub_sense_r = getattr(self.k2000r.sense, f)
                nplc = uniform(0.01, 60)
                sub_sense_w.nplc = nplc
                self.assertAlmostEqual(sub_sense_r.nplc, nplc, delta=0.01)
                for b in (True, False):
                    sub_sense_w.auto_range = b
                    self.assertEqual(sub_sense_r.auto_range, b)

    def test_triggering(self):
        for b in (True, False):
            self.k2000w.triggering.continuous_initiation = b
            self.assertEqual(self.k2000r.triggering.continuous_initiation, b)
        c = randint(1, 1000)
        self.k2000w.triggering.count = c
        self.assertEqual(self.k2000r.triggering.count ,c)
        d = uniform(0, 9999)
        self.k2000w.triggering.delay = d
        self.assertAlmostEqual(self.k2000r.triggering.delay, d, delta=0.1)
        for s in ('immediate', 'external', 'timer', 'manual', 'bus'):
            with self.subTest(trigger_source=s):
                self.k2000w.triggering.source = s
                self.assertEqual(self.k2000r.triggering.source, s)
        t = uniform(0.001, 9999)
        self.k2000w.triggering.timer = t
        self.assertAlmostEqual(self.k2000r.triggering.timer, t, delta=0.01)
        for sc in (1, 1024, randint(1, 1024), randint(1, 1024)):
            with self.subTest(sample_count=sc):
                self.k2000w.triggering.sample_count = sc
                self.assertEqual(self.k2000r.triggering.sample_count, sc)
        self.k2000w.reset()
        self.k2000w.triggering.initiate()
        self.k2000w.triggering.abort()
        self.k2000w.triggering.signal()

    def test_data_acquisition(self):
        for f in self.k2000w.sense.functions:
            with self.subTest(function=f):
                self.k2000w.sense.function = f
                self.k2000w.initiate()
                self.assertIsInstance(self.k2000r.fetch(), (float, list))
                self.k2000w.reset()
                self.assertIsInstance(self.k2000r.measure(function=f), (float, list))
