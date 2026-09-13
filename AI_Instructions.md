# AI Instructions — BookLore Reader Custom

Use this file to bring another AI coding assistant up to speed before modifying the project.

## Project purpose

This repository builds and deploys a customized BookLore ebook server/reader. It does not vendor the full upstream BookLore tree. `scripts/prepare-source.sh` fetches the release pinned in `config/upstream.env`; `customizations/apply-customizations.py` transforms that clean source before Docker builds it.

The production target is a fresh Ubuntu 24.04 Linode, currently sized at 2 GB RAM. GitHub is the code source of truth; `/srv/booklore-reader` on the Linode is the persistent state source of truth.

## Non-negotiable design constraints

1. Persistent state remains outside Git under `/srv/booklore-reader`.
2. Never commit `.env`, DB credentials, books, database files, voice caches, Caddy certificates, or backups.
3. Keep BookLore upstream pinned; do not point production at a moving `latest`/`develop` branch.
4. Prefer guarded source transforms; fail loudly with `Upstream changed:` when an upstream anchor changes.
5. Only Caddy exposes public app ports. MariaDB, Piper, and BookLore remain internal.
6. Browser Local TTS means inference happens in the browser; do not require a client-side container/daemon/API.
7. Paste-to-EPUB must bypass BookDrop. `libraryId` and `pathId` belong in URL query parameters, not multipart fields.
8. Production provisioning is fresh from GitHub; do not migrate the local development instance unless explicitly requested.
9. Deployment scripts must not assume `main`; `main` and `master` are both supported. Use the current branch unless `DEPLOY_BRANCH` is explicitly set.
10. The 2 GB production target requires low-memory builds: one Angular worker, Node heap limit, Gradle `--max-workers=1`, live stack stopped during image build, and swap available.
11. `/books` write permissions are functional requirements. Host paths manually created as root must be reassigned to `APP_USER_ID:APP_GROUP_ID`.

## Current upstream pin

Read `config/upstream.env`. The packaged baseline is BookLore `v2.3.1` unless that file has been deliberately updated.

## TTS behavior

### Desktop selection anchor

- User selects any amount of EPUB text.
- The first character of the selection is the start position.
- Selection length does not limit spoken text.
- `Read aloud` appears in BookLore's text-selection popup.

### Mobile tap-to-start

- Mobile/touch view has a top `Read from here` button while TTS is idle/error.
- Tapping it arms `Tap text…` mode.
- The next touch on EPUB text is converted to a collapsed range/caret and BookLore CFI/index.
- That exact location feeds the same continuous TTS queue as desktop selection.
- The consumed tap should not also turn the page/toggle the reader UI.
- Tapping the armed control again cancels.

### Queue and playback

- Default chunks are ~650 characters and sentence-aware.
- Each chunk carries text + EPUB CFI + section index.
- Prefetch future chunks, but move the reader only when a chunk starts playing.
- Continue across sections/chapters until paused/stopped.
- Pause/Resume and Stop are top-right; loading indicator stays below transport controls.
- When BookLore's header becomes visible, controls move down by the same header height.

### Reader settings

`More Settings -> Reader` contains sentence pause, chunk size, queue-ahead count, speed, and Local mode. Settings key: `bookloreReaderTtsSettings` in `localStorage`.

Preferred save semantics: sliders update visually during input and persist on release/change; toggles/reset persist immediately; no separate Save button; changed settings should normally affect the next TTS session.

### Server Piper

Caddy routes `/tts/*` to Piper. Voice is `en_US-libritts_r-medium`, speaker 0 (LibriTTS label 3922). The HTTP patch accepts `sentence_silence`; 16-bit silence must use an even byte count:

```python
bytes(int(sample_rate * sentence_silence) * 2)
```

### Browser Local Piper

Uses `piper-tts-web`/ONNX/WASM in-browser. Do not replace this with a local daemon. Browser speed can use `HTMLAudioElement.playbackRate` with pitch preservation.

## Paste to EPUB

The Support BookLore shortcut is replaced with Paste-to-EPUB. It accepts raw text, title, optional author, library/path, builds an EPUB with JSZip, and uploads directly.

Correct API contract:

```text
POST /api/v1/files/upload?libraryId=<libraryId>&pathId=<pathId>
```

Multipart body contains only the file. Historical bug: putting destination IDs in `FormData` routed generated EPUBs through BookDrop. Never reintroduce it.

## Low-memory build requirements

`customizations/apply-customizations.py` patches the upstream Dockerfile to use:

```text
NG_BUILD_MAX_WORKERS=1
NODE_OPTIONS=--max-old-space-size=1536
Gradle --max-workers=1 (not --parallel)
```

`scripts/deploy.sh` prepares source, then stops the live stack for the image build. It builds BookLore and Piper separately. On build failure after stopping the stack, it attempts to restart the previous containers.

The provisioner creates `/swapfile` at 2 GB by default (`SWAP_SIZE_GB=2`). Do not respond to memory pressure by casually increasing Node/Gradle concurrency.

Historical production failure: building with the live stack running exhausted 2 GB RAM and swap badly enough for the kernel to OOM-kill Java and system services, causing SSH banner timeouts and journald failures.

## Linode firewall model

UFW and Linode Cloud Firewall are separate. Provisioning configures UFW, but cannot change the user's Cloud Firewall without Linode API credentials. The public-interface firewall must allow TCP 22/80/443. Caddy ACME `Timeout during connect` is a strong signal to check that external firewall.

## Persistent storage and permissions

Host `/srv/booklore-reader/books` is mounted as container `/books`.

The application uses `APP_USER_ID`/`APP_GROUP_ID` from `.env`. A folder that exists but is owned `root:root` and not writable can make `POST /api/v1/files/upload` return HTTP 500 with `Error reading files from path`.

Use `scripts/create-book-folder.sh` to create folders and `sudo scripts/fix-books-permissions.sh` to repair the entire books tree. The definitive test is a `docker exec -u "$APP_USER_ID:$APP_GROUP_ID" ... mkdir /books/...` write test.

## Deployment lifecycle

### Fresh server

`scripts/provision-linode.sh` installs dependencies, configures UFW/fail2ban, creates the service user/state tree/swapfile, clones the repo's default branch (or `DEPLOY_BRANCH`), creates `.env`, and deploys.

### Normal deploy

`scripts/deploy.sh`:

1. creates `.env` if missing;
2. creates state directories;
3. backs up MariaDB when available;
4. prepares clean pinned upstream source;
5. stops the live stack when `STOP_STACK_FOR_BUILD` is enabled (default);
6. builds BookLore, then Piper;
7. starts the stack;
8. attempts recovery if the build fails after stopping the stack.

### Update

`scripts/update.sh` fast-forwards the current branch by default, or an explicit `DEPLOY_BRANCH`, then invokes deploy.

### Upstream upgrade

Use `scripts/update-upstream.sh <tag>`, prepare/build, repair any failed transform anchors, test all custom behavior, and commit the pin only after validation.

## Safe modification process

1. Inspect exact upstream source at the pinned ref.
2. Edit `customizations/apply-customizations.py`, not `.build/booklore-src`.
3. Run `./scripts/prepare-source.sh`.
4. Run `./scripts/validate.sh`.
5. Test build/deploy.
6. Never commit `.build/`.
7. Update docs when behavior/operations change.

Test at least: app login, library browsing, EPUB reader/progress, desktop Read Aloud, mobile Read from here, queued chunks, pause/resume/stop, cross-chapter continuation, server Piper, browser Local Piper, settings persistence, Paste-to-EPUB direct upload, BookDrop unaffected, and writable `/books` paths.
