# Social Credit Bot — Project Todo List
*Last updated: 2026-03-31*

## ✅ Completed
- Fix BM1397/BM1398 chip naming on S19 Pro row in trash.csv
- Fix 4 zero-hashrate cloud datacenters (Ashburn, Oregon, Sydney, Frankfurt)
- Fix 486 IPC advantage — 80486DX effective clock bumped ~1.5×
- Switch hashrate score formula from log2 to sqrt for better spread
- Add /recycle and /materials commands with materials wallet DB
- Add transistor density bonus to compute_score (up to 3.5×)
- Look up missing transistor counts for 13 console/mobile chips

## 🔲 Pending

### Data
- [ ] Research real SHA-256 hashrates for CPU/GPU items and quarterly mining data for datacenter/array items (Perplexity session)

### Discord Bot
- [ ] Add confirm/decline dialog to /scrap_all and any future bulk destructive commands before executing
- [ ] Wire ministry logo into decree embed and /get_permit (embed.set_thumbnail) once hosted on GitHub
- [ ] Rework /decree as a funded announcement system — dedicated #decrees channel, single edited message (TV-channel style), sorted by credit spend

### Economy / Game Design
- [ ] Design and implement production chain economy — materials have exclusive crafting uses (overclock modules, upgrade kits etc)
- [ ] Design and implement tech level progression system (levels 1–5, civilisation arc, stat system influencing material efficiency)
- [ ] Add Car Collector cog — credit/BTC sink, vintage cars, restoration using recycled materials

### Infrastructure
- [ ] Onboard Matthew on uploading Python Trash Collector 2 to its own GitHub repo
- [ ] Plan and document full project hierarchy (see below)

---

## 🏗️ Project Hierarchy (draft)

```
MatthewCarven/
├── PythonSocialCreditDiscordBot/   ← main Discord bot (social credit + trash collector + car collector lite cog)
│   ├── game_engine.py              ← trash collector shared source of truth
│   ├── car_engine.py               ← car collector shared source of truth
│   └── cogs/
│       ├── trash_collector.py      ← full trash collector cog
│       └── car_collector.py        ← car collector cog (credit/BTC sink, lite version)
│
├── PythonTrashCollector2/          ← standalone terminal edition (rich + prompt_toolkit)
│   └── game_engine.py              ← synced copy from Social Credit Bot
│
├── CarCollectorBot/                ← NEW: standalone Discord bot, full car collector experience
│   ├── car_engine.py               ← synced copy from Social Credit Bot
│   └── car_collector.db            ← standalone DB
│
└── CarCollectorTerminal/           ← NEW: terminal edition, reads from CarCollectorBot DB
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
