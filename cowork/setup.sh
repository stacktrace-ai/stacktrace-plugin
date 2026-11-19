#!/bin/sh
# Make Stacktrace ready in a Claude Cowork VM, once for each boot (ADR-0014).
# Only the Cowork zip runs this file: `scripts/build_cowork_zip.sh` puts
# `cowork/hooks.json` in the zip, and its hooks call the two wrappers here.
#
#   sh setup.sh WAIT_SECONDS
#
# Cowork runs the first prompt's hooks while SessionStart still runs, and it
# restarts the VM during a task, which stops the daemon. So every hook calls
# this first. It returns at once when this boot is ready. Else it starts one
# setup for the boot and waits for it, at most WAIT_SECONDS. The setup runs in
# its own session, so a hook that times out does not stop it. It installs the
# CLI and saves the zip's token, once for each task, because the disk stays
# across restarts. Then it starts the daemon and asks the daemon's socket for
# the policy. It is ready only when the daemon holds the organization's policy.
#
# Exit 0: ready, or not a Cowork VM. 1: not ready yet. 3: the install failed.
# 4: the API did not answer. 5: the daemon did not take the policy. A failure
# stays for its boot for five minutes, so later hooks do not wait on it again.
#
# Each step is one line in `cowork-setup.log` in the state folder: the time,
# the boot, the step and its milliseconds or code. Never a value or a payload.
set -u

[ "${CLAUDE_CODE_ENTRYPOINT:-}" = remote_cowork ] || exit 0

here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
plugin_root=$(dirname -- "$here")
state=${STACKTRACE_STATE_DIR:-${HOME:-/root}/.local/state/stacktrace}
# The kernel names each boot, so a restarted VM is not ready until set up again.
boot=${STACKTRACE_BOOT_ID:-$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || true)}
boot=$(printf '%s' "$boot" | tr -cd 'A-Za-z0-9-')
[ -n "$boot" ] || boot=unknown
ready="$state/cowork-ready"
failed="$state/cowork-failed"
# One lock for each boot: a lock that a restart left behind holds nothing back.
lock="$state/cowork-setup-$boot.lock"
log="$state/cowork-setup.log"
configured="$state/cowork-configured"
cli="${HOME:-/root}/.local/bin/stacktrace"
socket=${STACKTRACE_DAEMON_SOCKET:-/tmp/stacktrace-$(id -u 2>/dev/null || echo 0)/daemon-v1.sock}
COWORK_CLI='stacktrace-cli==0.27.0'
FAILURE_SECONDS=300
POLICY_SECONDS=${STACKTRACE_COWORK_POLICY_SECONDS:-30}
STALE_LOCK_MINUTES=3

# Milliseconds on a clock that does not step: the kernel's uptime in the VM,
# else python3's monotonic clock. A VM that syncs its time steps the wall
# clock, which would make a live lock look stale or a step take negative time.
# Each value is for this boot only, as the lock and the failure are.
clock() {
  if [ -r /proc/uptime ] && read -r up _ </proc/uptime; then
    whole=${up%.*}
    part=${up#*.}
    part=${part#0}
    case $whole${part:-0} in
      *[!0-9]*) ;;
      *) echo $((whole * 1000 + ${part:-0} * 10)); return ;;
    esac
  fi
  # Not time.monotonic(): on macOS it counts from each process's start.
  t=$(python3 -I -S -c 'import time; print(int(time.clock_gettime(time.CLOCK_MONOTONIC) * 1000))' 2>/dev/null)
  case $t in ''|*[!0-9]*) t=$(($(date +%s) * 1000)) ;; esac
  echo "$t"
}

note() {
  {
    if [ -f "$log" ] && [ "$(wc -c <"$log" 2>/dev/null || echo 0)" -gt 65536 ]; then
      tail -n 200 "$log" >"$log.$$" && mv -f "$log.$$" "$log"
    fi
    printf '%s %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$boot" "$*" >>"$log"
  } 2>/dev/null || true
}

# A step that may hang is cut off where the VM has `timeout`.
bounded() {
  seconds=$1
  shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "$seconds" "$@"
  else
    "$@"
  fi
}

# The daemon answers on its socket. A socket file alone can outlive the daemon.
daemon_up() {
  [ -S "$socket" ] || return 1
  command -v python3 >/dev/null 2>&1 || return 0
  python3 -I -S -c '
import socket, sys
s = socket.socket(socket.AF_UNIX)
s.settimeout(1)
s.connect(sys.argv[1])
' "$socket" </dev/null >/dev/null 2>&1
}

# The daemon holds a policy revision: one process asks the socket every 0.1 s.
# The CLI's `hooks status` is the fallback, and it costs a full CLI start.
policy_held() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -I -S -c '
import json, socket, sys, time
end = time.monotonic() + float(sys.argv[2])
while time.monotonic() < end:
    try:
        s = socket.socket(socket.AF_UNIX)
        s.settimeout(1)
        s.connect(sys.argv[1])
        s.sendall(b"{\"version\":1,\"type\":\"policy_status\"}\n")
        revision = json.loads(s.makefile("rb").readline(1 << 20))["status"]["desired_revision"]
        s.close()
        if type(revision) is int:
            sys.exit(0)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    time.sleep(0.1)
sys.exit(1)
' "$socket" "$1" </dev/null >/dev/null 2>&1
    return
  fi
  deadline=$(($(clock) + $1 * 1000))
  while [ "$(clock)" -lt "$deadline" ]; do
    bounded 10 "$cli" remote policy hooks status --agent-kind claude-code </dev/null 2>/dev/null |
      grep -Eq '"desired_revision": [0-9]+' && return 0
    sleep 0.2 2>/dev/null || sleep 1
  done
  return 1
}

# 0 when ready, a failure's code while it stands, else nothing.
outcome() {
  if [ "$(cat "$ready" 2>/dev/null)" = "$boot" ]; then
    if daemon_up; then
      echo 0
      return
    fi
    # The daemon stopped with no restart. Set this boot up again.
    rm -f "$ready"
    note daemon-gone 0
  fi
  [ -r "$failed" ] || return 0
  read -r f_boot f_code f_at <"$failed" 2>/dev/null || return 0
  case ${f_code:-}${f_at:-} in ''|*[!0-9]*) return 0 ;; esac
  if [ "$f_boot" = "$boot" ] && [ $(($(clock) - f_at)) -lt $((FAILURE_SECONDS * 1000)) ]; then
    echo "$f_code"
  fi
}

# A lock is stale when its setup is gone, or older than any setup takes.
clear_stale_lock() {
  for old in "$state"/cowork-setup-*.lock; do
    [ -d "$old" ] && [ "$old" != "$lock" ] && rm -rf "$old"
  done
  [ -d "$lock" ] || return 0
  pid='' at=''
  read -r pid at <"$lock/pid" 2>/dev/null || true
  case $pid in
    ''|*[!0-9]*) ;;
    *) kill -0 "$pid" 2>/dev/null || { rm -rf "$lock"; note stale-lock 0; return 0; } ;;
  esac
  case $at in
    ''|*[!0-9]*)
      # No start time yet, or a setup that stopped before it wrote one.
      [ -n "$(find "$lock" -maxdepth 0 -mmin +"$STALE_LOCK_MINUTES" 2>/dev/null)" ] || return 0 ;;
    *) [ $(($(clock) - at)) -gt $((STALE_LOCK_MINUTES * 60000)) ] || return 0 ;;
  esac
  rm -rf "$lock"
  note stale-lock 1
}

run() {
  mkdir "$lock" 2>/dev/null || exit 0
  echo "$$ $(clock)" >"$lock/pid"
  trap 'rm -rf "$lock"' EXIT
  trap 'exit 1' HUP INT TERM
  started=$(clock)
  code=0
  cli_wheel=''
  if [ -r "$plugin_root/cowork/enroll.env" ]; then
    # Known names only, and only a plain value: no space, quote or `$`.
    while IFS='=' read -r name value || [ -n "$name" ]; do
      case $value in ''|*[!A-Za-z0-9._:/@+-]*) continue ;; esac
      case $name in
        STACKTRACE_REMOTE_TOKEN) STACKTRACE_REMOTE_TOKEN=$value; export STACKTRACE_REMOTE_TOKEN ;;
        STACKTRACE_REMOTE_API_URL) STACKTRACE_REMOTE_API_URL=$value; export STACKTRACE_REMOTE_API_URL ;;
        STACKTRACE_CLI_WHEEL) case $value in */*|.*) ;; *) cli_wheel="$plugin_root/cowork/$value" ;; esac ;;
      esac
    done <"$plugin_root/cowork/enroll.env"
  fi
  if [ ! -x "$cli" ]; then
    step=$(clock)
    spec=$COWORK_CLI
    [ -n "$cli_wheel" ] && [ -r "$cli_wheel" ] && spec=$cli_wheel
    if bounded 120 uv tool install --quiet --compile-bytecode "$spec" </dev/null >/dev/null 2>&1 && [ -x "$cli" ]; then
      note install $(($(clock) - step))
    else
      code=3
    fi
  fi
  # Until a boot of this task is ready, check that the VM reaches the API. A
  # ready daemon keeps the policy on disk, so a restart needs no API call.
  if [ "$code" = 0 ] && [ ! -f "$ready" ] &&
    ! curl -s -o /dev/null -m 5 "${STACKTRACE_REMOTE_API_URL:-https://api.stacktrace.ai}/" </dev/null >/dev/null 2>&1; then
    code=4
  fi
  if [ "$code" = 0 ]; then
    PATH="$(dirname -- "$cli"):$PATH"
    export PATH
    # The daemon reads the token from the saved configuration, so save it
    # before the daemon starts. Click reads the token from the environment.
    # The disk stays across restarts, so this runs again only for a new
    # `enroll.env`, the one source of the token.
    if [ -n "${STACKTRACE_REMOTE_TOKEN:-}" ] &&
      { [ ! -f "$configured" ] || [ "$plugin_root/cowork/enroll.env" -nt "$configured" ]; }; then
      step=$(clock)
      bounded 60 "$cli" remote configure </dev/null >/dev/null 2>&1 && : >"$configured"
      note configure $(($(clock) - step))
    fi
    step=$(clock)
    if ! daemon_up; then
      if command -v setsid >/dev/null 2>&1; then
        setsid "$cli" daemon start --no-reasoning </dev/null >>"$state/daemon.log" 2>&1 &
      else
        "$cli" daemon start --no-reasoning </dev/null >>"$state/daemon.log" 2>&1 &
      fi
    fi
    if policy_held "$POLICY_SECONDS"; then
      note policy $(($(clock) - step))
      # Record the project with the daemon, as the CLI's own session start
      # does. Prompts and built-in tools need no record, so nothing waits.
      printf '%s\n' '{"hook_event_name":"SessionStart","source":"startup","session_id":"","transcript_path":""}' |
        bounded 60 "$cli" remote policy hooks register --agent-kind claude-code >/dev/null 2>&1 &
    else
      code=5
    fi
  fi
  if [ "$code" = 0 ]; then
    printf '%s\n' "$boot" >"$ready"
    rm -f "$failed"
    note ready $(($(clock) - started))
  else
    printf '%s %s %s\n' "$boot" "$code" "$(clock)" >"$failed"
    note failed "$code"
  fi
}

umask 077
mkdir -p "$state" 2>/dev/null || exit 1
if [ "${1:-}" = --run ]; then
  run
  exit 0
fi

wait_seconds=${1:-0}
case $wait_seconds in ''|*[!0-9]*) wait_seconds=0 ;; esac
result=$(outcome)
[ -z "$result" ] || exit "$result"

clear_stale_lock
if [ ! -d "$lock" ]; then
  if command -v setsid >/dev/null 2>&1; then
    setsid sh "$here/setup.sh" --run </dev/null >/dev/null 2>&1 &
  else
    sh "$here/setup.sh" --run </dev/null >/dev/null 2>&1 &
  fi
fi
deadline=$(($(clock) + wait_seconds * 1000))
while :; do
  result=$(outcome)
  [ -z "$result" ] || exit "$result"
  [ "$(clock)" -lt "$deadline" ] || exit 1
  sleep 0.2 2>/dev/null || sleep 1
done
