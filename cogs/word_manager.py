import discord
from discord.ext import commands
from discord import app_commands
from database import CreditDB

db = CreditDB()

class WordManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- Banned Word Commands ---
    @app_commands.command(name="add_banned_word", description="[ADMIN] Add a word to the banned list.")
    @app_commands.describe(word="The word to ban", penalty="The amount of credit to remove")
    @app_commands.default_permissions(manage_roles=True)
    async def add_banned_word(self, interaction: discord.Interaction, word: str, penalty: float):
        if penalty > 0:
            penalty = -penalty # Ensure penalty is negative
        db.add_banned_word(interaction.guild.id, word, penalty)
        await interaction.response.send_message(f"The word '{word}' has been banned with a penalty of {penalty} credits.", ephemeral=True)

    @app_commands.command(name="remove_banned_word", description="[ADMIN] Remove a word from the banned list.")
    @app_commands.describe(word="The word to unban")
    @app_commands.default_permissions(manage_roles=True)
    async def remove_banned_word(self, interaction: discord.Interaction, word: str):
        if db.remove_banned_word(interaction.guild.id, word):
            await interaction.response.send_message(f"The word '{word}' has been unbanned.", ephemeral=True)
        else:
            await interaction.response.send_message(f"The word '{word}' was not found in the banned list.", ephemeral=True)

    @app_commands.command(name="list_banned_words", description="[ADMIN] List all banned words.")
    @app_commands.default_permissions(manage_roles=True)
    async def list_banned_words(self, interaction: discord.Interaction):
        banned_words = db.get_banned_words(interaction.guild.id)
        if not banned_words:
            await interaction.response.send_message("There are no banned words in this server.", ephemeral=True)
            return

        embed = discord.Embed(title="Banned Words", color=discord.Color.red())
        for word, penalty in banned_words:
            embed.add_field(name=word, value=f"Penalty: {penalty}", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- Praised Word Commands ---
    @app_commands.command(name="add_praised_word", description="[ADMIN] Add a word to the praised list.")
    @app_commands.describe(word="The word to praise", reward="The amount of credit to add")
    @app_commands.default_permissions(manage_roles=True)
    async def add_praised_word(self, interaction: discord.Interaction, word: str, reward: float):
        if reward < 0:
            reward = -reward # Ensure reward is positive
        db.add_praised_word(interaction.guild.id, word, reward)
        await interaction.response.send_message(f"The word '{word}' has been praised with a reward of {reward} credits.", ephemeral=True)

    @app_commands.command(name="remove_praised_word", description="[ADMIN] Remove a word from the praised list.")
    @app_commands.describe(word="The word to unpraise")
    @app_commands.default_permissions(manage_roles=True)
    async def remove_praised_word(self, interaction: discord.Interaction, word: str):
        if db.remove_praised_word(interaction.guild.id, word):
            await interaction.response.send_message(f"The word '{word}' has been unpraised.", ephemeral=True)
        else:
            await interaction.response.send_message(f"The word '{word}' was not found in the praised list.", ephemeral=True)

    @app_commands.command(name="list_praised_words", description="[ADMIN] List all praised words.")
    @app_commands.default_permissions(manage_roles=True)
    async def list_praised_words(self, interaction: discord.Interaction):
        praised_words = db.get_praised_words(interaction.guild.id)
        if not praised_words:
            await interaction.response.send_message("There are no praised words in this server.", ephemeral=True)
            return

        embed = discord.Embed(title="Praised Words", color=discord.Color.green())
        for word, reward in praised_words:
            embed.add_field(name=word, value=f"Reward: {reward}", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- Channel Settings ---
    @app_commands.command(name="set_bot_channel", description="[ADMIN] Set the channel for bot announcements.")
    @app_commands.describe(channel="The channel to send announcements to")
    @app_commands.default_permissions(manage_roles=True)
    async def set_bot_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        db.set_output_channel(interaction.guild.id, channel.id)
        await interaction.response.send_message(f"Bot announcements will now be sent to {channel.mention}.", ephemeral=True)

    @app_commands.command(name="clear_bot_channel", description="[ADMIN] Clear the announcement channel setting.")
    @app_commands.default_permissions(manage_roles=True)
    async def clear_bot_channel(self, interaction: discord.Interaction):
        db.set_output_channel(interaction.guild.id, None)
        await interaction.response.send_message("Bot announcements will now be sent to the channel where commands are used.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(WordManager(bot))
