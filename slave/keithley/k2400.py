# -*- coding: utf-8 -*-
"""Keithley Model 2400 Source-Measure Unit"""
import itertools
import slave.iec60488 as iec
from slave.driver import Command, Driver
from slave.types import Boolean, Float, Integer, Mapping, Stream

try:
    import typing
except ImportError:
    typing = None


_format_elements = {
    'voltage': 'VOLT',
    'current': 'CURR',
    'resistance': 'RES',
    'time': 'TIME',
    'status': 'STAT'
}

_sense_functions = {
    'voltage': '"VOLT:DC"',
    'current': '"CURR:DC"',
    'resistance': '"RES"'
}
_source_functions = {
    'voltage': 'VOLT',
    'current': 'CURR',
}
_trigger_sources = {
    'immediate': 'IMM',
    'tlink': 'TLIN',
}
_arm_sources = {
    'immediate': 'IMM',
    'tlink': 'TLIN',
    'timer': 'TIM',
    'manual': 'MAN',
    'bus': 'BUS',
    'nstest': 'NST',
    'pstest': 'PST',
    'bstest': 'BST',
}

"""NOTE: The trigger subsystem must be in the Idle state for the status OPC bit to be
true. As far as triggers are concerned, OPC is false whenever the trigger subsystem
is in the Initiated state."""


# Maximum measure (source) values for B2902A
I_MAX = 10.0
V_MAX = 210.0
R_MAX = 200e6


def _command(mapping, query=None, write=None, type_=None, protocol=None, mode='rw'):
    query = query if query is None else query.format(**mapping)
    write = write if write is None else write.format(**mapping)
    if mode in ('r', 'ro'):
        write = None
    elif mode in ('w', 'wo'):
        query = None
    return Command(query, write, type_, protocol)


# -----------------------------------------------------------------------------
# Trigger Command Layer
# -----------------------------------------------------------------------------


class Triggering(Driver):
    """
    :ivar count: the trigger count for the specified device action. (min: 1, max: 100000, def: 1)
    :ivar delay: trigger delay in seconds (min: 0, max: 100, def: 0)
    :ivar source: trigger source, such as 'immediate', 'tlink', 'timer', 'manual', ...
    :ivar timer: the interval of the TIMer trigger source for the specified device action.
        (min: 1e-5, max: 1e5, def: 1e-5)
    """
    def __init__(self, transport, protocol, channel=1, layer='TRIG'):
        """
        :param channel: Trigger channel (Not used for K2400).
        :param layer: Trigger layer. 'TRIG' or 'ARM'.
        """
        super(Triggering, self).__init__(transport, protocol)

        if layer not in ('TRIG', 'ARM'):
            raise ValueError('Unknown layer: \'{0}\''.format(layer))

        m = {'l': layer}

        mode = 'rw'

        self.count = _command(m, ':{l}:COUN?', ':{l}:COUN', Integer(1, 2500), mode=mode)
        self.source = _command(m, ':{l}:SOUR?', ':{l}:SOUR',
                               Mapping(_trigger_sources if layer == 'TRIG' else _arm_sources),
                               mode=mode)
        if layer == 'ARM':
            self.timer = _command(m, ':{l}:TIM?', ':{l}:TIM', Float(0.001, 99999.99), mode=mode)
        if layer == 'TRIG':
            self.delay = _command(m, ':{l}:DEL?', ':{l}:DEL', Float(0, 999.9999), mode=mode)

    def abort(self):
        """Aborts the specified device action for the specified channel. Trigger status is
        changed to idle.

        ..NOTE: abort() method in TRIG and ARM is the same."""
        self._write(':ABOR')

    def initiate(self):
        """Initiates the specified device action for the specified channel. Trigger status is
        changed from idle to initiated.

        ..NOTE: initiate() method in TRIG and ARM is the same."""
        self._write(':INIT')

    def wait_idle(self):
        """Checks the status of the specified device action for the specified channel, and waits
        until the status is changed to idle.

        :return True

        ..NOTE: wait_idle() method in TRIG and ARM is the same."""
        self._query((':IDLE?', Integer))


# -----------------------------------------------------------------------------
# Sense Command Layer
# -----------------------------------------------------------------------------


class Sense(Driver):
    """
    :ivar remote_sense: Enables or disables remote sensing (four-wire meausurements)
    :ivar voltage: The sense voltage command subsystem
    :ivar current: The sense current command subsystem
    :ivar resistance: The sense resistance command subsystem
    """
    def __init__(self, transport, protocol, channel=1):
        super(Sense, self).__init__(transport, protocol)
        self._channel = channel
        m = {'c': self._channel}
        self.remote_sense = self.four_wire = _command(m, 'SYST:RSEN?', ':SYST:RSEN', Boolean)

        self.voltage = SubSense(self._transport, self._protocol, channel, 'VOLT', V_MAX)
        self.current = SubSense(self._transport, self._protocol, channel, 'CURR', I_MAX)
        self.resistance = SubSense(self._transport, self._protocol, channel, 'RES', R_MAX)

    def enable(self, function):
        """Enables a function.

        :param function: 'voltage', 'current', or 'resistance'."""
        Command(write=':SENS%s:FUNC:ON' % self._channel, type_=Mapping(_sense_functions)).write(
            self._transport, self._protocol, function
        )

    def disable(self, function):
        """Disables a function.

        :param function: 'voltage', 'current', or 'resistance'."""
        Command(write=':SENS%s:FUNC:OFF' % self._channel, type_=Mapping(_sense_functions)).write(
            self._transport, self._protocol, function
        )

    def enable_all_functions(self):
        self._write(':SENS%s:FUNC:ALL' % self._channel)

    def disable_all_functions(self):
        self._write(':SENS%s:FUNC:OFF:ALL' % self._channel)

    def get_data(self, offset=None, size=None):
        """Returns the array data which contains all of the current measurement data, voltage
        measurement data, resistance measurement data, source output setting data, status
        data, or time data specified by the :FORMat:ELEMents:SENSe command. The data
        is not cleared until the :INITiate, :MEASure, or :READ command is executed.

        :param offset: Indicates the beginning of the data received.
            offset=n specifies the n+1th data. n is an integer, 0 to maximum

        :param size: Number of data to be received. 1 to maximum (depends on the
            buffer state). Parameter data type is NR1. If this parameter is
            not specified, all data from offset is returned.

            Note: if offset is None, size is ignored.

        Note: If trigger count > 1, it returns all the data measured."""
        if offset is None:
            opts = ''
        else:
            if size:
                opts = '{0}, {1}'.format(int(offset), int(size))
            else:
                opts = '{0}'.format(int(offset))

        return self._query((':SENS{c}:DATA? {o}'.format(c=self._channel, o=opts), Stream(Float)))

    def get_data_latest(self):
        """Returns the latest current measurement data, voltage measurement data, resistance
        measurement data, source output setting data, status data, or time data specified by
        the :FORMat:ELEMents:SENSe command. The data is not cleared until the
        :INITiate, :MEASure, or :READ command is executed.

        Note:  As shown in the following example, response may contain multiple data elements.
        This example contains the latest current data (ch1curr10) and source data
        (ch1sour10) of the 10-step sweep measurement by channel 1. With the ASCII data
        output format, each data is separated by a comma.
        ch1curr10,ch1sour10"""
        return self._query(('SENS{c}:DATA'.format(c=self._channel), Stream(Float)))

    @property
    def available_functions(self):
        """list of available functions"""
        return list(self._functions)

    @property
    def functions(self):
        return self._query(
            (
                ':SENS{c}:FUNC?'.format(c=self._channel),
                Stream(Mapping(_sense_functions))
            )
        )

    @functions.setter
    def functions(self, value):
        if isinstance(value, str):
            value = (value,)
        Command(
            write=':SENS{c}:FUNC'.format(c=self._channel),
            type_=Stream(Mapping(_sense_functions))
        ).write(self._transport, self._protocol, *value)

        for f in self.functions:
            if f not in value:
                Command(
                    write=':SENS{c}:FUNC:OFF'.format(c=self._channel),
                    type_=Stream(Mapping(_sense_functions))
                ).write(self._transport, self._protocol, f)


class SubSense(Driver):
    """
    :ivar float aperture: integration time for one point measurement.
    :ivar float nplc: integration time in number of power line cycles (1/50 s or 1/60 s)
    :ivar bool auto_range: enables/disables automatic range
    :ivar float range: range (upper limit of measurements)
    :ivar float compliance: (only for function='volt' or 'curr') sense compliance
    :ivar bool is_in_compliance: (only for function='volt' or 'curr')
    :ivar bool offset_compensated: (only for function = 'res')
    :ivar str mode: (only for function = 'res') auto or man range settings
    :ivar tuple auto_range_limit: Specifies upper/lower limit of automatic range settings
    """
    def __init__(self, transport, protocol, channel=1, function='VOLT', ulim=V_MAX):
        """
        :param channel: channel number. 1 or 2
        :param function: sense function, 'VOLT', 'CURR', or 'RES'
        :param ulim: upper limit of sense values"""
        super(SubSense, self).__init__(transport, protocol)
        if function not in ('VOLT', 'CURR', 'RES'):
            raise ValueError("Invalid function: '{0}'".format(function))
        self._channel = channel
        self._function = function
        self._ulim = ulim

        m = {'c': self._channel, 'f': self._function}

        self.nplc = _command(m, ':SENS{c}:{f}:NPLC?', ':SENS{c}:{f}:NPLC', Float(0.01, 10))
        self.auto_range = _command(m, ':SENS{c}:{f}:RANG:AUTO?', ':SENS{c}:{f}:RANGE:AUTO', Boolean)
        self.range = _command(m, ':SENS{c}:{f}:RANG?', ':SENS{c}:{f}:RANG', Float(0, ulim))
        if function in ('VOLT', 'CURR'):
            self.compliance = _command(m, ':SENS{c}:{f}:PROT?', ':SENS{c}:{f}:PROT', Float(0, ulim))
            self.is_in_compliance = _command(m, ':SENS{c}:{f}:PROT:TRIP?', type_=Boolean)
        if function == 'RES':
            self.offset_compensated = _command(m, ':SENS{c}:{f}:OCOM?', ':SENS{c}:{f}:OCOM', Boolean)
            self.mode = _command(
                m,
                ':SENS{c}:{f}:MODE?',
                ':SENS{c}:{f}:MODE',
                Mapping({'auto': 'AUTO', 'manual': 'MAN'})
            )

    @property
    def auto_range_limit(self):
        lower = self._query(
            (':SENS{c}:{f}:RANG:AUTO:LLIM?'.format(c=self._channel, f=self._function), Float(0, self._ulim))
        )
        upper = self._query(
            (':SENS{c}:{f}:RANG:AUTO:ULIM?'.format(c=self._channel, f=self._function), Float(0, self._ulim))
        )
        return lower, upper

    @auto_range_limit.setter
    def auto_range_limit(self, values):
        lower, upper = values[:2]
        type_ = Float(0, self._ulim)
        commands = []
        if lower is not None:
            lower_str = type_.dump(lower)
            commands.append(':SENS%s:%s:RANGE:AUTO:LLIM %s' % (self._channel, self._function, lower_str))
        if upper is not None:
            upper_str = type_.dump(upper)
            commands.append(':SENS%s:%s:RANGE:AUTO:ULIM %s' % (self._channel, self._function, upper_str))
        if (lower and upper) and (lower > upper):
            raise ValueError('The lower limit must be smaller or equal to the upper limit.')
        self._write('; '.join(commands))


# -----------------------------------------------------------------------------
# Source Command Layer
# -----------------------------------------------------------------------------


class Source(Driver):
    """The Source Command Subsystem.
        :ivar mode: Sets the source mode. available values: 'current', 'voltage'
        :ivar function_shape: Sets the source shape. available values: 'dc', 'pulse'
        :ivar voltage: The source voltage command subsystem.
        :ivar current: The source current command subsystem.
        :ivar sweep: The source sweep command subsystem.
        :ivar list: The source list command subsystem.
    """
    _functions = _source_functions

    def __init__(self, transport, protocol, channel=1):
        super(Source, self).__init__(transport, protocol)
        self._channel = channel
        m = {'c': self._channel}
        self.mode = self.function_mode = _command(
            m,
            ':SOUR{c}:FUNC:MODE?',
            ':SOUR{c}:FUNC:MODE',
            Mapping(self._functions)
        )
        self.function_shape = _command(
            m,
            ':SOUR{c}:FUNC:SHAPE?',
            ':SOUR{c}:FUNC:SHAPE',
            Mapping({'pulse': 'PULS', 'dc': 'DC'})
        )  # Model 2430 only
        self.sweep = SourceSweep(transport, protocol, channel)
        self.list = SourceList(transport, protocol, channel)
        self.current = SubSource(transport, protocol, channel, 'CURR', I_MAX)
        self.voltage = SubSource(transport, protocol, channel, 'VOLT', V_MAX)

    def invert(self, functions=()):
        """Inverts source. Effective only when using fixed source"""
        if isinstance(functions, str):
            functions = (functions,)
        for f in functions:
            if f.lower().startswith('curr'):
                self.current.level_triggered *= -1
                self.current.level *= -1
            elif f.lower().startswith('volt'):
                self.voltage.level_triggered *= -1
                self.voltage.level *= -1
            else:
                raise ValueError('Unknown function: %s' % f)

    @property
    def functions(self):
        """List of available functions"""
        return list(self._functions)


class SourceSweep(Driver):
    """The sweep command subsystem of the Source node.

    :ivar direction: Sweep from start to stop ('up') or from stop to start ('down')
    :ivar spacing: The sweep type, valid are 'linear', 'log' and 'list'.
    :ivar int points: The number of sweep points in the range 1 to 65535.
    :ivar ranging: The sweep ranging, valid are 'auto', 'best' and 'fixed'.
    """
    def __init__(self, transport, protocol, channel):
        super(SourceSweep, self).__init__(transport, protocol)
        self._channel = channel
        m = {'c': self._channel}
        self.direction = _command(
            m,
            ':SOUR{c}:SWE:DIR?',
            ':SOUR{c}:SWE:DIR',
            Mapping({'up': 'UP', 'down': 'DOWN'})
        )
        self.points = _command(
            m,
            ':SOUR{c}:SWE:POIN?',
            ':SOUR{c}:SWE:POIN',
            Integer(2, 2500),
        )
        self.ranging = _command(
            m,
            ':SOUR{c}:SWE:RANG?',
            ':SOUR{c}:SWE:RANG',
            Mapping({'best': 'BEST', 'fixed': 'FIX', 'auto': 'AUTO'})
        )
        self.spacing = _command(
            m,
            ':SOUR{c}:SWE:SPAC?',
            ':SOUR{c}:SWE:SPAC',
            Mapping({'linear': 'LIN', 'logarithmic': 'LOG'})
        )


class SourceList(Driver):
    """The list command subsystem of the Source node.

    It is used to define arbitrary current/voltage. E.g. writing a
    current sequence is as simple as::

        >>> k2400.source.list.current[:] = [-0.01, -0.02, 0.0]
        >>> len(k2400.source.list.current)
        3

    To extend the list, a special member function is provided::

        >>> k2400.source.list.current.extend([0.01, 0.0, 0.0])
        >>> k2400.source.list.current[:]
        [-0.01, -0.02, 0.0, 0.01, 0.0, 0.0]

    Slicing notation can also be used to manipulate the sequence::

        >>> k2400.source.list.current[::2] = [-0.03, 0.05, 0.07]
        >>> k2400.source.list.current[:]
        [-0.03, -0.02, 0.05, 0.01, 0.07, 0.0]

    :ivar current: An instance of :class:`~.SourceListSequence`, giving access
        to the current subsystem.
    :ivar voltage: An instance of :class:'~.SourceListSequence', giving access
        to he voltage subsystem.
    """
    def __init__(self, transport, protocol, channel=1):
        super(SourceList, self).__init__(transport, protocol)
        self.current = SourceListSequence(
            transport,
            protocol,
            node='CURR',
            type=Float(min=-I_MAX, max=I_MAX),
            channel=channel,
        )
        self.voltage = SourceListSequence(
            transport,
            protocol,
            node='VOLT',
            type=Float(min=-V_MAX, max=V_MAX),
            channel=channel,
        )


class SourceListSequence(Driver):
    def __init__(self, transport, protocol, node, type, channel=1):
        super(SourceListSequence, self).__init__(transport, protocol)
        self._channel = channel
        self._node = node
        m = {'c': self._channel, 'node': self._node}
        self._extend = _command(
            m,
            write=':SOUR{c}:LIST:{node}:APPEND',
        )
        self._sequence = _command(
            m,
            ':SOUR{c}:LIST:{node}?',
            ':SOUR{c}:LIST:{node}',
            itertools.repeat(type)
        )

    def extend(self, iterable):
        """Extends the list."""
        self._extend = iterable

    def __getitem__(self, item):
        return self._sequence[item]

    def __setitem__(self, item, value):
        seq = self._sequence
        seq[item] = value
        self._sequence = seq

    def __len__(self):
        return self._query((':SOUR:LIST:{}:POIN?'.format(self._node), Integer))


class SubSource(Driver):
    """
    :ivar float level: Sets & gets level. This is applied when the output is on.
    :ivar float level_triggered: Sets & gets level when triggered. This is applied e.g. when initiate() is called.
    :ivar float range: The current range in ampere. [-105e-3, 105e3].
    :ivar bool auto_range: A boolean flag to enable/disable auto ranging.
    :ivar float start: The start current.
    :ivar float step: The step current.
    :ivar float stop: The stop current.
    :ivar float center: The center current.
    :ivar float span: The span current.
    :ivar mode: source mode. 'sweep', 'list', or 'fixed'
    :ivar tuple auto_range_limit: limits of source range for automatic range determination
    """
    def __init__(self, transport, protocol, channel=1, function='VOLT', ulim=V_MAX):
        super(SubSource, self).__init__(transport, protocol)
        self._channel = channel
        self._function = function
        self._ulim = ulim

        m = {'c': self._channel, 'f': self._function}

        self.level = self.amplitude = _command(
            m,
            ':SOUR{c}:{f}:LEV?',
            ':SOUR{c}:{f}:LEV',
            Float(-ulim, ulim)
        )
        self.level_triggered = _command(
            m,
            ':SOUR{c}:{f}:TRIG?',
            ':SOUR{c}:{f}:TRIG',
            Float(-ulim, ulim)
        )
        self.mode = _command(
            m,
            ':SOUR{c}:{f}:MODE?',
            ':SOUR{c}:{f}:MODE',
            Mapping({'sweep': 'SWE', 'list': 'LIST', 'fixed': 'FIX'})
        )
        self.range = _command(
            m,
            ':SOUR{c}:{f}:RANG?',
            ':SOUR{c}:{f}:RANG',
            Float(0, ulim)
        )
        self.auto_range = _command(
            m,
            ':SOUR{c}:{f}:RANG:AUTO?',
            ':SOUR{c}:{f}:RANG:AUTO',
            Boolean
        )

        # for sweep modes
        self.center = self.sweep_center = _command(
            m,
            ':SOUR{c}:{f}:CENT?',
            ':SOUR{c}:{f}:CENT',
            Float(-ulim, ulim)
        )
        self.span = self.sweep_span = _command(
            m,
            ':SOUR{c}:{f}:SPAN?',
            ':SOUR{c}:{f}:SPAN',
            Float(-ulim, ulim)
        )
        self.points = self.sweep_points = _command(
            m,
            ':SOUR{c}:POIN?',
            ':SOUR{c}:POIN',
            Integer(1, 2500)
        )
        self.step = self.sweep_step = _command(
            m,
            ':SOUR{c}:{f}:STEP?',
            ':SOUR{c}:{f}:STEP',
            Float(min=0)
        )
        self.start = self.sweep_start = _command(
            m,
            ':SOUR{c}:{f}:STAR?',
            ':SOUR{c}:{f}:STAR',
            Float(-ulim, ulim)
        )
        self.stop = self.sweep_stop = _command(
            m,
            ':SOUR{c}:{f}:STOP?',
            ':SOUR{c}:{f}:STOP',
            Float(-ulim, ulim)
        )

        # for list mode
        self.list = SourceListSequence(
            transport, protocol,
            node=function,
            type=Float(-ulim, ulim),
            channel=channel
        )

# -----------------------------------------------------------------------------
# Format Command Layer
# -----------------------------------------------------------------------------


class Format(Driver):
    def __init__(self, transport, protocol):
        super(Format, self).__init__(transport, protocol)
        self.elements = self.sense_elements = Command(
            ':FORM:ELEM:SENS?', ':FORM:ELEM:SENS', Stream(Mapping(_format_elements))
        )


# -----------------------------------------------------------------------------
# Output Command Layer
# -----------------------------------------------------------------------------


class Output(Driver):
    """The Output Command Subsystem.

    :ivar bool auto_on: If this function is enabled,
        the source output is automatically turned on when the :INITiate or :READ command
        is sent. Default is True.
    :ivar bool state: Enables or disables the source output.
    :ivar bool interlock_state: Enables or disables hardware interlock pin
    :ivar bool interlock_tripped: Checks if the enabled interlock has been tripped. (1 means that the source can be turned on)
    :ivar off_mode: Selects the output-off state of the SourceMeter.
        'high-impedance': the output relay opens when the source is turned off.
        'normal': source V, V=0, compliance 0.5% (default)
        'zero': source V, V=0, no change in current compliance.
        'guard': source I, I=0, compliance 0.5%
    """
    def __init__(self, transport, protocol, channel=1):
        super(Output, self).__init__(transport, protocol)
        self._channel = channel
        m = {'c': self._channel}
        self.state = _command(m, ':OUTP{c}?', 'OUTP{c}', Boolean)
        self.interlock_state = _command(m, ':OUTP{c}:INT:STAT?', ':OUTP{c}:INT:STAT', Boolean)
        self.interlock_tripped = _command(m, ':OUTP{c}:INT:TRIP?', type_=Boolean)
        self.off_mode = _command(m, ':OUTP{c}:SMODE?', ':OUTP{c}:SMODE',
                                 Mapping({'high-impedance': 'HIMP', 'normal': 'NORM', 'zero': 'ZERO', 'guard': 'GUAR'}))

    def save_settings(self, idx=0):
        """Save the channel setup.

        :param idx: channel setup id. 0 or 1"""
        self._write(':OUTP{c}:SAVE {idx}'.format(c=self._channel, idx=idx))

    def recall_settings(self, idx=0):
        """Recall teh channel setup.

        :param idx: channel setup id. 0 or 1"""
        self._write(':OUTP{c}:REC {idx}'.format(c=self._channel, idx=idx))


class Trace(Driver):
    """
    :ivar free: the available size (available) and the total size (total) of the trace buffer.
    :ivar points: the size of the trace buffer"""
    def __init__(self, transport, protocol, channel=1):
        super(Trace, self).__init__(transport, protocol)
        self._channel = channel
        m = {'c': self._channel}
        self.free = _command(m, ':TRAC{c}:FREE?', ':TRAC{c}:FREE', [Integer, Integer])
        self.points = _command(m, ':TRAC{c}:POIN?', 'TRAC{c}:POIN', Integer(1, 100000))
        self.actual_points = _command(m, ':TRAC{c}:POIN:ACT?', type_=Integer)

    def clear(self):
        self._write(':TRAC{c}:CLE'.format(c=self._channel))

    def get_data(self, offset=None, size=None):
        command = ':TRAC{c}:DATA?'.format(c=self._channel)
        if offset is not None:
            if size:
                command += ' {0},{1}'.format(offset, size)
            else:
                command += ' {0}'.format(offset)
        self._query((command, Stream(Float)))


# -----------------------------------------------------------------------------
# Common set-ups
# -----------------------------------------------------------------------------

class Setup(object):
    """Provides common quick setups."""
    def __init__(self, smu):
        self._smu = smu  # type: K2400

    def triggering(self, count=None, delay=None, channel=1):
        """
        :param count: trigger count
        :param delay: trigger delay
        :param channel: source channel, 1 or 2. (not used)
        """
        trig = self._smu.triggerings[channel - 1]
        if count is not None:
            trig.count = count
        if delay is not None:
            trig.delay = delay

    def fixed_source(self, function, value=None, channel=1):
        """Changes source function and sets output value. Also sets trigger count 1.

        :param function: source function, 'volt(age)' or 'curr(ent)'
        :param value: source value
        :param channel: SMU channel, default is 1
        """
        source = self._smu.sources[channel - 1]  # type: Source
        if function.lower().startswith('volt'):
            sub = source.voltage
        elif function.lower().startswith('curr'):
            sub = source.current
        else:
            raise ValueError("Invalid function: %r" % function)

        self.triggering(count=1, channel=channel)
        source.function_mode = function
        sub.mode = 'fixed'
        if value is not None:
            sub.level = value
            sub.level_triggered = value

    def fixed_source_with_compensation(self, function, value, channel=1):
        """ Sets up offset compensation by source inversion. ALso sets trigger count 2."""
        trig = self._smu.triggerings[channel - 1]  # type: Triggering
        source = self._smu.sources[channel - 1]  # type: Source
        source.function_mode = function
        trig.count = 2
        if function == 'volt':
            source.voltage.mode = 'list'
            source.voltage.list = (value, -value)
        elif function == 'curr':
            source.current.mode = 'list'
            source.current.list = (value, -value)

    def sweep_source(self, function, start, stop, points, channel=1):
        """Switch function mode and setup for sweep measurement

        :param str function: source function, 'volt(age)' or 'curr(ent)'
        :param float start: initial source value
        :param float stop: final source value
        :param int points: number of sweep points
        :param int channel: SMU channel, 1 or 2.
        """
        source = self._smu.sources[channel-1]  # type: Source

        if function.lower().startswith('volt'):
            sub = source.voltage
        elif function.lower().startswith('curr'):
            sub = source.current
        else:
            raise ValueError('Invalid function: %r' % function)

        self.triggering(count=points, channel=channel)
        source.function_mode = function

        sub.mode = 'sweep'
        sub.sweep_start = start
        sub.sweep_stop = stop
        sub.sweep_points = points

    def sense(self, function, auto_range=None, range_=None, nplc=None, compliance=None,
              four_wire=None, integration_time=None,
              channel=1):
        """Sets up voltage or current sense parameters.

        ..note: four wire settings apply both modes. to avoid confusion, this function does not support them.

        :param str function: 'voltage' or 'current'
        :param bool auto_range: enables or disables auto ranging
        :param float range_: upper limit of the sense range
        :param float nplc: number of power line cycles (integration time in (1/50) seconds)
        :param float compliance: sense compliance
        :param bool four_wire: activate or deactivate four_wire sensing
        :param float integration_time: integration time in seconds
        :param int channel: SMU channel, 1, or 2 (not used for K2400)
        """
        if auto_range and (range_ is not None):
            raise ValueError('Cannot enable auto_range and set range at the same time.')
        if (nplc is not None) and (integration_time is not None):
            raise ValueError('"nplc" and "integration_time" are mutually exclusive.')

        sense = self._smu.senses[channel-1]  # type: Sense
        if function.lower().startswith('volt'):
            sub = sense.voltage
        elif function.lower().startswith('curr'):
            sub = sense.current
        else:
            raise ValueError('Invalid function: %r' % function)

        if four_wire is not None:
            sense.four_wire = four_wire
        if auto_range is not None:
            sub.auto_range = auto_range
        if range_ is not None:
            sub.range = range_
        if nplc is not None:
            sub.nplc = nplc
        if integration_time is not None:
            sub.nplc = integration_time * 50
        if compliance is not None:
            sub.compliance = compliance

    def resistance(self, enable=None, mode=None, channel=1):
        """
        :param enable: None, True, or False
        :param mode: None, 'auto' or 'manual'
        :param channel: 1 or 2"""
        sense = self._smu.senses[channel - 1]  # type: Sense
        if enable is None:
            pass
        elif enable:
            sense.enable('resistance')
        else:
            sense.disable('resistance')
        if mode:
            sense.resistance.mode = mode


class K2400(iec.IEC60488, iec.Trigger, iec.StoredSetting):
    is_dual = False

    def __init__(self, transport):
        super(K2400, self).__init__(transport)

        ch = (1,)
        t, p = self._transport, self._protocol

        self.sources = tuple(Source(t, p, x) for x in ch)
        """:type: typing.List[Source]"""

        self.senses = tuple(Sense(t, p, x) for x in ch)
        """:type: typing.List[Sense]"""

        self.triggerings = tuple(Triggering(t, p, x, 'TRIG') for x in ch)
        """:type: typing.List[Triggering]"""

        self.arms = tuple(Triggering(t, p, x, 'ARM') for x in ch)
        """:type: typing.List[Triggering]"""

        self.outputs = tuple(Output(t, p, x) for x in ch)
        """:type: typing.List[Output]"""

        self.traces = tuple(Trace(t, p, x) for x in ch)
        """:type: typing.List[Trace]"""

        self.source = self.sources[0]
        self.sense = self.senses[0]
        self.arm = self.arms[0]
        self.triggering = self.triggerings[0]
        self.output = self.outputs[0]
        self.trace = self.traces[0]

        self.format = Format(self._transport, self._protocol)
        self.setup = Setup(self)

        self.sense_elements = Command(':FORM:ELEM:SENS?', ':FORM:ELEM:SENS', Stream(Mapping(_format_elements)))

    def beep(self, freq=200, duration=1):
        self._write(":SYST:BEEP:STAT ON")
        self._write(":SYST:BEEP %s,%s" % (freq, duration))

    def fetch(self):
        """Returns the latest measurement data specified by the :FORMat:ELEMents:SENSe command.

        The data is not cleared until the initiate(), measure(), or read() command is executed"""
        return self._query(('FETC?', Stream(Float)))

    def measure(self):
        """Executes a spot measurement (one-shot measurement) and returns the measurement result data.

        Measurement conditions must be set by SCPI commands or front panel
        operation before executing this command. Measurement items can be selected by
        the :FORMat:ELEMents:SENSe command."""
        return self._query(('MEAS?', Stream(Float)))

    def initiate(self):
        """Initiates selected channels."""
        self._write(':INIT')

    def abort(self):
        """aborts selected channels."""
        self._write(':ABOR')
