"""Take one current reading while sourcing a fixed voltage."""

import pyvisa
from keithley2400 import keithley2400


rm = pyvisa.ResourceManager()
meter = keithley2400()
meter.connect("GPIB0::24::INSTR", resource_manager=rm)
try:
    meter.abort()
    meter.configure_single_read()
    meter.source_function = "VOLT"
    meter.source_range = 20
    meter.source_level = 1.0
    meter.sense_functions = ("CURR",)
    meter.current_compliance = 0.01
    meter.output_enabled = True
    print(meter.read())
finally:
    meter.output_enabled = False
    meter.disconnect()
