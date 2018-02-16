# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
import re
import unittest
from random import randint
from itertools import product

import visa

from slave.agilent import B2900
from slave.transport import Visa


class TestB2902A(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        transport = Visa(search_b2900())
        cls.b2900 = B2900(transport)
        cls.b2900r = B2900(transport)

    def tearDown(self):
        self.b2900.reset()

    def test_setup_triggering(self):
        for s, cn, t, d, ch in product(
                ('automatic internal', 'bus', 'timer'),
                (1, 100000, randint(1, 100000)),
                (2e-5, 1e5, randint(2, 1e10) / 1e5),
                (0, 100, randint(0, 10000) / 100),
                (1, 2)
        ):
            with self.subTest(source=s, count=cn, timer=t, delay=d, channel=ch):
                self.b2900.setup.triggering(s, cn, t, d, ch)
                idx = ch - 1
                self.assertEqual(self.b2900r.triggerings[idx].transient.source, s)
                self.assertEqual(self.b2900r.triggerings[idx].acquire.source, s)
                self.assertEqual(self.b2900r.triggerings[idx].transient.count, cn)
                self.assertEqual(self.b2900r.triggerings[idx].acquire.count, cn)
                self.assertAlmostEqual(self.b2900r.triggerings[idx].transient.timer, t, delta=0.01)
                self.assertAlmostEqual(self.b2900r.triggerings[idx].acquire.delay, d, delta=0.01)

    def test_setup_fixed_source(self):
        self.b2900.reset()
        for f, v, c in product(
                ('voltage', 'current'),
                (0, 0.01, randint(0, 100) / 10000, None),
                (1, 2)
        ):
            with self.subTest(function=f, value=v, channel=c):

                for trig in self.b2900.triggerings:
                    trig.count = 100
                self.b2900.setup.fixed_source(f, v, c)
                idx = c - 1
                self.assertEqual(self.b2900r.triggerings[idx].transient.count, 1)
                self.assertEqual(self.b2900r.triggerings[idx].acquire.count, 1)
                self.assertEqual(self.b2900r.sources[idx].function_mode, f)
                if v is not None:
                    if f == 'voltage':
                        self.assertAlmostEqual(self.b2900r.sources[idx].voltage.level, v, delta=0.001)
                        self.assertAlmostEqual(self.b2900r.sources[idx].voltage.level_triggered, v, delta=0.001)
                    else:
                        self.assertAlmostEqual(self.b2900r.sources[idx].current.level, v, delta=0.001)
                        self.assertAlmostEqual(self.b2900r.sources[idx].current.level_triggered, v, delta=0.001)

    def test_sweep_source(self):
        self.b2900.reset()
        for f, start, stop, points, ch in product(
                ('voltage', 'current'),
                (0, 0.1),
                (0.15, 0.05),
                (1, 101, randint(1, 101)),
                (1, 2)
        ):
            with self.subTest(function=f, start=start, stop=stop, points=points, channel=ch):
                idx = ch - 1
                self.b2900.setup.sweep_source(f, start, stop, points, ch)
                self.assertEqual(self.b2900r.sources[idx].function_mode, f)
                sub = self.b2900r.sources[idx].voltage if f == 'voltage' else self.b2900r.sources[idx].current
                self.assertAlmostEqual(sub.sweep_start, start, delta=1e-4)
                self.assertAlmostEqual(sub.sweep_stop, stop, delta=1e-4)
                self.assertEqual(sub.points, points)
                self.assertEqual(self.b2900r.triggerings[idx].transient.count, points)
                self.assertEqual(self.b2900r.triggerings[idx].acquire.count, points)
                self.b2900.initiate(channels=(ch,))
                self.b2900.wait_to_continue()
                data = self.b2900.fetch_array((ch,))
                if isinstance(data, float):
                    length = 1
                else:
                    elms = self.b2900r.format.sense_elements
                    if isinstance(elms, str):
                        length = len(data)
                    else:
                        length = len(data) / len(elms)
                self.assertEqual(length, points)

    def test_setup_sense(self):
        for f, ar, r, nplc, compl, ch in product(
                ('voltage', 'current'),
                (True, False, None),
                (0.1, 1, None),
                (0.01, 10, None),
                (0, 0.01, None),
                (1, 2)
        ):
            with self.subTest(function=f, auto_range=ar, range_=r, nplc=nplc, compliance=compl, channel=ch):
                if ar and r:
                    continue
                self.b2900.setup.sense(f, ar, r, nplc, compl, ch)
                idx = ch - 1
                sub = self.b2900r.senses[idx].voltage if f == 'voltage' else self.b2900r.senses[idx].current
                if ar is not None:
                    self.assertEqual(sub.auto_range, ar)
                if r is not None:
                    self.assertGreaterEqual(sub.range, r)
                if nplc is not None:
                    self.assertAlmostEqual(sub.nplc, nplc, delta=0.01)
                if compl is not None:
                    self.assertAlmostEqual(sub.compliance, compl, delta=0.01)

    def test_setup_resistance(self):
        for e, m, c in product(
                (True, False, None),
                ('auto', 'manual', None),
                (1, 2)
        ):
            with self.subTest(enable=e, mode=m, channel=c):
                self.b2900.setup.resistance(e, m, c)
                idx = c - 1
                if e is None:
                    pass
                elif e:
                    self.assertIn('resistance', self.b2900r.senses[idx].functions)
                else:
                    self.assertNotIn('resistance', self.b2900r.senses[idx].functions)
                if m is not None:
                    self.assertEqual(self.b2900r.senses[idx].resistance.mode, m)


def search_b2900():
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
            if re.search(r'B29[0-9][0-9]', identity[1]):
                break
    else:
        raise RuntimeError('Could not find B290X Source-measure unit.')
    return res


if __name__ == '__main__':
    if not input('Hit ENTER to start tests. Input something to abort: '):
        unittest.main()
