#!/usr/bin/env bash
# Offline test stack: Python tests, then the Vitest UI tests.
# Browser tests live behind `pnpm test:e2e` in web/sveltekit and need a
# running server (.github/CONTRIBUTING.md); CI runs ruff and pytest only.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run pytest -q
(cd web/sveltekit && pnpm test:unit)
