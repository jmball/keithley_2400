"""VISA session lifecycle and shared SCPI communication helpers."""

from __future__ import annotations

from collections.abc import Collection, Sequence
import math
import struct
from types import TracebackType
from typing import Any, NamedTuple, TypeVar

import pyvisa
from pyvisa.resources import GPIBInstrument, SerialInstrument, TCPIPSocket


class NumericLimits(NamedTuple):
    """Instrument-reported minimum, maximum, and reset-default numeric parameters."""

    minimum: float
    maximum: float
    default: float


_T = TypeVar("_T", bound="_Communication")


class _Communication:
    """Shared transport; connecting never changes instrument settings."""

    def __init__(self) -> None:
        self._instr: pyvisa.resources.MessageBasedResource | None = None
        self.check_errors_after_write: bool = True

    def __enter__(self: _T) -> _T:
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
        settings = {"encoding": "ascii"}
        settings.update(resource_kwargs)
        instrument = manager.open_resource(resource_name, **settings)
        self._instr = instrument
        try:
            if isinstance(instrument, TCPIPSocket):
                if not resource_kwargs.get(
                    "read_termination"
                ) or not resource_kwargs.get("write_termination"):
                    raise ValueError(
                        "TCP sockets require read_termination and write_termination"
                    )
            serial = isinstance(instrument, SerialInstrument)
            if serial and not resource_kwargs.get("read_termination"):
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
        instrument, self._instr = self._instr, None
        if instrument is not None:
            instrument.close()

    def _write(self, command: str) -> None:
        if self._instr is not None:
            self._instr.write(command)
            if self.check_errors_after_write:
                self.check_errors()
        else:
            raise RuntimeError("not connected")

    def _query(self, command: str) -> str:
        if self._instr is not None:
            return self._instr.query(command).strip()
        raise RuntimeError("not connected")

    def _query_float(self, command: str) -> float:
        return float(self._query(command))

    def _query_bool(self, command: str) -> bool:
        return bool(int(self._query(command)))

    def _write_float(self, command: str, value: float | str) -> None:
        parameter = value if isinstance(value, str) else f"{value:.12g}"
        self._write(f"{command} {parameter}")

    def _write_bool(self, command: str, enabled: bool) -> None:
        self._write(f"{command} {'ON' if enabled else 'OFF'}")

    def _read(self) -> str:
        if self._instr is not None:
            return self._instr.read().strip()
        raise RuntimeError("not connected")

    def read_response(self) -> str:
        """Receive a pending ASCII response without issuing another command.

        After a timeout, first resolve the pending response or clear the VISA
        interface before querying instrument errors (manual Appendix B).
        """
        return self._read()

    def _query_int(self, command: str) -> int:
        value = self._query(command)
        if value.startswith("#"):
            base = {"H": 16, "Q": 8, "B": 2}[value[1].upper()]
            return int(value[2:], base)
        return int(value)

    def _query_floats(self, command: str) -> tuple[float, ...]:
        return tuple(float(value) for value in self._query(command).split(","))

    def _query_limits(self, command: str) -> NumericLimits:
        return NumericLimits(
            self._query_float(f"{command}? MIN"),
            self._query_float(f"{command}? MAX"),
            self._query_float(f"{command}? DEF"),
        )

    def _write_int(self, command: str, value: int | str) -> None:
        self._write(f"{command} {value}")

    def _write_str(self, command: str, value: str) -> None:
        quoted = value.replace('"', '""')
        self._write(f'{command} "{quoted}"')

    def _write_floats(self, command: str, values: Sequence[float]) -> None:
        self._write(f"{command} " + ",".join(f"{value:.12g}" for value in values))

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
            # Binary payloads can contain LF bytes; GPIB EOI ends the block.
            self._instr.read_termination = None
            # A query response must be consumed before checking any errors.
            self._instr.write(command)
            block = self._instr.read_raw()
        finally:
            self._instr.read_termination = termination
        if not block.startswith(b"#0") or not block.endswith(b"\n"):
            raise ValueError("expected a #0 binary block terminated by LF")
        payload = block[2:-1]
        order = {"NORM": ">", "SWAP": "<"}[byte_order.upper()]
        return struct.unpack(f"{order}{len(payload) // 4}f", payload)

    @staticmethod
    def _verify_positive_finite(value: float) -> None:
        if not math.isfinite(value) or value <= 0:
            raise ValueError("value must be positive and finite")

    @staticmethod
    def _normalize_sense_function(function: str) -> str:
        aliases = {
            "VOLT": "VOLT",
            "VOLTAGE": "VOLT",
            "VOLT:DC": "VOLT",
            "VOLTAGE:DC": "VOLT",
            "CURR": "CURR",
            "CURRENT": "CURR",
            "CURR:DC": "CURR",
            "CURRENT:DC": "CURR",
            "RES": "RES",
            "RESISTANCE": "RES",
        }
        value = function.strip().upper()
        if value not in aliases:
            raise ValueError("sense function must be VOLT, CURR, or RES")
        return aliases[value]

    @staticmethod
    def _normalize_choice(value: str, choices: Collection[str]) -> str:
        normalized = value.strip().upper()
        if normalized not in choices:
            raise ValueError("value must be one of " + ", ".join(sorted(choices)))
        return normalized

    def _write_enum(self, command: str, value: str, choices: Collection[str]) -> None:
        self._write(f"{command} {self._normalize_choice(value, choices)}")

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
