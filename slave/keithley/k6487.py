# -*- coding: utf-8 -*-
#
# E21, (c) 2012-2015, see AUTHORS.  Licensed under the GNU GPL.
from slave.driver import Command, Driver
from slave.types import Boolean, Float, Integer, Mapping, Stream, String
import slave.iec60488 as iec

from logging import getLogger
logger = getLogger(__name__)

I_MAX = 0.021
V_MAX = 505

_functions = {'current': 'CURRent'}
_data_elements = {
    'reading': 'READ',
    'units': 'UNIT',
    'voltage': 'VSO',
    'timestamp': 'TIME',
    'status': 'STAT',
    'default': 'DEF',
    'all': 'ALL'
}
_calc3_format = {
    'mean': 'MEAN',
    'sdeviation': 'SDEV',
    'maximum': 'MAX',
    'minimum': 'MIN',
    'PKPK': 'PKPK'
}


class Calculate(Driver):
    """The Calculate command layer"""
    def __init__(self, transport, protocol):
        super(Calculate, self).__init__(transport, protocol)
        self._transport = transport
        self._protocol = protocol

        self.calculate1 = Calculate1(self._transport, self._protocol)
        self.calculate2 = Calculate2(self._transport, self._protocol)
        self.calculate3 = Calculate3(self._transport, self._protocol)


class Calculate1(Driver):
    def __init__(self, transport, protocol):
        super(Calculate1, self).__init__(transport, protocol)


class Calculate2(Driver):
    def __init__(self, transport, protocol):
        super(Calculate2, self).__init__(transport, protocol)


class Calculate3(Driver):
    def __init__(self, transport, protocol):
        super(Calculate3, self).__init__(transport, protocol)
        self.format = Command(
            'CALC3:FORM?',
            'CALC3:FORM',
            Mapping(_calc3_format)
        )

    def get_data(self):
        return self._query(('CALC3:DATA?', Stream(Float)))


class Display(Driver):
    """The Display command layer.

    :param transport: A transport object.

    :param protocol: A protocol object.
    """

    def __init__(self, transport, protocol):
        super(Display, self).__init__(transport, protocol)
        self.degits = Command(
            'DISP:DIG?',
            'DISP:DIG',
            Integer(4, 7)
        )
        self.enable = Command(
            'DISP:ENAB?',
            'DISP:ENAB',
            Boolean
        )
        self.data = Command(
            'DISP:TEXT?',
            'DISP:TEXT',
            String(0, 12)
        )
        self.state = Command(
            'DISP:TEXT:STAT?',
            'DISP:TEXT:STAT',
            Boolean
        )


class Triggering(Driver):
    def __init__(self, transport, protocol):
        super(Triggering, self).__init__(transport, protocol)
        self._transport = transport
        self._protocol = protocol

        self.arm = Arm(self._transport, self._protocol)
        self.trigger = Trigger(self._transport, self._protocol)

    def initiate(self):
        self._write(':INIT')

    def abort(self):
        self._write(':ABOR')


class Arm(Driver):
    def __init__(self, transport, protocol):
        super(Arm, self).__init__(transport, protocol)

        self.source = Command(
            ':ARM:SOUR?',
            ':ARM:SOUR',
            Mapping({'immediate': 'IMM',  # Pass operation through immediately
                     'external': 'EXT',  # Select External Triggering as event
                     'timer': 'TIM',  # Select timer as event
                     'manual': 'MAN',  # Select manual event
                     'bus': 'BUS',  # Select bus trigger as event.
                     'tlink': 'TLIN',
                     'nstest': 'NST',
                     'bstest': 'BST'
                     })
        )
        self.count = Command(
            ':ARM:COUN?',
            ':ARM:COUN',
            Integer(1, 2048)
        )
        self.timer = Command(
            ':ARM:TIM?',
            ':ARM:TIM',
            Float(0.001, 99999.999)
        )


class Format(Driver):
    """The Format command layer.

        :param transport: A transport object.

        :param protocol: A protocol object.
    """
    def __init__(self, transport, protocol):
        super(Format, self).__init__(transport, protocol)

        self.data = Command(
            'FORM?',
            'FORM',
            Mapping({
                'ascii': 'ASC',
                'real': 'REAL',
                '32': '32',
                'sreal': 'SRE'
            })
        )
        self.elements = Command(
            'FORM:ELEM?',
            'FORM:ELEM',
            Stream(Mapping(_data_elements))
        )
        self.border = Command(
            'FORM:BORD?',
            'FORM:BORD',
            Mapping({'normal': 'NORM', 'swapped': 'SWAP'})
        )
        self.register = Command(
            'FORM:SREG?',
            'FORM:SREG',
            Mapping({'ascii': 'ASC', 'hexadecimal': 'HEX', 'octal': 'OCT', 'binary': 'BIN'})
        )
        self.soruce2 = Command(
            'FORM:SREG?',
            'FORM:SREG',
            Mapping({'ascii': 'ASC', 'hexadecimal': 'HEX', 'octal': 'OCT', 'binary': 'BIN'})
        )


class System(Driver):
    def __init__(self, transport, protocol):
        super(System, self).__init__(transport, protocol)
        self._transport = transport
        self._protocol = protocol

        self.zero_check = SystemZeroCheck(self._transport, self._protocol)
        self.zero_correct = SystemZeroCorrect(self._transport, self._protocol)

        self.power_line_frequency = Command(
            'SYST:LFR?',
            'SYST:LFR',
            Mapping({'50': 50, '60': 60})
        )
        self.auto_power_line_frequency = Command(
            'SYST:LFR:AUTO?',
            'SYST:LFR:AUTO',
            Boolean
        )
        self.autozero = Command(
            'SYST:AZER?',
            'SYST:AZER',
            Boolean
        )

    def preset(self):
        self._write('SYST:PRES')

    def reset_timestamp(self):
        self._write('SYST:TIME:RES')

    def error_oldest(self, code_only=False):
        if code_only:
            self._write('SYST:ERR:CODE?')
        else:
            self._write('SYST:ERR?')

    def error_all(self, code_only=False):
        if code_only:
            self._write('SYST:ERR:CODE:ALL?')
        else:
            self._write('SYST:ERR:ALL?')

    def error_count(self):
        self._write('SYST:ERR:COUN?')


class SystemZeroCheck(Driver):
    def __init__(self, transport, protocol):
        super(SystemZeroCheck, self).__init__(transport, protocol)
        self.enable = Command(
            'SYST:ZCH:STAT?',
            'SYST:ZCH:STAT',
            Boolean
        )


class SystemZeroCorrect(Driver):
    def __init__(self, transport, protocol):
        super(SystemZeroCorrect, self).__init__(transport, protocol)
        self.enable = Command(
            'SYST:ZCOR:STAT?',
            'SYST:ZCOR:STAT',
            Boolean
        )

    def acquire(self):
        self._write('SYST:ZCOR:ACQ')


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
        self.continuous = self.continuous_mode = self.continuous_initiation = Command(
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
        self.autodelay = Command(
            ':TRIG:DEL:AUTO?',
            ':TRIG:DEL:AUTO',
            Boolean
        )
        self.source = Command(
            ':TRIG:SOUR?',
            ':TRIG:SOUR',
            Mapping({'immediate': 'IMM',  # Pass operation through immediately
                     'tlink': 'TLIN'
                     })
        )

    def clear(self):
        self._write(':TRIG:CLE')


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
        self.nplc = Command(
            'NPLC?',
            'NPLC',
            Float(0.01, 60)
        )
        self.auto_range = Command(
            'RANG:AUTO?',
            'RANG:AUTO',
            Boolean
        )
        self.range = Command(
            'RANG?',
            'RANG',
            Float(0, I_MAX)
        )

    def get_data(self):
        """reads the latest instrument reading."""
        return self._query((':DATA?', Stream(Float)))


class Trace(Driver):
    """TRACe subsystem. Used to configure and control data storage into buffer.

    :ivar free: [int, int] The first value indicates available memory in bytes.
        The second indicates memory reserved to store readings in bytes.

    :ivar int points: buffer size in integer. (from 1 to 3000)
    :ivar feed: The source of readings to be placed in the buffer
        'sense' means raw readings
        'calculate' means calculated math readings
        'none' means no readings
    :ivar control: 'never' disables storage into the buffer.
                   'next' enables storage.
    """

    def __init__(self, transport, protocol):
        super(Trace, self).__init__(transport, protocol)
        self.free = Command(query=':TRAC:FREE?', type_=[Integer, Integer])
        self.points = Command(
            ':TRAC:POINts?',
            ':TRAC:POINts',
            Integer(1, 3000)
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


class K6487(iec.IEC60488, iec.Trigger, iec.StoredSetting):
    """Keithley Model 6487 Picoammeter/Voltage Source"""
    def __init__(self, transport):
        super(K6487, self).__init__(transport)
        self.triggering = Triggering(self._transport, self._protocol)
        self.triggering.continuous_initiation = False
        self.display = Display(self._transport, self._protocol)
        self.initiate = self.triggering.initiate

        self.sense = Sense(self._transport, self._protocol)
        self.trace = Trace(self._transport, self._protocol)
        self.system = System(self._transport, self._protocol)
        self.format = Format(self._transport, self._protocol)

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
