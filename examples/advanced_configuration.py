"""Configure source, concurrent measurements, and trigger settings explicitly.

Run this example from the project root after installing the project dependencies.
Replace the resource name below with your instrument's VISA resource name; the
illustrated GPIB interface and address are not detected automatically:

    uv run python examples/advanced_configuration.py GPIB0::24::INSTR

Add communication options to match your connection. For example, for serial,
replace ASRL1::INSTR and match the instrument's baud rate and response terminator:

    uv run python examples/advanced_configuration.py ASRL1::INSTR --baud-rate 9600 --read-termination CRLF

A raw serial-to-Ethernet adapter requires both --read-termination and
--write-termination, matching the instrument and adapter configuration. Use
--help to see all communication options. These commands illustrate the syntax;
the resource name and settings must be changed for your hardware.
"""

import argparse
from typing import Any

from keithley2400 import keithley2400


def parse_args() -> tuple[str, dict[str, Any]]:
    """Read VISA resource and communication options from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resource", help="VISA resource name")
    parser.add_argument("--baud-rate", type=int, help="serial baud rate")
    parser.add_argument(
        "--timeout-ms", dest="timeout", type=float, help="VISA I/O timeout"
    )
    terminators = {"CR": "\r", "LF": "\n", "CRLF": "\r\n", "LFCR": "\n\r"}
    parser.add_argument("--read-termination", choices=terminators)
    parser.add_argument("--write-termination", choices=terminators)
    options = vars(parser.parse_args())
    resource_name = options.pop("resource")
    for name in ("read_termination", "write_termination"):
        if options[name] is not None:
            options[name] = terminators[options[name]]
    return resource_name, {
        name: value for name, value in options.items() if value is not None
    }


def configure_sense_functions(smu: keithley2400, functions: tuple[str, ...]) -> None:
    """Application recipe: select one or more measurement functions."""
    smu.sense_concurrent = len(functions) > 1
    smu.disable_all_sense_functions()
    smu.enable_sense_functions(functions)


def main() -> None:
    resource_name, communication = parse_args()
    with keithley2400() as smu:
        smu.connect(resource_name, **communication)
        smu.reset()
        try:
            smu.source_function = "VOLT"
            smu.source_voltage_mode = "FIX"
            smu.source_voltage_range = 20
            smu.source_voltage_level = 1.0
            smu.current_compliance = 0.01
            configure_sense_functions(smu, ("VOLT", "CURR"))
            smu.sense_current_nplc = 1
            smu.data_format = "ASC"
            smu.data_elements = ("VOLT", "CURR", "RES", "TIME", "STAT")
            smu.auto_output_off = False
            smu.arm_source = "IMM"
            smu.arm_count = 1
            smu.trigger_source = "IMM"
            smu.trigger_count = 1
            smu.trigger_delay = 0
            smu.output_enabled = True
            print(smu.read())
        finally:
            smu.output_enabled = False


if __name__ == "__main__":
    main()
