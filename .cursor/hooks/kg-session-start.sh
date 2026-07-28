#!/usr/bin/env bash
# sessionStart wrapper — lean path only.
exec "$(dirname "$0")/kg-session-watermark.sh" workspaceOpen
