"""Low-level source, sense, output, and terminal commands for Series 2400."""

from __future__ import annotations

from collections.abc import Sequence
from ._communication import NumericLimits, _Communication


class _SourceChannel:
    """Settings shared by the explicitly indexed VOLT and CURR source paths."""

    def __init__(self, owner: SourceSenseCommands, function: str) -> None:
        self._owner, self._function = owner, function

    @property
    def mode(self) -> str:
        return self._owner._query(f":SOUR:{self._function}:MODE?").upper()

    @mode.setter
    def mode(self, value: str) -> None:
        value = value.upper()
        if value not in {"FIX", "FIXED", "SWE", "SWEEP", "LIST"}:
            raise ValueError("source channel mode must be FIX, SWEEP, or LIST")
        self._owner._write(f":SOUR:{self._function}:MODE {value}")

    @property
    def level(self) -> float:
        return self._owner._query_float(f":SOUR:{self._function}:LEV?")

    @level.setter
    def level(self, value: float | str) -> None:
        self._owner._write_float(f":SOUR:{self._function}:LEV", value)

    @property
    def range(self) -> float:
        return self._owner._query_float(f":SOUR:{self._function}:RANG?")

    @range.setter
    def range(self, value: float | str) -> None:
        self._owner._write_float(f":SOUR:{self._function}:RANG", value)

    @property
    def auto_range(self) -> bool:
        return self._owner._query_bool(f":SOUR:{self._function}:RANG:AUTO?")

    @auto_range.setter
    def auto_range(self, value: bool) -> None:
        self._owner._write_bool(f":SOUR:{self._function}:RANG:AUTO", value)

    @property
    def start(self) -> float:
        return self._owner._query_float(f":SOUR:{self._function}:STAR?")

    @start.setter
    def start(self, value: float | str) -> None:
        self._owner._write_float(f":SOUR:{self._function}:STAR", value)

    @property
    def stop(self) -> float:
        return self._owner._query_float(f":SOUR:{self._function}:STOP?")

    @stop.setter
    def stop(self, value: float | str) -> None:
        self._owner._write_float(f":SOUR:{self._function}:STOP", value)

    @property
    def step(self) -> float:
        return self._owner._query_float(f":SOUR:{self._function}:STEP?")

    @step.setter
    def step(self, value: float | str) -> None:
        self._owner._write_float(f":SOUR:{self._function}:STEP", value)

    @property
    def center(self) -> float:
        return self._owner._query_float(f":SOUR:{self._function}:CENT?")

    @center.setter
    def center(self, value: float | str) -> None:
        self._owner._write_float(f":SOUR:{self._function}:CENT", value)

    @property
    def span(self) -> float:
        return self._owner._query_float(f":SOUR:{self._function}:SPAN?")

    @span.setter
    def span(self, value: float | str) -> None:
        self._owner._write_float(f":SOUR:{self._function}:SPAN", value)

    @property
    def triggered_level(self) -> float:
        return self._owner._query_float(f":SOUR:{self._function}:LEV:TRIG?")

    @triggered_level.setter
    def triggered_level(self, value: float | str) -> None:
        self._owner._write_float(f":SOUR:{self._function}:LEV:TRIG", value)

    @property
    def scaling_factor(self) -> float:
        return self._owner._query_float(f":SOUR:{self._function}:LEV:TRIG:SFAC?")

    @scaling_factor.setter
    def scaling_factor(self, value: float | str) -> None:
        self._owner._write_float(f":SOUR:{self._function}:LEV:TRIG:SFAC", value)

    @property
    def scaling_enabled(self) -> bool:
        return self._owner._query_bool(f":SOUR:{self._function}:LEV:TRIG:SFAC:STAT?")

    @scaling_enabled.setter
    def scaling_enabled(self, value: bool) -> None:
        self._owner._write_bool(f":SOUR:{self._function}:LEV:TRIG:SFAC:STAT", value)

    @property
    def list_values(self) -> tuple[float, ...]:
        return self._owner._query_floats(f":SOUR:LIST:{self._function}?")

    @list_values.setter
    def list_values(self, values: Sequence[float]) -> None:
        self._owner._write_floats(f":SOUR:LIST:{self._function}", values)

    def append_list(self, values: Sequence[float]) -> None:
        self._owner._write_floats(f":SOUR:LIST:{self._function}:APP", values)

    @property
    def list_points(self) -> int:
        return self._owner._query_int(f":SOUR:LIST:{self._function}:POIN?")

    @property
    def list_start(self) -> int:
        return self._owner._query_int(f":SOUR:LIST:{self._function}:STAR?")

    @list_start.setter
    def list_start(self, value: int | str) -> None:
        self._owner._write_int(f":SOUR:LIST:{self._function}:STAR", value)

    @property
    def level_limits(self) -> NumericLimits:
        return self._owner._query_limits(f":SOUR:{self._function}:LEV")

    @property
    def range_limits(self) -> NumericLimits:
        return self._owner._query_limits(f":SOUR:{self._function}:RANG")

    @property
    def triggered_level_limits(self) -> NumericLimits:
        return self._owner._query_limits(f":SOUR:{self._function}:LEV:TRIG")

    @property
    def start_limits(self) -> NumericLimits:
        return self._owner._query_limits(f":SOUR:{self._function}:STAR")

    @property
    def stop_limits(self) -> NumericLimits:
        return self._owner._query_limits(f":SOUR:{self._function}:STOP")

    @property
    def center_limits(self) -> NumericLimits:
        return self._owner._query_limits(f":SOUR:{self._function}:CENT")

    @property
    def span_limits(self) -> NumericLimits:
        return self._owner._query_limits(f":SOUR:{self._function}:SPAN")

    @property
    def step_limits(self) -> NumericLimits:
        return self._owner._query_limits(f":SOUR:{self._function}:STEP")


class _SenseChannel:
    """Settings shared by the explicitly indexed VOLT, CURR, and RES paths."""

    def __init__(self, owner: SourceSenseCommands, function: str) -> None:
        self._owner, self._function = owner, function

    @property
    def range(self) -> float:
        return self._owner._query_float(f":SENS:{self._function}:RANG?")

    @range.setter
    def range(self, value: float | str) -> None:
        self._owner._write_float(f":SENS:{self._function}:RANG", value)

    @property
    def auto_range(self) -> bool:
        return self._owner._query_bool(f":SENS:{self._function}:RANG:AUTO?")

    @auto_range.setter
    def auto_range(self, value: bool) -> None:
        self._owner._write_bool(f":SENS:{self._function}:RANG:AUTO", value)

    @property
    def range_upper_limit(self) -> float:
        return self._owner._query_float(f":SENS:{self._function}:RANG:AUTO:ULIM?")

    @range_upper_limit.setter
    def range_upper_limit(self, value: float | str) -> None:
        if self._function != "RES":
            raise AttributeError(
                "the upper autorange limit is read-only for voltage and current"
            )
        self._owner._write_float(f":SENS:{self._function}:RANG:AUTO:ULIM", value)

    @property
    def range_lower_limit(self) -> float:
        return self._owner._query_float(f":SENS:{self._function}:RANG:AUTO:LLIM?")

    @range_lower_limit.setter
    def range_lower_limit(self, value: float | str) -> None:
        self._owner._write_float(f":SENS:{self._function}:RANG:AUTO:LLIM", value)

    @property
    def nplc(self) -> float:
        return self._owner._query_float(f":SENS:{self._function}:NPLC?")

    @nplc.setter
    def nplc(self, value: float | str) -> None:
        if not isinstance(value, str):
            self._owner._verify_positive_finite(value)
        self._owner._write_float(f":SENS:{self._function}:NPLC", value)

    @property
    def range_holdoff(self) -> bool:
        if self._function != "CURR":
            raise AttributeError("range holdoff is documented for current range only")
        return self._owner._query_bool(":SENS:CURR:RANG:HOLD?")

    @range_holdoff.setter
    def range_holdoff(self, value: bool) -> None:
        if self._function != "CURR":
            raise AttributeError("range holdoff is documented for current range only")
        self._owner._write_bool(":SENS:CURR:RANG:HOLD", value)

    @property
    def range_holdoff_delay(self) -> float:
        if self._function != "CURR":
            raise AttributeError(
                "range holdoff delay is documented for current range only"
            )
        return self._owner._query_float(":SENS:CURR:RANG:HOLD:DEL?")

    @range_holdoff_delay.setter
    def range_holdoff_delay(self, value: float | str) -> None:
        if self._function != "CURR":
            raise AttributeError(
                "range holdoff delay is documented for current range only"
            )
        self._owner._write_float(":SENS:CURR:RANG:HOLD:DEL", value)

    @property
    def range_limits(self) -> NumericLimits:
        return self._owner._query_limits(f":SENS:{self._function}:RANG")

    @property
    def nplc_limits(self) -> NumericLimits:
        return self._owner._query_limits(f":SENS:{self._function}:NPLC")


class SourceSenseCommands(_Communication):
    """Direct SCPI controls for source, measurement, output, and routing settings."""

    @property
    def source_voltage(self) -> _SourceChannel:
        return _SourceChannel(self, "VOLT")

    @property
    def source_current(self) -> _SourceChannel:
        return _SourceChannel(self, "CURR")

    @property
    def sense_voltage(self) -> _SenseChannel:
        return _SenseChannel(self, "VOLT")

    @property
    def sense_current(self) -> _SenseChannel:
        return _SenseChannel(self, "CURR")

    @property
    def sense_resistance(self) -> _SenseChannel:
        return _SenseChannel(self, "RES")

    @property
    def source_function(self) -> str:
        return self._query(":SOUR:FUNC?").strip('"').upper()

    @source_function.setter
    def source_function(self, value: str) -> None:
        value = value.upper().strip()
        if value not in {"VOLT", "VOLTAGE", "CURR", "CURRENT", "MEM", "MEMORY"}:
            raise ValueError("source function must be VOLT, CURR, or MEM")
        normalized = {
            "VOLT": "VOLT",
            "VOLTAGE": "VOLT",
            "CURR": "CURR",
            "CURRENT": "CURR",
            "MEM": "MEM",
            "MEMORY": "MEM",
        }[value]
        self._write(f":SOUR:FUNC {normalized}")

    @property
    def source_level(self) -> float:
        function = self.source_function
        if function.startswith("MEM"):
            raise ValueError(
                "memory source mode has no direct level; use memory recall"
            )
        return {"VOLT": self.source_voltage, "CURR": self.source_current}[
            function[:4]
        ].level

    @source_level.setter
    def source_level(self, value: float | str) -> None:
        function = self.source_function
        if function.startswith("MEM"):
            raise ValueError("memory source mode has no direct level")
        {"VOLT": self.source_voltage, "CURR": self.source_current}[
            function[:4]
        ].level = value

    @property
    def source_range(self) -> float:
        function = self.source_function
        if function.startswith("MEM"):
            raise ValueError("memory source mode has no direct range")
        return {"VOLT": self.source_voltage, "CURR": self.source_current}[
            function[:4]
        ].range

    @source_range.setter
    def source_range(self, value: float | str) -> None:
        function = self.source_function
        if function.startswith("MEM"):
            raise ValueError("memory source mode has no direct range")
        {"VOLT": self.source_voltage, "CURR": self.source_current}[
            function[:4]
        ].range = value

    @property
    def sense_functions(self) -> tuple[str, ...]:
        raw = self._query(":SENS:FUNC?").replace('"', "")
        return tuple(
            self._normalize_sense_function(part)
            for part in raw.split(",")
            if part.strip()
        )

    @sense_functions.setter
    def sense_functions(self, functions: Sequence[str]) -> None:
        if isinstance(functions, str):
            functions = (functions,)
        normalized = tuple(
            dict.fromkeys(self._normalize_sense_function(x) for x in functions)
        )
        if not normalized:
            raise ValueError("at least one sense function is required")
        self.sense_concurrent = len(normalized) > 1
        self.disable_all_sense_functions()
        self.enable_sense_functions(normalized)

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
            self._normalize_sense_function(part)
            for part in raw.split(",")
            if part.strip()
        )

    def enable_sense_functions(self, functions: Sequence[str]) -> None:
        for value in functions:
            function = self._normalize_sense_function(value)
            self._write_str(":SENS:FUNC:ON", function)

    def disable_sense_functions(self, functions: Sequence[str]) -> None:
        for value in functions:
            function = self._normalize_sense_function(value)
            self._write_str(":SENS:FUNC:OFF", function)

    def enable_all_sense_functions(self) -> None:
        self._write(":SENS:FUNC:ON:ALL")

    def disable_all_sense_functions(self) -> None:
        self._write(":SENS:FUNC:OFF:ALL")

    def sense_function_enabled(self, function: str) -> bool:
        normalized = self._normalize_sense_function(function)
        return self._query_bool(f':SENS:FUNC:STAT? "{normalized}"')

    @property
    def sense_auto_range(self) -> bool:
        functions = self.sense_functions
        if len(functions) != 1:
            raise ValueError(
                "sense_auto_range requires exactly one selected sense function; use a sense channel endpoint"
            )
        return {
            "VOLT": self.sense_voltage,
            "CURR": self.sense_current,
            "RES": self.sense_resistance,
        }[functions[0]].auto_range

    @sense_auto_range.setter
    def sense_auto_range(self, enabled: bool) -> None:
        functions = self.sense_functions
        if len(functions) != 1:
            raise ValueError(
                "sense_auto_range requires exactly one selected sense function; use a sense channel endpoint"
            )
        {
            "VOLT": self.sense_voltage,
            "CURR": self.sense_current,
            "RES": self.sense_resistance,
        }[functions[0]].auto_range = enabled

    @property
    def voltage_range(self) -> float:
        return self.sense_voltage.range

    @voltage_range.setter
    def voltage_range(self, value: float | str) -> None:
        self.sense_voltage.range = value

    @property
    def current_range(self) -> float:
        return self.sense_current.range

    @current_range.setter
    def current_range(self, value: float | str) -> None:
        self.sense_current.range = value

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
        return self.sense_voltage.nplc

    @nplc.setter
    def nplc(self, value: float | str) -> None:
        self.sense_voltage.nplc = value

    @property
    def resistance_mode(self) -> str:
        return self._query(":SENS:RES:MODE?").upper()

    @resistance_mode.setter
    def resistance_mode(self, value: str) -> None:
        value = value.upper()
        if value not in {"AUTO", "MAN", "MANUAL"}:
            raise ValueError("resistance_mode must be AUTO or MANual")
        self._write(f":SENS:RES:MODE {'MAN' if value.startswith('MAN') else 'AUTO'}")

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
        self._write(f":SENS:AVER:TCON {'REP' if value.startswith('REP') else 'MOV'}")

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
    def current_compliance_limits(self) -> NumericLimits:
        return self._query_limits(":SENS:CURR:PROT")

    @property
    def voltage_compliance_limits(self) -> NumericLimits:
        return self._query_limits(":SENS:VOLT:PROT")

    @property
    def average_count_limits(self) -> NumericLimits:
        return self._query_limits(":SENS:AVER:COUN")

    @property
    def voltage_protection_limits(self) -> NumericLimits:
        return self._query_limits(":SOUR:VOLT:PROT")

    @property
    def source_delay_limits(self) -> NumericLimits:
        return self._query_limits(":SOUR:DEL")

    @property
    def sweep_points_limits(self) -> NumericLimits:
        return self._query_limits(":SOUR:SWE:POIN")

    @property
    def pulse_width_limits(self) -> NumericLimits:
        return self._query_limits(":SOUR:PULS:WIDT")

    @property
    def pulse_delay_limits(self) -> NumericLimits:
        return self._query_limits(":SOUR:PULS:DEL")

    @property
    def digital_clear_delay_limits(self) -> NumericLimits:
        return self._query_limits(":SOUR2:CLE:AUTO:DEL")
