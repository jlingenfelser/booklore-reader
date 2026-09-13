#!/usr/bin/env bash
# <UDF name="REPO_URL" label="GitHub repository URL" example="https://github.com/you/booklore-reader.git" />
# <UDF name="SITE_ADDRESS" label="Domain name (or :80 for IP-only HTTP)" default=":80" />
# <UDF name="DEPLOY_BRANCH" label="Git branch override (blank = repository default)" default="" />
# <UDF name="SWAP_SIZE_GB" label="Swapfile size in GB (0 disables)" default="2" />
set -euo pipefail

REPO_URL="${REPO_URL:?GitHub repository URL is required}"
SITE_ADDRESS="${SITE_ADDRESS:-:80}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-}"
SWAP_SIZE_GB="${SWAP_SIZE_GB:-2}"
APP_USER=booklore
APP_DIR=/opt/booklore-reader
STATE_DIR=/srv/booklore-reader

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl gnupg git ufw fail2ban openssl python3 sudo rsync util-linux
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
install -d -o "$APP_USER" -g "$APP_USER" "$STATE_DIR"
sudo -u "$APP_USER" mkdir -p "$STATE_DIR"/{data,books,bookdrop,mariadb,piper-data,caddy-data,caddy-config,backups}

if [[ "$SWAP_SIZE_GB" =~ ^[0-9]+$ ]] && (( SWAP_SIZE_GB > 0 )); then
  if [[ ! -f /swapfile ]]; then
    fallocate -l "${SWAP_SIZE_GB}G" /swapfile || dd if=/dev/zero of=/swapfile bs=1M count="$((SWAP_SIZE_GB * 1024))" status=progress
    chmod 600 /swapfile
    mkswap /swapfile
  fi
  swapon --show=NAME --noheadings | grep -qx '/swapfile' || swapon /swapfile
  grep -qE '^/swapfile[[:space:]]' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable

echo "NOTE: If using a Linode Cloud Firewall, allow inbound TCP 22/80/443 there too (UDP 443 optional)."

rm -rf "$APP_DIR"
install -d -o "$APP_USER" -g "$APP_USER" "$APP_DIR"
if [[ -n "$DEPLOY_BRANCH" ]]; then
  sudo -u "$APP_USER" git clone --branch "$DEPLOY_BRANCH" "$REPO_URL" "$APP_DIR"
else
  sudo -u "$APP_USER" git clone "$REPO_URL" "$APP_DIR"
fi

sudo -u "$APP_USER" bash -lc "cd '$APP_DIR' && ./scripts/init-env.sh '$SITE_ADDRESS' && ./scripts/deploy.sh"
