# RUNBOOK

Exact working commands and problems solved. Updated continuously.

## Environment
- Dev laptop: see env_report.md. Python 3.13 approved (3.11 not installed).
- Project path contains spaces: always quote paths.

## Phase 0
- Created repo, .gitignore, CLAUDE.md, env_report.md, folder structure.

## Phase 1 - Lumo baseline (B1)
- Cloned https://github.com/mehedinaeem/Lumo.git into `baselines/lumo` (1.8 MB).
- **Pinned commit: `778ed055033ec3b0410349a82b9ea68e9546a4e0`** (branch HEAD, "Updated"). `scripts/setup.ps1` clones and checks out this commit.
- Code reviewed (Gate 1 summary given in chat). No binaries are committed in the Lumo repo (`piper.exe` is NOT included; README expects `piper\piper\piper.exe`).
