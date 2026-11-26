"""Read-only shared contract checks for virtual and opt-in hardware drivers."""

from keithley2400 import keithley2400, virtual_keithley2400


def test_connection_identity_and_output_state(
    instrument: keithley2400 | virtual_keithley2400,
) -> None:
    assert instrument.connected
    model = instrument.identity.split(",")[1].strip()
    assert model.startswith("MODEL 24")
    assert isinstance(instrument.output_enabled, bool)
    assert isinstance(instrument.output_enable_interlock_enabled, bool)
    assert isinstance(instrument.output_enable_interlock_tripped, bool)
    instrument.check_errors()


def test_documented_configuration_values(
    instrument: keithley2400 | virtual_keithley2400,
) -> None:
    assert instrument.source_function in {"VOLT", "CURR", "MEM"}
    assert isinstance(instrument.data_format, str)
    functions = instrument.sense_functions
    assert isinstance(functions, tuple)
    assert all(isinstance(function, str) for function in functions)
    assert isinstance(instrument.data_elements, str)


def test_trace_and_trigger_counts(
    instrument: keithley2400 | virtual_keithley2400,
) -> None:
    trace_points = instrument.trace_points
    trigger_count = instrument.trigger_count
    assert isinstance(trace_points, int)
    assert trace_points >= 1
    assert isinstance(trigger_count, int)
    assert trigger_count >= 1


def test_source_voltage_limits_and_timeout_round_trip(
    instrument: keithley2400 | virtual_keithley2400,
) -> None:
    minimum = instrument.source_voltage_level_minimum
    maximum = instrument.source_voltage_level_maximum
    default = instrument.source_voltage_level_default
    assert all(isinstance(value, float) for value in (minimum, maximum, default))
    assert minimum <= default <= maximum

    previous_timeout = instrument.timeout_ms
    try:
        instrument.timeout_ms = previous_timeout + 1
        assert instrument.timeout_ms == previous_timeout + 1
    finally:
        instrument.timeout_ms = previous_timeout
