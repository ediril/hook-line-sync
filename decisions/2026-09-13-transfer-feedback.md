# Transfer feedback

Date: 2026-09-13

## Decision

The executor emits an operation event only after successful completion. It
emits each failure or skip when the outcome is known, through the same feedback
callback. The CLI flushes those events immediately and reports counts at the
end without repeating issues. Dry push uses the same executor and events for
planned operations, identified by the dry-run heading.

## Rationale

Printing a success-shaped marker before an attempt, while delaying its error
until the summary, makes failed uploads appear successful. Feedback must reflect
known outcomes and make failures visible while independent work continues.

## Intentionally excluded

- Treating a file failure as proof that its entire directory is unwritable.
- Changing pruning suppression or directory-failure propagation.
- Claiming a dry run verifies remote write permissions.

This supersedes pre-mutation event timing in the 2026-09-02 transfer decision.
