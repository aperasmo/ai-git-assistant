# Installer Signing Decision

## Phase B Decision

Windows installer signing is deferred for the current Phase B release.

The Phase A/B installer is functional and verified, but paid code-signing is not required yet for the current distribution model. The next public releases should instead include:

- GitHub release notes with the exact installer filename.
- A SHA256 checksum for the uploaded installer.
- A short note that early builds may be unsigned.

## When To Revisit

Revisit code signing when one of these becomes true:

- The app is distributed beyond portfolio/early-adopter channels.
- Users report SmartScreen warnings as a meaningful adoption blocker.
- The project needs organization or enterprise trust signals.
- A release process exists that can protect a signing certificate safely.

## Preferred Path Later

Start with a standard code-signing certificate unless immediate SmartScreen reputation is critical. EV signing can be considered later, but it adds cost and operational overhead.
