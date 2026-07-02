#!/usr/bin/env bash
# sessionStart wrapper — full KG sync (not --fast).
exec "$(dirname "$0")/kg-session-watermark.sh" sessionStart
