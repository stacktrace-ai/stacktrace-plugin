#!/bin/sh
# SessionStart in the Cowork zip (ADR-0014). Make this boot ready, then run
# the plugin's own `scripts/session_start.sh` with the hook's input.
#
# When the install fails or the API does not answer, show one line that names
# the organization's network setting, in place of the plugin's own notices.
here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
status=0
sh "$here/setup.sh" 40 </dev/null >/dev/null 2>&1 || status=$?
case $status in
  3|4)
    printf '%s\n' '{"systemMessage":"Stacktrace is not connected in this Cowork task, so it does not check this task'"'"'s actions. Ask an Owner to allow api.stacktrace.ai and stacktrace.ai in Organization settings > Capabilities > Code execution."}'
    exit 0
    ;;
esac
exec sh "$here/../scripts/session_start.sh" "$@"
