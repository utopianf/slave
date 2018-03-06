#  -*- coding: utf-8 -*-
#
# Slave, (c) 2014, see AUTHORS.  Licensed under the GNU GPL.
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future.builtins import *
import collections

from slave.keithley import K2182, K6221, K2400
from slave.transport import SimulatedTransport


def test_K2182():
    # Test if instantiation fails
    K2182(SimulatedTransport())


def test_K6221():
    # Test if instantiation fails
    K6221(SimulatedTransport())

def test_k2400():
    # Test if instantiation fails
    K2400(SimulatedTransport())
