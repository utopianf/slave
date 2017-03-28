#  -*- coding: utf-8 -*-
#
# Slave, (c) 2014, see AUTHORS.  Licensed under the GNU GPL.
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future.builtins import *
import collections
import pytest
from itertools import product

from slave.keithley import K2182, K6221, K2000, K2400
from slave.driver import Command
from slave.transport import SimulatedTransport


def test_K2182():
    # Test if instantiation fails
    K2182(SimulatedTransport())


def test_K6221():
    # Test if instantiation fails
    K6221(SimulatedTransport())

def test_K2000():
    # Test if instantiation fails
    K2000(SimulatedTransport())


class TestK2400(object):
    k2400 = K2400(SimulatedTransport())
    ATOL = 1e-9

    @staticmethod
    def is_command(obj, attr):
        return isinstance(object.__getattribute__(obj, attr), Command)

    def test_setup_triggering(self):
        for count, delay in product((1, 5, None), (1, 0.1, None)):
            self.k2400.setup.triggering(count, delay)
            assert self.is_command(self.k2400.triggering, 'count')
            assert self.is_command(self.k2400.triggering, 'delay')
            if count is not None:
                assert self.k2400.triggering.count == count
            if delay is not None:
                assert abs(self.k2400.triggering.delay - delay) < self.ATOL

    def test_setup_fixed_source(self):
        for func, value in product(('voltage', 'current'), (1, -1, None)):
            self.k2400.setup.fixed_source(func, value)
            subsource = getattr(self.k2400.source, func)
            assert self.is_command(self.k2400.source, 'function_mode')
            assert self.is_command(subsource, 'level')
            assert self.is_command(subsource, 'level_triggered')
            assert self.k2400.source.function_mode == func
            if value is not None:
                assert abs(subsource.level - value) < self.ATOL
                assert abs(subsource.level_triggered - value) < self.ATOL

    def test_setup_resistance(self):
        for enable, mode in product((True, False, None), ('auto', 'manual', None)):
            self.k2400.setup.resistance(enable, mode)
            assert self.is_command(self.k2400.sense.resistance, 'mode')
            if (enable is not None) and not isinstance(self.k2400._transport, SimulatedTransport):
                assert 'resistance' in self.k2400.sense.functions  # only works when connected to a physical device
            if mode is not None:
                assert self.k2400.sense.resistance.mode == mode

    def test_setup_sense(self):
        for function, auto_range, range_, nplc, compliance, four_wire, integration_time in product(
                ('voltage', 'current'),
                (True, False, None),
                (0.1, 1, None),
                (0.1, 1, None),
                (0.1, 1, None),
                (True, False, None),
                (0.01, 0.1, None)
        ):
            if (auto_range and (range_ is not None)) or (nplc and integration_time):
                with pytest.raises(ValueError):
                    self.k2400.setup.sense(function, auto_range, range_, nplc, compliance, four_wire, integration_time)
            else:
                self.k2400.setup.sense(function, auto_range, range_, nplc, compliance, four_wire, integration_time)
                subsense = getattr(self.k2400.sense, function)
                assert self.is_command(subsense, 'auto_range')
                assert self.is_command(subsense, 'range')
                assert self.is_command(subsense, 'nplc')
                assert self.is_command(subsense, 'compliance')
                assert self.is_command(self.k2400.sense, 'four_wire')
                if auto_range is not None:
                    assert subsense.auto_range == auto_range
                if range_ is not None:
                    assert abs(subsense.range - range_) < self.ATOL
                if nplc is not None:
                    assert abs(subsense.nplc - nplc) < self.ATOL
                if compliance is not None:
                    assert abs(subsense.compliance - compliance) < self.ATOL
                if four_wire is not None:
                    assert self.k2400.sense.four_wire == four_wire
                if integration_time is not None:
                    assert abs(subsense.nplc - integration_time * 50) < self.ATOL

    def test_sweep_source(self):
        for function, start, stop, points in product(
                ('voltage', 'current'),
                (-1, 1),
                (-0.5, 0.5),
                (10, 100)
        ):
            self.k2400.setup.sweep_source(function, start, stop, points)
            subsource = getattr(self.k2400.source, function)
            assert self.is_command(self.k2400.source, 'function_mode')
            assert self.is_command(subsource, 'sweep_start')
            assert self.is_command(subsource, 'sweep_stop')
            assert self.is_command(subsource, 'sweep_points')
            assert self.is_command(self.k2400.triggering, 'count')
            assert self.k2400.source.function_mode == function
            assert abs(subsource.sweep_start - start) < self.ATOL
            assert abs(subsource.sweep_stop - stop) < self.ATOL
            assert subsource.sweep_points == points
            assert self.k2400.triggering.count == points
            if not isinstance(self.k2400._transport, SimulatedTransport):
                self.k2400.initiate()
                self.k2400.wait_to_continue()
                data = self.k2400.fetch()
                assert len(data) == (points * len(self.k2400.sense_elements))
