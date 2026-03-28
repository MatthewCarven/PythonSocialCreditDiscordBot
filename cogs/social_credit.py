import discord
from discord.ext import commands
from discord import app_commands
import math
import sqlite3
import random
import json
from database import CreditDB # Imports your DB class
from mining_db import MiningDB
from messages import random_fine_message, random_banned_word_message, random_earn_message, random_leaderboard_message

db = CreditDB()
mdb = MiningDB()





# Drop this class above your SocialCredit cog class
class WorkAssignment(discord.ui.View):
    def __init__(self, cog, user, level, multiplier=1.0):
        super().__init__(timeout=60) 
        self.cog = cog
        self.user = user
        self.level = level 
        self.multiplier = multiplier # This shrinks the payout for grind commands!

    @discord.ui.button(label="Report & Comply", style=discord.ButtonStyle.success, emoji="🏭")
    async def honest_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚨 This is not your assignment, citizen.", ephemeral=True)
            return

        bonus = max(0, self.level) * 0.2
        # Apply the multiplier to the final amount
        amount = round((random.uniform(0.5, 1.5) + bonus) * self.multiplier, 1)

        db.update_credit(interaction.user.id, interaction.guild.id, amount)
        new_score = db.get_credit(interaction.user.id, interaction.guild.id)
        self.cog.bot.dispatch("social_credit_change", interaction.user, new_score)

        embed = discord.Embed(
            title="🏭 Honest Labor Completed",
            description=f"You dutifully served the State and earned **{amount}** credits.",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"New Social Standing: {new_score:.1f}")

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Falsify & Skim", style=discord.ButtonStyle.danger, emoji="🤫")
    async def risky_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚨 Mind your own business, citizen.", ephemeral=True)
            return

        success = random.choice([True, False])

        if success:
            bonus = max(0, self.level) * 1.0
            # Apply the multiplier to the reward
            amount = round((random.uniform(3.0, 5.0) + bonus) * self.multiplier, 1)
            db.update_credit(interaction.user.id, interaction.guild.id, amount)
            new_score = db.get_credit(interaction.user.id, interaction.guild.id)
            self.cog.bot.dispatch("social_credit_change", interaction.user, new_score)
            title = "🤫 Under-the-Table Deal"
            description = f"You manipulated the system perfectly. You gained **{amount}** credits."
            color = discord.Color.dark_gold()
            embed = discord.Embed(title=title, description=description, color=color)
            embed.set_footer(text=f"New Social Standing: {new_score:.1f}")

        else:
            penalty_multiplier = max(1, self.level) * 4.0 
            # Apply the multiplier to the punishment
            amount = round((random.uniform(2.0, 5.0) + penalty_multiplier) * self.multiplier, 1)
            db.add_to_slush_fund(interaction.guild.id, amount)
            db.update_credit(interaction.user.id, interaction.guild.id, -amount)
            new_score = db.get_credit(interaction.user.id, interaction.guild.id)
            self.cog.bot.dispatch("social_credit_change", interaction.user, new_score)
            title = "🚨 Corruption Detected!"
            description = f"The State caught your treasonous act! You have been fined **{abs(amount)}** credits. The fine has been added to the slush fund."
            color = discord.Color.red()
            embed = discord.Embed(title=title, description=description, color=color)
            embed.set_footer(text=f"{random_fine_message()} | Current Social Standing: {new_score:.1f}")

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)





class HelpDropdown(discord.ui.Select):
    def __init__(self, cog):
        self.cog = cog
        # Define the options for the dropdown menu
        options = [
            discord.SelectOption(label="General Overview", description="How the Social Credit system works.", emoji="ℹ️", value="general"),
            discord.SelectOption(label="Labor & Economy", description="How to earn (or lose) credits.", emoji="🏭", value="economy"),
            discord.SelectOption(label="The Tier List", description="View the official social hierarchy.", emoji="📊", value="tiers"),
            discord.SelectOption(label="User & Credit Admin", description="State Enforcer commands for managing users.", emoji="⚖️", value="user_admin"),
            discord.SelectOption(label="Word Management", description="Admin commands for managing keywords.", emoji="✍️", value="word_admin"),
            discord.SelectOption(label="Database Management", description="Admin commands for backups and restores.", emoji="💾", value="db_admin")
        ]
        super().__init__(placeholder="Select a chapter of the State Manual...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selection = self.values[0]
        embed = discord.Embed(color=discord.Color.blue())
        
        if selection == "general":
            embed.title = "ℹ️ Social Credit System"
            embed.description = "Welcome to the State. Your worth is measured in Social Credit.\n\nYou earn a passive **+0.1 credit** for every message you send. Good behavior allows you to climb the ranks, but poor behavior or corruption will drag you into the negative tiers."
            embed.add_field(name="Basic Commands", value="`/profile` - Check your current status and rank\n`/leaderboard` - View the most compliant (and least compliant) citizens\n`/daily_ration` - Claim your free daily credit allowance\n`/give` - Transfer your credits to another citizen.")
        
        elif selection == "economy":
            embed.title = "🏭 Labor & Economy"
            embed.description = "Citizens are expected to contribute. You can perform tasks to earn credits, but beware the temptation to falsify records."
            embed.add_field(name="Major Labor (1 Hour Cooldown)", value="`/work` - Standard labor with standard payouts.", inline=False)
            base_grind_cmds = '`, `'.join(self.cog.grind_tasks[:4]) + '`...'
            embed.add_field(name=f"Minor Tasks (1 Hour Cooldown, 10% Payout)", value=f"`/{base_grind_cmds}`", inline=False)
            embed.add_field(name="High-Risk / Gambling", value="`/heist <user>` - Attempt to steal from another citizen.\n`/coinflip <amount> <guess>` - Bet credits on a coin toss.", inline=False)
            embed.set_footer(text="Warning: Getting caught skimming credits scales based on your rank.")

        elif selection == "tiers":
            embed.title = "📊 Official State Hierarchy"
            
            positive_tiers = " ➝ ".join([tier['name'] for tier in self.cog.tiers['positive']])
            negative_tiers = " ➝ ".join([tier['name'] for tier in self.cog.tiers['negative']])
            
            embed.description = f"**Positive Tiers:**\n{positive_tiers}\n\n**Negative Tiers:**\n{negative_tiers}"
            embed.set_footer(text="Your role will be updated automatically as you cross thresholds.")

        elif selection == "user_admin":
            embed.title = "⚖️ User & Credit Admin"
            embed.description = "Only authorized personnel may use these commands."
            embed.color = discord.Color.dark_red()
            embed.add_field(name="/adjust_credit <user> <amount>", value="Manually add or subtract points from a citizen. Use negative numbers for penalties.", inline=False)
            embed.add_field(name="/reset_score <user>", value="Reset a citizen's Social Credit to 0.", inline=False)

        elif selection == "word_admin":
            embed.title = "✍️ Word Management"
            embed.description = "Commands to manage words that grant or remove credits."
            embed.color = discord.Color.dark_red()
            embed.add_field(name="Banned Words", value="`/add_banned_word <word> <penalty>`\n`/remove_banned_word <word>`\n`/list_banned_words`", inline=False)
            embed.add_field(name="Praised Words", value="`/add_praised_word <word> <reward>`\n`/remove_praised_word <word>`\n`/list_praised_words`", inline=False)
            embed.add_field(name="Channel Control", value="`/set_bot_channel <channel>`\n`/clear_bot_channel`", inline=False)

        elif selection == "db_admin":
            embed.title = "💾 Database Management"
            embed.description = "Commands to manage the database."
            embed.color = discord.Color.dark_red()
            embed.add_field(name="/force_backup [download]", value="Create a manual backup of the database, with an option to download it.", inline=False)
            embed.add_field(name="/restore_backup <file>", value="Overwrite the live database with an uploaded `.db` backup file. **USE WITH CAUTION.**", inline=False)


        # Update the message with the newly selected embed
        await interaction.response.edit_message(embed=embed)

class HelpView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=120) # Menu stays active for 2 minutes
        self.add_item(HelpDropdown(cog))






class SocialCredit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.grind_tasks = [
            "toil", "audit", "grind", "labor", "drudge", "slog",
            "inspect", "patrol", "clean", "repair", "compile", "process", 
            "file", "sort", "censor", "monitor", "report", "construct", 
            "fabricate", "transcribe", "excavate"
        ]
        self._load_tiers()
        self._create_grind_commands()

    def _create_grind_commands(self):
        # This error handler is defined once and reused for all grind commands
        async def on_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
            if isinstance(error, app_commands.CommandOnCooldown):
                mins_left = error.retry_after / 60
                await interaction.response.send_message(f"🚨 The State demands patience. Also we remind you that greed is a crime against the state.  Try this specific task again in **{mins_left:.1f} minutes**.", ephemeral=True)

        for task_name in self.grind_tasks:
            # A factory is needed to correctly capture the task_name for the callback
            def command_factory(name):
                async def command_callback(interaction: discord.Interaction):
                    await self.trigger_work_scenario(interaction, task_name=name, multiplier=0.1)
                return command_callback

            callback = command_factory(task_name)
            
            # Create the slash command
            cmd = app_commands.Command(
                name=task_name,
                description=f"Perform the '{task_name}' minor task. (10% Payout)",
                callback=callback
            )
            # Add cooldown
            cmd = app_commands.checks.cooldown(1, 3600, key=lambda i: (i.guild_id, i.user.id))(cmd)
            
            # Attach the shared error handler
            cmd.error(on_error)
            
            # Add the command to the cog
            self.bot.tree.add_command(cmd, guild=None) # Add as global command

    def _load_tiers(self):
        with open('tiers.json', 'r') as f:
            self.tiers = json.load(f)
            # Sort positive tiers by threshold ascending, negative by threshold descending
            self.tiers['positive'].sort(key=lambda x: x['threshold'])
            self.tiers['negative'].sort(key=lambda x: x['threshold'], reverse=True)

    def get_social_status(self, xp):
        if xp >= 0:
            level = 0
            tier_name = "Unverified Resident"
            for i, tier in enumerate(self.tiers['positive']):
                if xp >= tier['threshold']:
                    tier_name = tier['name']
                    level = i + 1
                else:
                    break
            return tier_name, level
        else: # xp < 0
            level = 0
            tier_name = "Suspicious Element" # Default for any negative score
            for i, tier in enumerate(self.tiers['negative']):
                if xp <= tier['threshold']:
                    tier_name = tier['name']
                    level = -(i + 1)
                else:
                    break
            return tier_name, level

    async def _get_output_channel(self, interaction: discord.Interaction = None, message: discord.Message = None):
        guild = interaction.guild if interaction else message.guild
        channel_id = db.get_output_channel(guild.id)
        if channel_id:
            return guild.get_channel(channel_id)
        return interaction.channel if interaction else message.channel



# --- WORK COMMAND (Risk/Reward Mechanics) ---
    async def trigger_work_scenario(self, interaction: discord.Interaction, task_name: str, multiplier: float):
        """A shared function so we don't have to duplicate code for every command."""
        xp = db.get_credit(interaction.user.id, interaction.guild.id)
        _, level = self.get_social_status(xp)

        scenarios = [
            "You notice a shipping manifest has a discrepancy of 50 synthetic rations.",
            "A fellow citizen dropped a blank, unrecorded credit voucher in the hallway.",
            "The surveillance camera briefly reboots while you are counting the daily treasury tokens.",
            "You are asked to process a highly suspicious credit transfer for a low-ranking official.",
            "You find an unsecured terminal logged directly into the State Resource Vault.",
            "A deceased citizen's asset reallocation form is sitting on your desk, completely unsupervised.",
            "You are tasked with transporting a surplus of confiscated luxury goods to the incinerator.",
            "The automated ration dispenser malfunctions, spitting out unlogged credits onto the floor.",
            "You discover an accounting error that leaves a localized budget unaccounted for.",
            "A black-market merchant offers you a bribe to alter their monthly resource quota.",
            "You stumble upon a hidden cache of unsanctioned, high-grade machine parts.",
            "Your supervisor leaves their administrative access keycard next to an open ledger."
        ]
        
        
        scenario = random.choice(scenarios)

        embed = discord.Embed(
            title=f"📋 Task: {task_name.capitalize()}",
            description=f"**Scenario:** {scenario}\n\nHow do you wish to proceed?",
            color=discord.Color.blue()
        )

        view = WorkAssignment(self, interaction.user, level, multiplier)
        await interaction.response.send_message(embed=embed, view=view)



    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore bots and DMs
        if message.author.bot or not message.guild:
            return

        # Check for banned/praised words
        content = message.content.lower()
        guild_id = message.guild.id
        user_id = message.author.id

        # Prioritize checking for banned words
        banned_words = db.get_banned_words(guild_id)
        for word, penalty in banned_words:
            if word in content:
                db.add_to_slush_fund(guild_id, abs(penalty))
                db.update_credit(user_id, guild_id, penalty)
                new_score = db.get_credit(user_id, guild_id)
                self.bot.dispatch("social_credit_change", message.author, new_score)
                try:
                    output_channel = await self._get_output_channel(message=message)
                    await output_channel.send(f"🚨 State Violation by {message.author.mention}! {random_banned_word_message()} Use of banned word '{word}' has resulted in a **{abs(penalty):.1f}** credit fine. The fine has been added to the slush fund. New social standing: **{new_score:.1f}**")
                except discord.Forbidden:
                    pass # Can't send messages in this channel
                return # Stop after finding one banned word

        # Check for praised words if no banned words were found
        praised_words = db.get_praised_words(guild_id)
        for word, reward in praised_words:
            if word in content:
                db.update_credit(user_id, guild_id, reward)
                new_score = db.get_credit(user_id, guild_id)
                self.bot.dispatch("social_credit_change", message.author, new_score)
                
                # Only send a message if a bot channel is configured
                output_channel_id = db.get_output_channel(guild_id)
                if output_channel_id:
                    output_channel = message.guild.get_channel(output_channel_id)
                    if output_channel:
                        embed = discord.Embed(
                            title="🎉 Official State Commendation 🎉",
                            description=f"Citizen {message.author.mention} has shown exemplary behavior by using the phrase '{word}'.\nThey have been awarded **{reward}** credits.\n\n*{random_earn_message()}*",
                            color=discord.Color.gold()
                        )
                        embed.set_footer(text=f"New Social Standing: {new_score:.1f}")
                        try:
                            await output_channel.send(embed=embed)
                        except discord.Forbidden:
                            pass # Can't send messages
                return # Stop after finding one praised word

        # If no special words, add standard passive credit
        db.update_credit(user_id, guild_id, 0.1)
        new_score = db.get_credit(user_id, guild_id)

        # Broadcast the change to the Perm Manager (if active)
        self.bot.dispatch("social_credit_change", message.author, new_score)



    @app_commands.command(name="profile", description="Check a citizen's Social Credit tier.")
    @app_commands.describe(member="The citizen to view. Defaults to yourself.")
    async def profile(self, interaction: discord.Interaction, member: discord.Member = None):
        # If no member is specified, default to the user who invoked the command
        if member is None:
            member = interaction.user

        xp = db.get_credit(member.id, interaction.guild.id)
        tier_name, level = self.get_social_status(xp)
        
        btc_balance = mdb.get_btc_balance(member.id, interaction.guild.id)

        color = discord.Color.green() if xp >= 0 else discord.Color.red()
        embed = discord.Embed(title=f"Profile: {member.display_name}", color=color)
        embed.add_field(name="Credits", value=f"{xp:.1f}")
        embed.add_field(name="Status", value=f"Level {level}: {tier_name}")
        embed.add_field(name="El Virtual", value=f"{btc_balance:,.6f} BTC", inline=False)

        await interaction.response.send_message(embed=embed)



    @app_commands.command(name="give", description="Give some of your Social Credit to another citizen.")
    @app_commands.describe(member="The citizen to give credit to", amount="The amount of credit to give")
    async def give(self, interaction: discord.Interaction, member: discord.Member, amount: float):
        giver_id = interaction.user.id
        giver_guild_id = interaction.guild.id
        receiver_id = member.id
        receiver_guild_id = interaction.guild.id

        if giver_id == receiver_id:
            await interaction.response.send_message("You cannot give credits to yourself.", ephemeral=True)
            return

        if amount <= 0:
            await interaction.response.send_message("You must give a positive amount of credits.", ephemeral=True)
            return

        giver_balance = db.get_credit(giver_id, giver_guild_id)

        if giver_balance < amount:
            await interaction.response.send_message(f"You don't have enough credits to give {amount:.1f}. Your balance is {giver_balance:.1f}.", ephemeral=True)
            return

        # Perform the transfer
        db.update_credit(giver_id, giver_guild_id, -amount)
        db.update_credit(receiver_id, receiver_guild_id, amount)

        # Get new scores
        new_giver_score = db.get_credit(giver_id, giver_guild_id)
        new_receiver_score = db.get_credit(receiver_id, receiver_guild_id)

        # Dispatch events to update roles if necessary
        self.bot.dispatch("social_credit_change", interaction.user, new_giver_score)
        self.bot.dispatch("social_credit_change", member, new_receiver_score)

        embed = discord.Embed(
            title="💸 Credit Transfer Successful 💸",
            description=f"{interaction.user.mention} has given **{amount:.1f}** credits to {member.mention}.",
            color=discord.Color.blue()
        )
        embed.add_field(name=f"{interaction.user.display_name}'s New Balance", value=f"{new_giver_score:.1f}")
        embed.add_field(name=f"{member.display_name}'s New Balance", value=f"{new_receiver_score:.1f}")
        
        await interaction.response.send_message("Transfer complete.", ephemeral=True)
        try:
            output_channel = await self._get_output_channel(interaction=interaction)
            await output_channel.send(embed=embed)
        except discord.Forbidden:
            pass



    @app_commands.command(name="decree", description="Issue a decree of gift or debt against another citizen.")
    @app_commands.describe(target="The citizen the decree is against.", amount="The amount to give (positive) or take (negative).", reason="An optional reason for the decree.")
    async def decree(self, interaction: discord.Interaction, target: discord.Member, amount: float, reason: str = None):
        issuer = interaction.user
        guild_id = interaction.guild.id

        if issuer.id == target.id:
            await interaction.response.send_message("You cannot issue a decree against yourself.", ephemeral=True)
            return
        
        if amount == 0:
            await interaction.response.send_message("The amount of a decree cannot be zero.", ephemeral=True)
            return

        issuer_balance = db.get_credit(issuer.id, guild_id)
        target_balance = db.get_credit(target.id, guild_id)

        # Gifting credits
        if amount > 0:
            if issuer_balance < amount:
                await interaction.response.send_message(f"You do not have enough credits to gift {amount:.1f}. Your balance is {issuer_balance:.1f}.", ephemeral=True)
                return
            title = "📜 A Decree of Patronage 📜"
            description = f"{issuer.mention} has decreed a gift of **{amount:.1f}** credits to {target.mention}!"

        # Taking credits
        else: # amount < 0
            abs_amount = abs(amount)
            if target_balance < abs_amount:
                await interaction.response.send_message(f"{target.display_name} does not have enough credits to cover this debt of {abs_amount:.1f}. Their balance is {target_balance:.1f}.", ephemeral=True)
                return
            title = "⚖️ A Decree of Debt ⚖️"
            description = f"{issuer.mention} has decreed a debt of **{abs_amount:.1f}** credits against {target.mention}!"

        # Perform the transfer
        # Issuer loses the amount, target gains the amount.
        # If amount is negative, issuer GAINS credits, target LOSES them.
        db.update_credit(issuer.id, guild_id, -amount) 
        db.update_credit(target.id, guild_id, amount)

        # Get new scores
        new_issuer_score = db.get_credit(issuer.id, guild_id)
        new_target_score = db.get_credit(target.id, guild_id)

        # Dispatch events to update roles if necessary
        self.bot.dispatch("social_credit_change", issuer, new_issuer_score)
        self.bot.dispatch("social_credit_change", target, new_target_score)

        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blue()
        )
        embed.add_field(name=f"{issuer.display_name}'s New Balance", value=f"{new_issuer_score:.1f}")
        embed.add_field(name=f"{target.display_name}'s New Balance", value=f"{new_target_score:.1f}")
        
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        
        await interaction.response.send_message("Your decree has been issued.", ephemeral=True)
        try:
            output_channel = await self._get_output_channel(interaction=interaction)
            await output_channel.send(embed=embed)
        except discord.Forbidden:
            pass



    @app_commands.command(name="heist", description="Attempt to steal credits from another citizen. High risk, high reward.")
    @app_commands.describe(target="The citizen you want to steal from.")
    @app_commands.checks.cooldown(1, 3600, key=lambda i: (i.guild_id, i.user.id))
    async def heist(self, interaction: discord.Interaction, target: discord.Member):
        heister = interaction.user
        guild_id = interaction.guild.id

        # --- Validation Checks ---
        if heister.id == target.id:
            await interaction.response.send_message("You cannot steal from yourself, that's just bad accounting.", ephemeral=True)
            return

        if target.bot:
            await interaction.response.send_message("You cannot steal from The State's loyal machines!", ephemeral=True)
            return

        heister_score = db.get_credit(heister.id, guild_id)
        target_score = db.get_credit(target.id, guild_id)
        
        _, heister_level = self.get_social_status(heister_score)
        _, target_level = self.get_social_status(target_score)

        if heister_score <= 0:
            await interaction.response.send_message("You need positive social credit to attempt a heist. You have nothing to lose.", ephemeral=True)
            return

        if target_score <= 1:
            await interaction.response.send_message(f"{target.display_name} is destitute. There is nothing to steal.", ephemeral=True)
            return

        # --- Success Chance Calculation ---
        base_success_chance = 40.0  # 40%
        # Bonus/penalty based on level difference. Max of 25% bonus or penalty.
        level_difference_bonus = max(-25, min(25, (heister_level - target_level) * 5))
        final_chance = base_success_chance + level_difference_bonus

        # --- Execute Heist ---
        await interaction.response.defer() # Defer response as we have multiple outcomes

        is_success = random.uniform(0, 100) < final_chance
        output_channel = await self._get_output_channel(interaction=interaction)

        if is_success:
            # --- SUCCESS ---
            # Steal between 5% and 15% of the target's score
            stolen_amount = round(target_score * random.uniform(0.05, 0.15), 1)
            
            # Cannot steal more than they have
            stolen_amount = min(stolen_amount, target_score)

            # Update balances
            db.update_credit(heister.id, guild_id, stolen_amount)
            db.update_credit(target.id, guild_id, -stolen_amount)

            # Get new scores
            new_heister_score = db.get_credit(heister.id, guild_id)
            new_target_score = db.get_credit(target.id, guild_id)

            # Dispatch events
            self.bot.dispatch("social_credit_change", heister, new_heister_score)
            self.bot.dispatch("social_credit_change", target, new_target_score)
            
            embed = discord.Embed(
                title="💰 Heist Successful! 💰",
                description=f"{heister.mention} successfully stole **{stolen_amount:.1f}** credits from {target.mention}!",
                color=discord.Color.dark_gold()
            )
            embed.add_field(name="Heister's New Balance", value=f"{new_heister_score:.1f}", inline=True)
            embed.add_field(name="Victim's New Balance", value=f"{new_target_score:.1f}", inline=True)
            await output_channel.send(embed=embed)
            await interaction.followup.send("The deed is done.", ephemeral=True)

        else:
            # --- FAILURE ---
            # Penalty between 20 and 50 credits, scales slightly with level
            penalty_amount = round(random.uniform(20, 50) + abs(heister_level * 2.5), 1)
            
            # Apply penalty and add to slush fund
            db.update_credit(heister.id, guild_id, -penalty_amount)
            db.add_to_slush_fund(guild_id, penalty_amount)
            new_heister_score = db.get_credit(heister.id, guild_id)
            self.bot.dispatch("social_credit_change", heister, new_heister_score)

            embed = discord.Embed(
                title="🚨 Heist Failed! 🚨",
                description=f"{heister.mention} was caught trying to steal from {target.mention} and has been fined **{penalty_amount:.1f}** credits! The fine has been added to the slush fund.",
                color=discord.Color.dark_red()
            )
            embed.add_field(name="Heister's New Balance", value=f"{new_heister_score:.1f}", inline=True)
            embed.set_footer(text=random_fine_message())
            await output_channel.send(embed=embed)
            await interaction.followup.send("You were caught.", ephemeral=True)



    @app_commands.command(name="coinflip", description="Bet your Social Credit on the flip of a coin.")
    @app_commands.describe(amount="The amount of credits to bet (1-500).", guess="Your guess: Heads or Tails.")
    @app_commands.choices(guess=[
        app_commands.Choice(name="Heads", value="heads"),
        app_commands.Choice(name="Tails", value="tails"),
    ])
    @app_commands.checks.cooldown(1, 3600, key=lambda i: (i.guild_id, i.user.id))
    async def coinflip(self, interaction: discord.Interaction, amount: app_commands.Range[float, 1.0, 500.0], guess: app_commands.Choice[str]):
        user = interaction.user
        guild_id = interaction.guild.id

        user_balance = db.get_credit(user.id, guild_id)
        if user_balance < amount:
            await interaction.response.send_message(f"You don't have enough credits to bet {amount:.1f}. Your current balance is {user_balance:.1f}.", ephemeral=True)
            return

        # --- Game Logic ---
        await interaction.response.defer()
        
        result = random.choice(['heads', 'tails'])
        is_win = guess.value == result
        
        output_channel = await self._get_output_channel(interaction=interaction)

        if is_win:
            # --- WIN ---
            db.update_credit(user.id, guild_id, amount)
            new_balance = db.get_credit(user.id, guild_id)
            self.bot.dispatch("social_credit_change", user, new_balance)

            embed = discord.Embed(
                title="🎉 Coinflip Win! 🎉",
                description=f"The coin landed on **{result.capitalize()}**! {user.mention} won **{amount:.1f}** credits!",
                color=discord.Color.green()
            )
            embed.add_field(name="New Balance", value=f"{new_balance:.1f}")

        else:
            # --- LOSS ---
            db.update_credit(user.id, guild_id, -amount)
            new_balance = db.get_credit(user.id, guild_id)
            self.bot.dispatch("social_credit_change", user, new_balance)

            embed = discord.Embed(
                title="💸 Coinflip Loss 💸",
                description=f"The coin landed on **{result.capitalize()}**. {user.mention} lost **{amount:.1f}** credits.",
                color=discord.Color.red()
            )
            embed.add_field(name="New Balance", value=f"{new_balance:.1f}")

        await output_channel.send(embed=embed)
        await interaction.followup.send("Your bet has been settled.", ephemeral=True)



    # --- ADMIN COMMAND: Adjust Credit ---
    @app_commands.command(name="adjust_credit", description="[ADMIN] Manually add or subtract Social Credit.")
    @app_commands.describe(member="The user to adjust", amount="Amount to add (positive) or remove (negative)")
    @app_commands.default_permissions(manage_roles=True)
    async def adjust_credit(self, interaction: discord.Interaction, member: discord.Member, amount: float):
        db.update_credit(member.id, interaction.guild.id, amount)
        new_score = db.get_credit(member.id, interaction.guild.id)
        
        self.bot.dispatch("social_credit_change", member, new_score)
        await interaction.response.send_message("Adjustment processed.", ephemeral=True)
        
        action = "awarded" if amount > 0 else "deducted"
        color = discord.Color.gold() if amount > 0 else discord.Color.dark_red()
        
        embed = discord.Embed(
            title="🚨 Official State Decree 🚨", 
            description=f"Admin {interaction.user.mention} has {action} **{abs(amount)}** credits to {member.mention}.",
            color=color
        )
        embed.add_field(name="New Social Standing", value=f"{new_score:.1f} Credits")
        output_channel = await self._get_output_channel(interaction=interaction)
        await output_channel.send(embed=embed)

    @app_commands.command(name="reset_score", description="[ADMIN] Reset a user's Social Credit to 0.")
    @app_commands.describe(member="The user to reset")
    @app_commands.default_permissions(manage_roles=True)
    async def reset_score(self, interaction: discord.Interaction, member: discord.Member):
        db.reset_score(member.id, interaction.guild.id)
        
        self.bot.dispatch("social_credit_change", member, 0)
        await interaction.response.send_message(f"{member.display_name}'s score has been reset to 0.", ephemeral=True)

        embed = discord.Embed(
            title="🚨 Official State Decree 🚨",
            description=f"Admin {interaction.user.mention} has reset the score of {member.mention} to 0.",
            color=discord.Color.dark_red()
        )
        output_channel = await self._get_output_channel(interaction=interaction)
        await output_channel.send(embed=embed)
        


   # --- INTERACTIVE HELP COMMAND ---
    @app_commands.command(name="help", description="Open the State's interactive instruction manual.")
    async def help_command(self, interaction: discord.Interaction):
        # We start by showing the 'general' page as the default
        embed = discord.Embed(
            title="ℹ️ Social Credit System", 
            description="Welcome to the State. Your worth is measured in Social Credit.\n\nYou earn a passive **+0.1 credit** for every message you send. Good behavior allows you to climb the ranks, but poor behavior or corruption will drag you into the negative tiers.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Basic Commands", value="`/profile` - Check your current status and rank\n`/leaderboard` - View the most compliant (and least compliant) citizens\n`/daily_ration` - Claim your free daily credit allowance")
        
        view = HelpView(self)
        await interaction.response.send_message(embed=embed, view=view)



    # --- LEADERBOARD COMMAND ---
    @app_commands.command(name="leaderboard", description="View the most (and least) compliant citizens in the server.")
    async def leaderboard(self, interaction: discord.Interaction):
        top_users, bottom_users = db.get_leaderboard(interaction.guild.id)
            
        if not top_users:
            await interaction.response.send_message("The State has no records yet. Start chatting!", ephemeral=True)
            return
            
        embed = discord.Embed(title="📜 Official State Registry", color=discord.Color.gold())
        
        top_text = ""
        for index, (user_id, score) in enumerate(top_users, start=1):
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else "Unknown Citizen"
            top_text += f"**{index}.** {name} — **{score:.1f}**\n"
        embed.add_field(name="🏆 Model Citizens", value=top_text, inline=False)
        
        if bottom_users:
            bottom_text = ""
            for index, (user_id, score) in enumerate(bottom_users, start=1):
                member = interaction.guild.get_member(user_id)
                name = member.display_name if member else "Unknown Citizen"
                score_display = f"🚨 **{score:.1f}**" if score < 0 else f"**{score:.1f}**"
                bottom_text += f"**{index}.** {name} — {score_display}\n"
            embed.add_field(name="💀 Most Wanted (State Enemies)", value=bottom_text, inline=False)
            
        embed.set_footer(text=random_leaderboard_message())
        await interaction.response.send_message(embed=embed)

    # --- DAILY RATION COMMAND ---
    @app_commands.command(name="daily_ration", description="Claim your daily allowance of Social Credit from the State.")
    @app_commands.checks.cooldown(1, 86400, key=lambda i: (i.guild_id, i.user.id)) # 1 use per 86400 seconds (24 hours)
    async def daily_ration(self, interaction: discord.Interaction):
        # Grant a random amount between 1.0 and 5.0 credits
        amount = round(random.uniform(1.0, 5.0), 1)
        
        db.update_credit(interaction.user.id, interaction.guild.id, amount)
        new_score = db.get_credit(interaction.user.id, interaction.guild.id)
        
        self.bot.dispatch("social_credit_change", interaction.user, new_score)

        embed = discord.Embed(
            title="🍞 Daily Ration Claimed",
            description=f"The State has graciously awarded you **{amount}** credits.\nYour new standing is **{new_score:.1f}**.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    
    
    
    
    # The main work command (100% payout, 1 hour cooldown)
    @app_commands.command(name="work", description="Perform major labor for the State.")
    @app_commands.checks.cooldown(1, 3600, key=lambda i: (i.guild_id, i.user.id))
    async def work(self, interaction: discord.Interaction):
        await self.trigger_work_scenario(interaction, task_name="work", multiplier=1.0)

# --- 4. THE GLOBAL COOLDOWN HANDLER ---
    # Delete your old @work.error and @daily_ration.error functions and use this instead!
    # This automatically catches cooldowns for EVERY slash command in this Cog so you don't have to write 20 error handlers.
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            mins_left = error.retry_after / 60
            await interaction.response.send_message(f"🚨 The State demands patience. Also we remind you that greed is a crime against the state.  Try this specific task again in **{mins_left:.1f} minutes**.", ephemeral=True)





async def setup(bot):
    await bot.add_cog(SocialCredit(bot))