#!/bin/sh
# Export every component used by the assembly, in its assembled frame.
set -e
cd "$(dirname "$0")"
run_pi() { openscad -o "../parts/pi-$1.stl" -D "COMPONENT=\"$1\"" _pi_part.scad >/tmp/exp-pi-$1.log 2>&1; echo "pi-$1 done"; }
run_ce() { openscad -o "../parts/ce-$1.stl" -D "COMPONENT=\"$1\"" _ce_part.scad >/tmp/exp-ce-$1.log 2>&1; echo "ce-$1 done"; }
for p in pi wittypi lcd header leds switches base mid bezel plate; do
  run_pi "$p" &
  while [ "$(jobs -rp | wc -l)" -ge 4 ]; do sleep 0.5; done
done
wait
for p in base lid board- board+ esp32; do
  run_ce "$p" &
  while [ "$(jobs -rp | wc -l)" -ge 4 ]; do sleep 0.5; done
done
wait
