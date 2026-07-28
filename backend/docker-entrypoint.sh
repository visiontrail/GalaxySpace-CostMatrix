#!/bin/sh
set -e

# Bind-mounted volumes are host-owned; make sure the non-root runtime user
# can write to them before we drop root privileges.
for dir in /app/uploads /app/data /app/logs; do
    if [ -d "$dir" ]; then
        chown -R appuser:appuser "$dir" 2>/dev/null || true
    fi
done

exec gosu appuser "$@"
