#!/usr/bin/env bash
# One fleet box, behind the replay server and back (A11-165). Every change on a box is Ansible, run on the control plane; nothing is done by hand and no box is reached by ssh from here.
#
#     box.sh on <worker>        `change`, then `probes`
#     box.sh change <worker>    history off, the store emptied, the replay set-up, and the read-back of each by the plays: the changes, which are made one box at a time
#     box.sh probes <worker>    the two probes (`probe-history`: history `after`; `probe-replay`: replay `on`): captures, which several boxes may run at once
#     box.sh afterrun <worker>  the two probes again, once the corpus is captured
#     box.sh off <worker>       the replay set-up taken away, history back on, and the read-back of each; `fleet:status`
#
# Environment (RUNBOOK.md has each): EMU (this checkout), RUN_ID, R (the results directory), W (scratch), A11Y_CONTROL_HOST, A11Y_PVE_KEY, CAPTURE_HOST (this machine's address, for the boxes), PORTS ("worker=port,..."
# of the replay servers), HISTORY_PROBE (the history probe page's address on capture-host), EMU_DOWNLOADS. fleet:status runs from ~/repos/control.
set -euo pipefail
B=${2:?a worker name}; verb=${1:?on|change|probes|afterrun|off}
INV=~/.config/a11ign/inventory.yml; F=$EMU/q3/replay/fleet; PLAY=$R/fleet/plays; mkdir -p "$PLAY" "$W/probes" "$R/fleet/probes"
plane() { ssh -i "$A11Y_PVE_KEY" -o StrictHostKeyChecking=no root@"$A11Y_CONTROL_HOST" "$@"; }
worker_url() { python3 -c 'import yaml,sys; inv=yaml.safe_load(open(sys.argv[2])); print("http://%s:8765" % inv["all"]["children"]["a11y_workers"]["hosts"][sys.argv[1]]["ansible_host"])' "$1" "$INV"; }
port_of() { tr ',' '\n' <<<"$PORTS" | sed -n "s/^$1=//p"; }
scrub() { CAPTURE_HOST=$CAPTURE_HOST CONTROL_HOST=$A11Y_CONTROL_HOST python3 "$F/scrub.py" "$INV"; }
on_plane() { plane "cd /root/control/ansible && $*" 2>&1 | scrub; }      # a play's or a module's own output, addresses taken out
cap() { node "$EMU/q3/fleet_capture.mjs" "$B=$(worker_url "$B")" "$1" "$2"; }       # one capture of an address by the box
replay_probe() {      # the archive-only page, through the box's own replay server; $1 the stage
  python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); from control import control; control(int(sys.argv[2]), "/use?archive=probe.flows")' "$EMU/q3/replay" "$(port_of "$B")"
  cap https://replay-probe.test/ "$W/probes/$B.replay-$1.json"
  locked python3 "$EMU/q3/replay/replay_readback.py" probe "$R/replay-readback.json" "$B" "$1" "$W/probes/$B.replay-$1.json"
  scrub < "$W/probes/$B.replay-$1.json" > "$R/fleet/probes/$B.replay-$1.json"      # a record can name the page server by its address (the page the browser visited before)
}
history_probe() {     # the visit, then the read; $1 the stage name for the read
  cap "$HISTORY_PROBE" "$W/probes/$B.history-$1-visit.json"
  cap "$HISTORY_PROBE" "$W/probes/$B.history-$1.json"
  locked python3 "$EMU/q3/remeasure/readback.py" probe "$R/history-readback.json" "$B" "$1" "$W/probes/$B.history-$1.json"
  scrub < "$W/probes/$B.history-$1.json" > "$R/fleet/probes/$B.history-$1.json"
}
locked() { flock "$W/.readback.lock" "$@"; }      # the read-back files are read, changed and written whole: boxes whose probes end together must not write over each other
idle() { curl -fsS "$(worker_url "$B")/health" | python3 -c 'import json,sys; sys.exit(1 if json.load(sys.stdin).get("busy") else 0)' || { echo "$B is busy: nothing is run on it" >&2; exit 1; }; }
stop_edge() { on_plane "ansible $B -m ansible.windows.win_shell -a 'Get-Process msedge -ErrorAction SilentlyContinue | Stop-Process -Force; Start-Sleep 3; (Get-Process msedge -ErrorAction SilentlyContinue | Measure-Object).Count'"; }
history_value() { on_plane "ansible $B -b -m ansible.windows.win_reg_stat -a 'path=HKLM:\\\\SOFTWARE\\\\Policies\\\\Microsoft\\\\Edge name=SavingBrowserHistoryDisabled'"; }

case $verb in
on) "$0" change "$B"; "$0" probes "$B" ;;
change)
  idle; stop_edge | tee "$PLAY/$B.stop-edge.txt"
  # history off, through the fleet's own play (as A11-155): the plane's own list plus SavingBrowserHistoryDisabled=1
  on_plane "ANSIBLE_CONFIG=ansible.cfg ansible-playbook provision-role.yml --tags policy -l $B -e @/tmp/replay/$RUN_ID/override.yml" | tee "$PLAY/$B.policy.txt" | tail -8
  history_value | tee "$PLAY/$B.history-value.txt" | grep -qE '^ +value: 1$'
  locked python3 "$EMU/q3/remeasure/readback.py" policy "$R/history-readback.json" "$B" 1 "provision-role.yml --tags policy asserted all policy values; win_reg_stat read value 1"
  for f in History History-journal 'Visited Links'; do
    on_plane "ansible $B -m ansible.windows.win_file -a '{\"path\": \"%LOCALAPPDATA%\\\\a11y-witness\\\\edge-profile\\\\Default\\\\$f\", \"state\": \"absent\"}'" >/dev/null
  done
  locked python3 "$EMU/q3/remeasure/readback.py" emptied "$R/history-readback.json" "$B" "Default/History, History-journal removed by win_file"
  # the replay set-up: this repository's own play, from the plane's control/ansible
  on_plane "ANSIBLE_CONFIG=ansible.cfg ansible-playbook /tmp/replay/$RUN_ID/replay-on.yml -l $B -e @/tmp/replay/$RUN_ID/vars-$B.json" | tee "$PLAY/$B.replay-on.txt" | tail -12
  grep -q 'replay on: ProxyMode=fixed_servers' "$PLAY/$B.replay-on.txt"
  locked python3 "$EMU/q3/replay/replay_readback.py" proxy "$R/replay-readback.json" "$B" "capture-host:$(port_of "$B")" "replay-on.yml read ProxyMode, ProxyServer and ProxyBypassList back with win_reg_stat and asserted them"
  locked python3 "$EMU/q3/replay/replay_readback.py" certificate "$R/replay-readback.json" "$B" "replay-on.yml found the run's certificate once in LocalMachine\\Root and asserted it" ;;
probes) "$0" probe-history "$B"; "$0" probe-replay "$B" ;;
probe-history) idle; history_probe after ;;
probe-replay) idle; replay_probe on ;;
afterrun)
  idle; history_probe after-run; replay_probe after-run ;;
off)
  idle
  on_plane "ANSIBLE_CONFIG=ansible.cfg ansible-playbook /tmp/replay/$RUN_ID/replay-off.yml -l $B -e @/tmp/replay/$RUN_ID/vars-$B.json" | tee "$PLAY/$B.replay-off.txt" | tail -12
  grep -q 'replay off: ProxyMode, ProxyServer and ProxyBypassList are absent' "$PLAY/$B.replay-off.txt"
  locked python3 "$EMU/q3/replay/replay_readback.py" removed "$R/replay-readback.json" "$B" "replay-off.yml read the three proxy values back as absent and the certificate as not in LocalMachine\\Root, and asserted both"
  on_plane "ANSIBLE_CONFIG=ansible.cfg ansible-playbook provision-role.yml --tags policy -l $B -e @/tmp/replay/$RUN_ID/restore.yml" | tee "$PLAY/$B.restore.txt" | tail -8
  history_value | tee "$PLAY/$B.history-value-restored.txt" | grep -qE '^ +value: 0$'
  locked python3 "$EMU/q3/remeasure/readback.py" restored "$R/history-readback.json" "$B" "restore play failed=0; win_reg_stat read value 0"
  replay_probe off || true
  ( cd ~/repos/control && pnpm run fleet:status 2>&1 | scrub > "$W/status-$B.txt" )
  line=$(grep -E "^ +$B " "$W/status-$B.txt" | head -1); echo "$line"
  state=$(awk '{print $3}' <<<"$line")      # the columns: worker, its address (taken out), state, code
  locked python3 "$EMU/q3/replay/replay_readback.py" status "$R/replay-readback.json" "$B" "$state" "fleet:status after the restore: $line" ;;
*) echo "on|change|probes|probe-history|probe-replay|afterrun|off" >&2; exit 2 ;;
esac
