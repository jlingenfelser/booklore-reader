# Deploying to Linode

## Recommended shape

- Ubuntu 24.04 LTS Linode.
- A DNS name such as `books.example.com` pointing to the Linode's public IPv4/IPv6 address.
- This project in a GitHub repository.
- Persistent state under `/srv/booklore-reader`.
- Application checkout under `/opt/booklore-reader`.

The only public service is Caddy on ports 80/443. Caddy terminates TLS and proxies BookLore. `/tts/*` is proxied to the server-side Piper container.

## One-time provisioning

As `root` on a fresh Ubuntu 24.04 server:

```bash
curl -fsSL https://raw.githubusercontent.com/YOU/REPO/main/scripts/provision-linode.sh \
  -o /root/provision-booklore.sh
chmod +x /root/provision-booklore.sh

REPO_URL=https://github.com/YOU/REPO.git \
SITE_ADDRESS=books.example.com \
/root/provision-booklore.sh
```

Optional variables:

```bash
APP_USER=booklore
APP_DIR=/opt/booklore-reader
DEPLOY_BRANCH=main
SITE_ADDRESS=books.example.com
```

`SITE_ADDRESS=:80` disables domain-based automatic HTTPS and is useful only for initial testing.

## What the provisioner does

1. Installs Docker Engine/Compose from Docker's Ubuntu apt repository.
2. Installs Git, UFW, fail2ban, Python, OpenSSL, and supporting packages.
3. Creates an unprivileged `booklore` deployment user and adds it to the Docker group.
4. Opens SSH, HTTP, HTTPS, and HTTP/3 ports in UFW.
5. Creates `/srv/booklore-reader` for persistent state.
6. Clones the repository to `/opt/booklore-reader`.
7. Generates `.env` with random MariaDB passwords.
8. Fetches the pinned BookLore upstream source and applies our customizations.
9. Builds BookLore and Piper and starts the stack.

## DNS / HTTPS

For `SITE_ADDRESS=books.example.com`, create an A record (and optionally AAAA record) before deployment. Caddy will request and renew certificates automatically after the hostname resolves to the server and ports 80/443 are reachable.

## Day-to-day deployment

```bash
ssh booklore@YOUR_SERVER
cd /opt/booklore-reader
./scripts/update.sh
```

`update.sh` performs a fast-forward pull and invokes the normal deployment process.

## GitHub Actions deployment

The included workflow deploys on pushes to `main` and can also be run manually. Configure repository secrets:

| Secret | Required | Meaning |
|---|---|---|
| `LINODE_HOST` | yes | hostname or public IP |
| `LINODE_SSH_KEY` | yes | private SSH key for the deployment user |
| `LINODE_USER` | no | defaults to `booklore` |
| `LINODE_SSH_PORT` | no | defaults to `22` |
| `LINODE_APP_DIR` | no | defaults to `/opt/booklore-reader` |

For a safer workflow, protect `main` and require review before merges.

## Linode StackScript

`linode/stackscript.sh` is supplied if you prefer creating a Linode with a StackScript. It asks for the repository URL, site address, and deploy branch, then performs the same basic provisioning.

For a private GitHub repo, a StackScript cannot clone it without credentials. Prefer provisioning after configuring an SSH deploy key, or temporarily use a public repository.

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

The Git repository can therefore be deleted/recloned without deleting your library.

## Migrating the existing local instance

On the existing host, from this repository:

```bash
./scripts/export-local-install.sh
```

This exports `books`, `data`, `bookdrop`, and a compressed SQL dump. Copy that directory to the Linode, perform a normal fresh deployment, then:

```bash
cd /opt/booklore-reader
./scripts/restore-migration.sh /path/to/exported-directory
```

Keep the old installation untouched until the Linode instance has been tested.

## Troubleshooting

```bash
cd /opt/booklore-reader
docker compose ps
docker compose logs -f --tail=200 booklore
docker compose logs -f --tail=200 piper
docker compose logs -f --tail=200 gateway
```

If a custom build fails immediately after changing `BOOKLORE_UPSTREAM_REF`, read the first `Upstream changed:` message from `customizations/apply-customizations.py`. That is an intentional upgrade guard.
