# A.1 Log Parser / Error Triage

## Functional Requirements
- After any compile action (manual or via watch mode), the app parses the resulting `.log` file using regex-based extraction rules for common TeX/LaTeX error patterns:
  - `! LaTeX Error:` and `! Undefined control sequence` blocks
  - `Package <name> Error:` messages
  - `Overfull \hbox` / `Underfull \hbox` warnings (severity: low, collapsible)
  - Missing file errors (`! LaTeX Error: File 'X' not found`)
- Each parsed error is mapped to a human-readable explanation where possible (e.g., "Undefined control sequence" → "You used a command that isn't defined — check for typos or a missing `\usepackage`").
- Errors link back to the offending line number in the source file when available, with a "Jump to line" action if an editor integration is configured (see A.3/E extensions).
- Missing-file errors that match a known CTAN package are cross-referenced against Module A.2's resolver and offer a one-click install.

## UI Description
- New collapsible panel titled **"Compile Report"** appears below the Terminal Execution Logs expander in Tab 1.
- Uses `Adw.ExpanderRow` per error/warning category (Errors, Warnings, Overfull/Underfull boxes).
- Each row uses a colored icon (red = error, amber = warning) consistent with GNOME HIG status colors.
- A summary chip at the top reads e.g. "3 errors, 12 warnings" and is clickable to expand all.
