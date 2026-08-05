# Architecture

SocialCreditBot is a multi-game Discord bot built on **discord.py 2.x**. One bot
process hosts several loosely-coupled game systems (cogs) that share a social
credit economy. It is also the **hub of a project family**: some of its modules
are the source of truth for sibling projects and are copied out with `sync.py`.

```
main.py                     ← entry point: bot class, cog loader, penalty listeners
│
├── cogs/                   ← one file per game system, auto-loaded at startup
│   ├── social_credit.py    ← core economy: credits, work, heist, coinflip, /help
│   ├── trash_collector.py  ← mining game: scavenge → build rigs → mine BTC
│   ├── lottery.py          ← daily State lottery + slush fund viewer
│   ├── real_estate.py      ← procedurally generated world map, land claiming
│   ├── rpg.py              ← player-facing RPG (maps, combat, inventory)
│   ├── rpg_admin.py        ← RPG world-building commands
│   ├── word_manager.py     ← banned/praised words, designated bot channel
│   ├── perm_manager.py     ← assigns Discord roles from credit tiers
│   └── backup_manager.py   ← daily DB backups, rotation, restore command
│
├── views/                  ← large discord.ui.View classes (rendering-heavy)
│   ├── real_estate_views.py  (PIL + opensimplex map rendering/navigation)
│   └── rpg_views.py          (PIL map rendering, combat/inventory UI)
│
├── game_engine.py          ← ★ pure game logic for the trash collector (no Discord)
├── mining_db.py            ← ★ SQLite layer for the mining game
├── database.py             ← SQLite layer for the credit economy (CreditDB)
├── rpg_db.py               ← SQLite layer for the RPG
├── messages.py             ← randomized flavor-text pools
├── sync.py                 ← copies ★ files to sibling projects (see below)
│
├── trash.csv / trash2.csv  ← hardware datasets loaded by game_engine.py
├── tiers.json              ← credit tier names + thresholds
└── tools/                  ← offline dataset-building scripts (not used at runtime)
```

## The project family and the sync pattern

This repo is the source of truth for shared modules. `sync.py` (dry-run by
default, `--apply` to copy) pushes them to sibling folders under the same
parent directory:

| File | Synced to |
|---|---|
| `game_engine.py` | `Python Trash Colllector 2` (standalone terminal edition) |
| `mining_db.py` | `Python Trash Colllector 2` |
| `car_engine.py` (future) | `Python Car Collector 2` (+ Standalone) |

**Rule:** never edit the synced copies in the sibling projects — edit here and
run `python sync.py --apply`. This is why `game_engine.py` must stay free of
Discord imports: the terminal edition imports the exact same file.

## Startup sequence

1. `main.py` chdirs to its own folder (so relative paths to cogs/DBs always work),
   loads `.env`, and requires `DISCORD_TOKEN`.
2. `MyBot.setup_hook()` loads every `cogs/*.py` as an extension. A cog that
   fails to import is skipped with a console message — the rest still load.
3. `bot.tree.sync()` pushes the global slash-command set to Discord. This also
   *removes* commands that no longer exist in code (propagation can take up to
   an hour for global commands).
4. Task loops (`daily_backup`, `daily_state_decree`, `daily_drawing`) are
   started from each cog's `__init__` and gated on `wait_until_ready()`.

## The economy: how systems connect

- **Credits** (social standing) live in `social_credit.db` and are earned
  passively per message, via `/work`, `/daily_ration`, gambling, and praised
  words. Fines flow into a per-guild **slush fund**.
- **BTC** lives in `mining.db` and is earned by mining rigs. The BTC exchange
  (`/buy_btc`, `/sell_btc`) is the bridge between the two currencies.
- **Materials** (gold, copper, aluminium, PCB from `/recycle`) are the planned
  bridge into car restoration (see TODO.md's cross-project economy items).
- Land claims on the world map are paid in credits.

### The `social_credit_change` event

Whenever any code changes a citizen's credits, it dispatches
`self.bot.dispatch("social_credit_change", member, new_score)`.
`perm_manager.py` listens for it and swaps the member's tier role (from
`tiers.json`) when they cross a threshold. If you add a new credit
source/sink, dispatch this event or roles will drift.

### The designated bot channel

`word_manager.py` lets admins set one output channel per guild
(`guild_settings.output_channel_id`). `main.py` enforces it both ways:
slash commands *outside* the channel and chatter *inside* it each cost the
citizen 1 credit (added to the slush fund).

## Databases

One SQLite file per game system; every accessor opens a short-lived
connection per call, so files are never held open. All tables key on
`(user_id, guild_id)` — data is **per-guild**.

| File | Layer | Tables (abridged) |
|---|---|---|
| `social_credit.db` | `database.CreditDB` | economy, banned_words, praised_words, guild_settings (slush fund, bot channel), lottery_tickets |
| `mining.db` | `mining_db.MiningDB` | hardware_inventory, mining_rigs, rig_components, btc_wallet, btc_market, mining_cooldowns, parts_market, permits, cprm_pool/history, materials_wallet |
| `rpg.db` | `rpg_db` | maps, tiles, portals, players, items, player_inventory, chests, npcs, dialog_nodes, enemy_types, map_enemies, combat |
| `real_estate_bot.db` | inline in cog/views | world_map, users, last_location |

**Transactions:** anything that moves value in two steps must be one
transaction. `MiningDB.sell_hardware_bulk` is the reference pattern — it
deletes inventory rows and credits BTC atomically, and aborts entirely if
the rowcount doesn't match (prevents pay-for-nothing dupes). Balance checks
belong in the `WHERE` clause (`UPDATE … WHERE balance >= ?`), not in a
separate read.

**Backups:** `backup_manager.py` snapshots every DB daily into `backups/`,
keeps the newest 30 per database, and `/restore_backup` validates SQLite
magic bytes and snapshots the current file before overwriting.

## Cooldowns — two different systems

| Mechanism | Where | Survives restart? | Used by |
|---|---|---|---|
| `@app_commands.checks.cooldown` | in-memory, per command | ❌ | `/work`, `/heist`, `/coinflip`, `/daily_ration` |
| `mining_cooldowns` table | `mining.db` | ✅ | `/scavenge`, `/mine` |

Because decorator cooldowns are **per command**, duplicate commands sharing
one implementation each get their own timer. That is why the 21 grind-alias
commands (`/toil`, `/audit`, …) were removed — they were 21 independent
1-hour timers on the same payout. Don't reintroduce aliases; if two commands
should share a limit, use a DB-backed cooldown with a shared key.

Note: Discord caps a bot at **100 global slash commands**. Post-cleanup we
sit around 75 — mind the budget when adding command families.

## Conventions

- **Heavy work off the event loop:** DB loops and scoring over large
  inventories run via `await asyncio.to_thread(...)`. PIL map rendering in
  views does the same.
- **Destructive actions get a confirm View:** subclass `_ConfirmViewBase`
  (in `cogs/trash_collector.py`). It provides the owner check, a
  double-click guard (`claim()`), `disable_all()`, and greys out buttons on
  timeout. Confirm results edit the prompt in place — never post a second
  message under a live prompt.
- **Embeds:** in-universe Ministry voice, rarity colors from
  `RARITY_COLOR`, `MINISTRY_LOGO_URL` thumbnail on official notices.
- **Admin gating:** `@app_commands.default_permissions(...)` on the command
  (manage_roles for economy admin, administrator for RPG admin).
- **Cooldown errors:** `SocialCredit.cog_app_command_error` catches
  `CommandOnCooldown` for that cog; the trash collector reports cooldowns
  inline per command.
- **/help:** the interactive manual lives in `HelpDropdown`
  (`cogs/social_credit.py`). **When you add or remove player-facing
  commands, update the matching chapter** — it is hand-written, not
  generated.

## Adding a new game system (checklist)

1. Create `cogs/<name>.py` with a `commands.Cog` subclass and
   `async def setup(bot)` — it will be auto-loaded.
2. Give it its own `<name>.db` + accessor module if it has state; add the
   filename to `DB_FILES` in `cogs/backup_manager.py`.
3. Dispatch `social_credit_change` if it touches credits.
4. Add a chapter to `HelpDropdown` and note the command budget.
5. If its core logic should be shared with a standalone edition, keep the
   logic in a Discord-free `<name>_engine.py` and add a rule to `sync.py`.

## Running

```
pip install -r requirements.txt
# .env file containing: DISCORD_TOKEN=<token>
python main.py
```

Requires the **message content** and **server members** privileged intents
(enabled in the Discord developer portal). The bot creates any missing
`.db` files on first run.
