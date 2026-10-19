from __future__ import annotations

import pytest

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
        return self.instrument


def test_connect_configures_single_ascii_read_and_forwards_transport_options():
    instrument = FakeInstrument()
    manager = FakeManager(instrument)
    meter = keithley2400()

    meter.connect("ASRL1::INSTR", resource_manager=manager, baud_rate=19200, write_termination="\r")

    name, options = manager.calls[0]
    assert name == "ASRL1::INSTR"
    assert options == {"encoding": "ascii", "read_termination": "\n", "write_termination": "\r", "baud_rate": 19200}
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
    assert instrument.closed


def test_read_parses_five_fixed_fields_and_preserves_sentinel_values():
    instrument = FakeInstrument()
    instrument.responses[":READ?"] = "+9.91E37, -2.0E-3, +9.9E37, 1.25, 64\n"
    meter = keithley2400()
    meter._instrument = instrument

    assert meter.read() == Measurement(9.91e37, -0.002, 9.9e37, 1.25, 64)


def test_configuration_properties_use_documented_scpi_commands():
    instrument = FakeInstrument()
    instrument.responses[":SOUR:FUNC?"] = "VOLT"
    instrument.responses[":OUTP?"] = "1"
    meter = keithley2400()
    meter._instrument = instrument

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
    meter._instrument = instrument

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
    meter._instrument = instrument

    with pytest.raises(ValueError, match="five READ"):
        meter.read()


def test_initialization_failure_closes_open_instrument():
    class BrokenInstrument(FakeInstrument):
        def write(self, command):
            super().write(command)
            if command == ":FORM:DATA ASC":
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


def test_readback_and_error_queue_use_documented_responses():
    instrument = FakeInstrument()
    instrument.responses.update({
        ":SENS:FUNC?": '\"VOLT:DC\",\"CURR:DC\"',
        ":SENS:CURR:PROT?": "+1.000000E-02",
        ":SYST:RSEN?": "0",
        ":SYST:ERR?": '-222,"Parameter data out of range"',
    })
    meter = keithley2400()
    meter._instrument = instrument

    assert meter.sense_functions == ("VOLT", "CURR")
    assert meter.current_compliance == 0.01
    assert meter.remote_sense is False
    assert meter.read_error() == '-222,"Parameter data out of range"'
