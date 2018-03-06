#  -*- coding: utf-8 -*-
#
# Slave, (c) 2014, see AUTHORS.  Licensed under the GNU GPL.
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future.builtins import *
import collections
import pytest
from itertools import product

from slave.driver import Command
from slave.keithley import K2182, K6221, K2400
from slave.transport import SimulatedTransport


def test_K2182():
    # Test if instantiation fails
    K2182(SimulatedTransport())


def test_K6221():
    # Test if instantiation fails
    K6221(SimulatedTransport())


class TestK2400(object):
    ATOL = 1e-9

    @staticmethod
    def is_command(obj, attr):
        return isinstance(object.__getattribute__(obj, attr), Command)

    def test_setup_triggering(self):
        k2400 = K2400(SimulatedTransport())
        for count, delay in product((1, 5, None), (1, 0.1, None)):
            k2400.setup.triggering(count, delay)
            assert self.is_command(k2400.triggering, 'count')
            assert self.is_command(k2400.triggering, 'delay')
            if count is not None:
                assert k2400.triggering.count == count
            if delay is not None:
                assert abs(k2400.triggering.delay - delay) < self.ATOL

    def test_setup_fixed_source(self):
        k2400 = K2400(SimulatedTransport())
        for func, value in product(('voltage', 'current'), (1, -1, None)):
            k2400.setup.fixed_source(func, value)
            subsource = getattr(k2400.source, func)
            assert self.is_command(k2400.source, 'function_mode')
            assert self.is_command(subsource, 'level')
            assert self.is_command(subsource, 'level_triggered')
            assert k2400.source.function_mode == func
            if value is not None:
                assert abs(subsource.level - value) < self.ATOL
                assert abs(subsource.level_triggered - value) < self.ATOL

    def test_setup_resistance(self):
        k2400 = K2400(SimulatedTransport())
        for enable, mode in product((True, False, None), ('auto', 'manual', None)):
            k2400.setup.resistance(enable, mode)
            assert self.is_command(k2400.sense.resistance, 'mode')
            if enable is not None:
                pass
                # assert 'resistance' in k2400.sense.functions  # only works when connected to physical device
            if mode is not None:
                assert k2400.sense.resistance.mode == mode

    def test_setup_sense(self):
        k2400 = K2400(SimulatedTransport())
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
                    k2400.setup.sense(function, auto_range, range_, nplc, compliance, four_wire, integration_time)
            else:
                k2400.setup.sense(function, auto_range, range_, nplc, compliance, four_wire, integration_time)
                subsense = getattr(k2400.sense, function)
                assert self.is_command(subsense, 'auto_range')
                assert self.is_command(subsense, 'range')
                assert self.is_command(subsense, 'nplc')
                assert self.is_command(subsense, 'compliance')
                assert self.is_command(k2400.sense, 'four_wire')
                if auto_range is not None:
                    assert subsense.auto_range == auto_range
                if range_ is not None:
                    assert abs(subsense.range - range_) < self.ATOL
                if nplc is not None:
                    assert abs(subsense.nplc - nplc) < self.ATOL
                if compliance is not None:
                    assert abs(subsense.compliance - compliance) < self.ATOL
                if four_wire is not None:
                    assert k2400.sense.four_wire == four_wire
                if integration_time is not None:
                    assert abs(subsense.nplc - integration_time * 50) < self.ATOL

    def test_sweep_source(self):
        k2400 = K2400(SimulatedTransport())
        for function, start, stop, points in product(
                ('voltage', 'current'),
                (-1, 1),
                (-0.5, 0.5),
                (10, 100)
        ):
            k2400.setup.sweep_source(function, start, stop, points)
            subsource = getattr(k2400.source, function)
            assert self.is_command(k2400.source, 'function_mode')
            assert self.is_command(subsource, 'sweep_start')
            assert self.is_command(subsource, 'sweep_stop')
            assert self.is_command(subsource, 'sweep_points')
            assert k2400.source.function_mode == function
            assert abs(subsource.sweep_start - start) < self.ATOL
            assert abs(subsource.sweep_stop - stop) < self.ATOL
            assert subsource.sweep_points == points

