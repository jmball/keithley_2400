"""Representative command mapping tests for the low-level source/sense API."""

from __future__ import annotations

import pytest

from tests.fakes import RecordingMeter


def test_sweep_configuration_keeps_source_selection_separate_from_channel_mode() -> (
    None
):
    smu = RecordingMeter()
    smu.source_function = "VOLT"
    smu.source_voltage.mode = "SWEEP"
    smu.source_voltage.start = -1
    smu.source_voltage.stop = 2
    smu.sweep_points = 31
    assert smu.writes == [
        ":SOUR:FUNC VOLT",
        ":SOUR:VOLT:MODE SWEEP",
        ":SOUR:VOLT:STAR -1",
        ":SOUR:VOLT:STOP 2",
        ":SOUR:SWE:POIN 31",
    ]


def test_sense_range_endpoint_handles_concurrent_channels_and_alias_requires_one() -> (
    None
):
    smu = RecordingMeter()
    smu.responses[":SENS:FUNC?"] = '"VOLT","CURR"'
    smu.responses[":SENS:VOLT:RANG:AUTO?"] = "0"
    assert smu.sense_voltage.auto_range is False
    smu.sense_current.auto_range = True
    assert smu.writes == [":SENS:CURR:RANG:AUTO ON"]
    with pytest.raises(ValueError, match="exactly one"):
        _ = smu.sense_auto_range


def test_list_and_digital_commands_preserve_values() -> None:
    smu = RecordingMeter()
    smu.source_current.list_values = [0.1, 0.2, -0.3]
    smu.source_voltage.append_list([1.5])
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
        smu.sense_current.nplc = float("nan")
    assert smu.writes == [":SENS:VOLT:NPLC 1"]


def test_numeric_limits_query_the_instruments_documented_modifiers():
    smu = RecordingMeter(
        {
            ":SOUR:VOLT:LEV? MIN": "-210",
            ":SOUR:VOLT:LEV? MAX": "210",
            ":SOUR:VOLT:LEV? DEF": "0",
        }
    )
    limits = smu.source_voltage.level_limits
    assert (limits.minimum, limits.maximum, limits.default) == (-210, 210, 0)
    smu.source_voltage.level = "MIN"
    assert smu.writes == [":SOUR:VOLT:LEV MIN"]


def test_multiple_sense_functions_enable_concurrent_measurements():
    meter = RecordingMeter()
    meter.sense_functions = ("VOLT", "CURR")
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
