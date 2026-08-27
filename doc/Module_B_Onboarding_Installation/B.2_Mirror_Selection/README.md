# B.2 Mirror Selection

## Functional Requirements
- Queries the CTAN mirror list (`https://mirror.ctan.org/mirrors.json` or equivalent) and offers "Auto (nearest)" as default.
- Auto mode uses a lightweight latency probe (parallel HEAD requests) to pick the fastest of a short candidate list before falling back to the CTAN redirector.
- User can manually override with a specific mirror URL.

## UI Description
- `Adw.ComboRow` labeled **"Download Mirror"** in the same wizard step as scheme selection, with a small refresh icon to re-run the latency probe.
