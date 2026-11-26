"""Behavioral contracts for the in-memory Keithley 2400 implementation."""

from __future__ import annotations

import inspect
from typing import Any

import pytest
import pyvisa

from keithley2400 import keithley2400, virtual_keithley2400


def test_public_api_matches_hardware_driver() -> None:
    """Keep the virtual driver substitutable for the hardware driver."""
    hardware_names = {name for name in dir(keithley2400) if not name.startswith("_")}
    virtual_names = {
        name for name in dir(virtual_keithley2400) if not name.startswith("_")
    }
    assert virtual_names == hardware_names

    for name in hardware_names:
        hardware_member = getattr(keithley2400, name)
        virtual_member = getattr(virtual_keithley2400, name)
        if isinstance(hardware_member, property):
            assert isinstance(virtual_member, property)
            assert (virtual_member.fset is None) == (hardware_member.fset is None)
        elif callable(hardware_member):
            assert inspect.signature(virtual_member) == inspect.signature(
                hardware_member
            )


def test_virtual_connection_lifecycle_and_ignored_resource_manager() -> None:
    class Manager(pyvisa.ResourceManager):
        def __new__(cls):
            return object.__new__(cls)

        def __init__(self) -> None:
            self.open_calls: list[tuple[object, dict[str, object]]] = []
            self.closed = False

        def open_resource(self, *args: Any, **kwargs: Any) -> Any:
            self.open_calls.append((args, kwargs))

        def close(self) -> None:
            self.closed = True

    manager = Manager()
    meter = virtual_keithley2400()
    with meter as entered:
        assert entered is meter
        meter.connect("any resource", resource_manager=manager, timeout=17)
        assert meter.connected
        with pytest.raises(RuntimeError, match="already connected"):
            meter.connect("another resource", resource_manager=manager)
        meter.disconnect()
        meter.disconnect()
        assert not meter.connected
    assert manager.open_calls == []
    assert not manager.closed


def test_settings_survive_reconnect_and_reset_restores_documented_basics() -> None:
    meter = virtual_keithley2400()
    meter.connect("virtual")
    meter.source_voltage_level = 2.5
    meter.nplc = 3
    meter.disconnect()
    meter.connect("ignored")
    assert meter.source_function == "VOLT"
    assert meter.source_voltage_level == 2.5
    assert meter.sense_functions == ("CURR",)
    assert meter.nplc == 3
    assert meter.output_enabled is False

    meter.reset()
    assert meter.source_function == "VOLT"
    assert meter.sense_functions == ("CURR",)
    assert meter.nplc == 1
    assert meter.output_enabled is False


def test_source_aliases_and_sense_nplc_alias_share_values() -> None:
    meter = virtual_keithley2400()
    meter.connect("virtual")
    meter.source_function = "VOLT"
    meter.source_level = 4.25
    assert meter.source_voltage_level == 4.25
    assert meter.source_level == 4.25
    meter.sense_voltage_nplc = 2
    assert meter.nplc == 2
    meter.nplc = 5
    assert meter.sense_voltage_nplc == 5


def test_measurements_are_deterministic_and_follow_enabled_element_order() -> None:
    meter = virtual_keithley2400()
    meter.connect("virtual")
    meter.source_function = "VOLT"
    meter.source_voltage_level = 1.25
    meter.output_enabled = True
    meter.data_elements = ("VOLT", "CURR", "RES")
    meter.enable_sense_functions(("VOLT", "CURR"))
    meter.disable_sense_functions(("RES",))
    assert meter.read() == (1.25, 0.0, 9.91e37)
    assert meter.measure("VOLT") == (1.25, 9.91e37, 9.91e37)
    assert meter.measure("CURR") == (1.25, 0.0, 9.91e37)


def test_fetch_does_not_measure_and_trace_next_respects_capacity() -> None:
    meter = virtual_keithley2400()
    meter.connect("virtual")
    meter.source_voltage_level = 3
    meter.output_enabled = True
    meter.data_elements = ("VOLT", "CURR", "RES")
    meter.trace_points = 2
    meter.trace_feed = "SENSE"
    meter.trace_control = "NEXT"
    first = meter.read()
    recorded = meter.trace_data
    assert meter.fetch() == first
    assert meter.trace_data == recorded
    meter.read()
    meter.read()
    assert len(meter.trace_data) == 6


def test_save_recall_and_reset_restore_saved_settings() -> None:
    meter = virtual_keithley2400()
    meter.connect("virtual")
    meter.source_voltage_level = 6
    meter.save_setup(1)
    meter.source_voltage_level = -2
    meter.recall_setup(1)
    assert meter.source_voltage_level == 6
    meter.reset()
    assert meter.source_voltage_level == 0


def test_deferred_errors_are_consumed_and_completion_is_immediate() -> None:
    meter = virtual_keithley2400()
    meter.connect("virtual")
    meter.check_errors_after_write = False
    meter.trigger_count = -1
    with pytest.raises(RuntimeError):
        meter.check_errors()
    meter.check_errors()
    assert meter.wait_complete() is True


def test_query_function_validation_and_memory_source_level() -> None:
    meter = virtual_keithley2400()
    meter.connect("virtual")
    with pytest.raises(ValueError, match="sense function"):
        meter.measure("MEM")
    meter.source_function = "MEM"
    with pytest.raises(ValueError, match="memory source"):
        _ = meter.source_level


def test_min_max_default_metadata_and_buffer_clear() -> None:
    meter = virtual_keithley2400()
    meter.connect("virtual")
    meter.source_voltage_level = 1
    assert meter.source_voltage_level_minimum < meter.source_voltage_level_maximum
    assert isinstance(meter.source_voltage_level_default, float)
    meter.output_enabled = True
    meter.read()
    meter.clear_trace()
    assert meter.trace_data == ()
    meter.clear_errors()
    meter.check_errors()


def test_invalid_trigger_count_uses_runtime_error() -> None:
    meter = virtual_keithley2400()
    meter.connect("virtual")
    with pytest.raises(RuntimeError):
        meter.trigger_count = -1


def test_numeric_tokens_and_selected_element_order_with_multiple_readings() -> None:
    meter = virtual_keithley2400()
    meter.connect("virtual")
    meter.source_voltage_level = "MAX"
    assert meter.source_voltage_level == 210
    meter.source_voltage_level = "DEF"
    assert meter.source_voltage_level == 0
    meter.source_voltage_level = 2
    meter.data_elements = ("CURR", "VOLT")
    meter.trigger_count = 3
    meter.output_enabled = True
    assert meter.read() == (0, 2, 0, 2, 0, 2)
    meter.source_voltage_level = 4
    assert meter.fetch() == (0, 2, 0, 2, 0, 2)


def test_custom_math_scalar_and_vector_expressions_use_recorded_values() -> None:
    meter = virtual_keithley2400()
    meter.connect("virtual")
    meter.source_voltage_list_values = (1, 3)
    meter.source_voltage_mode = "LIST"
    meter.trigger_count = 2
    meter.math_name = "DOUBLE"
    meter.math_expression = "2*VOLT"
    meter.math_units = "V"
    meter.math_enabled = True
    meter.output_enabled = True
    meter.read()
    assert meter.math_data == (2, 6)
    meter.math_name = "DELTA"
    meter.math_expression = "VOLT[1]-VOLT[0]"
    assert meter.math_data == (2,)
    assert meter.math_latest == (2,)
    meter.delete_math_expression("DOUBLE")
    assert "DOUBLE" not in meter.math_catalog


def test_numeric_limit_failure_is_latched_until_cleared() -> None:
    meter = virtual_keithley2400()
    meter.connect("virtual")
    meter.source_voltage_level = 3
    meter.set_limit_test_upper(2, 2)
    meter.set_limit_test_enabled(2, True)
    meter.output_enabled = True
    meter.read()
    assert meter.get_limit_test_failed(2)
    meter.source_voltage_level = 1
    meter.read()
    assert meter.get_limit_test_failed(2)
    meter.clear_composite_limits()
    assert not meter.get_limit_test_failed(2)


def test_bus_trigger_and_deferred_checks_do_not_create_background_work() -> None:
    meter = virtual_keithley2400()
    meter.connect("virtual")
    meter.arm_source = "BUS"
    meter.output_enabled = True
    meter.check_errors_after_write = False
    meter.initiate()
    with pytest.raises(pyvisa.errors.VisaIOError):
        meter.wait_complete()
    meter.trigger_bus()
    assert meter.wait_complete()
    assert len(meter.fetch()) == 5
    meter.check_errors_after_write = True
    meter.check_errors()


def test_invalid_read_leaves_error_for_explicit_query() -> None:
    meter = virtual_keithley2400()
    meter.connect("virtual")
    with pytest.raises(pyvisa.errors.VisaIOError):
        meter.read()
    assert meter.error_count == 1
    assert meter.read_error() == '802,"Not permitted with OUTPUT off"'
    assert meter.error_count == 0


def test_error_mask_and_clear_on_read_status() -> None:
    meter = virtual_keithley2400()
    meter.connect("virtual")
    meter.error_queue_disabled = (-222,)
    meter.trigger_count = -1
    assert meter.error_count == 0
    meter.error_queue_enabled = (-222,)
    meter.check_errors_after_write = False
    meter.trigger_count = -1
    assert meter.read_event_status() & 16
    assert meter.read_event_status() == 0
    assert meter.read_error_codes() == "-222"
    assert meter.read_error_code() == 0


def test_source_memory_recall_leaves_unrelated_display_setting_unchanged() -> None:
    meter = virtual_keithley2400()
    meter.connect("virtual")
    meter.source_voltage_level = 2
    meter.display_top_text = "Before"
    meter.save_memory(1)
    meter.source_voltage_level = 4
    meter.display_top_text = "After"
    meter.recall_memory(1)
    assert meter.source_voltage_level == 2
    assert meter.display_top_text == "After"
