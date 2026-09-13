# Server-owned deployment permissions

Date: 2026-09-13

## Decision

Deployments through ftps-deploy must respect server-side group inheritance,
including setgid directories shared with www-data. HLSync must not copy local
ownership or modes to remote files, apply blanket chmod defaults, or clear group
write or setgid bits. Create staging files beside their final destinations so
server creation policy applies to both new uploads and replacements. Leave
existing directories' permissions untouched.

Writable app-data trees should retain group-writable files (0664) and
group-writable/setgid directories (02775) where the server configures them.
This requires server creation policy: setgid controls group inheritance but
does not itself grant group write. A suitable FTP umask or default ACL must
provide that permission. HLSync does not currently copy old destination modes
or ACLs to replacement files; replacements retain their staging-file metadata.

## Rationale

The deployment user and web process may share write access through www-data.
Applying local workstation modes or blanket 0644/0755 defaults could break that
access. Server policy defines the intended permissions for each remote tree.

## Intentionally excluded

- Automatically changing server ownership, FTP configuration, or ACLs.
- Treating setgid alone as a guarantee of group write permission.
- Claiming arbitrary existing file modes survive staging replacement.
- Broadening permissions across a whole profile to repair one writable tree.
