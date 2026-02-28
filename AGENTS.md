# Repository Guidelines

## Project Structure & Module Organization
- `bot.py`: Main Discord bot runtime, event handlers, OpenRouter integration, cooldowns, and owner override logic.
- `predefined_responses.json`: Editable exact-match message-to-response map.
- `requirements.txt`: Python dependencies.
- `.env.example`: Template for runtime configuration.
- `README.md`: Setup and usage instructions.
- No `tests/` directory exists yet; add tests under `tests/` when introduced.

## Build, Test, and Development Commands
- `python3 -m venv .venv`: Create local virtual environment.
- `source .venv/bin/activate`: Activate environment (macOS/Linux).
- `pip install -r requirements.txt`: Install dependencies.
- `python bot.py`: Run the bot locally.
- `python3 -m py_compile bot.py`: Quick syntax validation before commits.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation.
- Use `snake_case` for variables/functions and `UPPER_SNAKE_CASE` for constants/env-derived settings.
- Keep functions focused and short; prefer small helpers for message parsing and routing.
- Use type hints for public/internal helpers where practical.
- Logging should be concise and actionable (`logger.info`, `logger.error`) without leaking secrets.

## Testing Guidelines
- Current minimum check: `python3 -m py_compile bot.py`.
- When adding tests, use `pytest` and place files in `tests/` with names like `test_<feature>.py`.
- Prioritize tests for:
  - channel filtering (`TARGET_CHANNEL_ID`)
  - owner `!` echo and DM relay behavior
  - predefined response matching
  - cooldown and token-exhaustion handling

## Commit & Pull Request Guidelines
- Use clear, imperative commit messages (example: `Add owner DM relay to target channel`).
- Keep commits scoped to one change area when possible.
- PRs should include:
  - what changed and why
  - environment/config updates (`.env.example`, README)
  - verification steps and command output summary
- If behavior changes, include a short before/after example message flow.

## Security & Configuration Tips
- Never commit `.env` or API keys.
- Rotate credentials immediately if exposed.
- Keep `allowed_mentions` restricted to avoid unwanted mass mentions.
- Use low memory/token settings for faster and cheaper responses when operating on free models.
