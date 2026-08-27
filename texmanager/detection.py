"""Runtime detection of TeX Live installations on the host.

Detection is deliberately two-pronged:

1. ``PATH`` discovery finds whatever the shell would resolve (usually the
   upstream/TUG install that was prepended to ``PATH``).
2. Known-root globbing finds installs that are *not* first on ``PATH``
   (e.g. a distro/apt TeX Live living in ``/usr/bin``), and a run-probe
   distinguishes a real, functional install from a broken one whose
   symlink still exists but whose binary is gone.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

ENGINES = [
    "pdflatex", "xelatex", "lualatex", "xetex", "luatex",
    "ptex", "uptex", "context",
]
PROBE_ENGINES = ("pdflatex", "xelatex", "lualatex", "xetex", "luatex")
PROBE_TIMEOUT = 5
_YEAR_RE = re.compile(r"TeX Live (\d{4})")


@dataclass
class TexInstallation:
    root: str
    bin_dir: str
    year: int | None = None
    engines: list[str] = field(default_factory=list)
    has_tlmgr: bool = False
    functional: bool = False
    source: str = "unknown"  # "TUG" | "distro" | "unknown"
    raw_version: str = ""

    @property
    def label(self) -> str:
        name = f"TeX Live {self.year}" if self.year else "TeX (unknown version)"
        if not self.functional:
            return f"{name} — broken ({self.root})"
        return f"{name} — {self.root}"


def _candidate_bin_dirs() -> list[str]:
    dirs: list[str] = []

    # 1. What the shell would resolve via PATH.
    for engine in ("pdflatex", "xetex", "tlmgr", "kpsewhich"):
        path = shutil.which(engine)
        if path:
            dirs.append(os.path.dirname(path))

    # 2. Known install roots (upstream/TUG style layouts).
    roots = [
        Path("/usr/local/texlive"),
        Path("/opt/texlive"),
        Path.home() / "texlive",
    ]
    for root in roots:
        if not root.is_dir():
            continue
        for year_dir in root.iterdir():
            if not year_dir.is_dir():
                continue
            for arch in year_dir.glob("bin/*"):
                if arch.is_dir():
                    dirs.append(str(arch))

    # 3. Distro install (Debian/Ubuntu apt texlive symlinks live here).
    dirs.append("/usr/bin")
    return dirs


def _probe(bin_dir: str) -> TexInstallation | None:
    if bin_dir == "/usr/bin":
        root, source = "/usr", "distro"
    else:
        # TUG layout: <root>/bin/<arch>; the real TEXROOT is the grandparent.
        root, source = os.path.dirname(os.path.dirname(bin_dir)), "TUG"

    inst = TexInstallation(root=root, bin_dir=bin_dir, source=source)
    inst.has_tlmgr = os.path.exists(os.path.join(bin_dir, "tlmgr"))
    if inst.source == "unknown" and inst.has_tlmgr:
        inst.source = "TUG"
    inst.engines = [e for e in ENGINES
                    if os.path.exists(os.path.join(bin_dir, e))]

    probe = next((e for e in PROBE_ENGINES
                 if os.path.exists(os.path.join(bin_dir, e))), None)
    if probe is None:
        inst.functional = False
        return inst

    try:
        out = subprocess.run(
            [os.path.join(bin_dir, probe), "-version"],
            capture_output=True, text=True, timeout=PROBE_TIMEOUT,
        )
        inst.raw_version = (out.stdout or out.stderr).strip()
        match = _YEAR_RE.search(inst.raw_version)
        if match:
            inst.year = int(match.group(1))
        inst.functional = out.returncode == 0
    except (OSError, subprocess.SubprocessError):
        inst.functional = False
    return inst


def find_tex_installations() -> list[TexInstallation]:
    seen: set[str] = set()
    results: list[TexInstallation] = []
    for d in _candidate_bin_dirs():
        if d in seen:
            continue
        if not any(os.path.exists(os.path.join(d, e)) for e in ENGINES):
            continue
        seen.add(d)
        inst = _probe(d)
        if inst is not None:
            results.append(inst)
    return results


def detect() -> tuple[TexInstallation | None, list[TexInstallation], bool]:
    installs = find_tex_installations()
    primary = None
    if installs:
        functional = [i for i in installs if i.functional] or installs
        primary = max(functional,
                      key=lambda i: (i.year or 0, i.has_tlmgr))
    return primary, installs, len(installs) > 1
