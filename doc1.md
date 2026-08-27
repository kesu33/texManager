# SRS Addendum: TeXManager GNOME — Extended Feature Specifications

This addendum extends the original SRS with fully specified functional requirements and UI descriptions for the proposed additional features, organized by module.

---

## Module A Extensions — Inspection & Diagnostic Engine

### A.1 Log Parser / Error Triage

**Functional Requirements:**
- After any compile action (manual or via watch mode), the app parses the resulting `.log` file using regex-based extraction rules for common TeX/LaTeX error patterns:
  - `! LaTeX Error:` and `! Undefined control sequence` blocks
  - `Package <name> Error:` messages
  - `Overfull \hbox` / `Underfull \hbox` warnings (severity: low, collapsible)
  - Missing file errors (`! LaTeX Error: File 'X' not found`)
- Each parsed error is mapped to a human-readable explanation where possible (e.g., "Undefined control sequence" → "You used a command that isn't defined — check for typos or a missing `\usepackage`").
- Errors link back to the offending line number in the source file when available, with a "Jump to line" action if an editor integration is configured (see A.3/E extensions).
- Missing-file errors that match a known CTAN package are cross-referenced against Module A.2's resolver and offer a one-click install.

**UI Description:**
- New collapsible panel titled **"Compile Report"** appears below the Terminal Execution Logs expander in Tab 1.
- Uses `Adw.ExpanderRow` per error/warning category (Errors, Warnings, Overfull/Underfull boxes).
- Each row uses a colored icon (red = error, amber = warning) consistent with GNOME HIG status colors.
- A summary chip at the top reads e.g. "3 errors, 12 warnings" and is clickable to expand all.

---

### A.2 Package Dependency Resolver

**Functional Requirements:**
- On-demand or pre-compile scan of the active `.tex` file for `\usepackage{}` and `\RequirePackage{}` declarations.
- Cross-references detected package names against the local `tlmgr` package database (`tlmgr list --only-installed`).
- Produces a diff: packages required vs. packages installed.
- Missing packages are queued for one-click batch installation via `tlmgr install`, reusing the CTAN manager's install pathway from Module D.
- Gracefully handles package name aliases (e.g., `graphicx` bundled in `graphics` collection).

**UI Description:**
- Accessible via a **"Check Dependencies"** button next to the file picker in the new Compile & Watch tab (see Tab 4 below).
- Results shown as a simple two-column list: Required / Status (✓ Installed, ⚠ Missing).
- A footer button reads **"Install N Missing Packages"**, disabled if nothing is missing.

---

### A.3 Version Conflict Detector

**Functional Requirements:**
- Checks `$PATH` resolution order against all detected TeX installations (distro-managed and vanilla).
- If more than one `pdflatex`/`tex` binary exists on disk, determines which one `$PATH` currently resolves to and flags the shadowed installation(s).
- Suggests a remediation: either reorder `$PATH` in the shell rc file, or fully remove the shadowed installation via the existing Uninstallation Engine.

**UI Description:**
- Adds a new banner state to the Tab 1 Status Card: **"Conflict Detected"** (icon: `dialog-warning-symbolic`, orange).
- Clicking the banner opens an `Adw.MessageDialog` listing both installations with paths and versions, and two action buttons: "Reorder PATH" and "Remove Shadowed Install."

---

## Module B Extensions — Onboarding & Installation Manager

### B.1 Custom Scheme Picker

**Functional Requirements:**
- Replaces the binary Full/Minimal choice with a dropdown exposing all standard TeX Live schemes: `scheme-infraonly`, `scheme-basic`, `scheme-medium`, `scheme-full`, etc.
- Displays estimated download size per scheme (static lookup table, refreshed periodically from CTAN metadata).
- Selection is written directly into the generated `texlive.profile`.

**UI Description:**
- `Adw.ComboRow` in the Onboarding wizard, replacing the current two-button scheme choice.
- Subtitle text dynamically updates with estimated size, e.g. "scheme-medium — approx. 1.8 GB."

### B.2 Mirror Selection

**Functional Requirements:**
- Queries the CTAN mirror list (`https://mirror.ctan.org/mirrors.json` or equivalent) and offers "Auto (nearest)" as default.
- Auto mode uses a lightweight latency probe (parallel HEAD requests) to pick the fastest of a short candidate list before falling back to the CTAN redirector.
- User can manually override with a specific mirror URL.

**UI Description:**
- `Adw.ComboRow` labeled **"Download Mirror"** in the same wizard step as scheme selection, with a small refresh icon to re-run the latency probe.

### B.3 Resume/Retry Logic

**Functional Requirements:**
- Downloads use HTTP range requests where supported; partial `install-tl-unx.tar.gz` downloads are resumed rather than restarted.
- On network failure mid-install, the app retries up to a configurable number of times (default 3) with exponential backoff before surfacing an error to the user.
- Install state (scheme, mirror, profile path) is cached to disk so a fully failed install can be resumed from the last completed step without re-collecting user input.

**UI Description:**
- Progress bar in the wizard gains a secondary status line: "Retrying (attempt 2 of 3)…" on transient failure.
- A **"Resume Previous Install"** option appears on next launch if a cached incomplete state is found.

---

## Module C Extensions — Lifecycle Management Dashboard

### C.1 Rollback / Snapshot Support

**Functional Requirements:**
- Before any `tlmgr update` or distro upgrade action, the app records a lightweight snapshot: output of `tlmgr list --only-installed` with versions, plus a timestamp.
- Snapshots are stored locally (e.g., `~/.local/share/texmanager/snapshots/`) and pruned to the last 5 by default.
- Rollback re-invokes `tlmgr install --reinstall <pkg>@<version>` for each package that changed, where prior versions remain available in the TeX Live archive; otherwise warns that full rollback isn't possible and offers a diff-only view.

**UI Description:**
- New **"History"** expander in Tab 1 listing past snapshots with date/time and a "Restore" button per entry.
- Restore triggers a confirmation `Adw.MessageDialog` summarizing package-level changes before proceeding.

### C.2 Scheduled/Background Update Checks

**Functional Requirements:**
- Optional systemd user timer (`texmanager-update-check.timer`) installed on first opt-in, running a lightweight `tlmgr update --list` (or distro equivalent) on a user-configurable interval (default weekly).
- Results are written to a small state file; if updates are available, a desktop notification is issued via `Gio.Notification`.

**UI Description:**
- Toggle switch **"Check for updates automatically"** in a new Preferences dialog (`Adw.PreferencesWindow`), with an interval `Adw.ComboRow` (Daily/Weekly/Monthly).

---

## Module D Extensions — CTAN & Documentation Utilities

### D.1 Bulk Package Operations

**Functional Requirements:**
- Search results list gains checkboxes; selecting multiple packages enables a batch action bar.
- Batch install/remove is executed as a single `tlmgr` invocation with multiple package arguments where possible, falling back to sequential calls with aggregated progress reporting.

**UI Description:**
- `Gtk.ListView` rows gain leading checkboxes; a floating action bar appears at the bottom of Tab 2 reading "3 selected — Install / Remove."

### D.2 "Explain This Package" Panel

**Functional Requirements:**
- Selecting a single search result triggers `tlmgr info <package>` and parses the description, dependency list, and CTAN category.

**UI Description:**
- Slide-over side panel (`Adw.NavigationSplitView` secondary pane) showing package name, description, "Depends on" chips, and an Install button.

---

## Module E Extensions — Maintenance & Auxiliary Tools

### E.1 Project Templates

**Functional Requirements:**
- Ships bundled templates: Article, Beamer presentation, Thesis/Report, CV/Resume.
- "New Project" scaffolds the chosen template into a user-selected empty folder, including a `.gitignore` tuned for LaTeX build artifacts.

**UI Description:**
- New **"New Project"** button in the HeaderBar opens an `Adw.Dialog` with a grid of template cards (icon + name + short description) and a folder picker.

### E.2 Bibliography Tool Integration

**Functional Requirements:**
- Detects presence of `biber` and `bibtex` binaries alongside the main diagnostic scan.
- Provides a simple `.bib` file validator: checks for duplicate citation keys, malformed entries, and missing required fields per entry type (e.g., `@article` requires `journal`).

**UI Description:**
- Validator accessible from the Utilities tab via a file picker; results shown as a flat list of issues with line references, similar in style to the Compile Report panel (A.1).

### E.3 Symlink/PATH Doctor

**Functional Requirements:**
- Extends the existing Path Repair Action to also scan `/usr/local/bin` and other common bin directories for broken symlinks pointing to nonexistent TeX binaries (common after a vanilla TeX Live version bump).
- Offers to repair (re-point to current install) or remove dangling symlinks.

**UI Description:**
- Adds a row to the existing Path Repair result dialog: "2 broken symlinks found — Repair All."

---

## New Tab 4: Compile & Watch

**Functional Requirements:**
- File picker for a root `.tex` file.
- "Watch" toggle runs `latexmk -pvc` (or equivalent engine-specific watch command) as a background subprocess, streaming stdout/stderr into a live log view.
- Integrates with the Log Parser (A.1) to surface a live-updating Compile Report as the watched file is edited and recompiled.
- "Open PDF" button launches the output in the system default PDF viewer, and re-focuses/reloads it automatically on successive compiles where the viewer supports it (e.g., Evince with SyncTeX).
- Dependency Check button (A.2) available inline before starting watch mode.

**UI Description:**

```text
Tab 4: Compile & Watch
  ├── File Picker Row (selected .tex file, "Browse…")
  ├── Engine Selector (pdflatex / xelatex / lualatex)
  ├── Action Row: [ Check Dependencies ] [ Start Watching ] [ Open PDF ]
  ├── Live Log View (scrolling, monospace, auto-scroll toggle)
  └── Compile Report Panel (collapsed by default, shared component with A.1)
```

- Status indicator in the tab's title area shows a small colored dot: green (compiling clean), red (last compile failed), gray (idle).

---

## Cross-Cutting Extensions

### X.1 Flatpak / Sandboxing Considerations

**Functional Requirements:**
- If distributed as a Flatpak, `pkexec` calls must be replaced or supplemented with Polkit actions invoked through the `org.freedesktop.Flatpak.Portal` or a dedicated system helper service, since sandboxed apps cannot directly `pkexec` host binaries.
- Document a required manifest permission set: `--system-talk-name=org.freedesktop.PolicyKit1`, filesystem access scoped to `~/.local/share/fonts`, `/usr/local/texlive` (host passthrough where feasible), and network access for CTAN/mirror queries.
- A native (non-Flatpak) `.deb`/`.rpm`/AUR distribution path should be documented as the recommended default given the depth of root-level package manager interaction this app performs.

**UI Description:**
- No direct UI change; documented in installation instructions and surfaced as a one-time info banner if the app detects it's running inside a sandbox (`flatpak-spawn` check) with degraded capabilities.

### X.2 Consistent Undo/Confirmation Pattern

**Functional Requirements:**
- The `Adw.MessageDialog` confirmation pattern currently used only for uninstallation is extended to:
  - Aux-file cleaner (before deleting matched build artifacts, list affected file count and total size)
  - Font sync (before copying/overwriting font files)
  - Rollback restore (C.1)
  - Symlink repair (E.3)
- Each confirmation dialog follows a shared component template: title, summary line, expandable "Details" list of affected items, Cancel/Confirm buttons with the destructive action styled via `destructive-action` CSS class.

**UI Description:**
- No new screens; standardizes an existing pattern across five previously inconsistent action points.

---

## Summary Table

| Module | New Feature | Complexity | Priority |
|---|---|---|---|
| A | Log Parser / Error Triage | Medium | High |
| A | Package Dependency Resolver | Medium | High |
| A | Version Conflict Detector | Low | Medium |
| B | Custom Scheme Picker | Low | Medium |
| B | Mirror Selection | Medium | Low |
| B | Resume/Retry Logic | Medium | Medium |
| C | Rollback/Snapshot Support | High | Medium |
| C | Scheduled Update Checks | Low | Low |
| D | Bulk Package Operations | Low | Medium |
| D | Explain This Package Panel | Low | Low |
| E | Project Templates | Low | High |
| E | Bibliography Tool Integration | Medium | Medium |
| E | Symlink/PATH Doctor | Low | Low |
| New | Tab 4: Compile & Watch | High | High |
| Cross | Flatpak Considerations | Medium | Medium |
| Cross | Undo/Confirmation Consistency | Low | High |
