# One-click Windows updates

## Install once into an existing ZIP installation

1. Start Docker Desktop.
2. On GitHub, open **Update My Intelligence.cmd** and choose **Download raw file**. Sign into GitHub if the repository requires it.
3. Save that one file **inside your existing KUMAIL-main folder**, beside **Start My Intelligence.cmd** and your saved `.env`. Do not run it from Downloads or create another app folder.
4. Double-click **Update My Intelligence.cmd**. The first run installs Git for Windows through Windows Package Manager if Git is absent. Windows may ask for installation permission. If Windows Package Manager is unavailable, install Git for Windows once from its official site and retry.
5. Complete GitHub's browser sign-in if prompted. Git Credential Manager handles the Git credentials; do not put tokens in the application `.env` or remote URL.

The CMD is self-contained: it includes the PowerShell implementation, so installing it does not require a second script download. The standalone source in `scripts/update-windows.ps1` is kept identical for review and testing. The batch header stays stable so the file can update itself safely.

## Normal use

Double-click **Update My Intelligence.cmd** when you want the latest published code from the repository's main branch. The updater fetches code; it never commits or pushes your local work. It checks readiness and opens the browser when finished.

- `.env`, provider credentials, saved preferences and the existing named Docker data volume stay in place.
- Frontend changes build the dashboard image. Backend changes build one shared backend image, used by all backend processes. Changes to shared backend code therefore restart the backend services that use that image.
- Documentation and host-only script changes skip image builds. Compose may still start a stopped service or recreate containers whose environment configuration changed.
- Changed environment variables are applied by `docker compose up -d --no-build`; changing a key does not require downloading source or rebuilding an image.
- Builds finish before the running containers are updated. Build failure leaves existing containers running. Startup/readiness failure is reported; it does not trigger a destructive automatic rollback.
- The last successfully deployed commit is recorded under `.git`. A failed build or readiness check leaves it unchanged so the next click retries pending work.

The updater never runs `docker compose down -v`, deletes a data volume, forces a branch reset, stashes local edits or runs Git clean. The app remains in the same directory, preserving Compose's project name and volume mapping. Keep the folder name unchanged after installation. Regular encrypted backups are still required; an updater is not a backup system.

## ZIP migration protections

A ZIP has no Git history. The first run fetches repository metadata and compares the installed files against up to 200 actual main-branch releases using Git blob hashes. It normalises ordinary Windows line endings for this comparison. A matching release becomes the local baseline without resetting the source tree.

An edited source file or unknown installation stops migration. Identical files from a newer release that were already copied into the folder can be adopted; copies are retained under `.git/mi-bootstrap-backup`. A conflicting untracked file stops migration before those files are replaced. Symlink/reparse source paths require manual review.

After migration, tracked edits, staged changes, non-main branches, diverged history and local-ahead commits stop updates. An untracked file that Git would overwrite also stops its fast-forward. Application settings stored through the dashboard or `.env` are separate from tracked code and do not block normal updates.

If it stops, read the message and keep the existing folder. Do not delete `.env`, remove volumes or use a force reset. Review the differences before retrying. Manually modifying `config/publisher-feeds.json` counts as a source edit; publisher settings entered through the app are stored in the data volume instead.

## Validation and limits

Real-Git PowerShell tests cover the migration, preserved private files, conflicting files, Windows line-ending comparison, clean repeat updates, selective image planning, failed-build retries, last-deployed state and the full entry point with controlled Docker/GitHub substitutes. PowerShell was downloaded from the official release and checked against its published SHA-256. Tests ran with PowerShell on Linux, not on an actual Windows desktop. Windows installation prompts, Git Credential Manager browser interaction and the CMD host require validation on the user's PC.

Run the updater tests with PowerShell:

```powershell
pwsh -NoProfile -File scripts/tests/test-update.ps1
```

For source-only invocation from an existing checkout:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/update-windows.ps1 -RootDirectory .
```

Releases that change data formats still need a deliberate compatible migration and recovery plan; Git fast-forwards alone do not supply database rollback.
