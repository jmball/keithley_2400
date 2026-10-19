"""A compact driver for common Keithley 2400 source-measure tasks."""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import TracebackType
from typing import Any

import pyvisa
from pyvisa.resources import SerialInstrument, TCPIPSocket


@dataclass(frozen=True)
class Measurement:
    """One READ? result in the instrument's fixed VOLT,CURR,RES,TIME,STAT order."""

    voltage: float
    current: float
    resistance: float
    time: float
    status: int


class keithley2400:
    """Control a Keithley 2400 through a PyVISA message-based resource."""

    def __init__(self) -> None:
        self._instrument: pyvisa.resources.MessageBasedResource | None = None

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
        """Open a single-reading ASCII session.

        Serial connections require an explicit, nonempty read_termination matching
        the instrument's response setting. GPIB reads default to LF.
        TCP sockets require explicit, nonempty read and write terminations.
        Serial writes default to CR; GPIB writes default to LF.
        Resource keyword arguments override the transport defaults.
        """
        if self._instrument is not None:
            raise RuntimeError("already connected")
        manager = resource_manager if resource_manager is not None else pyvisa.ResourceManager()
        settings = {"encoding": "ascii"}
        settings.update(resource_kwargs)
        instrument = manager.open_resource(resource_name, **settings)
        self._instrument = instrument
        try:
            if isinstance(instrument, TCPIPSocket):
                if not resource_kwargs.get("read_termination") or not resource_kwargs.get("write_termination"):
                    raise ValueError("TCP sockets require read_termination and write_termination")
            serial = isinstance(instrument, SerialInstrument)
            if serial and not resource_kwargs.get("read_termination"):
                raise ValueError("serial connections require read_termination")
            if not serial and "read_termination" not in resource_kwargs:
                instrument.read_termination = "\n"
            if "write_termination" not in resource_kwargs:
                instrument.write_termination = "\r" if serial else "\n"
            self.abort()
            self.configure_single_read()
        except BaseException:
            self._instrument = None
            try:
                instrument.close()
            except Exception:
                pass
            raise

    @property
    def connected(self) -> bool:
        return self._instrument is not None

    def disconnect(self) -> None:
        """Close the instrument session, if connected."""
        instrument, self._instrument = self._instrument, None
        if instrument is not None:
            instrument.close()

    def _require_instrument(self) -> pyvisa.resources.MessageBasedResource:
        if self._instrument is None:
            raise RuntimeError("not connected")
        return self._instrument

    def _write(self, command: str) -> None:
        self._require_instrument().write(command)

    def _query(self, command: str) -> str:
        return self._require_instrument().query(command).strip()

    def _query_float(self, command: str) -> float:
        return float(self._query(command))

    def _query_bool(self, command: str) -> bool:
        return bool(int(self._query(command)))

    def _write_float(self, command: str, value: float) -> None:
        self._write(f"{command} {value:.12g}")

    def _write_bool(self, command: str, enabled: bool) -> None:
        self._write(f"{command} {'ON' if enabled else 'OFF'}")

    @property
    def identification(self) -> str:
        """Return the read-only *IDN? response."""
        return self._query("*IDN?")

    @property
    def output_enabled(self) -> bool:
        return self._query_bool(":OUTP?")

    @output_enabled.setter
    def output_enabled(self, enabled: bool) -> None:
        self._write_bool(":OUTP", enabled)

    @property
    def source_function(self) -> str:
        return self._query(":SOUR:FUNC?").upper()

    @source_function.setter
    def source_function(self, function: str) -> None:
        function = self._function(function)
        if function == "RES":
            raise ValueError("source function must be VOLT or CURR")
        self._write(f":SOUR:FUNC {function}")
        self._write(f":SOUR:{function}:MODE FIX")

    @property
    def source_level(self) -> float:
        """Fixed source level in volts or amps for the selected source function."""
        function = self.source_function
        return self._query_float(f":SOUR:{function}:LEV?")

    @source_level.setter
    def source_level(self, level: float) -> None:
        if not math.isfinite(level):
            raise ValueError("source level must be finite")
        function = self.source_function
        self._write_float(f":SOUR:{function}:LEV", level)

    @property
    def source_range(self) -> float:
        """Source range in volts or amps for the selected source function."""
        function = self.source_function
        return self._query_float(f":SOUR:{function}:RANG?")

    @source_range.setter
    def source_range(self, value: float) -> None:
        self._positive_finite(value)
        function = self.source_function
        self._write_float(f":SOUR:{function}:RANG", value)

    @property
    def sense_functions(self) -> tuple[str, ...]:
        """Enabled sense functions as VOLT, CURR, or RES names."""
        raw = self._query(":SENS:FUNC?")
        return tuple(
            self._function(part.strip().strip('"'))
            for part in raw.split(",")
            if part.strip()
        )

    @sense_functions.setter
    def sense_functions(self, functions: str | tuple[str, ...] | list[str]) -> None:
        if isinstance(functions, str):
            functions = (functions,)
        normalized = tuple(self._function(function) for function in functions)
        if not normalized or len(set(normalized)) != len(normalized):
            raise ValueError("sense_functions must contain unique functions")
        self._write_bool(":SENS:FUNC:CONC", len(normalized) > 1)
        self._write(":SENS:FUNC:OFF:ALL")
        for function in normalized:
            self._write(f':SENS:FUNC:ON "{function}"')

    @property
    def current_compliance(self) -> float:
        """Current compliance limit in amps when sourcing voltage."""
        return self._query_float(":SENS:CURR:PROT?")

    @current_compliance.setter
    def current_compliance(self, value: float) -> None:
        self._positive_finite(value)
        self._write_float(":SENS:CURR:PROT", value)

    @property
    def voltage_compliance(self) -> float:
        """Voltage compliance limit in volts when sourcing current."""
        return self._query_float(":SENS:VOLT:PROT?")

    @voltage_compliance.setter
    def voltage_compliance(self, value: float) -> None:
        self._positive_finite(value)
        self._write_float(":SENS:VOLT:PROT", value)

    @property
    def nplc(self) -> float:
        """Global integration period in power line cycles (0.01 to 10)."""
        return self._query_float(":SENS:VOLT:NPLC?")

    @nplc.setter
    def nplc(self, value: float) -> None:
        self._positive_finite(value)
        if not 0.01 <= value <= 10:
            raise ValueError("NPLC must be between 0.01 and 10")
        self._write_float(":SENS:VOLT:NPLC", value)

    @property
    def voltage_auto_range(self) -> bool:
        return self._query_bool(":SENS:VOLT:RANG:AUTO?")

    @voltage_auto_range.setter
    def voltage_auto_range(self, enabled: bool) -> None:
        self._write_bool(":SENS:VOLT:RANG:AUTO", enabled)

    @property
    def current_auto_range(self) -> bool:
        return self._query_bool(":SENS:CURR:RANG:AUTO?")

    @current_auto_range.setter
    def current_auto_range(self, enabled: bool) -> None:
        self._write_bool(":SENS:CURR:RANG:AUTO", enabled)

    @property
    def voltage_range(self) -> float:
        """Voltage measurement range in volts; setting disables autoranging."""
        return self._query_float(":SENS:VOLT:RANG?")

    @voltage_range.setter
    def voltage_range(self, value: float) -> None:
        self._positive_finite(value)
        self._write_float(":SENS:VOLT:RANG", value)

    @property
    def current_range(self) -> float:
        """Current measurement range in amps; setting disables autoranging."""
        return self._query_float(":SENS:CURR:RANG?")

    @current_range.setter
    def current_range(self, value: float) -> None:
        self._positive_finite(value)
        self._write_float(":SENS:CURR:RANG", value)

    @property
    def remote_sense(self) -> bool:
        """Whether four-wire remote sensing is enabled."""
        return self._query_bool(":SYST:RSEN?")

    @remote_sense.setter
    def remote_sense(self, enabled: bool) -> None:
        self._write_bool(":SYST:RSEN", enabled)

    @property
    def terminals(self) -> str:
        """Selected FRONT or REAR terminals."""
        return self._query(":ROUT:TERM?").upper()

    @terminals.setter
    def terminals(self, value: str) -> None:
        value = value.upper()
        if value not in {"FRONT", "REAR"}:
            raise ValueError("terminals must be 'front' or 'rear'")
        self._write(f":ROUT:TERM {value}")

    def abort(self) -> None:
        """Abort the current operation and return the trigger system to idle."""
        self._write(":ABOR")

    def configure_single_read(self) -> None:
        """Configure the ASCII format and immediate trigger recipe used by read().

        Call abort() first if an operation is running. This disables automatic
        output on/off; enable output explicitly before reading.
        """
        self._write(":FORM:DATA ASC")
        self.auto_output_off = False
        self._write(":FORM:ELEM VOLT,CURR,RES,TIME,STAT")
        self._write(":ARM:SOUR IMM")
        self._write(":ARM:COUN 1")
        self._write(":TRIG:SOUR IMM")
        self._write(":TRIG:COUN 1")
        self._write_float(":TRIG:DEL", 0.0)

    @property
    def auto_output_off(self) -> bool:
        """Whether each source-measure cycle automatically switches the output."""
        return self._query_bool(":SOUR:CLE:AUTO?")

    @auto_output_off.setter
    def auto_output_off(self, enabled: bool) -> None:
        self._write_bool(":SOUR:CLE:AUTO", enabled)

    def read(self) -> Measurement:
        """Trigger one immediate measurement and return the five documented fields."""
        values = [float(part.strip()) for part in self._query(":READ?").split(",")]
        if len(values) != 5:
            raise ValueError(f"expected five READ? fields, received {len(values)}")
        return Measurement(values[0], values[1], values[2], values[3], int(values[4]))

    def clear(self) -> None:
        """Clear instrument status and error queues."""
        self._write("*CLS")

    def read_error(self) -> str:
        """Read and remove the oldest instrument error."""
        return self._query(":SYST:ERR?")

    @staticmethod
    def _function(function: str) -> str:
        value = function.upper().replace(":DC", "").strip()
        if value not in {"VOLT", "CURR", "RES"}:
            raise ValueError("function must be VOLT, CURR, or RES")
        return value

    @staticmethod
    def _positive_finite(value: float) -> None:
        if not math.isfinite(value) or value <= 0:
            raise ValueError("value must be positive and finite")
