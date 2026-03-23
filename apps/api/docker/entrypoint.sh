#!/bin/sh
set -eu

exec /workspace/.venv/bin/python /workspace/apps/api/docker/entrypoint.py
