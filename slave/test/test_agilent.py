#  -*- coding: utf-8 -*-
#
# Slave, (c) 2014, see AUTHORS.  Licensed under the GNU GPL.
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future.builtins import *
import collections

from slave.agilent import B2900
from slave.transport import SimulatedTransport


def test_b2900():
    # Test if instantiation fails
    B2900(SimulatedTransport())

