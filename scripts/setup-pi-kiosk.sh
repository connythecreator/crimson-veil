#!/usr/bin/env bash
#
# Crimson Veil - Raspberry Pi 3 kiosk provisioning.
#
# Turns a headless Raspberry Pi OS Lite (Trixie, 64-bit) install into a
# single-app kiosk that boots straight into the native Rust UI:
#
#   1. shows a custom PNG splash for the ENTIRE boot, drawing boot log
#      lines one at a time on top of it (a custom Plymouth theme fed by a
#      journald log service - see below),
#   2. keeps the splash up until the X session is about to take over, then
#      hands the screen to it (plymouth quit --retain-splash),
#   3. console-autologins on tty1 and starts Xorg + openbox,
#   4. launches the application fullscreen in that X session.
#
# Target: Raspberry Pi OS Lite (Trixie) 64-bit, run ON the Pi as root:
#
#     sudo bash scripts/setup-pi-kiosk.sh --splash logo.png \
#         --binary ./crimson-veil-kiosk --repo /home/pi/crimson-veil
#
# It is idempotent: safe to re-run; every change no-ops if already applied.
#
# ---------------------------------------------------------------------------
# Splash PNG + one-at-a-time boot logs, for the whole boot
# ---------------------------------------------------------------------------
# Plymouth can only show one surface, so a stock theme cannot show a logo
# and scrolling console text together. Instead this installs a small custom
# Plymouth theme (script plugin) that:
#   * draws the custom PNG, scaled to fit, as the background, and
#   * appends each message it receives (via Plymouth.SetMessageFunction) as
#     a new text line, then scrolls, so log lines appear one at a time.
# A systemd service (veil-bootlog.service) tails the kernel + systemd
# journal and feeds each line to the theme with `plymouth display-message`.
# The theme is shown for the whole boot; a `veil-splash-stop` service calls
# `plymouth quit --retain-splash` right before the getty/X handover so the
# splash holds until the GUI paints. The kernel is NOT quieted, so if the
# handover is ever delayed, the real logs are also on the console.
#
# ---------------------------------------------------------------------------
# Configuration - edit these, or pass the matching flags
# ---------------------------------------------------------------------------
# The kiosk is now the native Rust UI (`crimson-veil-kiosk`); it talks to the
# Python control service over a localhost WebSocket. This script installs:
#   * the Rust binary (run as the X session's main process), and
#   * the Python service as `crimson-veil-backend.service`.
KIOSK_BINARY=""        # path to the crimson-veil-kiosk binary (see --binary)
BINARY_DEST="/usr/local/bin/crimson-veil-kiosk"

REPO_DIR=""            # crimson-veil checkout for the Python service (--repo)
SERVICE_PORT=8765      # service listen port

SPLASH_PNG=""          # required: path to your custom PNG splash
VENV_DIR=""            # Python venv for the service; empty = <repo>/.venv

INSTALL_PY=1           # 1 = create venv + pip install requirements
KIOSK_USER="${SUDO_USER:-}"   # login user; defaults to the sudo invoker

THEME_NAME="custom"
DRY_RUN=0
NO_REBOOT=0
SKIP_PKGS=0
SKIP_SPLASH=0
SKIP_VENV=0

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
if [[ -t 1 ]]; then
  C_INFO=$'\033[1;34m'; C_OK=$'\033[1;32m'; C_WARN=$'\033[1;33m'
  C_ERR=$'\033[1;31m'; C_OFF=$'\033[0m'
else
  C_INFO=""; C_OK=""; C_WARN=""; C_ERR=""; C_OFF=""
fi

log()  { printf '%s>>%s %s\n' "$C_INFO" "$C_OFF" "$*"; }
ok()   { printf '%s[ok]%s %s\n' "$C_OK" "$C_OFF" "$*"; }
warn() { printf '%s[!!]%s %s\n' "$C_WARN" "$C_OFF" "$*" >&2; }
die()  { printf '%s[xx]%s %s\n' "$C_ERR" "$C_OFF" "$*" >&2; exit 1; }

# run CMD...: echo it, then execute unless --dry-run.
run() {
  if (( DRY_RUN )); then
    printf '   [dry-run] %s\n' "$*"
  else
    "$@"
  fi
}

# write_file PATH < stdin: write atomically-ish; honour dry-run.
write_file() {
  local path="$1"
  if (( DRY_RUN )); then
    printf '   [dry-run] write %s:\n' "$path"
    sed 's/^/       | /'
  else
    cat > "$path"
  fi
}

usage() {
  cat <<'EOF'
Usage: sudo bash scripts/setup-pi-kiosk.sh [options]

  --binary PATH       crimson-veil-kiosk binary to install (required for X session)
  --repo PATH         crimson-veil checkout that the Python service runs from
  --port N            control-service WebSocket port (default 8765)
  --splash PATH       custom PNG for the boot splash (required)
  --venv PATH         Python venv directory (default: <repo>/.venv)
  --user NAME         kiosk login user (default: the sudo invoker)
  --no-pip            do not create the venv / install requirements
  --skip-packages     do not run apt-get install
  --skip-splash       do not touch Plymouth / boot files
  --dry-run           print intended changes, change nothing
  --no-reboot         do not prompt to reboot at the end
  -h, --help          this help
EOF
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while (( $# )); do
  case "$1" in
    --binary)       KIOSK_BINARY="$2"; shift 2 ;;
    --repo)         REPO_DIR="$2"; shift 2 ;;
    --port)         SERVICE_PORT="$2"; shift 2 ;;
    --splash)       SPLASH_PNG="$2"; shift 2 ;;
    --venv)         VENV_DIR="$2"; shift 2 ;;
    --user)         KIOSK_USER="$2"; shift 2 ;;
    --no-pip)       INSTALL_PY=0; shift ;;
    --skip-packages) SKIP_PKGS=1; shift ;;
    --skip-splash)  SKIP_SPLASH=1; shift ;;
    --dry-run)      DRY_RUN=1; shift ;;
    --no-reboot)    NO_REBOOT=1; shift ;;
    -h|--help)      usage; exit 0 ;;
    *)              die "unknown argument: $1 (try --help)" ;;
  esac
done

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
(( EUID == 0 )) || die "must run as root:  sudo bash $0 ..."

[[ -n "$KIOSK_USER" ]] || die "cannot infer the kiosk user; pass --user NAME"
id -u "$KIOSK_USER" >/dev/null 2>&1 || die "no such user: $KIOSK_USER"
KIOSK_HOME="$(getent passwd "$KIOSK_USER" | cut -d: -f6)"
[[ -d "$KIOSK_HOME" ]] || die "home directory not found for $KIOSK_USER"

# Resolve the repo that the Python service runs from (default: this checkout).
if [[ -z "$REPO_DIR" ]]; then
  REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
REPO_DIR="$(readlink -f "$REPO_DIR")"
[[ -f "$REPO_DIR/service/server.py" ]] \
  || die "no service/server.py under --repo $REPO_DIR (is this the crimson-veil checkout?)"

if [[ -n "$KIOSK_BINARY" ]]; then
  [[ -f "$KIOSK_BINARY" ]] || die "kiosk binary not found: $KIOSK_BINARY"
  KIOSK_BINARY="$(readlink -f "$KIOSK_BINARY")"
fi

[[ -n "$VENV_DIR" ]] || VENV_DIR="$REPO_DIR/.venv"
[[ "$VENV_DIR" == /* ]] || VENV_DIR="$(readlink -f "$VENV_DIR")"
if (( ! SKIP_SPLASH )); then
  [[ -n "$SPLASH_PNG" ]] || die "--splash PATH is required (or pass --skip-splash)"
  [[ -f "$SPLASH_PNG" ]] || die "splash PNG not found: $SPLASH_PNG"
  file --brief --mime-type "$SPLASH_PNG" | grep -q '^image/png$' \
    || die "splash is not a PNG: $SPLASH_PNG"
fi

# Distro / arch / boot paths -------------------------------------------------
[[ -r /etc/os-release ]] || die "/etc/os-release missing"
# shellcheck disable=SC1091
. /etc/os-release
case "${ID:-}" in
  debian|raspbian) : ;;
  *) warn "unexpected distro ID='${ID:-?}' (expected debian or raspbian); continuing" ;;
esac
[[ "${VERSION_CODENAME:-}" == "trixie" ]] \
  || warn "expected Debian trixie, found '${VERSION_CODENAME:-unknown}'; paths may differ"
ARCH="$(uname -m)"
[[ "$ARCH" == "aarch64" || "$ARCH" == "armv7l" ]] \
  || die "unsupported architecture: $ARCH (expected aarch64 or armv7l)"

if [[ -f /boot/firmware/cmdline.txt ]]; then
  BOOT_DIR="/boot/firmware"
elif [[ -f /boot/cmdline.txt ]]; then
  BOOT_DIR="/boot"
else
  BOOT_DIR=""
  (( SKIP_SPLASH )) || die "no cmdline.txt found under /boot/firmware or /boot"
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
backup() {
  local f="$1"
  [[ -e "$f" ]] || return 0
  [[ -e "${f}.bak.${STAMP}" ]] && return 0
  run cp -a "$f" "${f}.bak.${STAMP}"
  ok "backed up $f -> ${f}.bak.${STAMP}"
}

# ---------------------------------------------------------------------------
# File / token helpers (idempotent)
# ---------------------------------------------------------------------------
# ensure_cmdline_token TOKEN: add TOKEN to the single-line cmdline.txt if absent.
ensure_cmdline_token() {
  local token="$1" file="$BOOT_DIR/cmdline.txt" line
  (( SKIP_SPLASH )) && return 0
  line="$(tr -d '\n' < "$file")"
  if grep -qw -- "$token" <<<"$line"; then
    return 0
  fi
  if (( DRY_RUN )); then
    printf '   [dry-run] add cmdline token: %s\n' "$token"
  else
    printf '%s %s\n' "$line" "$token" > "$file"
    ok "cmdline.txt += $token"
  fi
}

# remove_cmdline_token TOKEN: drop a whitespace-delimited token if present.
remove_cmdline_token() {
  local token="$1" file="$BOOT_DIR/cmdline.txt" line
  (( SKIP_SPLASH )) && return 0
  line="$(tr -d '\n' < "$file")"
  grep -qw -- "$token" <<<"$line" || return 0
  if (( DRY_RUN )); then
    printf '   [dry-run] remove cmdline token: %s\n' "$token"
  else
    # word-boundary-safe removal: pad, collapse, trim (no xargs: it would
    # mangle quotes/backslashes in a kernel cmdline).
    line="$(sed -E "s/(^| )$token( |$)/ /g" <<<"$line")"
    line="$(sed -E 's/[[:space:]]+/ /g; s/^ //; s/ $//' <<<"$line")"
    printf '%s\n' "$line" > "$file"
    ok "cmdline.txt -= $token"
  fi
}

# ensure_config_setTING: append 'KEY=value' to config.txt if KEY absent.
ensure_config_line() {
  local kv="$1" key="${1%%=*}" file="$BOOT_DIR/config.txt"
  (( SKIP_SPLASH )) && return 0
  [[ -f "$file" ]] || { warn "config.txt not found; skipping $kv"; return 0; }
  if grep -qE "^[[:space:]]*$key=" "$file"; then
    return 0
  fi
  if (( DRY_RUN )); then
    printf '   [dry-run] config.txt += %s\n' "$kv"
  else
    printf '%s\n' "$kv" >> "$file"
    ok "config.txt += $kv"
  fi
}

# ---------------------------------------------------------------------------
# 1. Packages and groups
# ---------------------------------------------------------------------------
install_packages() {
  if (( SKIP_PKGS )); then
    warn "--skip-packages: not installing apt packages"
    return 0
  fi

  local pkgs=(
    # Lightest X stack: server + xinit + openbox, no display manager.
    # python3-xdg provides PyXDG, required by openbox-xdg-autostart.
    # xdotool is the fullscreen safety net used from the openbox autostart.
    xserver-xorg xserver-xorg-legacy xinit x11-xserver-utils openbox python3-xdg xdotool
    # Mesa/GL + xkb so eframe (the Rust kiosk) can get a GL context on the Pi.
    libgl1-mesa-dri mesa-utils libegl1 libgl1 libxkbcommon0 fonts-dejavu-core
    # Plymouth boot splash. rpd-plym-splash provides the stock `pix` theme,
    # kept as a known-good fallback to revert to.
    plymouth plymouth-themes rpd-plym-splash
    # Python venv tooling.
    python3-venv python3-full
  )

  log "installing packages"
  run env DEBIAN_FRONTEND=noninteractive apt-get update
  run env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${pkgs[@]}"
  ok "packages present"
}

# Allow non-root startx (trixie Xorg is rootless-only by default).
configure_xwrapper() {
  log "configuring X wrapper for non-root startx"
  if (( DRY_RUN )); then
    printf '   [dry-run] write /etc/X11/Xwrapper.config\n'
    return 0
  fi
  backup /etc/X11/Xwrapper.config
  mkdir -p /etc/X11
  if [[ -f /etc/X11/Xwrapper.config ]] \
     && grep -q '^allowed_users=anybody' /etc/X11/Xwrapper.config; then
    return 0
  fi
  printf 'allowed_users=anybody\nneeds_root_rights=yes\n' > /etc/X11/Xwrapper.config
  ok "Xwrapper.config written"
}

# ---------------------------------------------------------------------------
# 1b. Install the native kiosk binary
# ---------------------------------------------------------------------------
install_kiosk_binary() {
  if [[ -z "$KIOSK_BINARY" ]]; then
    warn "no --binary given: the X session will have no kiosk to launch"
    return 0
  fi
  log "installing kiosk binary -> $BINARY_DEST"
  run install -m 0755 "$KIOSK_BINARY" "$BINARY_DEST"
  ok "kiosk binary installed"
}

# ---------------------------------------------------------------------------
# 2. Python environment (for the control service)
# ---------------------------------------------------------------------------
setup_venv() {
  if (( ! INSTALL_PY )); then
    warn "--no-pip: leaving the Python environment alone"
    return 0
  fi

  log "creating virtualenv at $VENV_DIR"
  # --system-site-packages so apt-provided packages remain importable.
  run sudo -u "$KIOSK_USER" python3 -m venv --system-site-packages "$VENV_DIR"
  run sudo -u "$KIOSK_USER" "$VENV_DIR/bin/pip" install --upgrade pip

  if [[ -f "$REPO_DIR/requirements.txt" ]]; then
    log "installing requirements from $REPO_DIR"
    run sudo -u "$KIOSK_USER" "$VENV_DIR/bin/pip" install -r "$REPO_DIR/requirements.txt"
    [[ -f "$REPO_DIR/requirements-pi.txt" ]] \
      && run sudo -u "$KIOSK_USER" "$VENV_DIR/bin/pip" install -r "$REPO_DIR/requirements-pi.txt"
  else
    log "no requirements.txt; installing websockets"
    run sudo -u "$KIOSK_USER" "$VENV_DIR/bin/pip" install websockets
  fi

  if (( ! DRY_RUN )); then
    if "$VENV_DIR/bin/python" -c 'import websockets' 2>/dev/null; then
      ok "websockets importable from $VENV_DIR"
    else
      warn "websockets NOT importable from $VENV_DIR (the service will not start)"
    fi
  fi
}

# ---------------------------------------------------------------------------
# 2b. Control-service systemd unit
# ---------------------------------------------------------------------------
install_backend_service() {
  log "installing control service (crimson-veil-backend.service)"
  write_file /etc/systemd/system/crimson-veil-backend.service <<EOF
[Unit]
Description=Crimson Veil control service (WebSocket over software.pipeline)
After=network.target
Wants=network.target

[Service]
Type=simple
User=$KIOSK_USER
WorkingDirectory=$REPO_DIR
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=$REPO_DIR
ExecStart=$VENV_DIR/bin/python -m service.server --host 127.0.0.1 --port $SERVICE_PORT
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

  run systemctl daemon-reload
  run systemctl enable crimson-veil-backend.service
}

# ---------------------------------------------------------------------------
# 3. Custom boot splash (Plymouth): PNG background + one-at-a-time log lines
# ---------------------------------------------------------------------------
setup_splash() {
  if (( SKIP_SPLASH )); then
    warn "--skip-splash: leaving Plymouth and boot files alone"
    return 0
  fi

  remove_legacy_splash_units
  install_plymouth_theme
  install_bootlog_feed
  install_splash_stop
  configure_boot_files
}

# Remove units written by earlier versions of this script that dropped the
# splash early (they would quit Plymouth seconds into boot).
remove_legacy_splash_units() {
  local u found=0
  for u in splash-hold-quit.timer splash-hold-quit.service; do
    [[ -e "/etc/systemd/system/$u" ]] || continue
    found=1
    run systemctl disable --now "$u" 2>/dev/null || true
    run rm -f "/etc/systemd/system/$u"
  done
  if (( found )); then
    run systemctl daemon-reload
    ok "removed legacy splash-hold-quit units"
  fi
}

# Locate plymouth-set-default-theme: it lives in /usr/sbin, which is not on
# root's PATH on Raspberry Pi OS.
find_plymouth_setter() {
  local c
  for c in /usr/sbin/plymouth-set-default-theme /sbin/plymouth-set-default-theme plymouth-set-default-theme; do
    if command -v "$c" >/dev/null 2>&1 || [[ -x "$c" ]]; then
      printf '%s' "$c"
      return 0
    fi
  done
  return 1
}

# A self-contained theme: scale the PNG to fill the screen, then append each
# message from Plymouth.SetMessageFunction as a new line and scroll the
# block, so boot log lines appear one at a time over the image.
install_plymouth_theme() {
  local dst=/usr/share/plymouth/themes/$THEME_NAME

  log "writing Plymouth theme '$THEME_NAME'"
  run mkdir -p "$dst"

  write_file "$dst/$THEME_NAME.plymouth" <<EOF
[Plymouth Theme]
Name=$THEME_NAME
Description=Crimson Veil splash with live boot log
ModuleName=script

[script]
ImageDir=$dst
ScriptFile=$dst/$THEME_NAME.script
EOF

  write_file "$dst/$THEME_NAME.script" <<'EOF'
# Crimson Veil boot splash: custom PNG + one-at-a-time boot log lines.
# Written by scripts/setup-pi-kiosk.sh. Do not edit in place.

screen_w = Window.GetWidth();
screen_h = Window.GetHeight();

background = Image("splash.png");
bg_ratio = background.GetWidth() / background.GetHeight();
screen_ratio = screen_w / screen_h;
if (screen_ratio > bg_ratio) {
    scale = screen_w / background.GetWidth();
} else {
    scale = screen_h / background.GetHeight();
}
scaled = background.Scale(background.GetWidth() * scale,
                          background.GetHeight() * scale);
background_sprite = Sprite(scaled);
background_sprite.SetX((screen_w - scaled.GetWidth()) / 2);
background_sprite.SetY((screen_h - scaled.GetHeight()) / 2);
background_sprite.SetZ(-10000);

# Live log pane: a stack of one-line sprites at the bottom of the screen.
# New lines push the stack up; the oldest scroll off the top. Parallel
# arrays are used because the official themes only ever index plain arrays.
LINE_H = 18;
MARGIN = 24;
MAX_LINES = Math.Int((screen_h * 0.5) / LINE_H);
line_count = 0;

fun layout_lines() {
    start = line_count - MAX_LINES;
    if (start < 0)
        start = 0;
    for (i = start; i < line_count; i++) {
        y = screen_h - MARGIN - (line_count - i) * LINE_H;
        x = MARGIN;
        msg_sprite[i].SetPosition(x, y, 10001);
        msg_shadow[i].SetPosition(x + 1, y + 1, 10000);
    }
    # Push anything scrolled off the top out of view.
    for (j = 0; j < start; j++) {
        msg_sprite[j].SetOpacity(0);
        msg_shadow[j].SetOpacity(0);
    }
}

fun message_callback(text) {
    idx = line_count;
    msg_sprite[idx] = Sprite(Image.Text(text, 0.85, 0.85, 0.85));
    msg_shadow[idx] = Sprite(Image.Text(text, 0, 0, 0));
    line_count++;
    layout_lines();
}

fun refresh_callback() {
}

Plymouth.SetMessageFunction(message_callback);
Plymouth.SetRefreshFunction(refresh_callback);
EOF

  log "installing splash image"
  run cp "$SPLASH_PNG" "$dst/splash.png"
  if (( ! DRY_RUN )) && command -v identify >/dev/null 2>&1; then
    local w h
    w="$(identify -format '%w' "$dst/splash.png")"
    h="$(identify -format '%h' "$dst/splash.png")"
    ok "splash.png is ${w}x${h} (scaled to fit; a ratio matching the panel looks best)"
  else
    warn "the PNG is scaled to fit; one matching the panel aspect ratio looks best"
  fi

  log "setting '$THEME_NAME' as the default Plymouth theme"
  local setter
  setter="$(find_plymouth_setter)" || {
    warn "plymouth-set-default-theme not found; writing plymouthd.conf directly"
    setter=""
  }
  if (( DRY_RUN )); then
    printf '   [dry-run] set Plymouth theme to %s\n' "$THEME_NAME"
  elif [[ -n "$setter" ]]; then
    "$setter" -R "$THEME_NAME" \
      || { "$setter" "$THEME_NAME"; update-initramfs -u; }
    ok "default Plymouth theme set to $THEME_NAME"
  else
    # Fallback: set it in plymouthd.conf and rebuild the initrd by hand.
    if grep -q '^\[Daemon\]' /etc/plymouth/plymouthd.conf 2>/dev/null; then
      sed -i "s/^Theme=.*/Theme=$THEME_NAME/" /etc/plymouth/plymouthd.conf
      grep -q '^Theme=' /etc/plymouth/plymouthd.conf \
        || printf 'Theme=%s\n' "$THEME_NAME" >> /etc/plymouth/plymouthd.conf
    else
      printf '[Daemon]\nTheme=%s\n' "$THEME_NAME" >> /etc/plymouth/plymouthd.conf
    fi
    update-initramfs -u || true
    ok "plymouthd.conf Theme=$THEME_NAME"
  fi
}

# Tail the kernel + systemd journal and push each line to the splash one at
# a time via `plymouth display-message`. Kept as a real script (not a
# systemd-escaped one-liner) so the shell code is legible and testable.
install_bootlog_feed() {
  log "installing boot-log feed"
  write_file /usr/local/bin/veil-bootlog <<'EOF'
#!/bin/bash
# Feed boot log lines to the Plymouth splash. Written by setup-pi-kiosk.sh.
# -n 25 backfills the last lines so the pane is not empty on first paint.
delivered=0
# Process substitution keeps this loop in the main shell, so `delivered`
# persists and the exit condition actually works.
while IFS= read -r line; do
    if [ ! -e /run/plymouth/pid ] && [ "$delivered" -gt 0 ]; then
        break
    fi
    if plymouth display-message --text="${line:0:96}" 2>/dev/null; then
        delivered=$((delivered + 1))
    fi
done < <(stdbuf -oL journalctl -b -f -o cat -n 25)
echo "veil-bootlog: delivered ${delivered} lines to the splash"
EOF
  run chmod +x /usr/local/bin/veil-bootlog

  write_file /etc/systemd/system/veil-bootlog.service <<'EOF'
[Unit]
Description=Feed boot log lines to the Plymouth splash
After=plymouth-start.service systemd-journald.service
Wants=plymouth-start.service

[Service]
Type=simple
ExecStart=/usr/local/bin/veil-bootlog
Restart=no
Nice=10

[Install]
WantedBy=sysinit.target
EOF

  run systemctl daemon-reload
  run systemctl enable veil-bootlog.service
}

# Hold the splash for the whole boot, then quit with --retain-splash so the
# last frame stays on screen while the X session takes over the VT.
#
# The primary trigger is a drop-in on the distro's own plymouth-quit.service:
# it already runs at exactly the right moment (end of boot, around getty),
# so reusing its ordering is more reliable than inventing our own. The
# veil-splash-stop unit is a belt-and-suspenders fallback that only fires if
# plymouthd is somehow still alive once tty1's getty has come up.
install_splash_stop() {
  log "installing splash handover (retain-splash)"
  run mkdir -p /etc/systemd/system/plymouth-quit.service.d
  write_file /etc/systemd/system/plymouth-quit.service.d/retain-splash.conf <<'EOF'
[Service]
ExecStart=
ExecStart=/usr/bin/plymouth quit --retain-splash
EOF

  write_file /etc/systemd/system/veil-splash-stop.service <<'EOF'
[Unit]
Description=Retain the splash frame until X takes over (fallback)
After=veil-bootlog.service getty@tty1.service
Wants=getty@tty1.service
ConditionPathExists=/run/plymouth/pid

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/plymouth quit --retain-splash

[Install]
WantedBy=multi-user.target
EOF

  run systemctl daemon-reload
  run systemctl enable veil-splash-stop.service
}

configure_boot_files() {
  log "adjusting boot files"
  backup "$BOOT_DIR/cmdline.txt"
  backup "$BOOT_DIR/config.txt"
  # Show the theme from early boot; do NOT quiet the kernel (logs are the
  # point, and serve as a fallback if the handover is ever delayed).
  ensure_cmdline_token splash
  ensure_cmdline_token plymouth.ignore-serial-consoles
  remove_cmdline_token quiet
  remove_cmdline_token plymouth.enable=0
  # Kill the firmware rainbow and use KMS so Plymouth can set the mode early.
  ensure_config_line disable_splash=1
  ensure_config_line dtoverlay=vc4-kms-v3d
}

# ---------------------------------------------------------------------------
# 4. Kiosk autostart (console autologin -> startx -> openbox -> app)
# ---------------------------------------------------------------------------
setup_autostart() {
  log "enabling console autologin on tty1"
  if command -v raspi-config >/dev/null 2>&1; then
    run raspi-config nonint do_boot_behaviour B2
  else
    warn "raspi-config not found; setting autologin via getty override"
    install_getty_override
  fi

  local xinitrc="$KIOSK_HOME/.xinitrc"
  local profile="$KIOSK_HOME/.bash_profile"
  local rcxml="$KIOSK_HOME/.config/openbox/rc.xml"
  local ob_autostart="$KIOSK_HOME/.config/openbox/autostart"

  backup "$xinitrc"; backup "$profile"; backup "$rcxml"; backup "$ob_autostart"

  # The Rust kiosk reads the service URL from CV_WS_URL.
  local kiosk_cmd="$BINARY_DEST"
  if [[ -z "$KIOSK_BINARY" ]]; then
    kiosk_cmd="$BINARY_DEST  # NOTE: --binary was not given"
  fi

  log "writing $xinitrc"
  write_file "$xinitrc" <<EOF
#!/bin/sh
# Crimson Veil kiosk X session (managed by scripts/setup-pi-kiosk.sh).
xset s off
xset -dpms
xset s noblank
# Window manager first, then the kiosk as the session's main process so the
# X session ends when it exits. The Python control service runs separately as
# crimson-veil-backend.service.
export CV_WS_URL="ws://127.0.0.1:$SERVICE_PORT"
openbox-session &
exec $kiosk_cmd
EOF

  log "writing $profile (startx on tty1 only)"
  write_file "$profile" <<'EOF'
# Crimson Veil kiosk (managed by scripts/setup-pi-kiosk.sh).
# Auto-start X only on the first virtual console, and only once.
if [ "$(tty)" = "/dev/tty1" ] && [ -z "$DISPLAY" ] && [ -z "$SSH_CONNECTION" ]; then
    exec startx -- -nocursor
fi
EOF

  log "writing openbox fullscreen rule"
  run mkdir -p "$(dirname "$rcxml")"
  # Note: keep XML comments free of "--" (a double hyphen is illegal inside
  # an XML comment and makes openbox's parser abort).
  write_file "$rcxml" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!-- Crimson Veil kiosk window rule. If the title match does not apply, the
     openbox autostart file also forces the active window fullscreen. -->
<openbox_config xmlns="http://openbox.org/3.4/rc">
  <applications>
    <application title="Crimson Veil*" class="*">
      <fullscreen>yes</fullscreen>
      <decor>no</decor>
      <maximized>yes</maximized>
      <focus>yes</focus>
    </application>
  </applications>
</openbox_config>
EOF

  log "writing openbox autostart (fullscreen safety net)"
  write_file "$ob_autostart" <<'EOF'
# Crimson Veil kiosk (managed by scripts/setup-pi-kiosk.sh).
# The app requests fullscreen itself; this is a fallback that forces the
# active window fullscreen shortly after it appears.
sh -c 'sleep 3; command -v xdotool >/dev/null 2>&1 && xdotool search --sync --onlyvisible --name "Crimson Veil" windowstate --add fullscreen' &
EOF

  if (( ! DRY_RUN )); then
    local g
    # dialout: serial access to the ESP32.
    for g in video render input audio gpio dialout; do
      getent group "$g" >/dev/null 2>&1 && usermod -aG "$g" "$KIOSK_USER"
    done
    chown "$KIOSK_USER":"$KIOSK_USER" "$xinitrc" "$profile" "$rcxml" "$ob_autostart" 2>/dev/null || true
    chown "$KIOSK_USER":"$KIOSK_USER" "$(dirname "$rcxml")" 2>/dev/null || true
    ok "autostart configured for $KIOSK_USER"
  fi
}

# Fallback when raspi-config is unavailable: a systemd getty drop-in.
install_getty_override() {
  run mkdir -p /etc/systemd/system/getty@tty1.service.d
  write_file /etc/systemd/system/getty@tty1.service.d/autologin.conf <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $KIOSK_USER --noclear %I \$TERM
EOF
  run systemctl daemon-reload
}

# ---------------------------------------------------------------------------
# 5. Report
# ---------------------------------------------------------------------------
report() {
  log "verification"
  printf '   kiosk      : %s%s\n' "$BINARY_DEST" \
    "$( [[ -n "$KIOSK_BINARY" ]] || printf '  (no --binary given!)' )"
  printf '   service    : %s/.venv  ws://127.0.0.1:%s\n' "$REPO_DIR" "$SERVICE_PORT"
  printf '   user       : %s\n' "$KIOSK_USER"

  if (( ! SKIP_SPLASH )) && (( ! DRY_RUN )); then
    printf '   theme      : %s\n' "$(plymouth-set-default-theme 2>/dev/null || echo '?')"
    printf '   splash.png : %s\n' "$(file --brief /usr/share/plymouth/themes/$THEME_NAME/splash.png 2>/dev/null || echo missing)"
    printf '   cmdline    : %s\n' "$(cat "$BOOT_DIR/cmdline.txt" 2>/dev/null)"
    printf '   bootlog    : %s\n' "$(systemctl is-enabled veil-bootlog.service 2>/dev/null || echo '?')"
    printf '   handover   : %s\n' "$(systemctl is-enabled veil-splash-stop.service 2>/dev/null || echo '?')"
  fi

  if (( ! DRY_RUN )); then
    printf '   backend    : %s\n' "$(systemctl is-enabled crimson-veil-backend.service 2>/dev/null || echo '?')"
  fi

  cat <<EOF

Manual revert
  sudo cp -a ${BOOT_DIR}/cmdline.txt.bak.${STAMP} ${BOOT_DIR}/cmdline.txt
  sudo cp -a ${BOOT_DIR}/config.txt.bak.${STAMP}  ${BOOT_DIR}/config.txt
  sudo plymouth-set-default-theme -R pix
  sudo systemctl disable --now veil-bootlog.service veil-splash-stop.service
  sudo systemctl disable --now crimson-veil-backend.service
  sudo rm -rf /usr/share/plymouth/themes/${THEME_NAME}
  sudo rm -f ${BINARY_DEST} /etc/systemd/system/crimson-veil-backend.service
  sudo raspi-config nonint do_boot_behaviour B1   # console login
  # then: rm ~/.xinitrc ~/.config/openbox/rc.xml  (keep ~/.bash_profile)
EOF
}

# ---------------------------------------------------------------------------
main() {
  log "Crimson Veil Pi 3 kiosk setup"
  printf '   distro     : %s %s (%s)\n' "${ID:-?}" "${VERSION_CODENAME:-?}" "$ARCH"
  printf '   boot dir   : %s\n' "${BOOT_DIR:-<skip>}"
  (( DRY_RUN )) && warn "DRY RUN: no changes will be made"

  install_packages
  configure_xwrapper
  install_kiosk_binary
  setup_venv
  install_backend_service
  setup_splash
  setup_autostart
  report

  if (( ! NO_REBOOT )) && (( ! DRY_RUN )); then
    read -r -p "Reboot now to test the kiosk? [y/N] " reply
    case "$reply" in
      [yY]*) log "rebooting"; systemctl reboot ;;
      *)     warn "not rebooting; run 'sudo reboot' when ready" ;;
    esac
  fi
}

main "$@"
