#!/usr/bin/env bash
# Alias kept for muscle-memory: test-map.sh → sync-test-intelligence.sh
# (documented in OPS-INDEX; sync-test-intelligence.sh header references this alias)
exec bash "$(cd "$(dirname "$0")" && pwd)/sync-test-intelligence.sh" "$@"
