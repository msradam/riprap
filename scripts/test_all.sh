#!/usr/bin/env bash
# Offline test stack: Python tests, then the Vitest UI tests.
# Browser tests live behind `pnpm test:e2e` in web/sveltekit, which
# starts its own server (playwright.config.ts), as does CI.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run pytest -q
(cd web/sveltekit && pnpm test:unit)
