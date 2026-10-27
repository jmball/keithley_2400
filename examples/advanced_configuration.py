"""Compose low-level settings to replace the enabled sense functions."""

from contextlib import closing

import pyvisa

from keithley2400 import keithley2400


def configure_sense_functions(meter: keithley2400, functions: tuple[str, ...]) -> None:
    """Application recipe: select one or more measurement functions."""
    meter.sense_concurrent = len(functions) > 1
    meter.disable_all_sense_functions()
    meter.enable_sense_functions(functions)


def main() -> None:
    with closing(pyvisa.ResourceManager()) as manager, keithley2400() as meter:
        meter.connect("GPIB0::24::INSTR", resource_manager=manager)
        meter.abort()
        configure_sense_functions(meter, ("VOLT", "CURR"))
        print(meter.sense_functions)


if __name__ == "__main__":
    main()
