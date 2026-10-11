#!/bin/sh
set -eu
# Run outside the signing-key directory; no credentials are copied into the kit.
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$SCRIPT_DIR/build_pass.py" "$@"
