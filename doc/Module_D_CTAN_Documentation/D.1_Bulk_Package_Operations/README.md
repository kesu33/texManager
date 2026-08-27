# D.1 Bulk Package Operations

## Functional Requirements
- Search results list gains checkboxes; selecting multiple packages enables a batch action bar.
- Batch install/remove is executed as a single `tlmgr` invocation with multiple package arguments where possible, falling back to sequential calls with aggregated progress reporting.

## UI Description
- `Gtk.ListView` rows gain leading checkboxes; a floating action bar appears at the bottom of Tab 2 reading "3 selected — Install / Remove."
