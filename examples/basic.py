"""Take one current reading while sourcing a fixed voltage."""

import pyvisa

from keithley2400 import keithley2400


def configure_single_read(meter: keithley2400) -> None:
    """An application recipe, assembled from independent instrument settings."""
    meter.data_format = "ASC"
    meter.auto_output_off = False
    meter.data_elements = ("VOLT", "CURR", "RES", "TIME", "STAT")
    meter.arm_source = "IMM"
    meter.arm_count = 1
    meter.trigger_source = "IMM"
    meter.trigger_count = 1
    meter.trigger_delay = 0


def main() -> None:
    with pyvisa.ResourceManager() as manager, keithley2400() as meter:
        meter.connect("GPIB0::24::INSTR", resource_manager=manager)
        try:
            print(meter.identity)
            meter.abort()
            configure_single_read(meter)
            meter.source_function = "VOLT"
            meter.source_voltage.mode = "FIX"
            meter.source_voltage.range = 20
            meter.source_level = 1.0
            meter.sense_functions = ("CURR",)
            meter.current_compliance = 0.01
            meter.output_enabled = True
            voltage, current, resistance, timestamp, status = meter.read()
            print(current)
        finally:
            meter.output_enabled = False


if __name__ == "__main__":
    main()
