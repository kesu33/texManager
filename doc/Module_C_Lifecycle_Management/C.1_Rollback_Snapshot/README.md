# C.1 Rollback / Snapshot Support

## Functional Requirements
- Before any `tlmgr update` or distro upgrade action, the app records a lightweight snapshot: output of `tlmgr list --only-installed` with versions, plus a timestamp.
- Snapshots are stored locally (e.g., `~/.local/share/texmanager/snapshots/`) and pruned to the last 5 by default.
- Rollback re-invokes `tlmgr install --reinstall <pkg>@<version>` for each package that changed, where prior versions remain available in the TeX Live archive; otherwise warns that full rollback isn't possible and offers a diff-only view.

## UI Description
- New **"History"** expander in Tab 1 listing past snapshots with date/time and a "Restore" button per entry.
- Restore triggers a confirmation `Adw.MessageDialog` summarizing package-level changes before proceeding.
