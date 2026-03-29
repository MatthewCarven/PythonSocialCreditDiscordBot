import discord
from discord.ext import commands
import json

class PermManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._load_tiers()

    def _load_tiers(self):
        with open('tiers.json', 'r') as f:
            self.tiers = json.load(f)
            # Sort positive tiers by threshold ascending, negative by threshold descending
            self.tiers['positive'].sort(key=lambda x: x['threshold'])
            self.tiers['negative'].sort(key=lambda x: x['threshold'], reverse=True)
        # Create a flat list of all tier names for easier role management
        self.tier_role_names = [t['name'] for t in self.tiers['positive']] + [t['name'] for t in self.tiers['negative']] + ["Unverified Resident"]


    def get_tier_for_score(self, xp):
        """Determine the tier name for a given XP score."""
        if xp >= 0:
            tier_name = "Unverified Resident"
            for tier in self.tiers['positive']:
                if xp >= tier['threshold']:
                    tier_name = tier['name']
                else:
                    break
            return tier_name
        else: # xp < 0
            tier_name = "Suspicious Element"
            for tier in self.tiers['negative']:
                if xp <= tier['threshold']:
                    tier_name = tier['name']
                else:
                    break
            return tier_name

    @commands.Cog.listener()
    async def on_social_credit_change(self, member: discord.Member, new_score: float):
        guild = member.guild
        
        # 1. Determine the correct tier for the new score
        new_tier_name = self.get_tier_for_score(new_score)
        
        # 2. Find the role object for the new tier
        target_role = discord.utils.get(guild.roles, name=new_tier_name)
        if not target_role:
            print(f"⚠️ [Role Not Found] The role '{new_tier_name}' does not exist in '{guild.name}'. Cannot assign.")
            return

        # 3. Get a list of all tier roles the user currently has
        current_tier_roles = [role for role in member.roles if role.name in self.tier_role_names]

        # 4. If the user already has the correct role and no others, do nothing.
        if len(current_tier_roles) == 1 and current_tier_roles[0] == target_role:
            return
            
        # 5. Remove all existing tier roles from the user
        try:
            if current_tier_roles:
                await member.remove_roles(*current_tier_roles, reason="Social Credit Tier Change")
        except discord.Forbidden:
            print(f"🚨 [Permissions Error] Bot lacks permissions to remove roles in '{guild.name}'.")
            return
        except discord.HTTPException as e:
            print(f"🚨 [HTTP Error] Failed to remove roles: {e}")
            return
            
        # 6. Add the correct new role
        try:
            await member.add_roles(target_role, reason=f"Social Credit score reached {new_score:,.1f}")
            print(f"✅ Role '{target_role.name}' assigned to {member.display_name} in '{guild.name}'.")
        except discord.Forbidden:
            print(f"🚨 [Permissions Error] Bot lacks permissions to add roles in '{guild.name}'.")
        except discord.HTTPException as e:
            print(f"🚨 [HTTP Error] Failed to add role: {e}")

async def setup(bot):
    await bot.add_cog(PermManager(bot))