# GitHub Copilot Instructions for Python SocialCreditBot

This repository houses a very small Discord bot implemented in a single `main.py` file. The goal of these instructions is to get an AI agent productive quickly by describing the architecture, patterns and conventions used here.

## Big Picture

- **Single-module bot**: All logic lives in `main.py`. There is no package structure, only the `CreditDB` class and a slash command defined on a `discord.Bot` instance (named `bot`).
- **Data persistence**: A lightweight local [SQLite](https://www.sqlite.org) database (`social_credit.db` by default) is used to store `social_credit` scores keyed by `user_id` and `guild_id`. The `CreditDB` class handles creation and simple CRUD operations.
- **Discord integration**: Uses `discord.py` / `discord` library with application commands (`app_commands`). The bot is expected to be started by running `main.py` after setting up the `bot` object and providing a token (not shown but typical in a `if __name__ == "__main__":` section). The slash command defined is `/profile`.

## Key Components

- `CreditDB` (class in `main.py`)
  - Constructor accepts optional `db_path`.
  - `_create_table()` ensures the `economy` table exists.
  - `get_credit(user_id, guild_id)` returns the current score (default `0.0`).
  - `update_credit(user_id, guild_id, amount)` increments/decrements score via `ON CONFLICT` SQL.

- `get_social_status(xp)` helper function
  - Translates a numeric score into a tier name, level and the XP needed for the next tier.
  - Handles positive and negative scores separately using fixed thresholds and logarithmic scaling for 0&#8211;10 levels.

- `/profile` slash command
  - Retrieves the target member's score via `db.get_credit`.
  - Calculates tier and progress with `get_social_status`.
  - Constructs an `Embed` with color based on positive/negative balance.

## Running / Developer Workflow

1. **Dependencies**: install `discord.py` (or whichever fork provides `discord` and `app_commands`).
   ```powershell
   python -m pip install -U discord.py
   ```
   There are no tests or build steps in this repo.

2. **Bot token and startup**:
   - The code is incomplete; typically you would create a `bot = discord.Bot()` at the top, then at bottom call `bot.run(TOKEN)` using an environment variable or config file.
   - Ensure the bot is invited to your server with `applications.commands` scope.

3. **Database file**:
   - `social_credit.db` is created automatically in the working directory. No migrations.
   - Delete the file to reset all data.

4. **Debugging**:
   - Add print/log statements to `profile` command or use a debugger attached to `main.py`.
   - Use `sqlite3` CLI to inspect the DB (`sqlite3 social_credit.db` then `SELECT * FROM economy;`).

## Conventions & Patterns

- **Single file coding**: expect most edits to happen in `main.py`.
- **Simple DB abstraction**: the `CreditDB` class uses context managers (`with sqlite3.connect`) for thread-safety.
- **String formatting**: use f-strings and embed formatting as shown in the `profile` command.
- **Tier names**: hard-coded arrays in `get_social_status`; tiers are 13 (10 positive, 3 negative).

## External Dependencies & Integration

- **SQLite**: built into Python, no additional drivers.
- **Discord API**: the bot uses slash commands and embeds; the code assumes `discord.Member` and `discord.Interaction` objects provided by `discord.py`.

> ⚠️ This repository currently lacks a `requirements.txt` or bot initialization. Before running, supply the missing pieces yourself or reach out to the maintainer.

## Editing Guidance for Copilot

- When modifying or adding commands, follow the same structure: calculate the necessary data first, then build an `Embed` and send via `interaction.response.send_message()`.
- For any new database operations, extend `CreditDB` with methods and use SQLite's `ON CONFLICT` pattern as shown.
- Maintain use of helper functions (like `get_social_status`) for calculable business logic; they should remain pure functions.
- Avoid global mutable state except for the singleton `db` instance expected in `main.py`.

---

If any of the above is unclear or incomplete, please let me know what additional details would help make the instructions more useful for future AI agents.