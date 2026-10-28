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
Physical instruments and Ethernet adapters have not been tested.

## Development

Install the locked environment and run the project checks:

```sh
uv sync --locked --extra test
uv run --locked ty check --error-on-warning
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest -q
```

Use `uv run ruff format .` for formatting and `uv run ruff check --fix .`
for safe lint fixes. Configuration lives in `pyproject.toml`.
