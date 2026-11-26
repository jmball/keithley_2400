# Keithley 2400

A Python/PyVISA driver for the Keithley 2400 SourceMeter, based on the
[Series 2400 SourceMeter User's Manual, revision K](https://download.tek.com/manual/2400S-900-01_K-Sep2011_User.pdf).

Install with `pip install .`. PyVISA-py with serial support is included;
GPIB requires a suitable VISA backend and adapter support.

The driver exposes settings as properties and actions as methods. Its
[docstrings](src/keithley2400/keithley2400.py) describe arguments, return values,
units, and instrument behavior. Start with the runnable examples:

- [Basic read](examples/basic.py): identify the instrument, source a voltage,
  and print the complete reading response.
- [Advanced configuration](examples/advanced_configuration.py): set source,
  measurement, data-format, and trigger options explicitly.
- [Timeouts](examples/timeouts.py): estimate acquisition time and temporarily
  adjust the communication timeout for longer operations.

Run examples from the project root, replacing the illustrated resource and
communication settings with those for your hardware:

```sh
uv run python examples/basic.py GPIB0::24::INSTR
uv run python examples/basic.py ASRL1::INSTR --baud-rate 9600 --read-termination CRLF
uv run python examples/timeouts.py TCPIP0::adapter-host::4001::SOCKET --read-termination CRLF --write-termination CR
```

Each script's docstring explains its connection options; use `--help` to list
them. Serial and adapter termination settings must match the instrument.
The shared contract tests have passed on a Model 2401 over RS-232 through a
serial-to-Ethernet adapter. Other models, GPIB, and direct serial connections
have not been tested. Through that adapter, commands sent on a new TCP
connection were intermittently corrupted after repeated reconnects; keep one
connection open rather than reconnecting frequently.

## Virtual instrument

Use `from keithley2400 import virtual_keithley2400` as a hardware-free replacement
for the hardware class. It has the same public methods, properties, signatures,
and connection lifecycle. Call `connect("virtual")`; the resource name and any
supplied resource manager are never used to open hardware. Settings persist
across disconnect/reconnect. `reset()` restores the virtual instrument defaults.

[The virtual example](examples/virtual_basic.py) demonstrates ordinary usage:

```sh
uv run python examples/virtual_basic.py
```

The virtual instrument stores settings, source lists, saved setups, trace data,
math expressions, measurement limit tests, and error/status queues. Measurements
return programmed source values and zero for other enabled quantities, preserving
the selected element order and unavailable-value sentinel. It models no load,
noise, real acquisition timing, or protection/contact trips.
Timestamps stay zero. Finite immediate-trigger sequences complete synchronously;
external-trigger waits raise a VISA timeout immediately, and a pending BUS arm
can be completed with `trigger_bus()`. Numeric metadata uses model 2400 bounds;
optional-feature settings are software state rather than hardware capabilities.
Empty measurement/trace buffers return empty tuples. Self-test always passes.

## Development

Install the locked environment and run the project checks:

```sh
uv sync --locked --extra test
uv run --locked ty check --error-on-warning
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest -q
```

The shared contract tests use the virtual instrument by default. To run them
on hardware, supply the connection settings. Tests that reset the instrument and
briefly enable the output (at most 0.5 V with 105 µA compliance) also require
`--allow-state-changes`:

```sh
uv run --locked pytest tests/test_contract.py tests/test_contract_state.py \
    --resource-name TCPIP0::adapter-host::4000::SOCKET \
    --read-termination CRLF --write-termination CR --allow-state-changes
```

Use `uv run ruff format .` for formatting and `uv run ruff check --fix .`
for safe lint fixes. Configuration lives in `pyproject.toml`.
