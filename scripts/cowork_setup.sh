#!/bin/sh
# Make Stacktrace ready in a Claude Cowork VM, once for each boot (ADR-0014).
#
#   sh cowork_setup.sh WAIT_SECONDS
#
# Cowork runs the first prompt's hooks while SessionStart still runs, and it
# restarts the VM during a task, which stops the daemon. So session start and
# every hook that decides call this first. It returns at once when this boot is
# ready. Else it starts one setup for the boot and waits for it, at most
# WAIT_SECONDS. The setup runs in its own session, so a hook that times out
# does not stop it. It installs the CLI, enrolls with the zip's token, starts
# the daemon, and is ready only when the daemon holds the organization's policy.
#
# Exit 0: ready. 1: not ready yet. 3: the install failed. 4: the API did not
# answer. 5: the daemon did not take the policy. A failure stays for its boot
# for five minutes, so later hooks do not wait on it again.
set -u

here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
plugin_root=$(dirname -- "$here")
state=${STACKTRACE_STATE_DIR:-${HOME:-/root}/.local/state/stacktrace}
# The kernel names each boot, so a restarted VM is not ready until set up again.
boot=${STACKTRACE_BOOT_ID:-$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || true)}
[ -n "$boot" ] || boot=unknown
ready="$state/cowork-ready"
failed="$state/cowork-failed"
lock="$state/cowork-setup.lock"
COWORK_CLI='stacktrace-cli==0.26.0'
FAILURE_SECONDS=300
POLICY_SECONDS=${STACKTRACE_COWORK_POLICY_SECONDS:-30}

now() { date +%s; }

# 0 when ready, a failure's code while it stands, else nothing.
outcome() {
  if [ "$(cat "$ready" 2>/dev/null)" = "$boot" ]; then
    echo 0
    return
  fi
  [ -r "$failed" ] || return 0
  read -r f_boot f_code f_at <"$failed" 2>/dev/null || return 0
  case ${f_code:-}${f_at:-} in ''|*[!0-9]*) return 0 ;; esac
  if [ "$f_boot" = "$boot" ] && [ $(($(now) - f_at)) -lt "$FAILURE_SECONDS" ]; then
    echo "$f_code"
  fi
}

run() {
  mkdir "$lock" 2>/dev/null || exit 0
  trap 'rmdir "$lock" 2>/dev/null' EXIT
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
  cli="${HOME:-/root}/.local/bin/stacktrace"
  if [ ! -x "$cli" ]; then
    spec=$COWORK_CLI
    [ -n "$cli_wheel" ] && [ -r "$cli_wheel" ] && spec=$cli_wheel
    uv tool install --quiet "$spec" </dev/null >/dev/null 2>&1 || code=3
  fi
  if [ "$code" = 0 ] && ! curl -s -o /dev/null -m 5 "${STACKTRACE_REMOTE_API_URL:-https://api.stacktrace.ai}/" </dev/null >/dev/null 2>&1; then
    code=4
  fi
  if [ "$code" = 0 ]; then
    PATH="$(dirname -- "$cli"):$PATH"
    export PATH
    # The CLI starts the daemon and, for a session with no transcript, waits
    # for it (stacktrace docs/specs/cowork.md, "Failure behavior").
    printf '%s\n' '{"hook_event_name":"SessionStart","source":"startup","session_id":"","transcript_path":""}' |
      "$cli" remote policy hooks register --agent-kind claude-code >/dev/null 2>&1 || true
    code=5
    deadline=$(($(now) + POLICY_SECONDS))
    while [ "$(now)" -lt "$deadline" ]; do
      if "$cli" remote policy hooks status --agent-kind claude-code 2>/dev/null |
        grep -Eq '"desired_revision": [0-9]+'; then
        code=0
        break
      fi
      sleep 1
    done
  fi
  if [ "$code" = 0 ]; then
    printf '%s\n' "$boot" >"$ready"
    rm -f "$failed"
  else
    printf '%s %s %s\n' "$boot" "$code" "$(now)" >"$failed"
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

# A lock left by a setup that was killed does not hold the boot back.
if [ -d "$lock" ] && [ -n "$(find "$lock" -maxdepth 0 -mmin +3 2>/dev/null)" ]; then
  rmdir "$lock" 2>/dev/null || true
fi
if [ ! -d "$lock" ]; then
  if command -v setsid >/dev/null 2>&1; then
    setsid sh "$here/cowork_setup.sh" --run </dev/null >/dev/null 2>&1 &
  else
    sh "$here/cowork_setup.sh" --run </dev/null >/dev/null 2>&1 &
  fi
fi
deadline=$(($(now) + wait_seconds))
while :; do
  result=$(outcome)
  [ -z "$result" ] || exit "$result"
  [ "$(now)" -lt "$deadline" ] || exit 1
  sleep 1
done
