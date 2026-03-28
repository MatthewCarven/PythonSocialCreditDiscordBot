import discord
from discord.ext import commands
import sqlite3
import asyncio
from discord import app_commands
import io
import random
from views.real_estate_views import (
    MapNavigation, WorldResetView, EMOJI_MAP,
    generate_map_image, render_viewport_image,
    GENERATION_TYPES, generate_world,
)


class RealEstate(commands.Cog):
    def __init__(self, bot):
        self.bot     = bot
        self.db_path = 'real_estate_bot.db'
        self.init_database()

    def init_database(self):
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS world_map (
                    x INTEGER,
                    y INTEGER,
                    tile_type INTEGER,
                    owner_id TEXT,
                    PRIMARY KEY (x, y)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    balance INTEGER DEFAULT 1000
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS last_location (
                    user_id TEXT PRIMARY KEY,
                    x INTEGER,
                    y INTEGER
                )
            """)
            con.commit()

    # ------------------------------------------------------------------
    # /map
    # ------------------------------------------------------------------

    @app_commands.command(name="map", description="Shows the world map.")
    async def map(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute(
                "SELECT x, y FROM last_location WHERE user_id = ?",
                (str(interaction.user.id),)
            )
            location = cur.fetchone()
            if location:
                x, y = location
            else:
                import views.real_estate_views as rev
                x, y = rev.WORLD_WIDTH // 2, rev.WORLD_HEIGHT // 2
                cur.execute(
                    "INSERT OR REPLACE INTO last_location (user_id, x, y) VALUES (?, ?, ?)",
                    (str(interaction.user.id), x, y)
                )
                con.commit()

        import views.real_estate_views as rev
        loop = asyncio.get_running_loop()
        buf  = await loop.run_in_executor(None, render_viewport_image, x, y)

        embed = discord.Embed(
            title="🗺️ World Map",
            description=(
                f"**Citizen:** {interaction.user.mention}\n"
                f"**Location:** ({x}, {y})  |  **World:** {rev.WORLD_TYPE.title()}  |  **Seed:** `{rev.SEED}`"
            ),
            color=discord.Color.green()
        )
        embed.set_image(url="attachment://viewport.png")
        embed.set_footer(text="Use the navigation buttons to explore the world")

        view = MapNavigation(self.db_path, interaction.user, x, y)
        await interaction.followup.send(
            embed=embed,
            file=discord.File(buf, filename="viewport.png"),
            view=view,
            ephemeral=True
        )

    # ------------------------------------------------------------------
    # /map_image
    # ------------------------------------------------------------------

    @app_commands.command(name="map_image", description="Generates a PNG overview of the world map centered on your location.")
    async def map_image(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute(
                "SELECT x, y FROM last_location WHERE user_id = ?",
                (str(interaction.user.id),)
            )
            loc = cur.fetchone()
            x, y = loc if loc else (50, 50)

        loop = asyncio.get_running_loop()
        buf  = await loop.run_in_executor(None, generate_map_image, x, y, 75)

        await interaction.followup.send(
            content=f"🗺️ World map centered on **({x}, {y})**",
            file=discord.File(buf, filename="map.png"),
            ephemeral=True
        )

    # ------------------------------------------------------------------
    # /map_image_super
    # ------------------------------------------------------------------

    @app_commands.command(name="map_image_super", description="Generates a large PNG overview of the world map.")
    async def map_image_super(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute(
                "SELECT x, y FROM last_location WHERE user_id = ?",
                (str(interaction.user.id),)
            )
            loc = cur.fetchone()
            x, y = loc if loc else (50, 50)

        loop = asyncio.get_running_loop()
        buf  = await loop.run_in_executor(None, generate_map_image, x, y, 150)

        await interaction.followup.send(
            content=f"🗺️ World map centered on **({x}, {y})**",
            file=discord.File(buf, filename="map.png"),
            ephemeral=True
        )

    # ------------------------------------------------------------------
    # /reset_world
    # ------------------------------------------------------------------

    @app_commands.command(
        name="reset_world",
        description="[ADMIN] Wipes the world map and generates a fresh world."
    )
    @app_commands.describe(
        seed="Optional seed (0–999999). Omit for random.",
        generation_type="World generation style. Omit for random.",
        size="World size (width and height in tiles). Default 500."
    )
    @app_commands.choices(generation_type=[
        app_commands.Choice(name="Continental", value="continental"),
        app_commands.Choice(name="Archipelago", value="archipelago"),
        app_commands.Choice(name="Pangaea",     value="pangaea"),
        app_commands.Choice(name="Frozen",      value="frozen"),
        app_commands.Choice(name="Scorched",    value="scorched"),
        app_commands.Choice(name="Volatile",    value="volatile"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def reset_world(
        self,
        interaction: discord.Interaction,
        seed: int = None,
        generation_type: str = None,
        size: int = 500
    ):
        await interaction.response.defer(ephemeral=True)

        import views.real_estate_views as rev
        loop = asyncio.get_running_loop()
        actual_seed = await loop.run_in_executor(
            None, generate_world, self.db_path, size, size,
            seed if seed is not None else None,
            generation_type if generation_type is not None else random.choice(list(GENERATION_TYPES.keys()))
        )
        new_seed = actual_seed
        new_type = rev.WORLD_TYPE

        buf         = await loop.run_in_executor(None, generate_map_image, size // 2, size // 2, 150)
        image_bytes = buf.read()

        view = WorldResetView(self.db_path, new_seed, new_type, image_bytes)
        await interaction.followup.send(
            content=f"🌍 World reset! ({size}×{size})\n**Seed:** `{new_seed}`\n**Type:** {new_type.title()}\n\nAccept to announce to the channel, or reroll for a new world.",
            file=discord.File(io.BytesIO(image_bytes), filename="new_world.png"),
            view=view,
            ephemeral=True
        )

    # ------------------------------------------------------------------
    # /tile_leaderboard
    # ------------------------------------------------------------------

    @app_commands.command(name="tile_leaderboard", description="Shows the leaderboard of tile owners.")
    async def tile_leaderboard(self, interaction: discord.Interaction):
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("""
                SELECT owner_id, tile_type, COUNT(*)
                FROM world_map
                WHERE owner_id IS NOT NULL
                GROUP BY owner_id, tile_type
                ORDER BY owner_id, tile_type
            """)
            leaderboard_data = cur.fetchall()

        if not leaderboard_data:
            await interaction.response.send_message("No tiles are owned yet.")
            return

        embed = discord.Embed(title="Tile Leaderboard", color=discord.Color.gold())

        current_owner = None
        owner_data    = []

        for owner_id, tile_type, count in leaderboard_data:
            if owner_id != current_owner:
                if current_owner is not None:
                    try:
                        user = await self.bot.fetch_user(int(current_owner))
                        user_name = user.display_name
                    except discord.NotFound:
                        user_name = f"Unknown User (ID: {current_owner})"

                    field_value = "\n".join(
                        [f"{EMOJI_MAP.get(tt, '❓')}: {c}" for tt, c in owner_data]
                    )
                    embed.add_field(name=user_name, value=field_value, inline=False)

                current_owner = owner_id
                owner_data    = []

            owner_data.append((tile_type, count))

        if current_owner is not None:
            try:
                user = await self.bot.fetch_user(int(current_owner))
                user_name = user.display_name
            except discord.NotFound:
                user_name = f"Unknown User (ID: {current_owner})"
            field_value = "\n".join(
                [f"{EMOJI_MAP.get(tt, '❓')}: {c}" for tt, c in owner_data]
            )
            embed.add_field(name=user_name, value=field_value, inline=False)

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(RealEstate(bot))
