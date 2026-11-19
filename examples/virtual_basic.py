"""Run the virtual Keithley driver without an instrument or VISA resource.

From the project root, after installing the project dependencies, run:

    uv run python examples/virtual_basic.py

No connection arguments are needed. The virtual instrument returns the programmed
source value and zero for enabled measured quantities; it does not model a load.
"""

from keithley2400 import virtual_keithley2400


def main() -> None:
    """Configure the virtual source and print its deterministic reading response."""
    with virtual_keithley2400() as smu:
        smu.connect("virtual")
        print(smu.identity)
        smu.reset()
        try:
            smu.source_voltage_level = 1.0
            smu.current_compliance = 0.01
            smu.output_enabled = True
            print(smu.read())
        finally:
            smu.output_enabled = False


if __name__ == "__main__":
    main()
