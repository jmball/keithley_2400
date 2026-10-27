from __future__ import annotations

import runpy
import struct
from collections import deque
from typing import Any

import pytest
import pyvisa
from pyvisa import constants
from pyvisa.resources import (
    GPIBInstrument,
    MessageBasedResource,
    SerialInstrument,
    TCPIPSocket,
)

from keithley2400 import keithley2400


class FakeInstrument(MessageBasedResource):
    _session = None
    read_termination = None
    write_termination = None

    def __init__(self):
        self.attributes: dict[constants.ResourceAttribute, Any] = {
            constants.ResourceAttribute.timeout_value: 2000
        }
        self.writes = []
        self.queries = []
        self.responses: dict[str, str | deque[str] | Exception] = {
            ":SYST:ERR:ALL?": '0,"No error"',
            ":FORM:DATA?": "ASC",
        }
        self.closed = False

    def get_visa_attribute(self, name: constants.ResourceAttribute) -> Any:
        return self.attributes[name]

    def set_visa_attribute(
        self, name: constants.ResourceAttribute, state: Any
    ) -> constants.StatusCode:
        self.attributes[name] = state
        return constants.StatusCode.success

    def write(
        self, message: str, termination: str | None = None, encoding: str | None = None
    ) -> int:
        self.writes.append(message)
        return len(message)

    def query(self, message: str, delay: float | None = None) -> str:
        self.queries.append(message)
        response = self.responses[message]
        if isinstance(response, deque):
            response = response.popleft()
        if isinstance(response, Exception):
            raise response
        return response

    def close(self):
        self.closed = True


class FakeManager(pyvisa.ResourceManager):
    def __new__(cls, *args, **kwargs):
        return object.__new__(cls)

    def __init__(self, instrument):
        self.instrument = instrument
        self.calls = []

    def open_resource(self, resource_name: str, *args, **kwargs) -> FakeInstrument:
        self.calls.append((resource_name, kwargs))
        self.instrument.__dict__.update(kwargs)
        return self.instrument

    def close(self):
        pass


class FakeSerialInstrument(FakeInstrument, SerialInstrument):
    _session = None
    read_termination = None
    write_termination = None


class FakeSocketInstrument(FakeInstrument, TCPIPSocket):
    _session = None
    read_termination = None
    write_termination = None


class FakeGpibInstrument(FakeInstrument, GPIBInstrument):
    block: bytes
    _session = None
    read_termination = "\n"
    write_termination = None

    def read_raw(self, size: int | None = None) -> bytes:
        assert self.read_termination is None
        return self.block


def test_connect_only_configures_communication_and_forwards_options():
    instrument = FakeSerialInstrument()
    manager = FakeManager(instrument)
    meter = keithley2400()
    meter.connect(
        "serial_alias",
        resource_manager=manager,
        baud_rate=19200,
        read_termination="\r\n",
    )
    assert manager.calls == [
        (
            "serial_alias",
            {"encoding": "ascii", "read_termination": "\r\n", "baud_rate": 19200},
        )
    ]
    assert instrument.write_termination == "\r"
    assert instrument.writes == instrument.queries == []
    meter.disconnect()
    assert instrument.closed


def test_gpib_connection_sets_lf_without_sending_commands():
    instrument = FakeGpibInstrument()
    meter = keithley2400()
    meter.connect("GPIB0::24::INSTR", resource_manager=FakeManager(instrument))
    assert instrument.write_termination == instrument.read_termination == "\n"
    assert instrument.writes == instrument.queries == []
    meter.disconnect()


@pytest.mark.parametrize(
    "options", [{}, {"read_termination": None}, {"read_termination": ""}]
)
def test_serial_requires_read_termination_before_sending_commands(options):
    instrument = FakeSerialInstrument()
    meter = keithley2400()
    with pytest.raises(ValueError, match="serial connections require read_termination"):
        meter.connect(
            "serial_alias", resource_manager=FakeManager(instrument), **options
        )
    assert instrument.writes == instrument.queries == []
    assert instrument.closed
    assert not meter.connected


@pytest.mark.parametrize(
    "options", [{}, {"read_termination": "\r\n"}, {"write_termination": "\r"}]
)
def test_tcp_socket_requires_both_terminations_before_sending_commands(options):
    instrument = FakeSocketInstrument()
    meter = keithley2400()
    with pytest.raises(ValueError, match="TCP sockets require"):
        meter.connect(
            "adapter_alias", resource_manager=FakeManager(instrument), **options
        )
    assert instrument.writes == instrument.queries == []
    assert instrument.closed
    assert not meter.connected


def test_tcp_socket_preserves_adapter_terminations_and_reads_variable_data():
    instrument = FakeSocketInstrument()
    instrument.responses[":READ?"] = "1.0,0.002,9.91E37,0.5,0,2.0,0.003,9.9E37,0.6,64"
    with keithley2400() as meter:
        meter.connect(
            "adapter_alias",
            resource_manager=FakeManager(instrument),
            read_termination="\r\n",
            write_termination="\r",
        )
        assert instrument.writes == instrument.queries == []
        assert meter.read() == (1, 0.002, 9.91e37, 0.5, 0, 2, 0.003, 9.9e37, 0.6, 64)
        assert instrument.write_termination == "\r"
        assert instrument.read_termination == "\r\n"
    assert instrument.closed


def test_communication_configuration_failure_closes_open_instrument():

    class BrokenInstrument(FakeInstrument):
        @property
        def write_termination(self):
            return None

        @write_termination.setter
        def write_termination(self, value):
            raise OSError("transport failed")

    instrument = BrokenInstrument()
    meter = keithley2400()
    with pytest.raises(OSError, match="transport failed"):
        meter.connect("GPIB0::24::INSTR", resource_manager=FakeManager(instrument))
    assert instrument.closed
    assert not meter.connected


@pytest.mark.parametrize("fail", [False, True])
def test_context_closes_session_on_normal_and_exceptional_exit(fail):
    instrument = FakeInstrument()
    meter = keithley2400()

    def use_instrument():
        with meter as entered:
            assert entered is meter
            meter.connect("GPIB0::24::INSTR", resource_manager=FakeManager(instrument))
            if fail:
                raise ValueError("measurement failed")

    if fail:
        with pytest.raises(ValueError, match="measurement failed"):
            use_instrument()
    else:
        use_instrument()
    assert instrument.closed
    assert not meter.connected


def test_commands_require_connection():
    meter = keithley2400()
    with pytest.raises(RuntimeError, match="not connected"):
        meter.read()
    with pytest.raises(RuntimeError, match="not connected"):
        meter.output_enabled = True
    with pytest.raises(RuntimeError, match="not connected"):
        meter.read_response()


def test_read_response_receives_pending_data_without_sending_commands():
    class PendingInstrument(FakeInstrument):
        def read(
            self, termination: str | None = None, encoding: str | None = None
        ) -> str:
            return "1.25\r\n"

    instrument = PendingInstrument()
    with keithley2400() as meter:
        meter.connect("GPIB0::24::INSTR", resource_manager=FakeManager(instrument))
        assert meter.read_response() == "1.25"

    assert instrument.writes == instrument.queries == []


def test_write_checks_error_queue_and_raises_raw_instrument_messages():
    instrument = FakeInstrument()
    errors = '-222,"Parameter data out of range",-221,"Settings conflict"'
    instrument.responses[":SYST:ERR:ALL?"] = errors
    meter = keithley2400()
    meter._instr = instrument
    with pytest.raises(RuntimeError) as caught:
        meter.output_enabled = True
    assert str(caught.value) == errors
    assert instrument.writes == [":OUTP:STAT ON"]
    assert instrument.queries == [":SYST:ERR:ALL?"]


def test_error_checks_can_be_deferred_for_async_trigger_sequence():
    instrument = FakeInstrument()
    meter = keithley2400()
    meter._instr = instrument
    meter.check_errors_after_write = False
    meter.initiate()
    assert instrument.queries == []
    meter.check_errors()
    assert instrument.queries == [":SYST:ERR:ALL?"]


def test_query_timeout_does_not_issue_error_query_into_pending_response():
    instrument = FakeInstrument()
    timeout = pyvisa.errors.VisaIOError(constants.StatusCode.error_timeout)
    instrument.responses[":READ?"] = timeout
    meter = keithley2400()
    meter._instr = instrument
    with pytest.raises(pyvisa.errors.VisaIOError) as caught:
        meter.read()
    assert caught.value is timeout
    assert instrument.queries == [":FORM:DATA?", ":READ?"]


@pytest.mark.parametrize("order,packing", [("NORM", ">"), ("SWAP", "<")])
def test_gpib_binary_read_uses_eoi_and_restores_termination(order, packing):
    instrument = FakeGpibInstrument()
    value = struct.unpack(">f", b"?\x80\n\x00")[0]
    instrument.block = b"#0" + struct.pack(packing + "2f", value, -0.5) + b"\n"
    instrument.responses.update({":FORM:DATA?": "REAL,32", ":FORM:BORD?": order})
    meter = keithley2400()
    meter._instr = instrument
    assert meter.read() == (value, -0.5)
    assert instrument.read_termination == "\n"
    assert instrument.writes == [":READ?"]
    assert instrument.queries == [":FORM:DATA?", ":FORM:BORD?"]


def test_basic_example_uses_public_settings_and_switches_output_off(
    monkeypatch, capsys
):
    import runpy

    class ContextManager(FakeManager):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    instrument = FakeInstrument()
    instrument.responses.update(
        {
            "*IDN?": "KEITHLEY INSTRUMENTS INC.,MODEL 2400,1234,C32",
            ":SOUR:FUNC?": "VOLT",
            ":READ?": "1.0,0.001,9.91E37,0.5,0",
        }
    )
    manager = ContextManager(instrument)
    monkeypatch.setattr(pyvisa, "ResourceManager", lambda: manager)
    monkeypatch.setattr("sys.argv", ["basic.py", "GPIB0::24::INSTR"])
    example = runpy.run_path("examples/basic.py")
    example["main"]()
    assert "(1.0, 0.001, 9.91e+37, 0.5, 0.0)" in capsys.readouterr().out
    assert instrument.writes[-1] == ":OUTP:STAT OFF"
    assert instrument.closed


@pytest.mark.parametrize("operation", ["save", "recall", "trigger_line"])
def test_invalid_write_parameters_raise_instrument_error(operation):
    instrument = FakeInstrument()
    instrument.responses[":SYST:ERR:ALL?"] = '-222,"Parameter data out of range"'
    meter = keithley2400()
    meter._instr = instrument
    with pytest.raises(RuntimeError, match="Parameter data out of range"):
        if operation == "save":
            meter.save_setup(5)
        elif operation == "recall":
            meter.recall_setup(5)
        else:
            meter.trigger_input_line = 5
    assert instrument.queries == [":SYST:ERR:ALL?"]
    assert len(instrument.writes) == 1


def test_timeout_ms_exposes_session_setting_without_instrument_commands():
    instrument = FakeInstrument()
    meter = keithley2400()
    meter.connect("GPIB0::24::INSTR", resource_manager=FakeManager(instrument))
    assert meter.timeout_ms == 2000
    meter.timeout_ms = 60000
    assert instrument.timeout == 60000
    instrument.timeout = float("inf")
    assert meter.timeout_ms == float("inf")
    assert instrument.writes == instrument.queries == []


def test_timeout_ms_requires_connected_session():
    meter = keithley2400()
    with pytest.raises(RuntimeError, match="not connected"):
        _ = meter.timeout_ms
    with pytest.raises(RuntimeError, match="not connected"):
        meter.timeout_ms = 60000


def test_timeout_example_uses_estimate_and_restores_session_timeout(monkeypatch):
    class TimedInstrument(FakeInstrument):
        def __init__(self):
            super().__init__()
            self.query_timeouts: dict[str, float] = {}
            self.query_history: list[tuple[str, float]] = []

        def query(self, message: str, delay: float | None = None) -> str:
            self.query_timeouts[message] = self.timeout
            self.query_history.append((message, self.timeout))
            return super().query(message, delay)

    instrument = TimedInstrument()
    instrument.responses.update(
        {
            "*TST?": "0",
            ":SYST:LFR?": "50",
            ":READ?": "0.001",
            ":TRAC:DATA?": "0.001",
            "*OPC?": "1",
            ":FETC?": "0.001",
        }
    )
    manager = FakeManager(instrument)
    monkeypatch.setattr(pyvisa, "ResourceManager", lambda: manager)
    monkeypatch.setattr("sys.argv", ["timeouts.py", "GPIB0::24::INSTR"])
    example = runpy.run_path("examples/timeouts.py")
    example["main"]()
    # Ten readings, 10 PLC at 50 Hz, three A/D conversions per reading;
    # Appendix A Case I overheads, 2x margin, and 5 s transfer allowance.
    assert instrument.query_timeouts[":READ?"] == 17253
    assert instrument.query_timeouts["*OPC?"] == 17253
    assert instrument.query_timeouts["*TST?"] == 30000
    assert instrument.query_timeouts[":TRAC:DATA?"] == 30000
    assert instrument.query_history[-1] == (":SYST:ERR:ALL?", 2000)
    assert ":ABOR" not in instrument.writes
    assert ":SYST:CCH OFF" not in instrument.writes
    assert instrument.timeout == 2000
    assert instrument.writes[-1] == ":OUTP:STAT OFF"
    assert instrument.closed


@pytest.mark.parametrize(
    "script", ["basic.py", "advanced_configuration.py", "timeouts.py"]
)
def test_examples_parse_serial_communication_arguments(script, monkeypatch):
    arguments = [
        script,
        "ASRL1::INSTR",
        "--baud-rate",
        "9600",
        "--read-termination",
        "CRLF",
        "--write-termination",
        "CR",
    ]
    expected = {
        "baud_rate": 9600,
        "read_termination": "\r\n",
        "write_termination": "\r",
    }
    if script == "timeouts.py":
        expected["timeout"] = 2000
    else:
        arguments.extend(["--timeout-ms", "5000"])
        expected["timeout"] = 5000
    monkeypatch.setattr("sys.argv", arguments)
    example = runpy.run_path(f"examples/{script}")
    assert example["parse_args"]() == ("ASRL1::INSTR", expected)


def test_completion_example_reports_init_error_after_waiting(monkeypatch):
    class InitErrorInstrument(FakeInstrument):
        def write(
            self,
            message: str,
            termination: str | None = None,
            encoding: str | None = None,
        ) -> int:
            if message == ":INIT":
                self.responses[":SYST:ERR:ALL?"] = deque(
                    ['-213,"Init ignored"', '0,"No error"']
                )
            return super().write(message, termination, encoding)

    instrument = InitErrorInstrument()
    instrument.responses.update(
        {
            "*TST?": "0",
            ":SYST:LFR?": "50",
            ":READ?": "0.001",
            ":TRAC:DATA?": "0.001",
            "*OPC?": "1",
        }
    )
    monkeypatch.setattr(pyvisa, "ResourceManager", lambda: FakeManager(instrument))
    monkeypatch.setattr("sys.argv", ["timeouts.py", "GPIB0::24::INSTR"])
    example = runpy.run_path("examples/timeouts.py")
    with pytest.raises(RuntimeError, match="Init ignored"):
        example["main"]()
    assert instrument.queries[-3:] == ["*OPC?", ":SYST:ERR:ALL?", ":SYST:ERR:ALL?"]
    assert instrument.timeout == 2000


def test_timeout_example_rejects_timeout_argument(monkeypatch):
    monkeypatch.setattr(
        "sys.argv", ["timeouts.py", "GPIB0::24::INSTR", "--timeout-ms", "5000"]
    )
    example = runpy.run_path("examples/timeouts.py")
    with pytest.raises(SystemExit) as caught:
        example["parse_args"]()
    assert caught.value.code == 2
