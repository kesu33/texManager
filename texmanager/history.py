"""Persistent history log for actions TeXManager performs.

Every significant action (detection runs, uninstall commands) is appended to
a log file so the user can review exactly what code was executed. All writes
are best-effort: logging never raises into the UI.
"""
import tempfile
import threading
from datetime import datetime
from pathlib import Path

_lock = threading.Lock()


def _log_path() -> Path:
    candidates = [
        Path(__file__).resolve().parent.parent / "logs",
        Path.home() / ".local" / "share" / "texmanager",
    ]
    for directory in candidates:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            probe = directory / ".write_test"
            probe.write_text("")
            probe.unlink()
            return directory / "texmanager-history.log"
        except OSError:
            continue
    fallback = Path(tempfile.gettempdir()) / "texmanager"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback / "texmanager-history.log"


def log_event(function: str, command: str = "", result: str = "") -> None:
    try:
        path = _log_path()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [f"[{ts}] FUNCTION: {function}"]
        if command:
            lines.append(f"    COMMAND: {command}")
        if result:
            lines.append(f"    RESULT: {result}")
        text = "\n".join(lines) + "\n"
        with _lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(text)
    except Exception:
        pass


def read_history() -> str:
    try:
        return _log_path().read_text(encoding="utf-8")
    except Exception:
        return ""
