import io
from pathlib import PurePosixPath

import pytest

from hlsync.progress import DirectoryReadProgress


def test_remote_progress_counts_and_interruption_cleanup(monkeypatch):
    monkeypatch.delenv("TERM", raising=False)

    class Terminal(io.StringIO):
        def isatty(self):
            return True

    output = Terminal()
    with pytest.raises(KeyboardInterrupt):
        with DirectoryReadProgress(output) as reading:
            reading.counts(2, 12)
            reading.reading(PurePosixPath("notes"))
            assert "2/12 discovered directories read · notes/" in output.getvalue()
            reading.message("Recovered interrupted upload.")
            raise KeyboardInterrupt
    assert "Recovered interrupted upload.\n" in output.getvalue()
    assert output.getvalue().endswith("\r\033[2K")
    assert "Read 2/12 directories." not in output.getvalue()
