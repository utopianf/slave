# -*- coding: utf-8 -*-
#
# E21, (c) 2012-2015, see AUTHORS.  Licensed under the GNU GPL.
from slave.transport import SimulatedTransport
from slave.driver import Command, Driver
from slave.types import Boolean, Float, Integer, Mapping, Stream, String
import slave.iec60488 as iec

from logging import getLogger
logger = getLogger(__name__)

I_MAX = 3.1
V_MAX = 1010
V_AC_MAX = 757.5
R_MAX = 120e6

_functions = {'current_ac': 'CURR:AC',
              'current': 'CURR:DC',
              'voltage_ac': 'VOLT:AC',
              'volt_dc': 'VOLT:DC',
              'resistance': 'RES',
              'fresistance': 'FRES',
              'period': 'PER',
              'frequency': 'FREQ',
              'temperature': 'TEMP',
              'diode': 'DIOD',
              'continuity': 'CONT',
              }


class Display(Driver):
    """The Display command layer.

    :param transport: A transport object.

    :param protocol: A protocol object.
    """

    def __init__(self, transport, protocol):
        super(Display, self).__init__(transport, protocol)
        self.enable = Command(
            'DISP:ENAB?',
            'DISP:ENAB',
            Boolean
        )
        self.data = Command(
            'DISP:TEXT:DATA?',
            'DISP:TEXT:DATA',
            String(0, 12)
        )
        self.state = Command(
            'DISP:WIND:TEXT:STAT?',
            'DISP:WIND:TEXT:STAT',
            Boolean
        )


class Trigger(Driver):
    """The Trigger command layer.

    :param transport: A transport object.

    :param protocol: A protocol object.

    :ivar continuous_initiation: A boolean representing the continuous initiation mode.

    :ivar count: How many times operation loops around in the trigger operation.

    :ivar delay:  Used to delay operation of the trigger model.

    :ivar source: These commands are used to select the event control source.

    :ivar sample_count: This command specifies the sample count. The sample count defines how
        many times operation loops around in the trigger model to perform a device action.

        .. note:: If sample count is >1, you cannot use the :READ? command if there are readings stored in the buffer.
    """
    def __init__(self, transport, protocol):
        super(Trigger, self).__init__(transport, protocol)
        self.continuous_initiation = Command(
            ':INIT:CONT?',
            ':INIT:CONT',
            Boolean
        )
        self.count = Command(
            ':TRIG:COUN?',
            ':TRIG:COUN',
            Integer
        )
        self.delay = Command(
            ':TRIG:DEL?',
            ':TRIG:DEL',
            Float(0, 999999)
        )
        self.source = Command(
            ':TRIG:SOUR?',
            ':TRIG:SOUR',
            Mapping({'immediate': 'IMM',  # Pass operation through immediately
                     'external': 'EXT',  # Select External Triggering as event
                     'timer': 'TIM',  # Select timer as event
                     'manual': 'MAN',  # Select manual event
                     'bus': 'BUS',  # Select bus trigger as event.
                     })
        )
        self.timer = Command(
            ':TRIG:TIM?',
            ':TRIG:TIM',
            Float(0.001, 999999.999)
        )
        self.sample_count = Command(
            ':SAMP:COUN?',
            ':SAMP:COUN',
            Integer(1, 1024)
        )

    def initiate(self):
        """Initiates one measurement cycle."""
        self._write(':INIT')

    def abort(self):
        """Aborts operation and returns to the top of the Trigger Model."""
        self._write(':ABOR')

    def signal(self):
        self._write(':SIGN')


class Sense(Driver):
    """The Sense command layer.

    :param transport: A transport object.

    :param protocol: A protocol object.

    :ivar function: Current measurement function

    :ivar functions: List of available functions
    """
    def __init__(self, transport, protocol):
        super(Sense, self).__init__(transport, protocol)
        self.function = Command(
            ':SENS:FUNC?',
            ':SENS:FUNC',
            Mapping({name: ('"' + value + '"') for name, value in _functions.items()})
        )
        self.current = SubSense(self._transport, self._protocol, 'CURR:DC', I_MAX)
        self.current_ac = SubSense(self._transport, self._protocol, 'CURR:AC', I_MAX)
        self.voltage = SubSense(self._transport, self._protocol, 'VOLT:DC', V_MAX)
        self.voltage_ac = SubSense(self._transport, self._protocol, 'VOLT:AC', V_AC_MAX)
        self.resistance = SubSense(self._transport, self._protocol, 'RES', R_MAX)
        self.fresistance = SubSense(self._transport, self._protocol, 'FRES', R_MAX)
        self.voltage_dc = self.voltage
        self.current_dc = self.current

    def get_data(self):
        """reads the latest instrument reading."""
        return self._query((':SENS:DATA?', Stream(Float)))

    @property
    def functions(self):
        return tuple(_functions)


class SubSense(Driver):
    def __init__(self, transport, protocol, function, ulim):
        super(SubSense, self).__init__(transport, protocol)

        self._function = function
        self._ulim = ulim

        self.nplc = Command(
            ':SENS:%s:NPLC?' % function,
            ':SENS:%s:NPLC' % function,
            Float(0.01, 60)
        )
        self.auto_range = Command(
            ':SENS:%s:RANG:AUTO?' % function,
            ':SENS:%s:RANG:AUTO' % function,
            Boolean
        )
        self.range = Command(
            ':SENS:%s:RANG?' % function,
            ':SENS:%s:RANG' % function,
            Float(0, ulim)
        )


class Trace(Driver):
    """TRACe subsystem. Used to configure and control data storage into buffer.

    :ivar free: [int, int] The first value indicates available memory in bytes.
        The second indicates memory reserved to store readings in bytes.

    :ivar int points: buffer size in integer. (from 2 to 1024)
    :ivar feed: The source of readings to be placed in the buffer
        'sense' means raw readings
        'calculate' means calculated math readings
        'none' means no readings
    :ivar control: 'never' disables storage into the buffer.
                   'next' enables storage.
    """

    def __init__(self, transport, protocol):
        super(Trace, self).__init__(transport, protocol)
        self._transport = transport
        self._protocol = protocol

        self.free = Command(query=':TRAC:FREE?', type_=[Integer, Integer])
        self.points = Command(
            ':TRAC:POINts?',
            ':TRAC:POINts',
            Integer(2, 1024)
        )
        self.feed = Command(
            ':TRACe{c}:FEED?',
            'TRACe{c}:FEED',
            Mapping({'sense': 'SENSe', 'calculate': 'CALC', 'none': 'NONE'})
        )
        self.control = Command(
            'TRACe:CONT?',
            'TRACe:CONT',
            Mapping({'never': 'NEV', 'next': 'NEXT'})
        )
        self.data = Command(
            query='TRACe:DATA?',
            type_=Stream(Float)
        )

    def clear(self):
        self._write(':TRACe:CLEar')


class K2000(iec.IEC60488, iec.Trigger, iec.StoredSetting):
    """Keithley Model2000 Digital Multimeter"""
    def __init__(self, transport):
        super(K2000, self).__init__(transport)
        if not isinstance(transport, SimulatedTransport):
            # check identification
            idns = self.identification
            logger.debug('identification: %s', idns)
            if idns[1] != 'MODEL 2000':
                raise ValueError('Invalid identification: %s', idns)
        self.triggering = Trigger(self._transport, self._protocol)
        self.triggering.continuous_initiation = False
        self.initiate = self.triggering.initiate

        self.sense = Sense(self._transport, self._protocol)
        self.trace = Trace(self._transport, self._protocol)

        self.abort = self.triggering.abort

    def configure(self, function):
        """Configures the instrument for subsequent measurements on
        the specified function.

        Basically, this command places the instrument in a
        “one-shot” measurement mode. You then use the :READ? command to
        trigger a measurement and acquire a reading (see :READ?).

        .. note:: This will reset all controls related to the selected function."""
        self._write(':CONF:%s' % _functions[function])

    def read(self):
        """A high level command to perform a singleshot measurement.
        It resets the trigger model(idle), initiates it, and fetches a new
        value.
        It is equivalent to ':ABOR; :INIT; :READ?'.

        :return list of read values
        """
        return self._query((':READ?', Stream(Float)))

    def fetch(self):
        """Requests the latest post-processed reading.

        This command does not trigger a measurement. The command simply
        requests the last available reading. Note that this command can repeatedly
        return the same reading. Until there is a new reading, this command
        continues to return the old reading.

        :return list of fetched values

        .. note:: If external rapid triggers are applied, the unit may not return
        readings when using :FETCh?"""
        return self._query((':FETC?', Stream(Float)))

    def measure(self, function=None):
        """This command combines all of the other signal oriented measurement commands to
        perform a “one-shot” measurement and acquire the reading.

        When this command is sent, the following commands execute in the order
        that they are presented.
            :ABORt:CONFigure:<function>:READ?

        :return list of measured values

        .. note:: This is ~ 10 times slower than read()."""
        if function:
            return self._query((':MEAS:%s? ' % _functions[function], Stream(Float)))
        else:
            return self._query((':MEAS?', Stream(Float)))
