# New Tab 4: Compile & Watch

## Functional Requirements
- File picker for a root `.tex` file.
- "Watch" toggle runs `latexmk -pvc` (or equivalent engine-specific watch command) as a background subprocess, streaming stdout/stderr into a live log view.
- Integrates with the Log Parser (A.1) to surface a live-updating Compile Report as the watched file is edited and recompiled.
- "Open PDF" button launches the output in the system default PDF viewer, and re-focuses/reloads it automatically on successive compiles where the viewer supports it (e.g., Evince with SyncTeX).
- Dependency Check button (A.2) available inline before starting watch mode.

## UI Description

```text
Tab 4: Compile & Watch
  ├── File Picker Row (selected .tex file, "Browse…")
  ├── Engine Selector (pdflatex / xelatex / lualatex)
  ├── Action Row: [ Check Dependencies ] [ Start Watching ] [ Open PDF ]
  ├── Live Log View (scrolling, monospace, auto-scroll toggle)
  └── Compile Report Panel (collapsed by default, shared component with A.1)
```

- Status indicator in the tab's title area shows a small colored dot: green (compiling clean), red (last compile failed), gray (idle).
