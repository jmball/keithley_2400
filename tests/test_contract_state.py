"""State-changing shared contract checks for virtual and opt-in hardware drivers.

On hardware these run only with --allow-state-changes. Each test starts from
*RST and leaves the output off and the instrument reset. Output is enabled only
at 0.5 V or less with the reset current compliance (105 uA).
"""

import pytest

from keithley2400 import keithley2400, virtual_keithley2400

Instrument = keithley2400 | virtual_keithley2400

OUTPUT_VOLTAGE = 0.5  # V, kept low because the connected load is unknown
COMPLIANCE = 105e-6  # A, the documented *RST current compliance


def test_reset_restores_documented_defaults(reset_instrument: Instrument) -> None:
    smu = reset_instrument
    assert smu.output_enabled is False
    assert smu.source_function == "VOLT"
    assert smu.source_voltage_level == 0.0
    assert smu.source_voltage_mode == "FIX"
    assert smu.current_compliance == pytest.approx(COMPLIANCE)
    assert smu.output_enable_interlock_enabled is False
    assert smu.output_off_mode == "NORM"
    assert smu.trigger_count == 1


def test_output_off_mode_readback_can_be_written_back(
    reset_instrument: Instrument,
) -> None:
    smu = reset_instrument
    for mode in ("HIMPEDANCE", "ZERO", "GUARD", "NORMAL"):
        smu.output_off_mode = mode
        readback = smu.output_off_mode
        assert readback == mode[:4]
        smu.output_off_mode = readback
        assert smu.output_off_mode == readback


def test_setting_round_trips(reset_instrument: Instrument) -> None:
    smu = reset_instrument
    smu.source_voltage_level = 0.25
    smu.current_compliance = 50e-6
    smu.nplc = 0.1
    smu.output_off_mode = "NORMAL"
    smu.trigger_count = 3
    smu.data_elements = ("VOLT", "CURR")
    assert smu.source_voltage_level == pytest.approx(0.25)
    assert smu.current_compliance == pytest.approx(50e-6)
    assert smu.nplc == pytest.approx(0.1)
    assert smu.output_off_mode == "NORM"
    assert smu.trigger_count == 3
    assert smu.data_elements == "VOLT,CURR"
    smu.check_errors()


def test_out_of_range_source_level_reports_device_error(
    reset_instrument: Instrument,
) -> None:
    smu = reset_instrument
    with pytest.raises(RuntimeError, match="-222"):
        smu.source_voltage_level = 1e6
    assert smu.source_voltage_level == 0.0


def test_output_enable_interlock_round_trip(reset_instrument: Instrument) -> None:
    smu = reset_instrument
    smu.output_enable_interlock_enabled = True
    assert smu.output_enable_interlock_enabled is True
    assert smu.output_enabled is False
    smu.output_enable_interlock_enabled = False
    assert smu.output_enable_interlock_enabled is False


def test_read_returns_selected_elements_with_output_on(
    reset_instrument: Instrument,
) -> None:
    smu = reset_instrument
    smu.data_elements = ("VOLT", "CURR")
    smu.source_voltage_level = OUTPUT_VOLTAGE
    smu.output_enabled = True
    assert smu.output_enabled is True
    voltage, current = smu.read()
    assert abs(current) <= COMPLIANCE * 1.05
    if not smu.current_compliance_tripped:
        assert voltage == pytest.approx(OUTPUT_VOLTAGE, abs=0.01)
    smu.output_enabled = False
    assert smu.output_enabled is False


def test_triggered_readings_repeat_elements(reset_instrument: Instrument) -> None:
    smu = reset_instrument
    smu.data_elements = ("VOLT", "CURR")
    smu.nplc = 0.1
    smu.trigger_count = 3
    smu.source_voltage_level = 0.0
    smu.output_enabled = True
    readings = smu.read()
    assert len(readings) == 6
    assert all(isinstance(value, float) for value in readings)


def test_voltage_sweep_sources_each_step(reset_instrument: Instrument) -> None:
    smu = reset_instrument
    smu.data_elements = ("VOLT", "CURR")
    smu.nplc = 0.1
    smu.source_voltage_start = 0.0
    smu.source_voltage_stop = OUTPUT_VOLTAGE
    smu.sweep_points = 3
    smu.source_voltage_mode = "SWEEP"
    smu.trigger_count = 3
    smu.output_enabled = True
    readings = smu.read()
    voltages = readings[0::2]
    currents = readings[1::2]
    assert len(voltages) == 3
    assert all(abs(current) <= COMPLIANCE * 1.05 for current in currents)
    if not smu.current_compliance_tripped:
        assert voltages == pytest.approx(
            (0.0, OUTPUT_VOLTAGE / 2, OUTPUT_VOLTAGE), abs=0.01
        )
