# Server-owned deployment permissions

Date: 2026-09-13

## Decision

Remote ownership and modes are controlled by server policy. HLSync must not copy
local ownership or modes to remote files, apply blanket chmod defaults, or clear
group-write or setgid bits. Create staging files beside their destinations so
server creation policy applies to both new uploads and replacements. Leave
existing directories' permissions untouched.

Replacement files retain their staging-file metadata. HLSync does not currently
copy old destination modes or ACLs to replacement files. Shared writable trees
therefore require suitable server creation policy: setgid controls group
inheritance but does not itself grant group write. An FTP umask or default ACL
must provide that permission. Concrete setup examples belong in README.

## Rationale

The deployment user and web process may share write access. Applying workstation
modes or blanket file and directory defaults could break that access. Server
policy defines the intended permissions for each remote tree, including staging
files that become live destinations.

## Intentionally excluded

- Automatically changing server ownership, FTP configuration, or ACLs.
- Treating setgid alone as a guarantee of group-write permission.
- Claiming arbitrary existing modes survive staging replacement.
- Broadening permissions across a profile to repair one writable tree.
