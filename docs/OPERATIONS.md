# Operations and Troubleshooting

This is the routine runbook for the production Linode.

## Connect and check health

```bash
ssh root@books.example.com
cd /opt/booklore-reader
docker compose ps
```

Useful logs:

```bash
docker compose logs --tail=100 booklore
docker compose logs --tail=100 gateway
docker compose logs --tail=100 mariadb
docker compose logs --tail=100 piper
```

To capture a new BookLore error from its beginning:

```bash
docker compose logs -f --tail=0 booklore
```

Trigger the failure once, then press `Ctrl+C`.

## Routine update

```bash
cd /opt/booklore-reader
./scripts/update.sh
```

The script backs up the database when MariaDB is running, prepares source, stops the stack during the memory-heavy build, builds one service at a time, and starts the stack again.

## Memory / swap

```bash
free -h
swapon --show
```

The expected 2 GB Linode configuration normally has the Linode-provided small swap partition plus `/swapfile` (2 GB by default).

If SSH reaches port 22 but times out during banner exchange while a build is running, use Linode LISH. If LISH shows `Out of memory: Killed process`, the build has failed. If system services such as journald are being OOM-killed, reboot and use the current low-memory deployment scripts.

## Book storage mapping

Container path:

```text
/books
```

Host path:

```text
/srv/booklore-reader/books
```

### Create folders safely

```bash
cd /opt/booklore-reader
./scripts/create-book-folder.sh Personal_Library
./scripts/create-book-folder.sh School
./scripts/create-book-folder.sh Textbooks
```

Nested paths are supported:

```bash
./scripts/create-book-folder.sh 'School/Fall_2026'
```

### Repair permissions

If a direct upload returns HTTP 500 and the UI says:

```text
Error reading files from path: /books/Textbooks/...
```

repair ownership as root:

```bash
cd /opt/booklore-reader
sudo ./scripts/fix-books-permissions.sh
```

Then test a write as the exact UID/GID BookLore uses:

```bash
set -a
source .env
set +a

docker exec -u "$APP_USER_ID:$APP_GROUP_ID" booklore   sh -c 'mkdir /books/Textbooks/booklore-write-test && rmdir /books/Textbooks/booklore-write-test && echo WRITE_OK'
```

`WRITE_OK` proves the bind mount is writable by the application user.

## Upload-size setting

BookLore has an admin-configurable upload limit. Change **Settings -> Application -> File Management -> Max File Upload Size**, then restart BookLore:

```bash
docker compose restart booklore
```

A 500 error on a small file should not automatically be treated as a size-limit problem; inspect BookLore logs and storage permissions.

## Compress a PDF on Pop!_OS

Install Ghostscript:

```bash
sudo apt install ghostscript
```

General-purpose compression:

```bash
gs -sDEVICE=pdfwrite    -dCompatibilityLevel=1.4    -dPDFSETTINGS=/ebook    -dNOPAUSE -dQUIET -dBATCH    -sOutputFile='compressed.pdf'    'input.pdf'
```

Use `/screen` for stronger compression/lower image quality.

## HTTPS / Let's Encrypt

Caddy automatically obtains certificates when DNS and public ports are correct:

```bash
docker compose logs --since=30m gateway |   grep -Ei 'error|tls|acme|certificate|challenge|issuer'
```

`Timeout during connect (likely firewall problem)` usually means inbound TCP 80/443 is blocked by the Linode Cloud Firewall even if UFW is correct.

## UFW

```bash
sudo ufw status
```

Expected web rules include TCP 80/443; UDP 443 is optional for HTTP/3.

Do not expose MariaDB 3306, BookLore 6060, or Piper 5000 publicly.

## Database backup

```bash
cd /opt/booklore-reader
./scripts/backup.sh
```

Backups are stored under `/srv/booklore-reader/backups`. Back up the persistent state directory off-server as well.

## Restart services

BookLore only:

```bash
docker compose restart booklore
```

Whole stack:

```bash
docker compose up -d --remove-orphans
```

Status:

```bash
docker compose ps
```

## Mobile TTS

On a touch/mobile reader:

1. Tap **Read from here** in the top reader controls.
2. It changes to **Tap text…**.
3. Tap the desired text position in the EPUB.
4. That caret/CFI becomes the exact TTS starting point and reading continues forward.
5. Tap **Tap text…** again before choosing text to cancel.

Desktop text selection -> **Read aloud** remains available separately.

## Local Pop!_OS development stack

To stop the old local stack without deleting its state:

```bash
cd ~/booklore-tts
docker compose down
```

To also remove that project's Docker images:

```bash
docker compose down --rmi all
```
