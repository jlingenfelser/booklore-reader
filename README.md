# BookLore Reader Custom

A reproducible, GitHub-first deployment of BookLore with custom reader/TTS and paste-to-EPUB features.

The repository intentionally **does not vendor the full upstream BookLore tree**. It pins a known BookLore release in `config/upstream.env`, downloads that source during deployment, applies `customizations/apply-customizations.py`, and builds custom images. Persistent books/database/application state live outside Git under `/srv/booklore-reader`.

## Included customizations

- Piper read-aloud from an exact text-selection starting point on desktop.
- **Mobile `Read from here` control:** tap the button, then tap text in the EPUB to use that exact caret position as the TTS start point.
- Sentence-aware queued TTS with configurable chunk size and prefetch depth.
- Reader follows the current TTS chunk's EPUB CFI so BookLore progress stays close to spoken position.
- Top-right Pause/Resume, Stop, and loading indicator; controls move below BookLore's reader header when it appears.
- `More Settings -> Reader` settings for sentence pause, chunk size, queue depth, speech speed, and Local mode.
- Server TTS through Piper.
- Browser-local TTS through `piper-tts-web`/ONNX/WASM; no daemon is required on the reading device.
- `Paste text to EPUB` replaces the Support BookLore shortcut and uploads directly to the selected library/path, bypassing BookDrop.
- Low-memory production build defaults intended to allow deployment on a 2 GB Linode.

## Repository model

- **GitHub:** source overlay, deployment scripts, upstream pin, customization logic, docs.
- **Linode:** secrets + persistent books/database/data/certificates/backups.
- **Upstream BookLore:** fetched at the ref pinned in `config/upstream.env`.

Persistent state defaults to `/srv/booklore-reader`. It is never stored in Git.

## Fastest Linode deployment

### 1. Put this repository on GitHub

Either `main` or `master` works. The deployment scripts no longer assume a specific branch.

```bash
git init
git add .
git commit -m "Initial custom BookLore deployment"
git remote add origin https://github.com/YOUR-USER/YOUR-REPO.git
git push -u origin master   # or main
```

A public repository is simplest for first provisioning. For a private repository, configure GitHub authentication/deploy-key access before provisioning.

### 2. Create the Linode

Ubuntu 24.04 LTS is the intended target. A 2 GB Shared CPU Linode works for this project, but builds are memory-intensive; the provisioner creates a 2 GB swapfile by default and the custom build is deliberately restricted for low memory.

Point a DNS name such as `books.example.com` at the Linode before expecting Caddy to obtain HTTPS certificates.

**Linode Cloud Firewall:** in addition to UFW inside Ubuntu, the firewall attached to the Linode's Public Interface must allow inbound TCP 22, 80, and 443. UDP 443 is optional for HTTP/3.

### 3. Run the provisioner as root

The raw-file URL necessarily includes a Git branch. Set it to the branch where this repository lives:

```bash
BRANCH=master   # or main
curl -fsSL "https://raw.githubusercontent.com/YOUR-USER/YOUR-REPO/$BRANCH/scripts/provision-linode.sh"   -o /root/provision-booklore.sh
chmod +x /root/provision-booklore.sh

REPO_URL=https://github.com/YOUR-USER/YOUR-REPO.git SITE_ADDRESS=books.example.com /root/provision-booklore.sh
```

The provisioner clones the repository's **default branch** unless `DEPLOY_BRANCH` is explicitly supplied. Optional provisioning variables include:

```bash
DEPLOY_BRANCH=master   # optional override
SWAP_SIZE_GB=2        # set 0 to disable swapfile creation
APP_USER=booklore
APP_DIR=/opt/booklore-reader
```

For temporary IP-only HTTP testing, use `SITE_ADDRESS=:80`.

See [`docs/DEPLOY_LINODE.md`](docs/DEPLOY_LINODE.md) for the full deployment procedure.

## Routine update

On the Linode:

```bash
cd /opt/booklore-reader
./scripts/update.sh
```

`update.sh` uses the current checked-out branch unless `DEPLOY_BRANCH` is supplied. Deployment backs up the database, prepares the pinned source, stops the live stack for the memory-heavy build, builds BookLore and Piper separately, and starts the stack again. If the build fails after the stack was stopped, the script attempts to bring the previous containers back up.

## Storage and library folders

Inside the BookLore container, `/books` maps to `/srv/booklore-reader/books` on the host.

Do not create library folders as `root:root` and leave them that way; BookLore can see them but direct uploads can fail with HTTP 500 / `Error reading files from path` because the application UID cannot write there.

Use the included helper:

```bash
cd /opt/booklore-reader
./scripts/create-book-folder.sh Personal_Library
./scripts/create-book-folder.sh School
./scripts/create-book-folder.sh Textbooks
```

To repair an existing books tree, run as root:

```bash
cd /opt/booklore-reader
sudo ./scripts/fix-books-permissions.sh
```

See [`docs/OPERATIONS.md`](docs/OPERATIONS.md) for permission tests and routine administration.

## Updating BookLore itself

BookLore upstream is deliberately pinned. To change the pin:

```bash
./scripts/update-upstream.sh vNEW_VERSION
./scripts/deploy.sh
```

If an upstream source change conflicts with a transform, `apply-customizations.py` intentionally stops with `Upstream changed:` rather than silently shipping a partial customization. See [`docs/UPGRADING.md`](docs/UPGRADING.md).

## Optional automatic deploy from GitHub

`.github/workflows/deploy.yml` listens to pushes on both `main` and `master`, and can also be run manually. Configure:

- `LINODE_HOST`
- `LINODE_SSH_KEY`
- optional `LINODE_USER` (defaults to `booklore`)
- optional `LINODE_SSH_PORT` (defaults to `22`)
- optional `LINODE_APP_DIR` (defaults to `/opt/booklore-reader`)

The workflow passes the triggering branch to `scripts/update.sh`.

## Backups

Database backup:

```bash
./scripts/backup.sh
```

SQL dumps go to `/srv/booklore-reader/backups` by default. Books live under `/srv/booklore-reader/books`; use Linode Backups/snapshots or another off-server backup for persistent state.

## Fresh-install policy

Production Linode provisioning is intentionally a **fresh installation sourced from GitHub**. Nothing from the local Pop!_OS development instance is migrated unless that policy is explicitly changed later.

## Important files

- `config/upstream.env` — pinned upstream BookLore source.
- `customizations/apply-customizations.py` — all guarded BookLore transforms.
- `docker-compose.yml` — production stack.
- `piper/` — server-side Piper image and HTTP-server patch.
- `scripts/prepare-source.sh` — fetch upstream + apply customizations + prepare browser Piper assets.
- `scripts/deploy.sh` — low-memory-safe production build/start flow.
- `scripts/update.sh` — branch-aware Git update + deploy.
- `scripts/provision-linode.sh` — fresh server provisioner.
- `scripts/create-book-folder.sh` — safely create writable library folders.
- `scripts/fix-books-permissions.sh` — repair books-tree ownership/modes.
- `docs/OPERATIONS.md` — day-to-day admin and troubleshooting.
- `AI_Instructions.md` — handoff context for an AI coding assistant.

## Security notes

- Never commit `.env`; it contains database credentials.
- Only Caddy exposes public application ports. MariaDB, BookLore, and Piper stay on the internal Docker network.
- Prefer a real domain + HTTPS.
- Keep Ubuntu/Docker patched and maintain off-server backups.

## Upstream and licensing

This project is an overlay/custom build around BookLore. BookLore remains subject to its upstream license. See [`LICENSE-NOTICE.md`](LICENSE-NOTICE.md).
