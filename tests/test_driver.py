from __future__ import annotations

import pytest
from pyvisa.resources import SerialInstrument, TCPIPSocket

from keithley2400 import Measurement, keithley2400


class FakeInstrument:
    def __init__(self):
        self.writes = []
        self.responses = {}
        self.closed = False

    def write(self, command):
        self.writes.append(command)

    def query(self, command):
        return self.responses[command]

    def close(self):
        self.closed = True


class FakeManager:
    def __init__(self, instrument):
        self.instrument = instrument
        self.calls = []

    def open_resource(self, name, **kwargs):
        self.calls.append((name, kwargs))
        self.instrument.__dict__.update(kwargs)
        return self.instrument


class FakeSerialInstrument(FakeInstrument, SerialInstrument):
    _session = None

    def write(self, command):
        assert self.write_termination == "\r"
        super().write(command)


def test_connect_only_configures_communication_and_forwards_transport_options():
    instrument = FakeSerialInstrument()
    manager = FakeManager(instrument)
    meter = keithley2400()

    meter.connect("serial_alias", resource_manager=manager, baud_rate=19200, read_termination="\r\n")

    name, options = manager.calls[0]
    assert name == "serial_alias"
    assert options == {"encoding": "ascii", "read_termination": "\r\n", "baud_rate": 19200}
    assert instrument.write_termination == "\r"
    assert instrument.writes == []
    meter.disconnect()
    assert instrument.closed


def test_gpib_connection_sets_lf_without_sending_commands():
    instrument = FakeInstrument()
    meter = keithley2400()
    meter.connect("GPIB0::24::INSTR", resource_manager=FakeManager(instrument))

    assert instrument.write_termination == "\n"
    assert instrument.read_termination == "\n"
    assert instrument.writes == []
    meter.disconnect()


def test_explicit_setup_configures_single_read_protocol():
    instrument = FakeInstrument()
    meter = keithley2400()
    meter.connect("GPIB0::24::INSTR", resource_manager=FakeManager(instrument))

    meter.abort()
    meter.configure_single_read()

    assert instrument.writes == [
        ":ABOR",
        ":FORM:DATA ASC",
        ":SOUR:CLE:AUTO OFF",
        ":FORM:ELEM VOLT,CURR,RES,TIME,STAT",
        ":ARM:SOUR IMM",
        ":ARM:COUN 1",
        ":TRIG:SOUR IMM",
        ":TRIG:COUN 1",
        ":TRIG:DEL 0",
    ]
    meter.disconnect()


@pytest.mark.parametrize("options", [{}, {"read_termination": None}, {"read_termination": ""}])
def test_serial_requires_read_termination_before_sending_commands(options):
    instrument = FakeSerialInstrument()
    meter = keithley2400()

    with pytest.raises(ValueError, match="serial connections require read_termination"):
        meter.connect("serial_alias", resource_manager=FakeManager(instrument), **options)

    assert instrument.writes == []
    assert instrument.closed
    assert not meter.connected


def test_read_parses_five_fixed_fields_and_preserves_sentinel_values():
    instrument = FakeInstrument()
    instrument.responses[":READ?"] = "+9.91E37, -2.0E-3, +9.9E37, 1.25, 64\n"
    meter = keithley2400()
    meter._instr = instrument

    assert meter.read() == Measurement(9.91e37, -0.002, 9.9e37, 1.25, 64)


def test_configuration_properties_use_documented_scpi_commands():
    instrument = FakeInstrument()
    instrument.responses[":SOUR:FUNC?"] = "VOLT"
    instrument.responses[":OUTP?"] = "1"
    meter = keithley2400()
    meter._instr = instrument

    meter.source_function = "VOLT"
    meter.source_level = 2.5
    meter.sense_functions = ("CURR", "VOLT")
    meter.output_enabled = True

    assert meter.output_enabled is True
    assert instrument.writes == [
        ":SOUR:FUNC VOLT",
        ":SOUR:VOLT:MODE FIX",
        ":SOUR:VOLT:LEV 2.5",
        ":SENS:FUNC:CONC ON",
        ":SENS:FUNC:OFF:ALL",
        ':SENS:FUNC:ON "CURR"',
        ':SENS:FUNC:ON "VOLT"',
        ":OUTP ON",
    ]


def test_invalid_settings_fail_before_writing():
    instrument = FakeInstrument()
    meter = keithley2400()
    meter._instr = instrument

    with pytest.raises(ValueError):
        meter.nplc = 11
    with pytest.raises(ValueError):
        meter.terminals = "side"
    with pytest.raises(ValueError):
        meter.source_function = "RES"
    assert instrument.writes == []


def test_read_rejects_non_five_field_response():
    instrument = FakeInstrument()
    instrument.responses[":READ?"] = "1,2,3"
    meter = keithley2400()
    meter._instr = instrument

    with pytest.raises(ValueError, match="five READ"):
        meter.read()


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
    assert meter.connected is False


def test_methods_require_connection():
    meter = keithley2400()
    with pytest.raises(RuntimeError, match="not connected"):
        meter.read()
    with pytest.raises(RuntimeError, match="not connected"):
        meter.output_enabled = True


def test_abort_and_automatic_output_control_use_documented_commands():
    instrument = FakeInstrument()
    instrument.responses[":SOUR:CLE:AUTO?"] = "1"
    meter = keithley2400()
    meter._instr = instrument

    assert meter.auto_output_off is True
    meter.auto_output_off = False
    meter.abort()

    assert instrument.writes == [":SOUR:CLE:AUTO OFF", ":ABOR"]


@pytest.mark.parametrize("fail", [False, True])
def test_context_closes_session_on_normal_and_exceptional_exit(fail):
    instrument = FakeInstrument()
    meter = keithley2400()

    def use_instrument():
        with meter as entered:
            assert entered is meter
            assert not meter.connected
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


def test_readback_and_error_queue_use_documented_responses():
    instrument = FakeInstrument()
    instrument.responses.update({
        ":SENS:FUNC?": '\"VOLT:DC\",\"CURR:DC\"',
        ":SENS:CURR:PROT?": "+1.000000E-02",
        ":SYST:RSEN?": "0",
        ":SYST:ERR?": '-222,"Parameter data out of range"',
    })
    meter = keithley2400()
    meter._instr = instrument

    assert meter.sense_functions == ("VOLT", "CURR")
    assert meter.current_compliance == 0.01
    assert meter.remote_sense is False
    assert meter.read_error() == '-222,"Parameter data out of range"'


class FakeSocketInstrument(FakeInstrument, TCPIPSocket):
    _session = None
    read_termination = None
    write_termination = None

    def write(self, command):
        assert self.write_termination == "\r"
        assert self.read_termination == "\r\n"
        super().write(command)


def test_tcp_socket_preserves_adapter_terminations_and_reads_measurement():
    instrument = FakeSocketInstrument()
    instrument.responses[":READ?"] = "1.0,0.002,9.91E37,0.5,0"
    meter = keithley2400()

    with meter:
        meter.connect(
            "adapter_alias",
            resource_manager=FakeManager(instrument),
            read_termination="\r\n",
            write_termination="\r",
        )
        assert instrument.writes == []
        meter.abort()
        meter.configure_single_read()
        assert meter.read() == Measurement(1.0, 0.002, 9.91e37, 0.5, 0)

    assert instrument.closed


@pytest.mark.parametrize("options", [
    {},
    {"read_termination": "\r\n"},
    {"write_termination": "\r"},
])
def test_tcp_socket_requires_both_terminations_before_sending_commands(options):
    instrument = FakeSocketInstrument()
    meter = keithley2400()

    with pytest.raises(ValueError, match="TCP sockets require"):
        meter.connect("adapter_alias", resource_manager=FakeManager(instrument), **options)

    assert instrument.writes == []
    assert instrument.closed
    assert not meter.connected
