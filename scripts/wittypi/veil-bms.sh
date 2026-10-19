#!/bin/bash
# Crimson Veil BMS telemetry sampler for the Witty Pi 4 L3V7.
#
# Runs as its own systemd unit (veil-bms.service), independent of the kiosk and
# the control service. It reads the Witty Pi over I2C using UUGear's utilities
# and writes a small JSON snapshot that service/metrics.py consumes.
#
#   /run/veil-bms/telemetry.json
#
# Fields: ts, power_mode (0=USB, else battery), vin_v (battery when on
# battery), vout_v (5V rail), iout_a, temp_c (LM75B), charging, standby (both
# active-low, true=asserted), low_v (configured shutdown threshold, V).
#
# No battery SoC/time-left here: that estimation lives in metrics.py (host).

set -u

WITTYPI_DIR="${WITTYPI_DIR:-/home/pi/wittypi}"
STATUS_DIR="${VEIL_BMS_DIR:-/run/veil-bms}"
STATUS_FILE="$STATUS_DIR/telemetry.json"
INTERVAL_S="${VEIL_BMS_INTERVAL:-5}"

# UUGear register map + getters (overlaid copy with SYSUP_PIN=16).
# shellcheck source=/dev/null
. "$WITTYPI_DIR/utilities.sh" || { echo "veil-bms: cannot source $WITTYPI_DIR/utilities.sh" >&2; exit 1; }

mkdir -p "$STATUS_DIR"
chmod 755 "$STATUS_DIR"

# CHRG/STDBY are active-low inputs; mirror what the UUGear daemon does.
gpio -g mode "$CHRG_PIN" up 2>/dev/null || true
gpio -g mode "$CHRG_PIN" in 2>/dev/null || true
gpio -g mode "$STDBY_PIN" up 2>/dev/null || true
gpio -g mode "$STDBY_PIN" in 2>/dev/null || true

# Pull the first number out of a string ("3.86", "31.5C / 88.7F", "3.3V").
num() { grep -oE '^-?[0-9]+([.][0-9]+)?' <<<"$1" | head -1; }

# Active-low pin -> 1 when asserted (charged/charging status pulled low).
read_pin() {
  local v
  v=$(gpio -g read "$1" 2>/dev/null) || { echo 0; return; }
  [ "$v" = "0" ] && echo 1 || echo 0
}

json_bool() { [ "$1" = "1" ] && echo true || echo false; }

write_status() {
  local ts power vin vout iout temp low charging standby tmp mc
  ts=$(date +%s)
  mc=$(is_mc_connected 2>/dev/null)

  if [ "$mc" = "1" ]; then
    temp=$(num "$(get_temperature 2>/dev/null)")
    power=$(num "$(get_power_mode 2>/dev/null)")
    vin=$(num "$(get_input_voltage 2>/dev/null)")
    vout=$(num "$(get_output_voltage 2>/dev/null)")
    iout=$(num "$(get_output_current 2>/dev/null)")
    low=$(num "$(get_low_voltage_threshold 2>/dev/null)")
    charging=$(read_pin "$CHRG_PIN")
    standby=$(read_pin "$STDBY_PIN")
  else
    temp=""; power=""; vin=""; vout=""; iout=""; low=""; charging=0; standby=0
  fi

  tmp="$STATUS_FILE.tmp.$$"
  if printf '{"ts":%s,"power_mode":%s,"vin_v":%s,"vout_v":%s,"iout_a":%s,"temp_c":%s,"charging":%s,"standby":%s,"low_v":%s}\n' \
    "${ts:-0}" "${power:-null}" "${vin:-null}" "${vout:-null}" "${iout:-null}" "${temp:-null}" \
    "$(json_bool "$charging")" "$(json_bool "$standby")" "${low:-null}" > "$tmp" 2>/dev/null; then
    mv -f "$tmp" "$STATUS_FILE" && chmod 644 "$STATUS_FILE"
  else
    rm -f "$tmp" 2>/dev/null || true
  fi
}

while true; do
  write_status
  sleep "$INTERVAL_S"
done
