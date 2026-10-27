# Keithley 2400

A PyVISA driver exposing the SCPI commands in the manufacturer's [Series 2400 SourceMeter User's Manual, revision K](https://download.tek.com/manual/2400S-900-01_K-Sep2011_User.pdf). The implementation is one ordinary instrument class in [keithley2400.py](src/keithley2400/keithley2400.py), grouped by subsystem with comments. Settings and read-only values are direct properties; actions are methods. Indexed limit tests take an index argument. There are no subsystem base classes or intermediate source, sense, display, or status objects.

Install with `pip install .`. A VISA backend and suitable adapter support are required; PyVISA-py with serial support is included.

For development, use **ty** for type checking and **Ruff** for linting and formatting. Their configuration and locked development dependencies live in `pyproject.toml` and `uv.lock`. Install and run the same checks used by CI:

```sh
uv sync --locked --extra test
uv run --locked ty check --error-on-warning
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest -q
```

Apply formatting with `uv run ruff format .` and safe lint fixes with `uv run ruff check --fix .`. Checks cover source, tests, and examples; CI runs on Python 3.10 and 3.13.

```python
from contextlib import closing

import pyvisa
from keithley2400 import keithley2400

with closing(pyvisa.ResourceManager()) as manager, keithley2400() as meter:
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
        meter.source_voltage_mode = "FIX"
        meter.source_level = 1.0
        meter.sense_concurrent = False
        meter.disable_all_sense_functions()
        meter.enable_sense_functions(("CURR",))
        meter.sense_auto_range = True
        meter.current_compliance = 0.01
        meter.output_enabled = True
        voltage, current = meter.read()
        print(current)
    finally:
        meter.output_enabled = False
```

The [basic example](examples/basic.py) puts the single-read recipe in an application function. The [advanced configuration example](examples/advanced_configuration.py) composes concurrency, disabling, and enabling commands to replace the enabled sense functions. In the driver, `sense_functions` is read-only; callers explicitly use `sense_concurrent`, `disable_all_sense_functions()`, and `enable_sense_functions()` when configuring measurements. There is no `configure_single_read()` method in the driver. `connect()` configures communication only: it sends no instrument commands, does not abort operations, and does not change measurement settings. Context exit closes only the instrument session; it leaves the resource manager and output control to the caller.

`source_function` selects VOLT, CURR, or the documented MEM source-memory mode. It does not also select FIX/SWE/LIST mode: configure that independently on `source_voltage_mode` or `source_current_mode`. The source level/range conveniences infer voltage or current from `source_function` and reject MEM, which has no single level or range. Write parameters are validated by the instrument through automatic error checking. Sense functions used in query headers are validated locally to prevent invalid queries from timing out. `sense_auto_range` infers the sole enabled sense function; with concurrent measurements, use `sense_voltage_auto_range`, `sense_current_auto_range`, or `sense_resistance_auto_range`. NPLC is global across functions, as documented. Documented numeric query modifiers have independent read-only properties ending in `_minimum`, `_maximum`, or `_default`; for example, `meter.source_voltage_level_minimum` sends only `:SOUR:VOLT:LEV? MIN`. Indexed limit thresholds have corresponding methods such as `get_limit_test_upper_default(index)`.

`read()`, `fetch()`, `measure()`, and the trace/calculation data properties return flat tuples of floats matching the selected element layout and reading count. No fixed five-field `Measurement` type is imposed. Numeric overflow (`+9.9E37`) and unavailable-value (`+9.91E37`) sentinels are preserved. Reading data respects `data_format` and, for GPIB IEEE-754 binary blocks, `byte_order`. The guide allows binary reading transfers only over GPIB; serial-to-Ethernet bridges use ASCII.

## Direct API names

The former nested API has been replaced with direct members on the instrument:

```python
meter.source_voltage_mode = "FIX"
meter.source_voltage_level = 1.0
meter.sense_current_auto_range = True
meter.display_top_text = "Ready"
meter.measurement_status_enable = 7
meter.set_limit_test_upper(2, 1.5)
upper = meter.get_limit_test_upper(2)
```

Indexed limit getters and setters use `get_limit_test_*` and `set_limit_test_*` methods; no limit object is created. Source and sense property commands contain their explicit VOLT, CURR, or RES path. The existing `source_level`, `source_range`, and `sense_auto_range` conveniences still query the selected function when needed; they do not cache instrument configuration.

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
