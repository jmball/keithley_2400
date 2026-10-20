"""Command recorder for subsystem contracts; transport behavior is tested separately."""

from keithley2400 import keithley2400


class RecordingMeter(keithley2400):
    def __init__(self, responses=None):
        super().__init__()
        self.writes = []
        self.queries = []
        self.responses = {":FORM:DATA?": "ASC"}
        self.responses.update(responses or {})

    def _write(self, command):
        self.writes.append(command)

    def _query(self, command):
        self.queries.append(command)
        return self.responses[command]
