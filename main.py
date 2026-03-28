import discord
import os
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from database import CreditDB
from messages import random_wrong_channel_message, random_bot_channel_message

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

class MyBot(commands.Bot):
    def __init__(self):
        # Start with standard intents, then specifically enable the two we need
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(command_prefix="/", intents=intents)
        self.db = CreditDB()

    async def setup_hook(self):
        """This runs before the bot connects to Discord."""
        print("--- Loading Cogs ---")
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    # Strip .py and load as a module
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f'✅ Loaded: {filename}')
                except Exception as e:
                    print(f'❌ Failed to load {filename}: {e}')
        
        # Sync slash commands globally
        await self.tree.sync()
        print("--- Syncing Complete ---")

    async def on_interaction(self, interaction: discord.Interaction):
        # We only care about slash commands for this check
        if interaction.type == discord.InteractionType.application_command and interaction.guild is not None:
            output_channel_id = self.db.get_output_channel(interaction.guild.id)
            
            # If a designated channel exists AND this command is used outside of it
            if output_channel_id and interaction.channel_id != output_channel_id:
                penalty = -1.0
                user_id = interaction.user.id
                guild_id = interaction.guild.id
                
                # Apply penalty and add to slush fund
                self.db.update_credit(user_id, guild_id, penalty)
                self.db.add_to_slush_fund(guild_id, abs(penalty))
                new_score = self.db.get_credit(user_id, guild_id)
                
                # Dispatch event for other cogs (like perm_manager) to pick up the change
                self.dispatch("social_credit_change", interaction.user, new_score)
                
                try:
                    # Announce the penalty in the channel where the infraction occurred
                    await interaction.channel.send(f"🚨 State Violation by {interaction.user.mention}! {random_wrong_channel_message()} **{abs(penalty):.1f}** credit penalty applied. The fine has been added to the slush fund. New social standing: **{new_score:.1f}**")
                except discord.Forbidden:
                    print(f"WARNING: Could not send penalty message in channel '{interaction.channel.name}' due to missing permissions.")

        # CRUCIAL: This must be the last line. It ensures the bot actually processes
        # the command after our custom logic has run.
        await self.process_application_commands(interaction)

    async def on_message(self, message: discord.Message):
        # Ignore messages from bots (including ourselves)
        if message.author.bot:
            return

        if message.guild is not None:
            output_channel_id = self.db.get_output_channel(message.guild.id)

            # If a designated bot channel exists AND this message is in it AND it's not a command
            if output_channel_id and message.channel.id == output_channel_id and not message.content.startswith(self.command_prefix):
                penalty = -1.0
                user_id = message.author.id
                guild_id = message.guild.id

                self.db.update_credit(user_id, guild_id, penalty)
                self.db.add_to_slush_fund(guild_id, abs(penalty))
                new_score = self.db.get_credit(user_id, guild_id)

                self.dispatch("social_credit_change", message.author, new_score)

                try:
                    await message.channel.send(f"🚨 State Violation by {message.author.mention}! {random_bot_channel_message()} **{abs(penalty):.1f}** credit penalty applied. The fine has been added to the slush fund. New social standing: **{new_score:.1f}**")
                except discord.Forbidden:
                    print(f"WARNING: Could not send penalty message in channel '{message.channel.name}' due to missing permissions.")

        # Ensure prefix commands (if any) still work
        await self.process_commands(message)

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

bot = MyBot()

async def main():
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())