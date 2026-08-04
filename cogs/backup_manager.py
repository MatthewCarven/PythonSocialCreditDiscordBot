import discord
from discord.ext import commands, tasks
from discord import app_commands
import shutil
import os
from datetime import datetime

# Every database the State keeps records in. Backups cover all of them, and
# restore targets are limited to this list so an upload can't land anywhere else.
# Missing files are skipped, so retired databases can stay listed harmlessly.
DB_FILES = ["social_credit.db", "mining.db", "rpg.db", "real_estate_bot.db"]
BACKUP_DIR = "backups"
KEEP_PER_DB = 30  # newest timestamped backups kept per database

SQLITE_MAGIC = b"SQLite format 3\x00"


class BackupManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.daily_backup.start()

    def cog_unload(self):
        self.daily_backup.cancel()

    def perform_backup(self):
        """Copy every existing DB into backups/. Returns (copied_paths, errors)."""
        os.makedirs(BACKUP_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        copied, errors = [], []

        for db in DB_FILES:
            if not os.path.exists(db):
                continue
            stem = os.path.splitext(db)[0]
            dest = os.path.join(BACKUP_DIR, f"{stem}_{timestamp}.db")
            try:
                shutil.copy2(db, dest)
                copied.append(dest)
            except Exception as e:
                errors.append(f"{db}: {e}")

        self.prune_backups()
        return copied, errors

    def prune_backups(self):
        """Keep only the newest KEEP_PER_DB timestamped backups per database.
        Pre-restore safety snapshots (pre-restore_*) are never pruned."""
        if not os.path.isdir(BACKUP_DIR):
            return
        files = os.listdir(BACKUP_DIR)
        for db in DB_FILES:
            prefix = os.path.splitext(db)[0] + "_"
            # Timestamps are fixed-width, so a lexical sort is a date sort.
            matches = sorted(
                f for f in files
                if f.startswith(prefix) and f.endswith(".db")
            )
            for old in matches[:-KEEP_PER_DB]:
                try:
                    os.remove(os.path.join(BACKUP_DIR, old))
                except OSError:
                    pass

    # --- AUTOMATED DAILY BACKUP ---
    @tasks.loop(hours=24)
    async def daily_backup(self):
        copied, errors = self.perform_backup()
        if copied:
            print(f"📦 [DAILY BACKUP] {len(copied)} database(s) secured in {BACKUP_DIR}/")
        for err in errors:
            print(f"🚨 [DAILY BACKUP FAILED] {err}")

    @daily_backup.before_loop
    async def before_daily_backup(self):
        await self.bot.wait_until_ready()

    # --- MANUAL BACKUP & DOWNLOAD COMMAND ---
    @app_commands.command(name="force_backup", description="[ADMIN] Instantly secure a backup of the State's records.")
    @app_commands.describe(download="If True, the bot will attach the backup files for you to download.")
    @app_commands.default_permissions(manage_roles=True)
    async def force_backup(self, interaction: discord.Interaction, download: bool = False):
        await interaction.response.defer(ephemeral=True)  # Defer in case uploading takes a moment

        copied, errors = self.perform_backup()

        if copied:
            names = "\n".join(f"`{path}`" for path in copied)
            embed = discord.Embed(
                title="💾 State Records Secured",
                description=f"Backed up {len(copied)} database(s):\n{names}",
                color=discord.Color.green(),
            )
            if errors:
                embed.add_field(name="⚠️ Partial failures", value="\n".join(errors), inline=False)

            if download:
                files = [discord.File(path) for path in copied]
                await interaction.followup.send(embed=embed, files=files, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="🚨 Backup Failed",
                description="The archives could not be secured:\n" + ("\n".join(errors) or "No database files found."),
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    # --- RESTORE DATABASE COMMAND ---
    @app_commands.command(name="restore_backup", description="[ADMIN] Overwrite a database with an uploaded backup file.")
    @app_commands.describe(
        target="Which database to overwrite.",
        backup_file="The .db file to restore from.",
    )
    @app_commands.choices(target=[app_commands.Choice(name=db, value=db) for db in DB_FILES])
    @app_commands.default_permissions(manage_roles=True)
    async def restore_backup(
        self,
        interaction: discord.Interaction,
        target: app_commands.Choice[str],
        backup_file: discord.Attachment,
    ):
        await interaction.response.defer(ephemeral=True)

        data = await backup_file.read()
        # Check the actual file contents, not just the filename.
        if not data.startswith(SQLITE_MAGIC):
            await interaction.followup.send(
                "🚨 **Access Denied:** That file is not a SQLite database. Restore aborted.",
                ephemeral=True,
            )
            return

        db_path = target.value
        try:
            # Safety net: snapshot the current file before overwriting it.
            # The pre-restore_ prefix keeps these out of the pruning sweep.
            if os.path.exists(db_path):
                os.makedirs(BACKUP_DIR, exist_ok=True)
                ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                stem = os.path.splitext(db_path)[0]
                shutil.copy2(db_path, os.path.join(BACKUP_DIR, f"pre-restore_{stem}_{ts}.db"))

            with open(db_path, "wb") as f:
                f.write(data)

            embed = discord.Embed(
                title="⏪ Timeline Restored",
                description=(
                    f"`{db_path}` has been overwritten with the provided archive.\n"
                    f"The previous version was snapshotted to `{BACKUP_DIR}/` first."
                ),
                color=discord.Color.brand_red(),  # Red for dramatic effect!
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            print(f"⚠️ [WARNING] {db_path} was manually restored by {interaction.user.name}.")

        except Exception as e:
            await interaction.followup.send(f"🚨 **Restore Failed:** {e}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(BackupManager(bot))
