import discord
import os
import sys
import json
import asyncio
import hashlib
import logging
import logging.handlers
from discord.ext import commands
from dotenv import load_dotenv
from database import CreditDB
from messages import random_wrong_channel_message, random_bot_channel_message

# Anchor all relative paths (.env, cogs/, *.db) to this file's folder,
# so the bot behaves the same no matter which directory it's launched from.
os.chdir(os.path.dirname(os.path.abspath(__file__)))

LOG_FILE = "bot.log"
COMMAND_HASH_FILE = ".command_hash"


def _setup_logging():
    """Console + rotating file. All cogs and discord.py's own loggers
    propagate to root, so everything lands in bot.log as well."""
    # Windows consoles often default to cp1252, which can't print the emoji
    # used in log messages — replace rather than crash.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)


_setup_logging()
log = logging.getLogger("socialcreditbot")

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise SystemExit("DISCORD_TOKEN is not set — create a .env file containing DISCORD_TOKEN=<your bot token>.")

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
        log.info("--- Loading Cogs ---")
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    # Strip .py and load as a module
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    log.info("✅ Loaded: %s", filename)
                except Exception:
                    log.exception("❌ Failed to load %s", filename)

        await self._sync_commands_if_changed()

    async def _sync_commands_if_changed(self):
        """Global-sync the command tree only when it changed since last boot.

        Global syncs are rate-limited and slow to propagate, so we fingerprint
        the registered commands and skip the call when nothing changed.
        Delete the .command_hash file and restart to force a sync.
        """
        try:
            payload = [cmd.to_dict(self.tree) for cmd in self.tree.get_commands()]
        except TypeError:  # discord.py < 2.4: to_dict() takes no tree argument
            payload = [cmd.to_dict() for cmd in self.tree.get_commands()]
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

        previous = None
        if os.path.exists(COMMAND_HASH_FILE):
            with open(COMMAND_HASH_FILE) as f:
                previous = f.read().strip()

        if digest == previous:
            log.info("Command tree unchanged — skipping global sync.")
            return

        await self.tree.sync()
        with open(COMMAND_HASH_FILE, "w") as f:
            f.write(digest)
        log.info("Command tree synced globally (%d top-level commands).", len(payload))

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
                    await interaction.channel.send(f"🚨 State Violation by {interaction.user.mention}! {random_wrong_channel_message()} **{abs(penalty):,.1f}** credit penalty applied. The fine has been added to the slush fund. New social standing: **{new_score:,.1f}**")
                except discord.Forbidden:
                    log.warning("Could not send penalty message in channel '%s' due to missing permissions.", interaction.channel.name)

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
                    await message.channel.send(f"🚨 State Violation by {message.author.mention}! {random_bot_channel_message()} **{abs(penalty):,.1f}** credit penalty applied. The fine has been added to the slush fund. New social standing: **{new_score:,.1f}**")
                except discord.Forbidden:
                    log.warning("Could not send penalty message in channel '%s' due to missing permissions.", message.channel.name)

        # Ensure prefix commands (if any) still work
        await self.process_commands(message)

    async def on_ready(self):
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id)

bot = MyBot()

async def main():
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())