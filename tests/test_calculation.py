from __future__ import annotations

import pytest

from tests.fakes import RecordingMeter


def test_math_expression_catalog_state_and_data_contracts():
    meter = RecordingMeter()
    meter.responses.update(
        {
            ":CALC:MATH:CAT?": '"POWER","PER_DEV"',
            ":CALC:MATH:NAME?": '"PER_DEV"',
            ":CALC:MATH?": "(VOLT + CURR)",
            ":CALC:STAT?": "1",
            ":CALC:DATA:LAT?": "1.25,0.5",
        }
    )
    assert meter.math.catalog == '"POWER","PER_DEV"'
    assert meter.math.name == '"PER_DEV"'
    assert meter.math.expression == "(VOLT + CURR)"
    assert meter.math.enabled is True
    assert meter.math.latest == (1.25, 0.5)
    meter.math.name = "PER_DEV"
    meter.math.expression = "((RES - 10e3) / 10e3) * 100"
    meter.math.delete("PER_DEV")
    meter.math.delete_all()
    assert meter.writes == [
        ':CALC:MATH:NAME "PER_DEV"',
        ":CALC:MATH:EXPR ((RES - 10e3) / 10e3) * 100",
        ':CALC:MATH:DEL:SEL "PER_DEV"',
        ":CALC:MATH:DEL:ALL",
    ]


def test_indexed_limit_families_contact_check_and_composite_sorting():
    meter = RecordingMeter()
    meter.responses.update(
        {
            ":CALC2:LIM4:FAIL?": "1",
            ":CALC2:LIM5:UPP?": "+2.5",
            ":CALC2:CLIM:PASS:SOUR2?": "#H0F",
        }
    )
    assert meter.limit(4).failed is True
    assert meter.limit(5).upper == 2.5
    assert meter.composite_limits.pass_pattern == 15
    meter.limit(12).upper = 3.25
    meter.limit(1).compliance_fail_condition = "OUT"
    meter.composite_limits.mode = "SORT"
    meter.composite_limits.pass_memory_location = "NEXT"
    meter.composite_limits.auto_clear = False
    meter.composite_limits.clear()
    assert meter.writes == [
        ":CALC2:LIM12:UPP 3.25",
        ":CALC2:LIM:COMP:FAIL OUT",
        ":CALC2:CLIM:MODE SORT",
        ":CALC2:CLIM:PASS:SMLOCATION NEXT",
        ":CALC2:CLIM:CLE:AUTO OFF",
        ":CALC2:CLIM:CLE",
    ]
    with pytest.raises(ValueError):
        meter.limit(13)
    with pytest.raises(AttributeError):
        _ = meter.limit(4).upper


def test_display_format_and_status_register_command_contracts():
    meter = RecordingMeter()
    meter.responses.update(
        {
            ":DISP:WIND1:ATTR?": "0",
            ":STAT:OPER:COND?": "#B1010",
            ":STAT:QUES:EVEN?": "16",
        }
    )
    assert meter.display_top.attributes == "0"
    assert meter.operation_status.condition == 10
    assert meter.questionable_status.read_event() == 16
    meter.display_bottom.text = "Ready"
    meter.display_digits = 7
    meter.status_register_format = "HEX"
    meter.digital_format = "BIN"
    meter.data_elements = ("VOLT", "CURR", "STAT")
    meter.calculation_elements = "CALC,TIME"
    meter.measurement_status.enable = 7
    meter.error_queue_enabled = ("-110", "-222")
    meter.preset_status()
    meter.clear_status_errors()
    assert meter.writes == [
        ':DISP:WIND2:TEXT:DATA "Ready"',
        ":DISP:DIG 7",
        ":FORM:SREG HEX",
        ":FORM:SOUR2 BIN",
        ":FORM:ELEM VOLT,CURR,STAT",
        ":FORM:ELEM:CALC CALC,TIME",
        ":STAT:MEAS:ENAB 7",
        ":STAT:QUE:ENAB -110,-222",
        ":STAT:PRES",
        ":STAT:QUE:CLE",
    ]
