# X.2 Consistent Undo/Confirmation Pattern

## Functional Requirements
- The `Adw.MessageDialog` confirmation pattern currently used only for uninstallation is extended to:
  - Aux-file cleaner (before deleting matched build artifacts, list affected file count and total size)
  - Font sync (before copying/overwriting font files)
  - Rollback restore (C.1)
  - Symlink repair (E.3)
- Each confirmation dialog follows a shared component template: title, summary line, expandable "Details" list of affected items, Cancel/Confirm buttons with the destructive action styled via `destructive-action` CSS class.

## UI Description
- No new screens; standardizes an existing pattern across five previously inconsistent action points.
