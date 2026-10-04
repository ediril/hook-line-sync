# Independent presence and status columns

Date: 2026-09-30

## Decision

The presence column describes actual presence only: `l` for local only, `r`
for remote only, and blank when both copies exist. Keep its width fixed even
when blank. Determine presence from the observed local and remote entry kinds,
independently of transfer authority, planned action, or exclusion source.

The action/status column uses `x` for a local exclusion
and `#` for a remote exclusion. The user requested that these remain visually
distinct. Remove `!`, whose warning connotation obscured the meaning. Single-side
listings use the same exclusion symbols without claiming presence on the other
side. Directory rows keep blank status columns and display `▸` whenever their
contents were not inspected, including exclusion boundaries.

Locally excluded files still count as absent for push authority and can have
their remote copies deleted. Preserve observed local kind in their comparison
entries so display does not confuse this policy with physical absence. Action
continues to drive transfer execution; transfer and exclusion policies do not
change.

This supersedes the side/exclusion notation and column-zero ancestor headings
in the August 30 diff-presentation decision. Tree depth still adds indentation
before the fixed status columns.
