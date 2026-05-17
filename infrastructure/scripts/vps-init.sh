#!/bin/bash
#
# vps-init.sh — первоначальная настройка нового VPS под toponymics-live
#
# Что делает:
#   1. Обновляет систему
#   2. Ставит базовые утилиты
#   3. Ставит Docker + Compose plugin
#   4. Создаёт non-root юзера gisly с правами sudo и docker
#   5. Копирует SSH-ключи из root в gisly
#   6. Настраивает UFW firewall (только SSH, HTTP, HTTPS)
#   7. Ставит fail2ban
#   8. Включает автоматические обновления безопасности
#   9. Усиливает SSH (после ОБЯЗАТЕЛЬНОЙ проверки что новый юзер заходит!)
#  10. Включает swap-файл (полезно при пиках памяти)
#  11. Подготавливает /opt/toponymics для будущего git clone
#
# Использование:
#   1. Залить файл на VPS: scp vps-init.sh root@VPS_IP:/root/
#   2. Зайти: ssh root@VPS_IP
#   3. Запустить: bash vps-init.sh
#   4. Дочитать инструкции в конце скрипта
#
# Идемпотентность: можно безопасно запускать повторно — все шаги проверяют состояние.

set -euo pipefail

# ─── Параметры ─────────────────────────────────────────────────────────────

USERNAME="gisly"
PROJECT_DIR="/opt/toponymics"
SWAP_SIZE_GB=2
SSH_PORT=22  # измени, если хочешь нестандартный порт

# ─── Цветной вывод ──────────────────────────────────────────────────────────

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'  # без цвета

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*" >&2; }
step() { echo -e "\n${BLUE}━━━ $* ━━━${NC}"; }

# ─── Проверки перед стартом ────────────────────────────────────────────────

if [[ $EUID -ne 0 ]]; then
  err "Запускай от root: sudo bash $0  (или просто sh-сессия под root)"
  exit 1
fi

if ! grep -q "Ubuntu" /etc/os-release; then
  warn "Скрипт рассчитан на Ubuntu. Текущая ОС:"
  cat /etc/os-release | grep -E "^(NAME|VERSION)="
  read -p "Продолжить всё равно? [y/N] " -n 1 -r
  echo
  [[ ! $REPLY =~ ^[Yy]$ ]] && exit 1
fi

# ─── 1. Обновление системы ─────────────────────────────────────────────────

step "1/11 Обновление пакетов системы"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq -o Dpkg::Options::="--force-confold"
log "Система обновлена"

# ─── 2. Базовые утилиты ────────────────────────────────────────────────────

step "2/11 Установка базовых утилит"

apt-get install -y -qq \
  curl wget git vim nano \
  htop ncdu tree jq \
  ufw fail2ban \
  unattended-upgrades \
  ca-certificates gnupg \
  python3-pip \
  rsync zip unzip
log "Базовые утилиты установлены"

# ─── 3. Docker + Compose plugin ────────────────────────────────────────────

step "3/11 Установка Docker"

if command -v docker &>/dev/null && docker compose version &>/dev/null; then
  log "Docker и Compose уже установлены"
  docker --version
  docker compose version
else
  # Официальные docker repo для Ubuntu
  install -m 0755 -d /etc/apt/keyrings
  if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
  fi

  UBUNTU_CODENAME=$(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $UBUNTU_CODENAME stable" \
    > /etc/apt/sources.list.d/docker.list

  apt-get update -qq
  apt-get install -y -qq \
    docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin

  systemctl enable --now docker
  log "Docker установлен"
  docker --version
  docker compose version
fi

# Сконфигурировать Docker daemon: log rotation (важно, чтобы логи не съели диск)
if [[ ! -f /etc/docker/daemon.json ]]; then
  cat > /etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
  systemctl restart docker
  log "Настроена ротация Docker логов (10MB × 3 файла на контейнер)"
fi

# ─── 4. Создание non-root юзера ────────────────────────────────────────────

step "4/11 Создание пользователя $USERNAME"

if id "$USERNAME" &>/dev/null; then
  log "Пользователь $USERNAME уже существует"
else
  adduser --disabled-password --gecos "" "$USERNAME"
  log "Пользователь $USERNAME создан (без пароля — только SSH-ключ)"
fi

# Группы: sudo (для админских команд) и docker (чтобы работать без sudo с контейнерами)
usermod -aG sudo,docker "$USERNAME"
log "Добавлен в группы: sudo, docker"

# Sudo без пароля для удобства; если хочешь усилить — закомментируй
SUDOERS_FILE="/etc/sudoers.d/$USERNAME"
if [[ ! -f "$SUDOERS_FILE" ]]; then
  echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > "$SUDOERS_FILE"
  chmod 0440 "$SUDOERS_FILE"
  log "Настроен sudo без пароля (можно отключить позже)"
fi

# ─── 5. SSH-ключи ──────────────────────────────────────────────────────────

step "5/11 SSH-ключи для $USERNAME"

USER_HOME=$(getent passwd "$USERNAME" | cut -d: -f6)
mkdir -p "$USER_HOME/.ssh"

# Если у root есть authorized_keys — копируем их юзеру
if [[ -f /root/.ssh/authorized_keys ]]; then
  cp /root/.ssh/authorized_keys "$USER_HOME/.ssh/"
  log "SSH-ключи скопированы из /root/.ssh/authorized_keys"
else
  warn "У root нет authorized_keys — добавь ключ вручную:"
  warn "  echo 'ssh-ed25519 AAAA...' >> $USER_HOME/.ssh/authorized_keys"
fi

chown -R "$USERNAME:$USERNAME" "$USER_HOME/.ssh"
chmod 700 "$USER_HOME/.ssh"
[[ -f "$USER_HOME/.ssh/authorized_keys" ]] && chmod 600 "$USER_HOME/.ssh/authorized_keys"

# ─── 6. Firewall (UFW) ─────────────────────────────────────────────────────

step "6/11 Настройка firewall (UFW)"

ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow "$SSH_PORT/tcp" comment 'SSH'
ufw allow 80/tcp  comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
# Postgres и Redis НЕ открываем наружу — они только внутри Docker network
ufw --force enable
log "UFW активен. Открыты: SSH ($SSH_PORT), HTTP (80), HTTPS (443)"
ufw status verbose | head -20

# ─── 7. fail2ban ───────────────────────────────────────────────────────────

step "7/11 fail2ban (защита от брутфорса SSH)"

cat > /etc/fail2ban/jail.local <<EOF
[DEFAULT]
bantime  = 1h
findtime = 10m
maxretry = 5

[sshd]
enabled = true
port    = $SSH_PORT
EOF

systemctl enable --now fail2ban
systemctl restart fail2ban
log "fail2ban активен (5 неудач за 10 минут → бан на час)"

# ─── 8. Автоматические обновления безопасности ─────────────────────────────

step "8/11 Автообновления безопасности"

cat > /etc/apt/apt.conf.d/50unattended-upgrades <<'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
    "${distro_id}ESMApps:${distro_codename}-apps-security";
    "${distro_id}ESM:${distro_codename}-infra-security";
};
Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
EOF

cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF

systemctl enable --now unattended-upgrades
log "Автообновления безопасности включены (без автоматических reboot)"

# ─── 9. Усиление SSH ───────────────────────────────────────────────────────

step "9/11 Усиление SSH-конфига"

SSHD_CONFIG="/etc/ssh/sshd_config.d/99-hardening.conf"

# Проверка: есть ли SSH-ключ у нового юзера?
if [[ -s "$USER_HOME/.ssh/authorized_keys" ]]; then
  cat > "$SSHD_CONFIG" <<EOF
# Запрет логина паролем — только ключи
PasswordAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
PermitEmptyPasswords no

# Только этот юзер может зайти
AllowUsers $USERNAME

# Прочее
X11Forwarding no
ClientAliveInterval 300
ClientAliveCountMax 2
EOF

  # Проверка синтаксиса
  if sshd -t 2>/dev/null; then
    systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null || true
    log "SSH усилен: только ключи, только $USERNAME, без root-логина"
  else
    err "Ошибка в SSH конфиге, удаляю"
    rm -f "$SSHD_CONFIG"
  fi
else
  warn "У $USERNAME нет SSH-ключей — пропускаю усиление SSH"
  warn "Добавь ключ и запусти скрипт ещё раз:"
  warn "  echo 'ssh-ed25519 AAAA...' >> $USER_HOME/.ssh/authorized_keys"
fi

# ─── 10. Swap-файл ─────────────────────────────────────────────────────────

step "10/11 Swap-файл (${SWAP_SIZE_GB}GB)"

if [[ -f /swapfile ]]; then
  log "Swap уже настроен"
  swapon --show
else
  fallocate -l "${SWAP_SIZE_GB}G" /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile

  # Подключение при перезагрузке
  if ! grep -q "^/swapfile" /etc/fstab; then
    echo "/swapfile none swap sw 0 0" >> /etc/fstab
  fi

  # Низкий swappiness — swap только при реальной нехватке
  echo "vm.swappiness=10" > /etc/sysctl.d/99-swappiness.conf
  sysctl -p /etc/sysctl.d/99-swappiness.conf >/dev/null

  log "Swap ${SWAP_SIZE_GB}GB создан и активен (swappiness=10)"
fi

# ─── 11. Подготовка папки проекта ──────────────────────────────────────────

step "11/11 Подготовка $PROJECT_DIR"

if [[ ! -d "$PROJECT_DIR" ]]; then
  mkdir -p "$PROJECT_DIR"
fi
chown -R "$USERNAME:$USERNAME" "$PROJECT_DIR"
log "Папка $PROJECT_DIR готова, владелец: $USERNAME"

# ─── Финал ─────────────────────────────────────────────────────────────────

cat <<EOF

${GREEN}════════════════════════════════════════════════════════════════════${NC}
${GREEN}  Готово! VPS настроен.${NC}
${GREEN}════════════════════════════════════════════════════════════════════${NC}

${YELLOW}СЛЕДУЮЩИЕ ШАГИ:${NC}

1. ${YELLOW}ПРОВЕРЬ ВХОД ПОД НОВЫМ ЮЗЕРОМ${NC} (в НОВОМ окне терминала, не закрывая текущее!):
     ssh $USERNAME@$(hostname -I | awk '{print $1}')

   Если не входит — НЕ ЗАКРЫВАЙ текущую сессию, проверь:
   • Ключ в $USER_HOME/.ssh/authorized_keys
   • Права: ls -la $USER_HOME/.ssh
   • Логи: journalctl -u ssh -n 30

2. После подтверждения входа — клонируй репозиторий:
     ssh $USERNAME@<IP>
     cd $PROJECT_DIR
     git clone <твой git URL> .

3. Создай .env из примера и заполни production-значения:
     cp .env.example .env
     vim .env
     # Особенно: DJANGO_SECRET_KEY (длинная случайная строка), 
     # POSTGRES_PASSWORD, DJANGO_DEBUG=False, DJANGO_ALLOWED_HOSTS,
     # DJANGO_CSRF_TRUSTED_ORIGINS

4. Запусти стек:
     docker compose up -d --build

5. Создай суперюзера и (опционально) демо-данные:
     docker compose exec django python manage.py createsuperuser
     docker compose exec django python manage.py seed_demo

${YELLOW}ВАЖНО:${NC}
• Root SSH сейчас ОТКЛЮЧЕН — заходи только под $USERNAME
• Логи Docker ротируются автоматически (10MB × 3 на контейнер)
• fail2ban банит за 5 неудач/10 мин на час
• Автообновления безопасности включены (без auto-reboot)
• Swap ${SWAP_SIZE_GB}GB активен

Текущий IP: $(hostname -I | awk '{print $1}')
EOF
