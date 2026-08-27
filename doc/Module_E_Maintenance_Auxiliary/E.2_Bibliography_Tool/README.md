# E.2 Bibliography Tool Integration

## Functional Requirements
- Detects presence of `biber` and `bibtex` binaries alongside the main diagnostic scan.
- Provides a simple `.bib` file validator: checks for duplicate citation keys, malformed entries, and missing required fields per entry type (e.g., `@article` requires `journal`).

## UI Description
- Validator accessible from the Utilities tab via a file picker; results shown as a flat list of issues with line references, similar in style to the Compile Report panel (A.1).
