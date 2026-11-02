#!/usr/bin/env bash
# Maze Runner launcher: creates/uses a local venv, installs deps, runs the game.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
    echo "Creating virtualenv ..."
    python3 -m venv .venv
    .venv/bin/pip install --quiet --upgrade pip
fi

echo "Installing dependencies (pygame, matplotlib) ..."
.venv/bin/pip install --quiet -r requirements.txt

echo "Starting Maze Runner ..."
exec .venv/bin/python -m game.main "$@"
