# B.3 Resume/Retry Logic

## Functional Requirements
- Downloads use HTTP range requests where supported; partial `install-tl-unx.tar.gz` downloads are resumed rather than restarted.
- On network failure mid-install, the app retries up to a configurable number of times (default 3) with exponential backoff before surfacing an error to the user.
- Install state (scheme, mirror, profile path) is cached to disk so a fully failed install can be resumed from the last completed step without re-collecting user input.

## UI Description
- Progress bar in the wizard gains a secondary status line: "Retrying (attempt 2 of 3)…" on transient failure.
- A **"Resume Previous Install"** option appears on next launch if a cached incomplete state is found.
