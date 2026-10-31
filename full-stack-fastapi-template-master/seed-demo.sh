#!/usr/bin/env bash
set -e

echo "=== Seeding Brightloop Phase 2 Catalog ==="
cd "$(dirname "$0")/backend"
uv run python -m scripts.seed
echo "=== Seeding Complete ==="

