import sqlite3
import json
import uuid
import random

DB_PATH = 'rpg.db'

TILE_PASSABLE = {
    'grass':    True,
    'sand':     True,
    'floor':    True,
    'door':     True,
    'portal':   True,
    'path':     True,
    'stone':    True,
    'water':    False,
    'wall':     False,
    'mountain': False,
    'tree':     False,
    'void':     False,
    'chest':    False,
}

# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

def init_db():
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS maps (
                id         TEXT PRIMARY KEY,
                server_id  TEXT NOT NULL,
                name       TEXT NOT NULL,
                width      INTEGER NOT NULL,
                height     INTEGER NOT NULL,
                is_default INTEGER DEFAULT 0
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS tiles (
                map_id    TEXT NOT NULL,
                x         INTEGER NOT NULL,
                y         INTEGER NOT NULL,
                tile_type TEXT NOT NULL DEFAULT 'floor',
                PRIMARY KEY (map_id, x, y)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS portals (
                map_id     TEXT NOT NULL,
                x          INTEGER NOT NULL,
                y          INTEGER NOT NULL,
                target_map TEXT NOT NULL,
                target_x   INTEGER NOT NULL,
                target_y   INTEGER NOT NULL,
                label      TEXT DEFAULT 'Portal',
                PRIMARY KEY (map_id, x, y)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS players (
                user_id   TEXT NOT NULL,
                server_id TEXT NOT NULL,
                map_id    TEXT,
                x         INTEGER DEFAULT 0,
                y         INTEGER DEFAULT 0,
                hp        INTEGER DEFAULT 20,
                max_hp    INTEGER DEFAULT 20,
                attack    INTEGER DEFAULT 5,
                defence   INTEGER DEFAULT 2,
                level     INTEGER DEFAULT 1,
                xp        INTEGER DEFAULT 0,
                gold      INTEGER DEFAULT 10,
                PRIMARY KEY (user_id, server_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                description TEXT,
                item_type   TEXT NOT NULL,
                value       INTEGER DEFAULT 0,
                effect      TEXT DEFAULT '{}'
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS player_inventory (
                user_id   TEXT NOT NULL,
                server_id TEXT NOT NULL,
                item_id   TEXT NOT NULL,
                quantity  INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, server_id, item_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS map_items (
                id       TEXT PRIMARY KEY,
                map_id   TEXT NOT NULL,
                x        INTEGER NOT NULL,
                y        INTEGER NOT NULL,
                item_id  TEXT NOT NULL,
                quantity INTEGER DEFAULT 1
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS chests (
                map_id   TEXT NOT NULL,
                x        INTEGER NOT NULL,
                y        INTEGER NOT NULL,
                contents TEXT DEFAULT '[]',
                opened   INTEGER DEFAULT 0,
                PRIMARY KEY (map_id, x, y)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS npcs (
                id          TEXT PRIMARY KEY,
                map_id      TEXT NOT NULL,
                x           INTEGER NOT NULL,
                y           INTEGER NOT NULL,
                name        TEXT NOT NULL,
                sprite      TEXT DEFAULT '🧑',
                root_dialog TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS dialog_nodes (
                id      TEXT PRIMARY KEY,
                text    TEXT NOT NULL,
                choices TEXT DEFAULT '[]'
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS enemy_types (
                id         TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                sprite     TEXT DEFAULT '👾',
                hp         INTEGER DEFAULT 10,
                attack     INTEGER DEFAULT 3,
                defence    INTEGER DEFAULT 1,
                xp_reward  INTEGER DEFAULT 5,
                gold_min   INTEGER DEFAULT 0,
                gold_max   INTEGER DEFAULT 3,
                loot_table TEXT DEFAULT '[]'
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS map_enemies (
                id         TEXT PRIMARY KEY,
                map_id     TEXT NOT NULL,
                x          INTEGER NOT NULL,
                y          INTEGER NOT NULL,
                enemy_type TEXT NOT NULL,
                current_hp INTEGER NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS combat (
                user_id   TEXT NOT NULL,
                server_id TEXT NOT NULL,
                enemy_id  TEXT NOT NULL,
                PRIMARY KEY (user_id, server_id)
            )
        """)

        con.commit()

    _seed_items()
    _seed_enemies()


def _seed_items():
    defaults = [
        ('health_potion',  'Health Potion',  'Restores 20 HP',           'consumable', 10,  '{"heal": 20}'),
        ('bread',          'Bread',          'Restores 5 HP',            'consumable',  3,  '{"heal": 5}'),
        ('elixir',         'Elixir',         'Fully restores HP',        'consumable', 50,  '{"heal": 9999}'),
        ('iron_sword',     'Iron Sword',     '+3 attack',                'weapon',     50,  '{"damage_bonus": 3}'),
        ('steel_sword',    'Steel Sword',    '+6 attack',                'weapon',    120,  '{"damage_bonus": 6}'),
        ('leather_armour', 'Leather Armour', '+2 defence',               'armour',    40,   '{"defence_bonus": 2}'),
        ('chain_mail',     'Chain Mail',     '+5 defence',               'armour',   100,   '{"defence_bonus": 5}'),
        ('gold_key',       'Gold Key',       'Opens a gold locked door', 'key',        25,  '{"key_for": "gold_door"}'),
    ]
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.executemany(
            "INSERT OR IGNORE INTO items (id, name, description, item_type, value, effect) VALUES (?,?,?,?,?,?)",
            defaults
        )
        con.commit()


def _seed_enemies():
    defaults = [
        ('slime',    'Slime',    '🟢',  8,  2, 0,  3,  0, 2,  '[{"item_id":"bread","chance":0.3}]'),
        ('goblin',   'Goblin',   '👺', 12,  4, 1,  8,  1, 5,  '[{"item_id":"health_potion","chance":0.2}]'),
        ('orc',      'Orc',      '👹', 20,  6, 2, 15,  2, 8,  '[{"item_id":"iron_sword","chance":0.1}]'),
        ('skeleton', 'Skeleton', '💀', 15,  5, 3, 12,  1, 6,  '[{"item_id":"gold_key","chance":0.05}]'),
        ('dragon',   'Dragon',   '🐉', 50, 12, 5, 100,20,50,  '[{"item_id":"steel_sword","chance":0.5},{"item_id":"elixir","chance":0.3}]'),
    ]
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.executemany(
            "INSERT OR IGNORE INTO enemy_types (id,name,sprite,hp,attack,defence,xp_reward,gold_min,gold_max,loot_table) VALUES (?,?,?,?,?,?,?,?,?,?)",
            defaults
        )
        con.commit()

# ---------------------------------------------------------------------------
# Player helpers
# ---------------------------------------------------------------------------

def get_player(user_id, server_id):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM players WHERE user_id=? AND server_id=?", (str(user_id), str(server_id)))
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))


def create_player(user_id, server_id, map_id, x, y):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO players (user_id,server_id,map_id,x,y) VALUES (?,?,?,?,?)",
            (str(user_id), str(server_id), map_id, x, y)
        )
        con.commit()


def save_player_pos(user_id, server_id, map_id, x, y):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(
            "UPDATE players SET map_id=?,x=?,y=? WHERE user_id=? AND server_id=?",
            (map_id, x, y, str(user_id), str(server_id))
        )
        con.commit()


def update_player_hp(user_id, server_id, hp):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(
            "UPDATE players SET hp=? WHERE user_id=? AND server_id=?",
            (hp, str(user_id), str(server_id))
        )
        con.commit()


def get_effective_stats(user_id, server_id):
    """Returns (attack, defence, hp, max_hp) accounting for inventory."""
    p = get_player(user_id, server_id)
    if not p:
        return 5, 2, 20, 20

    best_weapon  = 0
    total_armour = 0

    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("""
            SELECT i.item_type, i.effect FROM player_inventory pi
            JOIN items i ON pi.item_id = i.id
            WHERE pi.user_id=? AND pi.server_id=?
        """, (str(user_id), str(server_id)))
        for item_type, effect_json in cur.fetchall():
            eff = json.loads(effect_json)
            if item_type == 'weapon':
                best_weapon = max(best_weapon, eff.get('damage_bonus', 0))
            elif item_type == 'armour':
                total_armour += eff.get('defence_bonus', 0)

    return (
        p['attack']  + best_weapon,
        p['defence'] + total_armour,
        p['hp'],
        p['max_hp'],
    )


def add_xp(user_id, server_id, amount):
    """Add XP and handle level-ups. Returns (new_level, levelled_up)."""
    p = get_player(user_id, server_id)
    if not p:
        return 1, False
    new_xp    = p['xp'] + amount
    new_level = p['level']
    levelled  = False
    xp_needed = new_level * 20
    while new_xp >= xp_needed:
        new_xp   -= xp_needed
        new_level += 1
        levelled   = True
        xp_needed  = new_level * 20

    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        if levelled:
            cur.execute("""
                UPDATE players SET xp=?,level=?,max_hp=max_hp+5,hp=max_hp+5,attack=attack+1,defence=defence+1
                WHERE user_id=? AND server_id=?
            """, (new_xp, new_level, str(user_id), str(server_id)))
        else:
            cur.execute(
                "UPDATE players SET xp=? WHERE user_id=? AND server_id=?",
                (new_xp, str(user_id), str(server_id))
            )
        con.commit()
    return new_level, levelled

# ---------------------------------------------------------------------------
# Inventory helpers
# ---------------------------------------------------------------------------

def get_inventory(user_id, server_id):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("""
            SELECT i.id, i.name, i.description, i.item_type, i.value, i.effect, pi.quantity
            FROM player_inventory pi JOIN items i ON pi.item_id = i.id
            WHERE pi.user_id=? AND pi.server_id=?
            ORDER BY i.item_type, i.name
        """, (str(user_id), str(server_id)))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def add_to_inventory(user_id, server_id, item_id, quantity=1):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("""
            INSERT INTO player_inventory (user_id, server_id, item_id, quantity)
            VALUES (?,?,?,?)
            ON CONFLICT(user_id,server_id,item_id) DO UPDATE SET quantity=quantity+?
        """, (str(user_id), str(server_id), item_id, quantity, quantity))
        con.commit()


def remove_from_inventory(user_id, server_id, item_id, quantity=1):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(
            "UPDATE player_inventory SET quantity=quantity-? WHERE user_id=? AND server_id=? AND item_id=?",
            (quantity, str(user_id), str(server_id), item_id)
        )
        cur.execute(
            "DELETE FROM player_inventory WHERE user_id=? AND server_id=? AND item_id=? AND quantity<=0",
            (str(user_id), str(server_id), item_id)
        )
        con.commit()


def use_item(user_id, server_id, item_id):
    """Apply a consumable. Returns (success, message)."""
    p = get_player(user_id, server_id)
    if not p:
        return False, "You don't exist yet. Use `/rpg start` first."

    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(
            "SELECT i.name, i.item_type, i.effect, pi.quantity FROM player_inventory pi JOIN items i ON pi.item_id=i.id WHERE pi.user_id=? AND pi.server_id=? AND pi.item_id=?",
            (str(user_id), str(server_id), item_id)
        )
        row = cur.fetchone()

    if not row:
        return False, "You don't have that item."
    name, item_type, effect_json, qty = row
    if item_type != 'consumable':
        return False, f"**{name}** can't be used directly — it applies automatically when in your inventory."

    eff    = json.loads(effect_json)
    heal   = eff.get('heal', 0)
    new_hp = min(p['max_hp'], p['hp'] + heal)
    update_player_hp(user_id, server_id, new_hp)
    remove_from_inventory(user_id, server_id, item_id, 1)
    healed = new_hp - p['hp']
    return True, f"You used **{name}** and restored **{healed} HP**. ({new_hp}/{p['max_hp']})"

# ---------------------------------------------------------------------------
# Map helpers
# ---------------------------------------------------------------------------

def get_default_map(server_id):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(
            "SELECT id, name, width, height FROM maps WHERE server_id=? AND is_default=1 LIMIT 1",
            (str(server_id),)
        )
        return cur.fetchone()


def get_map(map_id):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("SELECT id, server_id, name, width, height, is_default FROM maps WHERE id=?", (map_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))


def get_tile(map_id, x, y):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("SELECT tile_type FROM tiles WHERE map_id=? AND x=? AND y=?", (map_id, x, y))
        row = cur.fetchone()
        return row[0] if row else 'void'


def get_portal(map_id, x, y):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(
            "SELECT target_map, target_x, target_y, label FROM portals WHERE map_id=? AND x=? AND y=?",
            (map_id, x, y)
        )
        return cur.fetchone()


def get_enemy_at(map_id, x, y):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("""
            SELECT me.id, me.current_hp, et.name, et.sprite, et.attack, et.defence,
                   et.xp_reward, et.gold_min, et.gold_max, et.loot_table
            FROM map_enemies me JOIN enemy_types et ON me.enemy_type = et.id
            WHERE me.map_id=? AND me.x=? AND me.y=? AND me.current_hp > 0
        """, (map_id, x, y))
        row = cur.fetchone()
        if not row:
            return None
        keys = ['id','current_hp','name','sprite','attack','defence','xp_reward','gold_min','gold_max','loot_table']
        return dict(zip(keys, row))


def get_npc_at(map_id, x, y):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(
            "SELECT id, name, sprite, root_dialog FROM npcs WHERE map_id=? AND x=? AND y=?",
            (map_id, x, y)
        )
        row = cur.fetchone()
        if not row:
            return None
        return {'id': row[0], 'name': row[1], 'sprite': row[2], 'root_dialog': row[3]}


def get_chest_at(map_id, x, y):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("SELECT contents, opened FROM chests WHERE map_id=? AND x=? AND y=?", (map_id, x, y))
        row = cur.fetchone()
        if not row:
            return None
        return {'contents': json.loads(row[0]), 'opened': bool(row[1])}


def get_items_at(map_id, x, y):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("""
            SELECT mi.id, mi.item_id, i.name, mi.quantity
            FROM map_items mi JOIN items i ON mi.item_id = i.id
            WHERE mi.map_id=? AND mi.x=? AND mi.y=?
        """, (map_id, x, y))
        cols = ['id', 'item_id', 'name', 'quantity']
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def get_dialog_node(node_id):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("SELECT text, choices FROM dialog_nodes WHERE id=?", (node_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {'text': row[0], 'choices': json.loads(row[1])}

# ---------------------------------------------------------------------------
# Proc-gen
# ---------------------------------------------------------------------------

def _smooth_noise(width, height, seed=0):
    rng = random.Random(seed)
    grid = [[rng.random() for _ in range(width)] for _ in range(height)]
    for _ in range(4):
        new_grid = [[0.0] * width for _ in range(height)]
        for y in range(height):
            for x in range(width):
                total, count = 0.0, 0
                for dy in range(-1, 2):
                    for dx in range(-1, 2):
                        nx2, ny2 = x + dx, y + dy
                        if 0 <= nx2 < width and 0 <= ny2 < height:
                            total += grid[ny2][nx2]
                            count += 1
                new_grid[y][x] = total / count
        grid = new_grid
    return grid


def generate_overworld(map_id, width=60, height=60, seed=None):
    if seed is None:
        seed = random.randint(0, 999999)
    grid = _smooth_noise(width, height, seed)

    tiles_data = []
    rng = random.Random(seed + 1)
    start = None

    for y in range(height):
        for x in range(width):
            # Island falloff
            cx, cy = width / 2.0, height / 2.0
            dist    = max(abs(x - cx) / cx, abs(y - cy) / cy)
            falloff = max(0.0, 1.0 - max(0.0, dist - 0.4) / 0.6)
            h = grid[y][x] * falloff

            if h < 0.22:
                tile = 'water'
            elif h < 0.30:
                tile = 'sand'
            elif h < 0.65:
                tile = 'tree' if rng.random() < 0.12 else 'grass'
            elif h < 0.80:
                tile = 'stone'
            else:
                tile = 'mountain'

            if tile in ('grass', 'sand', 'stone') and start is None:
                cx2, cy2 = width // 2, height // 2
                if abs(x - cx2) <= 5 and abs(y - cy2) <= 5:
                    start = (x, y)

            tiles_data.append((map_id, x, y, tile))

    if start is None:
        start = (width // 2, height // 2)

    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.executemany(
            "INSERT OR REPLACE INTO tiles (map_id,x,y,tile_type) VALUES (?,?,?,?)",
            tiles_data
        )
        con.commit()

    return start


def generate_dungeon(map_id, width=40, height=40, seed=None):
    if seed is None:
        seed = random.randint(0, 999999)
    rng = random.Random(seed)

    grid = [['wall'] * width for _ in range(height)]

    # Seed random floors
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            if rng.random() < 0.48:
                grid[y][x] = 'floor'

    # Cellular automata — 5 passes
    for _ in range(5):
        new_grid = [row[:] for row in grid]
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                walls = sum(
                    1 for dy in range(-1, 2) for dx in range(-1, 2)
                    if grid[y + dy][x + dx] == 'wall'
                )
                new_grid[y][x] = 'wall' if walls >= 5 else 'floor'
        grid = new_grid

    # Flood fill — keep largest connected floor region
    all_floors = [(x, y) for y in range(height) for x in range(width) if grid[y][x] == 'floor']

    def flood(sx, sy):
        visited, stack = set(), [(sx, sy)]
        while stack:
            cx2, cy2 = stack.pop()
            if (cx2, cy2) in visited or not (0 <= cx2 < width and 0 <= cy2 < height):
                continue
            if grid[cy2][cx2] != 'floor':
                continue
            visited.add((cx2, cy2))
            for ddx, ddy in [(0,1),(0,-1),(1,0),(-1,0)]:
                stack.append((cx2 + ddx, cy2 + ddy))
        return visited

    unvisited = set(all_floors)
    regions   = []
    while unvisited:
        s = next(iter(unvisited))
        r = flood(s[0], s[1])
        regions.append(r)
        unvisited -= r

    if not regions:
        # Fallback: carve a simple room
        for y in range(2, height - 2):
            for x in range(2, width - 2):
                grid[y][x] = 'floor'
        regions = [set((x, y) for y in range(2, height - 2) for x in range(2, width - 2))]

    largest = max(regions, key=len)
    for x, y in all_floors:
        if (x, y) not in largest:
            grid[y][x] = 'wall'

    tiles_data = []
    for y in range(height):
        for x in range(width):
            tiles_data.append((map_id, x, y, grid[y][x]))

    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.executemany(
            "INSERT OR REPLACE INTO tiles (map_id,x,y,tile_type) VALUES (?,?,?,?)",
            tiles_data
        )
        con.commit()

    floor_list = list(largest)
    rng.shuffle(floor_list)
    entry = floor_list[0]
    exit_ = floor_list[-1]
    return entry, exit_


def scatter_enemies(map_id, enemy_type, count, passable_tiles=None):
    """Randomly place enemies on passable tiles of a map."""
    if passable_tiles is None:
        with sqlite3.connect(DB_PATH) as con:
            cur = con.cursor()
            cur.execute(
                "SELECT x,y FROM tiles WHERE map_id=? AND tile_type IN ('floor','grass','stone','sand')",
                (map_id,)
            )
            passable_tiles = cur.fetchall()

    if not passable_tiles:
        return

    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute("SELECT hp FROM enemy_types WHERE id=?", (enemy_type,))
        row = cur.fetchone()
        if not row:
            return
        base_hp = row[0]

        chosen = random.sample(passable_tiles, min(count, len(passable_tiles)))
        rows = [(str(uuid.uuid4()), map_id, x, y, enemy_type, base_hp) for x, y in chosen]
        cur.executemany(
            "INSERT OR IGNORE INTO map_enemies (id,map_id,x,y,enemy_type,current_hp) VALUES (?,?,?,?,?,?)",
            rows
        )
        con.commit()
