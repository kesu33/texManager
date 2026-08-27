# E.1 Project Templates

## Functional Requirements
- Ships bundled templates: Article, Beamer presentation, Thesis/Report, CV/Resume.
- "New Project" scaffolds the chosen template into a user-selected empty folder, including a `.gitignore` tuned for LaTeX build artifacts.

## UI Description
- New **"New Project"** button in the HeaderBar opens an `Adw.Dialog` with a grid of template cards (icon + name + short description) and a folder picker.
