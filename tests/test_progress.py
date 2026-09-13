import io
import threading
from pathlib import PurePosixPath

import pytest

from hlsync.progress import DirectoryReadProgress


def test_remote_indicator_animates_during_wait_and_stops_on_interrupt(monkeypatch):
    monkeypatch.delenv("TERM", raising=False)
    animated = threading.Event()

    class Terminal(io.StringIO):
        def isatty(self):
            return True

        def write(self, text):
            result = super().write(text)
            if threading.current_thread() is not threading.main_thread():
                animated.set()
            return result

    output = Terminal()
    reading = DirectoryReadProgress(output)
    with pytest.raises(KeyboardInterrupt):
        with reading:
            reading.reading(PurePosixPath("notes"))
            assert animated.wait(2), "indicator stopped while remote read was waiting"
            reading.message("Recovered interrupted upload.")
            raise KeyboardInterrupt
    assert reading.thread is not None and not reading.thread.is_alive()
    assert "Reading notes" in output.getvalue()
    assert "Recovered interrupted upload.\n" in output.getvalue()
    assert output.getvalue().endswith("\r\033[2K")
    assert "Read 1 directories." not in output.getvalue()
