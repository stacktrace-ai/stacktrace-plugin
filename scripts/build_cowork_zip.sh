#!/bin/sh
# Build the Stacktrace plugin zip for Claude Cowork (ADR-0014).
#
# Run it with no checkout:
#   curl -fsSL https://raw.githubusercontent.com/stacktrace-ai/stacktrace-plugin/main/scripts/build_cowork_zip.sh | sh
#
# Or from a checkout:
#   sh scripts/build_cowork_zip.sh [OUT.zip] [--wheel PATH]
#
# It asks for the organization's Fleet token, and writes
# ~/Downloads/stacktrace-cowork.zip unless OUT.zip is given. Upload that file
# in claude.ai under Organization settings > Plugins & skills.
#
# Environment:
#   STACKTRACE_REMOTE_TOKEN    the token, so the script does not ask
#   STACKTRACE_REMOTE_API_URL  an API other than https://api.stacktrace.ai
#   STACKTRACE_PLUGIN_REF      a plugin commit or tag, in place of the one
#                              production pins (no checkout only)
# `--wheel` adds a stacktrace-cli wheel that a Cowork VM installs in place of
# the pinned PyPI release. It is for testing a build that is not released.
#
# The zip holds an organization secret. Keep it as you keep the token.
set -eu

REPO=stacktrace-ai/stacktrace-plugin

out=''
wheel=''
while [ $# -gt 0 ]; do
  case $1 in
    --wheel)
      [ $# -ge 2 ] && [ -r "$2" ] || { echo "error: --wheel needs a readable file" >&2; exit 2; }
      wheel=$2; shift 2 ;;
    -*) echo "error: unknown option $1" >&2; exit 2 ;;
    *) [ -z "$out" ] || { echo "error: give one output file" >&2; exit 2; }; out=$1; shift ;;
  esac
done
[ -n "$out" ] || out="$HOME/Downloads/stacktrace-cowork.zip"

# The session start script takes only a plain value. Refuse what it would drop.
plain() {
  case $1 in ''|*[!A-Za-z0-9._:/@+-]*) return 1 ;; esac
}

token=${STACKTRACE_REMOTE_TOKEN:-}
if [ -z "$token" ] && { : </dev/tty; } 2>/dev/null; then
  # Standard input is this script when it is piped to sh, so ask the terminal.
  printf 'Fleet token for your organization (input hidden): ' >/dev/tty
  stty -echo </dev/tty 2>/dev/null || true
  IFS= read -r token </dev/tty || token=''
  stty echo </dev/tty 2>/dev/null || true
  printf '\n' >/dev/tty
fi
plain "$token" || { echo "error: give the organization's Fleet token (STACKTRACE_REMOTE_TOKEN)" >&2; exit 2; }
api=${STACKTRACE_REMOTE_API_URL:-}
if [ -n "$api" ] && ! plain "$api"; then
  echo "error: STACKTRACE_REMOTE_API_URL is not a plain URL" >&2
  exit 2
fi

umask 077
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT

# A checkout builds from itself. Anything else downloads the plugin at the
# commit that production pins (ADR-0010), or at STACKTRACE_PLUGIN_REF.
root=''
case $0 in
  */build_cowork_zip.sh) root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." 2>/dev/null && pwd) || root='' ;;
esac
if [ -z "$root" ] || [ ! -f "$root/.claude-plugin/plugin.json" ]; then
  ref=${STACKTRACE_PLUGIN_REF:-}
  if [ -z "$ref" ]; then
    ref=$(curl -fsSL "https://raw.githubusercontent.com/$REPO/main/.claude-plugin/marketplace.json" |
      sed -n 's/.*"sha"[[:space:]]*:[[:space:]]*"\([0-9a-f]\{40\}\)".*/\1/p' | head -n 1)
    [ -n "$ref" ] || { echo "error: cannot read the released plugin commit" >&2; exit 1; }
  fi
  plain "$ref" || { echo "error: STACKTRACE_PLUGIN_REF is not a plain ref" >&2; exit 2; }
  mkdir "$stage/source"
  curl -fsSL "https://codeload.github.com/$REPO/tar.gz/$ref" | tar -xzf - -C "$stage/source" --strip-components 1 ||
    { echo "error: cannot download the plugin at $ref" >&2; exit 1; }
  root="$stage/source"
fi
if [ ! -f "$root/cowork/hooks.json" ] || [ ! -f "$root/cowork/setup.sh" ]; then
  echo "error: this plugin release does not support Claude Cowork yet" >&2
  exit 1
fi

plugin="$stage/plugin"
mkdir -p "$plugin/.claude-plugin" "$plugin/hooks" "$plugin/cowork"
cp "$root/.claude-plugin/plugin.json" "$plugin/.claude-plugin/"
# The zip runs the Cowork hooks in place of the plugin's own. They call the
# plugin's scripts after this boot's setup. The plugin's own hooks never call
# the `cowork` folder.
cp "$root/cowork/hooks.json" "$plugin/hooks/hooks.json"
cp "$root/cowork/setup.sh" "$root/cowork/session_start.sh" "$root/cowork/policy_hook.sh" "$plugin/cowork/"
cp -R "$root/monitors" "$root/scripts" "$root/skills" "$plugin/"
rm -f "$plugin/scripts/build_cowork_zip.sh" "$plugin/scripts/validate_plugin.py"

{
  printf 'STACKTRACE_REMOTE_TOKEN=%s\n' "$token"
  [ -z "$api" ] || printf 'STACKTRACE_REMOTE_API_URL=%s\n' "$api"
  if [ -n "$wheel" ]; then
    name=$(basename -- "$wheel")
    plain "$name" || { echo "error: the wheel's file name is not plain" >&2; exit 2; }
    cp "$wheel" "$plugin/cowork/$name"
    printf 'STACKTRACE_CLI_WHEEL=%s\n' "$name"
  fi
} >"$plugin/cowork/enroll.env"

case $out in /*) target=$out ;; *) target=$(pwd)/$out ;; esac
mkdir -p "$(dirname -- "$target")"
rm -f "$target"
(cd "$plugin" && zip -qr "$target" .claude-plugin hooks monitors scripts skills cowork)

cat <<EOF
Wrote $out

Next, as an Owner on claude.ai:
  1. Organization settings > Capabilities > Code execution: keep network
     egress on, and allow api.stacktrace.ai and stacktrace.ai.
  2. Organization settings > Plugins & skills: upload this zip, and set it
     to Required.
Each new Cowork task then installs Stacktrace and connects to Fleet.
EOF
