# E.3 Symlink/PATH Doctor

## Functional Requirements
- Extends the existing Path Repair Action to also scan `/usr/local/bin` and other common bin directories for broken symlinks pointing to nonexistent TeX binaries (common after a vanilla TeX Live version bump).
- Offers to repair (re-point to current install) or remove dangling symlinks.

## UI Description
- Adds a row to the existing Path Repair result dialog: "2 broken symlinks found — Repair All."
