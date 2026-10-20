"""CALCulate, DISPlay, FORMat (except DATA/BORDer), and STATus commands."""

from __future__ import annotations

from collections.abc import Sequence

from ._communication import NumericLimits, _Communication


class _MathCommands:
    def __init__(self, owner: _Communication):
        self._owner = owner

    @property
    def catalog(self) -> str:
        return self._owner._query(":CALC:MATH:CAT?")

    @property
    def name(self) -> str:
        return self._owner._query(":CALC:MATH:NAME?")

    @name.setter
    def name(self, value: str) -> None:
        self._owner._write_str(":CALC:MATH:NAME", value)

    @property
    def expression(self) -> str:
        return self._owner._query(":CALC:MATH?")

    @expression.setter
    def expression(self, value: str) -> None:
        self._owner._write(":CALC:MATH:EXPR " + value)

    @property
    def units(self) -> str:
        return self._owner._query(":CALC:MATH:UNIT?").strip('"')

    @units.setter
    def units(self, value: str) -> None:
        self._owner._write_str(":CALC:MATH:UNIT", value)

    @property
    def enabled(self) -> bool:
        return self._owner._query_bool(":CALC:STAT?")

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._owner._write_bool(":CALC:STAT", value)

    @property
    def data(self) -> tuple[float, ...]:
        return self._owner._query_data(":CALC:DATA?")

    @property
    def latest(self) -> tuple[float, ...]:
        return self._owner._query_data(":CALC:DATA:LAT?")

    def delete(self, name: str) -> None:
        self._owner._write_str(":CALC:MATH:DEL:SEL", name)

    def delete_all(self) -> None:
        self._owner._write(":CALC:MATH:DEL:ALL")


class _RelativeCommands:
    def __init__(self, owner: _Communication):
        self._owner = owner

    @property
    def offset(self) -> float:
        return self._owner._query_float(":CALC2:NULL:OFFS?")

    @offset.setter
    def offset(self, value: float) -> None:
        self._owner._write_float(":CALC2:NULL:OFFS", value)

    @property
    def enabled(self) -> bool:
        return self._owner._query_bool(":CALC2:NULL:STAT?")

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._owner._write_bool(":CALC2:NULL:STAT", value)

    def acquire(self) -> None:
        self._owner._write(":CALC2:NULL:ACQ")


class _LimitTest:
    def __init__(self, owner: _Communication, index: int):
        self._owner, self._index = owner, index

    @property
    def enabled(self) -> bool:
        return self._owner._query_bool(f":CALC2:LIM{self._index}:STAT?")

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._owner._write_bool(f":CALC2:LIM{self._index}:STAT", value)

    @property
    def failed(self) -> bool:
        return self._owner._query_bool(f":CALC2:LIM{self._index}:FAIL?")

    def _pattern(self, suffix: str) -> int:
        return self._owner._query_int(f":CALC2:LIM{self._index}:{suffix}?")

    def _set_pattern(self, suffix: str, value: int | str) -> None:
        self._owner._write(f":CALC2:LIM{self._index}:{suffix} {value}")

    @property
    def upper(self) -> float:
        if self._index == 1 or self._index == 4:
            raise AttributeError("this limit has no numeric upper threshold")
        return self._owner._query_float(f":CALC2:LIM{self._index}:UPP?")

    @upper.setter
    def upper(self, value: float | str) -> None:
        if self._index == 1 or self._index == 4:
            raise AttributeError("this limit has no numeric upper threshold")
        self._owner._write_float(f":CALC2:LIM{self._index}:UPP", value)

    @property
    def lower(self) -> float:
        if self._index == 1 or self._index == 4:
            raise AttributeError("this limit has no numeric lower threshold")
        return self._owner._query_float(f":CALC2:LIM{self._index}:LOW?")

    @lower.setter
    def lower(self, value: float | str) -> None:
        if self._index == 1 or self._index == 4:
            raise AttributeError("this limit has no numeric lower threshold")
        self._owner._write_float(f":CALC2:LIM{self._index}:LOW", value)

    @property
    def fail_pattern(self) -> int:
        suffix = (
            "COMP:SOUR2"
            if self._index == 1
            else "SOUR2" if self._index == 4 else "LOW:SOUR2"
        )
        return self._pattern(suffix)

    @fail_pattern.setter
    def fail_pattern(self, value: int | str) -> None:
        suffix = (
            "COMP:SOUR2"
            if self._index == 1
            else "SOUR2" if self._index == 4 else "LOW:SOUR2"
        )
        self._set_pattern(suffix, value)

    @property
    def upper_fail_pattern(self) -> int:
        if self._index in (1, 4):
            raise AttributeError("this limit has no upper grading pattern")
        return self._pattern("UPP:SOUR2")

    @upper_fail_pattern.setter
    def upper_fail_pattern(self, value: int | str) -> None:
        if self._index in (1, 4):
            raise AttributeError("this limit has no upper grading pattern")
        self._set_pattern("UPP:SOUR2", value)

    @property
    def pass_pattern(self) -> int:
        if self._index in (1, 4):
            raise AttributeError("this limit has no pass pattern")
        return self._pattern("PASS:SOUR2")

    @pass_pattern.setter
    def pass_pattern(self, value: int | str) -> None:
        if self._index in (1, 4):
            raise AttributeError("this limit has no pass pattern")
        self._set_pattern("PASS:SOUR2", value)

    @property
    def compliance_fail_condition(self) -> str:
        if self._index != 1:
            raise AttributeError("only Limit 1 has a compliance fail condition")
        return self._owner._query(":CALC2:LIM:COMP:FAIL?").upper()

    @compliance_fail_condition.setter
    def compliance_fail_condition(self, value: str) -> None:
        if self._index != 1:
            raise AttributeError("only Limit 1 has a compliance fail condition")
        self._owner._write(":CALC2:LIM:COMP:FAIL " + value)

    @property
    def upper_limits(self) -> NumericLimits:
        if self._index in (1, 4):
            raise AttributeError("this limit has no numeric upper threshold")
        return self._owner._query_limits(f":CALC2:LIM{self._index}:UPP")

    @property
    def lower_limits(self) -> NumericLimits:
        if self._index in (1, 4):
            raise AttributeError("this limit has no numeric lower threshold")
        return self._owner._query_limits(f":CALC2:LIM{self._index}:LOW")


class _CompositeLimits:
    def __init__(self, owner: _Communication):
        self._owner = owner

    @property
    def pass_pattern(self) -> int:
        return self._owner._query_int(":CALC2:CLIM:PASS:SOUR2?")

    @pass_pattern.setter
    def pass_pattern(self, value: int | str) -> None:
        self._owner._write(f":CALC2:CLIM:PASS:SOUR2 {value}")

    @property
    def fail_pattern(self) -> int:
        return self._owner._query_int(":CALC2:CLIM:FAIL:SOUR2?")

    @fail_pattern.setter
    def fail_pattern(self, value: int | str) -> None:
        self._owner._write(f":CALC2:CLIM:FAIL:SOUR2 {value}")

    @property
    def pass_memory_location(self) -> str:
        return self._owner._query(":CALC2:CLIM:PASS:SMLOCATION?")

    @pass_memory_location.setter
    def pass_memory_location(self, value: int | str) -> None:
        self._owner._write(f":CALC2:CLIM:PASS:SMLOCATION {value}")

    @property
    def fail_memory_location(self) -> str:
        return self._owner._query(":CALC2:CLIM:FAIL:SMLOCATION?")

    @fail_memory_location.setter
    def fail_memory_location(self, value: int | str) -> None:
        self._owner._write(f":CALC2:CLIM:FAIL:SMLOCATION {value}")

    @property
    def mode(self) -> str:
        return self._owner._query(":CALC2:CLIM:MODE?").upper()

    @mode.setter
    def mode(self, value: str) -> None:
        self._owner._write(":CALC2:CLIM:MODE " + value)

    @property
    def bin_control(self) -> str:
        return self._owner._query(":CALC2:CLIM:BCON?").upper()

    @bin_control.setter
    def bin_control(self, value: str) -> None:
        self._owner._write(":CALC2:CLIM:BCON " + value)

    @property
    def auto_clear(self) -> bool:
        return self._owner._query_bool(":CALC2:CLIM:CLE:AUTO?")

    @auto_clear.setter
    def auto_clear(self, value: bool) -> None:
        self._owner._write_bool(":CALC2:CLIM:CLE:AUTO", value)

    def clear(self) -> None:
        self._owner._write(":CALC2:CLIM:CLE")


class _Calc3Commands:
    def __init__(self, owner: _Communication):
        self._owner = owner

    @property
    def statistic(self) -> str:
        return self._owner._query(":CALC3:FORM?").upper()

    @statistic.setter
    def statistic(self, value: str) -> None:
        self._owner._write(":CALC3:FORM " + value)

    @property
    def data(self) -> tuple[float, ...]:
        return self._owner._query_floats(":CALC3:DATA?")


class _DisplayWindow:
    def __init__(self, owner: _Communication, index: int):
        self._owner, self._index = owner, index

    @property
    def text(self) -> str:
        return self._owner._query(f":DISP:WIND{self._index}:TEXT:DATA?")

    @text.setter
    def text(self, value: str) -> None:
        self._owner._write_str(f":DISP:WIND{self._index}:TEXT:DATA", value)

    @property
    def text_enabled(self) -> bool:
        return self._owner._query_bool(f":DISP:WIND{self._index}:TEXT:STAT?")

    @text_enabled.setter
    def text_enabled(self, value: bool) -> None:
        self._owner._write_bool(f":DISP:WIND{self._index}:TEXT:STAT", value)

    @property
    def data(self) -> str:
        return self._owner._query(f":DISP:WIND{self._index}:DATA?")

    @property
    def attributes(self) -> str:
        return self._owner._query(f":DISP:WIND{self._index}:ATTR?")


class _StatusGroup:
    def __init__(self, owner: _Communication, group: str):
        self._owner, self._group = owner, group

    @property
    def enable(self) -> int:
        return self._owner._query_int(f":STAT:{self._group}:ENAB?")

    @enable.setter
    def enable(self, value: int | str) -> None:
        self._owner._write(f":STAT:{self._group}:ENAB {value}")

    @property
    def condition(self) -> int:
        return self._owner._query_int(f":STAT:{self._group}:COND?")

    def read_event(self) -> int:
        return self._owner._query_int(f":STAT:{self._group}:EVEN?")


class CalculationCommands(_Communication):
    @property
    def math(self) -> _MathCommands:
        return _MathCommands(self)

    @property
    def relative(self) -> _RelativeCommands:
        return _RelativeCommands(self)

    @property
    def calc3(self) -> _Calc3Commands:
        return _Calc3Commands(self)

    def limit(self, index: int) -> _LimitTest:
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or index not in range(1, 13)
        ):
            raise ValueError("limit index must be from 1 through 12")
        return _LimitTest(self, index)

    @property
    def composite_limits(self) -> _CompositeLimits:
        return _CompositeLimits(self)

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

    @property
    def display_top(self) -> _DisplayWindow:
        return _DisplayWindow(self, 1)

    @property
    def display_bottom(self) -> _DisplayWindow:
        return _DisplayWindow(self, 2)

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

    @property
    def measurement_status(self) -> _StatusGroup:
        return _StatusGroup(self, "MEAS")

    @property
    def operation_status(self) -> _StatusGroup:
        return _StatusGroup(self, "OPER")

    @property
    def questionable_status(self) -> _StatusGroup:
        return _StatusGroup(self, "QUES")

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
    def display_digits_limits(self) -> NumericLimits:
        return self._query_limits(":DISP:DIG")
