"""Backend helpers that query TeX Live for installed packages.

All functions are GUI-agnostic and safe to call from a worker thread: they
never touch GTK and only shell out to ``tlmgr`` or read the local TLPDB file.
"""
from __future__ import annotations

import os
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


def texmf_dist_dir() -> str | None:
    """Return the TEXMFDIST root (where installed package files live)."""
    kpse = shutil.which("kpsewhich")
    if kpse:
        try:
            out = subprocess.run([kpse, "-var-value", "TEXMFDIST"],
                                 capture_output=True, text=True, timeout=10)
            if out.returncode == 0:
                val = out.stdout.strip()
                if val:
                    return val
        except (OSError, subprocess.SubprocessError):
            pass
    return None


def package_details(name: str, tlmgr: str | None = None) -> dict:
    """Return metadata + installed file paths for a single package.

    Keys: name, category, shortdesc, longdesc, revision, installed, files
    (list of absolute file paths).
    """
    tlmgr = tlmgr or find_tlmgr()
    info: dict = {"name": name, "installed": True, "files": []}
    if tlmgr:
        try:
            out = subprocess.run([tlmgr, "info", "--list", name],
                                 capture_output=True, text=True, timeout=60)
            if out.returncode == 0:
                _parse_tlmgr_info(out.stdout, info)
        except (OSError, subprocess.SubprocessError):
            pass
    return info


def _parse_tlmgr_info(text: str, info: dict) -> None:
    texmf = texmf_dist_dir()
    in_files = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("package:"):
            info["name"] = s.split(":", 1)[1].strip()
        elif s.startswith("category:"):
            info["category"] = s.split(":", 1)[1].strip()
        elif s.startswith("shortdesc:"):
            info["shortdesc"] = s.split(":", 1)[1].strip()
        elif s.startswith("longdesc:"):
            info["longdesc"] = s.split(":", 1)[1].strip()
        elif s.startswith("installed:"):
            info["installed"] = s.split(":", 1)[1].strip().lower() == "yes"
        elif s.startswith("revision:"):
            info["revision"] = s.split(":", 1)[1].strip()
        elif s in ("files:",) or s.lower() in (
                "run files:", "doc files:", "source files:", "bin files:"):
            in_files = True
        elif in_files and s:
            path = s
            if texmf and path.startswith("texmf-dist/"):
                path = texmf + "/" + path[len("texmf-dist/"):]
            info["files"].append(path)


def uninstall_package(name: str, tlmgr: str | None = None) -> str:
    """Remove an installed package via ``tlmgr remove``.

    Uses ``pkexec`` automatically when the install root is not writable by the
    current user (system-wide TeX Live). Raises ``RuntimeError`` on failure.
    """
    tlmgr = tlmgr or find_tlmgr()
    if not tlmgr:
        raise RuntimeError("tlmgr not found; cannot uninstall packages")
    root = os.path.dirname(os.path.dirname(os.path.dirname(tlmgr)))
    cmd = [tlmgr, "remove", "--force", name]
    if not os.access(root, os.W_OK) and shutil.which("pkexec"):
        cmd = ["pkexec"] + cmd
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip()
                           or "tlmgr remove failed")
    return result.stdout
