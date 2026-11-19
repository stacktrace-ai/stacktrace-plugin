#!/bin/sh
# A policy hook in the Cowork zip (ADR-0014).
#
#   sh policy_hook.sh WAIT_SECONDS admit
#
# Make this boot ready first, waiting at most WAIT_SECONDS: 50 for a hook that
# decides, 0 for one that only reports. Then run the plugin's own
# `scripts/policy_hook.sh` with the hook's input. A boot that is not ready by
# then continues without a decision, as the plugin does everywhere.
here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
wait_seconds=${1:-0}
shift
sh "$here/setup.sh" "$wait_seconds" </dev/null >/dev/null 2>&1 || true
exec sh "$here/../scripts/policy_hook.sh" "$@"
