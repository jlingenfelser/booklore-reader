# Changelog

## 1.1.0 — 2026-09-12

Production-hardening pass based on the first fresh Linode deployment.

- Added mobile **Read from here -> Tap text…** TTS start-position workflow.
- Made the selection-popup customization tolerant of upstream whitespace differences.
- Added Angular low-memory build settings (`NG_BUILD_MAX_WORKERS=1`, 1536 MB Node heap).
- Replaced Gradle parallel build with `--max-workers=1`.
- Changed production deployment to stop the live stack during builds, build services separately, and attempt recovery on failure.
- Added default 2 GB swapfile creation to Linode provisioners.
- Removed `main` as a hard-coded deployment assumption; current/default branch is used unless overridden.
- GitHub Actions now supports pushes to `main` and `master`.
- Added Linode Cloud Firewall/ACME troubleshooting.
- Added safe library-folder creation and `/books` permission-repair helpers.
- Added operations runbook covering uploads, permissions, PDF compression, swap/OOM recovery, logs, backups, and mobile TTS.
