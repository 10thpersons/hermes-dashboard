# affiliate-bot (source snapshot)

Threads + Shopee affiliate pipeline used by `backend/routers/affiliate.py`.

Included: `bot/` (source) and `tests/`. Excluded on purpose: state, drafts, research corpus/bakeoff data, env files, caches, persona docs.

## Packaging limitations (not portable as-is)
- The router defaults to `AFFILIATE_BOT_DIR=/root/.hermes/work/affiliate-bot`. Point it at a checkout of this directory to use this copy.
- `bot/config.py` reads credentials from hard-coded `/root/.hermes/.env` paths (and `<bot dir>/.env`). No secrets are in this repo.
- `bot/writer.py` expects `research/manglish_style_guide.md`, which is not included. `state/` and `drafts/` are created at runtime.
- Needs `requests` (pinned in `backend/requirements.txt`). Tests are plain scripts: `python tests/test_risk.py`.
- Snapshot only; known issues are not fixed here.
