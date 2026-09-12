# AI Instructions — BookLore Reader Custom

Use this file to bring another AI coding assistant up to speed before making changes.

## Project purpose

This repository builds and deploys a customized BookLore ebook server/reader. It deliberately does not vendor BookLore's full upstream tree. `scripts/prepare-source.sh` fetches the release pinned in `config/upstream.env`, then `customizations/apply-customizations.py` modifies that clean source before Docker builds it.

The project should remain easy to deploy to Linode and easy to rebase onto newer BookLore releases.

## Non-negotiable design constraints

1. **Persistent state must remain outside Git.** Default state root: `/srv/booklore-reader`.
2. **Never commit `.env`, DB credentials, books, database files, voice caches, Caddy certificates, or backups.**
3. **Keep BookLore upstream pinned.** Do not switch production to a moving `latest`/`develop` source.
4. **Prefer guarded customizations over copying/replacing whole upstream files.** If an upstream anchor changes, fail loudly with `Upstream changed:`.
5. **Only Caddy should expose public ports.** MariaDB/Piper/BookLore stay on the internal Docker network.
6. **Browser Local TTS means inference occurs in the web browser.** It must not require a client-side container, Python daemon, or localhost API.
7. **Paste-to-EPUB must bypass BookDrop.** Direct upload destination IDs are URL query parameters, not multipart fields.

## Current upstream pin

Read `config/upstream.env`. The initial packaged pin is BookLore `v2.3.1`.

## Custom features

### TTS selection anchor

- User selects any amount of EPUB text.
- The selection's first character is the start position.
- The selection length does not limit spoken text.
- Read Aloud is an action in BookLore's text-selection popup.

### TTS queue

- Default chunk target: ~650 characters, sentence-aware.
- Each chunk has text + EPUB CFI + section index.
- Generate current chunk, play it, prefetch one or more ahead.
- Pause pauses current HTMLAudioElement.
- Stop aborts network generation, clears queue, revokes object URLs, and invalidates the session ID.
- Move the reader to a chunk's CFI when that chunk starts playing, not when it merely enters the prefetch queue.
- This keeps BookLore's saved progress and visible page near the spoken location.
- Continue across EPUB sections/chapters.

### TTS controls

- Top-right vertical stack.
- Pause/Resume button, then Stop button.
- Loading spinner below the buttons so generation does not move the transport buttons.
- When BookLore's reader header becomes visible (`headerVisible`), slide the control stack downward by the header height (~36 px) using the same ~0.25s timing.

### Reader settings

`More Settings -> Reader` provides:

- sentence pause
- chunk size
- queue-ahead count
- speech speed
- Local mode

Settings key: `bookloreReaderTtsSettings` in `localStorage`.

Preferred save semantics:

- range sliders: commit on `change` / slider release
- Local mode: immediate
- Reset: immediate
- no separate Save button
- new settings apply to the next TTS session rather than mutating a currently speaking queue unexpectedly

### Server TTS

Caddy routes `/tts/*` to the Piper container.

Voice:

- `en_US-libritts_r-medium`
- `speaker_id: 0`
- LibriTTS speaker label: `3922`

The custom Piper image patches the HTTP server to accept JSON `sentence_silence` and uses:

```python
bytes(int(sample_rate * sentence_silence) * 2)
```

for silence. Do not revert to calculating the byte count first with `int(sample_rate * sentence_silence * 2)`; that can create an odd byte count at some sample rates and corrupt following 16-bit PCM into static.

### Browser Local TTS

Uses `piper-tts-web` and `PiperWebEngine` in the browser. Copy the library's ONNX/Piper/worker runtime assets into the Angular public tree during `prepare-source.sh`.

Keep the same LibriTTS-R voice/speaker. Browser mode may implement configured sentence gaps by generating sentence audio and concatenating PCM with explicit silence. Speech speed may use HTML audio `playbackRate` with pitch preservation.

### Paste to EPUB

The main topbar Support BookLore heart is replaced by a file-edit/Paste-to-EPUB shortcut. Mobile equivalent is replaced too.

The page accepts arbitrary raw text, title, optional author, destination library/path, creates an EPUB in-browser with JSZip, and uploads it directly.

Correct upload contract:

```text
POST /api/v1/files/upload?libraryId=<libraryId>&pathId=<pathId>
```

Multipart body contains only:

```text
file=<generated EPUB>
```

IMPORTANT HISTORICAL BUG: the first implementation sent `libraryId` and `pathId` as FormData fields. The upload appeared successful but the file surfaced in BookDrop Review; trying to finalize could fail as “already there.” Do not reintroduce that implementation.

## BookDrop distinction

BookDrop is BookLore's staging/review workflow for watched-folder imports. It is useful for review, metadata work, and finalizing imported files. It is **not** the desired path for Paste-to-EPUB.

## Deployment lifecycle

### Fresh server

`scripts/provision-linode.sh`:

- Ubuntu 24.04
- installs Docker Engine/Compose from Docker's apt repository
- creates `booklore` user
- enables UFW/fail2ban
- clones repo to `/opt/booklore-reader`
- creates `/srv/booklore-reader`
- generates `.env`
- runs deploy

### Deploy

`scripts/deploy.sh`:

- uses existing `.env` or initializes it
- makes a DB backup when possible
- calls `prepare-source.sh`
- builds BookLore + Piper
- starts Compose stack

### Normal update

`scripts/update.sh` fast-forwards from GitHub and calls deploy.

### Upstream BookLore upgrade

Use `scripts/update-upstream.sh <tag>` to change only the pin, run a local/test deploy, repair any customization anchors, test all custom functionality, then commit the new pin.

## How to modify this project safely

When changing a customization:

1. Inspect the exact upstream source at the currently pinned ref.
2. Edit `customizations/apply-customizations.py`, not `.build/booklore-src`.
3. Run `./scripts/prepare-source.sh`.
4. Build/test with `./scripts/deploy.sh` or Docker build locally.
5. Do not commit `.build/`.
6. Update docs if architecture or operation changed.

When upgrading upstream, test at least:

- app boot/login
- library browsing
- EPUB reader and progress
- selection Read Aloud
- several queued TTS chunks
- pause/resume/stop + loading spinner position
- cross-chapter continuation
- server TTS
- browser Local TTS
- Reader settings persistence
- Paste-to-EPUB direct-to-library behavior
- ordinary BookDrop workflow still unaffected

## Files to inspect first

- `README.md`
- `config/upstream.env`
- `customizations/apply-customizations.py`
- `scripts/prepare-source.sh`
- `docker-compose.yml`
- `piper/patch-http-server.py`
- `docs/ARCHITECTURE.md`
- `docs/UPGRADING.md`

## Priorities

When choosing between convenience and maintainability, favor:

1. keeping user data safe
2. reproducible builds
3. explicit pinned versions
4. minimal manual Linode configuration
5. preserving upstream BookLore behavior outside the intentionally customized areas
