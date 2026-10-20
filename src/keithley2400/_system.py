"""System, trace, trigger, status, and signal-oriented commands."""

from __future__ import annotations

import math
from typing import Sequence

from ._communication import NumericLimits, _Communication


class SystemCommands(_Communication):
    """Documented miscellaneous and trigger-model controls for the 2400."""

    @property
    def identity(self) -> str:
        """Manufacturer, model, serial number, and firmware (*IDN?)."""
        return self._query("*IDN?")

    @property
    def options(self) -> str:
        return self._query("*OPT?")

    def clear_status(self) -> None:
        self._write("*CLS")

    @property
    def event_status_enable(self) -> int:
        return self._query_int("*ESE?")

    @event_status_enable.setter
    def event_status_enable(self, value: int) -> None:
        self._write_int("*ESE", value)

    def read_event_status(self) -> int:
        """Read and clear the Standard Event Status Register."""
        return self._query_int("*ESR?")

    @property
    def service_request_enable(self) -> int:
        return self._query_int("*SRE?")

    @service_request_enable.setter
    def service_request_enable(self, value: int) -> None:
        self._write_int("*SRE", value)

    @property
    def status_byte(self) -> int:
        return self._query_int("*STB?")

    def self_test(self) -> int:
        """Run the ROM checksum self-test and return its result (*TST?)."""
        return self._query_int("*TST?")

    def save_setup(self, location: int) -> None:
        self._verify_setup_location(location)
        self._write_int("*SAV", location)

    def recall_setup(self, location: int) -> None:
        self._verify_setup_location(location)
        self._write_int("*RCL", location)

    def reset(self) -> None:
        self._write("*RST")

    def trigger_bus(self) -> None:
        self._write("*TRG")

    def set_operation_complete(self) -> None:
        """Queue *OPC; read its completion bit later with read_event_status()."""
        self._write("*OPC")

    def wait_complete(self) -> bool:
        """Wait for pending operations using *OPC? (the documented reply is 1)."""
        return self._query_int("*OPC?") == 1

    def wait_to_continue(self) -> None:
        self._write("*WAI")

    @property
    def power_on_setup(self) -> str:
        return self._query(":SYST:POSetup?").upper()

    @power_on_setup.setter
    def power_on_setup(self, value: str) -> None:
        normalized = value.strip().upper().replace(" ", "")
        choices = {
            "RST": "RST",
            "PRESET": "PRES",
            "PRES": "PRES",
            **{f"SAV{i}": f"SAV {i}" for i in range(5)},
        }
        if normalized not in choices:
            raise ValueError("invalid power-on setup")
        self._write(f":SYST:POSetup {choices[normalized]}")

    def preset(self) -> None:
        self._write(":SYST:PRES")

    @property
    def remote_sense(self) -> bool:
        return self._query_bool(":SYST:RSEN?")

    @remote_sense.setter
    def remote_sense(self, enabled: bool) -> None:
        self._write_bool(":SYST:RSEN", enabled)

    @property
    def contact_check_enabled(self) -> bool:
        return self._query_bool(":SYST:CCH?")

    @contact_check_enabled.setter
    def contact_check_enabled(self, enabled: bool) -> None:
        self._write_bool(":SYST:CCH", enabled)

    @property
    def contact_check_resistance(self) -> float:
        return self._query_float(":SYST:CCH:RES?")

    @contact_check_resistance.setter
    def contact_check_resistance(self, value: float) -> None:
        self._verify_range(value, 0, 60)
        self._write_float(":SYST:CCH:RES", value)

    @property
    def guard_mode(self) -> str:
        return self._query(":SYST:GUAR?").upper()

    @guard_mode.setter
    def guard_mode(self, value: str) -> None:
        self._write_enum(":SYST:GUAR", value, ("OHMS", "CABLE"))

    def initialize_memory(self) -> None:
        """Initialize battery-backed RAM; clears trace data and saved setups."""
        self._write(":SYST:MEM:INIT")

    def beep(self, frequency: float, duration: float) -> None:
        self._verify_range(frequency, 65, 2e6)
        self._verify_range(duration, 0, 7.9)
        self._write(f":SYST:BEEP {frequency:.12g},{duration:.12g}")

    @property
    def beeper_enabled(self) -> bool:
        return self._query_bool(":SYST:BEEP:STAT?")

    @beeper_enabled.setter
    def beeper_enabled(self, enabled: bool) -> None:
        self._write_bool(":SYST:BEEP:STAT", enabled)

    @property
    def auto_zero(self) -> str:
        return self._query(":SYST:AZER:STAT?").upper()

    @auto_zero.setter
    def auto_zero(self, state: str) -> None:
        self._write_enum(":SYST:AZER:STAT", state, ("ON", "OFF", "ONCE"))

    @property
    def nplc_caching(self) -> bool:
        return self._query_bool(":SYST:AZER:CACH?")

    @nplc_caching.setter
    def nplc_caching(self, enabled: bool) -> None:
        self._write_bool(":SYST:AZER:CACH", enabled)

    @property
    def cached_nplc_values(self) -> tuple[float, ...]:
        return self._query_floats(":SYST:AZER:CACH:NPLC?")

    def refresh_nplc_cache(self) -> None:
        self._write(":SYST:AZER:CACH:REFR")

    def reset_nplc_cache(self) -> None:
        self._write(":SYST:AZER:CACH:RES")

    @property
    def line_frequency(self) -> int:
        return self._query_int(":SYST:LFR?")

    @line_frequency.setter
    def line_frequency(self, value: int) -> None:
        if value not in (50, 60):
            raise ValueError("line_frequency must be 50 or 60 Hz")
        self._write_int(":SYST:LFR", value)

    @property
    def auto_line_frequency(self) -> bool:
        return self._query_bool(":SYST:LFR:AUTO?")

    @auto_line_frequency.setter
    def auto_line_frequency(self, enabled: bool) -> None:
        self._write_bool(":SYST:LFR:AUTO", enabled)

    def read_errors(self) -> str:
        """Read and remove all queued errors in one query."""
        return self._query(":SYST:ERR:ALL?")

    @property
    def error_count(self) -> int:
        return self._query_int(":SYST:ERR:COUN?")

    def read_error_code(self) -> int:
        """Read and remove the oldest queued error code."""
        return self._query_int(":SYST:ERR:CODE?")

    def read_error_codes(self) -> str:
        """Read and remove all queued error codes."""
        return self._query(":SYST:ERR:CODE:ALL?")

    def clear_errors(self) -> None:
        self._write(":SYST:CLE")

    def press_key(self, key_code: int) -> None:
        if not 1 <= key_code <= 32:
            raise ValueError("key_code must be from 1 through 32")
        self._write_int(":SYST:KEY", key_code)

    def read_last_key(self) -> int:
        """Read the key code queued by the last physical or simulated press."""
        return self._query_int(":SYST:KEY?")

    @property
    def scpi_version(self) -> str:
        return self._query(":SYST:VERS?")

    def local(self) -> None:
        self._write(":SYST:LOC")

    @property
    def remote_lockout(self) -> bool:
        return self._query_bool(":SYST:RWLock?")

    @remote_lockout.setter
    def remote_lockout(self, enabled: bool) -> None:
        self._write_bool(":SYST:RWLock", enabled)

    @property
    def timestamp(self) -> float:
        return self._query_float(":SYST:TIME?")

    def reset_timestamp(self) -> None:
        self._write(":SYST:TIME:RES")

    @property
    def auto_reset_timestamp(self) -> bool:
        return self._query_bool(":SYST:TIME:RES:AUTO?")

    @auto_reset_timestamp.setter
    def auto_reset_timestamp(self, enabled: bool) -> None:
        self._write_bool(":SYST:TIME:RES:AUTO", enabled)

    @property
    def range_change_mode(self) -> str:
        return self._query(":SYST:RCM?").upper()

    @range_change_mode.setter
    def range_change_mode(self, mode: str) -> None:
        self._write_enum(":SYST:RCM", mode, ("SINGLE", "MULTIPLE"))

    # Trace/data buffer (the :DATA root is a documented synonym for :TRACe).
    @property
    def trace_data(self) -> tuple[float, ...]:
        return self._query_data(":TRAC:DATA?")

    def clear_trace(self) -> None:
        self._write(":TRAC:CLE")

    @property
    def trace_memory(self) -> tuple[int, int]:
        values = self._query(":TRAC:FREE?").split(",")
        if len(values) != 2:
            raise ValueError(
                "TRACE:FREE? must return available and reserved byte counts"
            )
        return int(values[0]), int(values[1])

    @property
    def trace_points(self) -> int:
        return self._query_int(":TRAC:POIN?")

    @trace_points.setter
    def trace_points(self, count: int | str) -> None:
        self._verify_range(count, 1, 2500)
        self._write_int(":TRAC:POIN", count)

    @property
    def trace_points_actual(self) -> int:
        return self._query_int(":TRAC:POIN:ACT?")

    @property
    def trace_feed(self) -> str:
        return self._query(":TRAC:FEED?").upper()

    @trace_feed.setter
    def trace_feed(self, feed: str) -> None:
        self._write_enum(
            ":TRAC:FEED", feed, ("SENSE", "SENSE1", "CALC", "CALC1", "CALC2")
        )

    @property
    def trace_control(self) -> str:
        return self._query(":TRAC:FEED:CONT?").upper()

    @trace_control.setter
    def trace_control(self, control: str) -> None:
        self._write_enum(":TRAC:FEED:CONT", control, ("NEXT", "NEVER"))

    @property
    def trace_timestamp_format(self) -> str:
        return self._query(":TRAC:TST:FORM?").upper()

    @trace_timestamp_format.setter
    def trace_timestamp_format(self, fmt: str) -> None:
        self._write_enum(":TRAC:TST:FORM", fmt, ("ABSOLUTE", "DELTA"))

    # Trigger model, including the arm layer and contact-check sequence 2.
    def clear_triggers(self) -> None:
        self._write(":TRIG:CLE")

    def initiate(self) -> None:
        self._write(":INIT")

    def abort(self) -> None:
        self._write(":ABOR")

    @property
    def arm_count(self) -> int | str:
        count = self._query_float(":ARM:COUN?")
        return "INFINITE" if count == 9.9e37 else int(count)

    @arm_count.setter
    def arm_count(self, count: int | str) -> None:
        if isinstance(count, str) and count.strip().upper() in {"INF", "INFINITE"}:
            parameter = "INF"
        else:
            self._verify_range(count, 1, 2500)
            parameter = count
        self._write_int(":ARM:COUN", parameter)

    @property
    def trigger_count(self) -> int:
        return self._query_int(":TRIG:COUN?")

    @trigger_count.setter
    def trigger_count(self, count: int | str) -> None:
        self._verify_range(count, 1, 2500)
        self._write_int(":TRIG:COUN", count)

    @property
    def arm_source(self) -> str:
        return self._query(":ARM:SOUR?").upper()

    @arm_source.setter
    def arm_source(self, source: str) -> None:
        self._write_enum(
            ":ARM:SOUR",
            source,
            (
                "IMM",
                "IMMEDIATE",
                "TLINK",
                "TIMER",
                "MANUAL",
                "BUS",
                "NSTEST",
                "PSTEST",
                "BSTEST",
            ),
        )

    @property
    def trigger_source(self) -> str:
        return self._query(":TRIG:SOUR?").upper()

    @trigger_source.setter
    def trigger_source(self, source: str) -> None:
        self._write_enum(":TRIG:SOUR", source, ("IMM", "IMMEDIATE", "TLINK"))

    @property
    def trigger_delay(self) -> float:
        return self._query_float(":TRIG:DEL?")

    @trigger_delay.setter
    def trigger_delay(self, delay: float | str) -> None:
        self._verify_range(delay, 0, 999.9999)
        self._write_float(":TRIG:DEL", delay)

    @property
    def arm_timer(self) -> float:
        return self._query_float(":ARM:TIM?")

    @arm_timer.setter
    def arm_timer(self, seconds: float | str) -> None:
        self._verify_range(seconds, 0.001, 99999.99)
        self._write_float(":ARM:TIM", seconds)

    @property
    def arm_bypass(self) -> str:
        return self._query(":ARM:DIR?").upper()

    @arm_bypass.setter
    def arm_bypass(self, direction: str) -> None:
        self._write_enum(":ARM:DIR", direction, ("SOURCE", "ACCEPTOR"))

    @property
    def trigger_bypass(self) -> str:
        return self._query(":TRIG:DIR?").upper()

    @trigger_bypass.setter
    def trigger_bypass(self, direction: str) -> None:
        self._write_enum(":TRIG:DIR", direction, ("SOURCE", "ACCEPTOR"))

    @property
    def arm_input_line(self) -> int:
        return self._query_int(":ARM:ILIN?")

    @arm_input_line.setter
    def arm_input_line(self, line: int) -> None:
        self._write_trigger_line("ARM:ILIN", line)

    @property
    def trigger_input_line(self) -> int:
        return self._query_int(":TRIG:ILIN?")

    @trigger_input_line.setter
    def trigger_input_line(self, line: int) -> None:
        self._write_trigger_line("TRIG:ILIN", line)

    @property
    def arm_output_line(self) -> int:
        return self._query_int(":ARM:OLIN?")

    @arm_output_line.setter
    def arm_output_line(self, line: int) -> None:
        self._write_trigger_line("ARM:OLIN", line)

    @property
    def trigger_output_line(self) -> int:
        return self._query_int(":TRIG:OLIN?")

    @trigger_output_line.setter
    def trigger_output_line(self, line: int) -> None:
        self._write_trigger_line("TRIG:OLIN", line)

    @property
    def arm_output_events(self) -> tuple[str, ...]:
        return self._tokens(self._query(":ARM:OUTP?"))

    @arm_output_events.setter
    def arm_output_events(self, events: str | Sequence[str]) -> None:
        self._write_event_list(":ARM:OUTP", events, ("TENTER", "TEXIT", "NONE"))

    @property
    def trigger_output_events(self) -> tuple[str, ...]:
        return self._tokens(self._query(":TRIG:OUTP?"))

    @trigger_output_events.setter
    def trigger_output_events(self, events: str | Sequence[str]) -> None:
        self._write_event_list(
            ":TRIG:OUTP",
            events,
            ("SOUR", "SOURCE", "DEL", "DELAY", "SENS", "SENSE", "NONE"),
        )

    @property
    def trigger_input_events(self) -> tuple[str, ...]:
        return self._tokens(self._query(":TRIG:INP?"))

    @trigger_input_events.setter
    def trigger_input_events(self, events: str | Sequence[str]) -> None:
        self._write_event_list(
            ":TRIG:INP",
            events,
            ("SOUR", "SOURCE", "DEL", "DELAY", "SENS", "SENSE", "NONE"),
        )

    @property
    def contact_check_event_source(self) -> str:
        return self._query(":TRIG:SEQ2:SOUR?").upper()

    @contact_check_event_source.setter
    def contact_check_event_source(self, source: str) -> None:
        self._write_enum(":TRIG:SEQ2:SOUR", source, ("CCHECK", "IMMEDIATE", "IMM"))

    @property
    def contact_check_timeout(self) -> float:
        return self._query_float(":TRIG:SEQ2:TOUT?")

    @contact_check_timeout.setter
    def contact_check_timeout(self, seconds: float) -> None:
        self._verify_range(seconds, 0, 999.9999)
        self._write_float(":TRIG:SEQ2:TOUT", seconds)

    def set_mep_holdoff(self, enabled: bool) -> None:
        """Set Appendix G NDAC holdoff (no query is documented)."""
        self._write_bool(":SYST:MEP:HOLD", enabled)

    @property
    def scpi_protocol_enabled(self) -> bool:
        """Query MEP state; true indicates SCPI protocol, false indicates 488.1."""
        return self._query_bool(":SYST:MEP?")

    # Section 17 signal-oriented measurement commands return the instrument's
    # format-dependent data unchanged as a flat tuple of values.
    def read(self) -> tuple[float, ...]:
        return self._query_data(":READ?")

    def fetch(self) -> tuple[float, ...]:
        return self._query_data(":FETC?")

    def measure(self, function: str | None = None) -> tuple[float, ...]:
        command = (
            ":MEAS?"
            if function is None
            else f":MEAS:{self._normalize_sense_function(function)}?"
        )
        return self._query_data(command)

    def configure_measurement(self, function: str) -> None:
        self._write(f":CONF:{self._normalize_sense_function(function)}")

    @property
    def configured_measurement(self) -> tuple[str, ...]:
        return self._tokens(self._query(":CONF?"))

    @property
    def sense_data_latest(self) -> tuple[float, ...]:
        return self._query_floats(":SENS:DATA?")

    @staticmethod
    def _verify_setup_location(value: int) -> None:
        if not 0 <= value <= 4:
            raise ValueError("setup location must be from 0 through 4")

    @staticmethod
    def _verify_range(value: float | str, low: float, high: float) -> None:
        if isinstance(value, str):
            _Communication._normalize_choice(
                value, ("MIN", "MINIMUM", "MAX", "MAXIMUM", "DEF", "DEFAULT")
            )
            return
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError("value must be finite and within the documented range")

    def _write_trigger_line(self, command: str, line: int) -> None:
        if line not in (1, 2, 3, 4):
            raise ValueError("trigger link line must be 1 through 4")
        self._write_int(f":{command}", line)

    @staticmethod
    def _tokens(value: str) -> tuple[str, ...]:
        return tuple(
            part.strip().strip('"').upper() for part in value.split(",") if part.strip()
        )

    def _write_event_list(
        self, command: str, events: str | Sequence[str], allowed: Sequence[str]
    ) -> None:
        values = (events,) if isinstance(events, str) else tuple(events)
        normalized = tuple(self._normalize_choice(event, allowed) for event in values)
        if (
            not normalized
            or len(set(normalized)) != len(normalized)
            or ("NONE" in normalized and len(normalized) != 1)
        ):
            raise ValueError("provide unique events; NONE must be used alone")
        self._write(f"{command} {','.join(normalized)}")

    @property
    def trace_points_limits(self) -> NumericLimits:
        return self._query_limits(":TRAC:POIN")

    @property
    def arm_count_limits(self) -> NumericLimits:
        return self._query_limits(":ARM:COUN")

    @property
    def trigger_count_limits(self) -> NumericLimits:
        return self._query_limits(":TRIG:COUN")

    @property
    def trigger_delay_limits(self) -> NumericLimits:
        return self._query_limits(":TRIG:DEL")

    @property
    def arm_timer_limits(self) -> NumericLimits:
        return self._query_limits(":ARM:TIM")
