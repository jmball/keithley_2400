"""Choose timeout budgets for acquisition, completion, and data transfer.

The acquisition estimate assumes voltage sourcing, one current measurement,
auto-zero enabled, fixed ranges, and immediate triggers. It is approximate.

Run this example from the project root after installing the project dependencies.
Replace the resource name below with your instrument's VISA resource name; the
illustrated GPIB interface and address are not detected automatically:

    uv run python examples/timeouts.py GPIB0::24::INSTR

Add communication options to match your connection. For example, for serial,
replace ASRL1::INSTR and match the instrument's baud rate and response terminator:

    uv run python examples/timeouts.py ASRL1::INSTR --baud-rate 9600 --read-termination CRLF

A raw serial-to-Ethernet adapter requires both --read-termination and
--write-termination, matching the instrument and adapter configuration. Use
--help to see all communication options. These commands illustrate the syntax;
the resource name and settings must be changed for your hardware.
"""

import argparse
from math import ceil
from typing import Any

from keithley2400 import keithley2400

# Two seconds for ordinary command replies; longer operations override this below.
COMMUNICATION_TIMEOUT_MS = 2_000


def parse_args() -> tuple[str, dict[str, Any]]:
    """Read VISA resource and communication options from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resource", help="VISA resource name")
    parser.add_argument("--baud-rate", type=int, help="serial baud rate")
    terminators = {"CR": "\r", "LF": "\n", "CRLF": "\r\n", "LFCR": "\n\r"}
    parser.add_argument("--read-termination", choices=terminators)
    parser.add_argument("--write-termination", choices=terminators)
    options = vars(parser.parse_args())
    resource_name = options.pop("resource")
    options["timeout"] = COMMUNICATION_TIMEOUT_MS
    for name in ("read_termination", "write_termination"):
        if options[name] is not None:
            options[name] = terminators[options[name]]
    return resource_name, {
        name: value for name, value in options.items() if value is not None
    }


def main() -> None:
    resource_name, communication = parse_args()
    with keithley2400() as smu:
        smu.connect(resource_name, **communication)
        original_timeout_ms = smu.timeout_ms
        try:
            # 1. Self-test: the reply waits for the ROM checksum to finish.
            # Increase the timeout if the usual I/O timeout is too short.
            # The guide gives no duration bound; this is an example budget.
            self_test_budget_ms = 30_000
            smu.timeout_ms = self_test_budget_ms
            try:
                print("Self-test result:", smu.self_test())
            finally:
                smu.timeout_ms = original_timeout_ms

            # 2. READ?: allow time to acquire all readings and transfer them.
            # Reset supplies immediate triggers, auto-zero ON, and averaging OFF.
            smu.reset()
            smu.source_voltage_level = 1
            smu.source_voltage_range = 20
            smu.current_compliance = 0.01
            smu.disable_all_sense_functions()
            smu.enable_sense_functions(("CURR",))
            smu.sense_current_range = 0.01
            smu.source_delay_auto = False

            reading_count = 10
            nplc = 10.0
            source_delay_s = 0.01
            smu.trigger_count = reading_count
            smu.sense_current_nplc = nplc
            smu.source_delay = source_delay_s

            # Store these readings for the buffer-transfer example below.
            smu.trace_points = reading_count
            smu.trace_feed = "SENSE"
            smu.trace_control = "NEXT"
            smu.output_enabled = True

            # One conversion takes the integration time plus A/D overhead.
            # Auto-zero adds reference and reference-zero conversions.
            adc_overhead_s = 185e-6
            conversions_per_reading = 3
            source_configuration_s = 50e-6
            source_voltage_firmware_overhead_s = 1.8e-3
            trigger_latency_s = 225e-6
            conversion_s = nplc / smu.line_frequency + adc_overhead_s
            source_on_s = (
                source_configuration_s
                + source_delay_s
                + conversions_per_reading * conversion_s
                + source_voltage_firmware_overhead_s
            )
            acquisition_s = reading_count * (trigger_latency_s + source_on_s)
            # Application-selected allowance for unmodelled acquisition time.
            acquisition_factor = 2
            transfer_allowance_s = 5
            milliseconds_per_second = 1000
            read_timeout_ms = ceil(
                milliseconds_per_second
                * (acquisition_factor * acquisition_s + transfer_allowance_s)
            )
            smu.timeout_ms = read_timeout_ms
            try:
                print("READ? results:", smu.read())
            finally:
                smu.timeout_ms = original_timeout_ms

            # 3. Buffer transfer: stored readings still take time to transmit.
            # Large ASCII replies over slow serial can exceed the usual timeout.
            # Choose a budget for the buffer and link; this is not a guarantee.
            buffer_transfer_budget_ms = 30_000
            smu.timeout_ms = buffer_transfer_budget_ms
            try:
                print("Stored readings:", smu.trace_data)
            finally:
                smu.timeout_ms = original_timeout_ms

            # 4. Completion: *OPC? waits for pending acquisition to finish.
            # Defer the error query so INIT returns while acquisition runs.
            smu.timeout_ms = read_timeout_ms
            smu.check_errors_after_write = False
            try:
                smu.initiate()
                smu.wait_complete()
            finally:
                smu.timeout_ms = original_timeout_ms
                smu.check_errors_after_write = True
            # *OPC? signals completion, not success; report initiation errors.
            smu.check_errors()
        finally:
            smu.timeout_ms = original_timeout_ms
            smu.output_enabled = False


if __name__ == "__main__":
    main()
