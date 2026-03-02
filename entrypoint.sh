#!/bin/sh
# Ensure /data is writable by botuser (mounted volumes inherit host permissions)
chown -R botuser:botuser /data
exec gosu botuser python main.py "$@"
