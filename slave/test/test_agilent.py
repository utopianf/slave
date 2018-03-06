#  -*- coding: utf-8 -*-
#
# Slave, (c) 2014, see AUTHORS.  Licensed under the GNU GPL.
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future.builtins import *
import collections
from itertools import product
from random import randint, uniform
import pytest
from slave.driver import Command
from slave.agilent import B2900
from slave.transport import SimulatedTransport


class TestB2900(object):
    b2900 = B2900(SimulatedTransport())
    channels = (1, 2) if b2900.is_dual else (1,)
    ATOL = 1e-6

    @staticmethod
    def is_command(obj, attr):
        return isinstance(object.__getattribute__(obj, attr), Command)

    def assert_command_equal(self, obj, attr, val):
        assert self.is_command(obj, attr)
        assert getattr(obj, attr) == val

    def assert_command_isclose(self, obj, attr, val, atol=None):
        atol = self.ATOL if atol is None else atol
        assert self.is_command(obj, attr)
        assert abs(getattr(obj, attr) - val) <= atol

    def test_triggering(self):
        for s, cn, t, d, ch in product(
                ('automatic internal', 'bus', 'timer'),
                (1, 100000, randint(1, 100000)),
                (2e-5, 1e5, randint(2, 1e10) / 1e5),
                (0, 100, randint(0, 10000) / 100),
                self.channels
        ):
            self.b2900.setup.triggering(s, cn, t, d, ch)
            idx = ch - 1
            triggering = self.b2900.triggerings[idx]
            if isinstance(self.b2900._transport, SimulatedTransport):
                assert self.is_command(triggering, 'source')
                assert self.is_command(triggering, 'count')
                assert self.is_command(triggering, 'timer')
                assert self.is_command(triggering, 'delay')
            else:
                # read values if connected to a physical device (this only works for physical devices)
                self.assert_command_equal(triggering.transient, 'source', s)
                self.assert_command_equal(triggering.acquire, 'source', s)
                self.assert_command_equal(triggering.transient, 'count', cn)
                self.assert_command_equal(triggering.acquire, 'count', cn)
                self.assert_command_isclose(triggering.transient, 'timer', t)
                self.assert_command_isclose(triggering.acquire, 'timer', t)
                self.assert_command_isclose(triggering.transient, 'delay', t)
                self.assert_command_isclose(triggering.acquire, 'delay', t)

    def test_fixed_source(self):
        TRIGGER_COUNT_BEFORE = 100
        for f, v, c in product(
                ('voltage', 'current'),
                (0, 0.01, randint(0, 100) / 10000, None),
                self.channels
        ):
            for trig in self.b2900.triggerings:
                trig.count = TRIGGER_COUNT_BEFORE
            self.b2900.setup.fixed_source(f, v, c)
            triggering = self.b2900.triggerings[c - 1]
            source = self.b2900.sources[c - 1]
            assert self.is_command(triggering, 'count')
            if isinstance(self.b2900._transport, SimulatedTransport):
                assert self.is_command(triggering, 'count')
            else:
                self.assert_command_equal(triggering.transient, 'count', 1)
                self.assert_command_equal(triggering.acquire, 'count', 1)
            self.assert_command_equal(source, 'function_mode', f)
            if v is not None:
                subsource = getattr(source, f)
                self.assert_command_isclose(subsource, 'level', v)
                self.assert_command_isclose(subsource, 'level_triggered', v)

    def test_fixed_source_compensate(self):
        TRIGGER_COUNT_BEFORE = 100
        for f, v, c in product(
                ('voltage', 'current'),
                (0, 0.01, randint(0, 100) / 10000, None),
                self.channels
        ):
            for trig in self.b2900.triggerings:
                trig.count = TRIGGER_COUNT_BEFORE
            self.b2900.setup.fixed_source_with_compensation(f, v, c)
            triggering = self.b2900.triggerings[c - 1]
            source = self.b2900.sources[c - 1]
            if not isinstance(self.b2900._transport, SimulatedTransport):
                self.assert_command_equal(triggering.transient, 'count', 2)
                self.assert_command_equal(triggering.acquire, 'count', 2)
                self.assert_command_equal(source, 'function_mode', f)
            if v is not None:
                subsource = getattr(source, f)
                assert self.is_command(subsource, 'list')
                assert len(subsource.list) == 2
                assert any(abs(x - v) < self.ATOL for x in (v, -v))

    def test_sweep_source(self):
        for f, start, stop, points, ch in product(
                ('voltage', 'current'),
                (0, 0.1),
                (0.15, 0.05),
                (1, 11, randint(1, 11)),
                self.channels
        ):
            self.b2900.setup.sweep_source(f, start, stop, points, ch)
            source = self.b2900.sources[ch - 1]  # type: B2900.Source
            triggering = self.b2900.triggerings[ch - 1]  # type: B2900.Triggering
            subsource = getattr(source, f)  # type: B2900.SubSource
            self.assert_command_equal(source, 'function_mode', f)
            self.assert_command_isclose(subsource, 'sweep_start', start)
            self.assert_command_isclose(subsource, 'sweep_stop', stop)
            self.assert_command_isclose(subsource, 'sweep_points', points)
            if not isinstance(self.b2900._transport, SimulatedTransport):
                self.b2900.initiate(channels=(ch,))
                self.b2900.wait_to_continue()
                self.assert_command_equal(triggering.transient, 'count', points)
                self.assert_command_equal(triggering.acquire, 'count', points)
                data = self.b2900.fetch_array((ch,))
                data = [data] if isinstance(data, (int, float)) else data
                elms = self.b2900.format.elements
                elms = [elms] if isinstance(elms, str) else elms
                assert len(data) == len(elms) * points

    def test_sense(self):
        for f, auto_range, range_, nplc, compl, four_wire, integration_time, ch in product(
                ('voltage', 'current'),
                (True, False, None),
                (0.1, 1, None),
                (0.01, uniform(0.01, 10), None),
                (0, uniform(0, 0.1), None),
                (True, False, None),
                (0.1, uniform(0.01, 0.1), None),
                self.channels
        ):
            if (auto_range and (range_ is not None)) or (None not in (nplc, integration_time)):
                with pytest.raises(ValueError):
                    self.b2900.setup.sense(f, auto_range, range_, nplc, compl, four_wire, integration_time, ch)
                continue
            self.b2900.setup.sense(f, auto_range, range_, nplc, compl, four_wire, integration_time, ch)
            subsense = getattr(self.b2900.senses[ch-1], f)  # type: B2900.SubSense
            if auto_range is not None:
                self.assert_command_equal(subsense, 'auto_range', auto_range)
            if range_ is not None:
                self.assert_command_isclose(subsense, 'range', range_)
            if nplc is not None:
                self.assert_command_isclose(subsense, 'nplc', nplc)
            if compl is not None:
                self.assert_command_isclose(subsense, 'compliance', compl)
            if integration_time is not None:
                self.assert_command_isclose(subsense, 'aperture', integration_time)
            if four_wire is not None:
                self.assert_command_equal(self.b2900.senses[ch-1], 'four_wire', four_wire)

    def test_resistance(self):
        for e, m, c in product(
                (True, False, None),
                ('auto', 'manual', None),
                self.channels
        ):
            self.b2900.setup.resistance(e, m, c)
            if not isinstance(self.b2900._transport, SimulatedTransport):
                if e is None:
                    pass
                elif e:
                    assert 'resistance' in self.b2900.senses[c-1].functions
                else:
                    assert 'resistance' not in self.b2900.senses[c-1].functions
            if m is not None:
                self.assert_command_equal(self.b2900.senses[c-1].resistance, 'mode', m)

