"""Keithley 2400 SCPI commands, implemented directly on one instrument class."""

from __future__ import annotations

import math
import struct
from collections.abc import Collection, Sequence
from types import TracebackType
from typing import Any

import pyvisa
from pyvisa.resources import (
    GPIBInstrument,
    MessageBasedResource,
    SerialInstrument,
    TCPIPSocket,
)


class keithley2400:
    """Control a Keithley 2400 directly through its documented SCPI commands.

    Connecting configures communication only. Writes check the error queue by
    default; disable check_errors_after_write for asynchronous trigger sequences.
    """

    # Connection lifecycle and communication

    def __init__(self) -> None:
        self._instr: pyvisa.resources.MessageBasedResource | None = None
        self.check_errors_after_write: bool = True

    def __enter__(self) -> keithley2400:
        """Return this instance; connect explicitly inside the context."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Disconnect on exit; output control remains explicit."""
        self.disconnect()

    def connect(
        self,
        resource_name: str,
        *,
        resource_manager: pyvisa.ResourceManager | None = None,
        **resource_kwargs: Any,
    ) -> None:
        """Open a VISA session and configure communication only.

        Serial connections require an explicit, nonempty read_termination matching
        the instrument's response setting. GPIB reads default to LF.
        TCP sockets require explicit, nonempty read and write terminations.
        Serial writes default to CR; GPIB writes default to LF.
        Resource keyword arguments override the transport defaults.
        """
        if self._instr is not None:
            raise RuntimeError("already connected")
        manager = (
            resource_manager
            if resource_manager is not None
            else pyvisa.ResourceManager()
        )
        settings: dict[str, Any] = {"encoding": "ascii"}
        settings.update(resource_kwargs)
        instrument = manager.open_resource(resource_name, **settings)
        try:
            if not isinstance(instrument, MessageBasedResource):
                raise TypeError("a message-based VISA resource is required")
            self._instr = instrument
            if isinstance(instrument, TCPIPSocket):
                if not resource_kwargs.get(
                    "read_termination"
                ) or not resource_kwargs.get("write_termination"):
                    raise ValueError(
                        "TCP sockets require read_termination and write_termination"
                    )
            serial = isinstance(instrument, SerialInstrument)
            if serial and (not resource_kwargs.get("read_termination")):
                raise ValueError("serial connections require read_termination")
            if not serial and "read_termination" not in resource_kwargs:
                instrument.read_termination = "\n"
            if "write_termination" not in resource_kwargs:
                instrument.write_termination = "\r" if serial else "\n"
        except BaseException:
            self._instr = None
            try:
                instrument.close()
            except Exception:
                pass
            raise

    @property
    def connected(self) -> bool:
        return self._instr is not None

    def disconnect(self) -> None:
        """Close the instrument session, if connected."""
        instrument, self._instr = (self._instr, None)
        if instrument is not None:
            instrument.close()

    # Write helpers

    def _write(self, command: str) -> None:
        if self._instr is not None:
            self._instr.write(command)
            if self.check_errors_after_write:
                self.check_errors()
        else:
            raise RuntimeError("not connected")

    def _write_bool(self, command: str, enabled: bool) -> None:
        self._write(f"{command} {('ON' if enabled else 'OFF')}")

    def _write_int(self, command: str, value: int | str) -> None:
        self._write(f"{command} {value}")

    def _write_float(self, command: str, value: float | str) -> None:
        parameter = value if isinstance(value, str) else f"{value:.12g}"
        self._write(f"{command} {parameter}")

    def _write_floats(self, command: str, values: Sequence[float]) -> None:
        self._write(f"{command} " + ",".join((f"{value:.12g}" for value in values)))

    def _write_str(self, command: str, value: str) -> None:
        quoted = value.replace('"', '""')
        self._write(f'{command} "{quoted}"')

    def _write_enum(self, command: str, value: str, choices: Collection[str]) -> None:
        self._verify_choice(value, choices)
        self._write(f"{command} {value}")

    def _write_trigger_line(self, command: str, line: int) -> None:
        if line not in (1, 2, 3, 4):
            raise ValueError("trigger link line must be 1 through 4")
        self._write_int(f":{command}", line)

    def _write_event_list(
        self, command: str, events: str | Sequence[str], allowed: Sequence[str]
    ) -> None:
        values = (events,) if isinstance(events, str) else tuple(events)
        for event in values:
            self._verify_choice(event, allowed)
        if (
            not values
            or len(set(values)) != len(values)
            or ("NONE" in values and len(values) != 1)
        ):
            raise ValueError("provide unique events; NONE must be used alone")
        self._write(f"{command} {','.join(values)}")

    # Query helpers

    def _query(self, command: str) -> str:
        if self._instr is not None:
            return self._instr.query(command).strip()
        raise RuntimeError("not connected")

    def _query_bool(self, command: str) -> bool:
        return bool(int(self._query(command)))

    def _query_int(self, command: str) -> int:
        value = self._query(command)
        if value.startswith("#"):
            base = {"H": 16, "Q": 8, "B": 2}[value[1].upper()]
            return int(value[2:], base)
        return int(value)

    def _query_float(self, command: str) -> float:
        return float(self._query(command))

    def _query_floats(self, command: str) -> tuple[float, ...]:
        return tuple((float(value) for value in self._query(command).split(",")))

    def _query_data(self, command: str) -> tuple[float, ...]:
        """Read the documented ASCII or GPIB #0 single-precision data block."""
        format_name = self.data_format.upper().split(",", 1)[0]
        if format_name == "ASC":
            return self._query_floats(command)
        if format_name not in {"REAL", "SREAL"}:
            raise ValueError("unsupported reading transfer format")
        if self._instr is None:
            raise RuntimeError("not connected")
        if not isinstance(self._instr, GPIBInstrument):
            raise ValueError("binary reading transfers require GPIB")
        byte_order = self.byte_order
        termination = self._instr.read_termination
        try:
            self._instr.read_termination = None
            self._instr.write(command)
            block = self._instr.read_raw()
        finally:
            self._instr.read_termination = termination
        if not block.startswith(b"#0") or not block.endswith(b"\n"):
            raise ValueError("expected a #0 binary block terminated by LF")
        payload = block[2:-1]
        order = {"NORM": ">", "SWAP": "<"}[byte_order.upper()]
        return struct.unpack(f"{order}{len(payload) // 4}f", payload)

    def read_response(self) -> str:
        """Receive a pending ASCII response without issuing another command.

        After a timeout, first resolve the pending response or clear the VISA
        interface before querying instrument errors (manual Appendix B).
        """
        if self._instr is not None:
            return self._instr.read().strip()
        raise RuntimeError("not connected")

    # Validation helpers

    @staticmethod
    def _verify_positive_finite(value: float) -> None:
        if not math.isfinite(value) or value <= 0:
            raise ValueError("value must be positive and finite")

    @staticmethod
    def _verify_sense_function(function: str) -> None:
        if function not in ("VOLT", "CURR", "RES"):
            raise ValueError("sense function must be VOLT, CURR, or RES")

    @staticmethod
    def _verify_source_function(function: str) -> None:
        if function not in ("VOLT", "CURR", "MEM"):
            raise ValueError("source function must be VOLT, CURR, or MEM")

    @staticmethod
    def _verify_choice(value: str, choices: Collection[str]) -> None:
        if value not in choices:
            raise ValueError("value must be one of " + ", ".join(sorted(choices)))

    @staticmethod
    def _verify_setup_location(value: int) -> None:
        if not 0 <= value <= 4:
            raise ValueError("setup location must be from 0 through 4")

    @staticmethod
    def _verify_range(value: float | str, low: float, high: float) -> None:
        if isinstance(value, str):
            keithley2400._verify_choice(
                value, ("MIN", "MINIMUM", "MAX", "MAXIMUM", "DEF", "DEFAULT")
            )
            return
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError("value must be finite and within the documented range")

    @staticmethod
    def _verify_limit_index(index: int) -> None:
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or not 1 <= index <= 12
        ):
            raise ValueError("limit index must be from 1 through 12")

    @staticmethod
    def _verify_numeric_limit_index(index: int) -> None:
        keithley2400._verify_limit_index(index)
        if index in (1, 4):
            raise ValueError(
                "numeric thresholds apply to limits 2, 3, and 5 through 12"
            )

    # Format commands

    @property
    def data_format(self) -> str:
        """Reading transfer format: ASC, REAL,32, or SREAL (binary is GPIB only)."""
        return self._query(":FORM:DATA?")

    @data_format.setter
    def data_format(self, value: str) -> None:
        self._write(f":FORM:DATA {value}")

    @property
    def byte_order(self) -> str:
        """Binary transfer byte order: NORM (big endian) or SWAP."""
        return self._query(":FORM:BORD?")

    @byte_order.setter
    def byte_order(self, value: str) -> None:
        self._write(f":FORM:BORD {value}")

    @property
    def status_register_format(self) -> str:
        return self._query(":FORM:SREG?").upper()

    @status_register_format.setter
    def status_register_format(self, value: str) -> None:
        self._write(":FORM:SREG " + value)

    @property
    def digital_format(self) -> str:
        return self._query(":FORM:SOUR2?").upper()

    @digital_format.setter
    def digital_format(self, value: str) -> None:
        self._write(":FORM:SOUR2 " + value)

    @property
    def data_elements(self) -> str:
        return self._query(":FORM:ELEM?")

    @data_elements.setter
    def data_elements(self, value: str | Sequence[str]) -> None:
        elements = ",".join(value) if not isinstance(value, str) else value
        self._write(":FORM:ELEM " + elements)

    @property
    def calculation_elements(self) -> str:
        return self._query(":FORM:ELEM:CALC?")

    @calculation_elements.setter
    def calculation_elements(self, value: str | Sequence[str]) -> None:
        self._write(
            ":FORM:ELEM:CALC "
            + (",".join(value) if not isinstance(value, str) else value)
        )

    # Identity, status, and common commands

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

    # System settings

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
        self._verify_range(frequency, 65, 2000000.0)
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

    def read_error(self) -> str:
        """Read and remove the oldest error, retaining the raw instrument text."""
        return self._query(":SYST:ERR?")

    def check_errors(self) -> None:
        """Drain the error queue and raise RuntimeError containing its raw messages."""
        errors = []
        while True:
            error = self.read_error()
            if int(error.split(",", 1)[0]) == 0:
                break
            errors.append(error)
        if errors:
            raise RuntimeError("\n".join(errors))

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

    # Trace buffer

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
        return (int(values[0]), int(values[1]))

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

    # Arm and trigger controls

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

    # Acquiring measurements

    def read(self) -> tuple[float, ...]:
        return self._query_data(":READ?")

    def fetch(self) -> tuple[float, ...]:
        return self._query_data(":FETC?")

    def measure(self, function: str | None = None) -> tuple[float, ...]:
        if function is not None:
            self._verify_sense_function(function)
        return self._query_data(":MEAS?" if function is None else f":MEAS:{function}?")

    def configure_measurement(self, function: str) -> None:
        self._verify_sense_function(function)
        self._write(f":CONF:{function}")

    @property
    def configured_measurement(self) -> tuple[str, ...]:
        return self._tokens(self._query(":CONF?"))

    @property
    def sense_data_latest(self) -> tuple[float, ...]:
        return self._query_floats(":SENS:DATA?")

    @staticmethod
    def _tokens(value: str) -> tuple[str, ...]:
        return tuple(
            (
                part.strip().strip('"').upper()
                for part in value.split(",")
                if part.strip()
            )
        )

    @property
    def trace_points_minimum(self) -> float:
        return self._query_float(":TRAC:POIN? MIN")

    @property
    def trace_points_maximum(self) -> float:
        return self._query_float(":TRAC:POIN? MAX")

    @property
    def trace_points_default(self) -> float:
        return self._query_float(":TRAC:POIN? DEF")

    @property
    def arm_count_minimum(self) -> float:
        return self._query_float(":ARM:COUN? MIN")

    @property
    def arm_count_maximum(self) -> float:
        return self._query_float(":ARM:COUN? MAX")

    @property
    def arm_count_default(self) -> float:
        return self._query_float(":ARM:COUN? DEF")

    @property
    def trigger_count_minimum(self) -> float:
        return self._query_float(":TRIG:COUN? MIN")

    @property
    def trigger_count_maximum(self) -> float:
        return self._query_float(":TRIG:COUN? MAX")

    @property
    def trigger_count_default(self) -> float:
        return self._query_float(":TRIG:COUN? DEF")

    @property
    def trigger_delay_minimum(self) -> float:
        return self._query_float(":TRIG:DEL? MIN")

    @property
    def trigger_delay_maximum(self) -> float:
        return self._query_float(":TRIG:DEL? MAX")

    @property
    def trigger_delay_default(self) -> float:
        return self._query_float(":TRIG:DEL? DEF")

    @property
    def arm_timer_minimum(self) -> float:
        return self._query_float(":ARM:TIM? MIN")

    @property
    def arm_timer_maximum(self) -> float:
        return self._query_float(":ARM:TIM? MAX")

    @property
    def arm_timer_default(self) -> float:
        return self._query_float(":ARM:TIM? DEF")

    # Source, sense, and output settings

    @property
    def source_function(self) -> str:
        return self._query(":SOUR:FUNC?").strip('"').upper()

    @source_function.setter
    def source_function(self, value: str) -> None:
        self._verify_source_function(value)
        self._write(f":SOUR:FUNC {value}")

    @property
    def source_level(self) -> float:
        function = self.source_function[:4]
        if function == "VOLT":
            return self.source_voltage_level
        if function == "CURR":
            return self.source_current_level
        raise ValueError("memory source mode has no direct level")

    @source_level.setter
    def source_level(self, value: float | str) -> None:
        function = self.source_function[:4]
        if function == "VOLT":
            self.source_voltage_level = value
        elif function == "CURR":
            self.source_current_level = value
        else:
            raise ValueError("memory source mode has no direct level")

    @property
    def source_range(self) -> float:
        function = self.source_function[:4]
        if function == "VOLT":
            return self.source_voltage_range
        if function == "CURR":
            return self.source_current_range
        raise ValueError("memory source mode has no direct range")

    @source_range.setter
    def source_range(self, value: float | str) -> None:
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
        raw = self._query(":SENS:FUNC?").replace('"', "")
        return tuple(
            (
                part.strip().removesuffix(":DC")
                for part in raw.split(",")
                if part.strip()
            )
        )

    @property
    def sense_concurrent(self) -> bool:
        return self._query_bool(":SENS:FUNC:CONC?")

    @sense_concurrent.setter
    def sense_concurrent(self, enabled: bool) -> None:
        self._write_bool(":SENS:FUNC:CONC", enabled)

    @property
    def enabled_sense_function_count(self) -> int:
        return self._query_int(":SENS:FUNC:ON:COUN?")

    @property
    def disabled_sense_function_count(self) -> int:
        return self._query_int(":SENS:FUNC:OFF:COUN?")

    @property
    def disabled_sense_functions(self) -> tuple[str, ...]:
        raw = self._query(":SENS:FUNC:OFF?").replace('"', "")
        return tuple(
            (
                part.strip().removesuffix(":DC")
                for part in raw.split(",")
                if part.strip()
            )
        )

    def enable_sense_functions(self, functions: Sequence[str]) -> None:
        for value in functions:
            self._verify_sense_function(value)
            self._write_str(":SENS:FUNC:ON", value)

    def disable_sense_functions(self, functions: Sequence[str]) -> None:
        for value in functions:
            self._verify_sense_function(value)
            self._write_str(":SENS:FUNC:OFF", value)

    def enable_all_sense_functions(self) -> None:
        self._write(":SENS:FUNC:ON:ALL")

    def disable_all_sense_functions(self) -> None:
        self._write(":SENS:FUNC:OFF:ALL")

    def sense_function_enabled(self, function: str) -> bool:
        self._verify_sense_function(function)
        return self._query_bool(f':SENS:FUNC:STAT? "{function}"')

    @property
    def sense_auto_range(self) -> bool:
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
        return self.sense_voltage_range

    @voltage_range.setter
    def voltage_range(self, value: float | str) -> None:
        self.sense_voltage_range = value

    @property
    def current_range(self) -> float:
        return self.sense_current_range

    @current_range.setter
    def current_range(self, value: float | str) -> None:
        self.sense_current_range = value

    @property
    def current_compliance(self) -> float:
        return self._query_float(":SENS:CURR:PROT?")

    @current_compliance.setter
    def current_compliance(self, value: float | str) -> None:
        self._write_float(":SENS:CURR:PROT", value)

    @property
    def voltage_compliance(self) -> float:
        return self._query_float(":SENS:VOLT:PROT?")

    @voltage_compliance.setter
    def voltage_compliance(self, value: float | str) -> None:
        self._write_float(":SENS:VOLT:PROT", value)

    @property
    def current_compliance_tripped(self) -> bool:
        return self._query_bool(":SENS:CURR:PROT:TRIP?")

    @property
    def voltage_compliance_tripped(self) -> bool:
        return self._query_bool(":SENS:VOLT:PROT:TRIP?")

    @property
    def current_range_synchronized(self) -> bool:
        return self._query_bool(":SENS:CURR:PROT:RSYN?")

    @current_range_synchronized.setter
    def current_range_synchronized(self, enabled: bool) -> None:
        self._write_bool(":SENS:CURR:PROT:RSYN", enabled)

    @property
    def voltage_range_synchronized(self) -> bool:
        return self._query_bool(":SENS:VOLT:PROT:RSYN?")

    @voltage_range_synchronized.setter
    def voltage_range_synchronized(self, enabled: bool) -> None:
        self._write_bool(":SENS:VOLT:PROT:RSYN", enabled)

    @property
    def nplc(self) -> float:
        return self.sense_voltage_nplc

    @nplc.setter
    def nplc(self, value: float | str) -> None:
        self.sense_voltage_nplc = value

    @property
    def resistance_mode(self) -> str:
        return self._query(":SENS:RES:MODE?").upper()

    @resistance_mode.setter
    def resistance_mode(self, value: str) -> None:
        value = value.upper()
        if value not in {"AUTO", "MAN", "MANUAL"}:
            raise ValueError("resistance_mode must be AUTO or MANual")
        self._write(f":SENS:RES:MODE {('MAN' if value.startswith('MAN') else 'AUTO')}")

    @property
    def offset_compensated_ohms(self) -> bool:
        return self._query_bool(":SENS:RES:OCOM?")

    @offset_compensated_ohms.setter
    def offset_compensated_ohms(self, value: bool) -> None:
        self._write_bool(":SENS:RES:OCOM", value)

    @property
    def voltage_protection(self) -> float:
        return self._query_float(":SOUR:VOLT:PROT?")

    @voltage_protection.setter
    def voltage_protection(self, value: float | str) -> None:
        self._write_float(":SOUR:VOLT:PROT", value)

    @property
    def voltage_protection_tripped(self) -> bool:
        return self._query_bool(":SOUR:VOLT:PROT:TRIP?")

    @property
    def average_type(self) -> str:
        return self._query(":SENS:AVER:TCON?").upper()

    @average_type.setter
    def average_type(self, value: str) -> None:
        value = value.upper()
        if value not in {"REP", "REPEAT", "MOV", "MOVING"}:
            raise ValueError("average_type must be REPeat or MOVing")
        self._write(f":SENS:AVER:TCON {('REP' if value.startswith('REP') else 'MOV')}")

    @property
    def average_count(self) -> int:
        return self._query_int(":SENS:AVER:COUN?")

    @average_count.setter
    def average_count(self, value: int | str) -> None:
        self._write_int(":SENS:AVER:COUN", value)

    @property
    def averaging_enabled(self) -> bool:
        return self._query_bool(":SENS:AVER:STAT?")

    @averaging_enabled.setter
    def averaging_enabled(self, value: bool) -> None:
        self._write_bool(":SENS:AVER:STAT", value)

    @property
    def output_enabled(self) -> bool:
        return self._query_bool(":OUTP:STAT?")

    @output_enabled.setter
    def output_enabled(self, value: bool) -> None:
        self._write_bool(":OUTP:STAT", value)

    @property
    def output_enable(self) -> bool:
        return self._query_bool(":OUTP:IENAB:STAT?")

    @output_enable.setter
    def output_enable(self, value: bool) -> None:
        self._write_bool(":OUTP:IENAB:STAT", value)

    @property
    def output_enable_tripped(self) -> bool:
        """Whether the output-enable input prevents operation (device replies 0)."""
        return not self._query_bool(":OUTP:ENAB:TRIP?")

    @property
    def output_off_mode(self) -> str:
        return self._query(":OUTP:SMOD?").upper()

    @output_off_mode.setter
    def output_off_mode(self, value: str) -> None:
        value = value.upper()
        if value not in {
            "HIMP",
            "HIMPEDANCE",
            "NORM",
            "NORMAL",
            "ZERO",
            "GUARD",
            "GUAR",
        }:
            raise ValueError("invalid output off mode")
        self._write(f":OUTP:SMOD {value}")

    @property
    def terminals(self) -> str:
        return self._query(":ROUT:TERM?").upper()

    @terminals.setter
    def terminals(self, value: str) -> None:
        value = value.upper()
        if value not in {"FRONT", "REAR"}:
            raise ValueError("terminals must be FRONT or REAR")
        self._write(f":ROUT:TERM {value}")

    def clear_source(self) -> None:
        self._write(":SOUR:CLE:IMM")

    @property
    def auto_output_off(self) -> bool:
        return self._query_bool(":SOUR:CLE:AUTO?")

    @auto_output_off.setter
    def auto_output_off(self, value: bool) -> None:
        self._write_bool(":SOUR:CLE:AUTO", value)

    @property
    def auto_output_off_mode(self) -> str:
        return self._query(":SOUR:CLE:AUTO:MODE?").upper()

    @auto_output_off_mode.setter
    def auto_output_off_mode(self, value: str) -> None:
        value = value.upper()
        if value not in {"ALW", "ALWAYS", "TCO", "TCOUNT"}:
            raise ValueError("mode must be ALWays or TCOunt")
        self._write(f":SOUR:CLE:AUTO:MODE {value}")

    @property
    def source_delay(self) -> float:
        return self._query_float(":SOUR:DEL?")

    @source_delay.setter
    def source_delay(self, value: float | str) -> None:
        self._write_float(":SOUR:DEL", value)

    @property
    def source_delay_auto(self) -> bool:
        return self._query_bool(":SOUR:DEL:AUTO?")

    @source_delay_auto.setter
    def source_delay_auto(self, value: bool) -> None:
        self._write_bool(":SOUR:DEL:AUTO", value)

    @property
    def sweep_spacing(self) -> str:
        return self._query(":SOUR:SWE:SPAC?").upper()

    @sweep_spacing.setter
    def sweep_spacing(self, value: str) -> None:
        self._write_enum(
            ":SOUR:SWE:SPAC", value, {"LIN", "LINEAR", "LOG", "LOGARITHMIC"}
        )

    @property
    def sweep_points(self) -> int:
        return self._query_int(":SOUR:SWE:POIN?")

    @sweep_points.setter
    def sweep_points(self, value: int | str) -> None:
        self._write_int(":SOUR:SWE:POIN", value)

    @property
    def sweep_direction(self) -> str:
        return self._query(":SOUR:SWE:DIR?").upper()

    @sweep_direction.setter
    def sweep_direction(self, value: str) -> None:
        self._write_enum(":SOUR:SWE:DIR", value, {"UP", "DOWN"})

    @property
    def sweep_ranging(self) -> str:
        return self._query(":SOUR:SWE:RANG?").upper()

    @sweep_ranging.setter
    def sweep_ranging(self, value: str) -> None:
        self._write_enum(":SOUR:SWE:RANG", value, {"BEST", "AUTO", "FIX", "FIXED"})

    @property
    def sweep_compliance_abort(self) -> str:
        return self._query(":SOUR:SWE:CAB?").upper()

    @sweep_compliance_abort.setter
    def sweep_compliance_abort(self, value: str) -> None:
        self._write_enum(
            ":SOUR:SWE:CAB", value, {"NEV", "NEVER", "EAR", "EARLY", "LAT", "LATE"}
        )

    @property
    def sweep_soak(self) -> float:
        return self._query_float(":SOUR:SOAK?")

    @sweep_soak.setter
    def sweep_soak(self, value: float | str) -> None:
        self._write_float(":SOUR:SOAK", value)

    @property
    def memory_points(self) -> int:
        return self._query_int(":SOUR:MEM:POIN?")

    @memory_points.setter
    def memory_points(self, value: int) -> None:
        self._write_int(":SOUR:MEM:POIN", value)

    @property
    def memory_start(self) -> int:
        return self._query_int(":SOUR:MEM:STAR?")

    @memory_start.setter
    def memory_start(self, value: int) -> None:
        self._write_int(":SOUR:MEM:STAR", value)

    def save_memory(self, location: int) -> None:
        self._write_int(":SOUR:MEM:SAVE", location)

    def recall_memory(self, location: int) -> None:
        self._write_int(":SOUR:MEM:RECall", location)

    @property
    def pulse_shape(self) -> str:
        return self._query(":SOUR:FUNC:SHAP?").upper()

    @pulse_shape.setter
    def pulse_shape(self, value: str) -> None:
        self._write_enum(":SOUR:FUNC:SHAP", value, {"DC", "PUL", "PULSE"})

    @property
    def pulse_width(self) -> float:
        return self._query_float(":SOUR:PULS:WIDT?")

    @pulse_width.setter
    def pulse_width(self, value: float | str) -> None:
        self._write_float(":SOUR:PULS:WIDT", value)

    @property
    def pulse_delay(self) -> float:
        return self._query_float(":SOUR:PULS:DEL?")

    @pulse_delay.setter
    def pulse_delay(self, value: float | str) -> None:
        self._write_float(":SOUR:PULS:DEL", value)

    @property
    def digital_bit_size(self) -> int:
        return self._query_int(":SOUR2:BSIZ?")

    @digital_bit_size.setter
    def digital_bit_size(self, value: int) -> None:
        self._write_int(":SOUR2:BSIZ", value)

    @property
    def digital_output_pattern(self) -> int:
        return self._query_int(":SOUR2:TTL:LEV:DEF?")

    @digital_output_pattern.setter
    def digital_output_pattern(self, value: int) -> None:
        self._write_int(":SOUR2:TTL:LEV:DEF", value)

    @property
    def digital_output_actual(self) -> int:
        return self._query_int(":SOUR2:TTL:LEV:ACT?")

    @property
    def digital_line4_mode(self) -> str:
        return self._query(":SOUR2:TTL4:MODE?").upper()

    @digital_line4_mode.setter
    def digital_line4_mode(self, value: str) -> None:
        self._write_enum(":SOUR2:TTL4:MODE", value, {"EOT", "EOTEST", "BUSY"})

    @property
    def digital_busy_polarity(self) -> str:
        return self._query(":SOUR2:TTL4:BST?").upper()

    @digital_busy_polarity.setter
    def digital_busy_polarity(self, value: str) -> None:
        self._write_enum(":SOUR2:TTL4:BST", value, {"HI", "LO"})

    def clear_digital_output(self) -> None:
        self._write(":SOUR2:CLE:IMM")

    @property
    def digital_clear_auto(self) -> bool:
        return self._query_bool(":SOUR2:CLE:AUTO?")

    @digital_clear_auto.setter
    def digital_clear_auto(self, value: bool) -> None:
        self._write_bool(":SOUR2:CLE:AUTO", value)

    @property
    def digital_clear_delay(self) -> float:
        return self._query_float(":SOUR2:CLE:AUTO:DEL?")

    @digital_clear_delay.setter
    def digital_clear_delay(self, value: float | str) -> None:
        self._write_float(":SOUR2:CLE:AUTO:DEL", value)

    @property
    def current_compliance_minimum(self) -> float:
        return self._query_float(":SENS:CURR:PROT? MIN")

    @property
    def current_compliance_maximum(self) -> float:
        return self._query_float(":SENS:CURR:PROT? MAX")

    @property
    def current_compliance_default(self) -> float:
        return self._query_float(":SENS:CURR:PROT? DEF")

    @property
    def voltage_compliance_minimum(self) -> float:
        return self._query_float(":SENS:VOLT:PROT? MIN")

    @property
    def voltage_compliance_maximum(self) -> float:
        return self._query_float(":SENS:VOLT:PROT? MAX")

    @property
    def voltage_compliance_default(self) -> float:
        return self._query_float(":SENS:VOLT:PROT? DEF")

    @property
    def average_count_minimum(self) -> float:
        return self._query_float(":SENS:AVER:COUN? MIN")

    @property
    def average_count_maximum(self) -> float:
        return self._query_float(":SENS:AVER:COUN? MAX")

    @property
    def average_count_default(self) -> float:
        return self._query_float(":SENS:AVER:COUN? DEF")

    @property
    def voltage_protection_minimum(self) -> float:
        return self._query_float(":SOUR:VOLT:PROT? MIN")

    @property
    def voltage_protection_maximum(self) -> float:
        return self._query_float(":SOUR:VOLT:PROT? MAX")

    @property
    def voltage_protection_default(self) -> float:
        return self._query_float(":SOUR:VOLT:PROT? DEF")

    @property
    def source_delay_minimum(self) -> float:
        return self._query_float(":SOUR:DEL? MIN")

    @property
    def source_delay_maximum(self) -> float:
        return self._query_float(":SOUR:DEL? MAX")

    @property
    def source_delay_default(self) -> float:
        return self._query_float(":SOUR:DEL? DEF")

    @property
    def sweep_points_minimum(self) -> float:
        return self._query_float(":SOUR:SWE:POIN? MIN")

    @property
    def sweep_points_maximum(self) -> float:
        return self._query_float(":SOUR:SWE:POIN? MAX")

    @property
    def sweep_points_default(self) -> float:
        return self._query_float(":SOUR:SWE:POIN? DEF")

    @property
    def pulse_width_minimum(self) -> float:
        return self._query_float(":SOUR:PULS:WIDT? MIN")

    @property
    def pulse_width_maximum(self) -> float:
        return self._query_float(":SOUR:PULS:WIDT? MAX")

    @property
    def pulse_width_default(self) -> float:
        return self._query_float(":SOUR:PULS:WIDT? DEF")

    @property
    def pulse_delay_minimum(self) -> float:
        return self._query_float(":SOUR:PULS:DEL? MIN")

    @property
    def pulse_delay_maximum(self) -> float:
        return self._query_float(":SOUR:PULS:DEL? MAX")

    @property
    def pulse_delay_default(self) -> float:
        return self._query_float(":SOUR:PULS:DEL? DEF")

    @property
    def digital_clear_delay_minimum(self) -> float:
        return self._query_float(":SOUR2:CLE:AUTO:DEL? MIN")

    @property
    def digital_clear_delay_maximum(self) -> float:
        return self._query_float(":SOUR2:CLE:AUTO:DEL? MAX")

    @property
    def digital_clear_delay_default(self) -> float:
        return self._query_float(":SOUR2:CLE:AUTO:DEL? DEF")

    # Source voltage

    @property
    def source_voltage_mode(self) -> str:
        return self._query(":SOUR:VOLT:MODE?").upper()

    @source_voltage_mode.setter
    def source_voltage_mode(self, value: str) -> None:
        value = value.upper()
        if value not in {"FIX", "FIXED", "SWE", "SWEEP", "LIST"}:
            raise ValueError("source channel mode must be FIX, SWEEP, or LIST")
        self._write(f":SOUR:VOLT:MODE {value}")

    @property
    def source_voltage_level(self) -> float:
        return self._query_float(":SOUR:VOLT:LEV?")

    @source_voltage_level.setter
    def source_voltage_level(self, value: float | str) -> None:
        self._write_float(":SOUR:VOLT:LEV", value)

    @property
    def source_voltage_range(self) -> float:
        return self._query_float(":SOUR:VOLT:RANG?")

    @source_voltage_range.setter
    def source_voltage_range(self, value: float | str) -> None:
        self._write_float(":SOUR:VOLT:RANG", value)

    @property
    def source_voltage_auto_range(self) -> bool:
        return self._query_bool(":SOUR:VOLT:RANG:AUTO?")

    @source_voltage_auto_range.setter
    def source_voltage_auto_range(self, value: bool) -> None:
        self._write_bool(":SOUR:VOLT:RANG:AUTO", value)

    @property
    def source_voltage_start(self) -> float:
        return self._query_float(":SOUR:VOLT:STAR?")

    @source_voltage_start.setter
    def source_voltage_start(self, value: float | str) -> None:
        self._write_float(":SOUR:VOLT:STAR", value)

    @property
    def source_voltage_stop(self) -> float:
        return self._query_float(":SOUR:VOLT:STOP?")

    @source_voltage_stop.setter
    def source_voltage_stop(self, value: float | str) -> None:
        self._write_float(":SOUR:VOLT:STOP", value)

    @property
    def source_voltage_step(self) -> float:
        return self._query_float(":SOUR:VOLT:STEP?")

    @source_voltage_step.setter
    def source_voltage_step(self, value: float | str) -> None:
        self._write_float(":SOUR:VOLT:STEP", value)

    @property
    def source_voltage_center(self) -> float:
        return self._query_float(":SOUR:VOLT:CENT?")

    @source_voltage_center.setter
    def source_voltage_center(self, value: float | str) -> None:
        self._write_float(":SOUR:VOLT:CENT", value)

    @property
    def source_voltage_span(self) -> float:
        return self._query_float(":SOUR:VOLT:SPAN?")

    @source_voltage_span.setter
    def source_voltage_span(self, value: float | str) -> None:
        self._write_float(":SOUR:VOLT:SPAN", value)

    @property
    def source_voltage_triggered_level(self) -> float:
        return self._query_float(":SOUR:VOLT:LEV:TRIG?")

    @source_voltage_triggered_level.setter
    def source_voltage_triggered_level(self, value: float | str) -> None:
        self._write_float(":SOUR:VOLT:LEV:TRIG", value)

    @property
    def source_voltage_scaling_factor(self) -> float:
        return self._query_float(":SOUR:VOLT:LEV:TRIG:SFAC?")

    @source_voltage_scaling_factor.setter
    def source_voltage_scaling_factor(self, value: float | str) -> None:
        self._write_float(":SOUR:VOLT:LEV:TRIG:SFAC", value)

    @property
    def source_voltage_scaling_enabled(self) -> bool:
        return self._query_bool(":SOUR:VOLT:LEV:TRIG:SFAC:STAT?")

    @source_voltage_scaling_enabled.setter
    def source_voltage_scaling_enabled(self, value: bool) -> None:
        self._write_bool(":SOUR:VOLT:LEV:TRIG:SFAC:STAT", value)

    @property
    def source_voltage_list_values(self) -> tuple[float, ...]:
        return self._query_floats(":SOUR:LIST:VOLT?")

    @source_voltage_list_values.setter
    def source_voltage_list_values(self, values: Sequence[float]) -> None:
        self._write_floats(":SOUR:LIST:VOLT", values)

    def append_source_voltage_list(self, values: Sequence[float]) -> None:
        self._write_floats(":SOUR:LIST:VOLT:APP", values)

    @property
    def source_voltage_list_points(self) -> int:
        return self._query_int(":SOUR:LIST:VOLT:POIN?")

    @property
    def source_voltage_list_start(self) -> int:
        return self._query_int(":SOUR:LIST:VOLT:STAR?")

    @source_voltage_list_start.setter
    def source_voltage_list_start(self, value: int | str) -> None:
        self._write_int(":SOUR:LIST:VOLT:STAR", value)

    @property
    def source_voltage_level_minimum(self) -> float:
        return self._query_float(":SOUR:VOLT:LEV? MIN")

    @property
    def source_voltage_level_maximum(self) -> float:
        return self._query_float(":SOUR:VOLT:LEV? MAX")

    @property
    def source_voltage_level_default(self) -> float:
        return self._query_float(":SOUR:VOLT:LEV? DEF")

    @property
    def source_voltage_range_minimum(self) -> float:
        return self._query_float(":SOUR:VOLT:RANG? MIN")

    @property
    def source_voltage_range_maximum(self) -> float:
        return self._query_float(":SOUR:VOLT:RANG? MAX")

    @property
    def source_voltage_range_default(self) -> float:
        return self._query_float(":SOUR:VOLT:RANG? DEF")

    @property
    def source_voltage_triggered_level_minimum(self) -> float:
        return self._query_float(":SOUR:VOLT:LEV:TRIG? MIN")

    @property
    def source_voltage_triggered_level_maximum(self) -> float:
        return self._query_float(":SOUR:VOLT:LEV:TRIG? MAX")

    @property
    def source_voltage_triggered_level_default(self) -> float:
        return self._query_float(":SOUR:VOLT:LEV:TRIG? DEF")

    @property
    def source_voltage_start_minimum(self) -> float:
        return self._query_float(":SOUR:VOLT:STAR? MIN")

    @property
    def source_voltage_start_maximum(self) -> float:
        return self._query_float(":SOUR:VOLT:STAR? MAX")

    @property
    def source_voltage_start_default(self) -> float:
        return self._query_float(":SOUR:VOLT:STAR? DEF")

    @property
    def source_voltage_stop_minimum(self) -> float:
        return self._query_float(":SOUR:VOLT:STOP? MIN")

    @property
    def source_voltage_stop_maximum(self) -> float:
        return self._query_float(":SOUR:VOLT:STOP? MAX")

    @property
    def source_voltage_stop_default(self) -> float:
        return self._query_float(":SOUR:VOLT:STOP? DEF")

    @property
    def source_voltage_center_minimum(self) -> float:
        return self._query_float(":SOUR:VOLT:CENT? MIN")

    @property
    def source_voltage_center_maximum(self) -> float:
        return self._query_float(":SOUR:VOLT:CENT? MAX")

    @property
    def source_voltage_center_default(self) -> float:
        return self._query_float(":SOUR:VOLT:CENT? DEF")

    @property
    def source_voltage_span_minimum(self) -> float:
        return self._query_float(":SOUR:VOLT:SPAN? MIN")

    @property
    def source_voltage_span_maximum(self) -> float:
        return self._query_float(":SOUR:VOLT:SPAN? MAX")

    @property
    def source_voltage_span_default(self) -> float:
        return self._query_float(":SOUR:VOLT:SPAN? DEF")

    @property
    def source_voltage_step_minimum(self) -> float:
        return self._query_float(":SOUR:VOLT:STEP? MIN")

    @property
    def source_voltage_step_maximum(self) -> float:
        return self._query_float(":SOUR:VOLT:STEP? MAX")

    @property
    def source_voltage_step_default(self) -> float:
        return self._query_float(":SOUR:VOLT:STEP? DEF")

    # Source current

    @property
    def source_current_mode(self) -> str:
        return self._query(":SOUR:CURR:MODE?").upper()

    @source_current_mode.setter
    def source_current_mode(self, value: str) -> None:
        value = value.upper()
        if value not in {"FIX", "FIXED", "SWE", "SWEEP", "LIST"}:
            raise ValueError("source channel mode must be FIX, SWEEP, or LIST")
        self._write(f":SOUR:CURR:MODE {value}")

    @property
    def source_current_level(self) -> float:
        return self._query_float(":SOUR:CURR:LEV?")

    @source_current_level.setter
    def source_current_level(self, value: float | str) -> None:
        self._write_float(":SOUR:CURR:LEV", value)

    @property
    def source_current_range(self) -> float:
        return self._query_float(":SOUR:CURR:RANG?")

    @source_current_range.setter
    def source_current_range(self, value: float | str) -> None:
        self._write_float(":SOUR:CURR:RANG", value)

    @property
    def source_current_auto_range(self) -> bool:
        return self._query_bool(":SOUR:CURR:RANG:AUTO?")

    @source_current_auto_range.setter
    def source_current_auto_range(self, value: bool) -> None:
        self._write_bool(":SOUR:CURR:RANG:AUTO", value)

    @property
    def source_current_start(self) -> float:
        return self._query_float(":SOUR:CURR:STAR?")

    @source_current_start.setter
    def source_current_start(self, value: float | str) -> None:
        self._write_float(":SOUR:CURR:STAR", value)

    @property
    def source_current_stop(self) -> float:
        return self._query_float(":SOUR:CURR:STOP?")

    @source_current_stop.setter
    def source_current_stop(self, value: float | str) -> None:
        self._write_float(":SOUR:CURR:STOP", value)

    @property
    def source_current_step(self) -> float:
        return self._query_float(":SOUR:CURR:STEP?")

    @source_current_step.setter
    def source_current_step(self, value: float | str) -> None:
        self._write_float(":SOUR:CURR:STEP", value)

    @property
    def source_current_center(self) -> float:
        return self._query_float(":SOUR:CURR:CENT?")

    @source_current_center.setter
    def source_current_center(self, value: float | str) -> None:
        self._write_float(":SOUR:CURR:CENT", value)

    @property
    def source_current_span(self) -> float:
        return self._query_float(":SOUR:CURR:SPAN?")

    @source_current_span.setter
    def source_current_span(self, value: float | str) -> None:
        self._write_float(":SOUR:CURR:SPAN", value)

    @property
    def source_current_triggered_level(self) -> float:
        return self._query_float(":SOUR:CURR:LEV:TRIG?")

    @source_current_triggered_level.setter
    def source_current_triggered_level(self, value: float | str) -> None:
        self._write_float(":SOUR:CURR:LEV:TRIG", value)

    @property
    def source_current_scaling_factor(self) -> float:
        return self._query_float(":SOUR:CURR:LEV:TRIG:SFAC?")

    @source_current_scaling_factor.setter
    def source_current_scaling_factor(self, value: float | str) -> None:
        self._write_float(":SOUR:CURR:LEV:TRIG:SFAC", value)

    @property
    def source_current_scaling_enabled(self) -> bool:
        return self._query_bool(":SOUR:CURR:LEV:TRIG:SFAC:STAT?")

    @source_current_scaling_enabled.setter
    def source_current_scaling_enabled(self, value: bool) -> None:
        self._write_bool(":SOUR:CURR:LEV:TRIG:SFAC:STAT", value)

    @property
    def source_current_list_values(self) -> tuple[float, ...]:
        return self._query_floats(":SOUR:LIST:CURR?")

    @source_current_list_values.setter
    def source_current_list_values(self, values: Sequence[float]) -> None:
        self._write_floats(":SOUR:LIST:CURR", values)

    def append_source_current_list(self, values: Sequence[float]) -> None:
        self._write_floats(":SOUR:LIST:CURR:APP", values)

    @property
    def source_current_list_points(self) -> int:
        return self._query_int(":SOUR:LIST:CURR:POIN?")

    @property
    def source_current_list_start(self) -> int:
        return self._query_int(":SOUR:LIST:CURR:STAR?")

    @source_current_list_start.setter
    def source_current_list_start(self, value: int | str) -> None:
        self._write_int(":SOUR:LIST:CURR:STAR", value)

    @property
    def source_current_level_minimum(self) -> float:
        return self._query_float(":SOUR:CURR:LEV? MIN")

    @property
    def source_current_level_maximum(self) -> float:
        return self._query_float(":SOUR:CURR:LEV? MAX")

    @property
    def source_current_level_default(self) -> float:
        return self._query_float(":SOUR:CURR:LEV? DEF")

    @property
    def source_current_range_minimum(self) -> float:
        return self._query_float(":SOUR:CURR:RANG? MIN")

    @property
    def source_current_range_maximum(self) -> float:
        return self._query_float(":SOUR:CURR:RANG? MAX")

    @property
    def source_current_range_default(self) -> float:
        return self._query_float(":SOUR:CURR:RANG? DEF")

    @property
    def source_current_triggered_level_minimum(self) -> float:
        return self._query_float(":SOUR:CURR:LEV:TRIG? MIN")

    @property
    def source_current_triggered_level_maximum(self) -> float:
        return self._query_float(":SOUR:CURR:LEV:TRIG? MAX")

    @property
    def source_current_triggered_level_default(self) -> float:
        return self._query_float(":SOUR:CURR:LEV:TRIG? DEF")

    @property
    def source_current_start_minimum(self) -> float:
        return self._query_float(":SOUR:CURR:STAR? MIN")

    @property
    def source_current_start_maximum(self) -> float:
        return self._query_float(":SOUR:CURR:STAR? MAX")

    @property
    def source_current_start_default(self) -> float:
        return self._query_float(":SOUR:CURR:STAR? DEF")

    @property
    def source_current_stop_minimum(self) -> float:
        return self._query_float(":SOUR:CURR:STOP? MIN")

    @property
    def source_current_stop_maximum(self) -> float:
        return self._query_float(":SOUR:CURR:STOP? MAX")

    @property
    def source_current_stop_default(self) -> float:
        return self._query_float(":SOUR:CURR:STOP? DEF")

    @property
    def source_current_center_minimum(self) -> float:
        return self._query_float(":SOUR:CURR:CENT? MIN")

    @property
    def source_current_center_maximum(self) -> float:
        return self._query_float(":SOUR:CURR:CENT? MAX")

    @property
    def source_current_center_default(self) -> float:
        return self._query_float(":SOUR:CURR:CENT? DEF")

    @property
    def source_current_span_minimum(self) -> float:
        return self._query_float(":SOUR:CURR:SPAN? MIN")

    @property
    def source_current_span_maximum(self) -> float:
        return self._query_float(":SOUR:CURR:SPAN? MAX")

    @property
    def source_current_span_default(self) -> float:
        return self._query_float(":SOUR:CURR:SPAN? DEF")

    @property
    def source_current_step_minimum(self) -> float:
        return self._query_float(":SOUR:CURR:STEP? MIN")

    @property
    def source_current_step_maximum(self) -> float:
        return self._query_float(":SOUR:CURR:STEP? MAX")

    @property
    def source_current_step_default(self) -> float:
        return self._query_float(":SOUR:CURR:STEP? DEF")

    # Sense voltage

    @property
    def sense_voltage_range(self) -> float:
        return self._query_float(":SENS:VOLT:RANG?")

    @sense_voltage_range.setter
    def sense_voltage_range(self, value: float | str) -> None:
        self._write_float(":SENS:VOLT:RANG", value)

    @property
    def sense_voltage_auto_range(self) -> bool:
        return self._query_bool(":SENS:VOLT:RANG:AUTO?")

    @sense_voltage_auto_range.setter
    def sense_voltage_auto_range(self, value: bool) -> None:
        self._write_bool(":SENS:VOLT:RANG:AUTO", value)

    @property
    def sense_voltage_range_upper_limit(self) -> float:
        return self._query_float(":SENS:VOLT:RANG:AUTO:ULIM?")

    @property
    def sense_voltage_range_lower_limit(self) -> float:
        return self._query_float(":SENS:VOLT:RANG:AUTO:LLIM?")

    @sense_voltage_range_lower_limit.setter
    def sense_voltage_range_lower_limit(self, value: float | str) -> None:
        self._write_float(":SENS:VOLT:RANG:AUTO:LLIM", value)

    @property
    def sense_voltage_nplc(self) -> float:
        return self._query_float(":SENS:VOLT:NPLC?")

    @sense_voltage_nplc.setter
    def sense_voltage_nplc(self, value: float | str) -> None:
        if not isinstance(value, str):
            self._verify_positive_finite(value)
        self._write_float(":SENS:VOLT:NPLC", value)

    @property
    def sense_voltage_range_minimum(self) -> float:
        return self._query_float(":SENS:VOLT:RANG? MIN")

    @property
    def sense_voltage_range_maximum(self) -> float:
        return self._query_float(":SENS:VOLT:RANG? MAX")

    @property
    def sense_voltage_range_default(self) -> float:
        return self._query_float(":SENS:VOLT:RANG? DEF")

    @property
    def sense_voltage_nplc_minimum(self) -> float:
        return self._query_float(":SENS:VOLT:NPLC? MIN")

    @property
    def sense_voltage_nplc_maximum(self) -> float:
        return self._query_float(":SENS:VOLT:NPLC? MAX")

    @property
    def sense_voltage_nplc_default(self) -> float:
        return self._query_float(":SENS:VOLT:NPLC? DEF")

    # Sense current

    @property
    def sense_current_range(self) -> float:
        return self._query_float(":SENS:CURR:RANG?")

    @sense_current_range.setter
    def sense_current_range(self, value: float | str) -> None:
        self._write_float(":SENS:CURR:RANG", value)

    @property
    def sense_current_auto_range(self) -> bool:
        return self._query_bool(":SENS:CURR:RANG:AUTO?")

    @sense_current_auto_range.setter
    def sense_current_auto_range(self, value: bool) -> None:
        self._write_bool(":SENS:CURR:RANG:AUTO", value)

    @property
    def sense_current_range_upper_limit(self) -> float:
        return self._query_float(":SENS:CURR:RANG:AUTO:ULIM?")

    @property
    def sense_current_range_lower_limit(self) -> float:
        return self._query_float(":SENS:CURR:RANG:AUTO:LLIM?")

    @sense_current_range_lower_limit.setter
    def sense_current_range_lower_limit(self, value: float | str) -> None:
        self._write_float(":SENS:CURR:RANG:AUTO:LLIM", value)

    @property
    def sense_current_nplc(self) -> float:
        return self._query_float(":SENS:CURR:NPLC?")

    @sense_current_nplc.setter
    def sense_current_nplc(self, value: float | str) -> None:
        if not isinstance(value, str):
            self._verify_positive_finite(value)
        self._write_float(":SENS:CURR:NPLC", value)

    @property
    def sense_current_range_holdoff(self) -> bool:
        return self._query_bool(":SENS:CURR:RANG:HOLD?")

    @sense_current_range_holdoff.setter
    def sense_current_range_holdoff(self, value: bool) -> None:
        self._write_bool(":SENS:CURR:RANG:HOLD", value)

    @property
    def sense_current_range_holdoff_delay(self) -> float:
        return self._query_float(":SENS:CURR:RANG:HOLD:DEL?")

    @sense_current_range_holdoff_delay.setter
    def sense_current_range_holdoff_delay(self, value: float | str) -> None:
        self._write_float(":SENS:CURR:RANG:HOLD:DEL", value)

    @property
    def sense_current_range_minimum(self) -> float:
        return self._query_float(":SENS:CURR:RANG? MIN")

    @property
    def sense_current_range_maximum(self) -> float:
        return self._query_float(":SENS:CURR:RANG? MAX")

    @property
    def sense_current_range_default(self) -> float:
        return self._query_float(":SENS:CURR:RANG? DEF")

    @property
    def sense_current_nplc_minimum(self) -> float:
        return self._query_float(":SENS:CURR:NPLC? MIN")

    @property
    def sense_current_nplc_maximum(self) -> float:
        return self._query_float(":SENS:CURR:NPLC? MAX")

    @property
    def sense_current_nplc_default(self) -> float:
        return self._query_float(":SENS:CURR:NPLC? DEF")

    # Sense resistance

    @property
    def sense_resistance_range(self) -> float:
        return self._query_float(":SENS:RES:RANG?")

    @sense_resistance_range.setter
    def sense_resistance_range(self, value: float | str) -> None:
        self._write_float(":SENS:RES:RANG", value)

    @property
    def sense_resistance_auto_range(self) -> bool:
        return self._query_bool(":SENS:RES:RANG:AUTO?")

    @sense_resistance_auto_range.setter
    def sense_resistance_auto_range(self, value: bool) -> None:
        self._write_bool(":SENS:RES:RANG:AUTO", value)

    @property
    def sense_resistance_range_upper_limit(self) -> float:
        return self._query_float(":SENS:RES:RANG:AUTO:ULIM?")

    @sense_resistance_range_upper_limit.setter
    def sense_resistance_range_upper_limit(self, value: float | str) -> None:
        self._write_float(":SENS:RES:RANG:AUTO:ULIM", value)

    @property
    def sense_resistance_range_lower_limit(self) -> float:
        return self._query_float(":SENS:RES:RANG:AUTO:LLIM?")

    @sense_resistance_range_lower_limit.setter
    def sense_resistance_range_lower_limit(self, value: float | str) -> None:
        self._write_float(":SENS:RES:RANG:AUTO:LLIM", value)

    @property
    def sense_resistance_nplc(self) -> float:
        return self._query_float(":SENS:RES:NPLC?")

    @sense_resistance_nplc.setter
    def sense_resistance_nplc(self, value: float | str) -> None:
        if not isinstance(value, str):
            self._verify_positive_finite(value)
        self._write_float(":SENS:RES:NPLC", value)

    @property
    def sense_resistance_range_minimum(self) -> float:
        return self._query_float(":SENS:RES:RANG? MIN")

    @property
    def sense_resistance_range_maximum(self) -> float:
        return self._query_float(":SENS:RES:RANG? MAX")

    @property
    def sense_resistance_range_default(self) -> float:
        return self._query_float(":SENS:RES:RANG? DEF")

    @property
    def sense_resistance_nplc_minimum(self) -> float:
        return self._query_float(":SENS:RES:NPLC? MIN")

    @property
    def sense_resistance_nplc_maximum(self) -> float:
        return self._query_float(":SENS:RES:NPLC? MAX")

    @property
    def sense_resistance_nplc_default(self) -> float:
        return self._query_float(":SENS:RES:NPLC? DEF")

    # Calculation, display, and status settings

    @property
    def limit_feed(self) -> str:
        return self._query(":CALC2:FEED?").upper()

    @limit_feed.setter
    def limit_feed(self, value: str) -> None:
        self._write(":CALC2:FEED " + value)

    @property
    def limit_data(self) -> tuple[float, ...]:
        return self._query_data(":CALC2:DATA?")

    @property
    def limit_latest(self) -> tuple[float, ...]:
        return self._query_data(":CALC2:DATA:LAT?")

    @property
    def display_enabled(self) -> bool:
        return self._query_bool(":DISP:ENAB?")

    @display_enabled.setter
    def display_enabled(self, value: bool) -> None:
        self._write_bool(":DISP:ENAB", value)

    def display_source_measure(self) -> None:
        self._write(":DISP:CND")

    @property
    def display_digits(self) -> int:
        return self._query_int(":DISP:DIG?")

    @display_digits.setter
    def display_digits(self, value: int | str) -> None:
        self._write_int(":DISP:DIG", value)

    def preset_status(self) -> None:
        self._write(":STAT:PRES")

    @property
    def error_queue_enabled(self) -> str:
        return self._query(":STAT:QUE:ENAB?")

    @error_queue_enabled.setter
    def error_queue_enabled(self, value: str | Sequence[int]) -> None:
        self._write(
            ":STAT:QUE:ENAB "
            + (",".join(map(str, value)) if not isinstance(value, str) else value)
        )

    @property
    def error_queue_disabled(self) -> str:
        return self._query(":STAT:QUE:DIS?")

    @error_queue_disabled.setter
    def error_queue_disabled(self, value: str | Sequence[int]) -> None:
        self._write(
            ":STAT:QUE:DIS "
            + (",".join(map(str, value)) if not isinstance(value, str) else value)
        )

    def read_status_error(self) -> str:
        return self._query(":STAT:QUE?")

    def clear_status_errors(self) -> None:
        self._write(":STAT:QUE:CLE")

    @property
    def display_digits_minimum(self) -> float:
        return self._query_float(":DISP:DIG? MIN")

    @property
    def display_digits_maximum(self) -> float:
        return self._query_float(":DISP:DIG? MAX")

    @property
    def display_digits_default(self) -> float:
        return self._query_float(":DISP:DIG? DEF")

    # Math

    @property
    def math_catalog(self) -> str:
        return self._query(":CALC:MATH:CAT?")

    @property
    def math_name(self) -> str:
        return self._query(":CALC:MATH:NAME?")

    @math_name.setter
    def math_name(self, value: str) -> None:
        self._write_str(":CALC:MATH:NAME", value)

    @property
    def math_expression(self) -> str:
        return self._query(":CALC:MATH?")

    @math_expression.setter
    def math_expression(self, value: str) -> None:
        self._write(":CALC:MATH:EXPR " + value)

    @property
    def math_units(self) -> str:
        return self._query(":CALC:MATH:UNIT?").strip('"')

    @math_units.setter
    def math_units(self, value: str) -> None:
        self._write_str(":CALC:MATH:UNIT", value)

    @property
    def math_enabled(self) -> bool:
        return self._query_bool(":CALC:STAT?")

    @math_enabled.setter
    def math_enabled(self, value: bool) -> None:
        self._write_bool(":CALC:STAT", value)

    @property
    def math_data(self) -> tuple[float, ...]:
        return self._query_data(":CALC:DATA?")

    @property
    def math_latest(self) -> tuple[float, ...]:
        return self._query_data(":CALC:DATA:LAT?")

    def delete_math_expression(self, name: str) -> None:
        self._write_str(":CALC:MATH:DEL:SEL", name)

    def delete_all_math_expressions(self) -> None:
        self._write(":CALC:MATH:DEL:ALL")

    # Relative

    @property
    def relative_offset(self) -> float:
        return self._query_float(":CALC2:NULL:OFFS?")

    @relative_offset.setter
    def relative_offset(self, value: float) -> None:
        self._write_float(":CALC2:NULL:OFFS", value)

    @property
    def relative_enabled(self) -> bool:
        return self._query_bool(":CALC2:NULL:STAT?")

    @relative_enabled.setter
    def relative_enabled(self, value: bool) -> None:
        self._write_bool(":CALC2:NULL:STAT", value)

    def acquire_relative(self) -> None:
        self._write(":CALC2:NULL:ACQ")

    # Composite limit

    @property
    def composite_limit_pass_pattern(self) -> int:
        return self._query_int(":CALC2:CLIM:PASS:SOUR2?")

    @composite_limit_pass_pattern.setter
    def composite_limit_pass_pattern(self, value: int | str) -> None:
        self._write(f":CALC2:CLIM:PASS:SOUR2 {value}")

    @property
    def composite_limit_fail_pattern(self) -> int:
        return self._query_int(":CALC2:CLIM:FAIL:SOUR2?")

    @composite_limit_fail_pattern.setter
    def composite_limit_fail_pattern(self, value: int | str) -> None:
        self._write(f":CALC2:CLIM:FAIL:SOUR2 {value}")

    @property
    def composite_limit_pass_memory_location(self) -> str:
        return self._query(":CALC2:CLIM:PASS:SMLOCATION?")

    @composite_limit_pass_memory_location.setter
    def composite_limit_pass_memory_location(self, value: int | str) -> None:
        self._write(f":CALC2:CLIM:PASS:SMLOCATION {value}")

    @property
    def composite_limit_fail_memory_location(self) -> str:
        return self._query(":CALC2:CLIM:FAIL:SMLOCATION?")

    @composite_limit_fail_memory_location.setter
    def composite_limit_fail_memory_location(self, value: int | str) -> None:
        self._write(f":CALC2:CLIM:FAIL:SMLOCATION {value}")

    @property
    def composite_limit_mode(self) -> str:
        return self._query(":CALC2:CLIM:MODE?").upper()

    @composite_limit_mode.setter
    def composite_limit_mode(self, value: str) -> None:
        self._write(":CALC2:CLIM:MODE " + value)

    @property
    def composite_limit_bin_control(self) -> str:
        return self._query(":CALC2:CLIM:BCON?").upper()

    @composite_limit_bin_control.setter
    def composite_limit_bin_control(self, value: str) -> None:
        self._write(":CALC2:CLIM:BCON " + value)

    @property
    def composite_limit_auto_clear(self) -> bool:
        return self._query_bool(":CALC2:CLIM:CLE:AUTO?")

    @composite_limit_auto_clear.setter
    def composite_limit_auto_clear(self, value: bool) -> None:
        self._write_bool(":CALC2:CLIM:CLE:AUTO", value)

    def clear_composite_limits(self) -> None:
        self._write(":CALC2:CLIM:CLE")

    # Statistics

    @property
    def statistics_function(self) -> str:
        return self._query(":CALC3:FORM?").upper()

    @statistics_function.setter
    def statistics_function(self, value: str) -> None:
        self._write(":CALC3:FORM " + value)

    @property
    def statistics_data(self) -> tuple[float, ...]:
        return self._query_floats(":CALC3:DATA?")

    # Display top

    @property
    def display_top_text(self) -> str:
        return self._query(":DISP:WIND1:TEXT:DATA?")

    @display_top_text.setter
    def display_top_text(self, value: str) -> None:
        self._write_str(":DISP:WIND1:TEXT:DATA", value)

    @property
    def display_top_text_enabled(self) -> bool:
        return self._query_bool(":DISP:WIND1:TEXT:STAT?")

    @display_top_text_enabled.setter
    def display_top_text_enabled(self, value: bool) -> None:
        self._write_bool(":DISP:WIND1:TEXT:STAT", value)

    @property
    def display_top_data(self) -> str:
        return self._query(":DISP:WIND1:DATA?")

    @property
    def display_top_attributes(self) -> str:
        return self._query(":DISP:WIND1:ATTR?")

    # Display bottom

    @property
    def display_bottom_text(self) -> str:
        return self._query(":DISP:WIND2:TEXT:DATA?")

    @display_bottom_text.setter
    def display_bottom_text(self, value: str) -> None:
        self._write_str(":DISP:WIND2:TEXT:DATA", value)

    @property
    def display_bottom_text_enabled(self) -> bool:
        return self._query_bool(":DISP:WIND2:TEXT:STAT?")

    @display_bottom_text_enabled.setter
    def display_bottom_text_enabled(self, value: bool) -> None:
        self._write_bool(":DISP:WIND2:TEXT:STAT", value)

    @property
    def display_bottom_data(self) -> str:
        return self._query(":DISP:WIND2:DATA?")

    @property
    def display_bottom_attributes(self) -> str:
        return self._query(":DISP:WIND2:ATTR?")

    # Measurement status

    @property
    def measurement_status_enable(self) -> int:
        return self._query_int(":STAT:MEAS:ENAB?")

    @measurement_status_enable.setter
    def measurement_status_enable(self, value: int | str) -> None:
        self._write(f":STAT:MEAS:ENAB {value}")

    @property
    def measurement_status_condition(self) -> int:
        return self._query_int(":STAT:MEAS:COND?")

    def read_measurement_status_event(self) -> int:
        return self._query_int(":STAT:MEAS:EVEN?")

    # Operation status

    @property
    def operation_status_enable(self) -> int:
        return self._query_int(":STAT:OPER:ENAB?")

    @operation_status_enable.setter
    def operation_status_enable(self, value: int | str) -> None:
        self._write(f":STAT:OPER:ENAB {value}")

    @property
    def operation_status_condition(self) -> int:
        return self._query_int(":STAT:OPER:COND?")

    def read_operation_status_event(self) -> int:
        return self._query_int(":STAT:OPER:EVEN?")

    # Questionable status

    @property
    def questionable_status_enable(self) -> int:
        return self._query_int(":STAT:QUES:ENAB?")

    @questionable_status_enable.setter
    def questionable_status_enable(self, value: int | str) -> None:
        self._write(f":STAT:QUES:ENAB {value}")

    @property
    def questionable_status_condition(self) -> int:
        return self._query_int(":STAT:QUES:COND?")

    def read_questionable_status_event(self) -> int:
        return self._query_int(":STAT:QUES:EVEN?")

    # Indexed limit tests

    def get_limit_enabled(self, index: int) -> bool:
        self._verify_limit_index(index)
        return self._query_bool(f":CALC2:LIM{index}:STAT?")

    def set_limit_enabled(self, index: int, enabled: bool) -> None:
        self._verify_limit_index(index)
        self._write_bool(f":CALC2:LIM{index}:STAT", enabled)

    def get_limit_failed(self, index: int) -> bool:
        self._verify_limit_index(index)
        return self._query_bool(f":CALC2:LIM{index}:FAIL?")

    def get_limit_upper(self, index: int) -> float:
        self._verify_numeric_limit_index(index)
        return self._query_float(f":CALC2:LIM{index}:UPP?")

    def set_limit_upper(self, index: int, value: float | str) -> None:
        self._verify_numeric_limit_index(index)
        self._write_float(f":CALC2:LIM{index}:UPP", value)

    def get_limit_lower(self, index: int) -> float:
        self._verify_numeric_limit_index(index)
        return self._query_float(f":CALC2:LIM{index}:LOW?")

    def set_limit_lower(self, index: int, value: float | str) -> None:
        self._verify_numeric_limit_index(index)
        self._write_float(f":CALC2:LIM{index}:LOW", value)

    def get_limit_fail_pattern(self, index: int) -> int:
        self._verify_limit_index(index)
        if index == 1:
            return self._query_int(":CALC2:LIM1:COMP:SOUR2?")
        if index == 4:
            return self._query_int(":CALC2:LIM4:SOUR2?")
        return self._query_int(f":CALC2:LIM{index}:LOW:SOUR2?")

    def set_limit_fail_pattern(self, index: int, value: int | str) -> None:
        self._verify_limit_index(index)
        if index == 1:
            self._write_int(":CALC2:LIM1:COMP:SOUR2", value)
        elif index == 4:
            self._write_int(":CALC2:LIM4:SOUR2", value)
        else:
            self._write_int(f":CALC2:LIM{index}:LOW:SOUR2", value)

    def get_limit_upper_fail_pattern(self, index: int) -> int:
        self._verify_numeric_limit_index(index)
        return self._query_int(f":CALC2:LIM{index}:UPP:SOUR2?")

    def set_limit_upper_fail_pattern(self, index: int, value: int | str) -> None:
        self._verify_numeric_limit_index(index)
        self._write_int(f":CALC2:LIM{index}:UPP:SOUR2", value)

    def get_limit_pass_pattern(self, index: int) -> int:
        self._verify_numeric_limit_index(index)
        return self._query_int(f":CALC2:LIM{index}:PASS:SOUR2?")

    def set_limit_pass_pattern(self, index: int, value: int | str) -> None:
        self._verify_numeric_limit_index(index)
        self._write_int(f":CALC2:LIM{index}:PASS:SOUR2", value)

    @property
    def limit1_compliance_fail_condition(self) -> str:
        return self._query(":CALC2:LIM:COMP:FAIL?").upper()

    @limit1_compliance_fail_condition.setter
    def limit1_compliance_fail_condition(self, value: str) -> None:
        self._write(f":CALC2:LIM:COMP:FAIL {value}")

    def get_limit_upper_minimum(self, index: int) -> float:
        self._verify_numeric_limit_index(index)
        return self._query_float(f":CALC2:LIM{index}:UPP? MIN")

    def get_limit_upper_maximum(self, index: int) -> float:
        self._verify_numeric_limit_index(index)
        return self._query_float(f":CALC2:LIM{index}:UPP? MAX")

    def get_limit_upper_default(self, index: int) -> float:
        self._verify_numeric_limit_index(index)
        return self._query_float(f":CALC2:LIM{index}:UPP? DEF")

    def get_limit_lower_minimum(self, index: int) -> float:
        self._verify_numeric_limit_index(index)
        return self._query_float(f":CALC2:LIM{index}:LOW? MIN")

    def get_limit_lower_maximum(self, index: int) -> float:
        self._verify_numeric_limit_index(index)
        return self._query_float(f":CALC2:LIM{index}:LOW? MAX")

    def get_limit_lower_default(self, index: int) -> float:
        self._verify_numeric_limit_index(index)
        return self._query_float(f":CALC2:LIM{index}:LOW? DEF")
