# Upgrade strategy

There are two independent upgrade types.

## 1. Updating this custom repository

Changes to our deployment scripts or customizations are normal Git commits. On production:

```bash
cd /opt/booklore-reader
./scripts/update.sh
```

The update process leaves `/srv/booklore-reader` untouched and creates a database dump before rebuilding when MariaDB is already running.

## 2. Updating upstream BookLore

The upstream release is pinned in:

```text
config/upstream.env
```

Current format:

```bash
BOOKLORE_UPSTREAM_REPO=https://github.com/booklore-app/booklore.git
BOOKLORE_UPSTREAM_REF=v2.3.1
```

Do **not** point production directly at `latest` or an unpinned moving branch. Upgrade intentionally:

```bash
./scripts/update-upstream.sh vNEW_VERSION
./scripts/deploy.sh
```

Then test:

- login/setup
- library browsing
- EPUB opening and normal progress
- select text -> Read Aloud
- TTS queue crossing several chunks
- pause/resume/stop controls
- Reader settings persistence
- Server mode
- Browser Local mode
- Paste text to EPUB -> direct appearance in selected library
- BookDrop remains independent and functional

If all tests pass:

```bash
git add config/upstream.env customizations/
git commit -m "Upgrade BookLore upstream to vNEW_VERSION"
git push
```

## Why upgrades fail loudly

`customizations/apply-customizations.py` operates on a small number of known upstream source anchors. If BookLore changes those files materially, the script raises an `Upstream changed:` error.

That is preferable to a partially applied patch. When this happens:

1. Inspect the referenced upstream file at the new release.
2. Compare it to the transformation in `apply-customizations.py`.
3. Update the anchor/replacement while preserving the intended behavior.
4. Run `./scripts/deploy.sh` again.
5. Test the feature before committing the new upstream pin.

## Rollback

Because state is outside the repository, application rollback is normally:

```bash
git log --oneline
git checkout <known-good-commit>
./scripts/deploy.sh
```

If an upstream/database migration made incompatible database changes, restore the matching SQL dump from `/srv/booklore-reader/backups`. Keep multiple backups and use Linode snapshots/backups before major upgrades.

## Dependency upgrades

The custom frontend currently adds:

- `jszip` for Paste-to-EPUB.
- `piper-tts-web` for browser-local TTS.

`prepare-source.sh` regenerates the frontend package lock against the pinned upstream source during each build. If changing versions, update both `customizations/apply-customizations.py` and `scripts/prepare-source.sh` where applicable.
