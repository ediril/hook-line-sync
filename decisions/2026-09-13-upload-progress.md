# Upload progress

Date: 2026-09-13

## Decision

Derive upload totals from the selected comparison plan and local metadata.
Report bytes through the transport's post-send callback, and installed files
through the executor's successful completion events. Bytes sent are not proof
of installation: size and timestamp verification and final rename must succeed
before the installed-file count advances.

Refresh a single terminal line at most ten times per second during byte
transfers. Clear it around operation outcomes and finish it on normal or
exceptional exit. Redirected and dumb-terminal streams retain plain logs.
Dry runs show planned totals without emitting byte-transfer events.

## Rationale

The distinction between bytes sent and files installed gives useful feedback
during large uploads without misrepresenting unverified files as complete.
The executor retains authority over completion; the display observes its
events and does not influence transfer or pruning decisions.

## Intentionally excluded

- Counting failed or skipped files as installed.
- Treating a full byte bar as successful installation.
- Parallel transfer workers or resumable partial-file uploads.
- Predicting upload totals before scanning finishes.
