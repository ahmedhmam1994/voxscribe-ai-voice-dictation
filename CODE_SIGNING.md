# Code signing policy

Free code signing provided by [SignPath.io](https://about.signpath.io), certificate by [SignPath Foundation](https://signpath.org)

## Repository

The official repository is [ahmedhmam1994/voxscribe-ai-voice-dictation](https://github.com/ahmedhmam1994/voxscribe-ai-voice-dictation). Only releases built from this repository's `main` branch are signed.

## What gets signed

The Windows installer (`VoxScribe-Setup.exe`) and the packaged application executable (`VoxScribe.exe`) it contains, produced by this repository's release build workflow (PyInstaller + Inno Setup). Signing happens exclusively inside that CI workflow, never a manual local build on a contributor's own machine.

## Team

VoxScribe is a solo-maintained project. One person currently holds all three roles below.

- **Committers**: people trusted to modify the source code in this repository's version control system without additional review. Currently: [ahmedhmam1994](https://github.com/ahmedhmam1994).
- **Reviewers**: each change proposed by someone who is not a committer must be reviewed by a team member before merging. Currently: [ahmedhmam1994](https://github.com/ahmedhmam1994).
- **Approvers**: each signing request must be approved by a team member trusted by the entire team to decide if a given release can be code signed. Currently: [ahmedhmam1994](https://github.com/ahmedhmam1994).

## Privacy

This program will not transfer any information to other networked systems unless specifically requested by the user. See VoxScribe's full [privacy policy](https://getvoxscribe.vercel.app/privacy.html) for exactly what the app does and does not send over the network.
