# Remote read progress

Date: 2026-09-13

## Decision

Show completed/discovered directory counts and the current path. Update only
on traversal events; do not animate idle time. The walker counts eligible child
directories after applying selection and exclusion boundaries. A directory is
complete after listing, artifact handling, and child classification finish.
The denominator grows as deeper work is discovered and includes the starting
directory. Both live and dry transfers use this same traversal accounting.

## Rationale

Counts describe observable work without a second traversal to obtain a fixed
total. Labeling the denominator as discovered avoids presenting a growing
estimate as a known total or an estimate of remaining time.

## Intentionally excluded

- Background animation threads or idle redraws.
- Entering excluded directories to count them.
- A preliminary recursive listing solely to calculate progress totals.
