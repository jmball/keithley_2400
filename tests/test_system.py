from __future__ import annotations

import pytest

from tests.fakes import RecordingMeter


def test_arm_trigger_and_trace_settings_use_manual_commands():
    meter = RecordingMeter({":ARM:COUN?": "3", ":TRIG:SOUR?": "TLINK"})
    meter.arm_count = 3
    meter.arm_source = "timer"
    meter.trigger_source = "tlink"
    meter.trigger_delay = 0.25
    meter.trace_points = 20
    meter.trace_feed = "sense"
    meter.trace_control = "next"
    meter.trace_timestamp_format = "delta"
    assert meter.arm_count == 3
    assert meter.trigger_source == "TLINK"
    assert meter.writes == [
        ":ARM:COUN 3",
        ":ARM:SOUR TIMER",
        ":TRIG:SOUR TLINK",
        ":TRIG:DEL 0.25",
        ":TRAC:POIN 20",
        ":TRAC:FEED SENSE",
        ":TRAC:FEED:CONT NEXT",
        ":TRAC:TST:FORM DELTA",
    ]


def test_common_synchronization_and_queue_reads_are_explicit():
    meter = RecordingMeter(
        {"*OPC?": "1", "*ESR?": "32", ":SYST:ERR?": '-222,"Data out of range"'}
    )
    meter.set_operation_complete()
    assert meter.wait_complete() is True
    assert meter.read_event_status() == 32
    assert meter.read_error() == '-222,"Data out of range"'
    assert meter.writes == ["*OPC"]
    assert meter.queries == ["*OPC?", "*ESR?", ":SYST:ERR?"]


def test_read_fetch_measure_and_trace_keep_variable_data():
    meter = RecordingMeter(
        {
            ":READ?": "1,2,3",
            ":FETC?": "1,2,3",
            ":MEAS:VOLT?": "1,2,3",
            ":MEAS?": "1,2,3",
            ":TRAC:DATA?": "1,2,3",
        }
    )
    assert meter.read() == (1.0, 2.0, 3.0)
    assert meter.fetch() == (1.0, 2.0, 3.0)
    assert meter.measure("voltage") == (1.0, 2.0, 3.0)
    assert meter.measure() == (1.0, 2.0, 3.0)
    assert meter.trace_data == (1.0, 2.0, 3.0)
    assert meter.queries[1::2] == [
        ":READ?",
        ":FETC?",
        ":MEAS:VOLT?",
        ":MEAS?",
        ":TRAC:DATA?",
    ]


def test_invalid_trigger_values_fail_before_writing():
    meter = RecordingMeter()
    with pytest.raises(ValueError):
        meter.trigger_input_line = 5
    with pytest.raises(ValueError):
        meter.arm_count = 0
    with pytest.raises(ValueError):
        meter.trigger_source = "BUS"
    assert meter.writes == []


def test_infinite_arm_count_uses_documented_numeric_sentinel():
    meter = RecordingMeter({":ARM:COUN?": "+9.900000E+37"})
    assert meter.arm_count == "INFINITE"


def test_trigger_numeric_settings_accept_documented_special_parameters():
    meter = RecordingMeter()
    meter.trigger_delay = "MAX"
    meter.arm_count = "INF"
    assert meter.writes == [":TRIG:DEL MAX", ":ARM:COUN INF"]
