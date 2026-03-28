import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import asyncio
import uuid
import json

import rpg_db as db
from views.rpg_views import render_rpg_map, MapEditorView


class RPGAdmin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ------------------------------------------------------------------
    # /rpg_admin create_map
    # ------------------------------------------------------------------

    @app_commands.command(name="rpg_admin_create_map", description="[ADMIN] Create and generate a new RPG map.")
    @app_commands.describe(
        name="Map name",
        map_type="Generation style",
        width="Width in tiles (default 60)",
        height="Height in tiles (default 60)",
        set_default="Make this the starting map for new players",
        scatter_enemies="Automatically scatter enemies on the map"
    )
    @app_commands.choices(map_type=[
        app_commands.Choice(name="Overworld", value="overworld"),
        app_commands.Choice(name="Dungeon",   value="dungeon"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def create_map(
        self,
        interaction: discord.Interaction,
        name: str,
        map_type: str = "overworld",
        width: int = 60,
        height: int = 60,
        set_default: bool = False,
        scatter_enemies: bool = True,
    ):
        await interaction.response.defer(ephemeral=True)
        server_id = str(interaction.guild.id)
        map_id    = str(uuid.uuid4())[:8]

        # If setting as default, clear existing default
        if set_default:
            with sqlite3.connect(db.DB_PATH) as con:
                con.cursor().execute(
                    "UPDATE maps SET is_default=0 WHERE server_id=?", (server_id,)
                )
                con.commit()

        with sqlite3.connect(db.DB_PATH) as con:
            cur = con.cursor()
            cur.execute(
                "INSERT INTO maps (id,server_id,name,width,height,is_default) VALUES (?,?,?,?,?,?)",
                (map_id, server_id, name, width, height, 1 if set_default else 0)
            )
            con.commit()

        loop = asyncio.get_running_loop()

        if map_type == "dungeon":
            entry, exit_ = await loop.run_in_executor(None, db.generate_dungeon, map_id, width, height)
            cx, cy = entry
        else:
            start = await loop.run_in_executor(None, db.generate_overworld, map_id, width, height)
            cx, cy = start

        if scatter_enemies:
            await loop.run_in_executor(None, db.scatter_enemies, map_id, 'slime',   max(2, width // 10))
            await loop.run_in_executor(None, db.scatter_enemies, map_id, 'goblin',  max(1, width // 15))
            await loop.run_in_executor(None, db.scatter_enemies, map_id, 'skeleton', max(1, width // 20))

        buf = await loop.run_in_executor(None, render_rpg_map, map_id, cx, cy)

        await interaction.followup.send(
            content=(
                f"✅ Map **{name}** (`{map_id}`) created!\n"
                f"Type: `{map_type}` | Size: {width}×{height} | Default: {set_default}"
            ),
            file=discord.File(buf, filename="map_preview.png"),
            ephemeral=True
        )

    # ------------------------------------------------------------------
    # /rpg_admin list_maps
    # ------------------------------------------------------------------

    @app_commands.command(name="rpg_admin_list_maps", description="[ADMIN] List all maps for this server.")
    @app_commands.default_permissions(administrator=True)
    async def list_maps(self, interaction: discord.Interaction):
        with sqlite3.connect(db.DB_PATH) as con:
            cur = con.cursor()
            cur.execute(
                "SELECT id, name, width, height, is_default FROM maps WHERE server_id=? ORDER BY name",
                (str(interaction.guild.id),)
            )
            rows = cur.fetchall()

        if not rows:
            await interaction.response.send_message("No maps yet. Use `/rpg_admin_create_map`.", ephemeral=True)
            return

        embed = discord.Embed(title="🗺️ Maps", color=discord.Color.blue())
        for map_id, name, w, h, is_default in rows:
            embed.add_field(
                name=f"{'⭐ ' if is_default else ''}{name}",
                value=f"ID: `{map_id}` | {w}×{h}",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # /rpg_admin set_default
    # ------------------------------------------------------------------

    @app_commands.command(name="rpg_admin_set_default", description="[ADMIN] Set the default starting map.")
    @app_commands.describe(map_id="Map ID to set as default")
    @app_commands.default_permissions(administrator=True)
    async def set_default(self, interaction: discord.Interaction, map_id: str):
        server_id = str(interaction.guild.id)
        m = db.get_map(map_id)
        if not m or m['server_id'] != server_id:
            await interaction.response.send_message("Map not found on this server.", ephemeral=True)
            return

        with sqlite3.connect(db.DB_PATH) as con:
            cur = con.cursor()
            cur.execute("UPDATE maps SET is_default=0 WHERE server_id=?", (server_id,))
            cur.execute("UPDATE maps SET is_default=1 WHERE id=?", (map_id,))
            con.commit()

        await interaction.response.send_message(f"✅ **{m['name']}** is now the default starting map.", ephemeral=True)

    # ------------------------------------------------------------------
    # /rpg_admin set_tile
    # ------------------------------------------------------------------

    @app_commands.command(name="rpg_admin_set_tile", description="[ADMIN] Set a tile type on a map.")
    @app_commands.describe(
        map_id="Map ID",
        x="X coordinate",
        y="Y coordinate",
        tile_type="Tile type"
    )
    @app_commands.choices(tile_type=[
        app_commands.Choice(name=t, value=t)
        for t in ['grass','water','sand','wall','floor','door','portal','mountain','tree','stone','path','void']
    ])
    @app_commands.default_permissions(administrator=True)
    async def set_tile(self, interaction: discord.Interaction, map_id: str, x: int, y: int, tile_type: str):
        m = db.get_map(map_id)
        if not m or m['server_id'] != str(interaction.guild.id):
            await interaction.response.send_message("Map not found.", ephemeral=True)
            return

        with sqlite3.connect(db.DB_PATH) as con:
            con.cursor().execute(
                "INSERT OR REPLACE INTO tiles (map_id,x,y,tile_type) VALUES (?,?,?,?)",
                (map_id, x, y, tile_type)
            )
            con.commit()

        await interaction.response.send_message(
            f"✅ Tile ({x},{y}) on **{m['name']}** set to `{tile_type}`.", ephemeral=True
        )

    # ------------------------------------------------------------------
    # /rpg_admin add_portal
    # ------------------------------------------------------------------

    @app_commands.command(name="rpg_admin_add_portal", description="[ADMIN] Add a portal between two maps.")
    @app_commands.describe(
        map_id="Source map ID",
        x="Portal X on source map",
        y="Portal Y on source map",
        target_map="Destination map ID",
        target_x="Landing X on destination",
        target_y="Landing Y on destination",
        label="Display name for this portal"
    )
    @app_commands.default_permissions(administrator=True)
    async def add_portal(
        self,
        interaction: discord.Interaction,
        map_id: str, x: int, y: int,
        target_map: str, target_x: int, target_y: int,
        label: str = "Portal"
    ):
        server_id = str(interaction.guild.id)
        src = db.get_map(map_id)
        dst = db.get_map(target_map)
        if not src or src['server_id'] != server_id:
            await interaction.response.send_message("Source map not found.", ephemeral=True)
            return
        if not dst or dst['server_id'] != server_id:
            await interaction.response.send_message("Destination map not found.", ephemeral=True)
            return

        with sqlite3.connect(db.DB_PATH) as con:
            cur = con.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO portals (map_id,x,y,target_map,target_x,target_y,label) VALUES (?,?,?,?,?,?,?)",
                (map_id, x, y, target_map, target_x, target_y, label)
            )
            # Also set the tile to portal type
            cur.execute(
                "INSERT OR REPLACE INTO tiles (map_id,x,y,tile_type) VALUES (?,?,?,'portal')",
                (map_id, x, y)
            )
            con.commit()

        await interaction.response.send_message(
            f"✅ Portal at ({x},{y}) on **{src['name']}** → **{dst['name']}** ({target_x},{target_y}). Label: *{label}*",
            ephemeral=True
        )

    # ------------------------------------------------------------------
    # /rpg_admin add_npc
    # ------------------------------------------------------------------

    @app_commands.command(name="rpg_admin_add_npc", description="[ADMIN] Place an NPC on a map.")
    @app_commands.describe(
        map_id="Map ID",
        x="X position",
        y="Y position",
        name="NPC name",
        sprite="Emoji sprite (default 🧑)",
        greeting="Opening line of dialog (optional)"
    )
    @app_commands.default_permissions(administrator=True)
    async def add_npc(
        self,
        interaction: discord.Interaction,
        map_id: str, x: int, y: int,
        name: str,
        sprite: str = "🧑",
        greeting: str = None
    ):
        m = db.get_map(map_id)
        if not m or m['server_id'] != str(interaction.guild.id):
            await interaction.response.send_message("Map not found.", ephemeral=True)
            return

        npc_id    = str(uuid.uuid4())[:8]
        dialog_id = None

        if greeting:
            dialog_id = str(uuid.uuid4())[:8]
            with sqlite3.connect(db.DB_PATH) as con:
                con.cursor().execute(
                    "INSERT INTO dialog_nodes (id, text, choices) VALUES (?,?,?)",
                    (dialog_id, greeting, '[]')
                )
                con.commit()

        with sqlite3.connect(db.DB_PATH) as con:
            con.cursor().execute(
                "INSERT INTO npcs (id,map_id,x,y,name,sprite,root_dialog) VALUES (?,?,?,?,?,?,?)",
                (npc_id, map_id, x, y, name, sprite, dialog_id)
            )
            con.commit()

        await interaction.response.send_message(
            f"✅ NPC **{name}** (`{npc_id}`) placed at ({x},{y}) on **{m['name']}**.",
            ephemeral=True
        )

    # ------------------------------------------------------------------
    # /rpg_admin spawn_enemy
    # ------------------------------------------------------------------

    @app_commands.command(name="rpg_admin_spawn_enemy", description="[ADMIN] Spawn an enemy on a map.")
    @app_commands.describe(
        map_id="Map ID",
        x="X position",
        y="Y position",
        enemy_type="Enemy type ID"
    )
    @app_commands.choices(enemy_type=[
        app_commands.Choice(name=e, value=e)
        for e in ['slime','goblin','orc','skeleton','dragon']
    ])
    @app_commands.default_permissions(administrator=True)
    async def spawn_enemy(self, interaction: discord.Interaction, map_id: str, x: int, y: int, enemy_type: str):
        m = db.get_map(map_id)
        if not m or m['server_id'] != str(interaction.guild.id):
            await interaction.response.send_message("Map not found.", ephemeral=True)
            return

        with sqlite3.connect(db.DB_PATH) as con:
            cur = con.cursor()
            cur.execute("SELECT hp, name FROM enemy_types WHERE id=?", (enemy_type,))
            row = cur.fetchone()
            if not row:
                await interaction.response.send_message("Unknown enemy type.", ephemeral=True)
                return
            base_hp, ename = row
            eid = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO map_enemies (id,map_id,x,y,enemy_type,current_hp) VALUES (?,?,?,?,?,?)",
                (eid, map_id, x, y, enemy_type, base_hp)
            )
            con.commit()

        await interaction.response.send_message(
            f"✅ Spawned **{ename}** at ({x},{y}) on **{m['name']}**.", ephemeral=True
        )

    # ------------------------------------------------------------------
    # /rpg_admin give_item
    # ------------------------------------------------------------------

    @app_commands.command(name="rpg_admin_give_item", description="[ADMIN] Give an item to a player.")
    @app_commands.describe(
        user="Target player",
        item_id="Item ID",
        quantity="Amount (default 1)"
    )
    @app_commands.default_permissions(administrator=True)
    async def give_item(self, interaction: discord.Interaction, user: discord.Member, item_id: str, quantity: int = 1):
        server_id = str(interaction.guild.id)
        if not db.get_player(str(user.id), server_id):
            await interaction.response.send_message(f"{user.display_name} hasn't started yet.", ephemeral=True)
            return

        with sqlite3.connect(db.DB_PATH) as con:
            cur = con.cursor()
            cur.execute("SELECT name FROM items WHERE id=?", (item_id,))
            row = cur.fetchone()

        if not row:
            await interaction.response.send_message(f"Item `{item_id}` not found. Use `/rpg_admin_list_items` to see available items.", ephemeral=True)
            return

        db.add_to_inventory(str(user.id), server_id, item_id, quantity)
        await interaction.response.send_message(
            f"✅ Gave **{row[0]} x{quantity}** to {user.mention}.", ephemeral=True
        )

    # ------------------------------------------------------------------
    # /rpg_admin list_items
    # ------------------------------------------------------------------

    @app_commands.command(name="rpg_admin_list_items", description="[ADMIN] List all available item IDs.")
    @app_commands.default_permissions(administrator=True)
    async def list_items(self, interaction: discord.Interaction):
        with sqlite3.connect(db.DB_PATH) as con:
            cur = con.cursor()
            cur.execute("SELECT id, name, item_type, value, description FROM items ORDER BY item_type, name")
            rows = cur.fetchall()

        embed = discord.Embed(title="📦 Items", color=discord.Color.orange())
        by_type = {}
        for row in rows:
            by_type.setdefault(row[2], []).append(row)
        for t, items in by_type.items():
            lines = [f"`{i[0]}` — {i[1]} ({i[3]} gold) {i[4] or ''}" for i in items]
            embed.add_field(name=t.title(), value="\n".join(lines), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # /rpg_admin add_chest
    # ------------------------------------------------------------------

    @app_commands.command(name="rpg_admin_add_chest", description="[ADMIN] Place a chest on a map.")
    @app_commands.describe(
        map_id="Map ID",
        x="X position",
        y="Y position",
        contents="JSON array e.g. [{\"item_id\":\"health_potion\",\"quantity\":2}]"
    )
    @app_commands.default_permissions(administrator=True)
    async def add_chest(self, interaction: discord.Interaction, map_id: str, x: int, y: int, contents: str = "[]"):
        m = db.get_map(map_id)
        if not m or m['server_id'] != str(interaction.guild.id):
            await interaction.response.send_message("Map not found.", ephemeral=True)
            return

        try:
            parsed = json.loads(contents)
        except json.JSONDecodeError:
            await interaction.response.send_message("Invalid JSON for contents.", ephemeral=True)
            return

        with sqlite3.connect(db.DB_PATH) as con:
            con.cursor().execute(
                "INSERT OR REPLACE INTO chests (map_id,x,y,contents,opened) VALUES (?,?,?,?,0)",
                (map_id, x, y, json.dumps(parsed))
            )
            con.commit()

        await interaction.response.send_message(
            f"✅ Chest placed at ({x},{y}) on **{m['name']}** with {len(parsed)} item type(s).", ephemeral=True
        )

    # ------------------------------------------------------------------
    # /rpg_admin view_map
    # ------------------------------------------------------------------

    @app_commands.command(name="rpg_admin_view_map", description="[ADMIN] Preview a map at a given position.")
    @app_commands.describe(map_id="Map ID", x="Centre X (defaults to map centre)", y="Centre Y (defaults to map centre)")
    @app_commands.default_permissions(administrator=True)
    async def view_map(self, interaction: discord.Interaction, map_id: str, x: int = -1, y: int = -1):
        await interaction.response.defer(ephemeral=True)
        m = db.get_map(map_id)
        if not m or m['server_id'] != str(interaction.guild.id):
            await interaction.followup.send("Map not found.", ephemeral=True)
            return

        if x < 0:
            x = m['width'] // 2
        if y < 0:
            y = m['height'] // 2

        loop = asyncio.get_running_loop()
        buf  = await loop.run_in_executor(None, render_rpg_map, map_id, x, y)
        await interaction.followup.send(
            content=f"🗺️ **{m['name']}** at ({x},{y})",
            file=discord.File(buf, filename="map_preview.png"),
            ephemeral=True
        )


    # ------------------------------------------------------------------
    # /rpg_admin_edit_map
    # ------------------------------------------------------------------

    @app_commands.command(name="rpg_admin_edit_map", description="[ADMIN] Open the visual tile editor for a map.")
    @app_commands.describe(map_id="Map ID to edit", x="Starting cursor X (defaults to map centre)", y="Starting cursor Y (defaults to map centre)")
    @app_commands.default_permissions(administrator=True)
    async def edit_map(self, interaction: discord.Interaction, map_id: str, x: int = -1, y: int = -1):
        await interaction.response.defer(ephemeral=True)

        m = db.get_map(map_id)
        if not m or m['server_id'] != str(interaction.guild.id):
            await interaction.followup.send("Map not found on this server.", ephemeral=True)
            return

        # Default to map centre — corners are ocean on overworld maps
        if x < 0:
            x = m['width'] // 2
        if y < 0:
            y = m['height'] // 2

        x = max(0, min(m['width']  - 1, x))
        y = max(0, min(m['height'] - 1, y))

        view = MapEditorView(map_id, x, y)
        tile = db.get_tile(map_id, x, y)

        embed = discord.Embed(
            title="🗺️ Map Editor",
            description=f"**{m['name']}** | ({x},{y}) — `{tile}`",
            color=discord.Color.orange()
        )
        embed.set_image(url="attachment://map.png")
        embed.set_footer(text="Navigate with arrows, press a tile button to paint the current tile")

        loop = asyncio.get_running_loop()
        buf  = await loop.run_in_executor(None, render_rpg_map, map_id, x, y)

        await interaction.followup.send(
            embed=embed,
            file=discord.File(buf, filename="map.png"),
            view=view,
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(RPGAdmin(bot))
