<!-- Thanks for opening a PR. The checklist below mirrors how Riprap
     was kept stable through hackathon week. -->

## Summary

<!-- One paragraph: what changed, and why. Reference issues with #N. -->

## Tested against

- [ ] Local dev server (`uvicorn web.main:app`)
- [ ] Local Docker (`docker compose up`)
- [ ] Modal deployment
- [ ] Mac Mini / self-hosted GPU inference

## Smoke probe

<!-- Paste the tail of `scripts/probe_cities_smoke.py` output against a
     local server. The PR should not be merged unless every deployment
     passes. -->

```
uv run python scripts/probe_cities_smoke.py http://127.0.0.1:7860
```

## Energy-ledger sanity check

<!-- If this PR touches inference, app/emissions.py, app/llm.py, or
     app/power_mac.py: paste the n_measured / n_calls ratio and
     confirm hardware label. -->

## Checklist

- [ ] No regression in `app/`, `web/`, or `services/` logic
      (typo-only edits OK).
- [ ] Docs updated (`README.md`, relevant `docs/*.md`) if public
      surface changed.
- [ ] `CHANGELOG.md` entry under `[Unreleased]` with the right
      `Added` / `Changed` / `Fixed` bucket.
- [ ] Conventional-commit prefix on the squash title
      (`feat:` / `fix:` / `docs:` / `chore:` / `build:`).
