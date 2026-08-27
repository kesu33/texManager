# A.3 Version Conflict Detector

## Functional Requirements
- Checks `$PATH` resolution order against all detected TeX installations (distro-managed and vanilla).
- If more than one `pdflatex`/`tex` binary exists on disk, determines which one `$PATH` currently resolves to and flags the shadowed installation(s).
- Suggests a remediation: either reorder `$PATH` in the shell rc file, or fully remove the shadowed installation via the existing Uninstallation Engine.

## UI Description
- Adds a new banner state to the Tab 1 Status Card: **"Conflict Detected"** (icon: `dialog-warning-symbolic`, orange).
- Clicking the banner opens an `Adw.MessageDialog` listing both installations with paths and versions, and two action buttons: "Reorder PATH" and "Remove Shadowed Install."
