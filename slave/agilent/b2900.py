# -*- coding: utf-8 -*-
import re
from collections import Iterable

import slave.iec60488 as iec
from slave.driver import Command, Driver
from slave.transport import SimulatedTransport, Transport
from slave.types import Boolean, Float, Integer, Mapping, Stream, String

try:
    import typing
except ImportError:
    typing = None


_elements = {
    'voltage': 'VOLT',
    'current': 'CURR',
    'resistance': 'RES',
    'time': 'TIME',
    'status': 'STAT',
    'source': 'SOUR',
}
_sense_functions = {
    'voltage': '"VOLT"',
    'current': '"CURR"',
    'resistance': '"RES"',
}
_source_functions = {
    'voltage': 'VOLT',
    'current': 'CURR',
}


"""NOTE: The trigger subsystem must be in the Idle state for the status OPC bit to be
true. As far as triggers are concerned, OPC is false whenever the trigger subsystem
is in the Initiated state."""


# Maximum measure (source) values for B2902A
I_MAX = 10.0
V_MAX = 210.0
R_MAX = 200e6


def _convert_channel_list(channels=(), default='1', delimiter=','):
    if not channels:
        channels = [default]
    elif not hasattr(channels, '__iter__'):
        channels = [channels]
    return delimiter.join(str(x) for x in channels)


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
    :ivar bypass: Enables or disables a bypass for the event detector in the trigger layer.
    :ivar count: the trigger count for the specified device action. (min: 1, max: 100000, def: 1)
    :ivar delay: trigger delay in seconds (min: 0, max: 100, def: 0)
    :ivar source: trigger source, such as 'automatic internal', 'bus', ...
        'automatic internal' Automatically selects the trigger source most suitable for the present operating mode
                             by using internal algorithms.
        'bus'                Selects the remote interface trigger command such as the group execute trigger (GET)
                             and the *TRG command.
        'timer'              Selects a signal internally generated every interval set by the
                             trigger_timer.
        'int1', 'int2'
        'lan'
        'ext1', 'ext2', ..., 'ext14'
    :ivar timer: the interval of the TIMer trigger source for the specified device action.
        (min: 1e-5, max: 1e5, def: 1e-5)
    :ivar output_state: Enables or disables the trigger output for the status change between the arm layer
        and the trigger layer. (bool, default: False)
    :ivar output_signal: Selects the trigger output for the status change between the arm layer and the trigger
        layer. Multiple trigger output ports can be set.
        available values: 'ext1' (default), 'ext2', 'ext3', ..., 'ext14', 'lan', 'int1', 'int2'
    """
    _sources = {
        'automatic internal': 'AINT',
        'bus': 'BUS',
        'timer': 'TIM',
        'internal1': 'INT1',
        'internal2': 'INT2',
        'lan': 'LAN'
    }
    for n in range(1, 15):
        _sources['ext%s' % n] = n

    def __init__(self, transport, protocol, channel=1, layer='ALL', action='ALL'):
        """
        :param channel: Trigger channel. 1 or 2.
        :param layer: Trigger layer. 'TRIG', 'ARM', or 'ALL').
        :param action: Trigger Action. 'ACQ', 'TRAN', or 'ALL'"""
        super(Triggering, self).__init__(transport, protocol)

        if layer not in ('TRIG', 'ARM', 'ALL'):
            raise ValueError('Unknown layer: \'{0}\''.format(layer))
        if action not in ('ACQ', 'TRAN', 'ALL'):
            'Unknown action: \'{0}\''.format(action)
        self._layer = layer
        self._action = action

        self._channel = channel
        m = self._mapping = {'c': self._channel, 'l': self._layer, 'a': self._action}

        if action == 'ALL':
            # Writing values for action 'ALL' (e.g. :TRIG:ALL:COUN 1000) changes both TRANsient and ACQuire actions.
            # However, we cannot query set values by using e.g. * :TRIG:ALL:COUN?.
            # So, set all commands in 'ALL' actions write-only by setting mode='wo'.
            mode = 'wo'
            self.transient = Triggering(transport, protocol, channel, layer, 'TRAN')
            self.acquire = Triggering(transport, protocol, channel, layer, 'ACQ')
        else:
            mode = 'rw'

        self.bypass = _command(m, ':{l}{c}:{a}:BYP?', ':{l}{c}:{a}:BYP', Boolean, mode=mode)
        self.count = _command(m, ':{l}{c}:{a}:COUN?', ':{l}{c}:{a}:COUN', Integer(1, 100000), mode=mode)
        self.delay = _command(m, ':{l}{c}:{a}:DEL?', ':{l}{c}:{a}:DEL', Float(0, 100), mode=mode)
        self.source_lan = _command(
            m,
            ':{l}{c}:{a}:SOUR:LAN?',
            ':{l}{c}:{a}:SOUR:LAN',
            Stream(Mapping({('lan%s' % x): ('LAN%s' % x) for x in range(8)})),
            mode=mode
        )
        self.source = _command(m, ':{l}{c}:{a}:SOUR?', ':{l}{c}:{a}:SOUR', Mapping(self._sources), mode=mode)
        self.timer = _command(m, ':{l}{c}:{a}:TIM?', ':{l}{c}:{a}:TIM', Float(2e-5, 1e5), mode=mode)

        _trigger_outputs = ['ext%s' % x for x in range(15)] + ['lan'] + ['int1', 'int2']
        self.output_signal = _command(
            m,
            ':{l}{c}:{a}:TOUT:SIGN?',
            ':{l}{c}:{a}:TOUT:SIGN',
            Stream(Mapping({o: o.upper() for o in _trigger_outputs})),
            mode=mode
        )
        self.output_state = _command(m, ':{l}{c}:{a}:TOUT:STAT?', ':{l}{c}:{a}:TOUT:STAT', Boolean, mode=mode)

    def send_immediate(self):
        """Sends an immediate trigger for the specified device action.

        When the status of the specified device action is initiated, the trigger causes the
        specified device action."""
        self._write(':{l}:{a}:IMM (@{c})'.format(**self._mapping))

    def abort(self):
        """Aborts the specified device action for the specified channel. Trigger status is
        changed to idle.

        ..NOTE: abort() method in TRIG and ARM is the same."""
        self._write(':ABOR:{a} (@{c})'.format(**self._mapping))

    def initiate(self):
        """Initiates the specified device action for the specified channel. Trigger status is
        changed from idle to initiated.

        ..NOTE: initiate() method in TRIG and ARM is the same."""
        self._write(':INIT:{a} (@{c})'.format(**self._mapping))

    def wait_idle(self):
        """Checks the status of the specified device action for the specified channel, and waits
        until the status is changed to idle.

        :return True

        ..NOTE: wait_idle() method in TRIG and ARM is the same."""
        self._query((':IDLE{c}:{a}?'.format(**self._mapping), Integer))


# -----------------------------------------------------------------------------
# Sense Command Layer
# -----------------------------------------------------------------------------


class Sense(Driver):
    """
    :ivar wait_auto: Enables or disables the initial wait time used for calculating the measurement wait
        time for the specified channel. The initial wait time is automatically set by the
        instrument and cannot be changed. See :SENSe:WAIT[:STATe].
    :ivar wait_gain: Sets the gain value used for calculating the measurement wait time for the specified
        channel.
    :ivar wait_offset: Sets the offset value used for calculating the measurement wait time for the specified
        channel.
    :ivar wait_state: Enables or disables the measurement wait time for the specified channel. The wait
        time is defined as the time the measurement channel cannot start measurement after
        the start of a DC output or the trailing edge of a pulse."""
    _functions = _sense_functions

    def __init__(self, transport, protocol, channel=1):
        super(Sense, self).__init__(transport, protocol)
        self._channel = channel
        m = {'c': self._channel}
        self.remote_sense = self.four_wire = _command(m, ':SENS{c}:REM?', ':SENS{c}:REM', Boolean)
        self.wait_auto = _command(m, ':SENS{c}:WAIT:AUTO?', ':SENS{c}:WAIT:AUTO', Boolean)
        self.wait_gain = _command(m, ':SENS{c}:WAIT:GAIN?', ':SENS{c}:WAIT:GAIN', Float(0, 100))
        self.wait_offset = _command(m, ':SENS{c}:WAIT:OFFS?', ':SENS{c}:WAIT:OFFS', Float(0, 1))
        self.wait_state = _command(m, ':SENS{c}:WAIT?', ':SENS{c}:WAIT', Boolean)

        self.voltage = SubSense(self._transport, self._protocol, channel, 'VOLT', V_MAX)
        self.current = SubSense(self._transport, self._protocol, channel, 'CURR', I_MAX)
        self.resistance = SubSense(self._transport, self._protocol, channel, 'RES', R_MAX)

    def enable(self, function):
        Command(write=':SENS{c}:FUNC:ON'.format(c=self._channel), type_=Mapping(self._functions)).write(
            self._transport, self._protocol, function
        )

    def disable(self, function):
        Command(write=':SENS{c}:FUNC:OFF'.format(c=self._channel), type_=Mapping(self._functions)).write(
            self._transport, self._protocol, function
        )

    def enable_all_functions(self):
        self._write(':SENS{c}:FUNC:ALL'.format(c=self._channel))

    def disable_all_functions(self):
        self._write(':SENS{c}:FUNC:OFF:ALL'.format(c=self._channel))

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
        return tuple(self._functions)

    @property
    def functions(self):
        return self._query(
            (
                ':SENS{c}:FUNC?'.format(c=self._channel),
                Stream(Mapping(self._functions))
            )
        )

    @functions.setter
    def functions(self, value):
        if isinstance(value, str):
            value = (value,)
        self.enable_all_functions()
        for f in self.available_functions:
            if f not in value:
                self.disable(f)


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
        :param function: sense function, 'volt', 'curr', or 'res'
        :param ulim: upper limit of sense values"""
        super(SubSense, self).__init__(transport, protocol)
        if function not in ('VOLT', 'CURR', 'RES'):
            raise ValueError("Invalid function: '{0}'".format(function))
        self._channel = channel
        self._function = function
        self._ulim = ulim

        m = {'c': self._channel, 'f': self._function}

        self.aperture = _command(m, ':SENS{c}:{f}:APER?', ':SENS{c}:{f}:APER', Float(8e-6, 2))
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
        :ivar continuous_triggering: Boolean. Enables and disables the source triggering.
        :ivar sweep_direction: Sets the source sweep direction. available values: 'up', 'down'
        :ivar sweep_points: Sets the number of source sweep points. (min: 1, max: 2500)
        :ivar sweep_ranging: Sets the source sweep range. available values: 'best', 'auto', 'fixed'
        :ivar sweep_spacing: Sets the source sweep space. available values: 'linear', 'logarithmic'
        :ivar sweep_mode: Sets the source sweep mode. available values: 'single', 'double'
        :ivar wait_auto: Enables or disables the initial wait time used for calculating the source wait
            time for the specified channel. The initial wait time is automatically set by the
            instrument and cannot be changed. See :SOURCe:WAIT[:STATe].
        :ivar wait_gain: Sets the gain value used for calculating the source wait time for the specified
            channel.
        :ivar wait_offset: Sets the offset value used for calculating the source wait time for the specified
            channel.
        :ivar wait_state: Enables or disables the source wait time for the specified channel. The wait
            time is defined as the time the source channel cannot change the output after
            the start of a DC output or the trailing edge of a pulse
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
        )
        self.continuous_triggering = _command(
            m,
            ':SOUR{c}:FUNC:TRIG:CONT?',
            ':SOUR{c}:FUNC:TRIG:CONT',
            Boolean
        )
        self.sweep = SourceSweep(transport, protocol, channel)
        self.sweep_direction = object.__getattribute__(self.sweep, 'direction')
        self.sweep_mode = object.__getattribute__(self.sweep, 'mode')
        self.sweep_points = object.__getattribute__(self.sweep, 'points')
        self.sweep_ranging = self.sweep_range = object.__getattribute__(self.sweep, 'ranging')
        self.sweep_spacing = self.sweep_space = object.__getattribute__(self.sweep, 'spacing')

        self.wait_auto = _command(m, ':SOUR{c}:WAIT:AUTO?', ':SOUR{c}:WAIT:AUTO', Boolean)
        self.wait_gain = _command(m, ':SOUR{c}:WAIT:GAIN?', ':SOUR{c}:WAIT:GAIN', Float(0, 100))
        self.wait_offset = _command(m, ':SOUR{c}:WAIT:OFFS?', ':SOUR{c}:WAIT:OFFS', Float(0, 1))
        self.wait_state = _command(m, ':SOUR{c}:WAIT?', ':SOUR{c}:WAIT', Boolean)

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
    :ivar spacing: The sweep type, valid are 'linear', or 'log'
    :ivar int points: The number of sweep points in the range 1 to 2500 (write only).
    :ivar ranging: The sweep ranging, valid are 'auto', 'best' and 'fixed'.
    """
    def __init__(self, transport, protocol, channel):
        super(SourceSweep, self).__init__(transport, protocol)
        self._channel = channel
        m = {'c': channel}
        self.direction = _command(
            m,
            ':SOUR{c}:SWE:DIR?',
            ':SOUR{c}:SWE:DIR',
            Mapping({'up': 'UP', 'down': 'DOWN'})
        )
        # to query number of sweep points we need to use "[:SOURce]:<CURRent|VOLTage>:POINts?".
        # see discussions on https://github.com/t-onoz/slave/pull/1
        self.points = _command(
            m,
            write=':SOUR{c}:SWE:POIN',
            type_=Integer(1, 2500)
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
        self.mode = _command(
            m,
            ':SOUR{c}:SWE:STA?',
            ':SOUR{c}:SWE:STA',
            Mapping({'single': 'SING', 'double': 'DOUB'})
        )


class SubSource(Driver):
    """

    :ivar level: Sets & gets level. This is applied when the output is on.
    :ivar level_triggered: Sets & gets level when triggered. This is applied e.g. when initiate() is called.
    :ivar mode: source mode. 'sweep', 'list', or 'fixed'
    :ivar tuple auto_range_limit: limits of source range for automatic range determination
    """
    def __init__(self, transport, protocol, channel, function='VOLT', ulim=V_MAX):
        super(SubSource, self).__init__(transport, protocol)
        self._channel = channel
        self._function = function
        self._ulim = ulim

        m = {'c': self._channel, 'f': self._function}

        self.center = _command(
            m,
            ':SOUR{c}:{f}:CENT?',
            ':SOUR{c}:{f}:CENT',
            Float(-ulim, ulim)
        )
        self.span = _command(
            m,
            ':SOUR{c}:{f}:SPAN?',
            ':SOUR{c}:{f}:SPAN',
            Float(-ulim, ulim)
        )
        self.level = _command(
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
        self.auto_range_limit = _command(
            m,
            ':SOUR{c}:{f}:RANG:AUTO:LLIM?',
            ':SOUR{c}:{f}:RANG:AUTO:LLIM',
            Float(-ulim, ulim)
        )

        # for sweep modes
        self.points = self.sweep_points = _command(
            m,
            ':SOUR{c}:{f}:POIN?',
            ':SOUR{c}:{f}:POIN',
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
        self.list = _command(
            m,
            ':SOUR{c}:LIST:{f}?',
            ':SOUR{c}:LIST:{f}',
            Stream(Float(-ulim, ulim))
        )

# -----------------------------------------------------------------------------
# Format Command Layer
# -----------------------------------------------------------------------------


class Format(Driver):
    _elements = _elements

    def __init__(self, transport, protocol):
        super(Format, self).__init__(transport, protocol)
        self.elements = self.sense_elements = Command(
            ':FORM:ELEM:SENS?', ':FORM:ELEM:SENS', Stream(Mapping(self._elements))
        )


# -----------------------------------------------------------------------------
# Output Command Layer
# -----------------------------------------------------------------------------


class Output(Driver):
    """The Output Command Subsystem.

    :ivar bool filter_auto: Enables or disables the automatic filter function. Default is False.
    :ivar float filter_cutoff_frequency: The cutoff frequency of the output filter.
        .. note::
              This command setting is ignored if the automatic filter function is enabled by the filter_auto variable.
    :ivar bool filter_status: Enables or disables the output filter. Default is True.
    :ivar float filter_time_constant: The time constant of the output filter.
        .. note::
            The time constant can be expressed by using the cutoff frequency set by the filter_cutoff_frequency.
            So the last command setting is effective for both time_constant and frequency.
    :ivar bool high_capacitance_mode: high capacitance mode. This mode is effective for high
        capacitive DUT.
    :ivar low_state: State of the low terminal.
        'float': the floating state.
        'ground': the ground state. The lwo terminal is connected to ground.
        .. note::
            Before executing this command, the source output must be disabled by the state command.
            Or else, an error occurs.
    :ivar bool auto_off: automatic output off function. If this function is enabled,
        the source output is automatically turned off immediately when the grouped
        channels change status from busy to idle. Default is False.

    :ivar bool auto_on: If this function is enabled,
        the source output is automatically turned on when the :INITiate or :READ command
        is sent. Default is True.
    :ivar bool state: Enables or disables the source output.
    :ivar off_mode: Selects the source condition after output off.
    """
    def __init__(self, transport, protocol, channel=1):
        super(Output, self).__init__(transport, protocol)
        self._channel = channel
        m = {'c': self._channel}
        self.filter_auto = _command(m, ':OUTP{c}:FILT:AUTO?', ':OUTP{c}:FILT:AUTO', Boolean)
        self.filter_cutoff_frequency = _command(m, ':OUTP{c}:FILT:FREQ?', ':OUTP{c}:FILT:FREQ', Float(31.830, 31831))
        self.filter_status = _command(m, ':OUTP{c}:FILT?', ':OUTP{c}:FILT', Boolean)
        self.filter_time_constant = _command(m, ':OUTP{c}:FILT:TCON?', ':OUTP{c}:FILT:TCON', Float)
        self.high_capacitance_mode = _command(m, ':OUTP{c}:HCAP?', ':OUTP{c}:HCAP', Boolean)
        self.low_state = _command(
            m,
            ':OUTP{c}:LOW?',
            ':OUTP{c}:LOW',
            Mapping({'float': 'FLO', 'ground': 'GRO'})
        )
        self.auto_off = _command(m, ':OUTP{c}:OFF:AUTO?', ':OUTP{c}:OFF:AUTO', Boolean)
        self.auto_on = _command(m, ':OUTP{c}:ON:AUTO?', ':OUTP{c}:ON:AUTO', Boolean)
        self.state = _command(m, ':OUTP{c}?', 'OUTP{c}', Boolean)
        self.off_mode = _command(m, ':OUTP{c}:OFF:MODE?', ':OUTP{c}:OFF:MODE',
                                 Mapping({'high-impedance': 'HIZ', 'normal': 'NORM', 'zero': 'ZERO'}))

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
        self._smu = smu  # type: B2900

    def triggering(self, source=None, count=None, timer=None, delay=None, channel=1):
        """
        :param source: trigger source, such as 'automatic internal', 'bus', 'time'
        :param count: trigger count
        :param timer: timer length
        :param delay: trigger delay
        :param channel: source channel, 1 or 2.
        """
        trig = self._smu.triggerings[channel - 1]  # type: Triggering
        if source is not None:
            trig.source = source
        if count is not None:
            trig.count = count
        if timer is not None:
            trig.timer = timer
        if delay is not None:
            trig.delay = delay

    def fixed_source(self, function, value=None, channel=1):
        """Changes source function and sets output value. Also sets trigger count 1.

        :param str function: source function, 'volt(age)' or 'curr(ent)'
        :param float value: source value
        :param int channel: SMU channel, default is 1
        """
        source = self._smu.sources[channel-1]
        if function.lower().startswith('volt'):
            sub = source.voltage
        elif function.lower().startswith('curr'):
            sub = source.current
        else:
            raise ValueError("Invalid function: %r" % function)

        self.triggering(count=1, channel=channel)
        source.function_mode = function
        source.function_shape = 'dc'

        sub.mode = 'fixed'
        if value is not None:
            sub.level = value
            sub.level_triggered = value

    def fixed_source_with_compensation(self, function, value=None, channel=1):
        """ Sets up offset compensation by source inversion. ALso sets trigger count 2."""
        source = self._smu.sources[channel - 1]  # type: Source
        source.function_mode = function
        self.triggering(count=2, channel=channel)
        if function.lower().startswith('volt'):
            source.voltage.mode = 'list'
            value = source.voltage.level if value is None else value
            source.voltage.list = (value, -value)
        elif function.lower().startswith('curr'):
            source.current.mode = 'list'
            value = source.current.level if value is None else value
            source.current.list = (value, -value)

    def sweep_source(self, function, start, stop, points, channel=1):
        """Switch function mode and setup for sweep measurement

        :param str function: source function, 'volt(age)' or 'curr(ent)'
        :param float start: initial source value
        :param float stop: final source value
        :param int points: number of sweep points
        :param int channel: SMU channel, 1, or 2.
        """
        source = self._smu.sources[channel-1]
        if function.lower().startswith('volt'):
            sub = source.voltage
        elif function.lower().startswith('curr'):
            sub = source.current
        else:
            raise ValueError('Invalid function: %r' % function)

        self.triggering(count=points, channel=channel)
        source.function_mode = function
        source.function_shape = 'dc'

        sub.mode = 'sweep'
        sub.sweep_start = start
        sub.sweep_stop = stop
        sub.points = points

    def sense(self, function, auto_range=None, range_=None, nplc=None, compliance=None,
              four_wire=None, integration_time=None, channel=1):
        """Sets up voltage or current sense parameters.

        ..note: four wire settings apply both modes. to avoid confusion, this function does not support them.

        :param function: 'voltage' or 'current'
        :param auto_range: bool
        :param range_: upper limit of the sense range
        :param nplc: number of power line cycles (integration time in (1/50) seconds)
        :param compliance: sense compliance
        :param four_wire: activate or deactivate four_wire sensing
        :param integration_time: integration time in seconds
        :param channel: SMU channel, 1, or 2.
        """
        sense = self._smu.senses[channel-1]
        if auto_range and (range_ is not None):
            raise ValueError('Cannot enable auto_range and set range at the same time.')
        if None not in (nplc, integration_time):
            raise ValueError('"nplc" and "integration_time" are mutually exclusive.')
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
            sub.aperture = integration_time
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


# -----------------------------------------------------------------------------
# B2902A 2ch SMU
# -----------------------------------------------------------------------------


class B2900(iec.IEC60488, iec.Trigger, iec.StoredSetting):
    is_dual = False

    def __init__(self, transport):
        super(B2900, self).__init__(transport)
        self.__check__()

        ch = (1, 2) if self.is_dual else (1,)
        t, p = self._transport, self._protocol

        self.sources = tuple(Source(t, p, x) for x in ch)
        """:type: typing.List[Source]"""

        self.senses = tuple(Sense(t, p, x) for x in ch)
        """:type: typing.List[Sense]"""

        self.triggerings = tuple(Triggering(t, p, x, 'TRIG', 'ALL') for x in ch)
        """:type: typing.List[Triggering]"""

        self.arms = tuple(Triggering(t, p, x, 'ARM', 'ALL') for x in ch)
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

        self.sense_elements = Command(':FORM:ELEM:SENS?', ':FORM:ELEM:SENS', Stream(Mapping(_elements)))

    def beep(self, freq=200, duration=1):
        self._write(":SYST:BEEP:STAT ON")
        self._write(":SYST:BEEP %s,%s" % (freq, duration))

    def fetch_array(self, channels=(1,)):
        """Returns the array data which contains all of the data specified by the :FORMat:ELEMents:SENSe command.

        .. NOTE:: The data is not cleared until the initiate(), measure(), or read() command is executed.

        :param channels: list of channels to get data from
        :return: list of all the data
        """
        return self._query(('FETC:ARR? (@{ch})'.format(ch=self._parse_channels(channels)),
                            Stream(Float)))

    def fetch(self, channels=(1,)):
        """Returns the latest measurement data specified by the :FORMat:ELEMents:SENSe command.

        The data is not cleared until the initiate(), measure(), or read() command is executed"""
        return self._query(('FETC? (@{ch})'.format(ch=self._parse_channels(channels)),
                            Stream(Float)))

    def measure(self, channels=(1,)):
        """Executes a spot measurement (one-shot measurement) and returns the measurement result data.

        Measurement conditions must be set by SCPI commands or front panel
        operation before executing this command. Measurement items can be selected by
        the :FORMat:ELEMents:SENSe command."""
        return self._query(
            (
                'MEAS? (@{ch})'.format(ch=self._parse_channels(channels)),
                Stream(Float)
            )
        )

    def initiate(self, channels=(1,)):
        """Initiates selected channels."""
        self._write(':INIT (@{ch})'.format(ch=self._parse_channels(channels)))

    def abort(self, channels=(1,)):
        """aborts selected channels."""
        self._write(':ABOR (@{ch})'.format(ch=self._parse_channels(channels)))

    def __check__(self):
        if isinstance(self._transport, SimulatedTransport):
            self.is_dual = True
        else:
            maker, model, serial, revision = self.identification
            # Valid IDN: Agilent Technologies,model,serial,revision
            if not re.fullmatch(r'B29[0-9][0-9][A-Z]?', model):
                raise ValueError("Unknown model: '{0}'".format(model))
            lang = self._query((':SYST:LANG?', String))
            if lang != '"DEF"':
                raise ValueError("Change Language mode to DEF from System -> Language")

            if model.strip().upper() in ('B2902A', 'B2912A', 'B2962A'):
                self.is_dual = True
            else:
                self.is_dual = False

    @staticmethod
    def _parse_channels(channels=(), default=1):
        if isinstance(channels, (str, bytes)) or not isinstance(channels, Iterable):
            channels = (channels,)
        else:
            channels = channels
        return ','.join(str(c) for c in channels) or default

