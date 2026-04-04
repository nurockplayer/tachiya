#!/bin/zsh

set -euo pipefail

exec claude --max-turns 5 "$@"
