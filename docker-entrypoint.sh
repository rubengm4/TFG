#!/bin/sh
set -e
# Named volumes mount as root:root; app runs as appuser (see Dockerfile).
mkdir -p /app/media /app/static
chown -R appuser:appuser /app/media /app/static
exec /usr/sbin/runuser -u appuser -- "$@"
