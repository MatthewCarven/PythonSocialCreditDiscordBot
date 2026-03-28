import discord
from discord.ext import commands
from discord import app_commands
import asyncio

import rpg_db as db
from views.rpg_views import RPGMapView, render_rpg_map, hp_bar, _inventory_embed, InventoryView


class RPG(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        db.init_db()

    # ------------------------------------------------------------------
    # /rpg start
    # ------------------------------------------------------------------

    @app_commands.command(name="rpg_start", description="Begin your RPG adventure.")
    async def rpg_start(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        server_id = str(interaction.guild.id)
        user_id   = str(interaction.user.id)

        existing = db.get_player(user_id, server_id)
        if existing:
            await interaction.followup.send(
                "You already have an adventurer! Use `/rpg_map` to continue.",
                ephemeral=True
            )
            return

        default_map = db.get_default_map(server_id)
        if not default_map:
            await interaction.followup.send(
                "No maps exist for this server yet. Ask an admin to run `/rpg_admin create_map` first.",
                ephemeral=True
            )
            return

        map_id, name, width, height = default_map
        x, y = width // 2, height // 2

        # Find a passable starting tile near centre
        for radius in range(1, max(width, height)):
            found = False
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    tx, ty = x + dx, y + dy
                    if 0 <= tx < width and 0 <= ty < height:
                        tile = db.get_tile(map_id, tx, ty)
                        if db.TILE_PASSABLE.get(tile, False):
                            x, y = tx, ty
                            found = True
                            break
                if found:
                    break
            if found:
                break

        db.create_player(user_id, server_id, map_id, x, y)
        db.add_to_inventory(user_id, server_id, 'health_potion', 2)
        db.add_to_inventory(user_id, server_id, 'bread', 3)

        loop = asyncio.get_running_loop()
        buf  = await loop.run_in_executor(None, render_rpg_map, map_id, x, y)

        p    = db.get_player(user_id, server_id)
        atk, dfn, hp, max_hp = db.get_effective_stats(user_id, server_id)

        desc = (
            f"**{interaction.user.display_name}** — {hp_bar(hp, max_hp)} {hp}/{max_hp} HP\n"
            f"⚔️ {atk}  🛡️ {dfn}  ⭐ Lv{p['level']}  📍 ({x},{y})\n"
            f"🗺️ **{name}**\n\n"
            f"*Your adventure begins! You start with 2 Health Potions and 3 Bread.*"
        )
        embed = discord.Embed(title="⚔️ RPG", description=desc, color=discord.Color.dark_green())
        embed.set_image(url="attachment://map.png")
        embed.set_footer(text="Move with the arrows • 🔍 Inspect • 🎒 Inventory")

        view = RPGMapView(interaction.user, server_id, map_id, x, y)
        await interaction.followup.send(
            embed=embed,
            file=discord.File(buf, filename="map.png"),
            view=view,
            ephemeral=True
        )

    # ------------------------------------------------------------------
    # /rpg_map
    # ------------------------------------------------------------------

    @app_commands.command(name="rpg_map", description="Open your RPG map.")
    async def rpg_map(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        server_id = str(interaction.guild.id)
        user_id   = str(interaction.user.id)

        p = db.get_player(user_id, server_id)
        if not p:
            await interaction.followup.send("You haven't started yet — use `/rpg_start`.", ephemeral=True)
            return

        map_id = p['map_id']
        x, y   = p['x'], p['y']

        m    = db.get_map(map_id)
        atk, dfn, hp, max_hp = db.get_effective_stats(user_id, server_id)

        desc = (
            f"**{interaction.user.display_name}** — {hp_bar(hp, max_hp)} {hp}/{max_hp} HP\n"
            f"⚔️ {atk}  🛡️ {dfn}  ⭐ Lv{p['level']}  📍 ({x},{y})\n"
            f"🗺️ **{m['name'] if m else map_id}**"
        )
        embed = discord.Embed(title="⚔️ RPG", description=desc, color=discord.Color.dark_green())
        embed.set_image(url="attachment://map.png")
        embed.set_footer(text="Move with the arrows • 🔍 Inspect • 🎒 Inventory")

        loop = asyncio.get_running_loop()
        buf  = await loop.run_in_executor(None, render_rpg_map, map_id, x, y)

        view = RPGMapView(interaction.user, server_id, map_id, x, y)
        await interaction.followup.send(
            embed=embed,
            file=discord.File(buf, filename="map.png"),
            view=view,
            ephemeral=True
        )

    # ------------------------------------------------------------------
    # /rpg_stats
    # ------------------------------------------------------------------

    @app_commands.command(name="rpg_stats", description="View your RPG stats.")
    async def rpg_stats(self, interaction: discord.Interaction):
        p = db.get_player(str(interaction.user.id), str(interaction.guild.id))
        if not p:
            await interaction.response.send_message("Use `/rpg_start` first.", ephemeral=True)
            return

        atk, dfn, hp, max_hp = db.get_effective_stats(interaction.user.id, interaction.guild.id)
        xp_needed = p['level'] * 20
        embed = discord.Embed(title=f"📊 {interaction.user.display_name}", color=discord.Color.blurple())
        embed.add_field(name="Level",   value=f"⭐ {p['level']}")
        embed.add_field(name="XP",      value=f"{p['xp']} / {xp_needed}")
        embed.add_field(name="Gold",    value=f"💰 {p['gold']}")
        embed.add_field(name="HP",      value=f"{hp_bar(hp, max_hp)} {hp}/{max_hp}")
        embed.add_field(name="Attack",  value=f"⚔️ {atk} (base {p['attack']})")
        embed.add_field(name="Defence", value=f"🛡️ {dfn} (base {p['defence']})")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # /rpg_inventory
    # ------------------------------------------------------------------

    @app_commands.command(name="rpg_inventory", description="View your inventory.")
    async def rpg_inventory(self, interaction: discord.Interaction):
        items = db.get_inventory(str(interaction.user.id), str(interaction.guild.id))
        if not items:
            await interaction.response.send_message("Your inventory is empty.", ephemeral=True)
            return
        p    = db.get_player(str(interaction.user.id), str(interaction.guild.id))
        view = InventoryView(interaction.user, str(interaction.guild.id),
                             p['map_id'] if p else None, p['x'] if p else 0, p['y'] if p else 0, items)
        await interaction.response.send_message(embed=_inventory_embed(items), view=view, ephemeral=True)

    # ------------------------------------------------------------------
    # /rpg_use
    # ------------------------------------------------------------------

    @app_commands.command(name="rpg_use", description="Use a consumable item.")
    @app_commands.describe(item_id="The item ID (e.g. health_potion)")
    async def rpg_use(self, interaction: discord.Interaction, item_id: str):
        success, msg = db.use_item(str(interaction.user.id), str(interaction.guild.id), item_id)
        await interaction.response.send_message(msg, ephemeral=True)

    # ------------------------------------------------------------------
    # /rpg_give
    # ------------------------------------------------------------------

    @app_commands.command(name="rpg_give", description="Give an item to another player.")
    @app_commands.describe(
        user="The player to give to",
        item_id="Item ID to give",
        quantity="How many (default 1)"
    )
    async def rpg_give(self, interaction: discord.Interaction, user: discord.Member, item_id: str, quantity: int = 1):
        server_id = str(interaction.guild.id)
        giver_id  = str(interaction.user.id)

        inv = db.get_inventory(giver_id, server_id)
        owned = next((i for i in inv if i['id'] == item_id), None)
        if not owned:
            await interaction.response.send_message(f"You don't have `{item_id}`.", ephemeral=True)
            return
        if owned['quantity'] < quantity:
            await interaction.response.send_message(
                f"You only have {owned['quantity']}x {owned['name']}.", ephemeral=True
            )
            return

        if not db.get_player(str(user.id), server_id):
            await interaction.response.send_message(f"{user.display_name} hasn't started their adventure yet.", ephemeral=True)
            return

        db.remove_from_inventory(giver_id, server_id, item_id, quantity)
        db.add_to_inventory(str(user.id), server_id, item_id, quantity)
        await interaction.response.send_message(
            f"✅ Gave **{owned['name']} x{quantity}** to {user.mention}.", ephemeral=False
        )


async def setup(bot):
    await bot.add_cog(RPG(bot))
