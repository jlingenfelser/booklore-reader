# Local development / test deployment

The same repository can be tested on Pop!_OS or another Docker host before pushing to Linode.

## First local run

```bash
cp .env.example .env
```

Edit `.env` and set a writable local state directory, for example:

```bash
STATE_DIR=/home/YOUR_USER/booklore-reader-state
SITE_ADDRESS=:8080
```

If using a nonstandard HTTP port, also change the Compose gateway port mapping for local testing or use the production `:80` mapping on a machine where port 80 is available.

Generate safe DB passwords rather than leaving `CHANGE_ME`, or simply delete `.env` and run:

```bash
STATE_DIR="$HOME/booklore-reader-state" SITE_ADDRESS=:80 ./scripts/init-env.sh :80
```

Then:

```bash
./scripts/deploy.sh
```

## Rebuilding after customization changes

Edit only tracked source such as:

```text
customizations/apply-customizations.py
piper/
scripts/
docker-compose.yml
```

Then run:

```bash
./scripts/validate.sh
./scripts/deploy.sh
```

Do not edit `.build/booklore-src` as the source of truth. It is regenerated from the pinned upstream release.

## Inspect generated source

After `./scripts/prepare-source.sh`, the customized source is available at:

```text
.build/booklore-src
```

It is useful for inspecting the final Angular/Java code or diagnosing build errors, but any permanent fix should be made in `customizations/apply-customizations.py`.

## Mobile scrolling and keeping TTS awake

The reader customization updates Foliate's restoration anchor on manual scroll,
without waiting for its debounced progress event. Previously a resize or content
expansion could restore an old anchor, including before TTS had ever played.
This is a suspected cause of mobile snap-back; verify on the affected device.
TTS still intentionally follows the spoken chunk during playback. Stop playback
when browsing independently. An armed Read from here now consumes only a short,
stationary tap, leaving drag gestures available for scrolling.

TTS requests a screen wake lock during generation and holds it through playback,
buffering, and pauses until Stop, completion, error, or reader exit. Returning to
the visible tab requests the lock again. This needs HTTPS (or localhost) and a
browser with Screen Wake Lock support; system settings can deny the request.
It prevents automatic screen sleep, but does not guarantee playback after manually
locking the phone or switching apps.

Device checks after deployment:

- In scrolling mode, drag repeatedly immediately after opening a book, after a
  chapter jump, and after stopping TTS. Wait between drags and toggle browser bars.
- Repeat with Read from here armed: a drag should scroll; a tap should start TTS.
- Check paginated mode, rotation, font changes, images loading, and saved progress.
- Play both server and browser Piper longer than the phone's auto-lock timeout;
  include buffering and pause/resume, then Stop and verify normal sleep returns.
- Switch away and back during playback; check wake-lock reacquisition. Exit the
  reader while audio is generating and confirm it cannot restart or keep awake.

After preparing source and installing frontend dependencies, run
`node tests/reader-mobile.cjs` for focused scroll-anchor and wake-lock lifecycle
regressions. These mocked checks supplement the device checks above.
