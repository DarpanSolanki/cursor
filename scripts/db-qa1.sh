#!/usr/bin/env bash
exec "$(cd "$(dirname "$0")" && pwd)/db/db-qa.sh" --env qa1 "$@"
