"""Representative command mapping tests for the low-level source/sense API."""

from __future__ import annotations

import runpy

import pytest

from tests.fakes import RecordingMeter


def test_sweep_configuration_keeps_source_selection_separate_from_channel_mode() -> (
    None
):
    smu = RecordingMeter()
    smu.source_function = "VOLT"
    smu.source_voltage_mode = "SWEEP"
    smu.source_voltage_start = -1
    smu.source_voltage_stop = 2
    smu.sweep_points = 31
    assert smu.writes == [
        ":SOUR:FUNC VOLT",
        ":SOUR:VOLT:MODE SWEEP",
        ":SOUR:VOLT:STAR -1",
        ":SOUR:VOLT:STOP 2",
        ":SOUR:SWE:POIN 31",
    ]


def test_explicit_sense_ranges_work_with_concurrent_functions() -> None:
    smu = RecordingMeter()
    smu.responses[":SENS:FUNC?"] = '"VOLT","CURR"'
    smu.responses[":SENS:VOLT:RANG:AUTO?"] = "0"
    assert smu.sense_voltage_auto_range is False
    smu.sense_current_auto_range = True
    assert smu.writes == [":SENS:CURR:RANG:AUTO ON"]
    with pytest.raises(ValueError, match="exactly one"):
        _ = smu.sense_auto_range


def test_list_and_digital_commands_preserve_values() -> None:
    smu = RecordingMeter()
    smu.source_current_list_values = [0.1, 0.2, -0.3]
    smu.append_source_voltage_list([1.5])
    smu.digital_output_pattern = 5
    assert smu.writes == [
        ":SOUR:LIST:CURR 0.1,0.2,-0.3",
        ":SOUR:LIST:VOLT:APP 1.5",
        ":SOUR2:TTL:LEV:DEF 5",
    ]


def test_source_function_rejects_sense_only_functions_and_memory_has_no_level():
    smu = RecordingMeter()
    with pytest.raises(ValueError, match="source function"):
        smu.source_function = "RES"
    assert smu.writes == []
    smu.responses[":SOUR:FUNC?"] = "MEM"
    with pytest.raises(ValueError, match="memory source"):
        smu.source_level = 1
    assert smu.writes == []


def test_sense_auto_range_infers_single_selected_function():
    smu = RecordingMeter()
    smu.responses[":SENS:FUNC?"] = '"CURR:DC"'
    smu.responses[":SENS:CURR:RANG:AUTO?"] = "1"
    assert smu.sense_auto_range is True
    smu.sense_auto_range = False
    assert smu.writes == [":SENS:CURR:RANG:AUTO OFF"]


def test_nplc_is_global_and_validates_positive_finite_numbers():
    smu = RecordingMeter()
    smu.nplc = 1.0
    assert smu.writes == [":SENS:VOLT:NPLC 1"]
    with pytest.raises(ValueError, match="positive and finite"):
        smu.sense_current_nplc = float("nan")
    assert smu.writes == [":SENS:VOLT:NPLC 1"]


def test_numeric_parameter_queries_are_independent():
    smu = RecordingMeter(
        {
            ":SOUR:VOLT:LEV? MIN": "-210",
            ":SOUR:VOLT:LEV? MAX": "210",
            ":SOUR:VOLT:LEV? DEF": "0",
        }
    )
    assert smu.source_voltage_level_minimum == -210
    assert smu.queries == [":SOUR:VOLT:LEV? MIN"]
    assert smu.source_voltage_level_maximum == 210
    assert smu.source_voltage_level_default == 0
    assert smu.queries == [
        ":SOUR:VOLT:LEV? MIN",
        ":SOUR:VOLT:LEV? MAX",
        ":SOUR:VOLT:LEV? DEF",
    ]
    smu.source_voltage_level = "MIN"
    assert smu.writes == [":SOUR:VOLT:LEV MIN"]


def test_advanced_configuration_example_selects_multiple_sense_functions():
    meter = RecordingMeter()
    example = runpy.run_path("examples/advanced_configuration.py")
    example["configure_sense_functions"](meter, ("VOLT", "CURR"))
    assert meter.writes == [
        ":SENS:FUNC:CONC ON",
        ":SENS:FUNC:OFF:ALL",
        ':SENS:FUNC:ON "VOLT"',
        ':SENS:FUNC:ON "CURR"',
    ]


@pytest.mark.parametrize("response,tripped", [("0", True), ("1", False)])
def test_output_enable_trip_uses_the_manuals_inverted_bit(response, tripped):
    meter = RecordingMeter({":OUTP:ENAB:TRIP?": response})
    assert meter.output_enable_tripped is tripped


def test_output_state_is_readable():
    meter = RecordingMeter({":OUTP:STAT?": "1"})
    assert meter.output_enabled is True


def test_direct_current_and_resistance_properties_use_explicit_commands():
    meter = RecordingMeter({":SOUR:CURR:LEV?": "0.001"})
    assert meter.source_current_level == 0.001
    meter.source_current_mode = "LIST"
    meter.sense_resistance_range_upper_limit = 1000
    assert meter.writes == [":SOUR:CURR:MODE LIST", ":SENS:RES:RANG:AUTO:ULIM 1000"]


def test_sense_functions_readback_only_queries_enabled_functions():
    meter = RecordingMeter({":SENS:FUNC?": '"VOLT:DC","CURR:DC"'})
    assert meter.sense_functions == ("VOLT", "CURR")
    assert meter.queries == [":SENS:FUNC?"]
    assert meter.writes == []
