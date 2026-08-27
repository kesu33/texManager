# A.2 Package Dependency Resolver

## Functional Requirements
- On-demand or pre-compile scan of the active `.tex` file for `\usepackage{}` and `\RequirePackage{}` declarations.
- Cross-references detected package names against the local `tlmgr` package database (`tlmgr list --only-installed`).
- Produces a diff: packages required vs. packages installed.
- Missing packages are queued for one-click batch installation via `tlmgr install`, reusing the CTAN manager's install pathway from Module D.
- Gracefully handles package name aliases (e.g., `graphicx` bundled in `graphics` collection).

## UI Description
- Accessible via a **"Check Dependencies"** button next to the file picker in the new Compile & Watch tab (see Tab 4 below).
- Results shown as a simple two-column list: Required / Status (✓ Installed, ⚠ Missing).
- A footer button reads **"Install N Missing Packages"**, disabled if nothing is missing.
