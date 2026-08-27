# X.1 Flatpak / Sandboxing Considerations

## Functional Requirements
- If distributed as a Flatpak, `pkexec` calls must be replaced or supplemented with Polkit actions invoked through the `org.freedesktop.Flatpak.Portal` or a dedicated system helper service, since sandboxed apps cannot directly `pkexec` host binaries.
- Document a required manifest permission set: `--system-talk-name=org.freedesktop.PolicyKit1`, filesystem access scoped to `~/.local/share/fonts`, `/usr/local/texlive` (host passthrough where feasible), and network access for CTAN/mirror queries.
- A native (non-Flatpak) `.deb`/`.rpm`/AUR distribution path should be documented as the recommended default given the depth of root-level package manager interaction this app performs.

## UI Description
- No direct UI change; documented in installation instructions and surfaced as a one-time info banner if the app detects it's running inside a sandbox (`flatpak-spawn` check) with degraded capabilities.
