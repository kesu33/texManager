# B.1 Custom Scheme Picker

## Functional Requirements
- Replaces the binary Full/Minimal choice with a dropdown exposing all standard TeX Live schemes: `scheme-infraonly`, `scheme-basic`, `scheme-medium`, `scheme-full`, etc.
- Displays estimated download size per scheme (static lookup table, refreshed periodically from CTAN metadata).
- Selection is written directly into the generated `texlive.profile`.

## UI Description
- `Adw.ComboRow` in the Onboarding wizard, replacing the current two-button scheme choice.
- Subtitle text dynamically updates with estimated size, e.g. "scheme-medium — approx. 1.8 GB."
