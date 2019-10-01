from slave.transport import Visa
from slave.quantum_design import PPMS
from slave.keithley.k6487 import K6487

ppms = PPMS(Visa('GPIB0::15'))
picoammeter = K6487(Visa('GPIB0::22'))

# Experiment setup
H1_START = 5e4   # Oe
H1_SWEEP = -80   # Oe / sec
H1_END = -5e4    # Oe
H2_START = -5e4  # Oe
H2_SWEEP = 80    # Oe / sec
H2_END = 5e4     # Oe
T_RATE = 10      # K / min
T = 2.0          # K

# Initialization of K6487 for current measurements
picoammeter.reset()
picoammeter.system.zero_check.enable = True
picoammeter.sense.range = 2e-9
picoammeter.initiate()
picoammeter.system.zero_correct.enable = False
picoammeter.system.zero_correct.acquire()
picoammeter.system.zero_correct.enable = True
picoammeter.sense.auto_range = True
picoammeter.system.zero_check = False

picoammeter.read()