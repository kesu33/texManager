# C.2 Scheduled/Background Update Checks

## Functional Requirements
- Optional systemd user timer (`texmanager-update-check.timer`) installed on first opt-in, running a lightweight `tlmgr update --list` (or distro equivalent) on a user-configurable interval (default weekly).
- Results are written to a small state file; if updates are available, a desktop notification is issued via `Gio.Notification`.

## UI Description
- Toggle switch **"Check for updates automatically"** in a new Preferences dialog (`Adw.PreferencesWindow`), with an interval `Adw.ComboRow` (Daily/Weekly/Monthly).
