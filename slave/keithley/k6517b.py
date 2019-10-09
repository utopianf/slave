from slave.driver import Command, Driver
from slave.types import Boolean, Float, Integer, Mapping, Stream, String
import slave.iec60488 as iec

from logging import getLogger
logger = getLogger(__name__)

_functions = {
    'Voltage': 'VOLT',
    'Amps': 'CURR',
    'Ohms': 'RES',
    'Coulombs': 'CHAR'
}


class K6517B(iec.IEC60488, iec.Trigger, iec.StoredSetting):
    """Keithley Model 6517B Electrometer"""
    def __init__(self, transport):
        super(K6517B, self).__init__(transport)
        self.calculate = Calculate(self._transport, self._protocol)
        self.display = Display(self._transport, self._protocol)
        self.format = Format(self._transport, self._protocol)
        self.output = Output(self._transport, self._protocol)
        self.route = Route(self._transport, self._protocol)
        self.sense = Sense(self._transport, self._protocol)
        self.source = Source(self._transport, self._protocol)
        self.status = Status(self._transport, self._protocol)
        self.system = System(self._transport, self._protocol)
        self.trace = Trace(self._transport, self._protocol)
        self.trigger = Trigger(self._transport, self._protocol)
        self.tsequence = Tsequence(self._transport, self._protocol)
        self.unit = Unit(self._transport, self._protocol)

    def fetch(self):
        return self.sense.fetch()

    def configure(self, function):
        return self.sense.configure(function)

    def read(self):
        return self.sense.read()

    def measure(self, function=None):
        return self.sense.measure(function)


class Calculate(Driver):
    def __init__(self, transport, protocol):
        super(Calculate, self).__init__(transport, protocol)
        self._transport = transport
        self._protocol = protocol
        self.calculate2 = Calculate2(self._transport, self._protocol)
        self.calculate3 = Calculate3(self._transport, self._protocol)

        self.format = Command(
            ':CALC:FORM?',
            ':CALC:FORM',
            Mapping({'none': 'NONE',
                     'polynomial': 'POL',
                     'percent': 'PER',
                     'ratio': 'RAT',
                     'deviation': 'DEV',
                     'pdeviation': 'PDEV',
                     'log10': 'LOG'})
        )
        self.state = Command(
            ':CALC:STAT?',
            ':CALC:STAT',
            Boolean
        )

    def get_data(self):
        return self._query((':CALC:DATA?', Stream(Float)))

    def get_fresh_data(self):
        return self._query((':CALC:DATA:FRES?', Stream(Float)))

    def recalculate(self):
        return self._write(':CALC:IMM')


class Calculate2(Driver):
    def __init__(self, transport, protocol):
        super(Calculate2, self).__init__(transport, protocol)

        self.format = Command(
            ':CALC:FORM?',
            ':CALC:FORM',
            Mapping({'none': 'NONE',
                     'mean': 'MEAN',
                     'sdeviation': 'SDEV',
                     'maximum': 'MAX',
                     'minimum': 'MIN',
                     'peak-to-peak': 'PKPK'})
        )
        self.state = Command(
            ':CALC:STAT?',
            ':CALC:STAT',
            Boolean
        )

    def get_data(self):
        return self._query((':CALC2:DATA?', Stream(Float)))

    def recalculate(self):
        return self._write(':CALC2:IMM')


class Calculate3(Driver):
    pass


class Display(Driver):
    pass


class Format(Driver):
    def __init__(self, transport, protocol):
        super(Format, self).__init__(transport, protocol)

        self.data = Command(
            ':FORM?',
            ':FORM',
            Mapping({'ascii': 'ASC',
                     'real32': 'REAL32',
                     'real64': 'REAL64',
                     'sreal': 'SRE',
                     'dreal': 'DRE'})
        )
        self.elements = Command(
            ':FORM:ELEM?',
            ':FORM:ELEM',
            Stream(Mapping({
                'reading': 'READ',
                'channel': 'CHAN',
                'rnumber': 'RNUM',
                'units': 'UNIT',
                'timestamp': 'TST',
                'status': 'STAT',
                'etemperature': 'ETEM',
                'humidity': 'HUM',
                'vsource': 'VSO'
            }))
        )
        self.byte_order = Command(
            ':FORM:BORD?',
            ':FORM:BORD',
            Mapping({'normal': 'NORM', 'swapped': 'SWAP'})
        )


class Output(Driver):
    pass


class Route(Driver):
    pass


class Sense(Driver):
    def __init__(self, transport, protocol):
        super(Sense, self).__init__(transport, protocol)
        self._transport = transport
        self._protocol = protocol

        self.voltage = Voltage(self._transport, self._protocol)
        self.current = Current(self._transport, self._protocol)
        self.resistance = Resistance(self._transport, self._protocol)
        self.coulombs = Coulombs(self._transport, self._protocol)

    def fetch(self):
        return self._query((':FETC?', Stream(Float)))

    def configure(self, function):
        return self._write(':CONF:%s' % _functions[function])

    def read(self):
        return self._query((':READ?', Stream(Float)))

    def measure(self, function=None):
        if function:
            return self._query((':MEAS:%s? ' % _functions[function], Stream(Float)))
        else:
            return self._query((':MEAS?', Stream(Float)))


class SubSense(Driver):
    def __init__(self, transport, protocol, function, ulim):
        super(SubSense, self).__init__(transport, protocol)
        self._transport = transport
        self._protocol = protocol
        self._function = _functions[function]

        self.aperture = Command(
            ':%s:APER?' % self._function,
            ':%s:APER' % self._function,
            Float(166.67e-6, 200e-3)
        )
        self.auto_aperature = Command(
            ':%s:APER:AUTO?' % self._function,
            ':%s:APER:AUTO' % self._function,
            Boolean
        )

        self.integration_rate = Command(
            ':%s:NPLC?' % self._function,
            ':%s:NPLC' % self._function,
            Float(0.01, 10)
        )
        self.auto_integration_rate = Command(
            ':%s:NPLC:AUTO?' % self._function,
            ':%s:NPLC:AUTO' % self._function,
            Boolean
        )

        self.range = Command(
            ':%s:RANG?' % self._function,
            ':%s:RANG' % self._function,
            Float(0, ulim)
        )
        self.auto_range = Command(
            ':%s:RANG:AUTO?' % self._function,
            ':%s:RANG:AUTO' % self._function,
            Boolean
        )
        self.auto_range_ulimit = Command(
            ':%s:RANG:AUTO:ULIM?' % self._function,
            ':%s:RANG:AUTO:ULIM' % self._function,
            Float(0, ulim)
        )
        self.auto_range_llimit = Command(
            ':%s:RANG:AUTO:LLIM?' % self._function,
            ':%s:RANG:AUTO:LLIM' % self._function,
            Float((-1) * ulim, 0)
        )

        self.reference = Command(
            ':%s:REF?' % self._function,
            ':%s:REF' % self._function,
            Float((-1) * ulim, ulim)
        )
        self.reference_state = Command(
            ':%s:REF:STAT?' % self._function,
            ':%s:REF:STAT' % self._function,
            Boolean
        )

        self.digits = Command(
            ':%s:DIG?' % self._function,
            ':%s:DIG' % self._function,
            Integer(4, 7)
        )
        self.auto_digits = Command(
            ':%s:DIG:AUTO?' % self._function,
            ':%s:DIG:AUTO' % self._function,
            Boolean
        )

        self.average = Average(self._transport, self._protocol, self._function)
        self.median = Median(self._transport, self._protocol, self._function)

    def auto_aperture_once(self):
        return self._write(':%s:APER:AUTO ONCE') % self._function

    def auto_integration_rate_once(self):
        return self._write(':%s:NPLC:AUTO ONCE') % self._function

    def auto_range_once(self):
        return self._write(':%s:RANG:AUTO ONCE') % self._function

    def require_reference(self):
        return self._write(':%s:REF:ACQ') % self._function

    def auto_digits_once(self):
        return self._write(':%s:DIG:AUTO ONCE') % self._function


class Average(Driver):
    def __init__(self, transport, protocol, function):
        super(Average, self).__init__(transport, protocol)
        self.state = Command(
            ':%s:AVER?' % function,
            ':%s:AVER' % function,
            Boolean
        )
        self.type = Command(
            ':%s:AVER:TYPE?' % function,
            ':%s:AVER:TYPE' % function,
            Mapping({'none': 'NONE', 'scalar': 'SCAL', 'advanced': 'ADV'})
        )
        self.noise_tolerance = Command(
            ':%s:AVER:ADV:NTOL?' % function,
            ':%s:AVER:ADV:NTOL' % function,
            Integer(0, 100)
        )
        self.control_type = Command(
            ':%s:AVER:TCON?' % function,
            ':%s:AVER:TCON' % function,
            Mapping({'moving': 'MOV', 'repeat': 'REP'})
        )
        self.count = Command(
            ':%s:AVER:COUN?' % function,
            ':%s:AVER:COUN' % function,
            Integer(1, 100)
        )


class Median(Driver):
    def __init__(self, transport, protocol, function):
        super(Median, self).__init__(transport, protocol)
        self.state = Command(
            ':%s:MED?' % function,
            ':%s:MED' % function,
            Boolean
        )
        self.rank = Command(
            ':%s:MED:RANK?' % function,
            ':%s:MED:RANK' % function,
            Integer
        )


class Voltage(SubSense):
    def __init__(self, transport, protocol, function):
        super(Voltage, self).__init__(transport, protocol, 'voltage', 210)


class Current(SubSense):
    def __init__(self, transport, protocol):
        super(Current, self).__init__(transport, protocol, 'current', 20e-3)
        self.dumping = Command(
            ':%s:DAMP?' % self._function,
            ':%s:DAMP' % self._function,
            Boolean
        )


class Resistance(SubSense):
    def __init__(self, transport, protocol):
        super(Resistance, self).__init__(transport, protocol, 'resistance', 2e6)


class Coulombs(SubSense):
    def __init__(self, transport, protocol):
        super(Coulombs, self).__init__(transport, protocol, 'coulombs', 2.1e-6)


class Source(Driver):
    pass


class Status(Driver):
    pass


class System(Driver):
    def __init__(self, transport, protocol):
        super(System, self).__init__(transport, protocol)

        self.power_on_setup = Command(
            ':SYST:POS?',
            ':SYST:POS',
            Mapping({'rst': 'RST',
                     'preset': 'PRES',
                     'sav0': 'SAVE0',
                     'sav1': 'SAVE1',
                     'sav2': 'SAVE2',
                     'sav3': 'SAVE3',
                     'sav4': 'SAVE4',
                     'sav5': 'SAVE5',
                     'sav6': 'SAVE6',
                     'sav7': 'SAVE7',
                     'sav8': 'SAVE8',
                     'sav9': 'SAVE9'})
        )
        self.version = Command(
            query=':SYST:VERS?',
            type_=String
        )
        self.line_synchronization = Command(
            ':SYST:LSYN?',
            ':SYST:LSYN',
            Boolean
        )
        self.key = Command(
            ':SYST:KEY?',
            ':SYST:KEY',
            Integer(1, 31)
        )
        self.date = Command(
            ':SYST:DATE?',
            ':SYST:DATE',
            String
        )
        self.time = Command(
            ':SYST:TIME?',
            ':SYST:TIME',
            String
        )
        self.timestamp_type = Command(
            ':SYST:TST:TYPE?',
            ':SYST:TST:TYPE',
            Mapping({'relative': 'REL', 'rtclock': 'RTC'})
        )
        self.zero_check = Command(
            ':SYST:ZCH?',
            ':SYST:ZCH',
            Boolean
        )
        self.zero_correct = Command(
            ':SYST:ZCOR?',
            ':SYST:ZCOR',
            Boolean
        )
        self.external_temperature = Command(
            ':SYST:TSC?',
            ':SYST:TSC',
            Boolean
        )
        self.hardware_limit = Command(
            ':SYST:HLC?',
            ':SYST:HLC',
            Boolean
        )
        self.humidity_reading = Command(
            ':SYST:HSC?',
            ':SYST:HSC',
            Boolean
        )
        self.interlock = Command(
            query=':SYST:INT?',
            type_=Integer
        )

    def preset(self):
        return self._write(':SYST:PRES')

    def get_error(self):
        return self._query((':SYST:ERR?', Stream(String)))

    def clear(self):
        return self._write(':SYST:CLE')

    def reset_relative_timestamp(self):
        return self._write(':SYST:TST:REL:RES')

    def reset_reading_number(self):
        return self._write(':SYST:RNUM:RES')

    def acquire_zero_correction(self):
        return self._write(':SYST:ZCOR:ACQ')

    def set_autoranging_speed(self, speed):
        if speed == 'fast':
            return self._write(':SYST:ARSP FAST')
        elif speed == 'normal':
            return self._write(':SYST:ARSP NORM')
        else:
            print('WRONG PARAMETER')
            return

    def local(self):
        return self._write(':SYST:LOC')

    def remote(self):
        return self._write(':SYST:REM')

    def enable_local_lockout(self):
        return self._write(':SYST:LLOC ON')

    def disable_local_lockout(self):
        return self._write(':SYST:LLOC OFF')

    def set_trigger_mode(self, mode):
        if mode in ['CONT', 'ONES']:
            return self._write(':SYST:MACR:TRIG:MODE %s') % mode
        else:
            print('WRONG PARAMETER')
            return

    def set_trigger_source(self, source):
        if source in ['IMM', 'MAN', 'BUS', 'EXT', 'TIM']:
            return self._write(':SYST:MACR:TRIG:SOUR %s') % source
        else:
            print('WRONG PARAMETER')
            return

    def set_trigger_timer(self, timer):
        if 0.001 <= timer <= 99999.999:
            return self._write(':SYST:MACR:TRIG:TIM %f') % timer
        else:
            print('WRONG PARAMETER')
            return


class Trace(Driver):
    def __init__(self, transport, protocol):
        super(Trace, self).__init__(transport, protocol)

        self.points = Command(
            ':TRAC:POIN?',
            ':TRAC:POIN',
            Integer
        )
        self.auto_points = Command(
            ':TRAC:POIN:AUTO?',
            ':TRAC:POIN:AUTO',
            Boolean
        )
        self.feed_amount = Command(
            ':TRAC:FEED:PRET:AMO?',
            ':TRAC:FEED:PRET:AMO',
            Integer(0, 100)
        )
        self.feed_readings = Command(
            ':TRAC:FEED:PRET:READ?',
            ':TRAC:FEED:PRET:READ',
            Integer
        )
        self.feed_source = Command(
            ':TRAC:FEED:PRET:SOURCE?',
            ':TRAC:FEED:PRET:SOURCE',
            Mapping({'external': 'EXT', 'tlink': 'TLIN', 'bus': 'BUS', 'manual': 'MAN'})
        )
        self.timestamp_format = Command(
            ':TRAC:TST:FORM?',
            ':TRAC:TST:FORM',
            Mapping({'absolute': 'ABS', 'delta': 'DELT'})
        )
        self.elements = Command(
            ':TRAC:ELEM?',
            ':TRAC:ELEM',
            Stream(Mapping({'timestamp': 'TST',
                            'humidity': 'HUM',
                            'channel': 'CHAN',
                            'etemperature': 'ETEM',
                            'vsource': 'VSO',
                            'none': 'NONE'}))
        )

    def clear(self):
        return self._write(':TRAC:CLE')

    def get_bytes(self):
        return self._query(':TRAC:FREE?')

    def get_data(self):
        return self._query((':TRAC:DATA?', Stream(Float)))

    def get_latest_data(self):
        return self._query((':TRAC:LAST?', Stream(Float)))


class Trigger(Driver):
    def __init__(self, transport, protocol):
        super(Trigger, self).__init__(transport, protocol)
        self._transport = transport
        self._protocol = protocol

        self.continuous_initiation = Command(
            ':INIT:CONT?',
            ':INIT:CONT',
            Boolean
        )
        self.pending_operation = Command(
            ':INIT:POFL?',
            ':INIT:POFL',
            Mapping({'include': 'INCL', 'exclude': 'EXCL'})
        )

        self.count = Command(
            ':TRIG:COUN?',
            ':TRIG:COUN',
            Integer(1, 99999)
        )
        self.delay = Command(
            ':TRIG:DEL?',
            ':TRIG:DEL',
            Float(0, 999999.999)
        )
        self.source = Command(
            ':TRIG:SOUR?',
            ':TRIG:SOUR',
            Mapping({'hold': 'HOLD',
                     'immediate': 'IMM',
                     'timer': 'TIM',
                     'manual': 'MAN',
                     'bus': 'BUS',
                     'tlink': 'TLIN',
                     'external': 'EXT'})
        )
        self.timer = Command(
            ':TRIG:TIM?',
            ':TRIG:TIM',
            Float(0, 999999.999)
        )
        self.protocol = Command(
            ':TRIG:TCON:PROT?',
            ':TRIG:TCON:PROT',
            Mapping({'asynchronous': 'ASYN', 'ssynchronous': 'SSYN'})
        )
        self.direction = Command(
            ':TRIG:TCON:DIR?',
            ':TRIG:TCON:DIR',
            Mapping({'enable': 'SOUR', 'disable': 'ACC'})
        )
        self.asynchronous_input_line = Command(
            ':TRIG:TCON:ASYN:ILIN?',
            ':TRIG:TCON:ASYN:ILIN',
            Integer(1, 6)
        )
        self.asynchronous_output_line = Command(
            ':TRIG:TCON:ASYN:OLIN?',
            ':TRIG:TCON:ASYN:OLIN',
            Integer(1, 6)
        )
        self.ssynchronous_line = Command(
            ':TRIG:TCON:SSYN:LINE?',
            ':TRIG:TCON:SSYN:LINE',
            Integer(1, 6)
        )

    def initiate(self):
        return self._write(':INIT')

    def abort(self):
        return self._write(':ABOR')

    def signal(self):
        return self._write(':TRIG:SIGN')


class Tsequence(Driver):
    pass


class Unit(Driver):
    pass
