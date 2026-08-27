"""Backend helpers that query TeX Live for installed packages.

All functions are GUI-agnostic and safe to call from a worker thread: they
never touch GTK and only shell out to ``tlmgr`` or read the local TLPDB file.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

# tlmgr prints one package per line as:  "i <pkg> <short description>"
_INSTALLED_LINE_RE = re.compile(r"^i\s+(\S+)", re.MULTILINE)
# The local TLPDB lists each package with a top-level "name <pkg>" entry.
_TLPDB_NAME_RE = re.compile(r"^name\s+(\S+)", re.MULTILINE)
_META_RE = re.compile(r"^00texlive\.")


def find_tlmgr() -> str | None:
    """Return the path to ``tlmgr`` on PATH, or ``None`` if not found."""
    return shutil.which("tlmgr")


def list_installed_packages(tlmgr: str | None = None) -> list[str]:
    """Return the sorted names of every installed TeX Live package.

    Prefers ``tlmgr list --only-installed`` (authoritative) and falls back to
    grepping the local TLPDB file so it still works when ``tlmgr`` is missing
    or offline.
    """
    tlmgr = tlmgr or find_tlmgr()
    if tlmgr:
        try:
            out = subprocess.run([tlmgr, "list", "--only-installed"],
                                 capture_output=True, text=True, timeout=180)
            if out.returncode == 0:
                # tlmgr prints "i <name>: <description>" — drop the trailing colon
                names = [n.rstrip(":") for n in _INSTALLED_LINE_RE.findall(out.stdout)]
                if names:
                    return sorted(names)
        except (OSError, subprocess.SubprocessError):
            pass
    return _installed_from_tlpdb()


def _installed_from_tlpdb() -> list[str]:
    tlpdb = _find_tlpdb()
    if tlpdb is None:
        return []
    try:
        text = tlpdb.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    names = [m for m in _TLPDB_NAME_RE.findall(text) if not _META_RE.match(m)]
    return sorted(names)


def _find_tlpdb() -> Path | None:
    roots = [
        Path.home() / "texlive",
        Path("/usr/local/texlive"),
        Path("/opt/texlive"),
    ]
    candidates: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for year_dir in root.iterdir():
            if not year_dir.is_dir():
                continue
            tlpdb = year_dir / "tlpkg" / "texlive.tlpdb"
            if tlpdb.is_file():
                candidates.append(tlpdb)
    if not candidates:
        return None
    # Prefer the lexicographically-last (newest) TLPDB on disk.
    return sorted(candidates)[-1]
