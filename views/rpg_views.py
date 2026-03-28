import discord
import sqlite3
import io
import json
import random
import asyncio
from PIL import Image, ImageDraw

import rpg_db as db

# ---------------------------------------------------------------------------
# Tile rendering constants
# ---------------------------------------------------------------------------

TILE_PX      = 24
VIEWPORT_R   = 6          # radius — viewport is (2*R+1) x (2*R+1) = 13x13
VIEWPORT_DIM = VIEWPORT_R * 2 + 1

TILE_COLORS = {
    'grass':    (34,  139,  34),
    'water':    (28,   95, 190),
    'sand':     (210, 185, 120),
    'wall':     (68,   68,  68),
    'floor':    (52,   42,  36),
    'door':     (120,  60,  15),
    'portal':   (140,   0, 200),
    'mountain': (90,   80,  75),
    'tree':     (0,    90,   0),
    'stone':    (118, 110, 105),
    'path':     (158, 138,  98),
    'void':     (5,    5,   10),
    'chest':    (52,   42,  36),  # same as floor, chest is an overlay
}

# ---------------------------------------------------------------------------
# Map renderer
# ---------------------------------------------------------------------------

def render_rpg_map(map_id, center_x, center_y):
    img_size = VIEWPORT_DIM * TILE_PX
    img  = Image.new("RGB", (img_size, img_size), (5, 5, 10))
    draw = ImageDraw.Draw(img)

    x0 = center_x - VIEWPORT_R
    x1 = center_x + VIEWPORT_R
    y0 = center_y - VIEWPORT_R
    y1 = center_y + VIEWPORT_R

    with sqlite3.connect(db.DB_PATH) as con:
        cur = con.cursor()

        cur.execute(
            "SELECT x,y,tile_type FROM tiles WHERE map_id=? AND x BETWEEN ? AND ? AND y BETWEEN ? AND ?",
            (map_id, x0, x1, y0, y1)
        )
        tile_map = {(r[0], r[1]): r[2] for r in cur.fetchall()}

        cur.execute(
            "SELECT x,y FROM portals WHERE map_id=? AND x BETWEEN ? AND ? AND y BETWEEN ? AND ?",
            (map_id, x0, x1, y0, y1)
        )
        portals = {(r[0], r[1]) for r in cur.fetchall()}

        cur.execute("""
            SELECT me.x, me.y, et.sprite
            FROM map_enemies me JOIN enemy_types et ON me.enemy_type=et.id
            WHERE me.map_id=? AND me.x BETWEEN ? AND ? AND me.y BETWEEN ? AND ? AND me.current_hp>0
        """, (map_id, x0, x1, y0, y1))
        enemies = {(r[0], r[1]): r[2] for r in cur.fetchall()}

        cur.execute(
            "SELECT x,y,name FROM npcs WHERE map_id=? AND x BETWEEN ? AND ? AND y BETWEEN ? AND ?",
            (map_id, x0, x1, y0, y1)
        )
        npcs = {(r[0], r[1]): r[2] for r in cur.fetchall()}

        cur.execute(
            "SELECT x,y,opened FROM chests WHERE map_id=? AND x BETWEEN ? AND ? AND y BETWEEN ? AND ?",
            (map_id, x0, x1, y0, y1)
        )
        chests = {(r[0], r[1]): bool(r[2]) for r in cur.fetchall()}

        cur.execute(
            "SELECT DISTINCT x,y FROM map_items WHERE map_id=? AND x BETWEEN ? AND ? AND y BETWEEN ? AND ?",
            (map_id, x0, x1, y0, y1)
        )
        ground_items = {(r[0], r[1]) for r in cur.fetchall()}

    for dy in range(VIEWPORT_DIM):
        for dx in range(VIEWPORT_DIM):
            wx = center_x - VIEWPORT_R + dx
            wy = center_y - VIEWPORT_R + dy

            tile  = tile_map.get((wx, wy), 'void')
            color = TILE_COLORS.get(tile, (5, 5, 10))
            px    = dx * TILE_PX
            py    = dy * TILE_PX
            draw.rectangle([px, py, px + TILE_PX - 1, py + TILE_PX - 1], fill=color)

            cxp = px + TILE_PX // 2
            cyp = py + TILE_PX // 2
            r   = TILE_PX // 2 - 5

            if (wx, wy) in portals:
                draw.ellipse([cxp-r, cyp-r, cxp+r, cyp+r], fill=(180, 0, 255), outline=(220, 100, 255), width=1)
            elif (wx, wy) in enemies:
                draw.ellipse([cxp-r, cyp-r, cxp+r, cyp+r], fill=(200, 30, 30), outline=(255, 80, 80), width=1)
            elif (wx, wy) in npcs:
                draw.ellipse([cxp-r, cyp-r, cxp+r, cyp+r], fill=(30, 150, 200), outline=(80, 200, 255), width=1)
            elif (wx, wy) in chests:
                col = (90, 75, 20) if chests[(wx, wy)] else (255, 200, 0)
                draw.rectangle([px+4, py+4, px+TILE_PX-5, py+TILE_PX-5], fill=col, outline=(180, 140, 0), width=1)
            elif (wx, wy) in ground_items:
                draw.ellipse([cxp-3, cyp-3, cxp+3, cyp+3], fill=(255, 230, 50))

    # Player crosshair
    cx = VIEWPORT_R * TILE_PX + TILE_PX // 2
    cy = VIEWPORT_R * TILE_PX + TILE_PX // 2
    cr = TILE_PX // 2 - 3
    draw.ellipse([cx-cr, cy-cr, cx+cr, cy+cr], outline=(255, 255, 255), width=2)
    draw.line([cx, cy-cr-3, cx, cy-cr+2], fill=(255,255,255), width=1)
    draw.line([cx, cy+cr-2, cx, cy+cr+3], fill=(255,255,255), width=1)
    draw.line([cx-cr-3, cy, cx-cr+2, cy], fill=(255,255,255), width=1)
    draw.line([cx+cr-2, cy, cx+cr+3, cy], fill=(255,255,255), width=1)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def hp_bar(current, maximum, length=10):
    if maximum <= 0:
        return '░' * length
    filled = round(length * max(0, current) / maximum)
    return '▓' * filled + '░' * (length - filled)


# ---------------------------------------------------------------------------
# Map navigation view
# ---------------------------------------------------------------------------

class RPGMapView(discord.ui.View):
    def __init__(self, user, server_id, map_id, x, y):
        super().__init__(timeout=None)
        self.user      = user
        self.server_id = str(server_id)
        self.map_id    = map_id
        self.x         = x
        self.y         = y

    # ------------------------------------------------------------------
    # Movement
    # ------------------------------------------------------------------

    async def _move(self, interaction: discord.Interaction, dx, dy):
        nx, ny = self.x + dx, self.y + dy

        m = db.get_map(self.map_id)
        if m:
            nx = max(0, min(m['width']  - 1, nx))
            ny = max(0, min(m['height'] - 1, ny))

        tile = db.get_tile(self.map_id, nx, ny)
        passable = db.TILE_PASSABLE.get(tile, False)

        if not passable:
            # Silently bounce — just re-render in place
            await self._render_map(interaction)
            return

        self.x, self.y = nx, ny
        db.save_player_pos(self.user.id, self.server_id, self.map_id, nx, ny)

        # Check what's here
        portal  = db.get_portal(self.map_id, nx, ny)
        enemy   = db.get_enemy_at(self.map_id, nx, ny)
        npc     = db.get_npc_at(self.map_id, nx, ny)
        chest   = db.get_chest_at(self.map_id, nx, ny)
        g_items = db.get_items_at(self.map_id, nx, ny)

        if portal:
            target_map, tx, ty, label = portal
            self.map_id = target_map
            self.x, self.y = tx, ty
            db.save_player_pos(self.user.id, self.server_id, target_map, tx, ty)
            await self._render_map(interaction, note=f"✨ You stepped through **{label}**.")

        elif enemy:
            view = CombatView(self.user, self.server_id, self.map_id, self.x, self.y, enemy)
            embed = _combat_embed(enemy, self.user, self.server_id)
            loop = asyncio.get_running_loop()
            buf  = await loop.run_in_executor(None, render_rpg_map, self.map_id, self.x, self.y)
            await interaction.response.edit_message(
                embed=embed,
                attachments=[discord.File(buf, filename="map.png")],
                view=view
            )

        elif npc and npc['root_dialog']:
            node = db.get_dialog_node(npc['root_dialog'])
            if node:
                view  = DialogView(self.user, self.server_id, self.map_id, self.x, self.y, npc)
                embed = _dialog_embed(npc, node)
                loop  = asyncio.get_running_loop()
                buf   = await loop.run_in_executor(None, render_rpg_map, self.map_id, self.x, self.y)
                await interaction.response.edit_message(
                    embed=embed,
                    attachments=[discord.File(buf, filename="map.png")],
                    view=view
                )
                return

            await self._render_map(interaction, note=f"*{npc['name']} has nothing to say.*")

        elif chest and not chest['opened']:
            view  = ChestView(self.user, self.server_id, self.map_id, self.x, self.y, chest['contents'])
            embed = _chest_embed(chest['contents'])
            loop  = asyncio.get_running_loop()
            buf   = await loop.run_in_executor(None, render_rpg_map, self.map_id, self.x, self.y)
            await interaction.response.edit_message(
                embed=embed,
                attachments=[discord.File(buf, filename="map.png")],
                view=view
            )

        elif g_items:
            # Auto pick up
            lines = []
            for item in g_items:
                db.add_to_inventory(self.user.id, self.server_id, item['item_id'], item['quantity'])
                with sqlite3.connect(db.DB_PATH) as con:
                    con.cursor().execute("DELETE FROM map_items WHERE id=?", (item['id'],))
                    con.commit()
                lines.append(f"• {item['name']} x{item['quantity']}")
            await self._render_map(interaction, note="🎒 Picked up:\n" + "\n".join(lines))

        else:
            await self._render_map(interaction)

    async def _render_map(self, interaction: discord.Interaction, note: str = None):
        p    = db.get_player(self.user.id, self.server_id)
        m    = db.get_map(self.map_id)
        atk, dfn, hp, max_hp = db.get_effective_stats(self.user.id, self.server_id)

        desc = (
            f"**{self.user.display_name}** — {hp_bar(hp, max_hp)} {hp}/{max_hp} HP\n"
            f"⚔️ {atk}  🛡️ {dfn}  ⭐ Lv{p['level']}  📍 ({self.x},{self.y})\n"
            f"🗺️ **{m['name'] if m else self.map_id}**"
        )
        if note:
            desc += f"\n\n{note}"

        embed = discord.Embed(title="⚔️ RPG", description=desc, color=discord.Color.dark_green())
        embed.set_image(url="attachment://map.png")
        embed.set_footer(text="Move with the arrows • 🔍 Inspect • 🎒 Inventory")

        loop = asyncio.get_running_loop()
        buf  = await loop.run_in_executor(None, render_rpg_map, self.map_id, self.x, self.y)

        await interaction.response.edit_message(
            embed=embed,
            attachments=[discord.File(buf, filename="map.png")],
            view=self
        )

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------

    @discord.ui.button(label="↖", style=discord.ButtonStyle.secondary, row=0)
    async def nw(self, i, b): await self._move(i, -1, -1)

    @discord.ui.button(label="⬆", style=discord.ButtonStyle.secondary, row=0)
    async def north(self, i, b): await self._move(i, 0, -1)

    @discord.ui.button(label="↗", style=discord.ButtonStyle.secondary, row=0)
    async def ne(self, i, b): await self._move(i, 1, -1)

    @discord.ui.button(label="⬅", style=discord.ButtonStyle.secondary, row=1)
    async def west(self, i, b): await self._move(i, -1, 0)

    @discord.ui.button(label="🔍", style=discord.ButtonStyle.primary, row=1)
    async def inspect(self, interaction: discord.Interaction, button: discord.ui.Button):
        tile    = db.get_tile(self.map_id, self.x, self.y)
        portal  = db.get_portal(self.map_id, self.x, self.y)
        enemy   = db.get_enemy_at(self.map_id, self.x, self.y)
        npc     = db.get_npc_at(self.map_id, self.x, self.y)
        lines   = [f"**Tile:** `{tile}`  **Pos:** ({self.x},{self.y})"]
        if portal:
            lines.append(f"🌀 Portal → {portal[3]}")
        if enemy:
            lines.append(f"{enemy['sprite']} {enemy['name']} — {enemy['current_hp']} HP")
        if npc:
            lines.append(f"💬 {npc['name']} is here")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @discord.ui.button(label="➡", style=discord.ButtonStyle.secondary, row=1)
    async def east(self, i, b): await self._move(i, 1, 0)

    @discord.ui.button(label="↙", style=discord.ButtonStyle.secondary, row=2)
    async def sw(self, i, b): await self._move(i, -1, 1)

    @discord.ui.button(label="⬇", style=discord.ButtonStyle.secondary, row=2)
    async def south(self, i, b): await self._move(i, 0, 1)

    @discord.ui.button(label="↘", style=discord.ButtonStyle.secondary, row=2)
    async def se(self, i, b): await self._move(i, 1, 1)

    @discord.ui.button(label="🎒 Inventory", style=discord.ButtonStyle.secondary, row=3)
    async def inventory(self, interaction: discord.Interaction, button: discord.ui.Button):
        items = db.get_inventory(self.user.id, self.server_id)
        if not items:
            await interaction.response.send_message("Your inventory is empty.", ephemeral=True)
            return
        view  = InventoryView(self.user, self.server_id, self.map_id, self.x, self.y, items, parent_view=self)
        embed = _inventory_embed(items)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="📊 Stats", style=discord.ButtonStyle.secondary, row=3)
    async def stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = db.get_player(self.user.id, self.server_id)
        atk, dfn, hp, max_hp = db.get_effective_stats(self.user.id, self.server_id)
        xp_needed = p['level'] * 20
        embed = discord.Embed(title=f"📊 {self.user.display_name}", color=discord.Color.blurple())
        embed.add_field(name="Level", value=f"⭐ {p['level']}")
        embed.add_field(name="XP",    value=f"{p['xp']} / {xp_needed}")
        embed.add_field(name="Gold",  value=f"💰 {p['gold']}")
        embed.add_field(name="HP",    value=f"{hp_bar(hp, max_hp)} {hp}/{max_hp}")
        embed.add_field(name="Attack",  value=f"⚔️ {atk} (base {p['attack']})")
        embed.add_field(name="Defence", value=f"🛡️ {dfn} (base {p['defence']})")
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# Combat view
# ---------------------------------------------------------------------------

def _combat_embed(enemy, user, server_id):
    atk, dfn, hp, max_hp = db.get_effective_stats(user.id, server_id)
    embed = discord.Embed(
        title=f"⚔️ Combat — {enemy['sprite']} {enemy['name']}",
        color=discord.Color.red()
    )
    embed.add_field(
        name=f"{user.display_name}",
        value=f"{hp_bar(hp, max_hp)} {hp}/{max_hp} HP\n⚔️ {atk}  🛡️ {dfn}",
        inline=True
    )
    embed.add_field(
        name=f"{enemy['name']}",
        value=f"{hp_bar(enemy['current_hp'], enemy.get('max_hp', enemy['current_hp']))} {enemy['current_hp']} HP\n⚔️ {enemy['attack']}  🛡️ {enemy['defence']}",
        inline=True
    )
    return embed


class CombatView(discord.ui.View):
    def __init__(self, user, server_id, map_id, x, y, enemy):
        super().__init__(timeout=None)
        self.user      = user
        self.server_id = str(server_id)
        self.map_id    = map_id
        self.x         = x
        self.y         = y
        self.enemy     = dict(enemy)
        self.enemy.setdefault('max_hp', enemy['current_hp'])
        self.log       = []

    async def _end_combat(self, interaction, won):
        if won:
            # Loot roll
            loot_table = json.loads(self.enemy.get('loot_table', '[]'))
            drops = []
            gold  = random.randint(self.enemy.get('gold_min', 0), self.enemy.get('gold_max', 0))
            for entry in loot_table:
                if random.random() < entry['chance']:
                    db.add_to_inventory(self.user.id, self.server_id, entry['item_id'])
                    with sqlite3.connect(db.DB_PATH) as con:
                        cur = con.cursor()
                        cur.execute("SELECT name FROM items WHERE id=?", (entry['item_id'],))
                        row = cur.fetchone()
                        drops.append(row[0] if row else entry['item_id'])

            if gold > 0:
                with sqlite3.connect(db.DB_PATH) as con:
                    con.cursor().execute(
                        "UPDATE players SET gold=gold+? WHERE user_id=? AND server_id=?",
                        (gold, str(self.user.id), self.server_id)
                    )
                    con.commit()

            new_level, levelled = db.add_xp(self.user.id, self.server_id, self.enemy['xp_reward'])

            # Remove enemy from map
            with sqlite3.connect(db.DB_PATH) as con:
                con.cursor().execute("DELETE FROM map_enemies WHERE id=?", (self.enemy['id'],))
                con.commit()

            note_parts = [f"🏆 You defeated **{self.enemy['name']}**! +{self.enemy['xp_reward']} XP, +{gold} gold"]
            if drops:
                note_parts.append("🎁 Drops: " + ", ".join(drops))
            if levelled:
                note_parts.append(f"⭐ **Level up! You are now level {new_level}!**")
            note = "\n".join(note_parts)
        else:
            # Player dead — respawn with 1 HP at map start
            m = db.get_map(self.map_id)
            rx, ry = (m['width'] // 2, m['height'] // 2) if m else (0, 0)
            db.save_player_pos(self.user.id, self.server_id, self.map_id, rx, ry)
            db.update_player_hp(self.user.id, self.server_id, 1)
            self.x, self.y = rx, ry
            note = "💀 You were defeated and respawned at the map centre with 1 HP."

        # Return to map
        back = RPGMapView(self.user, self.server_id, self.map_id, self.x, self.y)
        p    = db.get_player(self.user.id, self.server_id)
        m    = db.get_map(self.map_id)
        atk, dfn, hp, max_hp = db.get_effective_stats(self.user.id, self.server_id)
        desc = (
            f"**{self.user.display_name}** — {hp_bar(hp, max_hp)} {hp}/{max_hp} HP\n"
            f"⚔️ {atk}  🛡️ {dfn}  ⭐ Lv{p['level']}  📍 ({self.x},{self.y})\n"
            f"🗺️ **{m['name'] if m else self.map_id}**\n\n{note}"
        )
        embed = discord.Embed(title="⚔️ RPG", description=desc, color=discord.Color.dark_green())
        embed.set_image(url="attachment://map.png")

        loop = asyncio.get_running_loop()
        buf  = await loop.run_in_executor(None, render_rpg_map, self.map_id, self.x, self.y)
        await interaction.response.edit_message(
            embed=embed,
            attachments=[discord.File(buf, filename="map.png")],
            view=back
        )

    @discord.ui.button(label="⚔️ Attack", style=discord.ButtonStyle.danger, row=0)
    async def attack(self, interaction: discord.Interaction, button: discord.ui.Button):
        atk, dfn, hp, max_hp = db.get_effective_stats(self.user.id, self.server_id)

        # Player hits enemy
        p_dmg = max(1, atk - self.enemy['defence'] + random.randint(-1, 2))
        self.enemy['current_hp'] -= p_dmg

        if self.enemy['current_hp'] <= 0:
            self.enemy['current_hp'] = 0
            await self._end_combat(interaction, won=True)
            return

        # Enemy hits player
        e_dmg  = max(1, self.enemy['attack'] - dfn + random.randint(-1, 2))
        new_hp = hp - e_dmg
        db.update_player_hp(self.user.id, self.server_id, new_hp)

        if new_hp <= 0:
            await self._end_combat(interaction, won=False)
            return

        embed = _combat_embed(self.enemy, self.user, self.server_id)
        embed.add_field(
            name="Last round",
            value=f"You dealt **{p_dmg}** dmg | {self.enemy['name']} dealt **{e_dmg}** dmg",
            inline=False
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🧪 Use Item", style=discord.ButtonStyle.primary, row=0)
    async def use_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        items = [i for i in db.get_inventory(self.user.id, self.server_id) if i['item_type'] == 'consumable']
        if not items:
            await interaction.response.send_message("No consumables in inventory.", ephemeral=True)
            return
        view = CombatItemSelect(self.user, self.server_id, items, self)
        await interaction.response.send_message("Choose an item:", view=view, ephemeral=True)

    @discord.ui.button(label="🏃 Flee", style=discord.ButtonStyle.secondary, row=0)
    async def flee(self, interaction: discord.Interaction, button: discord.ui.Button):
        if random.random() < 0.5:
            # Flee success — step back
            fx = max(0, self.x - 1)
            fy = max(0, self.y - 1)
            db.save_player_pos(self.user.id, self.server_id, self.map_id, fx, fy)
            self.x, self.y = fx, fy
            back = RPGMapView(self.user, self.server_id, self.map_id, fx, fy)
            await back._render_map(interaction, note="🏃 You fled from combat!")
        else:
            # Flee fail — take a hit
            atk, dfn, hp, max_hp = db.get_effective_stats(self.user.id, self.server_id)
            e_dmg  = max(1, self.enemy['attack'] - dfn + random.randint(-1, 2))
            new_hp = hp - e_dmg
            db.update_player_hp(self.user.id, self.server_id, new_hp)
            if new_hp <= 0:
                await self._end_combat(interaction, won=False)
                return
            embed = _combat_embed(self.enemy, self.user, self.server_id)
            embed.add_field(name="Flee failed!", value=f"{self.enemy['name']} hit you for **{e_dmg}** as you turned away.", inline=False)
            await interaction.response.edit_message(embed=embed, view=self)


class CombatItemSelect(discord.ui.View):
    def __init__(self, user, server_id, items, combat_view):
        super().__init__(timeout=60)
        self.user        = user
        self.server_id   = server_id
        self.combat_view = combat_view

        options = [
            discord.SelectOption(label=f"{i['name']} x{i['quantity']}", value=i['id'], description=i['description'] or "")
            for i in items[:25]
        ]
        select = discord.ui.Select(placeholder="Select item…", options=options)
        select.callback = self._selected
        self.add_item(select)

    async def _selected(self, interaction: discord.Interaction):
        item_id       = interaction.data['values'][0]
        success, msg  = db.use_item(self.user.id, self.server_id, item_id)
        await interaction.response.send_message(msg, ephemeral=True)
        if success:
            embed = _combat_embed(self.combat_view.enemy, self.user, self.server_id)
            embed.add_field(name="Item used", value=msg, inline=False)
            # Edit the original combat message
            try:
                await interaction.message.edit(embed=embed, view=self.combat_view)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Inventory view
# ---------------------------------------------------------------------------

def _inventory_embed(items):
    embed = discord.Embed(title="🎒 Inventory", color=discord.Color.blurple())
    type_icons = {'weapon': '⚔️', 'armour': '🛡️', 'consumable': '🧪', 'key': '🗝️', 'misc': '📦'}
    by_type = {}
    for item in items:
        by_type.setdefault(item['item_type'], []).append(item)
    for t, t_items in by_type.items():
        lines = [f"{type_icons.get(t,'📦')} **{i['name']}** x{i['quantity']} — {i['description'] or ''}" for i in t_items]
        embed.add_field(name=t.title(), value="\n".join(lines), inline=False)
    return embed


class InventoryView(discord.ui.View):
    def __init__(self, user, server_id, map_id, x, y, items, parent_view=None):
        super().__init__(timeout=120)
        self.user        = user
        self.server_id   = server_id
        self.map_id      = map_id
        self.x           = x
        self.y           = y
        self.items       = items
        self.parent_view = parent_view

        consumables = [i for i in items if i['item_type'] == 'consumable']
        if consumables:
            options = [
                discord.SelectOption(label=f"{i['name']} x{i['quantity']}", value=i['id'], description=i['description'] or "")
                for i in consumables[:25]
            ]
            select = discord.ui.Select(placeholder="Use a consumable…", options=options)
            select.callback = self._use
            self.add_item(select)

    async def _use(self, interaction: discord.Interaction):
        item_id      = interaction.data['values'][0]
        success, msg = db.use_item(self.user.id, self.server_id, item_id)
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(label="Give item to player", style=discord.ButtonStyle.secondary, row=1)
    async def give(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Use `/rpg give @user item_id quantity` to give an item.",
            ephemeral=True
        )


# ---------------------------------------------------------------------------
# Dialog view
# ---------------------------------------------------------------------------

def _dialog_embed(npc, node):
    embed = discord.Embed(
        title=f"{npc['sprite']} {npc['name']}",
        description=node['text'],
        color=discord.Color.teal()
    )
    return embed


class DialogView(discord.ui.View):
    def __init__(self, user, server_id, map_id, x, y, npc, node_id=None):
        super().__init__(timeout=120)
        self.user      = user
        self.server_id = server_id
        self.map_id    = map_id
        self.x         = x
        self.y         = y
        self.npc       = npc
        node_id        = node_id or npc['root_dialog']
        self.node      = db.get_dialog_node(node_id)
        self._build_buttons()

    def _build_buttons(self):
        self.clear_items()
        if not self.node:
            return
        for i, choice in enumerate(self.node.get('choices', [])[:5]):
            btn       = discord.ui.Button(label=choice['label'][:80], style=discord.ButtonStyle.primary, row=i // 3)
            btn.custom_id = f"dialog_{i}"
            next_id   = choice.get('next_id')
            action    = choice.get('action')
            btn.callback = self._make_callback(next_id, action, choice)
            self.add_item(btn)

        leave = discord.ui.Button(label="Leave", style=discord.ButtonStyle.secondary, row=4)
        leave.callback = self._leave
        self.add_item(leave)

    def _make_callback(self, next_id, action, choice):
        async def callback(interaction: discord.Interaction):
            if action:
                await self._handle_action(interaction, action, choice)
                return
            if next_id:
                self.node = db.get_dialog_node(next_id)
                self._build_buttons()
                embed = _dialog_embed(self.npc, self.node)
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await self._leave(interaction)
        return callback

    async def _handle_action(self, interaction, action, choice):
        if action == 'give_item':
            item_id = choice.get('item_id')
            if item_id:
                db.add_to_inventory(self.user.id, self.server_id, item_id)
                with sqlite3.connect(db.DB_PATH) as con:
                    cur = con.cursor()
                    cur.execute("SELECT name FROM items WHERE id=?", (item_id,))
                    row = cur.fetchone()
                name = row[0] if row else item_id
                await interaction.response.send_message(f"**{self.npc['name']}** gave you **{name}**!", ephemeral=True)
        else:
            await interaction.response.send_message("...", ephemeral=True)

    async def _leave(self, interaction: discord.Interaction):
        back = RPGMapView(self.user, self.server_id, self.map_id, self.x, self.y)
        await back._render_map(interaction)


# ---------------------------------------------------------------------------
# Chest view
# ---------------------------------------------------------------------------

def _chest_embed(contents):
    embed = discord.Embed(title="📦 Chest", color=discord.Color.gold())
    if not contents:
        embed.description = "*The chest is empty.*"
        return embed
    lines = []
    for entry in contents:
        with sqlite3.connect(db.DB_PATH) as con:
            cur = con.cursor()
            cur.execute("SELECT name FROM items WHERE id=?", (entry['item_id'],))
            row = cur.fetchone()
        name = row[0] if row else entry['item_id']
        lines.append(f"• {name} x{entry.get('quantity',1)}")
    embed.description = "\n".join(lines)
    return embed


class ChestView(discord.ui.View):
    def __init__(self, user, server_id, map_id, x, y, contents):
        super().__init__(timeout=120)
        self.user      = user
        self.server_id = server_id
        self.map_id    = map_id
        self.x         = x
        self.y         = y
        self.contents  = contents

    @discord.ui.button(label="Take All", style=discord.ButtonStyle.success, row=0)
    async def take_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        taken = []
        for entry in self.contents:
            db.add_to_inventory(self.user.id, self.server_id, entry['item_id'], entry.get('quantity', 1))
            with sqlite3.connect(db.DB_PATH) as con:
                cur = con.cursor()
                cur.execute("SELECT name FROM items WHERE id=?", (entry['item_id'],))
                row = cur.fetchone()
            taken.append(row[0] if row else entry['item_id'])

        with sqlite3.connect(db.DB_PATH) as con:
            con.cursor().execute(
                "UPDATE chests SET opened=1, contents='[]' WHERE map_id=? AND x=? AND y=?",
                (self.map_id, self.x, self.y)
            )
            con.commit()

        back = RPGMapView(self.user, self.server_id, self.map_id, self.x, self.y)
        await back._render_map(interaction, note="📦 Took: " + ", ".join(taken))

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.secondary, row=0)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        back = RPGMapView(self.user, self.server_id, self.map_id, self.x, self.y)
        await back._render_map(interaction)


# ---------------------------------------------------------------------------
# Map editor view  (admin only)
# ---------------------------------------------------------------------------
# Layout (5 rows x 5 buttons max = 25 total):
#   Row 0: ↖  ⬆  ↗  ⬅  ➡           (navigation)
#   Row 1: ↙  ⬇  ↘  ✅Done  (x,y)   (navigation + done + pos indicator)
#   Row 2: 🌿  🌊  🏖  🧱  🪵        (grass water sand wall floor)
#   Row 3: 🚪  🌀  ⛰  🌲  🪨        (door portal mountain tree stone)
#   Row 4: 🛤  ⬛                     (path void)
#
# TODO: portal / chest tiles need a follow-up modal to set their extra data
#       (target map+coords for portals, contents JSON for chests). For now,
#       placing those tile types just sets the tile_type — use the existing
#       /rpg_admin_add_portal and /rpg_admin_add_chest commands to attach the data.

_EDITOR_TILES = [
    # (button label, tile_type)  — row 2
    ("🌿", "grass"), ("🌊", "water"), ("🏖", "sand"), ("🧱", "wall"), ("🪵", "floor"),
    # row 3
    ("🚪", "door"),  ("🌀", "portal"), ("⛰", "mountain"), ("🌲", "tree"), ("🪨", "stone"),
    # row 4
    ("🛤", "path"),  ("⬛", "void"),
]

_NEEDS_EXTRA = {"portal", "chest"}  # TODO: prompt for extra data


class MapEditorView(discord.ui.View):
    def __init__(self, map_id, x, y):
        super().__init__(timeout=None)
        self.map_id = map_id
        self.x      = x
        self.y      = y
        self._build()

    def _build(self):
        self.clear_items()

        # --- Row 0: diagonal + cardinal nav ---
        for label, dx, dy in [("↖", -1, -1), ("⬆", 0, -1), ("↗", 1, -1), ("⬅", -1, 0), ("➡", 1, 0)]:
            btn          = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary, row=0)
            btn.callback = self._make_nav(dx, dy)
            self.add_item(btn)

        # --- Row 1: more nav + Done + position indicator ---
        for label, dx, dy in [("↙", -1, 1), ("⬇", 0, 1), ("↘", 1, 1)]:
            btn          = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary, row=1)
            btn.callback = self._make_nav(dx, dy)
            self.add_item(btn)

        done          = discord.ui.Button(label="✅ Done", style=discord.ButtonStyle.success, row=1)
        done.callback = self._done
        self.add_item(done)

        pos = discord.ui.Button(
            label=f"({self.x},{self.y})", style=discord.ButtonStyle.secondary, row=1, disabled=True
        )
        self.add_item(pos)

        # --- Rows 2-4: tile type buttons ---
        for i, (icon, tile_type) in enumerate(_EDITOR_TILES):
            tile_row     = 2 + (i // 5)
            btn          = discord.ui.Button(label=icon, style=discord.ButtonStyle.primary, row=tile_row)
            btn.callback = self._make_paint(tile_type)
            self.add_item(btn)

    # ------------------------------------------------------------------

    def _make_nav(self, dx, dy):
        async def callback(interaction: discord.Interaction):
            m  = db.get_map(self.map_id)
            self.x = max(0, min((m['width']  - 1 if m else 999), self.x + dx))
            self.y = max(0, min((m['height'] - 1 if m else 999), self.y + dy))
            self._build()
            await self._render(interaction)
        return callback

    def _make_paint(self, tile_type):
        async def callback(interaction: discord.Interaction):
            with sqlite3.connect(db.DB_PATH) as con:
                con.cursor().execute(
                    "INSERT OR REPLACE INTO tiles (map_id,x,y,tile_type) VALUES (?,?,?,?)",
                    (self.map_id, self.x, self.y, tile_type)
                )
                con.commit()

            note = f"🖊️ ({self.x},{self.y}) → `{tile_type}`"
            if tile_type in _NEEDS_EXTRA:
                note += f"\n⚠️ *`{tile_type}` needs extra data — use the matching `/rpg_admin` command to finish setting it up.*"

            await self._render(interaction, note=note)
        return callback

    async def _done(self, interaction: discord.Interaction):
        m = db.get_map(self.map_id)
        await interaction.response.edit_message(
            content=f"✅ Finished editing **{m['name'] if m else self.map_id}**.",
            embed=None,
            attachments=[],
            view=None
        )

    async def _render(self, interaction: discord.Interaction, note: str = None):
        m    = db.get_map(self.map_id)
        tile = db.get_tile(self.map_id, self.x, self.y)
        desc = f"**{m['name'] if m else self.map_id}** | ({self.x},{self.y}) — `{tile}`"
        if note:
            desc += f"\n{note}"

        embed = discord.Embed(title="🗺️ Map Editor", description=desc, color=discord.Color.orange())
        embed.set_image(url="attachment://map.png")
        embed.set_footer(text="Navigate with arrows, press a tile button to paint the current tile")

        loop = asyncio.get_running_loop()
        buf  = await loop.run_in_executor(None, render_rpg_map, self.map_id, self.x, self.y)
        await interaction.response.edit_message(
            embed=embed,
            attachments=[discord.File(buf, filename="map.png")],
            view=self
        )
