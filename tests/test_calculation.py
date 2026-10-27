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
    assert meter.math_catalog == '"POWER","PER_DEV"'
    assert meter.math_name == '"PER_DEV"'
    assert meter.math_expression == "(VOLT + CURR)"
    assert meter.math_enabled is True
    assert meter.math_latest == (1.25, 0.5)
    meter.math_name = "PER_DEV"
    meter.math_expression = "((RES - 10e3) / 10e3) * 100"
    meter.delete_math_expression("PER_DEV")
    meter.delete_all_math_expressions()
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
    assert meter.get_limit_test_failed(4) is True
    assert meter.get_limit_test_upper(5) == 2.5
    assert meter.composite_limit_pass_pattern == 15
    meter.set_limit_test_upper(12, 3.25)
    meter.limit_test_1_compliance_fail_condition = "OUT"
    meter.composite_limit_mode = "SORT"
    meter.composite_limit_pass_memory_location = "NEXT"
    meter.composite_limit_auto_clear = False
    meter.clear_composite_limits()
    assert meter.writes == [
        ":CALC2:LIM12:UPP 3.25",
        ":CALC2:LIM:COMP:FAIL OUT",
        ":CALC2:CLIM:MODE SORT",
        ":CALC2:CLIM:PASS:SMLOCATION NEXT",
        ":CALC2:CLIM:CLE:AUTO OFF",
        ":CALC2:CLIM:CLE",
    ]
    with pytest.raises(ValueError):
        meter.get_limit_test_enabled(13)
    with pytest.raises(ValueError):
        _ = meter.get_limit_test_upper(4)


def test_display_format_and_status_register_command_contracts():
    meter = RecordingMeter()
    meter.responses.update(
        {
            ":DISP:WIND1:ATTR?": "0",
            ":STAT:OPER:COND?": "#B1010",
            ":STAT:QUES:EVEN?": "16",
        }
    )
    assert meter.display_top_attributes == "0"
    assert meter.operation_status_condition == 10
    assert meter.read_questionable_status_event() == 16
    meter.display_bottom_text = "Ready"
    meter.display_digits = 7
    meter.status_register_format = "HEX"
    meter.digital_format = "BIN"
    meter.data_elements = ("VOLT", "CURR", "STAT")
    meter.calculation_elements = "CALC,TIME"
    meter.measurement_status_enable = 7
    meter.error_queue_enabled = (-110, -222)
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


def test_indexed_limit_parameter_default_is_a_single_query():
    meter = RecordingMeter({":CALC2:LIM5:UPP? DEF": "1"})
    assert meter.get_limit_test_upper_default(5) == 1
    assert meter.queries == [":CALC2:LIM5:UPP? DEF"]
    assert meter.writes == []
