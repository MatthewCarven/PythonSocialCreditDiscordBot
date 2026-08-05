# Master Project Todo List
*Last updated: 2026-08-05*

> Single source of truth for all projects under the MatthewCarven umbrella.
> Projects: **SocialCreditBot** (hub) · **Trash Collector 2** (standalone terminal) · **Car Collector 2** (standalone Discord bot) · **Car Collector 2 Standalone** (future terminal edition)

---

## ✅ Completed

### SocialCreditBot / Trash Collector Cog
- Fix BM1397/BM1398 chip naming on S19 Pro row in trash.csv
- Fix 4 zero-hashrate cloud datacenters (Ashburn, Oregon, Sydney, Frankfurt)
- Fix 486 IPC advantage — 80486DX effective clock bumped ~1.5×
- Switch hashrate score formula from log2 to sqrt for better spread
- Add /recycle and /materials commands with materials wallet DB
- Add transistor density bonus to compute_score (up to 3.5×)
- Look up missing transistor counts for 13 console/mobile chips

### Trash Collector 2 (Standalone)
- Display improvements: fmt_score() with K/M/B/T/Q suffixes, fmt_watts() with W/kW/MW/GW
- TDP table columns widened to width=10
- Compiled V1, V101, V102 Windows executables

### Car Collector 2
- Phase 1: Initial car dataset built (3,400+ entries in cars.py spanning 1899–present)
- Phase 2: Base fields enriched (power_kw, drivetrain, price_new_usd, price_used_usd, rarity)
- Full data model designed and documented (FIELD_REFERENCE.md — 250 lines)
- Core Discord bot framework (bot.py + 4 cogs: market, garage, workshop, barnfind)
- SQLite persistence layer (database.py — players, cars, market_cache tables)
- Barn find generation with gremlin system (47 gremlins + British/Italian special pool)
- Repair system (18+ actions with quality tiers: Budget/Standard/Premium)
- Upgrade system (tune, TL conversion, engine swap with family/compatible/exotic paths)
- models.py dataclasses for all game objects
- Engine standards & upgrade paths (Phase 3) — fully implemented: TL1-TL5 progression, 10+ aspiration paths, family-based swap compatibility with 3 tiers, 14 secret modifier combos, donor car pipeline, rotating parts market
- Engine swap commands sanity checked — all imports, serialization, and flows verified clean (2026-04-02)

### Car Collector 2 Standalone
- Built tkinter desktop app from scratch (2026-04-02): standalone_game.py (GUI), car_game_engine.py (logic), car_database.py (SQLite)
- Race system: 6 rally stages + head-to-head vs AI, probability-based on car stats, gremlin triggers, arcade difficulty
- Pushed to GitHub: https://github.com/MatthewCarven/CarCollector2Standalone

### SocialCreditBot — Bug Fixes
- Fix daily_state_decree task not starting — moved .start() from cog_load() to __init__() to match lottery/backup pattern (2026-04-02)

### SocialCreditBot — UI/UX Improvements
- Add confirm/decline dialogs to /scrap_all, /scrap_num, and /sell_all_parts — danger-style Views with 30s timeout, following existing SellConfirmView pattern (2026-04-02)
- Wire ministry logo into decree embed and /get_permit embed — MINISTRY_LOGO_URL constant, set_thumbnail on both embeds (2026-04-02)

### SocialCreditBot — Command Cleanup & Docs (2026-08-05)
- Removed the 21 grind-alias slash commands (/toil, /audit, /grind … /excavate) — each carried its own independent 1-hour cooldown on the same 10%-payout work scenario, so citizens could chain all 21 per hour. /work is now the single labor command; the multiplier plumbing that only existed for the aliases went with them. Frees ~21 of Discord's 100 global command slots (~75 now used)
- Rewrote /help — new chapters for Mining Operations, Markets & Trading, Property & Lottery, and RPG Adventures (the manual previously only covered the credit economy); admin chapters updated for the new /restore_backup target parameter and backup rotation
- Added ARCHITECTURE.md — project family + sync pattern, cog map, database/table inventory, the social_credit_change event contract, the two cooldown systems, code conventions, and a new-game-system checklist

### Car Collector 2 — Bug Fixes
- Fix electrical_repair crash — made gremlin_desc optional with validation, added /repair gremlin parameter to workshop cog, synced fix to standalone (2026-04-02)
- Fix scrap_num variable scope bug — to_scrap was referenced outside its defining function; refactored to pre-score in thread then confirm (2026-04-02)

---

## 🔲 Pending

### Data — Trash Collector
- [ ] Research real SHA-256 hashrates for CPU/GPU items and quarterly mining data for datacenter/array items (Matthew to use Perplexity — sources: whattomine.com, mining forums, operator quarterly reports from Foundry USA, Hut 8, Bitfarms)

### Data — Car Collector
- [ ] Continue engine dataset enrichment: engine_code, engine_family, engine_config, displacement_cc, tech_level, aspiration, fuel_type for all entries in cars.py
- [ ] Expand car dataset with more markets/countries (acknowledged as a long-running task)

### Engine Swap System — Car Collector ✅ (design resolved, implementation done 2026-04-01)
**Design decisions:**
- Primary path: buy a donor car from a regional market → `/strip_parts <car_id>` → pulls engine into inventory, scraps shell for cash
- Secondary path: `/engine_market` → rotating 4-slot parts market of common families only (SR, RB, JZ, B, K, EJ, 4G, LS, Coyote, Windsor, 4A, 13B). Refreshes every 48 hours.
- Rare/exotic engines (RB26DETT, 2JZ-GTE, etc.) only come from donor cars in regional markets — regional gating is natural
- Engine condition on strip = average of donor car's fluids_condition + ignition_condition
- Shell scrap cash scales with rarity × chassis_condition (Common $50–300, Legendary up to $5,000)
- `/swap <car_id> <engine_id> [full|budget]` installs engine, applies its condition to car's fluids/ignition
- Secret modifier system fires on eligible combos (SR in Nissan, LS in Miata, etc.)
- **Implemented:** StoredEngine dataclass, engine_inventory DB table, engine_market_cache table, /strip_parts, /swap, /engines, /engine_market, /buy_engine

### Discord Bot — SocialCreditBot
- [x] ~~Add confirm/decline dialog to /scrap_all and bulk destructive commands~~ — done (2026-04-02)
- [x] ~~Wire ministry logo into decree embed and /get_permit (embed.set_thumbnail)~~ — done (2026-04-02)
- [ ] Rework /decree as a funded announcement system — dedicated #decrees channel, single edited message (TV-channel style), sorted by credit spend
- [x] ~~Fix atomicity gap in /sell_all_parts~~ — done (2026-08-04): new `MiningDB.sell_hardware_bulk` deletes parts and credits BTC in one transaction, and aborts the whole sale if the inventory changed since the quote
- [x] ~~Clean up double-message UX on /scrap_all and /scrap_num~~ — done (2026-08-04): confirm views now edit the original prompt in place via `edit_original_response`; timed-out prompts grey their buttons out

### Code Review Findings (2026-08-04 sweep) — all fixed same day
- [x] ~~**BUG:** main.py called `process_application_commands` (Pycord API, not discord.py) → AttributeError traceback on every guild slash command~~ — line deleted; the CommandTree handles slash commands on its own
- [x] ~~**EXPLOIT:** /sell_all_parts double-payout (stale confirm prompts / double-click paid full BTC for already-deleted parts)~~ — all confirm views now share `_ConfirmViewBase` with a `claim()` double-click guard, and selling uses atomic `sell_hardware_bulk` which aborts on any inventory mismatch. Verified with a replay-attack test against a scratch DB
- [x] ~~**REGRESSION:** compute_score defaults 0→1 made blank `word_bits` an 8× score cut~~ — unknown word size now defaults to 8 (ratio ×1.0, same as the old fallback), unknown cores to 1, unknown clock stays 1; dead inline fallbacks removed
- [x] ~~Commit pending fixes (`btc_wallet` rename, confirm views, sync.py) and run sync --apply~~ — committed and synced (2026-08-04)
- [x] ~~sync.py UnicodeEncodeError on cp1252 consoles (partial-sync risk in --apply)~~ — stdout reconfigured to UTF-8 at startup
- [x] ~~Backup coverage gap (only social_credit.db; no rotation; restore validated filename only)~~ — BackupManager now backs up all DBs, prunes to the newest 30 per DB (pre-restore snapshots exempt), validates SQLite magic bytes on restore, and snapshots the current DB before overwriting. NOTE: first run will prune the ~135 oldest social_credit backups
- [x] ~~Git hygiene (tracked rpg.db churn, duplicate .gitignore lines, backups/ half-ignored)~~ — rpg.db untracked, .gitignore rewritten, backups/ ignored wholesale
- [x] ~~Add requirements.txt~~ — discord.py>=2.3 + python-dotenv
- [x] ~~main.py robustness~~ — DISCORD_TOKEN check added; bot now chdirs to its own folder at startup so cogs/ and *.db paths work from any launch directory. (Global `tree.sync()` on every boot left as-is — see remaining item below)
- [x] ~~`remove_btc` TOCTOU race~~ — check+decrement now a single `UPDATE ... WHERE balance >= ?`; overdraw attempt verified to fail in test
- [x] ~~Confirm-view timeout UX (expired prompts still look clickable)~~ — views hold their message ref and grey out buttons on timeout
- [x] ~~Stray `trash3..csv`~~ — moved to old/trash3.csv
- [ ] Consider smarter slash-command syncing — `tree.sync()` global-syncs on every boot (rate-limit risk, slow propagation); fine at current scale, revisit if the bot joins more guilds or command count grows

### Economy / Game Design — Cross-Project
- [ ] Design and implement production chain economy — materials have exclusive crafting uses (overclock modules, upgrade kits etc)
- [ ] Design and implement tech level progression system (levels 1–5, civilisation arc, stat system influencing material efficiency)
- [ ] Add Car Collector cog to SocialCreditBot — credit/BTC sink, vintage cars, restoration using recycled materials (lite version of standalone Car Collector)
- [ ] Connect materials economy across projects: gold, copper, aluminium, PCB from /recycle flow into car restoration

### Trash Collector 2 — Standalone Features
- [ ] Implement `scrap` command: dismantle rigs/parts for materials (aluminium from heatsinks scales with TDP, copper heatpipes, gold connector plating scales with pin count/rarity)
- [ ] Build `talkie_toaster` rig (reserved by Matthew — Red Dwarf reference, built around IoT Smart Toaster Controller part)
- [ ] Plan "Trash Collector Professional" edition (name reserved, no details yet)

### Infrastructure
- [x] ~~Onboard Matthew on uploading Python Trash Collector 2 to its own GitHub repo~~ — pushed to https://github.com/MatthewCarven/PythonTrashCollector (2026-04-01)
- [x] ~~Car Collector 2 Standalone — build and push to GitHub~~ — pushed to https://github.com/MatthewCarven/CarCollector2Standalone (2026-04-02)
- [ ] Finalise and implement full project hierarchy (see below)
- [ ] Pre-requisite: extract trash collector logic out of trash_collector.py cog into a standalone game_engine.py before the sync pattern can be established
- [ ] Pre-requisite: extract car collector logic out of its cogs into a standalone car_engine.py before the sync pattern can be established
- [ ] Set up game_engine.py sync pattern: SocialCreditBot is source of truth → synced to Trash Collector 2
- [ ] Set up car_engine.py sync pattern: SocialCreditBot is source of truth → synced to Car Collector Bot and Car Collector Terminal
- [x] ~~Create Car Collector 2 Standalone~~ — built and pushed to GitHub (2026-04-02)
- [ ] Evaluate `aiosqlite` vs `asyncio.to_thread` for DB layer — SQLite has a connection-per-thread constraint that `to_thread` needs to respect; `aiosqlite` handles this natively. Benchmark both approaches under realistic concurrent load (multiple cogs hitting the DB simultaneously) and decide which pattern to standardise across all projects

---

## 🏗️ Project Hierarchy (draft)

```
MatthewCarven/
├── PythonSocialCreditDiscordBot/   ← main Discord bot (hub for all game systems)
│   ├── game_engine.py              ← trash collector shared source of truth
│   ├── car_engine.py               ← car collector shared source of truth
│   └── cogs/
│       ├── trash_collector.py      ← full trash collector cog
│       └── car_collector.py        ← car collector cog (credit/BTC sink, lite version)
│
├── PythonTrashCollector2/          ← standalone terminal edition (rich + prompt_toolkit)
│   └── game_engine.py              ← synced copy from Social Credit Bot
│
├── CarCollectorBot/                ← standalone Discord bot, full car collector experience
│   ├── car_engine.py               ← synced copy from Social Credit Bot
│   └── car_collector.db            ← standalone DB
│
└── CarCollectorTerminal/           ← terminal edition, reads from CarCollectorBot DB
    └── car_engine.py               ← synced copy from Social Credit Bot
```

### Design principles
- Each project has its own repo and entrance vector
- **car_engine.py** lives in Social Credit Bot and is the single source of truth — synced to all other projects
- **game_engine.py** same pattern for trash collector logic
- Car Collector cog in Social Credit Bot = lite credit sink version (no standalone DB needed)
- Car Collector standalone Bot = full experience with its own DB and economy
- Car Collector Terminal reads from the standalone bot's DB (same pattern as Trash Collector 2)
- Materials (gold, copper, aluminium, PCB) from /recycle flow into car restoration across all versions
- Discord bots and terminal editions share the same DB schema where possible

---

## 📌 Reserved Names & Ideas
*Do not suggest these as new ideas — they are already Matthew's plans.*

- `talkie_toaster` rig (Trash Collector)
- "Trash Collector Professional" edition
- `Fermented-Baby` interior odour (Car Collector)
- British/Italian 1960s–70s gremlin pool (Car Collector)
