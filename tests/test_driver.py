from __future__ import annotations

import struct
from collections import deque

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
        self.writes = []
        self.queries = []
        self.responses: dict[str, str | deque[str] | Exception] = {
            ":SYST:ERR:ALL?": '0,"No error"',
            ":FORM:DATA?": "ASC",
        }
        self.closed = False

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
    example = runpy.run_path("examples/basic.py")
    example["main"]()
    assert "0.001" in capsys.readouterr().out
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
