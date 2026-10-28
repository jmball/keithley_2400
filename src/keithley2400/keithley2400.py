"""Keithley 2400 SCPI commands, implemented directly on one instrument class."""

from __future__ import annotations

import struct
from collections.abc import Sequence
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
    default; disable check_errors_after_write for asynchronous trigger sequences
    and call check_errors() after completion. Invalid writes raise RuntimeError
    with the raw queued error response. VISA timeouts propagate without retries.

    Numeric string parameters are passed to the instrument unchanged; the
    instrument validates supported tokens and ranges. Reading transfers return
    flat tuples in the selected element order. Overflow (9.9e37) and unavailable
    (9.91e37) sentinels are preserved. Binary reading transfer is GPIB-only.
    """

    # Connection lifecycle and communication

    def __init__(self) -> None:
        """Initialize an unconnected driver with automatic write-error checks enabled."""
        self._instr: pyvisa.resources.MessageBasedResource | None = None
        self.check_errors_after_write: bool = True

    def __enter__(self) -> keithley2400:
        """Return this driver for use in a context manager.

        Call connect() explicitly; leaving the context closes the instrument
        session.

        Returns
        -------
        keithley2400
            This instance.
        """
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

        Serial connections require a nonempty read_termination matching the
        instrument. Their write termination defaults to CR. GPIB reads and writes
        default to LF. Raw TCP sockets require both terminations explicitly. No
        instrument commands are sent, and existing measurement settings are
        preserved.

        Parameters
        ----------
        resource_name : str
            VISA resource string, for example GPIB0::24::INSTR, ASRL1::INSTR, or
            TCPIP0::host::4001::SOCKET for a transparent serial-to-Ethernet
            adapter.
        resource_manager : pyvisa.ResourceManager or None, optional
            Existing resource manager; a new one is created when omitted.
        resource_kwargs : Any
            Settings passed to PyVISA open_resource, such as timeout
            (milliseconds), baud_rate, read_termination, and write_termination.
            Explicit settings override transport defaults.
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
        """Whether a VISA message-based instrument session is open."""
        return self._instr is not None

    @property
    def timeout_ms(self) -> float:
        """VISA I/O timeout in milliseconds; float("inf") disables the timeout."""
        if self._instr is not None:
            return self._instr.timeout
        raise RuntimeError("not connected")

    @timeout_ms.setter
    def timeout_ms(self, value: float) -> None:
        """Set the VISA I/O timeout in milliseconds; float("inf") disables it."""
        if self._instr is not None:
            self._instr.timeout = value
        else:
            raise RuntimeError("not connected")

    def disconnect(self) -> None:
        """Close the instrument session, if connected."""
        instrument, self._instr = (self._instr, None)
        if instrument is not None:
            instrument.close()

    # Write helpers

    def _write(self, command: str) -> None:
        """Send one SCPI command; when enabled, drain and check the instrument error
        queue afterward.
        """
        if self._instr is not None:
            self._instr.write(command)
            if self.check_errors_after_write:
                self.check_errors()
        else:
            raise RuntimeError("not connected")

    def _write_bool(self, command: str, enabled: bool) -> None:
        """Send a SCPI boolean parameter as ON or OFF."""
        self._write(f"{command} {('ON' if enabled else 'OFF')}")

    def _write_int(self, command: str, value: int | str) -> None:
        """Send an integer or SCPI numeric token as a command parameter."""
        self._write(f"{command} {value}")

    def _write_float(self, command: str, value: float | str) -> None:
        """Send a floating-point value with 12 significant digits, or pass a SCPI
        token unchanged.
        """
        parameter = value if isinstance(value, str) else f"{value:.12g}"
        self._write(f"{command} {parameter}")

    def _write_floats(self, command: str, values: Sequence[float]) -> None:
        """Send a comma-separated sequence of floating-point command parameters."""
        self._write(f"{command} " + ",".join((f"{value:.12g}" for value in values)))

    def _write_str(self, command: str, value: str) -> None:
        """Quote a string parameter and double embedded quote characters per SCPI
        string syntax.
        """
        quoted = value.replace('"', '""')
        self._write(f'{command} "{quoted}"')

    def _write_event_list(self, command: str, events: str | Sequence[str]) -> None:
        """Send one or more event names as a comma-separated SCPI parameter."""
        values = (events,) if isinstance(events, str) else events
        self._write(f"{command} {','.join(values)}")

    # Query helpers

    def _query(self, command: str) -> str:
        """Issue a SCPI query and strip surrounding whitespace from its response."""
        if self._instr is not None:
            return self._instr.query(command).strip()
        raise RuntimeError("not connected")

    def _query_bool(self, command: str) -> bool:
        """Parse a numeric SCPI boolean response as a Python bool."""
        return bool(int(self._query(command)))

    def _query_int(self, command: str) -> int:
        """Parse decimal or #H/#Q/#B-prefixed hexadecimal, octal, or binary integer
        response.
        """
        value = self._query(command)
        if value.startswith("#"):
            base = {"H": 16, "Q": 8, "B": 2}[value[1].upper()]
            return int(value[2:], base)
        return int(value)

    def _query_float(self, command: str) -> float:
        """Parse a SCPI numeric response as a Python float."""
        return float(self._query(command))

    def _query_floats(self, command: str) -> tuple[float, ...]:
        """Parse a comma-separated SCPI response as a tuple of floats."""
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
        """Receive a pending ASCII response without sending another command.

        May receive a late response after a timeout, but cannot reconstruct any
        bytes already consumed by the failed read. Resolve pending output before
        issuing another query; there is no automatic timeout recovery.

        Returns
        -------
        str
            Instrument response with surrounding whitespace removed.
        """
        if self._instr is not None:
            return self._instr.read().strip()
        raise RuntimeError("not connected")

    # Validation helpers

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
            or not 1 <= index <= 12
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

    # Format commands

    @property
    def data_format(self) -> str:
        """Reading transfer format: ASC, REAL,32, or SREAL (binary is GPIB only)."""
        return self._query(":FORM:DATA?")

    @data_format.setter
    def data_format(self, value: str) -> None:
        """Set data format; choices: ASC, REAL,32, or SREAL."""
        self._write(f":FORM:DATA {value}")

    @property
    def byte_order(self) -> str:
        """Binary transfer byte order: NORM (big endian) or SWAP."""
        return self._query(":FORM:BORD?")

    @byte_order.setter
    def byte_order(self, value: str) -> None:
        """Set byte order; choices: NORM or SWAP."""
        self._write(f":FORM:BORD {value}")

    @property
    def status_register_format(self) -> str:
        """Status-register response format, such as ASCII, HEX, OCT, or BIN."""
        return self._query(":FORM:SREG?").upper()

    @status_register_format.setter
    def status_register_format(self, value: str) -> None:
        """Set status register format."""
        self._write(":FORM:SREG " + value)

    @property
    def digital_format(self) -> str:
        """Digital I/O response format: ASCII, HEX, OCT, or BIN."""
        return self._query(":FORM:SOUR2?").upper()

    @digital_format.setter
    def digital_format(self, value: str) -> None:
        """Set digital format."""
        self._write(":FORM:SOUR2 " + value)

    @property
    def data_elements(self) -> str:
        """Enabled reading elements returned by :FORM:ELEM? (for example, VOLT, CURR,
        RES, TIME, or STAT).
        """
        return self._query(":FORM:ELEM?")

    @data_elements.setter
    def data_elements(self, value: str | Sequence[str]) -> None:
        """Set data elements."""
        elements = ",".join(value) if not isinstance(value, str) else value
        self._write(":FORM:ELEM " + elements)

    @property
    def calculation_elements(self) -> str:
        """Enabled calculation elements returned by :FORM:ELEM:CALC? (CALC, TIME, or
        STAT).
        """
        return self._query(":FORM:ELEM:CALC?")

    @calculation_elements.setter
    def calculation_elements(self, value: str | Sequence[str]) -> None:
        """Set calculation elements."""
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
        """Installed instrument option identifiers returned by *OPT?."""
        return self._query("*OPT?")

    def clear_status(self) -> None:
        """Clear status event registers and the instrument error queue with *CLS."""
        self._write("*CLS")

    @property
    def event_status_enable(self) -> int:
        """Standard Event Status Enable register bit mask."""
        return self._query_int("*ESE?")

    @event_status_enable.setter
    def event_status_enable(self, value: int) -> None:
        """Set event status enable."""
        self._write_int("*ESE", value)

    def read_event_status(self) -> int:
        """Read and clear the Standard Event Status Register.

        Returns
        -------
        int
            Register bit mask before it was cleared.
        """
        return self._query_int("*ESR?")

    @property
    def service_request_enable(self) -> int:
        """Service Request Enable register bit mask."""
        return self._query_int("*SRE?")

    @service_request_enable.setter
    def service_request_enable(self, value: int) -> None:
        """Set service request enable."""
        self._write_int("*SRE", value)

    @property
    def status_byte(self) -> int:
        """Current status-byte register bit mask, read with *STB?."""
        return self._query_int("*STB?")

    def self_test(self) -> int:
        """Run the ROM checksum self-test.

        The guide gives no execution-time bound; adjust timeout_ms if needed.

        Returns
        -------
        int
            Zero for a passed test, or one for failure.
        """
        return self._query_int("*TST?")

    def save_setup(self, location: int) -> None:
        """Save the current setup to instrument setup memory.

        Parameters
        ----------
        location : int
            Setup-memory location (0–4).
        """
        self._write_int("*SAV", location)

    def recall_setup(self, location: int) -> None:
        """Restore a setup from instrument setup memory.

        Parameters
        ----------
        location : int
            Setup-memory location (0–4).
        """
        self._write_int("*RCL", location)

    def reset(self) -> None:
        """Restore instrument settings using *RST."""
        self._write("*RST")

    def trigger_bus(self) -> None:
        """Send the IEEE-488 bus trigger (*TRG)."""
        self._write("*TRG")

    def set_operation_complete(self) -> None:
        """Queue *OPC; read its completion bit later with read_event_status()."""
        self._write("*OPC")

    def wait_complete(self) -> bool:
        """Wait for pending operations to complete with *OPC?.

        Uses timeout_ms and propagates VISA timeouts without retries. Works over
        GPIB, RS-232, and transparent serial adapters; it does not check success.

        Returns
        -------
        bool
            True when the instrument returns the documented completion value 1.
        """
        return self._query_int("*OPC?") == 1

    def wait_to_continue(self) -> None:
        """Send *WAI; the guide describes it as a no-op for this instrument."""
        self._write("*WAI")

    # System settings

    @property
    def power_on_setup(self) -> str:
        """Setup restored at power-on: RST, PRESet, or SAV followed by a setup
        location.
        """
        return self._query(":SYST:POSetup?").upper()

    @power_on_setup.setter
    def power_on_setup(self, value: str) -> None:
        """Set power on setup."""
        self._write(f":SYST:POSetup {value}")

    def preset(self) -> None:
        """Restore the instrument preset configuration with :SYST:PRES."""
        self._write(":SYST:PRES")

    @property
    def remote_sense(self) -> bool:
        """Whether remote sense is enabled."""
        return self._query_bool(":SYST:RSEN?")

    @remote_sense.setter
    def remote_sense(self, enabled: bool) -> None:
        """Set remote sense."""
        self._write_bool(":SYST:RSEN", enabled)

    @property
    def contact_check_enabled(self) -> bool:
        """Whether contact checking is enabled.

        Requires the contact-check option and remote sensing.
        """
        return self._query_bool(":SYST:CCH?")

    @contact_check_enabled.setter
    def contact_check_enabled(self, enabled: bool) -> None:
        """Set contact check enabled."""
        self._write_bool(":SYST:CCH", enabled)

    @property
    def contact_check_resistance(self) -> float:
        """Contact-check resistance threshold, in ohms (0–60).

        Requires the contact-check option.
        """
        return self._query_float(":SYST:CCH:RES?")

    @contact_check_resistance.setter
    def contact_check_resistance(self, value: float) -> None:
        """Set contact check resistance, in ohms."""
        self._write_float(":SYST:CCH:RES", value)

    @property
    def guard_mode(self) -> str:
        """Selected guard mode; documented choices are OHMS or CABLE."""
        return self._query(":SYST:GUAR?").upper()

    @guard_mode.setter
    def guard_mode(self, value: str) -> None:
        """Set guard mode."""
        self._write(f":SYST:GUAR {value}")

    def initialize_memory(self) -> None:
        """Initialize battery-backed RAM; clears trace data and saved setups."""
        self._write(":SYST:MEM:INIT")

    def beep(self, frequency: float, duration: float) -> None:
        """Sound the front-panel beeper at the requested frequency and duration.

        Parameters
        ----------
        frequency : float
            Tone frequency in hertz.
        duration : float
            Tone duration in seconds.
        """
        self._write(f":SYST:BEEP {frequency:.12g},{duration:.12g}")

    @property
    def beeper_enabled(self) -> bool:
        """Whether beeper is enabled."""
        return self._query_bool(":SYST:BEEP:STAT?")

    @beeper_enabled.setter
    def beeper_enabled(self, enabled: bool) -> None:
        """Set beeper enabled."""
        self._write_bool(":SYST:BEEP:STAT", enabled)

    @property
    def auto_zero(self) -> str:
        """Auto-zero state: ON, OFF, or ONCE; ONCE performs an immediate update."""
        return self._query(":SYST:AZER:STAT?").upper()

    @auto_zero.setter
    def auto_zero(self, state: str) -> None:
        """Set auto zero."""
        self._write(f":SYST:AZER:STAT {state}")

    @property
    def nplc_caching(self) -> bool:
        """Whether the instrument caches zero/reference values for multiple NPLC
        settings.
        """
        return self._query_bool(":SYST:AZER:CACH?")

    @nplc_caching.setter
    def nplc_caching(self, enabled: bool) -> None:
        """Set nplc caching."""
        self._write_bool(":SYST:AZER:CACH", enabled)

    @property
    def cached_nplc_values(self) -> tuple[float, ...]:
        """Cached integration-time settings, as a tuple of power-line-cycle values."""
        return self._query_floats(":SYST:AZER:CACH:NPLC?")

    def refresh_nplc_cache(self) -> None:
        """Refresh the instrument's NPLC cache."""
        self._write(":SYST:AZER:CACH:REFR")

    def reset_nplc_cache(self) -> None:
        """Reset the instrument's NPLC cache."""
        self._write(":SYST:AZER:CACH:RES")

    @property
    def line_frequency(self) -> int:
        """Selected mains line frequency, in hertz; 50 or 60 Hz (use 50 Hz for 400 Hz
        mains).
        """
        return self._query_int(":SYST:LFR?")

    @line_frequency.setter
    def line_frequency(self, value: int) -> None:
        """Set line frequency, in hertz."""
        self._write_int(":SYST:LFR", value)

    @property
    def auto_line_frequency(self) -> bool:
        """Whether the instrument automatically selects the mains line frequency."""
        return self._query_bool(":SYST:LFR:AUTO?")

    @auto_line_frequency.setter
    def auto_line_frequency(self, enabled: bool) -> None:
        """Set auto line frequency."""
        self._write_bool(":SYST:LFR:AUTO", enabled)

    def read_error(self) -> str:
        """Read and remove the oldest error/status message from the error queue.

        Returns
        -------
        str
            Raw numeric code and quoted message, or the no-error response.
        """
        return self._query(":SYST:ERR?")

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
        return self._query(":SYST:ERR:ALL?")

    @property
    def error_count(self) -> int:
        """Number of queued error/status messages; reading does not remove entries."""
        return self._query_int(":SYST:ERR:COUN?")

    def read_error_code(self) -> int:
        """Read and remove the oldest queued error/status entry.

        Returns
        -------
        int
            Numeric code for the removed entry, or zero if the queue was empty.
        """
        return self._query_int(":SYST:ERR:CODE?")

    def read_error_codes(self) -> str:
        """Read and remove all queued error/status codes.

        Returns
        -------
        str
            Raw list of numeric codes, or the no-error response.
        """
        return self._query(":SYST:ERR:CODE:ALL?")

    def clear_errors(self) -> None:
        """Remove all messages from the instrument error queue."""
        self._write(":SYST:CLE")

    def press_key(self, key_code: int) -> None:
        """Simulate a front-panel key press using its documented numeric key code.

        Parameters
        ----------
        key_code : int
            Documented numeric front-panel key code.
        """
        self._write_int(":SYST:KEY", key_code)

    def read_last_key(self) -> int:
        """Read the key code queued by the last physical or simulated press."""
        return self._query_int(":SYST:KEY?")

    @property
    def scpi_version(self) -> str:
        """SCPI standard version implemented by the instrument, as a raw string."""
        return self._query(":SYST:VERS?")

    def local(self) -> None:
        """Return the instrument to local control (documented for RS-232)."""
        self._write(":SYST:LOC")

    @property
    def remote_lockout(self) -> bool:
        """Whether the front-panel LOCAL key is locked out (documented for RS-232)."""
        return self._query_bool(":SYST:RWLock?")

    @remote_lockout.setter
    def remote_lockout(self, enabled: bool) -> None:
        """Set remote lockout."""
        self._write_bool(":SYST:RWLock", enabled)

    @property
    def timestamp(self) -> float:
        """Timestamp, in seconds."""
        return self._query_float(":SYST:TIME?")

    def reset_timestamp(self) -> None:
        """Reset the instrument's timestamp."""
        self._write(":SYST:TIME:RES")

    @property
    def auto_reset_timestamp(self) -> bool:
        """Whether the timestamp resets automatically when a measurement sequence
        starts.
        """
        return self._query_bool(":SYST:TIME:RES:AUTO?")

    @auto_reset_timestamp.setter
    def auto_reset_timestamp(self, enabled: bool) -> None:
        """Set auto reset timestamp."""
        self._write_bool(":SYST:TIME:RES:AUTO", enabled)

    @property
    def range_change_mode(self) -> str:
        """Selected range change mode; documented choices are SINGLE or MULTIPLE."""
        return self._query(":SYST:RCM?").upper()

    @range_change_mode.setter
    def range_change_mode(self, mode: str) -> None:
        """Set range change mode."""
        self._write(f":SYST:RCM {mode}")

    # Trace buffer

    @property
    def trace_data(self) -> tuple[float, ...]:
        """Stored trace-buffer reading values, as a flat tuple of floats.

        The selected format and elements determine the reply layout. Instrument
        overflow and unavailable-value sentinels are preserved.
        """
        return self._query_data(":TRAC:DATA?")

    def clear_trace(self) -> None:
        """Remove stored readings from the trace buffer."""
        self._write(":TRAC:CLE")

    @property
    def trace_memory(self) -> tuple[int, int]:
        """Available and reserved trace memory, in bytes."""
        values = self._query(":TRAC:FREE?").split(",")
        if len(values) != 2:
            raise ValueError(
                "TRACE:FREE? must return available and reserved byte counts"
            )
        return (int(values[0]), int(values[1]))

    @property
    def trace_points(self) -> int:
        """Configured trace-buffer capacity, in readings (1–2500)."""
        return self._query_int(":TRAC:POIN?")

    @trace_points.setter
    def trace_points(self, count: int | str) -> None:
        """Set trace points."""
        self._write_int(":TRAC:POIN", count)

    @property
    def trace_points_actual(self) -> int:
        """Number of readings currently stored in the trace buffer."""
        return self._query_int(":TRAC:POIN:ACT?")

    @property
    def trace_feed(self) -> str:
        """Selected trace feed; documented choices are SENSE, CALC, or CALC2."""
        return self._query(":TRAC:FEED?").upper()

    @trace_feed.setter
    def trace_feed(self, feed: str) -> None:
        """Set trace feed."""
        self._write(f":TRAC:FEED {feed}")

    @property
    def trace_control(self) -> str:
        """Selected trace control; documented choices are NEXT or NEVER."""
        return self._query(":TRAC:FEED:CONT?").upper()

    @trace_control.setter
    def trace_control(self, control: str) -> None:
        """Set trace control."""
        self._write(f":TRAC:FEED:CONT {control}")

    @property
    def trace_timestamp_format(self) -> str:
        """Selected trace timestamp format; documented choices are ABSOLUTE or DELTA."""
        return self._query(":TRAC:TST:FORM?").upper()

    @trace_timestamp_format.setter
    def trace_timestamp_format(self, fmt: str) -> None:
        """Set trace timestamp format."""
        self._write(f":TRAC:TST:FORM {fmt}")

    # Arm and trigger controls

    def clear_triggers(self) -> None:
        """Clear trigger-model configuration using :TRIG:CLE."""
        self._write(":TRIG:CLE")

    def initiate(self) -> None:
        """Start the configured trigger sequence by taking the instrument out of idle.

        With automatic write-error checking enabled, the following error query can
        wait until the sequence finishes. Disable that checking for asynchronous
        initiation, then check errors explicitly after completion.
        """
        self._write(":INIT")

    def abort(self) -> None:
        """Stop the active trigger sequence and return the instrument to idle."""
        self._write(":ABOR")

    @property
    def arm_count(self) -> int | str:
        """Arm-layer count; returns INFINITE when the instrument sentinel 9.9e37 is
        reported.
        """
        count = self._query_float(":ARM:COUN?")
        return "INFINITE" if count == 9.9e37 else int(count)

    @arm_count.setter
    def arm_count(self, count: int | str) -> None:
        """Set arm count."""
        self._write_int(":ARM:COUN", count)

    @property
    def trigger_count(self) -> int:
        """Number of source-measure cycles per arm event."""
        return self._query_int(":TRIG:COUN?")

    @trigger_count.setter
    def trigger_count(self, count: int | str) -> None:
        """Set trigger count."""
        self._write_int(":TRIG:COUN", count)

    @property
    def arm_source(self) -> str:
        """Arm-event source: IMM, TLINK, TIMER, MANUAL, BUS, NSTEST, PSTEST, or
        BSTEST.
        """
        return self._query(":ARM:SOUR?").upper()

    @arm_source.setter
    def arm_source(self, source: str) -> None:
        """Set arm source."""
        self._write(f":ARM:SOUR {source}")

    @property
    def trigger_source(self) -> str:
        """Selected trigger source; documented choices are IMMEDIATE or TLINK."""
        return self._query(":TRIG:SOUR?").upper()

    @trigger_source.setter
    def trigger_source(self, source: str) -> None:
        """Set trigger source."""
        self._write(f":TRIG:SOUR {source}")

    @property
    def trigger_delay(self) -> float:
        """Delay between a trigger event and its source-measure cycle, in seconds."""
        return self._query_float(":TRIG:DEL?")

    @trigger_delay.setter
    def trigger_delay(self, delay: float | str) -> None:
        """Set trigger delay, in seconds."""
        self._write_float(":TRIG:DEL", delay)

    @property
    def arm_timer(self) -> float:
        """Interval between timer-controlled arm events, in seconds."""
        return self._query_float(":ARM:TIM?")

    @arm_timer.setter
    def arm_timer(self, seconds: float | str) -> None:
        """Set arm timer, in seconds."""
        self._write_float(":ARM:TIM", seconds)

    @property
    def arm_bypass(self) -> str:
        """Arm-event bypass direction: SOURCE or ACCEPTOR."""
        return self._query(":ARM:DIR?").upper()

    @arm_bypass.setter
    def arm_bypass(self, direction: str) -> None:
        """Set arm bypass."""
        self._write(f":ARM:DIR {direction}")

    @property
    def trigger_bypass(self) -> str:
        """Trigger-event bypass direction: SOURCE or ACCEPTOR."""
        return self._query(":TRIG:DIR?").upper()

    @trigger_bypass.setter
    def trigger_bypass(self, direction: str) -> None:
        """Set trigger bypass."""
        self._write(f":TRIG:DIR {direction}")

    @property
    def arm_input_line(self) -> int:
        """Trigger Link input line used for arm events (1–4)."""
        return self._query_int(":ARM:ILIN?")

    @arm_input_line.setter
    def arm_input_line(self, line: int) -> None:
        """Set arm input line."""
        self._write_int(":ARM:ILIN", line)

    @property
    def trigger_input_line(self) -> int:
        """Trigger Link input line used for trigger events (1–4)."""
        return self._query_int(":TRIG:ILIN?")

    @trigger_input_line.setter
    def trigger_input_line(self, line: int) -> None:
        """Set trigger input line."""
        self._write_int(":TRIG:ILIN", line)

    @property
    def arm_output_line(self) -> int:
        """Trigger Link output line used for arm events (1–4)."""
        return self._query_int(":ARM:OLIN?")

    @arm_output_line.setter
    def arm_output_line(self, line: int) -> None:
        """Set arm output line."""
        self._write_int(":ARM:OLIN", line)

    @property
    def trigger_output_line(self) -> int:
        """Trigger Link output line used for trigger events (1–4)."""
        return self._query_int(":TRIG:OLIN?")

    @trigger_output_line.setter
    def trigger_output_line(self, line: int) -> None:
        """Set trigger output line."""
        self._write_int(":TRIG:OLIN", line)

    @property
    def arm_output_events(self) -> tuple[str, ...]:
        """Arm events that produce an output pulse: TENTER, TEXIT, or NONE."""
        return self._tokens(self._query(":ARM:OUTP?"))

    @arm_output_events.setter
    def arm_output_events(self, events: str | Sequence[str]) -> None:
        """Set arm output events."""
        self._write_event_list(":ARM:OUTP", events)

    @property
    def trigger_output_events(self) -> tuple[str, ...]:
        """Trigger stages that produce output pulses: SOURCE, DELAY, SENSE, or NONE."""
        return self._tokens(self._query(":TRIG:OUTP?"))

    @trigger_output_events.setter
    def trigger_output_events(self, events: str | Sequence[str]) -> None:
        """Set trigger output events."""
        self._write_event_list(":TRIG:OUTP", events)

    @property
    def trigger_input_events(self) -> tuple[str, ...]:
        """Trigger stages requiring input events: SOURCE, DELAY, SENSE, or NONE."""
        return self._tokens(self._query(":TRIG:INP?"))

    @trigger_input_events.setter
    def trigger_input_events(self, events: str | Sequence[str]) -> None:
        """Set trigger input events."""
        self._write_event_list(":TRIG:INP", events)

    @property
    def contact_check_event_source(self) -> str:
        """Contact-check event source: CCHECK or IMM.

        Requires an instrument supporting the contact-check option.
        """
        return self._query(":TRIG:SEQ2:SOUR?").upper()

    @contact_check_event_source.setter
    def contact_check_event_source(self, source: str) -> None:
        """Set contact check event source."""
        self._write(f":TRIG:SEQ2:SOUR {source}")

    @property
    def contact_check_timeout(self) -> float:
        """Contact-check event timeout, in seconds; zero permits an indefinite wait.

        Requires an instrument supporting the contact-check option.
        """
        return self._query_float(":TRIG:SEQ2:TOUT?")

    @contact_check_timeout.setter
    def contact_check_timeout(self, seconds: float) -> None:
        """Set contact check timeout, in seconds."""
        self._write_float(":TRIG:SEQ2:TOUT", seconds)

    def set_mep_holdoff(self, enabled: bool) -> None:
        """Set Appendix G NDAC holdoff (no query is documented).

        Parameters
        ----------
        enabled : bool
            True enables NDAC holdoff; False disables it.
        """
        self._write_bool(":SYST:MEP:HOLD", enabled)

    @property
    def scpi_protocol_enabled(self) -> bool:
        """Query MEP state; true indicates SCPI protocol, false indicates 488.1."""
        return self._query_bool(":SYST:MEP?")

    # Acquiring measurements

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
        return self._query_data(":READ?")

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
        return self._query_data(":FETC?")

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
        return self._query_data(":MEAS?" if function is None else f":MEAS:{function}?")

    def configure_measurement(self, function: str) -> None:
        """Configure a one-shot measurement and turn the source output on.

        The instrument resets the selected function to its defaults, selects
        immediate single-reading triggers, and disables math and trace operation.

        Parameters
        ----------
        function : str
            Measurement function: VOLT, CURR, or RES.
        """
        self._write(f":CONF:{function}")

    @property
    def configured_measurement(self) -> tuple[str, ...]:
        """Configured measurement function tokens returned by :CONF?.

        Returns
        -------
        tuple[str, ...]
            Value decoded from the instrument response.
        """
        return self._tokens(self._query(":CONF?"))

    @property
    def sense_data_latest(self) -> tuple[float, ...]:
        """Latest measurement values, as a flat tuple of floats.

        The selected format and elements determine the reply layout. Instrument
        overflow and unavailable-value sentinels are preserved.
        """
        return self._query_floats(":SENS:DATA?")

    @staticmethod
    def _tokens(value: str) -> tuple[str, ...]:
        """Split a comma-separated response into nonempty, stripped, uppercase tokens."""
        return tuple(
            (
                part.strip().strip('"').upper()
                for part in value.split(",")
                if part.strip()
            )
        )

    @property
    def trace_points_minimum(self) -> float:
        """Instrument-reported minimum value for trace points."""
        return self._query_float(":TRAC:POIN? MIN")

    @property
    def trace_points_maximum(self) -> float:
        """Instrument-reported maximum value for trace points."""
        return self._query_float(":TRAC:POIN? MAX")

    @property
    def trace_points_default(self) -> float:
        """Instrument-reported default value for trace points."""
        return self._query_float(":TRAC:POIN? DEF")

    @property
    def arm_count_minimum(self) -> float:
        """Instrument-reported minimum value for arm count."""
        return self._query_float(":ARM:COUN? MIN")

    @property
    def arm_count_maximum(self) -> float:
        """Instrument-reported maximum value for arm count."""
        return self._query_float(":ARM:COUN? MAX")

    @property
    def arm_count_default(self) -> float:
        """Instrument-reported default value for arm count."""
        return self._query_float(":ARM:COUN? DEF")

    @property
    def trigger_count_minimum(self) -> float:
        """Instrument-reported minimum value for trigger count."""
        return self._query_float(":TRIG:COUN? MIN")

    @property
    def trigger_count_maximum(self) -> float:
        """Instrument-reported maximum value for trigger count."""
        return self._query_float(":TRIG:COUN? MAX")

    @property
    def trigger_count_default(self) -> float:
        """Instrument-reported default value for trigger count."""
        return self._query_float(":TRIG:COUN? DEF")

    @property
    def trigger_delay_minimum(self) -> float:
        """Instrument-reported minimum value for trigger delay in seconds."""
        return self._query_float(":TRIG:DEL? MIN")

    @property
    def trigger_delay_maximum(self) -> float:
        """Instrument-reported maximum value for trigger delay in seconds."""
        return self._query_float(":TRIG:DEL? MAX")

    @property
    def trigger_delay_default(self) -> float:
        """Instrument-reported default value for trigger delay in seconds."""
        return self._query_float(":TRIG:DEL? DEF")

    @property
    def arm_timer_minimum(self) -> float:
        """Instrument-reported minimum value for arm timer in seconds."""
        return self._query_float(":ARM:TIM? MIN")

    @property
    def arm_timer_maximum(self) -> float:
        """Instrument-reported maximum value for arm timer in seconds."""
        return self._query_float(":ARM:TIM? MAX")

    @property
    def arm_timer_default(self) -> float:
        """Instrument-reported default value for arm timer in seconds."""
        return self._query_float(":ARM:TIM? DEF")

    # Source, sense, and output settings

    @property
    def source_function(self) -> str:
        """Selected source function; documented choices are VOLT, CURR, or MEM."""
        return self._query(":SOUR:FUNC?").strip('"').upper()

    @source_function.setter
    def source_function(self, value: str) -> None:
        """Set source function; choices: VOLT, CURR, or MEM."""
        self._write(f":SOUR:FUNC {value}")

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
        """Whether more than one measurement function can be enabled simultaneously."""
        return self._query_bool(":SENS:FUNC:CONC?")

    @sense_concurrent.setter
    def sense_concurrent(self, enabled: bool) -> None:
        """Set sense concurrent."""
        self._write_bool(":SENS:FUNC:CONC", enabled)

    @property
    def enabled_sense_function_count(self) -> int:
        """Number of enabled measurement functions."""
        return self._query_int(":SENS:FUNC:ON:COUN?")

    @property
    def disabled_sense_function_count(self) -> int:
        """Number of disabled measurement functions."""
        return self._query_int(":SENS:FUNC:OFF:COUN?")

    @property
    def disabled_sense_functions(self) -> tuple[str, ...]:
        """Disabled measurement functions as VOLT, CURR, and RES tokens."""
        raw = self._query(":SENS:FUNC:OFF?").replace('"', "")
        return tuple(
            (
                part.strip().removesuffix(":DC")
                for part in raw.split(",")
                if part.strip()
            )
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
        for value in functions:
            self._write_str(":SENS:FUNC:ON", value)

    def disable_sense_functions(self, functions: Sequence[str]) -> None:
        """Disable each requested measurement function using separate commands.

        Parameters
        ----------
        functions : Sequence[str]
            Functions to disable, such as VOLT, CURR, or RES.
        """
        for value in functions:
            self._write_str(":SENS:FUNC:OFF", value)

    def enable_all_sense_functions(self) -> None:
        """Enable all supported sense functions."""
        self._write(":SENS:FUNC:ON:ALL")

    def disable_all_sense_functions(self) -> None:
        """Disable all sense functions."""
        self._write(":SENS:FUNC:OFF:ALL")

    def sense_function_enabled(self, function: str) -> bool:
        """Whether the specified VOLT, CURR, or RES sense function is enabled.

        Parameters
        ----------
        function : str
            VOLT, CURR, or RES.
        """
        self._verify_sense_function(function)
        return self._query_bool(f':SENS:FUNC:STAT? "{function}"')

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
        return self._query_float(":SENS:CURR:PROT?")

    @current_compliance.setter
    def current_compliance(self, value: float | str) -> None:
        """Set current compliance, in amperes."""
        self._write_float(":SENS:CURR:PROT", value)

    @property
    def voltage_compliance(self) -> float:
        """Voltage compliance setting for current sourcing, in volts."""
        return self._query_float(":SENS:VOLT:PROT?")

    @voltage_compliance.setter
    def voltage_compliance(self, value: float | str) -> None:
        """Set voltage compliance, in volts."""
        self._write_float(":SENS:VOLT:PROT", value)

    @property
    def current_compliance_tripped(self) -> bool:
        """Whether the current compliance limit has been reached."""
        return self._query_bool(":SENS:CURR:PROT:TRIP?")

    @property
    def voltage_compliance_tripped(self) -> bool:
        """Whether the voltage compliance limit has been reached."""
        return self._query_bool(":SENS:VOLT:PROT:TRIP?")

    @property
    def current_range_synchronized(self) -> bool:
        """Whether the measurement range follows the compliance range.

        The current and voltage synchronization properties control the same
        setting.
        """
        return self._query_bool(":SENS:CURR:PROT:RSYN?")

    @current_range_synchronized.setter
    def current_range_synchronized(self, enabled: bool) -> None:
        """Set current range synchronized."""
        self._write_bool(":SENS:CURR:PROT:RSYN", enabled)

    @property
    def voltage_range_synchronized(self) -> bool:
        """Whether the measurement range follows the compliance range.

        The current and voltage synchronization properties control the same
        setting.
        """
        return self._query_bool(":SENS:VOLT:PROT:RSYN?")

    @voltage_range_synchronized.setter
    def voltage_range_synchronized(self, enabled: bool) -> None:
        """Set voltage range synchronized."""
        self._write_bool(":SENS:VOLT:PROT:RSYN", enabled)

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
        return self._query(":SENS:RES:MODE?").upper()

    @resistance_mode.setter
    def resistance_mode(self, value: str) -> None:
        """Set resistance mode."""
        self._write(f":SENS:RES:MODE {value}")

    @property
    def offset_compensated_ohms(self) -> bool:
        """Whether offset-compensated resistance measurement is enabled."""
        return self._query_bool(":SENS:RES:OCOM?")

    @offset_compensated_ohms.setter
    def offset_compensated_ohms(self, value: bool) -> None:
        """Set offset compensated ohms."""
        self._write_bool(":SENS:RES:OCOM", value)

    @property
    def voltage_protection(self) -> float:
        """Source-voltage protection threshold, in volts."""
        return self._query_float(":SOUR:VOLT:PROT?")

    @voltage_protection.setter
    def voltage_protection(self, value: float | str) -> None:
        """Set voltage protection, in volts."""
        self._write_float(":SOUR:VOLT:PROT", value)

    @property
    def voltage_protection_tripped(self) -> bool:
        """Whether the source-voltage protection threshold has been reached."""
        return self._query_bool(":SOUR:VOLT:PROT:TRIP?")

    @property
    def average_type(self) -> str:
        """Averaging filter type: REPEAT or MOVING."""
        return self._query(":SENS:AVER:TCON?").upper()

    @average_type.setter
    def average_type(self, value: str) -> None:
        """Set average type."""
        self._write(f":SENS:AVER:TCON {value}")

    @property
    def average_count(self) -> int:
        """Number of readings used by the averaging filter."""
        return self._query_int(":SENS:AVER:COUN?")

    @average_count.setter
    def average_count(self, value: int | str) -> None:
        """Set average count."""
        self._write_int(":SENS:AVER:COUN", value)

    @property
    def averaging_enabled(self) -> bool:
        """Whether the measurement averaging filter is enabled."""
        return self._query_bool(":SENS:AVER:STAT?")

    @averaging_enabled.setter
    def averaging_enabled(self, value: bool) -> None:
        """Set averaging enabled."""
        self._write_bool(":SENS:AVER:STAT", value)

    @property
    def output_enabled(self) -> bool:
        """Whether output is enabled."""
        return self._query_bool(":OUTP:STAT?")

    @output_enabled.setter
    def output_enabled(self, value: bool) -> None:
        """Set output enabled."""
        self._write_bool(":OUTP:STAT", value)

    @property
    def output_enable(self) -> bool:
        """Whether the external output-enable input is permitted to enable output.

        Uses the IENABle path in the detailed command reference; the summary table
        gives a different spelling. This path has not been hardware-verified.
        """
        return self._query_bool(":OUTP:IENAB:STAT?")

    @output_enable.setter
    def output_enable(self, value: bool) -> None:
        """Set whether the external output-enable input is active."""
        self._write_bool(":OUTP:IENAB:STAT", value)

    @property
    def output_enable_tripped(self) -> bool:
        """Whether the output-enable input prevents operation (device replies 0)."""
        return not self._query_bool(":OUTP:ENAB:TRIP?")

    @property
    def output_off_mode(self) -> str:
        """Output-off behavior: HIMP, NORMAL, ZERO, or GUARD."""
        return self._query(":OUTP:SMOD?").upper()

    @output_off_mode.setter
    def output_off_mode(self, value: str) -> None:
        """Set output off mode."""
        value = value.upper()
        self._write(f":OUTP:SMOD {value}")

    @property
    def terminals(self) -> str:
        """Selected terminals; documented choices are FRONT or REAR."""
        return self._query(":ROUT:TERM?").upper()

    @terminals.setter
    def terminals(self, value: str) -> None:
        """Set terminals."""
        value = value.upper()
        self._write(f":ROUT:TERM {value}")

    def clear_source(self) -> None:
        """Turn off the source output using :SOUR:CLE:IMM."""
        self._write(":SOUR:CLE:IMM")

    @property
    def auto_output_off(self) -> bool:
        """Whether the output turns on and off automatically for measurement cycles."""
        return self._query_bool(":SOUR:CLE:AUTO?")

    @auto_output_off.setter
    def auto_output_off(self, value: bool) -> None:
        """Set auto output off."""
        self._write_bool(":SOUR:CLE:AUTO", value)

    @property
    def auto_output_off_mode(self) -> str:
        """Automatic output-off schedule: ALWAYS or TCOUNT."""
        return self._query(":SOUR:CLE:AUTO:MODE?").upper()

    @auto_output_off_mode.setter
    def auto_output_off_mode(self, value: str) -> None:
        """Set auto output off mode."""
        value = value.upper()
        self._write(f":SOUR:CLE:AUTO:MODE {value}")

    @property
    def source_delay(self) -> float:
        """Settling delay before measurement, in seconds."""
        return self._query_float(":SOUR:DEL?")

    @source_delay.setter
    def source_delay(self, value: float | str) -> None:
        """Set source delay, in seconds."""
        self._write_float(":SOUR:DEL", value)

    @property
    def source_delay_auto(self) -> bool:
        """Whether the instrument adds its automatic source-settling delay."""
        return self._query_bool(":SOUR:DEL:AUTO?")

    @source_delay_auto.setter
    def source_delay_auto(self, value: bool) -> None:
        """Set source delay auto."""
        self._write_bool(":SOUR:DEL:AUTO", value)

    @property
    def sweep_spacing(self) -> str:
        """Selected sweep spacing; documented choices are LINEAR or LOGARITHMIC."""
        return self._query(":SOUR:SWE:SPAC?").upper()

    @sweep_spacing.setter
    def sweep_spacing(self, value: str) -> None:
        """Set sweep spacing."""
        self._write(f":SOUR:SWE:SPAC {value}")

    @property
    def sweep_points(self) -> int:
        """Number of source points in a staircase sweep."""
        return self._query_int(":SOUR:SWE:POIN?")

    @sweep_points.setter
    def sweep_points(self, value: int | str) -> None:
        """Set sweep points."""
        self._write_int(":SOUR:SWE:POIN", value)

    @property
    def sweep_direction(self) -> str:
        """Selected sweep direction; documented choices are UP or DOWN."""
        return self._query(":SOUR:SWE:DIR?").upper()

    @sweep_direction.setter
    def sweep_direction(self, value: str) -> None:
        """Set sweep direction."""
        self._write(f":SOUR:SWE:DIR {value}")

    @property
    def sweep_ranging(self) -> str:
        """Sweep source-ranging policy: BEST, AUTO, or FIXED."""
        return self._query(":SOUR:SWE:RANG?").upper()

    @sweep_ranging.setter
    def sweep_ranging(self, value: str) -> None:
        """Set sweep ranging."""
        self._write(f":SOUR:SWE:RANG {value}")

    @property
    def sweep_compliance_abort(self) -> str:
        """Sweep-abort policy on compliance: NEVER, EARLY, or LATE."""
        return self._query(":SOUR:SWE:CAB?").upper()

    @sweep_compliance_abort.setter
    def sweep_compliance_abort(self, value: str) -> None:
        """Set sweep compliance abort."""
        self._write(f":SOUR:SWE:CAB {value}")

    @property
    def sweep_soak(self) -> float:
        """Delay at the initial sweep level before measurement begins, in seconds."""
        return self._query_float(":SOUR:SOAK?")

    @sweep_soak.setter
    def sweep_soak(self, value: float | str) -> None:
        """Set sweep soak, in seconds."""
        self._write_float(":SOUR:SOAK", value)

    @property
    def memory_points(self) -> int:
        """Number of source-memory locations included in a memory sweep."""
        return self._query_int(":SOUR:MEM:POIN?")

    @memory_points.setter
    def memory_points(self, value: int) -> None:
        """Set memory points."""
        self._write_int(":SOUR:MEM:POIN", value)

    @property
    def memory_start(self) -> int:
        """First source-memory location used by a memory sweep."""
        return self._query_int(":SOUR:MEM:STAR?")

    @memory_start.setter
    def memory_start(self, value: int) -> None:
        """Set memory start."""
        self._write_int(":SOUR:MEM:STAR", value)

    def save_memory(self, location: int) -> None:
        """Save the current memory to instrument memory.

        Parameters
        ----------
        location : int
            Source-memory location to save.
        """
        self._write_int(":SOUR:MEM:SAVE", location)

    def recall_memory(self, location: int) -> None:
        """Recall the memory from instrument memory.

        Parameters
        ----------
        location : int
            Source-memory location to recall.
        """
        self._write_int(":SOUR:MEM:RECall", location)

    @property
    def pulse_shape(self) -> str:
        """Source waveform: DC or PULSE; pulse mode is specific to model 2430."""
        return self._query(":SOUR:FUNC:SHAP?").upper()

    @pulse_shape.setter
    def pulse_shape(self, value: str) -> None:
        """Set pulse shape."""
        self._write(f":SOUR:FUNC:SHAP {value}")

    @property
    def pulse_width(self) -> float:
        """Pulse width, in seconds; supported by model 2430."""
        return self._query_float(":SOUR:PULS:WIDT?")

    @pulse_width.setter
    def pulse_width(self, value: float | str) -> None:
        """Set pulse width, in seconds."""
        self._write_float(":SOUR:PULS:WIDT", value)

    @property
    def pulse_delay(self) -> float:
        """Pulse delay, in seconds; supported by model 2430."""
        return self._query_float(":SOUR:PULS:DEL?")

    @pulse_delay.setter
    def pulse_delay(self, value: float | str) -> None:
        """Set pulse delay, in seconds."""
        self._write_float(":SOUR:PULS:DEL", value)

    @property
    def digital_bit_size(self) -> int:
        """Digital I/O port width: 3 or 4 bits, or 16 with the 2499-DIGIO option."""
        return self._query_int(":SOUR2:BSIZ?")

    @digital_bit_size.setter
    def digital_bit_size(self, value: int) -> None:
        """Set digital bit size."""
        self._write_int(":SOUR2:BSIZ", value)

    @property
    def digital_output_pattern(self) -> int:
        """Programmed digital output bit pattern, as an integer."""
        return self._query_int(":SOUR2:TTL:LEV:DEF?")

    @digital_output_pattern.setter
    def digital_output_pattern(self, value: int) -> None:
        """Set digital output pattern."""
        self._write_int(":SOUR2:TTL:LEV:DEF", value)

    @property
    def digital_output_actual(self) -> int:
        """Actual digital output bit pattern, as an integer."""
        return self._query_int(":SOUR2:TTL:LEV:ACT?")

    @property
    def digital_line4_mode(self) -> str:
        """Digital line 4 function: EOT or BUSY."""
        return self._query(":SOUR2:TTL4:MODE?").upper()

    @digital_line4_mode.setter
    def digital_line4_mode(self, value: str) -> None:
        """Set digital line4 mode."""
        self._write(f":SOUR2:TTL4:MODE {value}")

    @property
    def digital_busy_polarity(self) -> str:
        """Digital EOT/BUSY signal polarity: HI or LO."""
        return self._query(":SOUR2:TTL4:BST?").upper()

    @digital_busy_polarity.setter
    def digital_busy_polarity(self, value: str) -> None:
        """Set digital busy polarity."""
        self._write(f":SOUR2:TTL4:BST {value}")

    def clear_digital_output(self) -> None:
        """Clear all digital output lines."""
        self._write(":SOUR2:CLE:IMM")

    @property
    def digital_clear_auto(self) -> bool:
        """Whether digital outputs clear automatically."""
        return self._query_bool(":SOUR2:CLE:AUTO?")

    @digital_clear_auto.setter
    def digital_clear_auto(self, value: bool) -> None:
        """Set digital clear auto."""
        self._write_bool(":SOUR2:CLE:AUTO", value)

    @property
    def digital_clear_delay(self) -> float:
        """Delay before automatically clearing digital outputs, in seconds."""
        return self._query_float(":SOUR2:CLE:AUTO:DEL?")

    @digital_clear_delay.setter
    def digital_clear_delay(self, value: float | str) -> None:
        """Set digital clear delay, in seconds."""
        self._write_float(":SOUR2:CLE:AUTO:DEL", value)

    @property
    def current_compliance_minimum(self) -> float:
        """Instrument-reported minimum value for current compliance in amperes."""
        return self._query_float(":SENS:CURR:PROT? MIN")

    @property
    def current_compliance_maximum(self) -> float:
        """Instrument-reported maximum value for current compliance in amperes."""
        return self._query_float(":SENS:CURR:PROT? MAX")

    @property
    def current_compliance_default(self) -> float:
        """Instrument-reported default value for current compliance in amperes."""
        return self._query_float(":SENS:CURR:PROT? DEF")

    @property
    def voltage_compliance_minimum(self) -> float:
        """Instrument-reported minimum value for voltage compliance in volts."""
        return self._query_float(":SENS:VOLT:PROT? MIN")

    @property
    def voltage_compliance_maximum(self) -> float:
        """Instrument-reported maximum value for voltage compliance in volts."""
        return self._query_float(":SENS:VOLT:PROT? MAX")

    @property
    def voltage_compliance_default(self) -> float:
        """Instrument-reported default value for voltage compliance in volts."""
        return self._query_float(":SENS:VOLT:PROT? DEF")

    @property
    def average_count_minimum(self) -> float:
        """Instrument-reported minimum value for average count."""
        return self._query_float(":SENS:AVER:COUN? MIN")

    @property
    def average_count_maximum(self) -> float:
        """Instrument-reported maximum value for average count."""
        return self._query_float(":SENS:AVER:COUN? MAX")

    @property
    def average_count_default(self) -> float:
        """Instrument-reported default value for average count."""
        return self._query_float(":SENS:AVER:COUN? DEF")

    @property
    def voltage_protection_minimum(self) -> float:
        """Instrument-reported minimum value for voltage protection in volts."""
        return self._query_float(":SOUR:VOLT:PROT? MIN")

    @property
    def voltage_protection_maximum(self) -> float:
        """Instrument-reported maximum value for voltage protection in volts."""
        return self._query_float(":SOUR:VOLT:PROT? MAX")

    @property
    def voltage_protection_default(self) -> float:
        """Instrument-reported default value for voltage protection in volts."""
        return self._query_float(":SOUR:VOLT:PROT? DEF")

    @property
    def source_delay_minimum(self) -> float:
        """Instrument-reported minimum value for source delay in seconds."""
        return self._query_float(":SOUR:DEL? MIN")

    @property
    def source_delay_maximum(self) -> float:
        """Instrument-reported maximum value for source delay in seconds."""
        return self._query_float(":SOUR:DEL? MAX")

    @property
    def source_delay_default(self) -> float:
        """Instrument-reported default value for source delay in seconds."""
        return self._query_float(":SOUR:DEL? DEF")

    @property
    def sweep_points_minimum(self) -> float:
        """Instrument-reported minimum value for sweep points."""
        return self._query_float(":SOUR:SWE:POIN? MIN")

    @property
    def sweep_points_maximum(self) -> float:
        """Instrument-reported maximum value for sweep points."""
        return self._query_float(":SOUR:SWE:POIN? MAX")

    @property
    def sweep_points_default(self) -> float:
        """Instrument-reported default value for sweep points."""
        return self._query_float(":SOUR:SWE:POIN? DEF")

    @property
    def pulse_width_minimum(self) -> float:
        """Instrument-reported minimum value for pulse width in seconds."""
        return self._query_float(":SOUR:PULS:WIDT? MIN")

    @property
    def pulse_width_maximum(self) -> float:
        """Instrument-reported maximum value for pulse width in seconds."""
        return self._query_float(":SOUR:PULS:WIDT? MAX")

    @property
    def pulse_width_default(self) -> float:
        """Instrument-reported default value for pulse width in seconds."""
        return self._query_float(":SOUR:PULS:WIDT? DEF")

    @property
    def pulse_delay_minimum(self) -> float:
        """Instrument-reported minimum value for pulse delay in seconds."""
        return self._query_float(":SOUR:PULS:DEL? MIN")

    @property
    def pulse_delay_maximum(self) -> float:
        """Instrument-reported maximum value for pulse delay in seconds."""
        return self._query_float(":SOUR:PULS:DEL? MAX")

    @property
    def pulse_delay_default(self) -> float:
        """Instrument-reported default value for pulse delay in seconds."""
        return self._query_float(":SOUR:PULS:DEL? DEF")

    @property
    def digital_clear_delay_minimum(self) -> float:
        """Instrument-reported minimum value for digital clear delay in seconds."""
        return self._query_float(":SOUR2:CLE:AUTO:DEL? MIN")

    @property
    def digital_clear_delay_maximum(self) -> float:
        """Instrument-reported maximum value for digital clear delay in seconds."""
        return self._query_float(":SOUR2:CLE:AUTO:DEL? MAX")

    @property
    def digital_clear_delay_default(self) -> float:
        """Instrument-reported default value for digital clear delay in seconds."""
        return self._query_float(":SOUR2:CLE:AUTO:DEL? DEF")

    # Source voltage

    @property
    def source_voltage_mode(self) -> str:
        """Selected source voltage mode: FIX, SWEEP, or LIST."""
        return self._query(":SOUR:VOLT:MODE?").upper()

    @source_voltage_mode.setter
    def source_voltage_mode(self, value: str) -> None:
        """Set source voltage mode; choices: FIX, SWEEP, or LIST."""
        value = value.upper()
        self._write(f":SOUR:VOLT:MODE {value}")

    @property
    def source_voltage_level(self) -> float:
        """Source voltage level, in volts."""
        return self._query_float(":SOUR:VOLT:LEV?")

    @source_voltage_level.setter
    def source_voltage_level(self, value: float | str) -> None:
        """Set source voltage level, in volts."""
        self._write_float(":SOUR:VOLT:LEV", value)

    @property
    def source_voltage_range(self) -> float:
        """Source voltage range, in volts."""
        return self._query_float(":SOUR:VOLT:RANG?")

    @source_voltage_range.setter
    def source_voltage_range(self, value: float | str) -> None:
        """Set source voltage range, in volts."""
        self._write_float(":SOUR:VOLT:RANG", value)

    @property
    def source_voltage_auto_range(self) -> bool:
        """Whether the voltage source selects its range automatically."""
        return self._query_bool(":SOUR:VOLT:RANG:AUTO?")

    @source_voltage_auto_range.setter
    def source_voltage_auto_range(self, value: bool) -> None:
        """Set source voltage auto range."""
        self._write_bool(":SOUR:VOLT:RANG:AUTO", value)

    @property
    def source_voltage_start(self) -> float:
        """Staircase voltage sweep starting level, in volts."""
        return self._query_float(":SOUR:VOLT:STAR?")

    @source_voltage_start.setter
    def source_voltage_start(self, value: float | str) -> None:
        """Set source voltage start, in volts."""
        self._write_float(":SOUR:VOLT:STAR", value)

    @property
    def source_voltage_stop(self) -> float:
        """Staircase voltage sweep ending level, in volts."""
        return self._query_float(":SOUR:VOLT:STOP?")

    @source_voltage_stop.setter
    def source_voltage_stop(self, value: float | str) -> None:
        """Set source voltage stop, in volts."""
        self._write_float(":SOUR:VOLT:STOP", value)

    @property
    def source_voltage_step(self) -> float:
        """Staircase voltage sweep step size, in volts."""
        return self._query_float(":SOUR:VOLT:STEP?")

    @source_voltage_step.setter
    def source_voltage_step(self, value: float | str) -> None:
        """Set source voltage step, in volts."""
        self._write_float(":SOUR:VOLT:STEP", value)

    @property
    def source_voltage_center(self) -> float:
        """Staircase voltage sweep center level, in volts."""
        return self._query_float(":SOUR:VOLT:CENT?")

    @source_voltage_center.setter
    def source_voltage_center(self, value: float | str) -> None:
        """Set source voltage center, in volts."""
        self._write_float(":SOUR:VOLT:CENT", value)

    @property
    def source_voltage_span(self) -> float:
        """Staircase voltage sweep span, in volts."""
        return self._query_float(":SOUR:VOLT:SPAN?")

    @source_voltage_span.setter
    def source_voltage_span(self, value: float | str) -> None:
        """Set source voltage span, in volts."""
        self._write_float(":SOUR:VOLT:SPAN", value)

    @property
    def source_voltage_triggered_level(self) -> float:
        """Voltage level applied on a source trigger, in volts."""
        return self._query_float(":SOUR:VOLT:LEV:TRIG?")

    @source_voltage_triggered_level.setter
    def source_voltage_triggered_level(self, value: float | str) -> None:
        """Set source voltage triggered level, in volts."""
        self._write_float(":SOUR:VOLT:LEV:TRIG", value)

    @property
    def source_voltage_scaling_factor(self) -> float:
        """Dimensionless scaling factor applied to triggered voltage source levels."""
        return self._query_float(":SOUR:VOLT:LEV:TRIG:SFAC?")

    @source_voltage_scaling_factor.setter
    def source_voltage_scaling_factor(self, value: float | str) -> None:
        """Set the dimensionless scaling factor for triggered source levels."""
        self._write_float(":SOUR:VOLT:LEV:TRIG:SFAC", value)

    @property
    def source_voltage_scaling_enabled(self) -> bool:
        """Whether triggered voltage source scaling is enabled."""
        return self._query_bool(":SOUR:VOLT:LEV:TRIG:SFAC:STAT?")

    @source_voltage_scaling_enabled.setter
    def source_voltage_scaling_enabled(self, value: bool) -> None:
        """Set source voltage scaling enabled."""
        self._write_bool(":SOUR:VOLT:LEV:TRIG:SFAC:STAT", value)

    @property
    def source_voltage_list_values(self) -> tuple[float, ...]:
        """Voltage source list values as a tuple, in volts; setters accept a sequence."""
        return self._query_floats(":SOUR:LIST:VOLT?")

    @source_voltage_list_values.setter
    def source_voltage_list_values(self, values: Sequence[float]) -> None:
        """Set source voltage list values, in volts."""
        self._write_floats(":SOUR:LIST:VOLT", values)

    def append_source_voltage_list(self, values: Sequence[float]) -> None:
        """Append values to the instrument's source voltage list.

        Parameters
        ----------
        values : Sequence[float]
            Voltage values to append, in volts.
        """
        self._write_floats(":SOUR:LIST:VOLT:APP", values)

    @property
    def source_voltage_list_points(self) -> int:
        """Number of entries in the voltage source list."""
        return self._query_int(":SOUR:LIST:VOLT:POIN?")

    @property
    def source_voltage_list_start(self) -> int:
        """First point index used in the voltage source list."""
        return self._query_int(":SOUR:LIST:VOLT:STAR?")

    @source_voltage_list_start.setter
    def source_voltage_list_start(self, value: int | str) -> None:
        """Set the first point index used in the source list."""
        self._write_int(":SOUR:LIST:VOLT:STAR", value)

    @property
    def source_voltage_level_minimum(self) -> float:
        """Instrument-reported minimum value for source voltage level in volts."""
        return self._query_float(":SOUR:VOLT:LEV? MIN")

    @property
    def source_voltage_level_maximum(self) -> float:
        """Instrument-reported maximum value for source voltage level in volts."""
        return self._query_float(":SOUR:VOLT:LEV? MAX")

    @property
    def source_voltage_level_default(self) -> float:
        """Instrument-reported default value for source voltage level in volts."""
        return self._query_float(":SOUR:VOLT:LEV? DEF")

    @property
    def source_voltage_range_minimum(self) -> float:
        """Instrument-reported minimum value for source voltage range in volts."""
        return self._query_float(":SOUR:VOLT:RANG? MIN")

    @property
    def source_voltage_range_maximum(self) -> float:
        """Instrument-reported maximum value for source voltage range in volts."""
        return self._query_float(":SOUR:VOLT:RANG? MAX")

    @property
    def source_voltage_range_default(self) -> float:
        """Instrument-reported default value for source voltage range in volts."""
        return self._query_float(":SOUR:VOLT:RANG? DEF")

    @property
    def source_voltage_triggered_level_minimum(self) -> float:
        """Instrument-reported minimum value for source voltage triggered level in
        volts.
        """
        return self._query_float(":SOUR:VOLT:LEV:TRIG? MIN")

    @property
    def source_voltage_triggered_level_maximum(self) -> float:
        """Instrument-reported maximum value for source voltage triggered level in
        volts.
        """
        return self._query_float(":SOUR:VOLT:LEV:TRIG? MAX")

    @property
    def source_voltage_triggered_level_default(self) -> float:
        """Instrument-reported default value for source voltage triggered level in
        volts.
        """
        return self._query_float(":SOUR:VOLT:LEV:TRIG? DEF")

    @property
    def source_voltage_start_minimum(self) -> float:
        """Instrument-reported minimum value for source voltage start in volts."""
        return self._query_float(":SOUR:VOLT:STAR? MIN")

    @property
    def source_voltage_start_maximum(self) -> float:
        """Instrument-reported maximum value for source voltage start in volts."""
        return self._query_float(":SOUR:VOLT:STAR? MAX")

    @property
    def source_voltage_start_default(self) -> float:
        """Instrument-reported default value for source voltage start in volts."""
        return self._query_float(":SOUR:VOLT:STAR? DEF")

    @property
    def source_voltage_stop_minimum(self) -> float:
        """Instrument-reported minimum value for source voltage stop in volts."""
        return self._query_float(":SOUR:VOLT:STOP? MIN")

    @property
    def source_voltage_stop_maximum(self) -> float:
        """Instrument-reported maximum value for source voltage stop in volts."""
        return self._query_float(":SOUR:VOLT:STOP? MAX")

    @property
    def source_voltage_stop_default(self) -> float:
        """Instrument-reported default value for source voltage stop in volts."""
        return self._query_float(":SOUR:VOLT:STOP? DEF")

    @property
    def source_voltage_center_minimum(self) -> float:
        """Instrument-reported minimum value for source voltage center in volts."""
        return self._query_float(":SOUR:VOLT:CENT? MIN")

    @property
    def source_voltage_center_maximum(self) -> float:
        """Instrument-reported maximum value for source voltage center in volts."""
        return self._query_float(":SOUR:VOLT:CENT? MAX")

    @property
    def source_voltage_center_default(self) -> float:
        """Instrument-reported default value for source voltage center in volts."""
        return self._query_float(":SOUR:VOLT:CENT? DEF")

    @property
    def source_voltage_span_minimum(self) -> float:
        """Instrument-reported minimum value for source voltage span in volts."""
        return self._query_float(":SOUR:VOLT:SPAN? MIN")

    @property
    def source_voltage_span_maximum(self) -> float:
        """Instrument-reported maximum value for source voltage span in volts."""
        return self._query_float(":SOUR:VOLT:SPAN? MAX")

    @property
    def source_voltage_span_default(self) -> float:
        """Instrument-reported default value for source voltage span in volts."""
        return self._query_float(":SOUR:VOLT:SPAN? DEF")

    @property
    def source_voltage_step_minimum(self) -> float:
        """Instrument-reported minimum value for source voltage step in volts."""
        return self._query_float(":SOUR:VOLT:STEP? MIN")

    @property
    def source_voltage_step_maximum(self) -> float:
        """Instrument-reported maximum value for source voltage step in volts."""
        return self._query_float(":SOUR:VOLT:STEP? MAX")

    @property
    def source_voltage_step_default(self) -> float:
        """Instrument-reported default value for source voltage step in volts."""
        return self._query_float(":SOUR:VOLT:STEP? DEF")

    # Source current

    @property
    def source_current_mode(self) -> str:
        """Selected source current mode: FIX, SWEEP, or LIST."""
        return self._query(":SOUR:CURR:MODE?").upper()

    @source_current_mode.setter
    def source_current_mode(self, value: str) -> None:
        """Set source current mode; choices: FIX, SWEEP, or LIST."""
        value = value.upper()
        self._write(f":SOUR:CURR:MODE {value}")

    @property
    def source_current_level(self) -> float:
        """Source current level, in amperes."""
        return self._query_float(":SOUR:CURR:LEV?")

    @source_current_level.setter
    def source_current_level(self, value: float | str) -> None:
        """Set source current level, in amperes."""
        self._write_float(":SOUR:CURR:LEV", value)

    @property
    def source_current_range(self) -> float:
        """Source current range, in amperes."""
        return self._query_float(":SOUR:CURR:RANG?")

    @source_current_range.setter
    def source_current_range(self, value: float | str) -> None:
        """Set source current range, in amperes."""
        self._write_float(":SOUR:CURR:RANG", value)

    @property
    def source_current_auto_range(self) -> bool:
        """Whether the current source selects its range automatically."""
        return self._query_bool(":SOUR:CURR:RANG:AUTO?")

    @source_current_auto_range.setter
    def source_current_auto_range(self, value: bool) -> None:
        """Set source current auto range."""
        self._write_bool(":SOUR:CURR:RANG:AUTO", value)

    @property
    def source_current_start(self) -> float:
        """Staircase current sweep starting level, in amperes."""
        return self._query_float(":SOUR:CURR:STAR?")

    @source_current_start.setter
    def source_current_start(self, value: float | str) -> None:
        """Set source current start, in amperes."""
        self._write_float(":SOUR:CURR:STAR", value)

    @property
    def source_current_stop(self) -> float:
        """Staircase current sweep ending level, in amperes."""
        return self._query_float(":SOUR:CURR:STOP?")

    @source_current_stop.setter
    def source_current_stop(self, value: float | str) -> None:
        """Set source current stop, in amperes."""
        self._write_float(":SOUR:CURR:STOP", value)

    @property
    def source_current_step(self) -> float:
        """Staircase current sweep step size, in amperes."""
        return self._query_float(":SOUR:CURR:STEP?")

    @source_current_step.setter
    def source_current_step(self, value: float | str) -> None:
        """Set source current step, in amperes."""
        self._write_float(":SOUR:CURR:STEP", value)

    @property
    def source_current_center(self) -> float:
        """Staircase current sweep center level, in amperes."""
        return self._query_float(":SOUR:CURR:CENT?")

    @source_current_center.setter
    def source_current_center(self, value: float | str) -> None:
        """Set source current center, in amperes."""
        self._write_float(":SOUR:CURR:CENT", value)

    @property
    def source_current_span(self) -> float:
        """Staircase current sweep span, in amperes."""
        return self._query_float(":SOUR:CURR:SPAN?")

    @source_current_span.setter
    def source_current_span(self, value: float | str) -> None:
        """Set source current span, in amperes."""
        self._write_float(":SOUR:CURR:SPAN", value)

    @property
    def source_current_triggered_level(self) -> float:
        """Current level applied on a source trigger, in amperes."""
        return self._query_float(":SOUR:CURR:LEV:TRIG?")

    @source_current_triggered_level.setter
    def source_current_triggered_level(self, value: float | str) -> None:
        """Set source current triggered level, in amperes."""
        self._write_float(":SOUR:CURR:LEV:TRIG", value)

    @property
    def source_current_scaling_factor(self) -> float:
        """Dimensionless scaling factor applied to triggered current source levels."""
        return self._query_float(":SOUR:CURR:LEV:TRIG:SFAC?")

    @source_current_scaling_factor.setter
    def source_current_scaling_factor(self, value: float | str) -> None:
        """Set the dimensionless scaling factor for triggered source levels."""
        self._write_float(":SOUR:CURR:LEV:TRIG:SFAC", value)

    @property
    def source_current_scaling_enabled(self) -> bool:
        """Whether triggered current source scaling is enabled."""
        return self._query_bool(":SOUR:CURR:LEV:TRIG:SFAC:STAT?")

    @source_current_scaling_enabled.setter
    def source_current_scaling_enabled(self, value: bool) -> None:
        """Set source current scaling enabled."""
        self._write_bool(":SOUR:CURR:LEV:TRIG:SFAC:STAT", value)

    @property
    def source_current_list_values(self) -> tuple[float, ...]:
        """Current source list values as a tuple, in amperes; setters accept a
        sequence.
        """
        return self._query_floats(":SOUR:LIST:CURR?")

    @source_current_list_values.setter
    def source_current_list_values(self, values: Sequence[float]) -> None:
        """Set source current list values, in amperes."""
        self._write_floats(":SOUR:LIST:CURR", values)

    def append_source_current_list(self, values: Sequence[float]) -> None:
        """Append values to the instrument's source current list.

        Parameters
        ----------
        values : Sequence[float]
            Current values to append, in amperes.
        """
        self._write_floats(":SOUR:LIST:CURR:APP", values)

    @property
    def source_current_list_points(self) -> int:
        """Number of entries in the current source list."""
        return self._query_int(":SOUR:LIST:CURR:POIN?")

    @property
    def source_current_list_start(self) -> int:
        """First point index used in the current source list."""
        return self._query_int(":SOUR:LIST:CURR:STAR?")

    @source_current_list_start.setter
    def source_current_list_start(self, value: int | str) -> None:
        """Set the first point index used in the source list."""
        self._write_int(":SOUR:LIST:CURR:STAR", value)

    @property
    def source_current_level_minimum(self) -> float:
        """Instrument-reported minimum value for source current level in amperes."""
        return self._query_float(":SOUR:CURR:LEV? MIN")

    @property
    def source_current_level_maximum(self) -> float:
        """Instrument-reported maximum value for source current level in amperes."""
        return self._query_float(":SOUR:CURR:LEV? MAX")

    @property
    def source_current_level_default(self) -> float:
        """Instrument-reported default value for source current level in amperes."""
        return self._query_float(":SOUR:CURR:LEV? DEF")

    @property
    def source_current_range_minimum(self) -> float:
        """Instrument-reported minimum value for source current range in amperes."""
        return self._query_float(":SOUR:CURR:RANG? MIN")

    @property
    def source_current_range_maximum(self) -> float:
        """Instrument-reported maximum value for source current range in amperes."""
        return self._query_float(":SOUR:CURR:RANG? MAX")

    @property
    def source_current_range_default(self) -> float:
        """Instrument-reported default value for source current range in amperes."""
        return self._query_float(":SOUR:CURR:RANG? DEF")

    @property
    def source_current_triggered_level_minimum(self) -> float:
        """Instrument-reported minimum value for source current triggered level in
        amperes.
        """
        return self._query_float(":SOUR:CURR:LEV:TRIG? MIN")

    @property
    def source_current_triggered_level_maximum(self) -> float:
        """Instrument-reported maximum value for source current triggered level in
        amperes.
        """
        return self._query_float(":SOUR:CURR:LEV:TRIG? MAX")

    @property
    def source_current_triggered_level_default(self) -> float:
        """Instrument-reported default value for source current triggered level in
        amperes.
        """
        return self._query_float(":SOUR:CURR:LEV:TRIG? DEF")

    @property
    def source_current_start_minimum(self) -> float:
        """Instrument-reported minimum value for source current start in amperes."""
        return self._query_float(":SOUR:CURR:STAR? MIN")

    @property
    def source_current_start_maximum(self) -> float:
        """Instrument-reported maximum value for source current start in amperes."""
        return self._query_float(":SOUR:CURR:STAR? MAX")

    @property
    def source_current_start_default(self) -> float:
        """Instrument-reported default value for source current start in amperes."""
        return self._query_float(":SOUR:CURR:STAR? DEF")

    @property
    def source_current_stop_minimum(self) -> float:
        """Instrument-reported minimum value for source current stop in amperes."""
        return self._query_float(":SOUR:CURR:STOP? MIN")

    @property
    def source_current_stop_maximum(self) -> float:
        """Instrument-reported maximum value for source current stop in amperes."""
        return self._query_float(":SOUR:CURR:STOP? MAX")

    @property
    def source_current_stop_default(self) -> float:
        """Instrument-reported default value for source current stop in amperes."""
        return self._query_float(":SOUR:CURR:STOP? DEF")

    @property
    def source_current_center_minimum(self) -> float:
        """Instrument-reported minimum value for source current center in amperes."""
        return self._query_float(":SOUR:CURR:CENT? MIN")

    @property
    def source_current_center_maximum(self) -> float:
        """Instrument-reported maximum value for source current center in amperes."""
        return self._query_float(":SOUR:CURR:CENT? MAX")

    @property
    def source_current_center_default(self) -> float:
        """Instrument-reported default value for source current center in amperes."""
        return self._query_float(":SOUR:CURR:CENT? DEF")

    @property
    def source_current_span_minimum(self) -> float:
        """Instrument-reported minimum value for source current span in amperes."""
        return self._query_float(":SOUR:CURR:SPAN? MIN")

    @property
    def source_current_span_maximum(self) -> float:
        """Instrument-reported maximum value for source current span in amperes."""
        return self._query_float(":SOUR:CURR:SPAN? MAX")

    @property
    def source_current_span_default(self) -> float:
        """Instrument-reported default value for source current span in amperes."""
        return self._query_float(":SOUR:CURR:SPAN? DEF")

    @property
    def source_current_step_minimum(self) -> float:
        """Instrument-reported minimum value for source current step in amperes."""
        return self._query_float(":SOUR:CURR:STEP? MIN")

    @property
    def source_current_step_maximum(self) -> float:
        """Instrument-reported maximum value for source current step in amperes."""
        return self._query_float(":SOUR:CURR:STEP? MAX")

    @property
    def source_current_step_default(self) -> float:
        """Instrument-reported default value for source current step in amperes."""
        return self._query_float(":SOUR:CURR:STEP? DEF")

    # Sense voltage

    @property
    def sense_voltage_range(self) -> float:
        """Voltage measurement range, in volts."""
        return self._query_float(":SENS:VOLT:RANG?")

    @sense_voltage_range.setter
    def sense_voltage_range(self, value: float | str) -> None:
        """Set sense voltage range, in volts."""
        self._write_float(":SENS:VOLT:RANG", value)

    @property
    def sense_voltage_auto_range(self) -> bool:
        """Whether voltage measurement autoranging is enabled."""
        return self._query_bool(":SENS:VOLT:RANG:AUTO?")

    @sense_voltage_auto_range.setter
    def sense_voltage_auto_range(self, value: bool) -> None:
        """Set sense voltage auto range."""
        self._write_bool(":SENS:VOLT:RANG:AUTO", value)

    @property
    def sense_voltage_range_upper_limit(self) -> float:
        """Upper voltage measurement autorange bound, in volts."""
        return self._query_float(":SENS:VOLT:RANG:AUTO:ULIM?")

    @property
    def sense_voltage_range_lower_limit(self) -> float:
        """Lower voltage measurement autorange bound, in volts."""
        return self._query_float(":SENS:VOLT:RANG:AUTO:LLIM?")

    @sense_voltage_range_lower_limit.setter
    def sense_voltage_range_lower_limit(self, value: float | str) -> None:
        """Set sense voltage range lower limit, in volts."""
        self._write_float(":SENS:VOLT:RANG:AUTO:LLIM", value)

    @property
    def sense_voltage_nplc(self) -> float:
        """Integration time, in power-line cycles; this setting is shared by all
        measurement functions.
        """
        return self._query_float(":SENS:VOLT:NPLC?")

    @sense_voltage_nplc.setter
    def sense_voltage_nplc(self, value: float | str) -> None:
        """Set sense voltage nplc, in power-line cycles."""
        self._write_float(":SENS:VOLT:NPLC", value)

    @property
    def sense_voltage_range_minimum(self) -> float:
        """Instrument-reported minimum value for sense voltage range in volts."""
        return self._query_float(":SENS:VOLT:RANG? MIN")

    @property
    def sense_voltage_range_maximum(self) -> float:
        """Instrument-reported maximum value for sense voltage range in volts."""
        return self._query_float(":SENS:VOLT:RANG? MAX")

    @property
    def sense_voltage_range_default(self) -> float:
        """Instrument-reported default value for sense voltage range in volts."""
        return self._query_float(":SENS:VOLT:RANG? DEF")

    @property
    def sense_voltage_nplc_minimum(self) -> float:
        """Instrument-reported minimum value for sense voltage NPLC in power-line
        cycles.
        """
        return self._query_float(":SENS:VOLT:NPLC? MIN")

    @property
    def sense_voltage_nplc_maximum(self) -> float:
        """Instrument-reported maximum value for sense voltage NPLC in power-line
        cycles.
        """
        return self._query_float(":SENS:VOLT:NPLC? MAX")

    @property
    def sense_voltage_nplc_default(self) -> float:
        """Instrument-reported default value for sense voltage NPLC in power-line
        cycles.
        """
        return self._query_float(":SENS:VOLT:NPLC? DEF")

    # Sense current

    @property
    def sense_current_range(self) -> float:
        """Current measurement range, in amperes."""
        return self._query_float(":SENS:CURR:RANG?")

    @sense_current_range.setter
    def sense_current_range(self, value: float | str) -> None:
        """Set sense current range, in amperes."""
        self._write_float(":SENS:CURR:RANG", value)

    @property
    def sense_current_auto_range(self) -> bool:
        """Whether current measurement autoranging is enabled."""
        return self._query_bool(":SENS:CURR:RANG:AUTO?")

    @sense_current_auto_range.setter
    def sense_current_auto_range(self, value: bool) -> None:
        """Set sense current auto range."""
        self._write_bool(":SENS:CURR:RANG:AUTO", value)

    @property
    def sense_current_range_upper_limit(self) -> float:
        """Upper current measurement autorange bound, in amperes."""
        return self._query_float(":SENS:CURR:RANG:AUTO:ULIM?")

    @property
    def sense_current_range_lower_limit(self) -> float:
        """Lower current measurement autorange bound, in amperes."""
        return self._query_float(":SENS:CURR:RANG:AUTO:LLIM?")

    @sense_current_range_lower_limit.setter
    def sense_current_range_lower_limit(self, value: float | str) -> None:
        """Set sense current range lower limit, in amperes."""
        self._write_float(":SENS:CURR:RANG:AUTO:LLIM", value)

    @property
    def sense_current_nplc(self) -> float:
        """Integration time, in power-line cycles; this setting is shared by all
        measurement functions.
        """
        return self._query_float(":SENS:CURR:NPLC?")

    @sense_current_nplc.setter
    def sense_current_nplc(self, value: float | str) -> None:
        """Set sense current nplc, in power-line cycles."""
        self._write_float(":SENS:CURR:NPLC", value)

    @property
    def sense_current_range_holdoff(self) -> bool:
        """Whether current measurement range changes are delayed during source-memory
        sweeps.
        """
        return self._query_bool(":SENS:CURR:RANG:HOLD?")

    @sense_current_range_holdoff.setter
    def sense_current_range_holdoff(self, value: bool) -> None:
        """Set sense current range holdoff."""
        self._write_bool(":SENS:CURR:RANG:HOLD", value)

    @property
    def sense_current_range_holdoff_delay(self) -> float:
        """Current measurement range-change holdoff interval, in seconds."""
        return self._query_float(":SENS:CURR:RANG:HOLD:DEL?")

    @sense_current_range_holdoff_delay.setter
    def sense_current_range_holdoff_delay(self, value: float | str) -> None:
        """Set sense current range holdoff delay, in seconds."""
        self._write_float(":SENS:CURR:RANG:HOLD:DEL", value)

    @property
    def sense_current_range_minimum(self) -> float:
        """Instrument-reported minimum value for sense current range in amperes."""
        return self._query_float(":SENS:CURR:RANG? MIN")

    @property
    def sense_current_range_maximum(self) -> float:
        """Instrument-reported maximum value for sense current range in amperes."""
        return self._query_float(":SENS:CURR:RANG? MAX")

    @property
    def sense_current_range_default(self) -> float:
        """Instrument-reported default value for sense current range in amperes."""
        return self._query_float(":SENS:CURR:RANG? DEF")

    @property
    def sense_current_nplc_minimum(self) -> float:
        """Instrument-reported minimum value for sense current NPLC in power-line
        cycles.
        """
        return self._query_float(":SENS:CURR:NPLC? MIN")

    @property
    def sense_current_nplc_maximum(self) -> float:
        """Instrument-reported maximum value for sense current NPLC in power-line
        cycles.
        """
        return self._query_float(":SENS:CURR:NPLC? MAX")

    @property
    def sense_current_nplc_default(self) -> float:
        """Instrument-reported default value for sense current NPLC in power-line
        cycles.
        """
        return self._query_float(":SENS:CURR:NPLC? DEF")

    # Sense resistance

    @property
    def sense_resistance_range(self) -> float:
        """Resistance measurement range, in ohms."""
        return self._query_float(":SENS:RES:RANG?")

    @sense_resistance_range.setter
    def sense_resistance_range(self, value: float | str) -> None:
        """Set sense resistance range, in ohms."""
        self._write_float(":SENS:RES:RANG", value)

    @property
    def sense_resistance_auto_range(self) -> bool:
        """Whether resistance measurement autoranging is enabled."""
        return self._query_bool(":SENS:RES:RANG:AUTO?")

    @sense_resistance_auto_range.setter
    def sense_resistance_auto_range(self, value: bool) -> None:
        """Set sense resistance auto range."""
        self._write_bool(":SENS:RES:RANG:AUTO", value)

    @property
    def sense_resistance_range_upper_limit(self) -> float:
        """Upper resistance measurement autorange bound, in ohms."""
        return self._query_float(":SENS:RES:RANG:AUTO:ULIM?")

    @sense_resistance_range_upper_limit.setter
    def sense_resistance_range_upper_limit(self, value: float | str) -> None:
        """Set sense resistance range upper limit, in ohms."""
        self._write_float(":SENS:RES:RANG:AUTO:ULIM", value)

    @property
    def sense_resistance_range_lower_limit(self) -> float:
        """Lower resistance measurement autorange bound, in ohms."""
        return self._query_float(":SENS:RES:RANG:AUTO:LLIM?")

    @sense_resistance_range_lower_limit.setter
    def sense_resistance_range_lower_limit(self, value: float | str) -> None:
        """Set sense resistance range lower limit, in ohms."""
        self._write_float(":SENS:RES:RANG:AUTO:LLIM", value)

    @property
    def sense_resistance_nplc(self) -> float:
        """Integration time, in power-line cycles; this setting is shared by all
        measurement functions.
        """
        return self._query_float(":SENS:RES:NPLC?")

    @sense_resistance_nplc.setter
    def sense_resistance_nplc(self, value: float | str) -> None:
        """Set sense resistance nplc, in power-line cycles."""
        self._write_float(":SENS:RES:NPLC", value)

    @property
    def sense_resistance_range_minimum(self) -> float:
        """Instrument-reported minimum value for sense resistance range in ohms."""
        return self._query_float(":SENS:RES:RANG? MIN")

    @property
    def sense_resistance_range_maximum(self) -> float:
        """Instrument-reported maximum value for sense resistance range in ohms."""
        return self._query_float(":SENS:RES:RANG? MAX")

    @property
    def sense_resistance_range_default(self) -> float:
        """Instrument-reported default value for sense resistance range in ohms."""
        return self._query_float(":SENS:RES:RANG? DEF")

    @property
    def sense_resistance_nplc_minimum(self) -> float:
        """Instrument-reported minimum value for sense resistance NPLC in power-line
        cycles.
        """
        return self._query_float(":SENS:RES:NPLC? MIN")

    @property
    def sense_resistance_nplc_maximum(self) -> float:
        """Instrument-reported maximum value for sense resistance NPLC in power-line
        cycles.
        """
        return self._query_float(":SENS:RES:NPLC? MAX")

    @property
    def sense_resistance_nplc_default(self) -> float:
        """Instrument-reported default value for sense resistance NPLC in power-line
        cycles.
        """
        return self._query_float(":SENS:RES:NPLC? DEF")

    # Calculation, display, and status settings

    @property
    def limit_feed(self) -> str:
        """Measurement limit-test input: CALC, VOLT, CURR, or RES."""
        return self._query(":CALC2:FEED?").upper()

    @limit_feed.setter
    def limit_feed(self, value: str) -> None:
        """Set limit feed."""
        self._write(":CALC2:FEED " + value)

    @property
    def limit_data(self) -> tuple[float, ...]:
        """CALC2 relative/limit-test feed values for the completed sequence, as a flat
        tuple of floats.

        The selected format and elements determine the reply layout. Instrument
        overflow and unavailable-value sentinels are preserved.
        """
        return self._query_data(":CALC2:DATA?")

    @property
    def limit_latest(self) -> tuple[float, ...]:
        """Latest CALC2 relative/limit-test feed values, as a flat tuple of floats.

        The selected format and elements determine the reply layout. Instrument
        overflow and unavailable-value sentinels are preserved.
        """
        return self._query_data(":CALC2:DATA:LAT?")

    @property
    def display_enabled(self) -> bool:
        """Whether display is enabled."""
        return self._query_bool(":DISP:ENAB?")

    @display_enabled.setter
    def display_enabled(self, value: bool) -> None:
        """Set display enabled."""
        self._write_bool(":DISP:ENAB", value)

    def display_source_measure(self) -> None:
        """Return the display to its normal source/measurement presentation."""
        self._write(":DISP:CND")

    @property
    def display_digits(self) -> int:
        """Number of displayed measurement digits (4–7)."""
        return self._query_int(":DISP:DIG?")

    @display_digits.setter
    def display_digits(self, value: int | str) -> None:
        """Set display digits."""
        self._write_int(":DISP:DIG", value)

    def preset_status(self) -> None:
        """Restore status-register enable masks with :STAT:PRES; preserve the error
        queue.
        """
        self._write(":STAT:PRES")

    @property
    def error_queue_enabled(self) -> str:
        """Raw list of error/status codes enabled for inclusion in the error queue."""
        return self._query(":STAT:QUE:ENAB?")

    @error_queue_enabled.setter
    def error_queue_enabled(self, value: str | Sequence[int]) -> None:
        """Set error queue enabled."""
        self._write(
            ":STAT:QUE:ENAB "
            + (",".join(map(str, value)) if not isinstance(value, str) else value)
        )

    @property
    def error_queue_disabled(self) -> str:
        """Raw list of error/status codes excluded from the error queue."""
        return self._query(":STAT:QUE:DIS?")

    @error_queue_disabled.setter
    def error_queue_disabled(self, value: str | Sequence[int]) -> None:
        """Set error queue disabled."""
        self._write(
            ":STAT:QUE:DIS "
            + (",".join(map(str, value)) if not isinstance(value, str) else value)
        )

    def read_status_error(self) -> str:
        """Read and remove the oldest status/error queue entry with :STAT:QUE?.

        Returns
        -------
        str
            Raw code and message; this consumes the same queue as read_error().
        """
        return self._query(":STAT:QUE?")

    def clear_status_errors(self) -> None:
        """Remove all entries from the status/error queue."""
        self._write(":STAT:QUE:CLE")

    @property
    def display_digits_minimum(self) -> float:
        """Instrument-reported minimum value for display digits."""
        return self._query_float(":DISP:DIG? MIN")

    @property
    def display_digits_maximum(self) -> float:
        """Instrument-reported maximum value for display digits."""
        return self._query_float(":DISP:DIG? MAX")

    @property
    def display_digits_default(self) -> float:
        """Instrument-reported default value for display digits."""
        return self._query_float(":DISP:DIG? DEF")

    # Math

    @property
    def math_catalog(self) -> str:
        """Raw catalog of built-in and user-defined math expression names."""
        return self._query(":CALC:MATH:CAT?")

    @property
    def math_name(self) -> str:
        """Selected math expression name.

        Built-in names include POWER, OFFCOMPOHM, VOLTCOEF, and VARALPHA. Custom
        names may contain up to 10 ASCII characters.
        """
        return self._query(":CALC:MATH:NAME?")

    @math_name.setter
    def math_name(self, value: str) -> None:
        """Set math name."""
        self._write_str(":CALC:MATH:NAME", value)

    @property
    def math_expression(self) -> str:
        """Selected math expression as raw instrument text; setters accept an
        expression string.
        """
        return self._query(":CALC:MATH?")

    @math_expression.setter
    def math_expression(self, value: str) -> None:
        """Set math expression."""
        self._write(":CALC:MATH:EXPR " + value)

    @property
    def math_units(self) -> str:
        """User-defined math-result unit label, up to three ASCII characters."""
        return self._query(":CALC:MATH:UNIT?").strip('"')

    @math_units.setter
    def math_units(self, value: str) -> None:
        """Set math units."""
        self._write_str(":CALC:MATH:UNIT", value)

    @property
    def math_enabled(self) -> bool:
        """Whether CALC1 math processing is enabled."""
        return self._query_bool(":CALC:STAT?")

    @math_enabled.setter
    def math_enabled(self, value: bool) -> None:
        """Set math enabled."""
        self._write_bool(":CALC:STAT", value)

    @property
    def math_data(self) -> tuple[float, ...]:
        """CALC1 math results for the completed sequence, as a flat tuple of floats.

        The selected format and elements determine the reply layout. Instrument
        overflow and unavailable-value sentinels are preserved.
        """
        return self._query_data(":CALC:DATA?")

    @property
    def math_latest(self) -> tuple[float, ...]:
        """Latest CALC1 math result, as a flat tuple of floats.

        The selected format and elements determine the reply layout. Instrument
        overflow and unavailable-value sentinels are preserved.
        """
        return self._query_data(":CALC:DATA:LAT?")

    def delete_math_expression(self, name: str) -> None:
        """Delete the math expression from instrument memory.

        Parameters
        ----------
        name : str
            Custom expression name to delete.
        """
        self._write_str(":CALC:MATH:DEL:SEL", name)

    def delete_all_math_expressions(self) -> None:
        """Delete all user-defined math expressions from instrument memory."""
        self._write(":CALC:MATH:DEL:ALL")

    # Relative

    @property
    def relative_offset(self) -> float:
        """Offset subtracted from the selected limit-test feed, in that feed's units."""
        return self._query_float(":CALC2:NULL:OFFS?")

    @relative_offset.setter
    def relative_offset(self, value: float) -> None:
        """Set relative offset."""
        self._write_float(":CALC2:NULL:OFFS", value)

    @property
    def relative_enabled(self) -> bool:
        """Whether relative-offset subtraction is enabled for the limit-test feed."""
        return self._query_bool(":CALC2:NULL:STAT?")

    @relative_enabled.setter
    def relative_enabled(self, value: bool) -> None:
        """Set relative enabled."""
        self._write_bool(":CALC2:NULL:STAT", value)

    def acquire_relative(self) -> None:
        """Acquire a relative offset from the current feed reading.

        If no reading is available, the instrument uses the next available reading.
        """
        self._write(":CALC2:NULL:ACQ")

    # Composite limit

    @property
    def composite_limit_pass_pattern(self) -> int:
        """Digital output bit pattern used for composite measurement-test pass
        results.
        """
        return self._query_int(":CALC2:CLIM:PASS:SOUR2?")

    @composite_limit_pass_pattern.setter
    def composite_limit_pass_pattern(self, value: int | str) -> None:
        """Set composite limit pass pattern."""
        self._write(f":CALC2:CLIM:PASS:SOUR2 {value}")

    @property
    def composite_limit_fail_pattern(self) -> int:
        """Digital output bit pattern used for composite measurement-test fail
        results.
        """
        return self._query_int(":CALC2:CLIM:FAIL:SOUR2?")

    @composite_limit_fail_pattern.setter
    def composite_limit_fail_pattern(self, value: int | str) -> None:
        """Set composite limit fail pattern."""
        self._write(f":CALC2:CLIM:FAIL:SOUR2 {value}")

    @property
    def composite_limit_pass_memory_location(self) -> str:
        """Next source-memory location on a composite pass: location text or NEXT."""
        return self._query(":CALC2:CLIM:PASS:SMLOCATION?")

    @composite_limit_pass_memory_location.setter
    def composite_limit_pass_memory_location(self, value: int | str) -> None:
        """Set composite limit pass memory location."""
        self._write(f":CALC2:CLIM:PASS:SMLOCATION {value}")

    @property
    def composite_limit_fail_memory_location(self) -> str:
        """Next source-memory location on a composite failure: location text or NEXT."""
        return self._query(":CALC2:CLIM:FAIL:SMLOCATION?")

    @composite_limit_fail_memory_location.setter
    def composite_limit_fail_memory_location(self, value: int | str) -> None:
        """Set composite limit fail memory location."""
        self._write(f":CALC2:CLIM:FAIL:SMLOCATION {value}")

    @property
    def composite_limit_mode(self) -> str:
        """Digital pass/fail interpretation for composite measurement limit tests."""
        return self._query(":CALC2:CLIM:MODE?").upper()

    @composite_limit_mode.setter
    def composite_limit_mode(self, value: str) -> None:
        """Set composite limit mode."""
        self._write(":CALC2:CLIM:MODE " + value)

    @property
    def composite_limit_bin_control(self) -> str:
        """When digital pass/fail outputs update: IMMEDIATE or END."""
        return self._query(":CALC2:CLIM:BCON?").upper()

    @composite_limit_bin_control.setter
    def composite_limit_bin_control(self, value: str) -> None:
        """Set composite limit bin control."""
        self._write(":CALC2:CLIM:BCON " + value)

    @property
    def composite_limit_auto_clear(self) -> bool:
        """Whether measurement limit-test failure indications clear automatically."""
        return self._query_bool(":CALC2:CLIM:CLE:AUTO?")

    @composite_limit_auto_clear.setter
    def composite_limit_auto_clear(self, value: bool) -> None:
        """Set composite limit auto clear."""
        self._write_bool(":CALC2:CLIM:CLE:AUTO", value)

    def clear_composite_limits(self) -> None:
        """Clear composite measurement limit-test results."""
        self._write(":CALC2:CLIM:CLE")

    # Statistics

    @property
    def statistics_function(self) -> str:
        """Selected statistics function; documented choices are MEAN, SDEVIATION,
        MAXIMUM, MINIMUM, or PKPK.
        """
        return self._query(":CALC3:FORM?").upper()

    @statistics_function.setter
    def statistics_function(self, value: str) -> None:
        """Set statistics function."""
        self._write(":CALC3:FORM " + value)

    @property
    def statistics_data(self) -> tuple[float, ...]:
        """Selected statistic calculated from the stored trace readings, as a flat
        tuple of floats.

        The selected format and elements determine the reply layout. Instrument
        overflow and unavailable-value sentinels are preserved.
        """
        return self._query_floats(":CALC3:DATA?")

    # Display top

    @property
    def display_top_text(self) -> str:
        """User message for the top display line, up to 20 characters."""
        return self._query(":DISP:WIND1:TEXT:DATA?")

    @display_top_text.setter
    def display_top_text(self, value: str) -> None:
        """Set display top text."""
        self._write_str(":DISP:WIND1:TEXT:DATA", value)

    @property
    def display_top_text_enabled(self) -> bool:
        """Whether the user message is shown on the top display line."""
        return self._query_bool(":DISP:WIND1:TEXT:STAT?")

    @display_top_text_enabled.setter
    def display_top_text_enabled(self, value: bool) -> None:
        """Set display top text enabled."""
        self._write_bool(":DISP:WIND1:TEXT:STAT", value)

    @property
    def display_top_data(self) -> str:
        """Raw text currently shown on the top display line."""
        return self._query(":DISP:WIND1:DATA?")

    @property
    def display_top_attributes(self) -> str:
        """Raw annunciator/attribute information for the top display line."""
        return self._query(":DISP:WIND1:ATTR?")

    # Display bottom

    @property
    def display_bottom_text(self) -> str:
        """User message for the bottom display line, up to 32 characters."""
        return self._query(":DISP:WIND2:TEXT:DATA?")

    @display_bottom_text.setter
    def display_bottom_text(self, value: str) -> None:
        """Set display bottom text."""
        self._write_str(":DISP:WIND2:TEXT:DATA", value)

    @property
    def display_bottom_text_enabled(self) -> bool:
        """Whether the user message is shown on the bottom display line."""
        return self._query_bool(":DISP:WIND2:TEXT:STAT?")

    @display_bottom_text_enabled.setter
    def display_bottom_text_enabled(self, value: bool) -> None:
        """Set display bottom text enabled."""
        self._write_bool(":DISP:WIND2:TEXT:STAT", value)

    @property
    def display_bottom_data(self) -> str:
        """Raw text currently shown on the bottom display line."""
        return self._query(":DISP:WIND2:DATA?")

    @property
    def display_bottom_attributes(self) -> str:
        """Raw annunciator/attribute information for the bottom display line."""
        return self._query(":DISP:WIND2:ATTR?")

    # Measurement status

    @property
    def measurement_status_enable(self) -> int:
        """Measurement status event-enable register bit mask."""
        return self._query_int(":STAT:MEAS:ENAB?")

    @measurement_status_enable.setter
    def measurement_status_enable(self, value: int | str) -> None:
        """Set measurement status enable."""
        self._write(f":STAT:MEAS:ENAB {value}")

    @property
    def measurement_status_condition(self) -> int:
        """Current measurement status condition register bit mask; reading does not
        clear it.
        """
        return self._query_int(":STAT:MEAS:COND?")

    def read_measurement_status_event(self) -> int:
        """Read and clear the measurement status event register."""
        return self._query_int(":STAT:MEAS:EVEN?")

    # Operation status

    @property
    def operation_status_enable(self) -> int:
        """Operation status event-enable register bit mask."""
        return self._query_int(":STAT:OPER:ENAB?")

    @operation_status_enable.setter
    def operation_status_enable(self, value: int | str) -> None:
        """Set operation status enable."""
        self._write(f":STAT:OPER:ENAB {value}")

    @property
    def operation_status_condition(self) -> int:
        """Current operation status condition register bit mask; reading does not
        clear it.
        """
        return self._query_int(":STAT:OPER:COND?")

    def read_operation_status_event(self) -> int:
        """Read and clear the operation status event register."""
        return self._query_int(":STAT:OPER:EVEN?")

    # Questionable status

    @property
    def questionable_status_enable(self) -> int:
        """Questionable status event-enable register bit mask."""
        return self._query_int(":STAT:QUES:ENAB?")

    @questionable_status_enable.setter
    def questionable_status_enable(self, value: int | str) -> None:
        """Set questionable status enable."""
        self._write(f":STAT:QUES:ENAB {value}")

    @property
    def questionable_status_condition(self) -> int:
        """Current questionable status condition register bit mask; reading does not
        clear it.
        """
        return self._query_int(":STAT:QUES:COND?")

    def read_questionable_status_event(self) -> int:
        """Read and clear the questionable status event register."""
        return self._query_int(":STAT:QUES:EVEN?")

    # Measurement limit tests (CALCulate2:LIMit1–12)

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
        self._verify_limit_test_index(index)
        return self._query_bool(f":CALC2:LIM{index}:STAT?")

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
        self._verify_limit_test_index(index)
        self._write_bool(f":CALC2:LIM{index}:STAT", enabled)

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
        self._verify_limit_test_index(index)
        return self._query_bool(f":CALC2:LIM{index}:FAIL?")

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
        self._verify_numeric_limit_test_index(index)
        return self._query_float(f":CALC2:LIM{index}:UPP?")

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
        self._verify_numeric_limit_test_index(index)
        self._write_float(f":CALC2:LIM{index}:UPP", value)

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
        self._verify_numeric_limit_test_index(index)
        return self._query_float(f":CALC2:LIM{index}:LOW?")

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
        self._verify_numeric_limit_test_index(index)
        self._write_float(f":CALC2:LIM{index}:LOW", value)

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
        self._verify_limit_test_index(index)
        if index == 1:
            return self._query_int(":CALC2:LIM1:COMP:SOUR2?")
        if index == 4:
            return self._query_int(":CALC2:LIM4:SOUR2?")
        return self._query_int(f":CALC2:LIM{index}:LOW:SOUR2?")

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
        self._verify_limit_test_index(index)
        if index == 1:
            self._write_int(":CALC2:LIM1:COMP:SOUR2", value)
        elif index == 4:
            self._write_int(":CALC2:LIM4:SOUR2", value)
        else:
            self._write_int(f":CALC2:LIM{index}:LOW:SOUR2", value)

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
        self._verify_numeric_limit_test_index(index)
        return self._query_int(f":CALC2:LIM{index}:UPP:SOUR2?")

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
        self._verify_numeric_limit_test_index(index)
        self._write_int(f":CALC2:LIM{index}:UPP:SOUR2", value)

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
        self._verify_numeric_limit_test_index(index)
        return self._query_int(f":CALC2:LIM{index}:PASS:SOUR2?")

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
        self._verify_numeric_limit_test_index(index)
        self._write_int(f":CALC2:LIM{index}:PASS:SOUR2", value)

    @property
    def limit_test_1_compliance_fail_condition(self) -> str:
        """Read the compliance condition that fails measurement limit test 1."""
        return self._query(":CALC2:LIM:COMP:FAIL?").upper()

    @limit_test_1_compliance_fail_condition.setter
    def limit_test_1_compliance_fail_condition(self, value: str) -> None:
        """Set limit test 1 compliance fail condition."""
        self._write(f":CALC2:LIM:COMP:FAIL {value}")

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
        self._verify_numeric_limit_test_index(index)
        return self._query_float(f":CALC2:LIM{index}:UPP? MIN")

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
        self._verify_numeric_limit_test_index(index)
        return self._query_float(f":CALC2:LIM{index}:UPP? MAX")

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
        self._verify_numeric_limit_test_index(index)
        return self._query_float(f":CALC2:LIM{index}:UPP? DEF")

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
        self._verify_numeric_limit_test_index(index)
        return self._query_float(f":CALC2:LIM{index}:LOW? MIN")

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
        self._verify_numeric_limit_test_index(index)
        return self._query_float(f":CALC2:LIM{index}:LOW? MAX")

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
        self._verify_numeric_limit_test_index(index)
        return self._query_float(f":CALC2:LIM{index}:LOW? DEF")
