"""Shared contract fixture; virtual by default, hardware only on request."""

from collections.abc import Iterator

import pytest
import pyvisa

from keithley2400 import keithley2400, virtual_keithley2400


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register optional hardware connection settings."""
    group = parser.getgroup("keithley2400")
    group.addoption("--resource-name", help="VISA resource name for hardware tests")
    group.addoption(
        "--read-termination", choices=("CR", "LF", "CRLF", "LFCR"), default=None
    )
    group.addoption(
        "--write-termination", choices=("CR", "LF", "CRLF", "LFCR"), default="CR"
    )
    group.addoption("--timeout-ms", type=float, default=3000)
    group.addoption(
        "--allow-state-changes",
        action="store_true",
        help="allow hardware tests that reset settings and briefly enable output",
    )


TERMINATIONS = {"CR": "\r", "LF": "\n", "CRLF": "\r\n", "LFCR": "\n\r"}


@pytest.fixture(scope="session")
def hardware_instrument(request: pytest.FixtureRequest) -> Iterator[keithley2400]:
    """Yield one hardware connection shared by the whole test session.

    A single connection avoids repeated reconnects, which corrupted commands
    through the tested serial-to-Ethernet adapter, and keeps hardware use
    sequential.
    """
    resource_name = request.config.getoption("--resource-name")
    read_termination = request.config.getoption("--read-termination")
    if read_termination is None:
        pytest.fail("--read-termination is required when --resource-name is supplied")
    manager = pyvisa.ResourceManager("@py")
    device = keithley2400()
    try:
        device.connect(
            resource_name,
            resource_manager=manager,
            read_termination=TERMINATIONS[read_termination],
            write_termination=TERMINATIONS[
                request.config.getoption("--write-termination")
            ],
            timeout=request.config.getoption("--timeout-ms"),
        )
        yield device
    finally:
        try:
            device.disconnect()
        finally:
            manager.close()


@pytest.fixture
def instrument(
    request: pytest.FixtureRequest,
) -> Iterator[keithley2400 | virtual_keithley2400]:
    """Yield a fresh virtual driver, or the shared hardware connection on request."""
    if request.config.getoption("--resource-name") is not None:
        yield request.getfixturevalue("hardware_instrument")
        return
    device = virtual_keithley2400()
    device.connect("virtual", timeout=request.config.getoption("--timeout-ms"))
    try:
        yield device
    finally:
        device.disconnect()


@pytest.fixture
def reset_instrument(
    request: pytest.FixtureRequest,
    instrument: keithley2400 | virtual_keithley2400,
) -> Iterator[keithley2400 | virtual_keithley2400]:
    """Yield a reset instrument; turn output off and reset again afterward.

    Hardware use requires --allow-state-changes because the instrument settings
    are reset and some tests enable the output at low levels.
    """
    hardware = request.config.getoption("--resource-name") is not None
    if hardware and not request.config.getoption("--allow-state-changes"):
        pytest.skip("state-changing hardware test requires --allow-state-changes")
    instrument.reset()
    instrument.check_errors()
    try:
        yield instrument
    finally:
        try:
            instrument.output_enabled = False
        finally:
            instrument.reset()
