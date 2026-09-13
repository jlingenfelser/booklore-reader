# Deploying to Linode

## Recommended shape

- Ubuntu 24.04 LTS.
- 2 GB Shared CPU is a workable minimum for this customized stack; builds require the low-memory safeguards in this repo.
- DNS hostname such as `books.example.com`.
- Application checkout: `/opt/booklore-reader`.
- Persistent state: `/srv/booklore-reader`.
- Only Caddy is exposed publicly.

## DNS and both firewall layers

Create an A record for the hostname pointing at the Linode IPv4. Add AAAA only if IPv6 is actually configured correctly.

There are **two firewall layers**:

1. Ubuntu UFW, configured automatically by the provisioner.
2. Linode Cloud Firewall attached to the Public Interface, configured in Linode Cloud Manager.

The Linode Cloud Firewall should allow inbound:

```text
TCP 22   0.0.0.0/0, ::/0
TCP 80   0.0.0.0/0, ::/0
TCP 443  0.0.0.0/0, ::/0
UDP 443  0.0.0.0/0, ::/0   # optional; HTTP/3
```

If Caddy logs `Timeout during connect (likely firewall problem)` while obtaining a certificate, check the Cloud Firewall first. Correct UFW rules alone do not prove public traffic can reach the VM.

## One-time provisioning

The raw GitHub URL needs a branch name, but the provisioner itself does not assume one:

```bash
BRANCH=master   # or main
curl -fsSL "https://raw.githubusercontent.com/YOU/REPO/$BRANCH/scripts/provision-linode.sh"   -o /root/provision-booklore.sh
chmod +x /root/provision-booklore.sh

REPO_URL=https://github.com/YOU/REPO.git SITE_ADDRESS=books.example.com /root/provision-booklore.sh
```

Optional variables:

```bash
DEPLOY_BRANCH=master   # otherwise clone repository default branch
SWAP_SIZE_GB=2        # default; 0 disables swapfile creation
APP_USER=booklore
APP_DIR=/opt/booklore-reader
STATE_DIR=/srv/booklore-reader
```

`SITE_ADDRESS=:80` is available for temporary HTTP-only testing.

## What the provisioner does

1. Installs Docker Engine/Compose, Git, UFW, fail2ban, Python, OpenSSL, and helpers.
2. Creates the `booklore` deployment user and adds it to the Docker group.
3. Creates `/srv/booklore-reader` and its persistent subdirectories owned by the deployment user.
4. Creates/enables `/swapfile` at 2 GB by default, without removing any existing swap partition.
5. Opens SSH, HTTP, HTTPS, and HTTP/3 in UFW.
6. Clones the default Git branch or explicit `DEPLOY_BRANCH`.
7. Generates `.env` and random MariaDB secrets.
8. Fetches the pinned BookLore source and applies customizations.
9. Builds and starts the stack.

The swapfile consumes space from the Linode's existing disk and is not a separately billed service.

## Why the low-memory build is special

On a 2 GB VM, Angular + Java + the live BookLore stack can exhaust RAM badly enough for Linux to OOM-kill Java/system services and make SSH appear hung. This repository therefore:

- sets `NG_BUILD_MAX_WORKERS=1`;
- sets Node heap to 1536 MB;
- removes Gradle `--parallel` and uses `--max-workers=1`;
- stops the running Compose stack before the image build;
- builds `booklore` and `piper` separately;
- attempts to restart the prior stack if a build fails.

If you see `Worker terminated due to reaching memory limit: JS heap out of memory`, verify the current customizer is in use and swap is active:

```bash
free -h
swapon --show
```

## Day-to-day deployment

```bash
ssh booklore@YOUR_SERVER
cd /opt/booklore-reader
./scripts/update.sh
```

The current checked-out branch is used by default. Override when needed:

```bash
DEPLOY_BRANCH=master ./scripts/update.sh
```

## HTTPS / Caddy troubleshooting

```bash
cd /opt/booklore-reader
docker compose logs --since=30m gateway | grep -Ei 'error|tls|acme|certificate|challenge|issuer'
```

From another machine:

```bash
nc -vz books.example.com 80
nc -vz books.example.com 443
```

From the Linode:

```bash
sudo ss -lntp | grep -E ':(80|443)\b'
sudo ufw status
```

## State layout

```text
/srv/booklore-reader/
├── books/
├── bookdrop/
├── data/
├── mariadb/
├── piper-data/
├── caddy-data/
├── caddy-config/
└── backups/
```

The Git checkout can be replaced without deleting the library.

## Book-folder ownership

BookLore sees `/srv/booklore-reader/books` as `/books`. The application runs with `APP_USER_ID` / `APP_GROUP_ID` from `.env`. Manually creating folders as root can make them unwritable and cause HTTP 500 upload errors.

Create folders with:

```bash
cd /opt/booklore-reader
./scripts/create-book-folder.sh Textbooks
```

Repair the whole tree as root with:

```bash
sudo ./scripts/fix-books-permissions.sh
```

See `docs/OPERATIONS.md` for a direct container write test.

## GitHub Actions

The included workflow supports `main` and `master` and uses the triggering branch. Configure `LINODE_HOST`, `LINODE_SSH_KEY`, and optional user/port/app-dir secrets.

## Fresh-install policy

Provisioning creates a new production instance from GitHub. It does not migrate the local Pop!_OS development database, books, BookDrop, or application data.
