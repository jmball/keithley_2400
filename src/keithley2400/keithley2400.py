"""Keithley 2400 SCPI command interface."""

from ._calculation import CalculationCommands
from ._source_sense import SourceSenseCommands
from ._system import SystemCommands


class keithley2400(SourceSenseCommands, CalculationCommands, SystemCommands):
    """Control a Keithley 2400 using the manufacturer's SCPI command set.

    Connecting configures communication only. Writes check the instrument error
    queue by default. Disable check_errors_after_write for asynchronous trigger
    sequences, then explicitly check_errors() after the operation completes.
    """
