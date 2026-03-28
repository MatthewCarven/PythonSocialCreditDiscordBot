import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import math
from datetime import datetime, time, timedelta, timezone
from database import CreditDB

# --- Constants ---
TICKET_PRICE = 5.0
TICKET_LIMIT_PER_USER = 10
STATE_TAX = 0.10 # 10%

# Initialize the database connection
db = CreditDB()

class Lottery(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.daily_drawing.start()

    def cog_unload(self):
        self.daily_drawing.cancel()

    # --- Lottery Commands ---
    @app_commands.command(name="lottery", description="Buy tickets or check the status of the State lottery.")
    @app_commands.describe(action="Choose what you want to do.", tickets="Number of tickets to buy (if buying).")
    @app_commands.choices(action=[
        app_commands.Choice(name="Check Status", value="status"),
        app_commands.Choice(name="Buy Tickets", value="buy"),
    ])
    async def lottery(self, interaction: discord.Interaction, action: app_commands.Choice[str], tickets: app_commands.Range[int, 1, TICKET_LIMIT_PER_USER] = None):
        if action.value == "buy":
            if tickets is None:
                await interaction.response.send_message("You must specify how many tickets you want to buy.", ephemeral=True)
                return
            await self.buy_tickets(interaction, tickets)
        elif action.value == "status":
            await self.check_status(interaction)

    async def buy_tickets(self, interaction: discord.Interaction, tickets: int):
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        cost = tickets * TICKET_PRICE

        # Check if user can afford the tickets
        user_balance = db.get_credit(user_id, guild_id)
        if user_balance < cost:
            await interaction.response.send_message(f"You need **{cost:.1f}** credits to buy {tickets} ticket(s), but you only have **{user_balance:.1f}**.", ephemeral=True)
            return

        # Check if user will exceed the ticket limit
        user_ticket_count = db.get_user_ticket_count(guild_id, user_id)
        if (user_ticket_count + tickets) > TICKET_LIMIT_PER_USER:
            await interaction.response.send_message(f"You can only hold a maximum of **{TICKET_LIMIT_PER_USER}** tickets. You already have **{user_ticket_count}**.", ephemeral=True)
            return

        # Process the purchase
        db.update_credit(user_id, guild_id, -cost)
        db.add_lottery_tickets(guild_id, user_id, tickets)

        embed = discord.Embed(
            title="🎟️ Lottery Tickets Purchased 🎟️",
            description=f"You have successfully purchased **{tickets}** lottery ticket(s) for **{cost:.1f}** credits.",
            color=discord.Color.green()
        )
        new_balance = user_balance - cost
        embed.add_field(name="Your New Balance", value=f"{new_balance:.1f} credits")
        embed.set_footer(text="May fortune favor your loyalty to the State.")
        await interaction.response.send_message(embed=embed)


    async def check_status(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        user_id = interaction.user.id

        total_tickets = db.count_lottery_tickets(guild_id)
        user_tickets = db.get_user_ticket_count(guild_id, user_id)
        
        pot_size = total_tickets * TICKET_PRICE
        prize_pool = pot_size * (1 - STATE_TAX)

        # Calculate time until next drawing (set for midnight UTC)
        now_utc = datetime.now(timezone.utc)
        next_draw_time = (now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        time_remaining = next_draw_time - now_utc

        embed = discord.Embed(
            title="📊 State Lottery Status 📊",
            description="The official daily drawing for all loyal citizens.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Current Prize Pool", value=f"**{prize_pool:.1f}** credits", inline=True)
        embed.add_field(name="Total Tickets Sold", value=f"{total_tickets}", inline=True)
        embed.add_field(name="Your Tickets", value=f"{user_tickets}", inline=True)
        embed.add_field(name="Next Drawing In", value=f"{str(time_remaining).split('.')[0]}", inline=False)
        
        await interaction.response.send_message(embed=embed)


    @app_commands.command(name="slushfund", description="View the State's discretionary slush fund.")
    async def slushfund(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        fund_balance = db.get_slush_fund(guild_id)

        embed = discord.Embed(
            title="💰 State Slush Fund 💰",
            description="The discretionary treasury of the State.",
            color=discord.Color.gold()
        )
        embed.add_field(name="Current Balance", value=f"**{fund_balance:.1f}** credits")
        embed.set_footer(text="This fund is supported by taxes and other state-run enterprises.")
        
        await interaction.response.send_message(embed=embed)

    # --- Daily Drawing Task ---
    @tasks.loop(time=time(0, 0, tzinfo=timezone.utc)) # Runs at midnight UTC
    async def daily_drawing(self):
        print("--- Running Daily Lottery Drawing ---")
        # Iterate over all guilds the bot is in
        for guild in self.bot.guilds:
            guild_id = guild.id
            all_entries = db.get_all_lottery_entries(guild_id)

            if not all_entries:
                print(f"No lottery tickets sold in '{guild.name}'. Skipping draw.")
                continue

            # --- Announce winner and distribute prize ---
            output_channel_id = db.get_output_channel(guild_id)
            if not output_channel_id:
                print(f"No output channel set for '{guild.name}'. Cannot announce lottery winner.")
                continue
            
            output_channel = guild.get_channel(output_channel_id)
            if not output_channel:
                print(f"Could not find output channel for '{guild.name}'.")
                continue

            # Calculate pot and pick winner
            total_tickets = len(all_entries)
            pot_size = total_tickets * TICKET_PRICE
            tax_amount = pot_size * STATE_TAX
            prize_amount = pot_size - tax_amount

            winner_id = random.choice(all_entries)
            winner_member = guild.get_member(winner_id)

            # Update balances
            db.update_credit(winner_id, guild_id, prize_amount)
            db.add_to_slush_fund(guild_id, tax_amount)

            # Announce the winner
            embed = discord.Embed(
                title="🎉 State Lottery Winner! 🎉",
                description=f"The daily drawing has concluded! Out of **{total_tickets}** total entries, a winner has been chosen.",
                color=discord.Color.gold()
            )
            winner_name = winner_member.mention if winner_member else f"Citizen ID: {winner_id}"
            embed.add_field(name="🏆 Grand Prize Winner", value=winner_name, inline=False)
            embed.add_field(name="💰 Prize Awarded", value=f"**{prize_amount:.1f}** credits", inline=False)
            embed.set_footer(text=f"{tax_amount:.1f} credits have been collected as State Tax.")

            try:
                await output_channel.send(embed=embed)
                print(f"Announced lottery winner in '{guild.name}'.")
            except discord.Forbidden:
                print(f"Failed to announce lottery winner in '{guild.name}' due to permissions.")

            # Clear tickets for the next round
            db.clear_lottery_tickets(guild_id)
        print("--- Daily Lottery Drawing Complete ---")


async def setup(bot):
    await bot.add_cog(Lottery(bot))
