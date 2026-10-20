# Keithley 2400

A PyVISA driver exposing the SCPI commands in the manufacturer's [Series 2400 SourceMeter User's Manual, revision K](https://download.tek.com/manual/2400S-900-01_K-Sep2011_User.pdf). Settings and read-only values are properties; actions are methods. Command implementations are grouped by subsystem, with shared endpoints for voltage/current sources, sense functions, limit tests, display windows, and status registers.

Install with `pip install .`. A VISA backend and suitable adapter support are required; PyVISA-py with serial support is included. Run the behavioral tests with `uv run --extra test pytest`.

```python
import pyvisa
from keithley2400 import keithley2400

with pyvisa.ResourceManager() as manager, keithley2400() as meter:
    meter.connect("GPIB0::24::INSTR", resource_manager=manager)
    try:
        print(meter.identity)
        meter.abort()
        meter.data_format = "ASC"
        meter.data_elements = ("VOLT", "CURR")
        meter.auto_output_off = False
        meter.arm_source = "IMM"
        meter.arm_count = 1
        meter.trigger_source = "IMM"
        meter.trigger_count = 1
        meter.trigger_delay = 0
        meter.source_function = "VOLT"
        meter.source_voltage.mode = "FIX"
        meter.source_level = 1.0
        meter.sense_functions = ("CURR",)
        meter.sense_auto_range = True
        meter.current_compliance = 0.01
        meter.output_enabled = True
        voltage, current = meter.read()
        print(current)
    finally:
        meter.output_enabled = False
```

The [basic example](examples/basic.py) puts the single-read recipe in an application function. There is no `configure_single_read()` method in the driver. `connect()` configures communication only: it sends no instrument commands, does not abort operations, and does not change measurement settings. Context exit closes only the instrument session; it leaves the resource manager and output control to the caller.

`source_function` selects VOLT, CURR, or the documented MEM source-memory mode. It does not also select FIX/SWE/LIST mode: configure that independently on `source_voltage.mode` or `source_current.mode`. The source level/range conveniences infer voltage or current from `source_function` and reject MEM, which has no single level or range. Source and sense function validation are separate. `sense_auto_range` infers the sole enabled sense function; with concurrent measurements, use `sense_voltage.auto_range`, `sense_current.auto_range`, or `sense_resistance.auto_range`. NPLC is global across functions, as documented. Documented numeric query modifiers are exposed as `*_limits` properties returning `NumericLimits(minimum, maximum, default)`; for example, `meter.source_voltage.level_limits`.

`read()`, `fetch()`, `measure()`, and the trace/calculation data properties return flat tuples of floats matching the selected element layout and reading count. No fixed five-field `Measurement` type is imposed. Numeric overflow (`+9.9E37`) and unavailable-value (`+9.91E37`) sentinels are preserved. Reading data respects `data_format` and, for GPIB IEEE-754 binary blocks, `byte_order`. The guide allows binary reading transfers only over GPIB; serial-to-Ethernet bridges use ASCII.

## Communication

Write termination defaults to LF for GPIB and CR for RS-232, selected from the opened VISA resource type, including aliases. GPIB read termination defaults to LF. RS-232 requires a nonempty `read_termination` matching the instrument's front-panel setting: CR, CR+LF, LF, or LF+CR. Serial baud rate, parity, and flow control must also match. Supply those through `connect()` resource keyword arguments. Explicit transport options override defaults. Missing required terminations close the session and raise `ValueError` before instrument commands are sent.

A transparent serial-to-Ethernet adapter uses a raw TCP socket, with both terminations specified:

```python
with keithley2400() as meter:
    meter.connect(
        "TCPIP0::adapter-host::4001::SOCKET",
        write_termination="\r",
        read_termination="\r\n",  # Match the Keithley's response setting.
    )
    print(meter.identity)
```

Replace the hostname and port with the adapter's raw TCP endpoint. Configure the adapter's serial settings separately to match the Keithley. The driver does not configure adapter firmware or negotiate Telnet/RFC 2217.

## Errors and synchronization

Writes automatically drain the error queue and raise `RuntimeError` containing the raw instrument error messages when any are returned. Queries consume their response without interleaving an error query. `check_errors()` is also available explicitly, along with the guide's individual error/status queue commands.

Error checking is distinct from operation synchronization. `wait_complete()` uses `*OPC?`; `set_operation_complete()` queues `*OPC`; `wait_to_continue()` sends `*WAI` (a documented no-op on this instrument). Most commands, including error queries, are queued while a source-measure sequence runs. Automatic checks after `initiate()` can therefore block until the sequence finishes. For asynchronous or software-triggered sequences, set `meter.check_errors_after_write = False`, issue the sequence and its triggers, wait for completion, then call `meter.check_errors()` and restore the flag when appropriate. No checks or extra queries occur merely on connection.

Query timeouts propagate as their original PyVISA exceptions. The driver does not automatically query errors after a timeout: a pending response may still arrive, and another query could interrupt it or read the wrong reply (manual Appendix B). Resolve the pending response with `read_response()` or clear the interface using the appropriate VISA/device procedure before issuing further queries.

## Command coverage and verification

The [command coverage index](docs/commands.md) maps the common commands, signal-oriented commands, every SCPI subsystem, and the contact-check/protocol extensions to Python APIs. Model-specific commands are exposed with their documented restrictions; exposing a command does not make an option available on hardware that lacks it. The guide contains several inconsistent summary/detail spellings; the coverage notes identify those cases and follow the detailed reference without speculative fallback commands.

Calibration service commands are not specified in this user/programming reference and are not invented by this driver. The separate 488.1 bus protocol described in Appendix G is not the SCPI programming language; its documented SCPI MEP controls are exposed. Calibration service commands would require the corresponding service programming documentation.

Tests exercise representative protocol contracts, binary framing/byte order, lifecycle behavior, and automatic error/timeout handling. Physical instruments and Ethernet adapters have not been tested.
