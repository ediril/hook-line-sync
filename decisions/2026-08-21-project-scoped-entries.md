# Configured entries represent deployment profiles

Date: 2026-08-21

## Decision

Each named entry represents one deployment profile, not one server. It owns
the protocol and endpoint, credential environment-variable names, required
absolute remote root, and optional local root. Multiple profiles may use the
same host while targeting different projects or remote roots.

Removing a profile deletes only its local configuration. Credential values are
read from the named environment variables and are never stored in the profile.

## Rationale

The meaningful safety boundary is the complete local-to-remote deployment
target. Server identity alone cannot distinguish projects hosted by the same
service.

## Intentionally excluded

- Deduplicating profiles by host or sharing a mutable server record.
- Storing usernames, passwords, or other credential values.
- Connecting to or deleting remote content when a profile is removed.
