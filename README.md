# Keithley 2400

A small PyVISA driver for common source-measure work on the Keithley 2400. It exposes configuration properties, a single-reading `read()` method, identification, and basic status helpers. The public class is `keithley2400` (lowercase); `Measurement` is the immutable result type.

You can use `with keithley2400() as meter:` and call `connect()` inside the block. Exiting the block disconnects the session, including when an exception occurs. Output control remains explicit: turn the output off in a `finally` block when needed, as below.

```python
import pyvisa
from keithley2400 import keithley2400

rm = pyvisa.ResourceManager()
meter = keithley2400()
meter.connect("GPIB0::24::INSTR", resource_manager=rm)
try:
    print(meter.identification)
    meter.source_function = "VOLT"
    meter.source_range = 20
    meter.source_level = 1.0
    meter.sense_functions = ("CURR",)
    meter.current_compliance = 0.01
    meter.output_enabled = True
    reading = meter.read()
    print(reading.current)
finally:
    meter.output_enabled = False
    meter.disconnect()
```

`connect()` opens and owns the PyVISA instrument session; disconnect closes that session. A caller-supplied resource manager remains caller-owned. Connection aborts any pending trigger cycle, configures ASCII transfer, a fixed five-field `READ?` response (`VOLT,CURR,RES,TIME,STAT`), one immediate arm/trigger, zero trigger delay, and disables automatic output on/off. It does not reset the instrument, change the source function or level, or enable output. Select `source_function` before taking readings to establish fixed sourcing mode. Other settings, including sense functions, ranges, filtering and source delay, are inherited; configure those needed by your measurement. Output remains explicitly controlled by `output_enabled`. Setting `source_function` selects fixed mode for the chosen voltage or current source function. Multiple sense functions enable concurrent measurement.

Write termination defaults to LF for GPIB and CR for RS-232, selected from the opened VISA resource type (including when connecting by alias). GPIB read termination defaults to LF. RS-232 requires an explicit, nonempty `read_termination` matching the instrument’s front-panel setting (CR, CR+LF, LF, or LF+CR); if omitted, the session is closed and `connect()` raises `ValueError` before sending commands. Set serial baud rate, parity, and flow control through `connect()` kwargs to match the instrument too. Explicit transport kwargs override the defaults. For GPIB, PyVISA normally also asserts EOI with the message terminator.

For a transparent serial-to-Ethernet adapter, use a raw TCP socket resource and specify both terminations. TCP sockets require nonempty `read_termination` and `write_termination`; missing values close the session and raise `ValueError` before commands are sent. Configure baud rate, parity, and flow control on the adapter to match the Keithley. The driver does not configure the adapter or negotiate Telnet/RFC 2217.

```python
with keithley2400() as meter:
    meter.connect(
        "TCPIP0::adapter-host::4001::SOCKET",
        write_termination="\r",
        read_termination="\r\n",  # Match the Keithley's response setting.
    )
    print(meter.identification)
```

Replace the hostname and port with the adapter's raw TCP endpoint. Adapter hardware has not been tested.


`read()` returns the five values in the manual's fixed ASCII order. The status field is an integer. Numeric sentinels are preserved as returned: `+9.9E37` indicates overflow and `+9.91E37` indicates an unavailable element. Configure only functions and ranges supported by the connected instrument; this compact driver does not model all instrument modes, sweeps, triggering, or error decoding. NPLC is limited here to the standard 2400 range of 0.01 to 10 PLC.

The command behavior follows the [Keithley 2400 Series SourceMeter User's Manual](https://download.tek.com/manual/2400S-900-01_K-Sep2011_User.pdf), especially sections 3 (basic source-measure operation), 14 (remote operations), and 18 (SCPI command reference). The instrument family has model and firmware variations; validate range/function combinations against the connected unit's manual. This driver has been tested with a fake PyVISA transport, not physical hardware.

Install with `pip install .` and a VISA backend supported by your interface. The included PyVISA-py backend supports serial; GPIB also needs suitable adapter support. Run tests with `uv run --extra test pytest`. Instrument errors remain in the error queue until `read_error()` removes them; setting a property does not automatically query that queue.
