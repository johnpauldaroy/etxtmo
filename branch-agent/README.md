# branch-agent

Branch-side service that bridges central TextBlast queue with local GSM/Gammu storage.

## Send modes

- Production: point `GAMMU_DB_PATH` to a real Gammu SMSD database and run `gammu-smsd`.
  The agent writes to `outbox`; Gammu performs actual modem send and writes `sentitems`.
- Local/dev: set `SIMULATE_SEND=true` to let the agent mark outbox rows as sent
  (no real modem delivery).

## Quick start

```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
copy .env.example .env
python -m agent.main
```
