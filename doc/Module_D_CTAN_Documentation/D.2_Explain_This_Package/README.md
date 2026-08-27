# D.2 "Explain This Package" Panel

## Functional Requirements
- Selecting a single search result triggers `tlmgr info <package>` and parses the description, dependency list, and CTAN category.

## UI Description
- Slide-over side panel (`Adw.NavigationSplitView` secondary pane) showing package name, description, "Depends on" chips, and an Install button.
