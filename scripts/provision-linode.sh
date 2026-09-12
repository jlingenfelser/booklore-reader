#!/usr/bin/env bash
set -euo pipefail
[[ ${EUID} -eq 0 ]] || { echo "Run as root on Ubuntu 24.04." >&2; exit 1; }
: "${REPO_URL:?Set REPO_URL to your GitHub repository URL}"
APP_USER="${APP_USER:-booklore}"; APP_DIR="${APP_DIR:-/opt/booklore-reader}"; SITE_ADDRESS="${SITE_ADDRESS:-:80}"; DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl gnupg git ufw fail2ban openssl python3 sudo rsync
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker fail2ban
id "$APP_USER" >/dev/null 2>&1 || useradd -m -s /bin/bash "$APP_USER"
usermod -aG docker "$APP_USER"
mkdir -p /srv/booklore-reader; chown -R "$APP_USER:$APP_USER" /srv/booklore-reader
ufw default deny incoming; ufw default allow outgoing; ufw allow OpenSSH; ufw allow 80/tcp; ufw allow 443/tcp; ufw allow 443/udp; ufw --force enable
if [[ ! -d "$APP_DIR/.git" ]]; then rm -rf "$APP_DIR"; install -d -o "$APP_USER" -g "$APP_USER" "$APP_DIR"; sudo -u "$APP_USER" git clone --branch "$DEPLOY_BRANCH" "$REPO_URL" "$APP_DIR"; fi
sudo -u "$APP_USER" bash -lc "cd '$APP_DIR' && ./scripts/init-env.sh '$SITE_ADDRESS'"
sudo -u "$APP_USER" bash -lc "cd '$APP_DIR' && ./scripts/deploy.sh"
echo "Provisioning complete: $SITE_ADDRESS"
