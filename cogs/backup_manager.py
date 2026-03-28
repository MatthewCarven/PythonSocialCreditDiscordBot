import discord
from discord.ext import commands, tasks
from discord import app_commands
import shutil
import os
from datetime import datetime

class BackupManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "social_credit.db"
        self.backup_dir = "backups"
        self.daily_backup.start()

    def cog_unload(self):
        self.daily_backup.cancel()

    def perform_backup(self):
        """Helper function to handle file copying. Returns (success, full_path)."""
        if not os.path.exists(self.db_path):
            return False, "Database file not found."
            
        os.makedirs(self.backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_filename = f"social_credit_{timestamp}.db"
        backup_path = os.path.join(self.backup_dir, backup_filename)

        try:
            shutil.copy2(self.db_path, backup_path)
            return True, backup_path # We return the full path now so Discord can attach it
        except Exception as e:
            return False, str(e)

    # --- AUTOMATED DAILY BACKUP ---
    @tasks.loop(hours=24)
    async def daily_backup(self):
        success, result = self.perform_backup()
        if success:
            print(f"📦 [DAILY BACKUP SUCCESS] Database secured at: {result}")
        else:
            print(f"🚨 [DAILY BACKUP FAILED] {result}")

    @daily_backup.before_loop
    async def before_daily_backup(self):
        await self.bot.wait_until_ready()

    # --- MANUAL BACKUP & DOWNLOAD COMMAND ---
    @app_commands.command(name="force_backup", description="[ADMIN] Instantly secure a backup of the State's records.")
    @app_commands.describe(download="If True, the bot will attach the backup file for you to download.")
    @app_commands.default_permissions(manage_roles=True)
    async def force_backup(self, interaction: discord.Interaction, download: bool = False):
        await interaction.response.defer(ephemeral=True) # Defer in case uploading takes a moment
        
        success, result = self.perform_backup()
        
        if success:
            embed = discord.Embed(
                title="💾 State Records Secured", 
                description="Manual backup completed successfully.",
                color=discord.Color.green()
            )
            
            if download:
                # Attach the file to the response
                file = discord.File(result)
                await interaction.followup.send(embed=embed, file=file, ephemeral=True)
            else:
                embed.description += f"\n**Saved locally as:** `{result}`"
                await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="🚨 Backup Failed", 
                description=f"The archives could not be secured: {result}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    # --- RESTORE DATABASE COMMAND ---
    @app_commands.command(name="restore_backup", description="[ADMIN] Overwrite the current database with an uploaded backup file.")
    @app_commands.describe(backup_file="The .db file to restore from.")
    @app_commands.default_permissions(manage_roles=True)
    async def restore_backup(self, interaction: discord.Interaction, backup_file: discord.Attachment):
        # 1. Security Check: Ensure it's actually a SQLite database file
        if not backup_file.filename.endswith('.db'):
            await interaction.response.send_message("🚨 **Access Denied:** You must upload a valid `.db` file.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # 2. Overwrite the live database file directly with the downloaded attachment
            await backup_file.save(self.db_path)
            
            embed = discord.Embed(
                title="⏪ Timeline Restored",
                description="The State's records have been successfully overwritten with the provided archive.",
                color=discord.Color.brand_red() # Red for dramatic effect!
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            print(f"⚠️ [WARNING] Database was manually restored by {interaction.user.name}.")
            
        except Exception as e:
            await interaction.followup.send(f"🚨 **Restore Failed:** {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(BackupManager(bot))