# TeXManager — UI (first pass)

A GNOME app (GTK4 + libadwaita) for managing TeX Live, built **UI-first** from
`doc.md`. The entire interface is constructed in **Python/PyGObject** (no
Blueprint / blueprint-compiler dependency), with backend logic stubbed via
`TODO`/`on_*` handlers so the UI can be iterated before wiring `tlmgr` and
system calls.

## Layout

```
src/texmanager/
  application.py    Adw.Application + actions (preferences/about/new-project/onboarding)
  window.py         MainWindow: ViewStack (Overview, Packages, Compile & Watch, Utilities)
  dialogs.py        Preferences / NewProject / DependencyCheck / Onboarding + confirm factory (X.2)
  models.py         GObject models for list factories (PackageItem, TemplateItem)
main.py             Dev entry point: runs the app
meson.build, data/  Build + .desktop + launcher
```

## Features covered (UI)

| Doc section | UI |
|---|---|
| A.1 | Compile Report panel in Overview (errors/warnings/box expanders, summary chip) |
| A.2 | "Check Dependencies" button (Tab 4) -> DependencyCheckDialog |
| A.3 | Conflict banner in Overview -> resolve handler |
| B.1–B.3 | Onboarding window: scheme ComboRow, mirror ComboRow + refresh, progress/retry |
| C.1 | History expander in Overview |
| C.2 | Preferences: auto-update switch + interval ComboRow |
| D.1–D.2 | Packages tab: checkboxes + bulk action bar; NavigationSplitView explain panel |
| E.1 | New Project dialog with template grid |
| E.2/E.3 | Utilities tab: .bib validator + symlink/PATH doctor buttons |
| New Tab 4 | Compile & Watch: file picker, engine ComboRow, watch/PDF actions, live log, status dot |
| X.2 | Shared `show_confirm()` destructive-action dialog factory |

## Build & run

Requires: `gtk4`, `libadwaita-1` (>=1.4), Python 3 + PyGObject.

Dev run (no install):

```sh
python3 main.py
```

Installed build:

```sh
meson setup build
meson compile -C build
meson install -C build
texmanager
```

## Next steps (backend)

Wire the `on_*` handlers in `window.py`/`dialogs.py` to `tlmgr`, `latexmk`,
`biber`/`bibtex`, systemd timers, and Polkit/Flatpak portals (X.1).
