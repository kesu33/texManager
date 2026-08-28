"""Backend helpers that query TeX Live for installed packages and metadata.

All functions are GUI-agnostic and safe to call from a worker thread: they
never touch GTK and only shell out to ``tlmgr``, read local TLPDB files, or
fetch remote metadata over HTTPS.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
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


def _escalate(cmd: list[str], tlmgr: str) -> list[str]:
    """Prefix ``cmd`` with an elevation tool when the install isn't writable.

    Prefers ``pkexec`` (the graphical standard for GUI apps); falls back to
    ``sudo``. If neither is available the command is returned unchanged and will
    fail with a clear permission error from ``tlmgr``.
    """
    root = os.path.dirname(os.path.dirname(os.path.dirname(tlmgr)))
    if os.access(root, os.W_OK):
        return cmd
    for elev in ("pkexec", "sudo"):
        if shutil.which(elev):
            return [elev] + cmd
    return cmd


def uninstall_package(name: str, tlmgr: str | None = None) -> str:
    """Remove an installed package via ``tlmgr remove``.

    Elevates with ``pkexec``/``sudo`` when the install root is not writable by
    the current user (system-wide TeX Live). Raises ``RuntimeError`` on failure.
    """
    tlmgr = tlmgr or find_tlmgr()
    if not tlmgr:
        raise RuntimeError("tlmgr not found; cannot uninstall packages")
    cmd = _escalate([tlmgr, "remove", "--force", name], tlmgr)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip()
                           or "tlmgr remove failed")
    return result.stdout


def list_updatable_packages(tlmgr: str | None = None) -> list[str]:
    """Return the sorted names of installed packages that have updates.

    Parses ``tlmgr update --list`` (a dry run that contacts the repository but
    does not change anything). Lines of the form ``update: <pkg> ...`` are the
    packages with a newer version available.
    """
    tlmgr = tlmgr or find_tlmgr()
    if not tlmgr:
        return []
    try:
        out = subprocess.run([tlmgr, "update", "--list"],
                             capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError):
        return []
    names: list[str] = []
    for line in out.stdout.splitlines():
        s = line.strip()
        if s.startswith("update:"):
            rest = s[len("update:"):].strip()
            if rest:
                names.append(rest.split()[0])
    return sorted(names)


def update_package(name: str, tlmgr: str | None = None) -> str:
    """Update a single installed package via ``tlmgr update``.

    Elevates with ``pkexec``/``sudo`` when the install root is not writable by
    the current user (system-wide TeX Live). Raises ``RuntimeError`` on failure.
    """
    tlmgr = tlmgr or find_tlmgr()
    if not tlmgr:
        raise RuntimeError("tlmgr not found; cannot update packages")
    cmd = _escalate([tlmgr, "update", name], tlmgr)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip()
                           or "tlmgr update failed")
    return result.stdout


def fetch_available_texlive_years(timeout: int = 15) -> list[int]:
    """Return a sorted list of available TeX Live years from TUG.

    Parses the TUG homepage for the current release year and supplements
    with known recent years from the historic archive. Falls back to a
    short recent list when the network request fails.
    """
    years: list[int] = []
    url = "https://www.tug.org/texlive/"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TeXManager/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        for m in re.finditer(r"TeX Live (\d{4}) is available", text):
            years.append(int(m.group(1)))
        for m in re.finditer(r"texlive-(\d{4})\.html", text):
            years.append(int(m.group(1)))
    except (OSError, ValueError):
        pass
    if years:
        years = sorted(set(years))
    else:
        from datetime import date
        y = date.today().year
        years = [y - 3, y - 2, y - 1, y]
    if len(years) == 1:
        years.extend([years[0] - 1, years[0] - 2, years[0] - 3])
    elif len(years) == 2:
        years.extend([years[0] - 1, years[0] - 2])
    elif len(years) == 3:
        years.append(years[0] - 1)
    years = sorted(set(years))
    return years


def install_texlive(year: int, scheme: str, install_dir: str | None = None,
                    progress_callback=None) -> str:
    """Download and run the TeX Live network installer.

    Streams installer output through *progress_callback* when provided.
    Returns the complete installer output on success.
    Raises ``RuntimeError`` on failure.
    """
    if install_dir is None:
        install_dir = f"/usr/local/texlive/{year}"

    url = "https://mirror.ctan.org/systems/texlive/tlnet/install-tl-unx.tar.gz"

    with tempfile.TemporaryDirectory(prefix="texlive-installer-") as tmpdir:
        tarball = os.path.join(tmpdir, "install-tl-unx.tar.gz")

        req = urllib.request.Request(url, headers={"User-Agent": "TeXManager/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            with open(tarball, "wb") as f:
                f.write(resp.read())

        with tarfile.open(tarball, "r:gz") as tf:
            tf.extractall(tmpdir)

        install_script = None
        for root, dirs, files in os.walk(tmpdir):
            if "install-tl" in files:
                install_script = os.path.join(root, "install-tl")
                break

        if not install_script:
            raise RuntimeError("install-tl not found in downloaded archive")

        os.chmod(install_script, 0o755)

        cmd = [install_script, "-scheme", scheme, "-no-interaction",
               "-texdir", install_dir]

        if os.geteuid() != 0:
            parent = os.path.dirname(install_dir)
            needs_elev = False
            if not os.path.exists(install_dir):
                if not os.access(parent, os.W_OK):
                    needs_elev = True
            else:
                if not os.access(install_dir, os.W_OK):
                    needs_elev = True
            if needs_elev:
                for elev in ("pkexec", "sudo"):
                    if shutil.which(elev):
                        cmd = [elev] + cmd
                        break

        buf: list[str] = []
        cwd = os.path.dirname(install_script)
        proc = subprocess.Popen(
            cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip()
            buf.append(line)
            if progress_callback is not None:
                progress_callback(line)
        proc.wait()
        if proc.returncode != 0:
            tail = "\n".join(buf[-20:]) if buf else "install-tl failed"
            raise RuntimeError(tail)
        return "\n".join(buf)
