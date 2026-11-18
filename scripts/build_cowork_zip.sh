#!/bin/sh
# Build the Stacktrace plugin zip for Claude Cowork (ADR-0014).
#
# Usage:
#   STACKTRACE_REMOTE_TOKEN=<token> sh scripts/build_cowork_zip.sh OUT.zip [--wheel PATH]
#
# The zip holds the Claude plugin and `cowork/enroll.env` with the token.
# Set STACKTRACE_REMOTE_API_URL for an API other than https://api.stacktrace.ai.
# `--wheel` adds a stacktrace-cli wheel that a Cowork VM installs instead of
# the pinned PyPI release. Upload the zip in Customize > Plugins.
#
# The zip holds an organization secret. Keep it as you keep the token.
set -eu

out=${1:-}
[ -n "$out" ] || { echo "usage: STACKTRACE_REMOTE_TOKEN=<token> sh $0 OUT.zip [--wheel PATH]" >&2; exit 2; }
shift
wheel=''
if [ "${1:-}" = --wheel ]; then
  wheel=${2:-}
  [ -r "$wheel" ] || { echo "error: --wheel needs a readable file" >&2; exit 2; }
fi

# The session start script takes only a plain value. Refuse what it would drop.
plain() {
  case $1 in ''|*[!A-Za-z0-9._:/@+-]*) return 1 ;; esac
}
token=${STACKTRACE_REMOTE_TOKEN:-}
plain "$token" || { echo "error: set STACKTRACE_REMOTE_TOKEN to the organization's token" >&2; exit 2; }
api=${STACKTRACE_REMOTE_API_URL:-}
if [ -n "$api" ] && ! plain "$api"; then
  echo "error: STACKTRACE_REMOTE_API_URL is not a plain URL" >&2
  exit 2
fi

root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
umask 077
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT

mkdir -p "$stage/.claude-plugin" "$stage/hooks" "$stage/cowork"
cp "$root/.claude-plugin/plugin.json" "$stage/.claude-plugin/"
cp "$root/hooks/hooks.json" "$stage/hooks/"
cp -R "$root/monitors" "$root/scripts" "$root/skills" "$stage/"
rm -f "$stage/scripts/build_cowork_zip.sh" "$stage/scripts/validate_plugin.py"

{
  printf 'STACKTRACE_REMOTE_TOKEN=%s\n' "$token"
  [ -z "$api" ] || printf 'STACKTRACE_REMOTE_API_URL=%s\n' "$api"
  if [ -n "$wheel" ]; then
    name=$(basename -- "$wheel")
    plain "$name" || { echo "error: the wheel's file name is not plain" >&2; exit 2; }
    cp "$wheel" "$stage/cowork/$name"
    printf 'STACKTRACE_CLI_WHEEL=%s\n' "$name"
  fi
} >"$stage/cowork/enroll.env"

case $out in /*) target=$out ;; *) target=$(pwd)/$out ;; esac
rm -f "$target"
(cd "$stage" && zip -qr "$target" .claude-plugin hooks monitors scripts skills cowork)
echo "wrote $out"
