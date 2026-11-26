"""Deterministic, hardware-free counterpart to the Keithley 2400 driver.

Numeric limits use the model-2400 values in manual 2400S-900-01 Rev. K.
The public API is explicit; no VISA session, SCPI parser, or physical model is used.
"""

from __future__ import annotations

import ast
import math
import operator
from collections import deque
from collections.abc import Callable, Sequence
from copy import deepcopy
from statistics import mean, stdev
from types import TracebackType
from typing import Any

import pyvisa
from pyvisa import constants

_NUMERIC = {
    "trace_points": (1, 2500, 100),
    "arm_count": (1, 2500, 1),
    "trigger_count": (1, 2500, 1),
    "trigger_delay": (0, 999.9999, 0),
    "arm_timer": (0.001, 99999.99, 0.1),
    "current_compliance": (1e-08, 1.05, 105e-6),
    "voltage_compliance": (0.0002, 210, 20),
    "average_count": (1, 100, 10),
    "voltage_protection": (20, 160, 20),
    "source_delay": (0, 9999.999, 0),
    "sweep_points": (1, 2500, 100),
    "pulse_width": (0.00015, 0.005, 0.00015),
    "pulse_delay": (0, 9999.999, 0),
    "digital_clear_delay": (0, 60, 1e-05),
    "display_digits": (4, 7, 6),
    "contact_check_resistance": (0, 60, 2),
    "contact_check_timeout": (0, 999.9999, 0),
    "source_voltage_range": (-210, 210, 21),
    "source_current_range": (-1.05, 1.05, 0.000105),
    "sense_voltage_range": (-210, 210, 21),
    "sense_current_range": (-1.05, 1.05, 0.000105),
    "sense_resistance_range": (0, 210000000.0, 210000.0),
    "sense_voltage_nplc": (0.01, 10, 1),
    "sense_current_range_holdoff_delay": (0, 999.9999, 0),
    "sense_voltage_range_upper_limit": (-210, 210, 210),
    "sense_voltage_range_lower_limit": (-21, 21, 0),
    "sense_current_range_upper_limit": (-1.05, 1.05, 1.05),
    "sense_current_range_lower_limit": (-0.000105, 0.000105, 0),
    "sense_resistance_range_upper_limit": (-210000000.0, 210000000.0, 210000000.0),
    "sense_resistance_range_lower_limit": (-210000000.0, 210000000.0, 0),
    "source_voltage_scaling_factor": (-9.999999e20, 9.999999e20, 1),
    "source_current_scaling_factor": (-9.999999e20, 9.999999e20, 1),
    "source_voltage_list_start": (1, 2500, 1),
    "source_current_list_start": (1, 2500, 1),
    "memory_points": (1, 100, 1),
    "memory_start": (1, 100, 1),
    "source_delay_auto": (0, 1, 1),
    "relative_offset": (-9.999999e20, 9.999999e20, 0),
    "sweep_soak": (0, 9999.999, 0),
    "source_voltage_level": (-210, 210, 0),
    "source_voltage_triggered_level": (-210, 210, 0),
    "source_voltage_start": (-210, 210, 0),
    "source_voltage_stop": (-210, 210, 0),
    "source_voltage_center": (-210, 210, 0),
    "source_voltage_span": (-420, 420, 0),
    "source_voltage_step": (-420, 420, 0),
    "source_current_level": (-1.05, 1.05, 0),
    "source_current_triggered_level": (-1.05, 1.05, 0),
    "source_current_start": (-1.05, 1.05, 0),
    "source_current_stop": (-1.05, 1.05, 0),
    "source_current_center": (-1.05, 1.05, 0),
    "source_current_span": (-2.1, 2.1, 0),
    "source_current_step": (-2.1, 2.1, 0),
    "measurement_status_enable": (0, 65535, 0),
    "operation_status_enable": (0, 65535, 0),
    "questionable_status_enable": (0, 65535, 0),
    "event_status_enable": (0, 255, 0),
    "service_request_enable": (0, 255, 0),
    "arm_input_line": (1, 4, 1),
    "arm_output_line": (1, 4, 1),
    "trigger_input_line": (1, 4, 1),
    "trigger_output_line": (1, 4, 1),
    "digital_output_pattern": (0, 65535, 0),
    "composite_limit_pass_pattern": (0, 65535, 0),
    "composite_limit_fail_pattern": (0, 65535, 0),
}

_ENUMS = {
    "data_format": ("ASCii", "REAL,32", "SREal"),
    "byte_order": ("NORMal", "SWAPped"),
    "status_register_format": ("ASCii", "HEXadecimal", "OCTal", "BINary"),
    "digital_format": ("ASCii", "HEXadecimal", "OCTal", "BINary"),
    "guard_mode": ("OHMS", "CABLE"),
    "auto_zero": ("ON", "OFF", "ONCE"),
    "range_change_mode": ("SINGle", "MULTiple"),
    "trace_feed": ("SENSe", "SENSe1", "CALCulate", "CALCulate1", "CALCulate2"),
    "trace_control": ("NEXT", "NEVer"),
    "trace_timestamp_format": ("ABSolute", "DELTa"),
    "arm_source": (
        "IMMediate",
        "TLINk",
        "TIMer",
        "MANual",
        "BUS",
        "NSTest",
        "PSTest",
        "BSTest",
    ),
    "trigger_source": ("IMMediate", "TLINk"),
    "arm_bypass": ("SOURce", "ACCeptor"),
    "trigger_bypass": ("SOURce", "ACCeptor"),
    "contact_check_event_source": ("CCHeck", "IMMediate"),
    "source_function": ("VOLTage", "CURRent", "MEMory"),
    "resistance_mode": ("AUTO", "MANual"),
    "average_type": ("REPeat", "MOVing"),
    "output_off_mode": ("HIMPedance", "NORMal", "ZERO", "GUARd"),
    "terminals": ("FRONt", "REAR"),
    "auto_output_off_mode": ("ALWays", "TCOunt"),
    "sweep_spacing": ("LINear", "LOGarithmic"),
    "sweep_direction": ("UP", "DOWN"),
    "sweep_ranging": ("BEST", "AUTO", "FIXed"),
    "sweep_compliance_abort": ("NEVer", "EARly", "LATe"),
    "pulse_shape": ("DC", "PULSe"),
    "digital_line4_mode": ("EOT", "EOTEST", "BUSY"),
    "digital_busy_polarity": ("HI", "LO"),
    "source_voltage_mode": ("FIXed", "SWEep", "LIST"),
    "source_current_mode": ("FIXed", "SWEep", "LIST"),
    "limit_feed": ("VOLTage", "CURRent", "RESistance", "CALCulate"),
    "composite_limit_mode": ("GRADing", "SORTing"),
    "composite_limit_bin_control": ("IMMediate", "END"),
    "statistics_function": ("MEAN", "SDEViation", "MAXimum", "MINimum", "PKPK"),
    "limit_test_1_compliance_fail_condition": ("IN", "OUT"),
}

_DEFAULTS = {
    "arm_bypass": "SOUR",
    "arm_count": 1,
    "arm_input_line": 1,
    "arm_output_events": ("TENTER",),
    "arm_output_line": 1,
    "arm_source": "IMM",
    "arm_timer": 0.1,
    "auto_line_frequency": True,
    "auto_output_off": False,
    "auto_output_off_mode": "ALW",
    "auto_reset_timestamp": False,
    "auto_zero": "ON",
    "average_count": 10,
    "average_type": "REP",
    "averaging_enabled": False,
    "beeper_enabled": True,
    "byte_order": "NORM",
    "calculation_elements": "CALC",
    "composite_limit_auto_clear": False,
    "composite_limit_bin_control": "IMM",
    "composite_limit_fail_memory_location": "NEXT",
    "composite_limit_fail_pattern": 0,
    "composite_limit_mode": "GRAD",
    "composite_limit_pass_memory_location": "NEXT",
    "composite_limit_pass_pattern": 0,
    "contact_check_enabled": False,
    "contact_check_event_source": "CCH",
    "contact_check_resistance": 2.0,
    "contact_check_timeout": 0.0,
    "current_compliance": 105e-6,
    "current_range_synchronized": False,
    "data_elements": "VOLT,CURR,RES,TIME,STAT",
    "data_format": "ASC",
    "digital_bit_size": 3,
    "digital_busy_polarity": "HI",
    "digital_clear_auto": False,
    "digital_clear_delay": 1e-05,
    "digital_format": "ASC",
    "digital_line4_mode": "EOT",
    "digital_output_pattern": 0,
    "display_bottom_text": "",
    "display_bottom_text_enabled": False,
    "display_digits": 6,
    "display_enabled": False,
    "display_top_text": "",
    "display_top_text_enabled": False,
    "error_queue_disabled": "",
    "error_queue_enabled": "-999: -1",
    "event_status_enable": 0,
    "guard_mode": "OHMS",
    "limit_feed": "VOLT",
    "limit_test_1_compliance_fail_condition": "OUT",
    "line_frequency": 60,
    "math_enabled": False,
    "math_name": "POWER",
    "measurement_status_enable": 0,
    "memory_points": 1,
    "memory_start": 1,
    "nplc_caching": False,
    "offset_compensated_ohms": False,
    "operation_status_enable": 0,
    "output_enable_interlock_enabled": False,
    "output_enabled": False,
    "output_off_mode": "NORM",
    "power_on_setup": "RST",
    "pulse_delay": 0.0,
    "pulse_shape": "DC",
    "pulse_width": 0.00015,
    "questionable_status_enable": 0,
    "range_change_mode": "SING",
    "relative_enabled": False,
    "relative_offset": 0.0,
    "remote_lockout": False,
    "remote_sense": False,
    "resistance_mode": "AUTO",
    "sense_concurrent": True,
    "sense_current_auto_range": True,
    "sense_current_range": 0.000105,
    "sense_current_range_holdoff": False,
    "sense_current_range_holdoff_delay": 0.0,
    "sense_current_range_lower_limit": 0.0,
    "sense_resistance_auto_range": True,
    "sense_resistance_range": 210000.0,
    "sense_resistance_range_lower_limit": 0.0,
    "sense_resistance_range_upper_limit": 210000000.0,
    "sense_voltage_auto_range": True,
    "sense_voltage_nplc": 1.0,
    "sense_voltage_range": 21.0,
    "sense_voltage_range_lower_limit": 0.0,
    "service_request_enable": 0,
    "source_current_auto_range": True,
    "source_current_center": 0.0,
    "source_current_level": 0.0,
    "source_current_list_start": 1,
    "source_current_list_values": (0.0,),
    "source_current_mode": "FIX",
    "source_current_range": 0.000105,
    "source_current_scaling_enabled": False,
    "source_current_scaling_factor": 1.0,
    "source_current_span": 0.0,
    "source_current_start": 0.0,
    "source_current_step": 0.0,
    "source_current_stop": 0.0,
    "source_current_triggered_level": 0.0,
    "source_delay": 0.0,
    "source_delay_auto": True,
    "source_function": "VOLT",
    "source_voltage_auto_range": True,
    "source_voltage_center": 0.0,
    "source_voltage_level": 0.0,
    "source_voltage_list_start": 1,
    "source_voltage_list_values": (0.0,),
    "source_voltage_mode": "FIX",
    "source_voltage_range": 21.0,
    "source_voltage_scaling_enabled": False,
    "source_voltage_scaling_factor": 1.0,
    "source_voltage_span": 0.0,
    "source_voltage_start": 0.0,
    "source_voltage_step": 0.0,
    "source_voltage_stop": 0.0,
    "source_voltage_triggered_level": 0.0,
    "statistics_function": "MEAN",
    "status_register_format": "ASC",
    "sweep_compliance_abort": "NEV",
    "sweep_direction": "UP",
    "sweep_points": 100,
    "sweep_ranging": "BEST",
    "sweep_soak": 0.0,
    "sweep_spacing": "LIN",
    "terminals": "FRON",
    "trace_control": "NEV",
    "trace_feed": "SENS",
    "trace_points": 100,
    "trace_timestamp_format": "ABS",
    "trigger_bypass": "SOUR",
    "trigger_count": 1,
    "trigger_delay": 0.0,
    "trigger_input_events": ("NONE",),
    "trigger_input_line": 1,
    "trigger_output_events": ("NONE",),
    "trigger_output_line": 1,
    "trigger_source": "IMM",
    "voltage_compliance": 20.0,
    "voltage_protection": 20.0,
}

_RANGES = {
    "voltage": (0.21, 2.1, 21.0, 210.0),
    "current": (1.05e-6, 10.5e-6, 105e-6, 1.05e-3, 10.5e-3, 105e-3, 1.05),
    "resistance": (21.0, 210.0, 2100.0, 21000.0, 210000.0, 2.1e6, 21e6, 210e6),
}
_UNAVAILABLE = 9.91e37
_OVERFLOW = 9.9e37
_BUILTIN_MATH = {
    "POWER": ("VOLT*CURR", "W"),
    "OFFCOMPOHM": ("(VOLT[1]-VOLT[0])/(CURR[1]-CURR[0])", "Ohm"),
    "VOLTCOEF": ("100*(RES[1]-RES[0])/(RES[0]*(VOLT[1]-VOLT[0]))", ""),
    "VARALPHA": ("log(CURR[1]/CURR[0])/log(VOLT[1]/VOLT[0])", ""),
}


class virtual_keithley2400:
    """Use the hardware driver's API without connecting to hardware.

    Unmeasured source values reflect programmed levels. Measurements of other
    enabled quantities are zero; disabled quantities retain the unavailable
    sentinel. Acquisition takes no time and timestamps remain zero. Electrical
    behavior, settling, protection trips, and external events are not modeled.
    Optional-feature settings are stored as software state, without model
    detection. Numerical limits use model 2400 ratings.
    """

    def __init__(self) -> None:
        """Create disconnected in-memory instrument state; perform no I/O."""
        self._connected = False
        self._timeout_ms = 2000.0
        self.check_errors_after_write: bool = True
        self._settings: dict[str, Any] = deepcopy(_DEFAULTS)
        self._sense: tuple[str, ...] = ("CURR",)
        self._errors: deque[tuple[int, str]] = deque()
        self._enabled_errors = set(range(-999, 1000))
        self._setups: dict[int, Any] = {}
        self._source_memory: dict[int, Any] = {}
        self._math = dict(_BUILTIN_MATH)
        self._limits = self._default_limit_tests()
        self._readings: list[dict[str, float]] = []
        self._trace: list[dict[str, float]] = []
        self._cached_nplc: set[float] = set()
        self._pending = False
        self._operation_complete_requested = False
        self._event_status = 0
        self._events = {"measurement": 0, "operation": 0, "questionable": 0}
        self._last_key = -1

    def __enter__(self) -> virtual_keithley2400:
        """Return this instance; connect explicitly inside the context."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Disconnect on exit without changing the programmed output state."""
        self.disconnect()

    def _verify_connected(self) -> None:
        """Require an open virtual session for instrument operations."""
        if not self.connected:
            raise RuntimeError("not connected")

    @staticmethod
    def _default_limit_tests() -> dict[int, dict[str, Any]]:
        """Create independent settings for each numbered measurement test."""
        return {
            index: {
                "enabled": False,
                "failed": False,
                "upper": 1.0,
                "lower": -1.0,
                "fail_pattern": 0,
                "upper_fail_pattern": 0,
                "pass_pattern": 0,
            }
            for index in range(1, 13)
        }

    def _get(self, name: str) -> Any:
        """Read stored settings after checking the session lifecycle."""
        self._verify_connected()
        return self._settings[name]

    def _finish_write(self) -> None:
        """Apply the same optional post-write error check as the hardware driver."""
        if self.check_errors_after_write:
            if self._pending:
                raise pyvisa.errors.VisaIOError(constants.StatusCode.error_timeout)
            self.check_errors()

    def _record_error(self, code: int, message: str) -> None:
        """Record an error without issuing the optional post-write check."""
        self._verify_connected()
        if code not in self._enabled_errors:
            return
        if len(self._errors) < 9:
            self._errors.append((code, message))
        elif len(self._errors) == 9:
            self._errors.append((-350, "Queue overflow"))
        self._event_status |= 32 if code == -113 else 16

    def _error(self, code: int, message: str) -> None:
        """Record a write error and apply automatic checking when enabled."""
        self._record_error(code, message)
        self._finish_write()

    @staticmethod
    def _enum(value: str, choices: tuple[str, ...]) -> str:
        """Match documented SCPI short/long enum spellings to the short form."""
        token = value.strip().upper()
        for choice in choices:
            short = "".join(c for c in choice if not c.islower())
            if token in (short, choice.upper()):
                return short
        raise ValueError("invalid parameter")

    def _limit(self, name: str, position: int) -> float:
        """Read one model-2400 numeric bound or default."""
        self._verify_connected()
        if name in ("sense_current_nplc", "sense_resistance_nplc"):
            name = "sense_voltage_nplc"
        return float(_NUMERIC[name][position])

    @staticmethod
    def _codes(value: str | Sequence[int]) -> set[int]:
        """Expand documented comma-separated error-code lists and inclusive ranges."""
        items = value.split(",") if isinstance(value, str) else value
        codes: set[int] = set()
        for item in items:
            token = str(item).strip().upper()
            if token == "ALL":
                codes.update(range(-999, 1000))
            elif token == "NONE" or not token:
                continue
            elif ":" in token:
                start, stop = (int(v) for v in token.split(":"))
                codes.update(range(start, stop + 1))
            else:
                codes.add(int(token))
        if any(not -999 <= code <= 999 for code in codes):
            raise ValueError("invalid error code")
        return codes

    def _code_string(self, enabled: bool) -> str:
        """Return enabled or disabled error/status codes as a raw code list."""
        self._verify_connected()
        codes = (
            self._enabled_errors
            if enabled
            else set(range(-999, 1000)) - self._enabled_errors
        )
        return ",".join(str(code) for code in sorted(codes))

    def _set(self, name: str, value: Any) -> None:
        """Validate and store a setting, preserving error-queue behavior."""
        self._verify_connected()
        original = self._settings[name]
        try:
            if isinstance(original, bool):
                value = bool(value)
            elif name in _ENUMS:
                value = self._enum(str(value), _ENUMS[name])
            elif name in _NUMERIC:
                low, high, default = _NUMERIC[name]
                if isinstance(value, str):
                    tokens = {
                        "MIN": low,
                        "MINIMUM": low,
                        "MAX": high,
                        "MAXIMUM": high,
                        "DEF": default,
                        "DEFAULT": default,
                    }
                    token = value.strip().upper()
                    if name == "arm_count" and token in ("INF", "INFINITE"):
                        self._settings[name] = "INFINITE"
                        self._finish_write()
                        return
                    if token.startswith(("#H", "#Q", "#B")):
                        value = int(token[2:], {"H": 16, "Q": 8, "B": 2}[token[1]])
                    elif token in tokens:
                        value = tokens[token]
                    else:
                        value = float(value)
                value = float(value)
                if not math.isfinite(value) or not low <= value <= high:
                    raise ValueError("out of range")
                if isinstance(original, int):
                    if not value.is_integer():
                        raise ValueError("integer required")
                    value = int(value)
                elif name == "arm_count":
                    if not value.is_integer():
                        raise ValueError("integer required")
                    value = int(value)
                if name.endswith("_range") and name.startswith(("source_", "sense_")):
                    function = name.split("_")[1]
                    value = next(r for r in _RANGES[function] if r >= abs(value))
            elif name in ("data_elements", "calculation_elements"):
                allowed = (
                    ("VOLTage", "CURRent", "RESistance", "TIME", "STATus")
                    if name == "data_elements"
                    else ("CALCulate", "TIME", "STATus")
                )
                items = value.split(",") if isinstance(value, str) else value
                value = ",".join(self._enum(str(item), allowed) for item in items)
                if not value:
                    raise ValueError("empty element list")
            elif name.endswith("_list_values"):
                maximum = 210 if "voltage" in name else 1.05
                value = tuple(float(v) for v in value)
                if not 1 <= len(value) <= 100 or any(
                    not math.isfinite(v) or abs(v) > maximum for v in value
                ):
                    raise ValueError("invalid source list")
            elif name in (
                "arm_output_events",
                "trigger_output_events",
                "trigger_input_events",
            ):
                choices = (
                    ("TENTer", "TEXit", "NONE")
                    if name == "arm_output_events"
                    else ("SOURce", "DELay", "SENSe", "NONE")
                )
                items = (value,) if isinstance(value, str) else value
                value = tuple(self._enum(str(v), choices) for v in items)
                if (
                    not value
                    or len(set(value)) != len(value)
                    or ("NONE" in value and len(value) != 1)
                ):
                    raise ValueError("invalid event list")
            elif name == "digital_bit_size":
                value = int(value)
                if value not in (3, 4, 16):
                    raise ValueError("invalid bit size")
            elif name == "line_frequency":
                if value not in (50, 60):
                    raise ValueError("invalid line frequency")
                value = int(value)
            elif name == "power_on_setup":
                value = str(value).strip().upper()
                if value not in ("RST", "PRES", "PRESET") and value not in tuple(
                    f"SAV {i}" for i in range(5)
                ):
                    raise ValueError("invalid setup")
            elif name in (
                "composite_limit_pass_memory_location",
                "composite_limit_fail_memory_location",
            ):
                value = str(value).upper()
                if value != "NEXT" and not 1 <= int(value) <= 100:
                    raise ValueError("invalid memory location")
            elif name.startswith("display_") and name.endswith("_text"):
                value = str(value)
                if len(value) > (20 if "top" in name else 32):
                    raise ValueError("display message too long")
            elif name == "math_name":
                value = str(value).upper()
                if not value or len(value) > 10 or not value.isascii():
                    raise ValueError("invalid expression name")
                if value not in self._math:
                    if len(self._math) - len(_BUILTIN_MATH) >= 5:
                        self._error(804, "Expression list full")
                        return
                    self._math[value] = ("", self.math_units)
            elif name in ("error_queue_enabled", "error_queue_disabled"):
                codes = self._codes(value)
                if name == "error_queue_enabled":
                    self._enabled_errors.update(codes)
                else:
                    self._enabled_errors.difference_update(codes)
                value = str(value)
        except (ValueError, TypeError, StopIteration):
            self._error(-222, "Parameter data out of range")
            return
        if name == "data_format" and value == "SRE":
            value = "SREAL"
        if (
            name
            in (
                "digital_output_pattern",
                "composite_limit_pass_pattern",
                "composite_limit_fail_pattern",
            )
            and value >= 2 ** self._settings["digital_bit_size"]
        ):
            self._error(-222, "Parameter data out of range")
            return
        self._settings[name] = value
        if name.endswith("_range") and name.startswith(("sense_", "source_")):
            self._settings[name.removesuffix("_range") + "_auto_range"] = False
        if name == "sense_concurrent" and not value:
            self._sense = ("VOLT",)
        if name == "sense_voltage_nplc" and self._settings["nplc_caching"]:
            self._cached_nplc.add(self._settings[name])
        self._finish_write()

    def _snapshot(self) -> Any:
        """Copy setup state without including measurements or communication state."""
        return deepcopy((self._settings, self._sense, self._limits, self._math))

    def _restore(self, state: Any) -> None:
        """Restore a saved configuration without changing session ownership."""
        self._settings, self._sense, self._limits, self._math = deepcopy(state)
        self._pending = False

    def _restore_source(self, state: Any) -> None:
        """Restore source-memory fields without overwriting unrelated settings."""
        settings, sense, tests, expressions = deepcopy(state)
        for name, value in settings.items():
            if name.startswith(
                (
                    "source_",
                    "sense_",
                    "pulse_",
                    "relative_",
                    "composite_limit_",
                    "math_",
                )
            ) or name in (
                "current_compliance",
                "voltage_compliance",
                "resistance_mode",
                "offset_compensated_ohms",
                "average_type",
                "average_count",
                "averaging_enabled",
                "limit_feed",
            ):
                self._settings[name] = value
        self._sense, self._limits, self._math = sense, tests, expressions

    def _save(self, bank: dict[int, Any], location: int, low: int, high: int) -> None:
        """Save configuration to a documented memory-bank location."""
        self._verify_connected()
        if not low <= location <= high:
            self._error(-222, "Parameter data out of range")
            return
        bank[location] = self._snapshot()
        self._finish_write()

    def _recall(self, bank: dict[int, Any], location: int, low: int, high: int) -> None:
        """Recall configuration and report empty or invalid memory locations."""
        self._verify_connected()
        if not low <= location <= high:
            self._error(-222, "Parameter data out of range")
            return
        if location not in bank:
            self._error(-230, "Data corrupt or stale")
            return
        if bank is self._source_memory:
            self._restore_source(bank[location])
        else:
            self._restore(bank[location])
        self._finish_write()

    def _format(
        self, rows: list[dict[str, float]], calculation: bool = False
    ) -> tuple[float, ...]:
        """Flatten stored readings in the selected public element order."""
        elements = self._settings[
            "calculation_elements" if calculation else "data_elements"
        ].split(",")
        return tuple(
            row.get(element, _UNAVAILABLE) for row in rows for element in elements
        )

    def _math_value(
        self, row: dict[str, float], vector: Sequence[dict[str, float]] = ()
    ) -> float:
        """Evaluate arithmetic against one scalar or a documented vector group."""
        if not self._settings["math_enabled"]:
            return _UNAVAILABLE
        expression = self._math[self._settings["math_name"]][0]
        functions = {
            "LOG": lambda value: math.log10(abs(value)),
            "LN": math.log,
            "SIN": math.sin,
            "COS": math.cos,
            "TAN": math.tan,
            "EXP": math.exp,
        }
        binary: dict[type[ast.operator], Callable[[float, float], float]] = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
        }

        def evaluate(node: ast.AST) -> float:
            """Evaluate only documented arithmetic and measurement references."""
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return float(node.value)
            if isinstance(node, ast.Name):
                name = self._enum(node.id, ("VOLTage", "CURRent", "RESistance", "TIME"))
                value = row[name]
                if value == _UNAVAILABLE:
                    raise LookupError("measurement function disabled")
                return value
            if (
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Name)
                and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, int)
            ):
                name = self._enum(
                    node.value.id, ("VOLTage", "CURRent", "RESistance", "TIME")
                )
                if node.slice.value >= len(vector):
                    raise LookupError("insufficient vector data")
                value = vector[node.slice.value][name]
                if value == _UNAVAILABLE:
                    raise LookupError("measurement function disabled")
                return value
            if isinstance(node, ast.UnaryOp) and isinstance(
                node.op, (ast.UAdd, ast.USub)
            ):
                return evaluate(node.operand) * (
                    -1 if isinstance(node.op, ast.USub) else 1
                )
            if isinstance(node, ast.BinOp) and type(node.op) in binary:
                return float(
                    binary[type(node.op)](evaluate(node.left), evaluate(node.right))
                )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and len(node.args) == 1
                and not node.keywords
            ):
                return float(functions[node.func.id.upper()](evaluate(node.args[0])))
            raise ValueError("invalid expression")

        try:
            return evaluate(ast.parse(expression.replace("^", "**"), mode="eval").body)
        except (LookupError, SyntaxError):
            return _UNAVAILABLE
        except (ValueError, ZeroDivisionError, OverflowError, TypeError):
            return _OVERFLOW

    def _calculation_rows(self) -> list[dict[str, float]]:
        """Group completed readings according to the selected expression's vector size."""
        self._verify_connected()
        expression = self._math[self._settings["math_name"]][0]
        if not expression:
            return [{**row, "CALC": _UNAVAILABLE} for row in self._readings]
        tree = ast.parse(expression.replace("^", "**"), mode="eval")
        indexes = [
            node.slice.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, int)
        ]
        size = max(indexes, default=0) + 1
        results = []
        for offset in range(0, len(self._readings), size):
            vector = self._readings[offset : offset + size]
            row = vector[0]
            results.append({**row, "CALC": self._math_value(row, vector)})
        return results

    def _feed_value(self, row: dict[str, float]) -> float:
        """Select the measurement-test input and apply its relative offset."""
        name = self._settings["limit_feed"]
        value = row["CALC"] if name == "CALC" else row[name]
        return (
            value - self._settings["relative_offset"]
            if self._settings["relative_enabled"]
            else value
        )

    def _acquire(self) -> bool:
        """Complete one finite sequence synchronously without electrical simulation."""
        if (
            not self._settings["output_enabled"]
            and not self._settings["auto_output_off"]
        ):
            self._record_error(802, "Not permitted with OUTPUT off")
            return False
        arms = self._settings["arm_count"]
        if arms == "INFINITE":
            self._record_error(-221, "Settings conflict")
            return False
        count = int(arms) * self._settings["trigger_count"]
        if count > 2500:
            self._record_error(-222, "Parameter data out of range")
            return False
        self._readings = []
        memory_mode = self._settings["source_function"] == "MEM"
        if self._settings["composite_limit_auto_clear"]:
            self._clear_limit_flags()
        for i in range(count):
            function = self._settings["source_function"]
            if memory_mode:
                location = (
                    self._settings["memory_start"] + i % self._settings["memory_points"]
                )
                if location not in self._source_memory:
                    self._record_error(-230, "Data corrupt or stale")
                    return False
                state = self._source_memory[location]
                for name, value in state[0].items():
                    if name != "source_function" and (
                        name.startswith(("source_", "sense_"))
                        or name in ("current_compliance", "voltage_compliance")
                    ):
                        self._settings[name] = deepcopy(value)
                self._sense = state[1]
                function = state[0]["source_function"]
            channel = "voltage" if function == "VOLT" else "current"
            level_key = f"source_{channel}_level"
            mode = self._settings[f"source_{channel}_mode"]
            if mode == "LIST":
                values = self._settings[f"source_{channel}_list_values"]
                start = self._settings[f"source_{channel}_list_start"] - 1
                self._settings[level_key] = values[(start + i) % len(values)]
            elif mode == "SWE":
                start = self._settings[f"source_{channel}_start"]
                stop = self._settings[f"source_{channel}_stop"]
                points = self._settings["sweep_points"]
                fraction = (i % points) / max(points - 1, 1)
                if self._settings["sweep_direction"] == "DOWN":
                    fraction = 1 - fraction
                if self._settings["sweep_spacing"] == "LOG":
                    if start <= 0 or stop <= 0:
                        self._record_error(-222, "Parameter data out of range")
                        return False
                    value = start * (stop / start) ** fraction
                else:
                    value = start + (stop - start) * fraction
                self._settings[level_key] = value
            row = {
                name: (0.0 if name in self._sense else _UNAVAILABLE)
                for name in ("VOLT", "CURR", "RES")
            }
            row[function] = float(self._settings[level_key])
            row["TIME"] = 0.0
            row["STAT"] = 0.0
            row["CALC"] = self._math_value(row)
            self._readings.append(row)
        limit_rows = (
            self._calculation_rows()
            if self._settings["limit_feed"] == "CALC"
            else self._readings
        )
        for row in limit_rows:
            self._evaluate_limits(row)
        feed = self._settings["trace_feed"]
        trace_rows = (
            self._readings
            if feed in ("SENS", "SENS1")
            else self._calculation_rows()
            if feed in ("CALC", "CALC1")
            else [{**row, "CALC": self._feed_value(row)} for row in limit_rows]
        )
        if self._settings["trace_control"] == "NEXT":
            available = self._settings["trace_points"] - len(self._trace)
            self._trace.extend(dict(row) for row in trace_rows[:available])
            if len(self._trace) == self._settings["trace_points"]:
                self._settings["trace_control"] = "NEV"
        self._pending = False
        if self._operation_complete_requested:
            self._event_status |= 1
            self._operation_complete_requested = False
        if self._settings["auto_output_off"]:
            self._settings["output_enabled"] = False

        return True

    def _evaluate_limits(self, row: dict[str, float]) -> None:
        """Evaluate numeric measurement-test thresholds and update digital patterns."""
        value = self._feed_value(row)
        failed = False
        for index, test in self._limits.items():
            if not test["enabled"]:
                continue
            if index in (1, 4):
                continue  # Physical compliance/contact trips are not simulated.
            below, above = value < test["lower"], value > test["upper"]
            test["failed"] |= below or above
            failed |= below or above
            self._settings["digital_output_pattern"] = (
                test["fail_pattern"]
                if below
                else test["upper_fail_pattern"]
                if above
                else test["pass_pattern"]
            )
        if failed:
            self._settings["digital_output_pattern"] = self._settings[
                "composite_limit_fail_pattern"
            ]

    def _clear_limit_flags(self) -> None:
        """Clear latched failure flags without changing test configuration."""
        for test in self._limits.values():
            test["failed"] = False

    def _test_get(self, index: int, field: str, numeric: bool = False) -> Any:
        """Read a numbered measurement-test field with common index validation."""
        self._verify_connected()
        if numeric:
            self._verify_numeric_limit_test_index(index)
        else:
            self._verify_limit_test_index(index)
        return self._limits[index][field]

    def _test_set(
        self, index: int, field: str, value: Any, numeric: bool = False
    ) -> None:
        """Write a measurement-test field and preserve post-write error checks."""
        self._test_get(index, field, numeric)
        try:
            if field == "enabled":
                value = bool(value)
            elif field in ("upper", "lower"):
                tokens = {
                    "MIN": -9.999999e20,
                    "MAX": 9.999999e20,
                    "DEF": 1.0 if field == "upper" else -1.0,
                }
                if isinstance(value, str):
                    token = value.upper()
                    value = tokens[token[:3]] if token[:3] in tokens else float(value)
                value = float(value)
                if not math.isfinite(value) or abs(value) > 9.999999e20:
                    raise ValueError("out of range")
            else:
                token = str(value).upper()
                value = (
                    int(token[2:], {"H": 16, "Q": 8, "B": 2}[token[1]])
                    if token.startswith(("#H", "#Q", "#B"))
                    else int(value)
                )
                if not 0 <= value < 2 ** self._settings["digital_bit_size"]:
                    raise ValueError("invalid pattern")
        except (ValueError, TypeError):
            self._error(-222, "Parameter data out of range")
            return
        self._limits[index][field] = value
        self._finish_write()

    def _append_list(self, channel: str, values: Sequence[float]) -> None:
        """Append a documented batch of list source values without truncation."""
        self._verify_connected()
        key = f"source_{channel}_list_values"
        maximum = 210 if channel == "voltage" else 1.05
        values = tuple(float(v) for v in values)
        if (
            not 1 <= len(values) <= 100
            or len(self._settings[key]) + len(values) > 2500
            or any(not math.isfinite(v) or abs(v) > maximum for v in values)
        ):
            self._error(-222, "Parameter data out of range")
            return
        self._settings[key] += values
        self._finish_write()

    def connect(
        self,
        resource_name: str,
        *,
        resource_manager: pyvisa.ResourceManager | None = None,
        **resource_kwargs: Any,
    ) -> None:
        """Open an in-memory session without opening hardware resources.

        Parameters
        ----------
        resource_name : str
            Accepted for API compatibility; any string such as "virtual" works.
        resource_manager : pyvisa.ResourceManager or None, optional
            Ignored and never opened or closed by the virtual instrument.
        resource_kwargs : Any
            Communication settings accepted for compatibility. Only timeout is used;
            framing, addresses, and serial settings do not affect virtual operation.
        """
        if self.connected:
            raise RuntimeError("already connected")
        timeout = resource_kwargs.get("timeout", 2000)
        if timeout is None:
            timeout = float("inf")
        value = float(timeout)
        if value < 0 or math.isnan(value):
            raise ValueError("timeout must be nonnegative")
        self._timeout_ms = value
        self._connected = True

    @property
    def connected(self) -> bool:
        """Whether a VISA message-based instrument session is open."""
        return self._connected

    @property
    def timeout_ms(self) -> float:
        """VISA I/O timeout in milliseconds; float("inf") disables the timeout."""
        self._verify_connected()
        return self._timeout_ms

    @timeout_ms.setter
    def timeout_ms(self, value: float) -> None:
        """Set the VISA I/O timeout in milliseconds; float("inf") disables it."""
        self._verify_connected()
        value = float(value)
        if value < 0 or math.isnan(value):
            raise ValueError("timeout must be nonnegative")
        self._timeout_ms = value

    def disconnect(self) -> None:
        """Close the instrument session, if connected."""
        self._connected = False

    def read_response(self) -> str:
        """Raise a VISA timeout because virtual operations leave no pending ASCII reply."""
        self._verify_connected()
        raise pyvisa.errors.VisaIOError(constants.StatusCode.error_timeout)

    @staticmethod
    def _verify_sense_function(function: str) -> None:
        """Require a sense function token of VOLT, CURR, or RES."""
        if function not in ("VOLT", "CURR", "RES"):
            raise ValueError("sense function must be VOLT, CURR, or RES")

    @staticmethod
    def _verify_limit_test_index(index: int) -> None:
        """Validate a measurement limit test number (1–12)."""
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or (not 1 <= index <= 12)
        ):
            raise ValueError("measurement limit test index must be from 1 through 12")

    def _verify_numeric_limit_test_index(self, index: int) -> None:
        """Validate a numeric measurement limit test number (2, 3, or 5–12).

        Exclude compliance test 1 and contact-check test 4, which have no numeric
        thresholds or corresponding upper-failure/pass patterns.
        """
        self._verify_limit_test_index(index)
        if index in (1, 4):
            raise ValueError(
                "numeric measurement limit tests are 2, 3, and 5 through 12"
            )

    @property
    def data_format(self) -> str:
        """Reading transfer format: ASC, REAL,32, or SREAL (binary is GPIB only)."""
        return self._get("data_format")

    @data_format.setter
    def data_format(self, value: str) -> None:
        """Set data format; choices: ASC, REAL,32, or SREAL."""
        self._set("data_format", value)

    @property
    def byte_order(self) -> str:
        """Binary transfer byte order: NORM (big endian) or SWAP."""
        return self._get("byte_order")

    @byte_order.setter
    def byte_order(self, value: str) -> None:
        """Set byte order; choices: NORM or SWAP."""
        self._set("byte_order", value)

    @property
    def status_register_format(self) -> str:
        """Status-register response format, such as ASCII, HEX, OCT, or BIN."""
        return self._get("status_register_format")

    @status_register_format.setter
    def status_register_format(self, value: str) -> None:
        """Set status register format."""
        self._set("status_register_format", value)

    @property
    def digital_format(self) -> str:
        """Digital I/O response format: ASCII, HEX, OCT, or BIN."""
        return self._get("digital_format")

    @digital_format.setter
    def digital_format(self, value: str) -> None:
        """Set digital format."""
        self._set("digital_format", value)

    @property
    def data_elements(self) -> str:
        """Enabled reading elements returned by :FORM:ELEM? (for example, VOLT, CURR,
        RES, TIME, or STAT).
        """
        return self._get("data_elements")

    @data_elements.setter
    def data_elements(self, value: str | Sequence[str]) -> None:
        """Set data elements."""
        self._set("data_elements", value)

    @property
    def calculation_elements(self) -> str:
        """Enabled calculation elements returned by :FORM:ELEM:CALC? (CALC, TIME, or
        STAT).
        """
        return self._get("calculation_elements")

    @calculation_elements.setter
    def calculation_elements(self, value: str | Sequence[str]) -> None:
        """Set calculation elements."""
        self._set("calculation_elements", value)

    @property
    def identity(self) -> str:
        """Identity string containing the VIRTUAL serial number."""
        self._verify_connected()
        return "KEITHLEY INSTRUMENTS INC.,MODEL 2400,VIRTUAL,0"

    @property
    def options(self) -> str:
        """Virtual option identification; returns "0" without probing hardware."""
        self._verify_connected()
        return "0"

    def clear_status(self) -> None:
        """Clear status event registers and the instrument error queue with *CLS."""
        self._verify_connected()
        self._errors.clear()
        self._event_status = 0
        for name in self._events:
            self._events[name] = 0
        self._finish_write()

    @property
    def event_status_enable(self) -> int:
        """Standard Event Status Enable register bit mask."""
        return self._get("event_status_enable")

    @event_status_enable.setter
    def event_status_enable(self, value: int) -> None:
        """Set event status enable."""
        self._set("event_status_enable", value)

    def read_event_status(self) -> int:
        """Read and clear the Standard Event Status Register.

        Returns
        -------
        int
            Register bit mask before it was cleared.
        """
        self._verify_connected()
        value, self._event_status = self._event_status, 0
        return value

    @property
    def service_request_enable(self) -> int:
        """Service Request Enable register bit mask."""
        return self._get("service_request_enable")

    @service_request_enable.setter
    def service_request_enable(self, value: int) -> None:
        """Set service request enable."""
        self._set("service_request_enable", value)

    @property
    def status_byte(self) -> int:
        """Current status-byte register bit mask, read with *STB?."""
        self._verify_connected()
        value = 4 if self._errors else 0
        if self._event_status & self._settings["event_status_enable"]:
            value |= 32
        if value & self._settings["service_request_enable"]:
            value |= 64
        return value

    def self_test(self) -> int:
        """Return zero for the virtual instrument's deterministic successful self-test."""
        self._verify_connected()
        return 0

    def save_setup(self, location: int) -> None:
        """Save the current setup to instrument setup memory.

        Parameters
        ----------
        location : int
            Setup-memory location (0–4).
        """
        self._save(self._setups, location, 0, 4)

    def recall_setup(self, location: int) -> None:
        """Restore a setup from instrument setup memory.

        Parameters
        ----------
        location : int
            Setup-memory location (0–4).
        """
        self._recall(self._setups, location, 0, 4)

    def reset(self) -> None:
        """Restore instrument settings using *RST."""
        self._verify_connected()
        preserved = {
            key: value
            for key, value in self._settings.items()
            if key.startswith("display_")
            or key in ("error_queue_enabled", "error_queue_disabled", "power_on_setup")
        }
        self._settings = deepcopy(_DEFAULTS)
        self._settings.update(preserved)
        self._sense = ("CURR",)
        self._limits = self._default_limit_tests()
        self._readings.clear()
        self._trace.clear()
        self._pending = False
        self._operation_complete_requested = False
        self._finish_write()

    def trigger_bus(self) -> None:
        """Send the IEEE-488 bus trigger (*TRG)."""
        self._verify_connected()
        if self._pending and self._settings["arm_source"] == "BUS":
            self._acquire()
        else:
            self._error(-211, "Trigger ignored")
            return
        self._finish_write()

    def set_operation_complete(self) -> None:
        """Queue *OPC; read its completion bit later with read_event_status()."""
        self._verify_connected()
        if self._pending:
            self._operation_complete_requested = True
        else:
            self._event_status |= 1
        self._finish_write()

    def wait_complete(self) -> bool:
        """Return True after a completed finite virtual acquisition.

        Acquisition is synchronous for immediate triggers. If waiting for an external
        trigger, raise the VISA timeout error immediately rather than sleeping.

        Returns
        -------
        bool
            True when no acquisition is pending.
        """
        self._verify_connected()
        if self._pending:
            raise pyvisa.errors.VisaIOError(constants.StatusCode.error_timeout)
        return True

    def wait_to_continue(self) -> None:
        """Send *WAI; the guide describes it as a no-op for this instrument."""
        self._verify_connected()
        self._finish_write()

    @property
    def power_on_setup(self) -> str:
        """Setup restored at power-on: RST, PRESet, or SAV followed by a setup
        location.
        """
        return self._get("power_on_setup")

    @power_on_setup.setter
    def power_on_setup(self, value: str) -> None:
        """Set power on setup."""
        self._set("power_on_setup", value)

    def preset(self) -> None:
        """Restore the instrument preset configuration with :SYST:PRES."""
        self.reset()

    @property
    def remote_sense(self) -> bool:
        """Whether remote sense is enabled."""
        return self._get("remote_sense")

    @remote_sense.setter
    def remote_sense(self, enabled: bool) -> None:
        """Set remote sense."""
        self._set("remote_sense", enabled)

    @property
    def contact_check_enabled(self) -> bool:
        """Whether contact checking is enabled.

        Requires the contact-check option and remote sensing.
        """
        return self._get("contact_check_enabled")

    @contact_check_enabled.setter
    def contact_check_enabled(self, enabled: bool) -> None:
        """Set contact check enabled."""
        self._set("contact_check_enabled", enabled)

    @property
    def contact_check_resistance(self) -> float:
        """Contact-check resistance threshold, in ohms (0–60).

        Requires the contact-check option.
        """
        return self._get("contact_check_resistance")

    @contact_check_resistance.setter
    def contact_check_resistance(self, value: float) -> None:
        """Set contact check resistance, in ohms."""
        self._set("contact_check_resistance", value)

    @property
    def guard_mode(self) -> str:
        """Selected guard mode; documented choices are OHMS or CABLE."""
        return self._get("guard_mode")

    @guard_mode.setter
    def guard_mode(self, value: str) -> None:
        """Set guard mode."""
        self._set("guard_mode", value)

    def initialize_memory(self) -> None:
        """Initialize battery-backed RAM; clears trace data and saved setups."""
        self._verify_connected()
        self._setups.clear()
        self._source_memory.clear()
        self._math = dict(_BUILTIN_MATH)
        self._settings["math_name"] = "POWER"
        self._trace.clear()
        self._readings.clear()
        self._finish_write()

    def beep(self, frequency: float, duration: float) -> None:
        """Validate tone parameters without emitting sound.

        Parameters
        ----------
        frequency : float
            Tone frequency in hertz (65–2000000).
        duration : float
            Tone duration in seconds (0–7.9).
        """
        self._verify_connected()
        if not 65 <= frequency <= 2e6 or not 0 <= duration <= 7.9:
            self._error(-222, "Parameter data out of range")
            return
        self._finish_write()

    @property
    def beeper_enabled(self) -> bool:
        """Whether beeper is enabled."""
        return self._get("beeper_enabled")

    @beeper_enabled.setter
    def beeper_enabled(self, enabled: bool) -> None:
        """Set beeper enabled."""
        self._set("beeper_enabled", enabled)

    @property
    def auto_zero(self) -> str:
        """Auto-zero state: ON, OFF, or ONCE; ONCE performs an immediate update."""
        return self._get("auto_zero")

    @auto_zero.setter
    def auto_zero(self, state: str) -> None:
        """Set auto zero."""
        self._set("auto_zero", state)

    @property
    def nplc_caching(self) -> bool:
        """Whether the instrument caches zero/reference values for multiple NPLC
        settings.
        """
        return self._get("nplc_caching")

    @nplc_caching.setter
    def nplc_caching(self, enabled: bool) -> None:
        """Set nplc caching."""
        self._set("nplc_caching", enabled)

    @property
    def cached_nplc_values(self) -> tuple[float, ...]:
        """Cached integration-time settings, as a tuple of power-line-cycle values."""
        self._verify_connected()
        return tuple(sorted(self._cached_nplc))

    def refresh_nplc_cache(self) -> None:
        """Refresh the instrument's NPLC cache."""
        self._verify_connected()
        self._cached_nplc.add(self.nplc)
        self._finish_write()

    def reset_nplc_cache(self) -> None:
        """Reset the instrument's NPLC cache."""
        self._verify_connected()
        self._cached_nplc.clear()
        self._finish_write()

    @property
    def line_frequency(self) -> int:
        """Selected mains line frequency, in hertz; 50 or 60 Hz (use 50 Hz for 400 Hz
        mains).
        """
        return self._get("line_frequency")

    @line_frequency.setter
    def line_frequency(self, value: int) -> None:
        """Set line frequency, in hertz."""
        self._set("line_frequency", value)

    @property
    def auto_line_frequency(self) -> bool:
        """Whether the instrument automatically selects the mains line frequency."""
        return self._get("auto_line_frequency")

    @auto_line_frequency.setter
    def auto_line_frequency(self, enabled: bool) -> None:
        """Set auto line frequency."""
        self._set("auto_line_frequency", enabled)

    def read_error(self) -> str:
        """Read and remove the oldest error/status message from the error queue.

        Returns
        -------
        str
            Raw numeric code and quoted message, or the no-error response.
        """
        self._verify_connected()
        if not self._errors:
            return '0,"No error"'
        code, message = self._errors.popleft()
        return f'{code},"{message}"'

    def check_errors(self) -> None:
        """Read and clear the error queue, raising RuntimeError for nonzero errors.

        The exception contains the instrument's unchanged full error response. Uses
        read_errors() once; an empty queue returns normally.
        """
        errors = self.read_errors()
        if int(errors.split(",", 1)[0]) != 0:
            raise RuntimeError(errors)

    def read_errors(self) -> str:
        """Read and remove all error/status messages from the queue in one query.

        Returns
        -------
        str
            Raw response containing all queued codes and messages, or the no-error
            response.
        """
        self._verify_connected()
        if not self._errors:
            return '0,"No error"'
        response = ",".join(f'{code},"{message}"' for code, message in self._errors)
        self._errors.clear()
        return response

    @property
    def error_count(self) -> int:
        """Number of queued error/status messages; reading does not remove entries."""
        self._verify_connected()
        return len(self._errors)

    def read_error_code(self) -> int:
        """Read and remove the oldest queued error/status entry.

        Returns
        -------
        int
            Numeric code for the removed entry, or zero if the queue was empty.
        """
        return int(self.read_error().split(",", 1)[0])

    def read_error_codes(self) -> str:
        """Read and remove all queued error/status codes.

        Returns
        -------
        str
            Raw list of numeric codes, or the no-error response.
        """
        self._verify_connected()
        response = ",".join(str(code) for code, _ in self._errors) or "0"
        self._errors.clear()
        return response

    def clear_errors(self) -> None:
        """Remove all messages from the instrument error queue."""
        self._verify_connected()
        self._errors.clear()
        self._clear_limit_flags()
        self._finish_write()

    def press_key(self, key_code: int) -> None:
        """Simulate a front-panel key press using its documented numeric key code.

        Parameters
        ----------
        key_code : int
            Documented numeric front-panel key code.
        """
        self._verify_connected()
        if not 1 <= key_code <= 32:
            self._error(-222, "Parameter data out of range")
            return
        self._last_key = key_code
        self._finish_write()

    def read_last_key(self) -> int:
        """Read the key code queued by the last physical or simulated press."""
        self._verify_connected()
        key, self._last_key = self._last_key, -1
        return key

    @property
    def scpi_version(self) -> str:
        """SCPI standard version implemented by the instrument, as a raw string."""
        self._verify_connected()
        return "1996.0"

    def local(self) -> None:
        """Return the instrument to local control (documented for RS-232)."""
        self._set("remote_lockout", False)

    @property
    def remote_lockout(self) -> bool:
        """Whether the front-panel LOCAL key is locked out (documented for RS-232)."""
        return self._get("remote_lockout")

    @remote_lockout.setter
    def remote_lockout(self, enabled: bool) -> None:
        """Set remote lockout."""
        self._set("remote_lockout", enabled)

    @property
    def timestamp(self) -> float:
        """Timestamp, in seconds."""
        self._verify_connected()
        return 0.0

    def reset_timestamp(self) -> None:
        """Reset the instrument's timestamp."""
        self._verify_connected()
        self._finish_write()

    @property
    def auto_reset_timestamp(self) -> bool:
        """Whether the timestamp resets automatically when a measurement sequence
        starts.
        """
        return self._get("auto_reset_timestamp")

    @auto_reset_timestamp.setter
    def auto_reset_timestamp(self, enabled: bool) -> None:
        """Set auto reset timestamp."""
        self._set("auto_reset_timestamp", enabled)

    @property
    def range_change_mode(self) -> str:
        """Selected range change mode; documented choices are SINGLE or MULTIPLE."""
        return self._get("range_change_mode")

    @range_change_mode.setter
    def range_change_mode(self, mode: str) -> None:
        """Set range change mode."""
        self._set("range_change_mode", mode)

    @property
    def trace_data(self) -> tuple[float, ...]:
        """Stored trace-buffer reading values, as a flat tuple of floats.

        The selected format and elements determine the reply layout. Instrument
        overflow and unavailable-value sentinels are preserved.
        """
        self._verify_connected()
        if self._settings["trace_feed"] in ("CALC", "CALC2"):
            return self._format(self._trace, True)
        return self._format(self._trace)

    def clear_trace(self) -> None:
        """Remove stored readings from the trace buffer."""
        self._verify_connected()
        self._trace.clear()
        self._finish_write()

    @property
    def trace_memory(self) -> tuple[int, int]:
        """Available and reserved trace memory, in bytes."""
        self._verify_connected()
        bytes_per_reading = 20
        reserved = self.trace_points * bytes_per_reading
        return (2500 * bytes_per_reading - reserved, reserved)

    @property
    def trace_points(self) -> int:
        """Configured trace-buffer capacity, in readings (1–2500)."""
        return self._get("trace_points")

    @trace_points.setter
    def trace_points(self, count: int | str) -> None:
        """Set trace points."""
        self._set("trace_points", count)

    @property
    def trace_points_actual(self) -> int:
        """Number of readings currently stored in the trace buffer."""
        self._verify_connected()
        return len(self._trace)

    @property
    def trace_feed(self) -> str:
        """Selected trace feed; documented choices are SENSE, CALC, or CALC2."""
        return self._get("trace_feed")

    @trace_feed.setter
    def trace_feed(self, feed: str) -> None:
        """Set trace feed."""
        self._set("trace_feed", feed)

    @property
    def trace_control(self) -> str:
        """Selected trace control; documented choices are NEXT or NEVER."""
        return self._get("trace_control")

    @trace_control.setter
    def trace_control(self, control: str) -> None:
        """Set trace control."""
        self._set("trace_control", control)

    @property
    def trace_timestamp_format(self) -> str:
        """Selected trace timestamp format; documented choices are ABSOLUTE or DELTA."""
        return self._get("trace_timestamp_format")

    @trace_timestamp_format.setter
    def trace_timestamp_format(self, fmt: str) -> None:
        """Set trace timestamp format."""
        self._set("trace_timestamp_format", fmt)

    def clear_triggers(self) -> None:
        """Clear trigger-model configuration using :TRIG:CLE."""
        self._verify_connected()
        for name in _DEFAULTS:
            if name.startswith(("arm_", "trigger_")):
                self._settings[name] = deepcopy(_DEFAULTS[name])
        self._pending = False
        self._finish_write()

    def initiate(self) -> None:
        """Start the configured trigger sequence by taking the instrument out of idle.

        With automatic write-error checking enabled, the following error query can
        wait until the sequence finishes. Disable that checking for asynchronous
        initiation, then check errors explicitly after completion.
        """
        self._verify_connected()
        if self._pending:
            self._error(-213, "Init ignored")
            return
        if (
            self._settings["arm_count"] != "INFINITE"
            and self._settings["arm_source"] == "IMM"
            and self._settings["trigger_source"] == "IMM"
        ):
            self._acquire()
        else:
            self._pending = True
        self._finish_write()

    def abort(self) -> None:
        """Stop the active trigger sequence and return the instrument to idle."""
        self._verify_connected()
        self._pending = False
        self._finish_write()

    @property
    def arm_count(self) -> int | str:
        """Arm-layer count; returns INFINITE when the instrument sentinel 9.9e37 is
        reported.
        """
        return self._get("arm_count")

    @arm_count.setter
    def arm_count(self, count: int | str) -> None:
        """Set arm count."""
        self._set("arm_count", count)

    @property
    def trigger_count(self) -> int:
        """Number of source-measure cycles per arm event."""
        return self._get("trigger_count")

    @trigger_count.setter
    def trigger_count(self, count: int | str) -> None:
        """Set trigger count."""
        self._set("trigger_count", count)

    @property
    def arm_source(self) -> str:
        """Arm-event source: IMM, TLINK, TIMER, MANUAL, BUS, NSTEST, PSTEST, or
        BSTEST.
        """
        return self._get("arm_source")

    @arm_source.setter
    def arm_source(self, source: str) -> None:
        """Set arm source."""
        self._set("arm_source", source)

    @property
    def trigger_source(self) -> str:
        """Selected trigger source; documented choices are IMMEDIATE or TLINK."""
        return self._get("trigger_source")

    @trigger_source.setter
    def trigger_source(self, source: str) -> None:
        """Set trigger source."""
        self._set("trigger_source", source)

    @property
    def trigger_delay(self) -> float:
        """Delay between a trigger event and its source-measure cycle, in seconds."""
        return self._get("trigger_delay")

    @trigger_delay.setter
    def trigger_delay(self, delay: float | str) -> None:
        """Set trigger delay, in seconds."""
        self._set("trigger_delay", delay)

    @property
    def arm_timer(self) -> float:
        """Interval between timer-controlled arm events, in seconds."""
        return self._get("arm_timer")

    @arm_timer.setter
    def arm_timer(self, seconds: float | str) -> None:
        """Set arm timer, in seconds."""
        self._set("arm_timer", seconds)

    @property
    def arm_bypass(self) -> str:
        """Arm-event bypass direction: SOURCE or ACCEPTOR."""
        return self._get("arm_bypass")

    @arm_bypass.setter
    def arm_bypass(self, direction: str) -> None:
        """Set arm bypass."""
        self._set("arm_bypass", direction)

    @property
    def trigger_bypass(self) -> str:
        """Trigger-event bypass direction: SOURCE or ACCEPTOR."""
        return self._get("trigger_bypass")

    @trigger_bypass.setter
    def trigger_bypass(self, direction: str) -> None:
        """Set trigger bypass."""
        self._set("trigger_bypass", direction)

    @property
    def arm_input_line(self) -> int:
        """Trigger Link input line used for arm events (1–4)."""
        return self._get("arm_input_line")

    @arm_input_line.setter
    def arm_input_line(self, line: int) -> None:
        """Set arm input line."""
        self._set("arm_input_line", line)

    @property
    def trigger_input_line(self) -> int:
        """Trigger Link input line used for trigger events (1–4)."""
        return self._get("trigger_input_line")

    @trigger_input_line.setter
    def trigger_input_line(self, line: int) -> None:
        """Set trigger input line."""
        self._set("trigger_input_line", line)

    @property
    def arm_output_line(self) -> int:
        """Trigger Link output line used for arm events (1–4)."""
        return self._get("arm_output_line")

    @arm_output_line.setter
    def arm_output_line(self, line: int) -> None:
        """Set arm output line."""
        self._set("arm_output_line", line)

    @property
    def trigger_output_line(self) -> int:
        """Trigger Link output line used for trigger events (1–4)."""
        return self._get("trigger_output_line")

    @trigger_output_line.setter
    def trigger_output_line(self, line: int) -> None:
        """Set trigger output line."""
        self._set("trigger_output_line", line)

    @property
    def arm_output_events(self) -> tuple[str, ...]:
        """Arm events that produce an output pulse: TENTER, TEXIT, or NONE."""
        return self._get("arm_output_events")

    @arm_output_events.setter
    def arm_output_events(self, events: str | Sequence[str]) -> None:
        """Set arm output events."""
        self._set("arm_output_events", events)

    @property
    def trigger_output_events(self) -> tuple[str, ...]:
        """Trigger stages that produce output pulses: SOURCE, DELAY, SENSE, or NONE."""
        return self._get("trigger_output_events")

    @trigger_output_events.setter
    def trigger_output_events(self, events: str | Sequence[str]) -> None:
        """Set trigger output events."""
        self._set("trigger_output_events", events)

    @property
    def trigger_input_events(self) -> tuple[str, ...]:
        """Trigger stages requiring input events: SOURCE, DELAY, SENSE, or NONE."""
        return self._get("trigger_input_events")

    @trigger_input_events.setter
    def trigger_input_events(self, events: str | Sequence[str]) -> None:
        """Set trigger input events."""
        self._set("trigger_input_events", events)

    @property
    def contact_check_event_source(self) -> str:
        """Contact-check event source: CCHECK or IMM.

        Requires an instrument supporting the contact-check option.
        """
        return self._get("contact_check_event_source")

    @contact_check_event_source.setter
    def contact_check_event_source(self, source: str) -> None:
        """Set contact check event source."""
        self._set("contact_check_event_source", source)

    @property
    def contact_check_timeout(self) -> float:
        """Contact-check event timeout, in seconds; zero permits an indefinite wait.

        Requires an instrument supporting the contact-check option.
        """
        return self._get("contact_check_timeout")

    @contact_check_timeout.setter
    def contact_check_timeout(self, seconds: float) -> None:
        """Set contact check timeout, in seconds."""
        self._set("contact_check_timeout", seconds)

    def set_mep_holdoff(self, enabled: bool) -> None:
        """Set Appendix G NDAC holdoff (no query is documented).

        Parameters
        ----------
        enabled : bool
            True enables NDAC holdoff; False disables it.
        """
        self._verify_connected()
        self._mep_holdoff = bool(enabled)
        self._finish_write()

    @property
    def scpi_protocol_enabled(self) -> bool:
        """Query MEP state; true indicates SCPI protocol, false indicates 488.1."""
        self._verify_connected()
        return True

    def read(self) -> tuple[float, ...]:
        """Initiate the configured sequence and return its measurement results.

        READ? performs INIT followed by FETCH. The output must already be on unless
        automatic output-off operation is enabled. The reply waits for all
        configured arm/trigger cycles to finish; adjust timeout_ms accordingly.

        Returns
        -------
        tuple[float, ...]
            Flat reading values in data_elements order, repeated for each reading.
            Overflow (9.9e37) and unavailable-value (9.91e37) sentinels are
            preserved.
        """
        self._verify_connected()
        if (
            self._settings["arm_source"] != "IMM"
            or self._settings["trigger_source"] != "IMM"
        ):
            self._pending = True
            raise pyvisa.errors.VisaIOError(constants.StatusCode.error_timeout)
        if not self._acquire():
            raise pyvisa.errors.VisaIOError(constants.StatusCode.error_timeout)
        return self._format(self._readings)

    def fetch(self) -> tuple[float, ...]:
        """Return completed-sequence results without initiating a measurement.

        If acquisition is active, the instrument waits until it returns to idle.
        Repeated calls may return the same readings.

        Returns
        -------
        tuple[float, ...]
            Flat reading values in data_elements order, repeated for each reading.
            Instrument overflow and unavailable-value sentinels are preserved.
        """
        self._verify_connected()
        if self._pending:
            raise pyvisa.errors.VisaIOError(constants.StatusCode.error_timeout)
        return self._format(self._readings)

    def measure(self, function: str | None = None) -> tuple[float, ...]:
        """Configure and perform a one-shot measurement, turning the source on.

        This native command resets the selected function's settings and trigger
        configuration before reading. Use read() to preserve an explicit setup.

        Parameters
        ----------
        function : str or None, optional
            VOLT, CURR, or RES. None uses the currently selected function.

        Returns
        -------
        tuple[float, ...]
            Flat reading values in the configured element order, preserving
            instrument overflow and unavailable-value sentinels.
        """
        if function is not None:
            self._verify_sense_function(function)
        self._verify_connected()
        self.configure_measurement(function if function is not None else self._sense[0])
        return self.read()

    def configure_measurement(self, function: str) -> None:
        """Configure a one-shot measurement and turn the source output on.

        The instrument resets the selected function to its defaults, selects
        immediate single-reading triggers, and disables math and trace operation.

        Parameters
        ----------
        function : str
            Measurement function: VOLT, CURR, or RES.
        """
        self._verify_sense_function(function)
        self._verify_connected()
        self._sense = (function,)
        for name in self._settings:
            if name.startswith(
                "sense_"
                + {"VOLT": "voltage", "CURR": "current", "RES": "resistance"}[function]
            ):
                self._settings[name] = deepcopy(_DEFAULTS[name])
        self._settings.update(
            arm_source="IMM",
            arm_count=1,
            trigger_source="IMM",
            trigger_count=1,
            trigger_delay=0.0,
            math_enabled=False,
            trace_control="NEV",
            auto_zero="ON",
            output_enabled=True,
        )
        self._pending = False
        self._finish_write()

    @property
    def configured_measurement(self) -> tuple[str, ...]:
        """Configured measurement function tokens returned by :CONF?.

        Returns
        -------
        tuple[str, ...]
            Value decoded from the instrument response.
        """
        self._verify_connected()
        return self._sense

    @property
    def sense_data_latest(self) -> tuple[float, ...]:
        """Latest measurement values, as a flat tuple of floats.

        The selected format and elements determine the reply layout. Instrument
        overflow and unavailable-value sentinels are preserved.
        """
        self._verify_connected()
        return self._format(self._readings[-1:])

    @property
    def trace_points_minimum(self) -> float:
        """Instrument-reported minimum value for trace points."""
        return self._limit("trace_points", 0)

    @property
    def trace_points_maximum(self) -> float:
        """Instrument-reported maximum value for trace points."""
        return self._limit("trace_points", 1)

    @property
    def trace_points_default(self) -> float:
        """Instrument-reported default value for trace points."""
        return self._limit("trace_points", 2)

    @property
    def arm_count_minimum(self) -> float:
        """Instrument-reported minimum value for arm count."""
        return self._limit("arm_count", 0)

    @property
    def arm_count_maximum(self) -> float:
        """Instrument-reported maximum value for arm count."""
        return self._limit("arm_count", 1)

    @property
    def arm_count_default(self) -> float:
        """Instrument-reported default value for arm count."""
        return self._limit("arm_count", 2)

    @property
    def trigger_count_minimum(self) -> float:
        """Instrument-reported minimum value for trigger count."""
        return self._limit("trigger_count", 0)

    @property
    def trigger_count_maximum(self) -> float:
        """Instrument-reported maximum value for trigger count."""
        return self._limit("trigger_count", 1)

    @property
    def trigger_count_default(self) -> float:
        """Instrument-reported default value for trigger count."""
        return self._limit("trigger_count", 2)

    @property
    def trigger_delay_minimum(self) -> float:
        """Instrument-reported minimum value for trigger delay in seconds."""
        return self._limit("trigger_delay", 0)

    @property
    def trigger_delay_maximum(self) -> float:
        """Instrument-reported maximum value for trigger delay in seconds."""
        return self._limit("trigger_delay", 1)

    @property
    def trigger_delay_default(self) -> float:
        """Instrument-reported default value for trigger delay in seconds."""
        return self._limit("trigger_delay", 2)

    @property
    def arm_timer_minimum(self) -> float:
        """Instrument-reported minimum value for arm timer in seconds."""
        return self._limit("arm_timer", 0)

    @property
    def arm_timer_maximum(self) -> float:
        """Instrument-reported maximum value for arm timer in seconds."""
        return self._limit("arm_timer", 1)

    @property
    def arm_timer_default(self) -> float:
        """Instrument-reported default value for arm timer in seconds."""
        return self._limit("arm_timer", 2)

    @property
    def source_function(self) -> str:
        """Selected source function; documented choices are VOLT, CURR, or MEM."""
        return self._get("source_function")

    @source_function.setter
    def source_function(self, value: str) -> None:
        """Set source function; choices: VOLT, CURR, or MEM."""
        self._set("source_function", value)

    @property
    def source_level(self) -> float:
        """Immediate level for the selected source function, in volts or amperes.

        Queries source_function to select the channel. MEM has no direct level.
        """
        function = self.source_function[:4]
        if function == "VOLT":
            return self.source_voltage_level
        if function == "CURR":
            return self.source_current_level
        raise ValueError("memory source mode has no direct level")

    @source_level.setter
    def source_level(self, value: float | str) -> None:
        """Set source level."""
        function = self.source_function[:4]
        if function == "VOLT":
            self.source_voltage_level = value
        elif function == "CURR":
            self.source_current_level = value
        else:
            raise ValueError("memory source mode has no direct level")

    @property
    def source_range(self) -> float:
        """Range for the selected source function, in volts or amperes.

        Queries source_function to select the channel. MEM has no direct range.
        """
        function = self.source_function[:4]
        if function == "VOLT":
            return self.source_voltage_range
        if function == "CURR":
            return self.source_current_range
        raise ValueError("memory source mode has no direct range")

    @source_range.setter
    def source_range(self, value: float | str) -> None:
        """Set source range, in the measured quantity's units."""
        function = self.source_function[:4]
        if function == "VOLT":
            self.source_voltage_range = value
        elif function == "CURR":
            self.source_current_range = value
        else:
            raise ValueError("memory source mode has no direct range")

    @property
    def sense_functions(self) -> tuple[str, ...]:
        """Enabled measurement functions (read-only)."""
        self._verify_connected()
        return self._sense

    @property
    def sense_concurrent(self) -> bool:
        """Whether more than one measurement function can be enabled simultaneously."""
        return self._get("sense_concurrent")

    @sense_concurrent.setter
    def sense_concurrent(self, enabled: bool) -> None:
        """Set sense concurrent."""
        self._set("sense_concurrent", enabled)

    @property
    def enabled_sense_function_count(self) -> int:
        """Number of enabled measurement functions."""
        return len(self.sense_functions)

    @property
    def disabled_sense_function_count(self) -> int:
        """Number of disabled measurement functions."""
        return len(self.disabled_sense_functions)

    @property
    def disabled_sense_functions(self) -> tuple[str, ...]:
        """Disabled measurement functions as VOLT, CURR, and RES tokens."""
        self._verify_connected()
        return tuple(
            name for name in ("VOLT", "CURR", "RES") if name not in self._sense
        )

    def enable_sense_functions(self, functions: Sequence[str]) -> None:
        """Enable each requested measurement function using separate commands.

        Parameters
        ----------
        functions : Sequence[str]
            Functions to enable, such as VOLT, CURR, or RES. Other enabled
            functions remain enabled; use sense_concurrent for concurrent
            measurement.
        """
        self._verify_connected()
        for function in functions:
            try:
                function = self._enum(
                    function.upper().removesuffix(":DC"),
                    ("VOLTage", "CURRent", "RESistance"),
                )
            except ValueError:
                self._error(-224, "Illegal parameter value")
                return
            if function not in self._sense:
                self._sense = (
                    (*self._sense, function)
                    if self._settings["sense_concurrent"]
                    else (function,)
                )
            self._finish_write()

    def disable_sense_functions(self, functions: Sequence[str]) -> None:
        """Disable each requested measurement function using separate commands.

        Parameters
        ----------
        functions : Sequence[str]
            Functions to disable, such as VOLT, CURR, or RES.
        """
        self._verify_connected()
        for function in functions:
            try:
                function = self._enum(
                    function.upper().removesuffix(":DC"),
                    ("VOLTage", "CURRent", "RESistance"),
                )
            except ValueError:
                self._error(-224, "Illegal parameter value")
                return
            self._sense = tuple(value for value in self._sense if value != function)
            self._finish_write()

    def enable_all_sense_functions(self) -> None:
        """Enable all supported sense functions."""
        self._verify_connected()
        if not self._settings["sense_concurrent"]:
            self._error(-221, "Settings conflict")
            return
        self._sense = ("VOLT", "CURR", "RES")
        self._finish_write()

    def disable_all_sense_functions(self) -> None:
        """Disable all sense functions."""
        self._verify_connected()
        self._sense = ()
        self._finish_write()

    def sense_function_enabled(self, function: str) -> bool:
        """Whether the specified VOLT, CURR, or RES sense function is enabled.

        Parameters
        ----------
        function : str
            VOLT, CURR, or RES.
        """
        self._verify_sense_function(function)
        self._verify_connected()
        return function in self._sense

    @property
    def sense_auto_range(self) -> bool:
        """Whether autoranging is enabled for the sole enabled measurement function.

        Queries sense_functions; exactly one must be enabled. Use the function-
        specific autorange properties for concurrent measurements.
        """
        functions = self.sense_functions
        if len(functions) != 1:
            raise ValueError(
                "sense_auto_range requires exactly one selected sense function"
            )
        if functions[0] == "VOLT":
            return self.sense_voltage_auto_range
        if functions[0] == "CURR":
            return self.sense_current_auto_range
        return self.sense_resistance_auto_range

    @sense_auto_range.setter
    def sense_auto_range(self, enabled: bool) -> None:
        """Set sense auto range."""
        functions = self.sense_functions
        if len(functions) != 1:
            raise ValueError(
                "sense_auto_range requires exactly one selected sense function"
            )
        if functions[0] == "VOLT":
            self.sense_voltage_auto_range = enabled
        elif functions[0] == "CURR":
            self.sense_current_auto_range = enabled
        else:
            self.sense_resistance_auto_range = enabled

    @property
    def voltage_range(self) -> float:
        """Voltage measurement range, in volts; alias of sense_voltage_range."""
        return self.sense_voltage_range

    @voltage_range.setter
    def voltage_range(self, value: float | str) -> None:
        """Set voltage range, in volts."""
        self.sense_voltage_range = value

    @property
    def current_range(self) -> float:
        """Current measurement range, in amperes; alias of sense_current_range."""
        return self.sense_current_range

    @current_range.setter
    def current_range(self, value: float | str) -> None:
        """Set current range, in amperes."""
        self.sense_current_range = value

    @property
    def current_compliance(self) -> float:
        """Current compliance setting for voltage sourcing, in amperes."""
        return self._get("current_compliance")

    @current_compliance.setter
    def current_compliance(self, value: float | str) -> None:
        """Set current compliance, in amperes."""
        self._set("current_compliance", value)

    @property
    def voltage_compliance(self) -> float:
        """Voltage compliance setting for current sourcing, in volts."""
        return self._get("voltage_compliance")

    @voltage_compliance.setter
    def voltage_compliance(self, value: float | str) -> None:
        """Set voltage compliance, in volts."""
        self._set("voltage_compliance", value)

    @property
    def current_compliance_tripped(self) -> bool:
        """Whether the current compliance limit has been reached."""
        self._verify_connected()
        return False

    @property
    def voltage_compliance_tripped(self) -> bool:
        """Whether the voltage compliance limit has been reached."""
        self._verify_connected()
        return False

    @property
    def current_range_synchronized(self) -> bool:
        """Whether the measurement range follows the compliance range.

        The current and voltage synchronization properties control the same
        setting.
        """
        return self._get("current_range_synchronized")

    @current_range_synchronized.setter
    def current_range_synchronized(self, enabled: bool) -> None:
        """Set current range synchronized."""
        self._set("current_range_synchronized", enabled)

    @property
    def voltage_range_synchronized(self) -> bool:
        """Whether the measurement range follows the compliance range.

        The current and voltage synchronization properties control the same
        setting.
        """
        return self.current_range_synchronized

    @voltage_range_synchronized.setter
    def voltage_range_synchronized(self, enabled: bool) -> None:
        """Set voltage range synchronized."""
        self.current_range_synchronized = enabled

    @property
    def nplc(self) -> float:
        """Integration time, in power-line cycles; shared by all measurement
        functions.
        """
        return self.sense_voltage_nplc

    @nplc.setter
    def nplc(self, value: float | str) -> None:
        """Set nplc, in power-line cycles."""
        self.sense_voltage_nplc = value

    @property
    def resistance_mode(self) -> str:
        """Resistance measurement mode: AUTO or MANUAL."""
        return self._get("resistance_mode")

    @resistance_mode.setter
    def resistance_mode(self, value: str) -> None:
        """Set resistance mode."""
        self._set("resistance_mode", value)

    @property
    def offset_compensated_ohms(self) -> bool:
        """Whether offset-compensated resistance measurement is enabled."""
        return self._get("offset_compensated_ohms")

    @offset_compensated_ohms.setter
    def offset_compensated_ohms(self, value: bool) -> None:
        """Set offset compensated ohms."""
        self._set("offset_compensated_ohms", value)

    @property
    def voltage_protection(self) -> float:
        """Source-voltage protection threshold, in volts."""
        return self._get("voltage_protection")

    @voltage_protection.setter
    def voltage_protection(self, value: float | str) -> None:
        """Set voltage protection, in volts."""
        self._set("voltage_protection", value)

    @property
    def voltage_protection_tripped(self) -> bool:
        """Whether the source-voltage protection threshold has been reached."""
        self._verify_connected()
        return False

    @property
    def average_type(self) -> str:
        """Averaging filter type: REPEAT or MOVING."""
        return self._get("average_type")

    @average_type.setter
    def average_type(self, value: str) -> None:
        """Set average type."""
        self._set("average_type", value)

    @property
    def average_count(self) -> int:
        """Number of readings used by the averaging filter."""
        return self._get("average_count")

    @average_count.setter
    def average_count(self, value: int | str) -> None:
        """Set average count."""
        self._set("average_count", value)

    @property
    def averaging_enabled(self) -> bool:
        """Whether the measurement averaging filter is enabled."""
        return self._get("averaging_enabled")

    @averaging_enabled.setter
    def averaging_enabled(self, value: bool) -> None:
        """Set averaging enabled."""
        self._set("averaging_enabled", value)

    @property
    def output_enabled(self) -> bool:
        """Whether output is enabled."""
        return self._get("output_enabled")

    @output_enabled.setter
    def output_enabled(self, value: bool) -> None:
        """Set output enabled."""
        self._set("output_enabled", value)

    @property
    def output_enable_interlock_enabled(self) -> bool:
        """Whether the external output-enable interlock is enabled.

        The virtual output-enable line is always at logic low, so enabling the
        interlock never prevents output.
        """
        return self._get("output_enable_interlock_enabled")

    @output_enable_interlock_enabled.setter
    def output_enable_interlock_enabled(self, value: bool) -> None:
        """Enable or disable the external output-enable interlock."""
        self._set("output_enable_interlock_enabled", value)

    @property
    def output_enable_interlock_tripped(self) -> bool:
        """Whether the output-enable line prevents output; always False here."""
        return False

    @property
    def output_off_mode(self) -> str:
        """Output-off behavior, read back as HIMP, NORM, ZERO, or GUAR."""
        return self._get("output_off_mode")

    @output_off_mode.setter
    def output_off_mode(self, value: str) -> None:
        """Set output off mode."""
        self._set("output_off_mode", value)

    @property
    def terminals(self) -> str:
        """Selected terminals; documented choices are FRONT or REAR."""
        return self._get("terminals")

    @terminals.setter
    def terminals(self, value: str) -> None:
        """Set terminals."""
        self._set("terminals", value)

    def clear_source(self) -> None:
        """Turn off the source output using :SOUR:CLE:IMM."""
        self.output_enabled = False

    @property
    def auto_output_off(self) -> bool:
        """Whether the output turns on and off automatically for measurement cycles."""
        return self._get("auto_output_off")

    @auto_output_off.setter
    def auto_output_off(self, value: bool) -> None:
        """Set auto output off."""
        self._set("auto_output_off", value)

    @property
    def auto_output_off_mode(self) -> str:
        """Automatic output-off schedule: ALWAYS or TCOUNT."""
        return self._get("auto_output_off_mode")

    @auto_output_off_mode.setter
    def auto_output_off_mode(self, value: str) -> None:
        """Set auto output off mode."""
        self._set("auto_output_off_mode", value)

    @property
    def source_delay(self) -> float:
        """Settling delay before measurement, in seconds."""
        return self._get("source_delay")

    @source_delay.setter
    def source_delay(self, value: float | str) -> None:
        """Set source delay, in seconds."""
        self._set("source_delay", value)

    @property
    def source_delay_auto(self) -> bool:
        """Whether the instrument adds its automatic source-settling delay."""
        return self._get("source_delay_auto")

    @source_delay_auto.setter
    def source_delay_auto(self, value: bool) -> None:
        """Set source delay auto."""
        self._set("source_delay_auto", value)

    @property
    def sweep_spacing(self) -> str:
        """Selected sweep spacing; documented choices are LINEAR or LOGARITHMIC."""
        return self._get("sweep_spacing")

    @sweep_spacing.setter
    def sweep_spacing(self, value: str) -> None:
        """Set sweep spacing."""
        self._set("sweep_spacing", value)

    @property
    def sweep_points(self) -> int:
        """Number of source points in a staircase sweep."""
        return self._get("sweep_points")

    @sweep_points.setter
    def sweep_points(self, value: int | str) -> None:
        """Set sweep points."""
        self._set("sweep_points", value)

    @property
    def sweep_direction(self) -> str:
        """Selected sweep direction; documented choices are UP or DOWN."""
        return self._get("sweep_direction")

    @sweep_direction.setter
    def sweep_direction(self, value: str) -> None:
        """Set sweep direction."""
        self._set("sweep_direction", value)

    @property
    def sweep_ranging(self) -> str:
        """Sweep source-ranging policy: BEST, AUTO, or FIXED."""
        return self._get("sweep_ranging")

    @sweep_ranging.setter
    def sweep_ranging(self, value: str) -> None:
        """Set sweep ranging."""
        self._set("sweep_ranging", value)

    @property
    def sweep_compliance_abort(self) -> str:
        """Sweep-abort policy on compliance: NEVER, EARLY, or LATE."""
        return self._get("sweep_compliance_abort")

    @sweep_compliance_abort.setter
    def sweep_compliance_abort(self, value: str) -> None:
        """Set sweep compliance abort."""
        self._set("sweep_compliance_abort", value)

    @property
    def sweep_soak(self) -> float:
        """Delay at the initial sweep level before measurement begins, in seconds."""
        return self._get("sweep_soak")

    @sweep_soak.setter
    def sweep_soak(self, value: float | str) -> None:
        """Set sweep soak, in seconds."""
        self._set("sweep_soak", value)

    @property
    def memory_points(self) -> int:
        """Number of source-memory locations included in a memory sweep."""
        return self._get("memory_points")

    @memory_points.setter
    def memory_points(self, value: int) -> None:
        """Set memory points."""
        self._set("memory_points", value)

    @property
    def memory_start(self) -> int:
        """First source-memory location used by a memory sweep."""
        return self._get("memory_start")

    @memory_start.setter
    def memory_start(self, value: int) -> None:
        """Set memory start."""
        self._set("memory_start", value)

    def save_memory(self, location: int) -> None:
        """Save the current memory to instrument memory.

        Parameters
        ----------
        location : int
            Source-memory location to save.
        """
        self._save(self._source_memory, location, 1, 100)

    def recall_memory(self, location: int) -> None:
        """Recall the memory from instrument memory.

        Parameters
        ----------
        location : int
            Source-memory location to recall.
        """
        self._recall(self._source_memory, location, 1, 100)

    @property
    def pulse_shape(self) -> str:
        """Source waveform: DC or PULSE; pulse mode is specific to model 2430."""
        return self._get("pulse_shape")

    @pulse_shape.setter
    def pulse_shape(self, value: str) -> None:
        """Set pulse shape."""
        self._set("pulse_shape", value)

    @property
    def pulse_width(self) -> float:
        """Pulse width, in seconds; supported by model 2430."""
        return self._get("pulse_width")

    @pulse_width.setter
    def pulse_width(self, value: float | str) -> None:
        """Set pulse width, in seconds."""
        self._set("pulse_width", value)

    @property
    def pulse_delay(self) -> float:
        """Pulse delay, in seconds; supported by model 2430."""
        return self._get("pulse_delay")

    @pulse_delay.setter
    def pulse_delay(self, value: float | str) -> None:
        """Set pulse delay, in seconds."""
        self._set("pulse_delay", value)

    @property
    def digital_bit_size(self) -> int:
        """Digital I/O port width: 3 or 4 bits, or 16 with the 2499-DIGIO option."""
        return self._get("digital_bit_size")

    @digital_bit_size.setter
    def digital_bit_size(self, value: int) -> None:
        """Set digital bit size."""
        self._set("digital_bit_size", value)

    @property
    def digital_output_pattern(self) -> int:
        """Programmed digital output bit pattern, as an integer."""
        return self._get("digital_output_pattern")

    @digital_output_pattern.setter
    def digital_output_pattern(self, value: int) -> None:
        """Set digital output pattern."""
        self._set("digital_output_pattern", value)

    @property
    def digital_output_actual(self) -> int:
        """Actual digital output bit pattern, as an integer."""
        return self.digital_output_pattern

    @property
    def digital_line4_mode(self) -> str:
        """Digital line 4 function: EOT or BUSY."""
        return self._get("digital_line4_mode")

    @digital_line4_mode.setter
    def digital_line4_mode(self, value: str) -> None:
        """Set digital line4 mode."""
        self._set("digital_line4_mode", value)

    @property
    def digital_busy_polarity(self) -> str:
        """Digital EOT/BUSY signal polarity: HI or LO."""
        return self._get("digital_busy_polarity")

    @digital_busy_polarity.setter
    def digital_busy_polarity(self, value: str) -> None:
        """Set digital busy polarity."""
        self._set("digital_busy_polarity", value)

    def clear_digital_output(self) -> None:
        """Clear all digital output lines."""
        self.digital_output_pattern = 0

    @property
    def digital_clear_auto(self) -> bool:
        """Whether digital outputs clear automatically."""
        return self._get("digital_clear_auto")

    @digital_clear_auto.setter
    def digital_clear_auto(self, value: bool) -> None:
        """Set digital clear auto."""
        self._set("digital_clear_auto", value)

    @property
    def digital_clear_delay(self) -> float:
        """Delay before automatically clearing digital outputs, in seconds."""
        return self._get("digital_clear_delay")

    @digital_clear_delay.setter
    def digital_clear_delay(self, value: float | str) -> None:
        """Set digital clear delay, in seconds."""
        self._set("digital_clear_delay", value)

    @property
    def current_compliance_minimum(self) -> float:
        """Instrument-reported minimum value for current compliance in amperes."""
        return self._limit("current_compliance", 0)

    @property
    def current_compliance_maximum(self) -> float:
        """Instrument-reported maximum value for current compliance in amperes."""
        return self._limit("current_compliance", 1)

    @property
    def current_compliance_default(self) -> float:
        """Instrument-reported default value for current compliance in amperes."""
        return self._limit("current_compliance", 2)

    @property
    def voltage_compliance_minimum(self) -> float:
        """Instrument-reported minimum value for voltage compliance in volts."""
        return self._limit("voltage_compliance", 0)

    @property
    def voltage_compliance_maximum(self) -> float:
        """Instrument-reported maximum value for voltage compliance in volts."""
        return self._limit("voltage_compliance", 1)

    @property
    def voltage_compliance_default(self) -> float:
        """Instrument-reported default value for voltage compliance in volts."""
        return self._limit("voltage_compliance", 2)

    @property
    def average_count_minimum(self) -> float:
        """Instrument-reported minimum value for average count."""
        return self._limit("average_count", 0)

    @property
    def average_count_maximum(self) -> float:
        """Instrument-reported maximum value for average count."""
        return self._limit("average_count", 1)

    @property
    def average_count_default(self) -> float:
        """Instrument-reported default value for average count."""
        return self._limit("average_count", 2)

    @property
    def voltage_protection_minimum(self) -> float:
        """Instrument-reported minimum value for voltage protection in volts."""
        return self._limit("voltage_protection", 0)

    @property
    def voltage_protection_maximum(self) -> float:
        """Instrument-reported maximum value for voltage protection in volts."""
        return self._limit("voltage_protection", 1)

    @property
    def voltage_protection_default(self) -> float:
        """Instrument-reported default value for voltage protection in volts."""
        return self._limit("voltage_protection", 2)

    @property
    def source_delay_minimum(self) -> float:
        """Instrument-reported minimum value for source delay in seconds."""
        return self._limit("source_delay", 0)

    @property
    def source_delay_maximum(self) -> float:
        """Instrument-reported maximum value for source delay in seconds."""
        return self._limit("source_delay", 1)

    @property
    def source_delay_default(self) -> float:
        """Instrument-reported default value for source delay in seconds."""
        return self._limit("source_delay", 2)

    @property
    def sweep_points_minimum(self) -> float:
        """Instrument-reported minimum value for sweep points."""
        return self._limit("sweep_points", 0)

    @property
    def sweep_points_maximum(self) -> float:
        """Instrument-reported maximum value for sweep points."""
        return self._limit("sweep_points", 1)

    @property
    def sweep_points_default(self) -> float:
        """Instrument-reported default value for sweep points."""
        return self._limit("sweep_points", 2)

    @property
    def pulse_width_minimum(self) -> float:
        """Instrument-reported minimum value for pulse width in seconds."""
        return self._limit("pulse_width", 0)

    @property
    def pulse_width_maximum(self) -> float:
        """Instrument-reported maximum value for pulse width in seconds."""
        return self._limit("pulse_width", 1)

    @property
    def pulse_width_default(self) -> float:
        """Instrument-reported default value for pulse width in seconds."""
        return self._limit("pulse_width", 2)

    @property
    def pulse_delay_minimum(self) -> float:
        """Instrument-reported minimum value for pulse delay in seconds."""
        return self._limit("pulse_delay", 0)

    @property
    def pulse_delay_maximum(self) -> float:
        """Instrument-reported maximum value for pulse delay in seconds."""
        return self._limit("pulse_delay", 1)

    @property
    def pulse_delay_default(self) -> float:
        """Instrument-reported default value for pulse delay in seconds."""
        return self._limit("pulse_delay", 2)

    @property
    def digital_clear_delay_minimum(self) -> float:
        """Instrument-reported minimum value for digital clear delay in seconds."""
        return self._limit("digital_clear_delay", 0)

    @property
    def digital_clear_delay_maximum(self) -> float:
        """Instrument-reported maximum value for digital clear delay in seconds."""
        return self._limit("digital_clear_delay", 1)

    @property
    def digital_clear_delay_default(self) -> float:
        """Instrument-reported default value for digital clear delay in seconds."""
        return self._limit("digital_clear_delay", 2)

    @property
    def source_voltage_mode(self) -> str:
        """Selected source voltage mode: FIX, SWEEP, or LIST."""
        return self._get("source_voltage_mode")

    @source_voltage_mode.setter
    def source_voltage_mode(self, value: str) -> None:
        """Set source voltage mode; choices: FIX, SWEEP, or LIST."""
        self._set("source_voltage_mode", value)

    @property
    def source_voltage_level(self) -> float:
        """Source voltage level, in volts."""
        return self._get("source_voltage_level")

    @source_voltage_level.setter
    def source_voltage_level(self, value: float | str) -> None:
        """Set source voltage level, in volts."""
        self._set("source_voltage_level", value)

    @property
    def source_voltage_range(self) -> float:
        """Source voltage range, in volts."""
        return self._get("source_voltage_range")

    @source_voltage_range.setter
    def source_voltage_range(self, value: float | str) -> None:
        """Set source voltage range, in volts."""
        self._set("source_voltage_range", value)

    @property
    def source_voltage_auto_range(self) -> bool:
        """Whether the voltage source selects its range automatically."""
        return self._get("source_voltage_auto_range")

    @source_voltage_auto_range.setter
    def source_voltage_auto_range(self, value: bool) -> None:
        """Set source voltage auto range."""
        self._set("source_voltage_auto_range", value)

    @property
    def source_voltage_start(self) -> float:
        """Staircase voltage sweep starting level, in volts."""
        return self._get("source_voltage_start")

    @source_voltage_start.setter
    def source_voltage_start(self, value: float | str) -> None:
        """Set source voltage start, in volts."""
        self._set("source_voltage_start", value)

    @property
    def source_voltage_stop(self) -> float:
        """Staircase voltage sweep ending level, in volts."""
        return self._get("source_voltage_stop")

    @source_voltage_stop.setter
    def source_voltage_stop(self, value: float | str) -> None:
        """Set source voltage stop, in volts."""
        self._set("source_voltage_stop", value)

    @property
    def source_voltage_step(self) -> float:
        """Staircase voltage sweep step size, in volts."""
        return self._get("source_voltage_step")

    @source_voltage_step.setter
    def source_voltage_step(self, value: float | str) -> None:
        """Set source voltage step, in volts."""
        self._set("source_voltage_step", value)

    @property
    def source_voltage_center(self) -> float:
        """Staircase voltage sweep center level, in volts."""
        return self._get("source_voltage_center")

    @source_voltage_center.setter
    def source_voltage_center(self, value: float | str) -> None:
        """Set source voltage center, in volts."""
        self._set("source_voltage_center", value)

    @property
    def source_voltage_span(self) -> float:
        """Staircase voltage sweep span, in volts."""
        return self._get("source_voltage_span")

    @source_voltage_span.setter
    def source_voltage_span(self, value: float | str) -> None:
        """Set source voltage span, in volts."""
        self._set("source_voltage_span", value)

    @property
    def source_voltage_triggered_level(self) -> float:
        """Voltage level applied on a source trigger, in volts."""
        return self._get("source_voltage_triggered_level")

    @source_voltage_triggered_level.setter
    def source_voltage_triggered_level(self, value: float | str) -> None:
        """Set source voltage triggered level, in volts."""
        self._set("source_voltage_triggered_level", value)

    @property
    def source_voltage_scaling_factor(self) -> float:
        """Dimensionless scaling factor applied to triggered voltage source levels."""
        return self._get("source_voltage_scaling_factor")

    @source_voltage_scaling_factor.setter
    def source_voltage_scaling_factor(self, value: float | str) -> None:
        """Set the dimensionless scaling factor for triggered source levels."""
        self._set("source_voltage_scaling_factor", value)

    @property
    def source_voltage_scaling_enabled(self) -> bool:
        """Whether triggered voltage source scaling is enabled."""
        return self._get("source_voltage_scaling_enabled")

    @source_voltage_scaling_enabled.setter
    def source_voltage_scaling_enabled(self, value: bool) -> None:
        """Set source voltage scaling enabled."""
        self._set("source_voltage_scaling_enabled", value)

    @property
    def source_voltage_list_values(self) -> tuple[float, ...]:
        """Voltage source list values as a tuple, in volts; setters accept a sequence."""
        return self._get("source_voltage_list_values")

    @source_voltage_list_values.setter
    def source_voltage_list_values(self, values: Sequence[float]) -> None:
        """Set source voltage list values, in volts."""
        self._set("source_voltage_list_values", values)

    def append_source_voltage_list(self, values: Sequence[float]) -> None:
        """Append values to the instrument's source voltage list.

        Parameters
        ----------
        values : Sequence[float]
            Voltage values to append, in volts.
        """
        self._append_list("voltage", values)

    @property
    def source_voltage_list_points(self) -> int:
        """Number of entries in the voltage source list."""
        return len(self.source_voltage_list_values)

    @property
    def source_voltage_list_start(self) -> int:
        """First point index used in the voltage source list."""
        return self._get("source_voltage_list_start")

    @source_voltage_list_start.setter
    def source_voltage_list_start(self, value: int | str) -> None:
        """Set the first point index used in the source list."""
        self._set("source_voltage_list_start", value)

    @property
    def source_voltage_level_minimum(self) -> float:
        """Instrument-reported minimum value for source voltage level in volts."""
        return self._limit("source_voltage_level", 0)

    @property
    def source_voltage_level_maximum(self) -> float:
        """Instrument-reported maximum value for source voltage level in volts."""
        return self._limit("source_voltage_level", 1)

    @property
    def source_voltage_level_default(self) -> float:
        """Instrument-reported default value for source voltage level in volts."""
        return self._limit("source_voltage_level", 2)

    @property
    def source_voltage_range_minimum(self) -> float:
        """Instrument-reported minimum value for source voltage range in volts."""
        return self._limit("source_voltage_range", 0)

    @property
    def source_voltage_range_maximum(self) -> float:
        """Instrument-reported maximum value for source voltage range in volts."""
        return self._limit("source_voltage_range", 1)

    @property
    def source_voltage_range_default(self) -> float:
        """Instrument-reported default value for source voltage range in volts."""
        return self._limit("source_voltage_range", 2)

    @property
    def source_voltage_triggered_level_minimum(self) -> float:
        """Instrument-reported minimum value for source voltage triggered level in
        volts.
        """
        return self._limit("source_voltage_triggered_level", 0)

    @property
    def source_voltage_triggered_level_maximum(self) -> float:
        """Instrument-reported maximum value for source voltage triggered level in
        volts.
        """
        return self._limit("source_voltage_triggered_level", 1)

    @property
    def source_voltage_triggered_level_default(self) -> float:
        """Instrument-reported default value for source voltage triggered level in
        volts.
        """
        return self._limit("source_voltage_triggered_level", 2)

    @property
    def source_voltage_start_minimum(self) -> float:
        """Instrument-reported minimum value for source voltage start in volts."""
        return self._limit("source_voltage_start", 0)

    @property
    def source_voltage_start_maximum(self) -> float:
        """Instrument-reported maximum value for source voltage start in volts."""
        return self._limit("source_voltage_start", 1)

    @property
    def source_voltage_start_default(self) -> float:
        """Instrument-reported default value for source voltage start in volts."""
        return self._limit("source_voltage_start", 2)

    @property
    def source_voltage_stop_minimum(self) -> float:
        """Instrument-reported minimum value for source voltage stop in volts."""
        return self._limit("source_voltage_stop", 0)

    @property
    def source_voltage_stop_maximum(self) -> float:
        """Instrument-reported maximum value for source voltage stop in volts."""
        return self._limit("source_voltage_stop", 1)

    @property
    def source_voltage_stop_default(self) -> float:
        """Instrument-reported default value for source voltage stop in volts."""
        return self._limit("source_voltage_stop", 2)

    @property
    def source_voltage_center_minimum(self) -> float:
        """Instrument-reported minimum value for source voltage center in volts."""
        return self._limit("source_voltage_center", 0)

    @property
    def source_voltage_center_maximum(self) -> float:
        """Instrument-reported maximum value for source voltage center in volts."""
        return self._limit("source_voltage_center", 1)

    @property
    def source_voltage_center_default(self) -> float:
        """Instrument-reported default value for source voltage center in volts."""
        return self._limit("source_voltage_center", 2)

    @property
    def source_voltage_span_minimum(self) -> float:
        """Instrument-reported minimum value for source voltage span in volts."""
        return self._limit("source_voltage_span", 0)

    @property
    def source_voltage_span_maximum(self) -> float:
        """Instrument-reported maximum value for source voltage span in volts."""
        return self._limit("source_voltage_span", 1)

    @property
    def source_voltage_span_default(self) -> float:
        """Instrument-reported default value for source voltage span in volts."""
        return self._limit("source_voltage_span", 2)

    @property
    def source_voltage_step_minimum(self) -> float:
        """Instrument-reported minimum value for source voltage step in volts."""
        return self._limit("source_voltage_step", 0)

    @property
    def source_voltage_step_maximum(self) -> float:
        """Instrument-reported maximum value for source voltage step in volts."""
        return self._limit("source_voltage_step", 1)

    @property
    def source_voltage_step_default(self) -> float:
        """Instrument-reported default value for source voltage step in volts."""
        return self._limit("source_voltage_step", 2)

    @property
    def source_current_mode(self) -> str:
        """Selected source current mode: FIX, SWEEP, or LIST."""
        return self._get("source_current_mode")

    @source_current_mode.setter
    def source_current_mode(self, value: str) -> None:
        """Set source current mode; choices: FIX, SWEEP, or LIST."""
        self._set("source_current_mode", value)

    @property
    def source_current_level(self) -> float:
        """Source current level, in amperes."""
        return self._get("source_current_level")

    @source_current_level.setter
    def source_current_level(self, value: float | str) -> None:
        """Set source current level, in amperes."""
        self._set("source_current_level", value)

    @property
    def source_current_range(self) -> float:
        """Source current range, in amperes."""
        return self._get("source_current_range")

    @source_current_range.setter
    def source_current_range(self, value: float | str) -> None:
        """Set source current range, in amperes."""
        self._set("source_current_range", value)

    @property
    def source_current_auto_range(self) -> bool:
        """Whether the current source selects its range automatically."""
        return self._get("source_current_auto_range")

    @source_current_auto_range.setter
    def source_current_auto_range(self, value: bool) -> None:
        """Set source current auto range."""
        self._set("source_current_auto_range", value)

    @property
    def source_current_start(self) -> float:
        """Staircase current sweep starting level, in amperes."""
        return self._get("source_current_start")

    @source_current_start.setter
    def source_current_start(self, value: float | str) -> None:
        """Set source current start, in amperes."""
        self._set("source_current_start", value)

    @property
    def source_current_stop(self) -> float:
        """Staircase current sweep ending level, in amperes."""
        return self._get("source_current_stop")

    @source_current_stop.setter
    def source_current_stop(self, value: float | str) -> None:
        """Set source current stop, in amperes."""
        self._set("source_current_stop", value)

    @property
    def source_current_step(self) -> float:
        """Staircase current sweep step size, in amperes."""
        return self._get("source_current_step")

    @source_current_step.setter
    def source_current_step(self, value: float | str) -> None:
        """Set source current step, in amperes."""
        self._set("source_current_step", value)

    @property
    def source_current_center(self) -> float:
        """Staircase current sweep center level, in amperes."""
        return self._get("source_current_center")

    @source_current_center.setter
    def source_current_center(self, value: float | str) -> None:
        """Set source current center, in amperes."""
        self._set("source_current_center", value)

    @property
    def source_current_span(self) -> float:
        """Staircase current sweep span, in amperes."""
        return self._get("source_current_span")

    @source_current_span.setter
    def source_current_span(self, value: float | str) -> None:
        """Set source current span, in amperes."""
        self._set("source_current_span", value)

    @property
    def source_current_triggered_level(self) -> float:
        """Current level applied on a source trigger, in amperes."""
        return self._get("source_current_triggered_level")

    @source_current_triggered_level.setter
    def source_current_triggered_level(self, value: float | str) -> None:
        """Set source current triggered level, in amperes."""
        self._set("source_current_triggered_level", value)

    @property
    def source_current_scaling_factor(self) -> float:
        """Dimensionless scaling factor applied to triggered current source levels."""
        return self._get("source_current_scaling_factor")

    @source_current_scaling_factor.setter
    def source_current_scaling_factor(self, value: float | str) -> None:
        """Set the dimensionless scaling factor for triggered source levels."""
        self._set("source_current_scaling_factor", value)

    @property
    def source_current_scaling_enabled(self) -> bool:
        """Whether triggered current source scaling is enabled."""
        return self._get("source_current_scaling_enabled")

    @source_current_scaling_enabled.setter
    def source_current_scaling_enabled(self, value: bool) -> None:
        """Set source current scaling enabled."""
        self._set("source_current_scaling_enabled", value)

    @property
    def source_current_list_values(self) -> tuple[float, ...]:
        """Current source list values as a tuple, in amperes; setters accept a
        sequence.
        """
        return self._get("source_current_list_values")

    @source_current_list_values.setter
    def source_current_list_values(self, values: Sequence[float]) -> None:
        """Set source current list values, in amperes."""
        self._set("source_current_list_values", values)

    def append_source_current_list(self, values: Sequence[float]) -> None:
        """Append values to the instrument's source current list.

        Parameters
        ----------
        values : Sequence[float]
            Current values to append, in amperes.
        """
        self._append_list("current", values)

    @property
    def source_current_list_points(self) -> int:
        """Number of entries in the current source list."""
        return len(self.source_current_list_values)

    @property
    def source_current_list_start(self) -> int:
        """First point index used in the current source list."""
        return self._get("source_current_list_start")

    @source_current_list_start.setter
    def source_current_list_start(self, value: int | str) -> None:
        """Set the first point index used in the source list."""
        self._set("source_current_list_start", value)

    @property
    def source_current_level_minimum(self) -> float:
        """Instrument-reported minimum value for source current level in amperes."""
        return self._limit("source_current_level", 0)

    @property
    def source_current_level_maximum(self) -> float:
        """Instrument-reported maximum value for source current level in amperes."""
        return self._limit("source_current_level", 1)

    @property
    def source_current_level_default(self) -> float:
        """Instrument-reported default value for source current level in amperes."""
        return self._limit("source_current_level", 2)

    @property
    def source_current_range_minimum(self) -> float:
        """Instrument-reported minimum value for source current range in amperes."""
        return self._limit("source_current_range", 0)

    @property
    def source_current_range_maximum(self) -> float:
        """Instrument-reported maximum value for source current range in amperes."""
        return self._limit("source_current_range", 1)

    @property
    def source_current_range_default(self) -> float:
        """Instrument-reported default value for source current range in amperes."""
        return self._limit("source_current_range", 2)

    @property
    def source_current_triggered_level_minimum(self) -> float:
        """Instrument-reported minimum value for source current triggered level in
        amperes.
        """
        return self._limit("source_current_triggered_level", 0)

    @property
    def source_current_triggered_level_maximum(self) -> float:
        """Instrument-reported maximum value for source current triggered level in
        amperes.
        """
        return self._limit("source_current_triggered_level", 1)

    @property
    def source_current_triggered_level_default(self) -> float:
        """Instrument-reported default value for source current triggered level in
        amperes.
        """
        return self._limit("source_current_triggered_level", 2)

    @property
    def source_current_start_minimum(self) -> float:
        """Instrument-reported minimum value for source current start in amperes."""
        return self._limit("source_current_start", 0)

    @property
    def source_current_start_maximum(self) -> float:
        """Instrument-reported maximum value for source current start in amperes."""
        return self._limit("source_current_start", 1)

    @property
    def source_current_start_default(self) -> float:
        """Instrument-reported default value for source current start in amperes."""
        return self._limit("source_current_start", 2)

    @property
    def source_current_stop_minimum(self) -> float:
        """Instrument-reported minimum value for source current stop in amperes."""
        return self._limit("source_current_stop", 0)

    @property
    def source_current_stop_maximum(self) -> float:
        """Instrument-reported maximum value for source current stop in amperes."""
        return self._limit("source_current_stop", 1)

    @property
    def source_current_stop_default(self) -> float:
        """Instrument-reported default value for source current stop in amperes."""
        return self._limit("source_current_stop", 2)

    @property
    def source_current_center_minimum(self) -> float:
        """Instrument-reported minimum value for source current center in amperes."""
        return self._limit("source_current_center", 0)

    @property
    def source_current_center_maximum(self) -> float:
        """Instrument-reported maximum value for source current center in amperes."""
        return self._limit("source_current_center", 1)

    @property
    def source_current_center_default(self) -> float:
        """Instrument-reported default value for source current center in amperes."""
        return self._limit("source_current_center", 2)

    @property
    def source_current_span_minimum(self) -> float:
        """Instrument-reported minimum value for source current span in amperes."""
        return self._limit("source_current_span", 0)

    @property
    def source_current_span_maximum(self) -> float:
        """Instrument-reported maximum value for source current span in amperes."""
        return self._limit("source_current_span", 1)

    @property
    def source_current_span_default(self) -> float:
        """Instrument-reported default value for source current span in amperes."""
        return self._limit("source_current_span", 2)

    @property
    def source_current_step_minimum(self) -> float:
        """Instrument-reported minimum value for source current step in amperes."""
        return self._limit("source_current_step", 0)

    @property
    def source_current_step_maximum(self) -> float:
        """Instrument-reported maximum value for source current step in amperes."""
        return self._limit("source_current_step", 1)

    @property
    def source_current_step_default(self) -> float:
        """Instrument-reported default value for source current step in amperes."""
        return self._limit("source_current_step", 2)

    @property
    def sense_voltage_range(self) -> float:
        """Voltage measurement range, in volts."""
        return self._get("sense_voltage_range")

    @sense_voltage_range.setter
    def sense_voltage_range(self, value: float | str) -> None:
        """Set sense voltage range, in volts."""
        self._set("sense_voltage_range", value)

    @property
    def sense_voltage_auto_range(self) -> bool:
        """Whether voltage measurement autoranging is enabled."""
        return self._get("sense_voltage_auto_range")

    @sense_voltage_auto_range.setter
    def sense_voltage_auto_range(self, value: bool) -> None:
        """Set sense voltage auto range."""
        self._set("sense_voltage_auto_range", value)

    @property
    def sense_voltage_range_upper_limit(self) -> float:
        """Upper voltage measurement autorange bound, in volts."""
        return self._limit("sense_voltage_range_upper_limit", 2)

    @property
    def sense_voltage_range_lower_limit(self) -> float:
        """Lower voltage measurement autorange bound, in volts."""
        return self._get("sense_voltage_range_lower_limit")

    @sense_voltage_range_lower_limit.setter
    def sense_voltage_range_lower_limit(self, value: float | str) -> None:
        """Set sense voltage range lower limit, in volts."""
        self._set("sense_voltage_range_lower_limit", value)

    @property
    def sense_voltage_nplc(self) -> float:
        """Integration time, in power-line cycles; this setting is shared by all
        measurement functions.
        """
        return self._get("sense_voltage_nplc")

    @sense_voltage_nplc.setter
    def sense_voltage_nplc(self, value: float | str) -> None:
        """Set sense voltage nplc, in power-line cycles."""
        self._set("sense_voltage_nplc", value)

    @property
    def sense_voltage_range_minimum(self) -> float:
        """Instrument-reported minimum value for sense voltage range in volts."""
        return self._limit("sense_voltage_range", 0)

    @property
    def sense_voltage_range_maximum(self) -> float:
        """Instrument-reported maximum value for sense voltage range in volts."""
        return self._limit("sense_voltage_range", 1)

    @property
    def sense_voltage_range_default(self) -> float:
        """Instrument-reported default value for sense voltage range in volts."""
        return self._limit("sense_voltage_range", 2)

    @property
    def sense_voltage_nplc_minimum(self) -> float:
        """Instrument-reported minimum value for sense voltage NPLC in power-line
        cycles.
        """
        return self._limit("sense_voltage_nplc", 0)

    @property
    def sense_voltage_nplc_maximum(self) -> float:
        """Instrument-reported maximum value for sense voltage NPLC in power-line
        cycles.
        """
        return self._limit("sense_voltage_nplc", 1)

    @property
    def sense_voltage_nplc_default(self) -> float:
        """Instrument-reported default value for sense voltage NPLC in power-line
        cycles.
        """
        return self._limit("sense_voltage_nplc", 2)

    @property
    def sense_current_range(self) -> float:
        """Current measurement range, in amperes."""
        return self._get("sense_current_range")

    @sense_current_range.setter
    def sense_current_range(self, value: float | str) -> None:
        """Set sense current range, in amperes."""
        self._set("sense_current_range", value)

    @property
    def sense_current_auto_range(self) -> bool:
        """Whether current measurement autoranging is enabled."""
        return self._get("sense_current_auto_range")

    @sense_current_auto_range.setter
    def sense_current_auto_range(self, value: bool) -> None:
        """Set sense current auto range."""
        self._set("sense_current_auto_range", value)

    @property
    def sense_current_range_upper_limit(self) -> float:
        """Upper current measurement autorange bound, in amperes."""
        return self._limit("sense_current_range_upper_limit", 2)

    @property
    def sense_current_range_lower_limit(self) -> float:
        """Lower current measurement autorange bound, in amperes."""
        return self._get("sense_current_range_lower_limit")

    @sense_current_range_lower_limit.setter
    def sense_current_range_lower_limit(self, value: float | str) -> None:
        """Set sense current range lower limit, in amperes."""
        self._set("sense_current_range_lower_limit", value)

    @property
    def sense_current_nplc(self) -> float:
        """Integration time, in power-line cycles; this setting is shared by all
        measurement functions.
        """
        return self.sense_voltage_nplc

    @sense_current_nplc.setter
    def sense_current_nplc(self, value: float | str) -> None:
        """Set sense current nplc, in power-line cycles."""
        self.sense_voltage_nplc = value

    @property
    def sense_current_range_holdoff(self) -> bool:
        """Whether current measurement range changes are delayed during source-memory
        sweeps.
        """
        return self._get("sense_current_range_holdoff")

    @sense_current_range_holdoff.setter
    def sense_current_range_holdoff(self, value: bool) -> None:
        """Set sense current range holdoff."""
        self._set("sense_current_range_holdoff", value)

    @property
    def sense_current_range_holdoff_delay(self) -> float:
        """Current measurement range-change holdoff interval, in seconds."""
        return self._get("sense_current_range_holdoff_delay")

    @sense_current_range_holdoff_delay.setter
    def sense_current_range_holdoff_delay(self, value: float | str) -> None:
        """Set sense current range holdoff delay, in seconds."""
        self._set("sense_current_range_holdoff_delay", value)

    @property
    def sense_current_range_minimum(self) -> float:
        """Instrument-reported minimum value for sense current range in amperes."""
        return self._limit("sense_current_range", 0)

    @property
    def sense_current_range_maximum(self) -> float:
        """Instrument-reported maximum value for sense current range in amperes."""
        return self._limit("sense_current_range", 1)

    @property
    def sense_current_range_default(self) -> float:
        """Instrument-reported default value for sense current range in amperes."""
        return self._limit("sense_current_range", 2)

    @property
    def sense_current_nplc_minimum(self) -> float:
        """Instrument-reported minimum value for sense current NPLC in power-line
        cycles.
        """
        return self._limit("sense_current_nplc", 0)

    @property
    def sense_current_nplc_maximum(self) -> float:
        """Instrument-reported maximum value for sense current NPLC in power-line
        cycles.
        """
        return self._limit("sense_current_nplc", 1)

    @property
    def sense_current_nplc_default(self) -> float:
        """Instrument-reported default value for sense current NPLC in power-line
        cycles.
        """
        return self._limit("sense_current_nplc", 2)

    @property
    def sense_resistance_range(self) -> float:
        """Resistance measurement range, in ohms."""
        return self._get("sense_resistance_range")

    @sense_resistance_range.setter
    def sense_resistance_range(self, value: float | str) -> None:
        """Set sense resistance range, in ohms."""
        self._set("sense_resistance_range", value)

    @property
    def sense_resistance_auto_range(self) -> bool:
        """Whether resistance measurement autoranging is enabled."""
        return self._get("sense_resistance_auto_range")

    @sense_resistance_auto_range.setter
    def sense_resistance_auto_range(self, value: bool) -> None:
        """Set sense resistance auto range."""
        self._set("sense_resistance_auto_range", value)

    @property
    def sense_resistance_range_upper_limit(self) -> float:
        """Upper resistance measurement autorange bound, in ohms."""
        return self._get("sense_resistance_range_upper_limit")

    @sense_resistance_range_upper_limit.setter
    def sense_resistance_range_upper_limit(self, value: float | str) -> None:
        """Set sense resistance range upper limit, in ohms."""
        self._set("sense_resistance_range_upper_limit", value)

    @property
    def sense_resistance_range_lower_limit(self) -> float:
        """Lower resistance measurement autorange bound, in ohms."""
        return self._get("sense_resistance_range_lower_limit")

    @sense_resistance_range_lower_limit.setter
    def sense_resistance_range_lower_limit(self, value: float | str) -> None:
        """Set sense resistance range lower limit, in ohms."""
        self._set("sense_resistance_range_lower_limit", value)

    @property
    def sense_resistance_nplc(self) -> float:
        """Integration time, in power-line cycles; this setting is shared by all
        measurement functions.
        """
        return self.sense_voltage_nplc

    @sense_resistance_nplc.setter
    def sense_resistance_nplc(self, value: float | str) -> None:
        """Set sense resistance nplc, in power-line cycles."""
        self.sense_voltage_nplc = value

    @property
    def sense_resistance_range_minimum(self) -> float:
        """Instrument-reported minimum value for sense resistance range in ohms."""
        return self._limit("sense_resistance_range", 0)

    @property
    def sense_resistance_range_maximum(self) -> float:
        """Instrument-reported maximum value for sense resistance range in ohms."""
        return self._limit("sense_resistance_range", 1)

    @property
    def sense_resistance_range_default(self) -> float:
        """Instrument-reported default value for sense resistance range in ohms."""
        return self._limit("sense_resistance_range", 2)

    @property
    def sense_resistance_nplc_minimum(self) -> float:
        """Instrument-reported minimum value for sense resistance NPLC in power-line
        cycles.
        """
        return self._limit("sense_resistance_nplc", 0)

    @property
    def sense_resistance_nplc_maximum(self) -> float:
        """Instrument-reported maximum value for sense resistance NPLC in power-line
        cycles.
        """
        return self._limit("sense_resistance_nplc", 1)

    @property
    def sense_resistance_nplc_default(self) -> float:
        """Instrument-reported default value for sense resistance NPLC in power-line
        cycles.
        """
        return self._limit("sense_resistance_nplc", 2)

    @property
    def limit_feed(self) -> str:
        """Measurement limit-test input: CALC, VOLT, CURR, or RES."""
        return self._get("limit_feed")

    @limit_feed.setter
    def limit_feed(self, value: str) -> None:
        """Set limit feed."""
        self._set("limit_feed", value)

    @property
    def limit_data(self) -> tuple[float, ...]:
        """CALC2 relative/limit-test feed values for the completed sequence, as a flat
        tuple of floats.

        The selected format and elements determine the reply layout. Instrument
        overflow and unavailable-value sentinels are preserved.
        """
        self._verify_connected()
        return self._format(
            [{**row, "CALC": self._feed_value(row)} for row in self._readings], True
        )

    @property
    def limit_latest(self) -> tuple[float, ...]:
        """Latest CALC2 relative/limit-test feed values, as a flat tuple of floats.

        The selected format and elements determine the reply layout. Instrument
        overflow and unavailable-value sentinels are preserved.
        """
        self._verify_connected()
        return self._format(
            [{**row, "CALC": self._feed_value(row)} for row in self._readings[-1:]],
            True,
        )

    @property
    def display_enabled(self) -> bool:
        """Whether display is enabled."""
        return self._get("display_enabled")

    @display_enabled.setter
    def display_enabled(self, value: bool) -> None:
        """Set display enabled."""
        self._set("display_enabled", value)

    def display_source_measure(self) -> None:
        """Return the display to its normal source/measurement presentation."""
        self._verify_connected()
        self._settings["display_top_text_enabled"] = False
        self._settings["display_bottom_text_enabled"] = False
        self._finish_write()

    @property
    def display_digits(self) -> int:
        """Number of displayed measurement digits (4–7)."""
        return self._get("display_digits")

    @display_digits.setter
    def display_digits(self, value: int | str) -> None:
        """Set display digits."""
        self._set("display_digits", value)

    def preset_status(self) -> None:
        """Restore status-register enable masks with :STAT:PRES; preserve the error
        queue.
        """
        self._verify_connected()
        for group in self._events:
            self._settings[group + "_status_enable"] = 0
        self._finish_write()

    @property
    def error_queue_enabled(self) -> str:
        """Raw list of error/status codes enabled for inclusion in the error queue."""
        return self._code_string(True)

    @error_queue_enabled.setter
    def error_queue_enabled(self, value: str | Sequence[int]) -> None:
        """Set error queue enabled."""
        self._set("error_queue_enabled", value)

    @property
    def error_queue_disabled(self) -> str:
        """Raw list of error/status codes excluded from the error queue."""
        return self._code_string(False)

    @error_queue_disabled.setter
    def error_queue_disabled(self, value: str | Sequence[int]) -> None:
        """Set error queue disabled."""
        self._set("error_queue_disabled", value)

    def read_status_error(self) -> str:
        """Read and remove the oldest status/error queue entry with :STAT:QUE?.

        Returns
        -------
        str
            Raw code and message; this consumes the same queue as read_error().
        """
        return self.read_error()

    def clear_status_errors(self) -> None:
        """Remove all entries from the status/error queue."""
        self._verify_connected()
        self._errors.clear()
        self._finish_write()

    @property
    def display_digits_minimum(self) -> float:
        """Instrument-reported minimum value for display digits."""
        return self._limit("display_digits", 0)

    @property
    def display_digits_maximum(self) -> float:
        """Instrument-reported maximum value for display digits."""
        return self._limit("display_digits", 1)

    @property
    def display_digits_default(self) -> float:
        """Instrument-reported default value for display digits."""
        return self._limit("display_digits", 2)

    @property
    def math_catalog(self) -> str:
        """Raw catalog of built-in and user-defined math expression names."""
        self._verify_connected()
        return ",".join(f'"{name}"' for name in self._math)

    @property
    def math_name(self) -> str:
        """Selected math expression name.

        Built-in names include POWER, OFFCOMPOHM, VOLTCOEF, and VARALPHA. Custom
        names may contain up to 10 ASCII characters.
        """
        return self._get("math_name")

    @math_name.setter
    def math_name(self, value: str) -> None:
        """Set math name."""
        self._set("math_name", value)

    @property
    def math_expression(self) -> str:
        """Selected math expression as raw instrument text; setters accept an
        expression string.
        """
        self._verify_connected()
        return self._math[self._settings["math_name"]][0]

    @math_expression.setter
    def math_expression(self, value: str) -> None:
        """Define the selected custom math expression using documented arithmetic."""
        self._verify_connected()
        name = self._settings["math_name"]
        if name in _BUILTIN_MATH:
            self._error(807, "Definition not allowed")
            return
        try:
            tree = ast.parse(value.replace("^", "**"), mode="eval")
            if len(value) > 256:
                raise ValueError("expression too long")
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.Expression, ast.Load, ast.operator, ast.unaryop)
                ):
                    continue
                if isinstance(node, ast.BinOp) and isinstance(
                    node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
                ):
                    continue
                if isinstance(node, ast.UnaryOp) and isinstance(
                    node.op, (ast.UAdd, ast.USub)
                ):
                    continue
                if isinstance(node, ast.Constant) and isinstance(
                    node.value, (int, float)
                ):
                    continue
                if isinstance(node, ast.Name):
                    if node.id.upper() in ("LOG", "LN", "SIN", "COS", "TAN", "EXP"):
                        continue
                    self._enum(node.id, ("VOLTage", "CURRent", "RESistance", "TIME"))
                    continue
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id.upper()
                    in ("LOG", "LN", "SIN", "COS", "TAN", "EXP")
                    and len(node.args) == 1
                    and not node.keywords
                ):
                    continue
                if (
                    isinstance(node, ast.Subscript)
                    and isinstance(node.value, ast.Name)
                    and isinstance(node.slice, ast.Constant)
                    and isinstance(node.slice.value, int)
                    and node.slice.value >= 0
                ):
                    continue
                raise ValueError("invalid expression")
        except (ValueError, SyntaxError):
            self._error(813, "Not a number or data handle")
            return
        self._math[name] = (value, self._math[name][1])
        self._finish_write()

    @property
    def math_units(self) -> str:
        """User-defined math-result unit label, up to three ASCII characters."""
        self._verify_connected()
        return self._math[self._settings["math_name"]][1]

    @math_units.setter
    def math_units(self, value: str) -> None:
        """Set math units."""
        self._verify_connected()
        if len(value) > 3:
            self._error(-222, "Parameter data out of range")
            return
        name = self._settings["math_name"]
        self._math[name] = (self._math[name][0], value)
        self._finish_write()

    @property
    def math_enabled(self) -> bool:
        """Whether CALC1 math processing is enabled."""
        return self._get("math_enabled")

    @math_enabled.setter
    def math_enabled(self, value: bool) -> None:
        """Set math enabled."""
        self._set("math_enabled", value)

    @property
    def math_data(self) -> tuple[float, ...]:
        """CALC1 math results for the completed sequence, as a flat tuple of floats.

        The selected format and elements determine the reply layout. Instrument
        overflow and unavailable-value sentinels are preserved.
        """
        self._verify_connected()
        return self._format(self._calculation_rows(), True)

    @property
    def math_latest(self) -> tuple[float, ...]:
        """Latest CALC1 math result, as a flat tuple of floats.

        The selected format and elements determine the reply layout. Instrument
        overflow and unavailable-value sentinels are preserved.
        """
        return self._format(self._calculation_rows()[-1:], True)

    def delete_math_expression(self, name: str) -> None:
        """Delete the math expression from instrument memory.

        Parameters
        ----------
        name : str
            Custom expression name to delete.
        """
        self._verify_connected()
        name = name.upper()
        if name not in self._math or name in _BUILTIN_MATH:
            self._error(
                808 if name in _BUILTIN_MATH else 806,
                "Expression cannot be deleted"
                if name in _BUILTIN_MATH
                else "Expression not found",
            )
            return
        del self._math[name]
        if self._settings["math_name"] == name:
            self._settings["math_name"] = "POWER"
        self._finish_write()

    def delete_all_math_expressions(self) -> None:
        """Delete all user-defined math expressions from instrument memory."""
        self._verify_connected()
        self._math = dict(_BUILTIN_MATH)
        self._settings["math_name"] = "POWER"
        self._finish_write()

    @property
    def relative_offset(self) -> float:
        """Offset subtracted from the selected limit-test feed, in that feed's units."""
        return self._get("relative_offset")

    @relative_offset.setter
    def relative_offset(self, value: float) -> None:
        """Set relative offset."""
        self._set("relative_offset", value)

    @property
    def relative_enabled(self) -> bool:
        """Whether relative-offset subtraction is enabled for the limit-test feed."""
        return self._get("relative_enabled")

    @relative_enabled.setter
    def relative_enabled(self, value: bool) -> None:
        """Set relative enabled."""
        self._set("relative_enabled", value)

    def acquire_relative(self) -> None:
        """Acquire a relative offset from the current feed reading.

        If no reading is available, the instrument uses the next available reading.
        """
        self._verify_connected()
        if not self._readings:
            self._error(-230, "Data corrupt or stale")
            return
        row = self._readings[-1]
        name = self._settings["limit_feed"]
        self._settings["relative_offset"] = (
            self._math_value(row) if name == "CALC" else row[name]
        )
        self._finish_write()

    @property
    def composite_limit_pass_pattern(self) -> int:
        """Digital output bit pattern used for composite measurement-test pass
        results.
        """
        return self._get("composite_limit_pass_pattern")

    @composite_limit_pass_pattern.setter
    def composite_limit_pass_pattern(self, value: int | str) -> None:
        """Set composite limit pass pattern."""
        self._set("composite_limit_pass_pattern", value)

    @property
    def composite_limit_fail_pattern(self) -> int:
        """Digital output bit pattern used for composite measurement-test fail
        results.
        """
        return self._get("composite_limit_fail_pattern")

    @composite_limit_fail_pattern.setter
    def composite_limit_fail_pattern(self, value: int | str) -> None:
        """Set composite limit fail pattern."""
        self._set("composite_limit_fail_pattern", value)

    @property
    def composite_limit_pass_memory_location(self) -> str:
        """Next source-memory location on a composite pass: location text or NEXT."""
        return self._get("composite_limit_pass_memory_location")

    @composite_limit_pass_memory_location.setter
    def composite_limit_pass_memory_location(self, value: int | str) -> None:
        """Set composite limit pass memory location."""
        self._set("composite_limit_pass_memory_location", value)

    @property
    def composite_limit_fail_memory_location(self) -> str:
        """Next source-memory location on a composite failure: location text or NEXT."""
        return self._get("composite_limit_fail_memory_location")

    @composite_limit_fail_memory_location.setter
    def composite_limit_fail_memory_location(self, value: int | str) -> None:
        """Set composite limit fail memory location."""
        self._set("composite_limit_fail_memory_location", value)

    @property
    def composite_limit_mode(self) -> str:
        """Digital pass/fail interpretation for composite measurement limit tests."""
        return self._get("composite_limit_mode")

    @composite_limit_mode.setter
    def composite_limit_mode(self, value: str) -> None:
        """Set composite limit mode."""
        self._set("composite_limit_mode", value)

    @property
    def composite_limit_bin_control(self) -> str:
        """When digital pass/fail outputs update: IMMEDIATE or END."""
        return self._get("composite_limit_bin_control")

    @composite_limit_bin_control.setter
    def composite_limit_bin_control(self, value: str) -> None:
        """Set composite limit bin control."""
        self._set("composite_limit_bin_control", value)

    @property
    def composite_limit_auto_clear(self) -> bool:
        """Whether measurement limit-test failure indications clear automatically."""
        return self._get("composite_limit_auto_clear")

    @composite_limit_auto_clear.setter
    def composite_limit_auto_clear(self, value: bool) -> None:
        """Set composite limit auto clear."""
        self._set("composite_limit_auto_clear", value)

    def clear_composite_limits(self) -> None:
        """Clear composite measurement limit-test results."""
        self._verify_connected()
        self._clear_limit_flags()
        self._finish_write()

    @property
    def statistics_function(self) -> str:
        """Selected statistics function; documented choices are MEAN, SDEVIATION,
        MAXIMUM, MINIMUM, or PKPK.
        """
        return self._get("statistics_function")

    @statistics_function.setter
    def statistics_function(self, value: str) -> None:
        """Set statistics function."""
        self._set("statistics_function", value)

    @property
    def statistics_data(self) -> tuple[float, ...]:
        """Selected statistic of stored deterministic reading values, or an empty tuple."""
        self._verify_connected()
        if not self._trace:
            return ()
        key = self._settings["statistics_function"]
        values = [
            row["CALC"]
            if self._settings["trace_feed"] in ("CALC", "CALC2")
            else self._feed_value(row)
            for row in self._trace
        ]
        if key == "MEAN":
            value = mean(values)
        elif key == "SDEV":
            value = stdev(values) if len(values) > 1 else 0.0
        elif key == "MAX":
            value = max(values)
        elif key == "MIN":
            value = min(values)
        else:
            value = max(values) - min(values)
        return (float(value),)

    @property
    def display_top_text(self) -> str:
        """User message for the top display line, up to 20 characters."""
        return self._get("display_top_text")

    @display_top_text.setter
    def display_top_text(self, value: str) -> None:
        """Set display top text."""
        self._set("display_top_text", value)

    @property
    def display_top_text_enabled(self) -> bool:
        """Whether the user message is shown on the top display line."""
        return self._get("display_top_text_enabled")

    @display_top_text_enabled.setter
    def display_top_text_enabled(self, value: bool) -> None:
        """Set display top text enabled."""
        self._set("display_top_text_enabled", value)

    @property
    def display_top_data(self) -> str:
        """Raw text currently shown on the top display line."""
        self._verify_connected()
        return (
            self.display_top_text
            if self.display_top_text_enabled
            else str(self._readings[-1]["VOLT" if "top" == "top" else "CURR"])
            if self._readings
            else ""
        )

    @property
    def display_top_attributes(self) -> str:
        """Raw annunciator/attribute information for the top display line."""
        self._verify_connected()
        return "0"

    @property
    def display_bottom_text(self) -> str:
        """User message for the bottom display line, up to 32 characters."""
        return self._get("display_bottom_text")

    @display_bottom_text.setter
    def display_bottom_text(self, value: str) -> None:
        """Set display bottom text."""
        self._set("display_bottom_text", value)

    @property
    def display_bottom_text_enabled(self) -> bool:
        """Whether the user message is shown on the bottom display line."""
        return self._get("display_bottom_text_enabled")

    @display_bottom_text_enabled.setter
    def display_bottom_text_enabled(self, value: bool) -> None:
        """Set display bottom text enabled."""
        self._set("display_bottom_text_enabled", value)

    @property
    def display_bottom_data(self) -> str:
        """Raw text currently shown on the bottom display line."""
        self._verify_connected()
        return (
            self.display_bottom_text
            if self.display_bottom_text_enabled
            else str(self._readings[-1]["VOLT" if "bottom" == "top" else "CURR"])
            if self._readings
            else ""
        )

    @property
    def display_bottom_attributes(self) -> str:
        """Raw annunciator/attribute information for the bottom display line."""
        self._verify_connected()
        return "0"

    @property
    def measurement_status_enable(self) -> int:
        """Measurement status event-enable register bit mask."""
        return self._get("measurement_status_enable")

    @measurement_status_enable.setter
    def measurement_status_enable(self, value: int | str) -> None:
        """Set measurement status enable."""
        self._set("measurement_status_enable", value)

    @property
    def measurement_status_condition(self) -> int:
        """Current measurement status condition register bit mask; reading does not
        clear it.
        """
        self._verify_connected()
        return 0

    def read_measurement_status_event(self) -> int:
        """Read and clear the measurement status event register."""
        self._verify_connected()
        value, self._events["measurement"] = self._events["measurement"], 0
        return value

    @property
    def operation_status_enable(self) -> int:
        """Operation status event-enable register bit mask."""
        return self._get("operation_status_enable")

    @operation_status_enable.setter
    def operation_status_enable(self, value: int | str) -> None:
        """Set operation status enable."""
        self._set("operation_status_enable", value)

    @property
    def operation_status_condition(self) -> int:
        """Current operation status condition register bit mask; reading does not
        clear it.
        """
        self._verify_connected()
        return 0 if self._pending else 1024

    def read_operation_status_event(self) -> int:
        """Read and clear the operation status event register."""
        self._verify_connected()
        value, self._events["operation"] = self._events["operation"], 0
        return value

    @property
    def questionable_status_enable(self) -> int:
        """Questionable status event-enable register bit mask."""
        return self._get("questionable_status_enable")

    @questionable_status_enable.setter
    def questionable_status_enable(self, value: int | str) -> None:
        """Set questionable status enable."""
        self._set("questionable_status_enable", value)

    @property
    def questionable_status_condition(self) -> int:
        """Current questionable status condition register bit mask; reading does not
        clear it.
        """
        self._verify_connected()
        return 0

    def read_questionable_status_event(self) -> int:
        """Read and clear the questionable status event register."""
        self._verify_connected()
        value, self._events["questionable"] = self._events["questionable"], 0
        return value

    def get_limit_test_enabled(self, index: int) -> bool:
        """Read whether measurement limit test `index` is enabled (1–12).

        Test 1 checks compliance; test 4 checks contact; tests 2, 3, and 5–12
        compare measurements against numeric thresholds.

        Parameters
        ----------
        index : int
            Physical test number (1–12).

        Returns
        -------
        bool
            True if the specified limit test is enabled.
        """
        return self._test_get(index, "enabled", False)

    def set_limit_test_enabled(self, index: int, enabled: bool) -> None:
        """Enable or disable a numbered measurement limit test.

        Parameters
        ----------
        index : int
            Test number (1–12): compliance test 1, contact-check test 4, or numeric
            comparison tests 2, 3, and 5–12.
        enabled : bool
            Whether the test participates in pass/fail evaluation.
        """
        self._test_set(index, "enabled", enabled, False)

    def get_limit_test_failed(self, index: int) -> bool:
        """Read whether a measurement limit test has failed.

        Reading does not clear the failure indication. Test 1 checks compliance;
        test 4 checks contact; tests 2, 3, and 5–12 compare numeric thresholds.

        Parameters
        ----------
        index : int
            Physical test number (1–12). Test 4 requires the contact-check option.

        Returns
        -------
        bool
            Whether the selected test's failure flag is set.
        """
        return self._test_get(index, "failed", False)

    def get_limit_test_upper(self, index: int) -> float:
        """Read the upper measurement threshold for limit test `index`.

        Applies to numeric tests 2, 3, and 5–12. Test 1 is the compliance test and
        test 4 is the contact-check test; neither has thresholds.

        Parameters
        ----------
        index : int
            Numeric test number (2, 3, or 5–12).

        Returns
        -------
        float
            Upper threshold in selected measurement units.
        """
        return self._test_get(index, "upper", True)

    def set_limit_test_upper(self, index: int, value: float | str) -> None:
        """Set the upper measurement threshold for limit test `index`.

        Applies to numeric tests 2, 3, and 5–12. Test 1 is the compliance test and
        test 4 is the contact-check test; neither has thresholds.

        Parameters
        ----------
        index : int
            Numeric test number (2, 3, or 5–12).
        value : float | str
            Threshold in the selected measurement units, or a supported SCPI
            numeric token.
        """
        self._test_set(index, "upper", value, True)

    def get_limit_test_lower(self, index: int) -> float:
        """Read the lower measurement threshold for limit test `index`.

        Applies to numeric tests 2, 3, and 5–12. Test 1 is the compliance test and
        test 4 is the contact-check test; neither has thresholds.

        Parameters
        ----------
        index : int
            Numeric test number (2, 3, or 5–12).

        Returns
        -------
        float
            Lower threshold in selected measurement units.
        """
        return self._test_get(index, "lower", True)

    def set_limit_test_lower(self, index: int, value: float | str) -> None:
        """Set the lower measurement threshold for limit test `index`.

        Applies to numeric tests 2, 3, and 5–12. Test 1 is the compliance test and
        test 4 is the contact-check test; neither has thresholds.

        Parameters
        ----------
        index : int
            Numeric test number (2, 3, or 5–12).
        value : float | str
            Threshold in the selected measurement units, or a supported SCPI
            numeric token.
        """
        self._test_set(index, "lower", value, True)

    def get_limit_test_fail_pattern(self, index: int) -> int:
        """Read the digital failure pattern for measurement limit test `index` (1–12).

        Test 1 checks compliance; test 4 checks contact; tests 2, 3, and 5–12
        compare measurements against numeric thresholds. For numeric tests, this is
        the lower-threshold failure pattern.

        Parameters
        ----------
        index : int
            Physical test number (1–12).

        Returns
        -------
        int
            Digital output pattern as an integer.
        """
        return self._test_get(index, "fail_pattern", False)

    def set_limit_test_fail_pattern(self, index: int, value: int | str) -> None:
        """Set the digital failure pattern for measurement limit test `index` (1–12).

        Test 1 checks compliance; test 4 checks contact; tests 2, 3, and 5–12
        compare measurements against numeric thresholds. For numeric tests, this is
        the lower-threshold failure pattern.

        Parameters
        ----------
        index : int
            Physical test number (1–12); test 4 requires the contact-check option.
        value : int | str
            Digital output pattern as an integer or SCPI numeric token.
        """
        self._test_set(index, "fail_pattern", value, False)

    def get_limit_test_upper_fail_pattern(self, index: int) -> int:
        """Read the digital upper-failure pattern for measurement limit test `index`.

        Applies to numeric tests 2, 3, and 5–12. Test 1 is the compliance test and
        test 4 is the contact-check test; neither has thresholds.

        Parameters
        ----------
        index : int
            Numeric test number (2, 3, or 5–12).

        Returns
        -------
        int
            Digital output pattern as an integer.
        """
        return self._test_get(index, "upper_fail_pattern", True)

    def set_limit_test_upper_fail_pattern(self, index: int, value: int | str) -> None:
        """Set the digital upper-failure pattern for measurement limit test `index`.

        Applies to numeric tests 2, 3, and 5–12. Test 1 is the compliance test and
        test 4 is the contact-check test; neither has thresholds.

        Parameters
        ----------
        index : int
            Numeric test number (2, 3, or 5–12).
        value : int | str
            Digital output pattern as an integer or SCPI numeric token.
        """
        self._test_set(index, "upper_fail_pattern", value, True)

    def get_limit_test_pass_pattern(self, index: int) -> int:
        """Read the digital pass pattern for measurement limit test `index`.

        Applies to numeric tests 2, 3, and 5–12. Test 1 is the compliance test and
        test 4 is the contact-check test; neither has thresholds.

        Parameters
        ----------
        index : int
            Numeric test number (2, 3, or 5–12).

        Returns
        -------
        int
            Digital output pattern as an integer.
        """
        return self._test_get(index, "pass_pattern", True)

    def set_limit_test_pass_pattern(self, index: int, value: int | str) -> None:
        """Set the digital pass pattern for measurement limit test `index`.

        Applies to numeric tests 2, 3, and 5–12. Test 1 is the compliance test and
        test 4 is the contact-check test; neither has thresholds.

        Parameters
        ----------
        index : int
            Numeric test number (2, 3, or 5–12).
        value : int | str
            Digital output pattern as an integer or SCPI numeric token.
        """
        self._test_set(index, "pass_pattern", value, True)

    @property
    def limit_test_1_compliance_fail_condition(self) -> str:
        """Read the compliance condition that fails measurement limit test 1."""
        return self._get("limit_test_1_compliance_fail_condition")

    @limit_test_1_compliance_fail_condition.setter
    def limit_test_1_compliance_fail_condition(self, value: str) -> None:
        """Set limit test 1 compliance fail condition."""
        self._set("limit_test_1_compliance_fail_condition", value)

    def get_limit_test_upper_minimum(self, index: int) -> float:
        """Read the minimum allowed upper threshold for measurement limit test
        `index`.

        Applies to numeric tests 2, 3, and 5–12. Test 1 is the compliance test and
        test 4 is the contact-check test; neither has thresholds.

        Parameters
        ----------
        index : int
            Numeric test number (2, 3, or 5–12).

        Returns
        -------
        float
            Instrument-reported threshold value in the selected limit-test feed
            units.
        """
        self._test_get(index, "upper", True)
        return -9.999999e20

    def get_limit_test_upper_maximum(self, index: int) -> float:
        """Read the maximum allowed upper threshold for measurement limit test
        `index`.

        Applies to numeric tests 2, 3, and 5–12. Test 1 is the compliance test and
        test 4 is the contact-check test; neither has thresholds.

        Parameters
        ----------
        index : int
            Numeric test number (2, 3, or 5–12).

        Returns
        -------
        float
            Instrument-reported threshold value in the selected limit-test feed
            units.
        """
        self._test_get(index, "upper", True)
        return 9.999999e20

    def get_limit_test_upper_default(self, index: int) -> float:
        """Read the default upper threshold for measurement limit test `index`.

        Applies to numeric tests 2, 3, and 5–12. Test 1 is the compliance test and
        test 4 is the contact-check test; neither has thresholds.

        Parameters
        ----------
        index : int
            Numeric test number (2, 3, or 5–12).

        Returns
        -------
        float
            Instrument-reported threshold value in the selected limit-test feed
            units.
        """
        self._test_get(index, "upper", True)
        return 1.0

    def get_limit_test_lower_minimum(self, index: int) -> float:
        """Read the minimum allowed lower threshold for measurement limit test
        `index`.

        Applies to numeric tests 2, 3, and 5–12. Test 1 is the compliance test and
        test 4 is the contact-check test; neither has thresholds.

        Parameters
        ----------
        index : int
            Numeric test number (2, 3, or 5–12).

        Returns
        -------
        float
            Instrument-reported threshold value in the selected limit-test feed
            units.
        """
        self._test_get(index, "lower", True)
        return -9.999999e20

    def get_limit_test_lower_maximum(self, index: int) -> float:
        """Read the maximum allowed lower threshold for measurement limit test
        `index`.

        Applies to numeric tests 2, 3, and 5–12. Test 1 is the compliance test and
        test 4 is the contact-check test; neither has thresholds.

        Parameters
        ----------
        index : int
            Numeric test number (2, 3, or 5–12).

        Returns
        -------
        float
            Instrument-reported threshold value in the selected limit-test feed
            units.
        """
        self._test_get(index, "lower", True)
        return 9.999999e20

    def get_limit_test_lower_default(self, index: int) -> float:
        """Read the default lower threshold for measurement limit test `index`.

        Applies to numeric tests 2, 3, and 5–12. Test 1 is the compliance test and
        test 4 is the contact-check test; neither has thresholds.

        Parameters
        ----------
        index : int
            Numeric test number (2, 3, or 5–12).

        Returns
        -------
        float
            Instrument-reported threshold value in the selected limit-test feed
            units.
        """
        self._test_get(index, "lower", True)
        return -1.0
