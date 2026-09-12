# BookLore Reader Custom

A reproducible, GitHub-first deployment of BookLore with the reader/TTS customizations built during this project.

The repository intentionally **does not vendor the full upstream BookLore tree**. Instead it pins a known upstream BookLore release, downloads that exact source during deployment, applies the customizations in `customizations/apply-customizations.py`, and builds a custom image. This keeps the GitHub repository small and makes future BookLore upgrades reviewable.

## Included customizations

- Piper read-aloud from an exact text-selection starting point.
- Sentence-aware queued TTS with configurable chunk size and prefetch depth.
- The reader follows the current TTS chunk's EPUB CFI so normal BookLore progress stays close to spoken position.
- Top-right Pause/Resume, Stop, and loading indicator; controls slide below BookLore's header when it appears.
- `More Settings -> Reader` settings for sentence pause, chunk size, queue depth, speech speed, and Local mode.
- Server TTS through Piper.
- Browser-local TTS through `piper-tts-web`/ONNX/WASM; no Piper daemon is required on the reading device.
- `Paste text to EPUB` replaces the Support BookLore heart shortcut.
- Paste-to-EPUB builds the EPUB in-browser and **uploads directly to the chosen library/path**, bypassing BookDrop review.

## Repository model

- **GitHub:** code, deployment scripts, upstream pin, customization logic.
- **Linode:** secrets and persistent state (`books`, database, BookLore data, backups).
- **Upstream BookLore:** fetched at the ref pinned in `config/upstream.env`.

Persistent state defaults to `/srv/booklore-reader`. It is never stored in this Git repository.

## Fastest Linode deployment

### 1. Put this repository on GitHub

Unpack the archive, create a GitHub repository, then:

```bash
git init
git add .
git commit -m "Initial custom BookLore deployment"
git branch -M main
git remote add origin https://github.com/YOUR-USER/YOUR-REPO.git
git push -u origin main
```

A public repository is simplest for first provisioning. For a private repository, configure a deploy key/token before running the provisioning script.

### 2. Create a Linode

Ubuntu 24.04 LTS is the intended target. Point a DNS name such as `books.example.com` to the Linode first if you want automatic HTTPS from Caddy.

### 3. Run the provisioner as root

```bash
curl -fsSL https://raw.githubusercontent.com/YOUR-USER/YOUR-REPO/main/scripts/provision-linode.sh \
  -o /root/provision-booklore.sh
chmod +x /root/provision-booklore.sh

REPO_URL=https://github.com/YOUR-USER/YOUR-REPO.git \
SITE_ADDRESS=books.example.com \
/root/provision-booklore.sh
```

For temporary IP-only HTTP testing, use `SITE_ADDRESS=:80`.

The provisioner installs Docker, configures UFW/fail2ban, creates the `booklore` service user, clones the repository to `/opt/booklore-reader`, generates database secrets, prepares the custom source, builds it, and starts the stack.

See [`docs/DEPLOY_LINODE.md`](docs/DEPLOY_LINODE.md) for the full deployment and DNS details.

## Routine update

On the Linode:

```bash
cd /opt/booklore-reader
./scripts/update.sh
```

That performs a DB backup, pulls the repository, rebuilds the pinned BookLore source with the customizations, and recreates the services while preserving `/srv/booklore-reader`.

## Updating BookLore itself

BookLore upstream is deliberately pinned in `config/upstream.env`. To test a newer upstream release:

```bash
./scripts/update-upstream.sh vNEW_VERSION
./scripts/deploy.sh
```

If an upstream source change conflicts with one of our transformations, `apply-customizations.py` should stop with an `Upstream changed:` error. Update the transformation, test, then commit the new pin.

See [`docs/UPGRADING.md`](docs/UPGRADING.md).

For testing the generated build on Pop!_OS or another Docker host, see [`docs/LOCAL_DEVELOPMENT.md`](docs/LOCAL_DEVELOPMENT.md).

## Optional automatic deploy from GitHub

`.github/workflows/deploy.yml` can deploy every push to `main` over SSH. Add these GitHub Actions secrets:

- `LINODE_HOST`
- `LINODE_SSH_KEY`
- `LINODE_USER` (optional; defaults to `booklore`)
- `LINODE_SSH_PORT` (optional; defaults to `22`)
- `LINODE_APP_DIR` (optional; defaults to `/opt/booklore-reader`)

You can also delete/disable that workflow and use `./scripts/update.sh` manually.

## Backups

Database backup:

```bash
./scripts/backup.sh
```

SQL dumps are stored in `/srv/booklore-reader/backups` by default. Book files already live separately under `/srv/booklore-reader/books`; use Linode Backups, snapshots, or another off-server backup for those persistent directories.

## Moving the current local installation

On the current Pop!_OS machine:

```bash
./scripts/export-local-install.sh
```

Copy the resulting migration directory to the Linode, deploy this repository once, then run:

```bash
cd /opt/booklore-reader
./scripts/restore-migration.sh /path/to/booklore-migration-YYYYMMDD-HHMMSS
```

## Important project files

- `config/upstream.env` — pinned upstream BookLore source.
- `customizations/apply-customizations.py` — all BookLore source transformations.
- `docker-compose.yml` — production stack.
- `piper/` — server-side Piper image and HTTP-server fixes.
- `scripts/prepare-source.sh` — fetch upstream + apply customizations + prepare frontend dependencies/assets.
- `scripts/deploy.sh` — build/start current repository.
- `scripts/update.sh` — pull GitHub + deploy.
- `scripts/provision-linode.sh` — one-time server provisioner.
- `linode/stackscript.sh` — same basic provisioning flow in StackScript form.
- `AI_Instructions.md` — handoff context for an LLM or future developer.

## Security notes

- Never commit `.env`; it contains database credentials.
- Only Caddy exposes public ports. MariaDB, BookLore, and Piper remain on the Docker network.
- Prefer a real domain and HTTPS for browser-local TTS and normal account security.
- Keep Ubuntu and Docker patched and maintain off-server backups.

## Upstream and licensing

This project is an overlay/custom build around BookLore. BookLore is an upstream open-source project and its own licensing remains applicable to the modified application. See [`LICENSE-NOTICE.md`](LICENSE-NOTICE.md).
